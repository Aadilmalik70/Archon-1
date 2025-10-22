# AI-PM Orchestration MVP Plan

**Status**: Ready for Implementation
**Target**: End-to-end workflow from Slack → AI-PM → Claude Code → Slack
**Estimated Time**: 6-8 hours

---

## 🎯 MVP Goal

Build a complete workflow where:

1. User sends message to Slack: `/aipm create feature: Fix authentication bug`
2. AI-PM Orchestrator analyzes with GitHub context
3. Breaks down into atomic tasks and stores in database
4. Notifies Slack with breakdown summary + link to tasks
5. Claude Code (via MCP) picks up tasks automatically
6. Executes tasks and reports progress back to Slack
7. Final completion summary sent to Slack

---

## ✅ What We Already Have

### Infrastructure (100% Ready)
- ✅ **Slack Integration**: OAuth, webhooks, `/aipm` command handler
- ✅ **MCP Server**: Task tools, RAG tools, project tools (port 8051)
- ✅ **Orchestrator Agent**: PydanticAI agent with GPT-4o for task breakdown
- ✅ **GitHub Service**: Repo cloning, file analysis, code extraction
- ✅ **Database**: Supabase with task tables, RLS policies
- ✅ **Notification System**: Slack message sending, Block Kit formatting

### MCP Tools Available for Claude Code
```
✓ list_tasks() - Search, filter, get tasks
✓ manage_task() - Create, update, delete tasks
✓ rag_search_knowledge_base() - Semantic search
✓ rag_search_code_examples() - Code snippet search
✓ list_projects() - Project management
✓ manage_document() - Document management
```

---

## 🚧 What Needs to Be Built (MVP Scope)

### 1. GitHub Context Integration (2 hours)
**File**: `python/src/server/services/github/github_context_service.py` (NEW)

**Purpose**: Extract relevant context from GitHub for orchestrator

**Functions**:
```python
async def get_repo_context(
    repo_url: str,
    feature_description: str,
    repo_branch: str = "main"
) -> dict:
    """
    Get GitHub context for feature planning.

    Returns:
        {
            "relevant_files": [...],  # Files related to feature
            "file_structure": {...},  # Directory tree
            "dependencies": [...],    # Package dependencies
            "similar_code": [...]     # RAG search results
        }
    """
```

**Implementation**:
- Clone repo using GitHubService
- Use RAG to find similar code patterns
- Analyze file structure
- Extract dependencies from package.json/pyproject.toml
- Return structured context dict

---

### 2. Complete Slack Command Handler (1 hour)
**File**: `python/src/server/integrations/slack/slack_events.py` (UPDATE)

**Current**: Line 400 has `# TODO: Trigger orchestrator agent asynchronously`

**Complete**:
```python
async def _handle_create_command(args: str, channel_id: str, user_id: str):
    # ... existing code ...

    # NEW: Trigger orchestrator
    from ...services.github.github_context_service import get_repo_context
    from ....agents.product_manager.orchestrator_agent import plan_feature

    # Get project info
    project = supabase.table("archon_projects").select("*").eq("id", project_id).single()

    # Get GitHub context if repo linked
    code_context = {}
    if project.github_repo:
        code_context = await get_repo_context(
            repo_url=project.github_repo,
            feature_description=description
        )

    # Plan feature with orchestrator
    breakdown = await plan_feature(
        feature_description=description,
        project_id=project_id,
        code_context=code_context
    )

    # Create tasks in database via MCP client
    from ....agents.mcp_client import get_mcp_client
    mcp = await get_mcp_client()

    for task in breakdown.subtasks:
        await mcp.manage_task(
            action="create",
            project_id=project_id,
            title=task.title,
            description=task.description,
            status="todo",
            metadata={
                "assigned_agent": task.assigned_agent,
                "acceptance_criteria": task.acceptance_criteria,
                "files_affected": task.files_affected
            }
        )

    # Send breakdown to Slack
    await SlackService.send_breakdown_summary(
        channel_id=channel_id,
        breakdown=breakdown,
        project_id=project_id
    )
```

---

### 3. Breakdown Summary Formatter (1 hour)
**File**: `python/src/server/integrations/slack/slack_service.py` (UPDATE)

**Add Method**:
```python
async def send_breakdown_summary(
    channel_id: str,
    breakdown: TaskBreakdown,
    project_id: str
) -> dict:
    """
    Send rich task breakdown summary to Slack.

    Uses Block Kit for formatting:
    - Header with task count
    - List of tasks with emoji status
    - Dependency info
    - Risk warnings
    - Call-to-action for Claude Code
    """
```

