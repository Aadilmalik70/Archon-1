# Phase 1: Full Implementation - No Mocks

## ✅ Completed So Far (3 hours)

### Slack Integration (75% Complete)
- ✅ `slack_client.py` - Full Slack API wrapper (370 lines)
- ✅ `slack_oauth.py` - Complete OAuth flow with token encryption (280 lines)
- ✅ `slack_service.py` - Business logic layer (330 lines)
- ⏳ `slack_events.py` - Webhook event handling (NEXT)
- ⏳ API routes in `slack_api.py` (NEXT)

## 🚧 Remaining for Full Phase 1 (8-10 hours)

### 1. Slack Event Handlers (1-2 hours)
**File**: `slack_events.py`
- Webhook signature verification
- Event routing (message, command, interaction)
- Slash command handlers (`/aipm`, `/task`)
- Interactive button/modal handling
- Rate limiting and deduplication

### 2. Slack API Routes (1 hour)
**File**: `api_routes/slack_api.py`
- POST `/api/integrations/slack/oauth/callback`
- POST `/api/integrations/slack/events`
- GET `/api/integrations/slack/channels`
- POST `/api/integrations/slack/link-channel`
- DELETE `/api/integrations/slack/disconnect`
- GET `/api/integrations/slack/test`

### 3. Asana Complete Integration (5-6 hours)

#### Asana Client (1 hour)
**File**: `asana/asana_client.py`
- Task CRUD operations
- Project queries
- Custom field management
- Attachment handling
- Error handling with rate limits

#### Asana OAuth (1 hour)
**File**: `asana/asana_oauth.py`
- OAuth 2.0 flow
- Token refresh (Asana tokens expire after 1 hour!)
- Secure storage
- Auto-refresh logic

#### Asana Sync Service (2 hours)
**File**: `asana/asana_sync.py`
- Bidirectional sync logic
- Conflict resolution (last-write-wins with logging)
- Field mapping (Archon status ↔ Asana sections)
- Batch sync operations
- Sync error recovery

#### Asana Webhooks (1 hour)
**File**: `asana/asana_webhook.py`
- Webhook signature verification
- Event processing (task created/updated/deleted)
- Idempotency handling
- Failed event retry queue

#### Asana API Routes (1 hour)
**File**: `api_routes/asana_api.py`
- OAuth callback
- Workspace/project listing
- Project linking
- Manual sync trigger
- Webhook endpoint

### 4. Update Integration Tools (1 hour)
**File**: `agents/product_manager/tools/integration_tools.py`
- Replace all TODO/placeholder code
- Wire up actual SlackService calls
- Wire up actual Asana sync calls
- Add error handling and retries

### 5. Configuration & Environment (30 min)
**Files**: `.env.example`, `config/integrations.py`
- Environment variable templates
- Configuration validation
- Secrets management setup
- Integration health checks

### 6. Integration Tests (2 hours)
**Files**: `tests/integrations/`
- Slack OAuth flow test
- Slack message sending test
- Asana sync test
- Webhook handling test
- End-to-end workflow test

### 7. Documentation (1 hour)
**Files**: Various READMEs
- Setup instructions for Slack app
- Setup instructions for Asana app
- Configuration guide
- Troubleshooting guide
- API documentation

## 📋 Detailed Implementation Checklist

### Slack Events (`slack_events.py`)
- [ ] HMAC signature verification using `SLACK_SIGNING_SECRET`
- [ ] Event deduplication (store event IDs)
- [ ] Slash command parser `/aipm create feature: X`
- [ ] Interactive button handler (approve/reject tasks)
- [ ] Modal submission handler (task details)
- [ ] URL verification for Slack app setup
- [ ] Rate limiting (max 10 events/second per workspace)

### Asana Client (`asana_client.py`)
- [ ] Base client with retry logic
- [ ] `get_workspaces()` - List user's workspaces
- [ ] `get_projects(workspace_id)` - List projects
- [ ] `create_task(data)` - Create task with custom fields
- [ ] `update_task(gid, data)` - Update task
- [ ] `get_task(gid)` - Get task details
- [ ] `delete_task(gid)` - Delete/archive task
- [ ] `add_comment(task_gid, text)` - Add comment
- [ ] Handle Asana rate limits (150 req/min)

### Asana OAuth (`asana_oauth.py`)
- [ ] Authorization URL generation
- [ ] Token exchange
- [ ] Refresh token flow (tokens expire after 1 hour!)
- [ ] Auto-refresh before expiration
- [ ] Secure token storage
- [ ] Token revocation

