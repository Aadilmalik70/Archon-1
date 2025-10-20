# AI-PM Implementation: Dependencies & Risk Analysis

## Dependency Graph

### Critical Path Analysis

```
Database Schema (Week 1)
├── Core Tables (1.1.1) ────────┐
├── Integration Tables (1.1.2) ─┤
└── Task Extensions (1.1.3) ────┤
                                │
                                ├──→ Slack Integration (1.2)
                                │    ├── OAuth Flow (1.2.1)
                                │    ├── Service Layer (1.2.2)
                                │    ├── Event Listener (1.2.3)
                                │    └── API Routes (1.2.4)
                                │
                                ├──→ Asana Integration (1.3)
                                │    ├── OAuth Flow (1.3.1)
                                │    ├── Sync Service (1.3.2)
                                │    ├── Webhook Handler (1.3.3)
                                │    └── API Routes (1.3.4)
                                │
                                └──→ AI Agent System (Week 3-4)
                                     ├── Orchestrator (2.1)
                                     ├── Coding Agent (2.2)
                                     ├── QA Agent (2.3)
                                     └── Docs Agent (2.4)
                                            │
                                            └──→ Execution System (Week 5)
                                                 ├── Context Service (3.1)
                                                 └── Execution Engine (3.2)
                                                        │
                                                        └──→ UI Dashboard (Week 6)
                                                             └──→ Automation (Week 7)
```

### Parallel Work Streams

**Stream 1: Database & Backend Foundation (Week 1-2)**
- Database migrations (sequential)
- Slack integration (parallel after DB)
- Asana integration (parallel after DB)

**Stream 2: AI Agents (Week 3-4)**
- Orchestrator (prerequisite for others)
- Coding/QA/Docs agents (parallel after orchestrator)

**Stream 3: Frontend (Week 6)**
- Can start after API routes defined (Week 2-5)
- Parallel with automation workflows

---

## Technical Dependencies

### External Services

| Service | Purpose | Critical Path | Setup Time | Docs |
|---------|---------|---------------|------------|------|
| **Slack API** | Messaging, notifications | Yes (1.2) | 2 hours | https://api.slack.com/docs |
| **Asana API** | Task sync | Yes (1.3) | 2 hours | https://developers.asana.com |
| **OpenAI API** | Agent LLMs | Yes (2.x) | Existing | https://platform.openai.com |
| **GitHub API** | Code context | Optional | 1 hour | https://docs.github.com/rest |
| **Supabase** | Database | Yes (all) | Existing | - |

### Internal Dependencies

| Component | Depends On | Blocks | Status |
|-----------|------------|--------|--------|
| **BaseAgent** | PydanticAI, rate limiting | All agents | ✅ Exists |
| **Supabase Client** | Database connection | All data ops | ✅ Exists |
| **Service Layer Pattern** | FastAPI, Supabase | All services | ✅ Exists |
| **TanStack Query** | React Query v5 | All UI | ✅ Exists |
| **ETag System** | apiClient | Polling optimization | ✅ Exists |
| **Vertical Slices** | Feature structure | UI organization | ✅ Exists |

---

## Risk Assessment Matrix

### High Priority Risks

#### 1. OAuth Token Management
**Risk Level**: 🔴 High
**Probability**: 80%
**Impact**: Service unavailable, sync failures

**Details**:
- Slack tokens expire after workspace revokes access
- Asana tokens expire after 1 hour without refresh
- Users may disconnect integrations

**Mitigation Strategy**:
```python
# Implement automatic token refresh
class TokenRefreshService:
    async def refresh_if_needed(self, credential_id: str):
        """Check expiration and refresh before use"""
        cred = await self.get_credential(credential_id)

        if cred.expires_at and cred.expires_at < datetime.now() + timedelta(minutes=5):
            # Refresh 5 minutes before expiration
            new_token = await self.refresh_token(cred)
            await self.update_credential(credential_id, new_token)

        return cred

# Add monitoring
async def monitor_token_health():
    """Check all tokens daily"""
    expiring = await db.query(
        "SELECT * FROM integration_credentials WHERE expires_at < NOW() + INTERVAL '7 days'"
    )

    for cred in expiring:
        await notify_admin(f"Token expiring soon: {cred.service_name}")
```

**Acceptance Criteria**:
- [ ] Automatic refresh 5 minutes before expiration
- [ ] Admin notification 7 days before expiration
- [ ] Graceful degradation if refresh fails
- [ ] User notification in UI if token invalid

---

#### 2. AI Agent Rate Limiting
**Risk Level**: 🔴 High
**Probability**: 90%
**Impact**: Failed executions, poor UX