**Slack Message Format**:
```
🤖 AI-PM Task Breakdown Complete

Feature: Fix authentication bug
Total Tasks: 5 tasks | Effort: Medium (8-12 hours)

📋 Tasks Created:
1. ⚙️ Update JWT validation logic (coding) - 2h
2. 🧪 Add authentication tests (qa) - 2h
3. 📝 Update API docs (docs) - 1h
4. 🔍 Security audit (security) - 3h
5. 🚀 Deploy to staging (devops) - 1h

⚠️ Risks Identified:
• Token refresh may break existing sessions
• Rate limiting not implemented

🎯 Ready for Claude Code
Tasks are available via MCP. Claude Code can now execute:
`list_tasks(filter_by="status", filter_value="todo")`

[View All Tasks] [View in Archon UI]
```

---

### 4. Task Execution Orchestrator (2 hours)
**File**: `python/src/agents/product_manager/task_executor.py` (NEW)

**Purpose**: Coordinate task execution and progress reporting

**Class**:
```python
class TaskExecutor:
    """Manages task execution workflow"""

    async def execute_task_workflow(
        self,
        project_id: str,
        notify_slack: bool = True
    ) -> dict:
        """
        Execute tasks in dependency order.

        Workflow:
        1. Get all todo tasks for project
        2. Sort by dependencies and priority
        3. For each task:
           - Notify Slack task started
           - Wait for Claude Code to pick up (manual via MCP)
           - Monitor task status changes
           - Report progress to Slack
        4. Send final summary
        """
```

**Key Features**:
- Task dependency resolution
- Progress monitoring (poll task status)
- Slack notifications at each stage
- Error handling and retry logic

---

### 5. Progress Reporter (1 hour)
**File**: `python/src/agents/product_manager/progress_reporter.py` (NEW)

**Purpose**: Format and send progress updates to Slack

**Functions**:
```python
async def notify_task_started(project_id: str, task: dict) -> None:
    """Send 'Task started by Claude Code' message"""

async def notify_task_progress(project_id: str, task: dict, status: str) -> None:
    """Send task status update (doing → review → done)"""

async def notify_task_completed(project_id: str, task: dict) -> None:
    """Send task completion with checkmark"""

async def notify_all_tasks_complete(project_id: str, summary: dict) -> None:
    """Send final summary when all tasks done"""
```

**Slack Message Updates**:
```
🔄 Task In Progress
Task: Update JWT validation logic
Status: doing → review
Agent: Claude Code (coding)
Time: 45 minutes

[View Task] [View Code Changes]
```

---

### 6. Automated Workflow Trigger (Optional - 30 min)
**File**: `python/src/server/api_routes/workflow_api.py` (NEW)

**Endpoint**: `POST /api/workflows/execute-tasks`

**Purpose**: API endpoint to trigger task execution workflow

**Body**:
```json
{
  "project_id": "uuid",
  "notify_slack": true
}
```

**Use Case**: Frontend UI button or scheduled job to kick off execution

---

## 📋 Implementation Order

### Phase 1: Core Integration (3-4 hours)
1. ✅ Create `github_context_service.py`
2. ✅ Update Slack command handler (complete TODO)
3. ✅ Add `send_breakdown_summary()` to SlackService
4. ✅ Test: `/aipm create feature: Test` → Tasks created in DB → Slack notification

### Phase 2: Execution Workflow (2-3 hours)
5. ✅ Create `task_executor.py`
6. ✅ Create `progress_reporter.py`
7. ✅ Test: Monitor task status changes → Slack updates

### Phase 3: Polish & Testing (1-2 hours)
8. ✅ Add error handling throughout
9. ✅ Test end-to-end workflow
10. ✅ Document workflow for users

---

## 🔄 Complete Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER ACTION (Slack)                                      │
│    /aipm create feature: Fix authentication bug             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SLACK EVENT HANDLER                                      │
│    - Parse command                                          │
│    - Get project from channel link                          │
│    - Validate user permissions                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. GITHUB CONTEXT SERVICE                                   │
│    - Clone repo                                             │
│    - Search for similar code (RAG)                          │
│    - Extract file structure                                 │
│    - Return context dict                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ORCHESTRATOR AGENT (PydanticAI + GPT-4o)                │
│    - Analyze feature request                                │
│    - Use GitHub context                                     │
│    - Break into atomic tasks                                │
│    - Assign to agents (coding, qa, docs)                   │
│    - Return TaskBreakdown                                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. TASK CREATION (via MCP Client)                          │
│    For each subtask:                                        │
│      - manage_task(action="create", ...)                   │
│      - Store in database                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. SLACK NOTIFICATION                                       │
│    - Send breakdown summary (Block Kit)                     │
│    - Show task count, effort, risks                         │
│    - Include "Ready for Claude Code" message               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. CLAUDE CODE EXECUTION (via MCP)                         │
│    Claude Code automatically or manually:                   │
│      - list_tasks(filter_value="todo")                     │
│      - manage_task(action="update", status="doing")        │
│      - rag_search_knowledge_base(query="...")              │
│      - [Execute implementation]                             │
│      - manage_task(action="update", status="review")       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. PROGRESS MONITORING (TaskExecutor)                      │
│    - Poll task status every 30 seconds                      │
│    - Detect status changes (todo → doing → review → done)  │
│    - Trigger Slack notifications                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. PROGRESS REPORTER → SLACK                                │
│    - Task started notification                              │
│    - Task in progress updates                               │
│    - Task completed confirmation                            │
│    - Final summary when all done                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 Testing Plan