### Asana Sync (`asana_sync.py`)
- [ ] Field mapping configuration
  - `todo` ↔ Asana section "To Do"
  - `doing` ↔ Asana section "In Progress"
  - `review` ↔ Asana section "Review"
  - `done` ↔ Asana section "Done"
- [ ] Sync Archon → Asana (outbound)
- [ ] Sync Asana → Archon (inbound)
- [ ] Conflict detection (timestamp comparison)
- [ ] Conflict resolution (last-write-wins)
- [ ] Conflict logging to `task_sync_log`
- [ ] Batch sync for initial setup
- [ ] Incremental sync for updates

### Asana Webhooks (`asana_webhook.py`)
- [ ] Webhook creation/management
- [ ] Signature verification
- [ ] Event parsing
- [ ] Idempotency (check `task_sync_log`)
- [ ] Event handlers:
  - [ ] Task created
  - [ ] Task changed (status, assignee, description)
  - [ ] Task deleted
  - [ ] Comment added
- [ ] Retry failed events (3 attempts)
- [ ] Dead letter queue for permanent failures

## 🎯 Implementation Order (Optimized)

### Session 1: Complete Slack (2-3 hours)
1. `slack_events.py` (1 hour)
2. `slack_api.py` routes (1 hour)
3. Update `integration_tools.py` for Slack (30 min)
4. Test Slack OAuth + messaging (30 min)

**Deliverable**: Full working Slack integration

### Session 2: Asana Client & OAuth (2 hours)
1. `asana_client.py` (1 hour)
2. `asana_oauth.py` with refresh logic (1 hour)

**Deliverable**: Can connect to Asana and make API calls

### Session 3: Asana Sync & Webhooks (3 hours)
1. `asana_sync.py` with conflict resolution (2 hours)
2. `asana_webhook.py` (1 hour)

**Deliverable**: Bidirectional sync working

### Session 4: Integration & Testing (3 hours)
1. `asana_api.py` routes (1 hour)
2. Update `integration_tools.py` for Asana (30 min)
3. Integration tests (1.5 hours)

**Deliverable**: Full Phase 1 complete with tests

### Session 5: Documentation & Polish (1 hour)
1. Setup guides
2. API documentation
3. Troubleshooting docs

**Deliverable**: Production-ready Phase 1

## ⚠️ Critical Implementation Notes

### Token Security
- **Slack**: Bot tokens don't expire but can be revoked
- **Asana**: Tokens expire after 1 hour - MUST implement refresh
- **Storage**: Use encrypted storage + environment secrets
- **Production**: Move to AWS Secrets Manager / HashiCorp Vault

### Rate Limiting
- **Slack**: Tier-based (varies by method, ~1 req/sec typical)
- **Asana**: 150 requests/minute per token
- **Implementation**: Exponential backoff with jitter
- **Monitoring**: Log rate limit hits for capacity planning

### Webhook Security
- **Slack**: HMAC-SHA256 signature with signing secret
- **Asana**: X-Hook-Secret header verification
- **Both**: Timestamp validation (reject old events)
- **Idempotency**: Check event_id before processing

### Conflict Resolution
- **Strategy**: Last-write-wins (compare `updated_at`)
- **Logging**: All conflicts logged to `task_sync_log`
- **Notification**: Alert on conflicts via Slack
- **Manual Override**: UI to manually resolve conflicts

### Error Handling
- **Transient**: Retry with exponential backoff (3 attempts)
- **Rate Limits**: Wait and retry after rate limit window
- **Auth Errors**: Invalidate token, notify user to reconnect
- **Network**: Circuit breaker pattern (5 failures → pause 5 min)

## 📊 Testing Strategy

### Unit Tests
- OAuth flows (mocked HTTP)
- Sync logic (conflict scenarios)
- Webhook signature verification
- Field mapping

### Integration Tests
- OAuth roundtrip (requires test apps)
- Message sending
- Task creation/update
- Webhook delivery

### E2E Tests
1. Create task in Archon → Appears in Asana
2. Update task in Asana → Updates in Archon
3. Conflict scenario → Logged correctly
4. Slash command in Slack → Creates tasks

## 🚀 Ready to Continue?

I'll implement all remaining components with:
- ✅ No mocks or placeholders
- ✅ Full error handling
- ✅ Proper rate limiting
- ✅ Security best practices
- ✅ Comprehensive tests
- ✅ Production-ready code

**Next command options**:
1. "Continue with Slack events and API routes" (2-3 hours)
2. "Build complete Asana integration" (5-6 hours)
3. "Do everything in order" (8-10 hours, I'll update progress)

Which would you like?