**Details**:
- OpenAI rate limits: 10,000 TPM (tokens per minute) on tier 1
- PydanticAI doesn't have built-in queue system
- Multiple agents running concurrently
- Contextual embeddings also consume quota

**Current BaseAgent Implementation**:
```python
# Existing rate limiter in BaseAgent
class RateLimitHandler:
    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.min_request_interval = 0.1  # 100ms between requests

    async def execute_with_rate_limit(self, func, *args, **kwargs):
        """Exponential backoff on 429 errors"""
        # Waits 1s, 2s, 4s, 8s, 16s on retries
```

**Enhanced Mitigation Strategy**:
```python
# Add global rate limit coordinator
class GlobalRateLimiter:
    """Coordinate rate limits across all agents"""

    def __init__(self):
        self.token_bucket = asyncio.Semaphore(100)  # Max 100 concurrent requests
        self.tpm_tracker = TPMTracker(limit=10000)  # Track tokens per minute

    async def acquire(self, estimated_tokens: int):
        """Acquire permission to make request"""
        async with self.token_bucket:
            # Wait if we're approaching TPM limit
            await self.tpm_tracker.wait_if_needed(estimated_tokens)

            # Track this request
            self.tpm_tracker.record(estimated_tokens)

            yield

    async def release(self):
        """Release rate limit slot"""
        pass

# Use in agents
class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.rate_limiter = GlobalRateLimiter()

    async def _run_agent(self, prompt: str, deps):
        estimated_tokens = len(prompt.split()) * 2  # Rough estimate

        async with self.rate_limiter.acquire(estimated_tokens):
            return await super()._run_agent(prompt, deps)
```

**Acceptance Criteria**:
- [ ] Global rate limiter coordinates all agents
- [ ] TPM tracking prevents quota exhaustion
- [ ] Queue system for burst requests
- [ ] Admin dashboard shows rate limit usage
- [ ] Alerts when approaching limits

---

#### 3. Asana Sync Conflicts
**Risk Level**: 🟡 Medium
**Probability**: 60%
**Impact**: Data inconsistency, lost updates

**Details**:
- Bidirectional sync can cause conflicts
- User updates in Asana while agent updates in Archon
- Network delays cause race conditions
- Webhook delivery order not guaranteed

**Conflict Scenarios**:
```
Scenario 1: Simultaneous Updates
─────────────────────────────────
T0: Task status = "todo" (both systems)
T1: User changes to "doing" in Asana
T2: Agent changes to "done" in Archon
T3: Asana webhook arrives (→ "doing")
T4: Archon sync pushes "done" to Asana
Result: Data loss, user confused
```

**Mitigation Strategy**:
```python
class SyncConflictResolver:
    """Resolve bidirectional sync conflicts"""

    async def sync_task_status(
        self,
        archon_task_id: str,
        asana_task_id: str,
        source: str,  # 'asana' or 'archon'
        new_status: str
    ):
        # Get current state from both systems
        archon_task = await self.get_archon_task(archon_task_id)
        asana_task = await self.get_asana_task(asana_task_id)

        # Check for conflict
        if archon_task.updated_at != asana_task.modified_at:
            # Conflict detected
            await self.log_conflict({
                "archon_task_id": archon_task_id,
                "asana_task_id": asana_task_id,
                "archon_status": archon_task.status,
                "asana_status": asana_task.status,
                "source": source,
                "new_status": new_status
            })

            # Apply conflict resolution strategy
            resolution = await self.resolve_conflict(
                archon_task, asana_task, source, new_status
            )

            return resolution

        # No conflict, apply update
        if source == 'asana':
            await self.update_archon_task(archon_task_id, new_status)
        else:
            await self.update_asana_task(asana_task_id, new_status)

    async def resolve_conflict(self, archon_task, asana_task, source, new_status):
        """
        Conflict Resolution Strategies:
        1. Last-write-wins (default)
        2. Source-priority (Asana wins)
        3. Human intervention (flag for review)
        """
        strategy = await self.get_sync_strategy()

        if strategy == 'last_write_wins':
            # Compare timestamps
            if source == 'asana':
                winner = asana_task
            else:
                winner = archon_task

        elif strategy == 'asana_priority':
            # Asana is source of truth
            winner = asana_task if source == 'asana' else None

        elif strategy == 'human_review':
            # Create conflict record for human review
            await self.create_conflict_ticket({
                "archon_task": archon_task,
                "asana_task": asana_task,
                "source": source,
                "status": "pending_review"
            })
            return {"status": "conflict", "action": "pending_review"}

        # Apply winning change
        if winner:
            await self.apply_resolution(winner, archon_task, asana_task)

        return {"status": "resolved", "winner": winner.source}
```