### Unit Tests
- ✅ `test_github_context_service.py` - Context extraction
- ✅ `test_slack_events.py` - Command handling
- ✅ `test_task_executor.py` - Workflow orchestration
- ✅ `test_progress_reporter.py` - Slack formatting

### Integration Tests
1. **Slack → Orchestrator**: Send `/aipm create` → Verify tasks created
2. **GitHub Context**: Test with real repo → Verify relevant files found
3. **Task Execution**: Update task status → Verify Slack notification
4. **End-to-End**: Full workflow from Slack → Claude Code → Slack

### Manual Testing
1. Link Slack channel to project
2. Send `/aipm create feature: Add user profile page`
3. Verify task breakdown in Slack
4. Use Claude Code MCP to execute tasks
5. Verify progress updates in Slack
6. Confirm final summary

---

## 🚀 Deployment Checklist

### Environment Variables
```bash
# Already configured
SLACK_CLIENT_ID=✓
SLACK_CLIENT_SECRET=✓
SLACK_SIGNING_SECRET=✓
OPENAI_API_KEY=✓
SUPABASE_URL=✓
SUPABASE_SERVICE_KEY=✓

# May need to add
GITHUB_TOKEN=<your-github-pat>  # For private repos
```

### Database Migrations
- ✅ Run AI-PM migrations (001, 002, 003) if not already done
- ✅ Verify `slack_channels` table exists
- ✅ Verify `archon_tasks` table has metadata column

### Services Running
- ✅ Docker Compose up (archon-server, archon-mcp, archon-ui)
- ✅ MCP server healthy (port 8051)
- ✅ Slack bot connected
- ✅ Claude Code connected to MCP

---

## 📊 Success Metrics

### MVP Success Criteria
1. ✅ User can send `/aipm create feature: X` in Slack
2. ✅ AI-PM breaks down feature into 3-5 tasks
3. ✅ Tasks appear in Archon database
4. ✅ Slack receives breakdown summary
5. ✅ Claude Code can list tasks via MCP
6. ✅ Task status changes trigger Slack notifications
7. ✅ End-to-end workflow completes in <5 minutes

### Performance Targets
- Task breakdown: <30 seconds
- Context extraction: <10 seconds
- Slack notifications: <2 seconds
- Status polling: Every 30 seconds

---

## 🎯 Post-MVP Enhancements

### Phase 2 Features (Future)
- Automatic task assignment to Claude Code (no manual trigger)
- Real-time WebSocket updates (replace polling)
- Task approval workflow (Slack buttons)
- Code review integration (GitHub PR comments)
- Task time tracking and estimates
- Agent performance metrics
- Asana bidirectional sync
- Multi-agent collaboration (coding + qa + docs in parallel)

### Phase 3 Features (Future)
- Custom agent creation
- Natural language task queries
- Automated testing and deployment
- Integration with Linear, Jira, etc.
- Voice command via Slack calls
- Analytics dashboard

---

## 📝 Development Notes

### Key Design Decisions
1. **MCP for Task Management**: Claude Code uses existing MCP tools (no new protocol needed)
2. **Polling for Progress**: Simple polling vs WebSockets (MVP simplicity)
3. **Async Orchestration**: Background tasks for orchestrator (non-blocking Slack)
4. **GitHub Context**: Shallow clone + RAG search (fast context extraction)
5. **Manual Claude Code Trigger**: User starts Claude Code execution (MVP safety)

### Known Limitations (MVP)
- No automatic retries on task failure
- No task time tracking
- No parallel task execution
- No code review integration
- No rollback mechanism
- Polling-based (not real-time)

### Security Considerations
- ✅ Slack signature verification (HMAC-SHA256)
- ✅ Channel-project authorization
- ✅ Database RLS policies
- ✅ No secrets in task metadata
- ⚠️ GitHub token stored in env (move to secrets manager in production)

---

## 🏁 Ready to Start?

**Implementation starts with**:
1. Create `github_context_service.py`
2. Test context extraction with a real repo
3. Complete Slack command handler
4. End-to-end test with simple feature

**Estimated MVP Completion**: 6-8 hours of focused work

**First Task**: Create GitHub Context Service ✨