**Acceptance Criteria**:
- [ ] Conflicts detected with timestamp comparison
- [ ] All conflicts logged to task_sync_log table
- [ ] Configurable resolution strategy (UI setting)
- [ ] Admin UI shows conflicts and resolution
- [ ] Webhook idempotency prevents duplicate processing

---

#### 4. Agent Execution Timeouts
**Risk Level**: 🟡 Medium
**Probability**: 40%
**Impact**: Incomplete tasks, wasted API calls

**Details**:
- Complex code generation can take >2 minutes
- BaseAgent has 120s timeout
- Large files slow down processing
- Network issues cause delays

**Current Implementation**:
```python
# From base_agent.py
async def _run_agent(self, user_prompt: str, deps: DepsT) -> OutputT:
    try:
        result = await asyncio.wait_for(
            self._agent.run(user_prompt, deps=deps),
            timeout=120.0,  # 2 minute timeout
        )
        return result.data
    except asyncio.TimeoutError:
        raise Exception(f"Agent {self.name} operation timed out")
```

**Enhanced Mitigation**:
```python
class AgentExecutionService:
    """Manage long-running agent executions"""

    async def execute_with_checkpoints(
        self,
        agent: BaseAgent,
        task_id: str,
        prompt: str,
        deps: Any
    ):
        """Execute agent with progress checkpoints"""

        # Create execution record
        execution_id = await self.create_execution(task_id, agent.name)

        try:
            # Use streaming for long operations
            async with agent.run_stream(prompt, deps) as stream:
                full_result = ""
                last_checkpoint = datetime.now()

                async for chunk in stream:
                    full_result += chunk

                    # Save checkpoint every 30 seconds
                    if (datetime.now() - last_checkpoint).seconds > 30:
                        await self.save_checkpoint(execution_id, full_result)
                        last_checkpoint = datetime.now()

            # Mark complete
            await self.complete_execution(execution_id, full_result)
            return full_result

        except asyncio.TimeoutError:
            # Try to recover partial result
            partial = await self.get_latest_checkpoint(execution_id)

            if partial:
                await self.fail_execution(
                    execution_id,
                    "Timeout - partial result saved"
                )
                return {"status": "partial", "data": partial}
            else:
                await self.fail_execution(execution_id, "Timeout - no progress")
                raise
```

**Acceptance Criteria**:
- [ ] Streaming execution for long operations
- [ ] Progress checkpoints every 30 seconds
- [ ] Partial results recoverable on timeout
- [ ] Configurable timeout per agent type
- [ ] UI shows execution progress

---

### Medium Priority Risks

#### 5. Database Migration Failures
**Risk Level**: 🟡 Medium
**Probability**: 30%
**Impact**: Development blocked, data loss

**Mitigation**:
```sql
-- Always create rollback scripts
-- migration/ai_pm/001_core_tables.sql
BEGIN;

-- Migration
CREATE TABLE ai_pm_executions (...);

-- Test insertion
INSERT INTO ai_pm_executions (task_id, agent_type, status)
VALUES (NULL, 'test', 'pending');

-- Rollback if fails
ROLLBACK;

-- File: migration/ai_pm/rollback_001_core_tables.sql
DROP TABLE IF EXISTS ai_pm_executions CASCADE;
DROP TABLE IF EXISTS agent_configurations CASCADE;
```

**Process**:
1. Test migration on local database
2. Create rollback script
3. Backup production data
4. Apply migration
5. Verify with test queries
6. Keep rollback script for 7 days

---

#### 6. Webhook Delivery Failures
**Risk Level**: 🟡 Medium
**Probability**: 50%
**Impact**: Missed events, sync delays

**Details**:
- Slack/Asana webhooks can fail
- Network issues cause missed events
- No built-in retry from external services
- Duplicate webhook delivery possible

**Mitigation**:
```python
class WebhookHandler:
    """Reliable webhook processing"""

    async def process_webhook(
        self,
        service: str,
        event_id: str,
        payload: dict
    ):
        # Check for duplicate (idempotency)
        if await self.is_duplicate(service, event_id):
            logger.info(f"Duplicate webhook: {event_id}")
            return {"status": "duplicate"}

        # Store event
        await self.store_event(service, event_id, payload)

        try:
            # Process with timeout
            result = await asyncio.wait_for(
                self.handle_event(service, payload),
                timeout=30.0
            )

            # Mark processed
            await self.mark_processed(service, event_id)
            return result

        except Exception as e:
            # Queue for retry
            await self.queue_retry(service, event_id, payload)
            raise

    async def retry_failed_webhooks(self):
        """Background task to retry failed webhooks"""
        failed = await self.get_failed_events()

        for event in failed:
            try:
                await self.handle_event(event.service, event.payload)
                await self.mark_processed(event.service, event.event_id)
            except Exception as e:
                logger.error(f"Retry failed: {event.event_id}")
```

**Acceptance Criteria**:
- [ ] Idempotency check prevents duplicates
- [ ] All webhooks logged to database
- [ ] Failed webhooks retry up to 3 times
- [ ] Admin UI shows webhook status
- [ ] Alerts for repeated failures

---

### Low Priority Risks

#### 7. UI State Inconsistency
**Risk Level**: 🟢 Low
**Probability**: 20%
**Impact**: UI confusion, requires refresh

**Mitigation**: Existing TanStack Query handles this well
- Optimistic updates with rollback
- Smart polling with ETag caching
- Automatic retries on failure

---

#### 8. External API Changes
**Risk Level**: 🟢 Low
**Probability**: 10%
**Impact**: Integration breaks

**Mitigation**:
- Version API clients
- Monitor API changelog
- Integration tests detect changes
- Graceful degradation on incompatibility

---

## Dependency Installation Requirements

### Backend Dependencies

Add to `python/pyproject.toml`:
```toml
[project]
dependencies = [
    # Existing...
    "httpx>=0.27.0",          # For Slack/Asana API calls
    "bcrypt>=4.1.0",          # For token encryption
    "python-jose>=3.3.0",     # For JWT handling (OAuth)
]
```

### Environment Variables

Add to `.env`:
```bash
# Slack Integration
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret
SLACK_SIGNING_SECRET=your_slack_signing_secret

# Asana Integration
ASANA_CLIENT_ID=your_asana_client_id
ASANA_CLIENT_SECRET=your_asana_client_secret

# Agent Configuration
AI_PM_ENABLED=true
MAX_CONCURRENT_AGENTS=5
AGENT_TIMEOUT_SECONDS=180
```

---

## Success Metrics & Monitoring

### Key Performance Indicators

| Metric | Target | Measurement |
|--------|--------|-------------|
| Agent success rate | >90% | Completed / Total executions |
| Sync latency | <30s | Time from Asana update to Archon |
| Webhook delivery | >99% | Received / Expected |
| Token refresh success | >99.9% | Successful refreshes / Attempts |
| Average execution time | <60s | Mean agent execution duration |

### Monitoring Strategy

```python
# Add to execution service
class ExecutionMonitoring:
    """Track agent execution metrics"""

    async def record_execution(self, execution_id: str, metrics: dict):
        """Record execution metrics for monitoring"""
        await db.table("ai_pm_execution_metrics").insert({
            "execution_id": execution_id,
            "agent_type": metrics["agent_type"],
            "duration_seconds": metrics["duration"],
            "tokens_used": metrics["tokens"],
            "success": metrics["success"],
            "timestamp": datetime.now()
        })

    async def get_daily_stats(self) -> dict:
        """Get daily execution statistics"""
        return await db.query("""
            SELECT
                agent_type,
                COUNT(*) as total,
                AVG(duration_seconds) as avg_duration,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                SUM(tokens_used) as total_tokens
            FROM ai_pm_execution_metrics
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY agent_type
        """)
```

---

## Rollout Strategy

### Phase 1: Internal Testing (Week 1-2)
- Deploy to staging
- Test with 1-2 sample projects
- Validate all integrations
- Fix critical bugs

### Phase 2: Limited Beta (Week 3-4)
- Enable for 5 projects
- Monitor metrics closely
- Gather user feedback
- Iterate on UX

### Phase 3: Full Rollout (Week 5-7)
- Enable for all projects
- Monitor scaling issues
- Optimize performance
- Document lessons learned

---

## Next Actions

**Immediate (This Week)**:
1. Set up Slack app in workspace
2. Set up Asana developer app
3. Run database migrations on local
4. Create environment variables

**Short-term (Next 2 Weeks)**:
1. Implement OAuth flows
2. Build service layers
3. Create webhook handlers
4. Develop orchestrator agent

**Long-term (Weeks 3-7)**:
1. Specialist agents
2. UI dashboard
3. Automation workflows
4. Performance optimization

Would you like me to:
1. Create the actual migration SQL files
2. Build the Slack integration (OAuth + service)
3. Implement the orchestrator agent
4. Create the API route specifications
5. Build the frontend components

Choose your next priority!
