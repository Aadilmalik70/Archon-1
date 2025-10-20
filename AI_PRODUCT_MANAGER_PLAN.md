# AI Product Manager - Implementation Plan

## 🎯 Vision
Build an AI-driven Product Manager that coordinates specialized AI agents to autonomously manage the entire software development lifecycle, with deep integrations into Slack and Asana for real-world team collaboration.

---

## 📋 Implementation Phases

### Phase 1: Foundation & Integrations (Weeks 1-2)

#### 1.1 Database Schema
**Location**: `migration/ai_pm/`

**New Tables**:
```sql
-- AI-PM executions log
CREATE TABLE ai_pm_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES archon_tasks(id),
    agent_type VARCHAR(50), -- 'orchestrator', 'coding', 'qa', 'docs'
    status VARCHAR(20), -- 'pending', 'running', 'completed', 'failed'
    input_context JSONB,
    output_result JSONB,
    execution_log TEXT[],
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Agent configurations
CREATE TABLE agent_configurations (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_type VARCHAR(50) UNIQUE,
    enabled BOOLEAN DEFAULT true,
    config JSONB, -- model, temperature, tools, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- External integrations credentials
CREATE TABLE integration_credentials (
    integration_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(50), -- 'slack', 'asana', 'github'
    credential_type VARCHAR(50), -- 'oauth_token', 'api_key', 'webhook_url'
    encrypted_value TEXT,
    metadata JSONB, -- workspace_id, team_id, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Slack channels mapping
CREATE TABLE slack_channels (
    channel_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES archon_projects(id),
    slack_channel_id VARCHAR(50),
    slack_channel_name VARCHAR(255),
    notification_types TEXT[], -- 'task_created', 'task_completed', 'agent_action', etc.
    created_at TIMESTAMP DEFAULT NOW()
);

-- Asana workspaces and projects mapping
CREATE TABLE asana_projects (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    archon_project_id UUID REFERENCES archon_projects(id),
    asana_workspace_id VARCHAR(50),
    asana_project_id VARCHAR(50),
    sync_enabled BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Task sync tracking
CREATE TABLE task_sync_log (
    sync_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    archon_task_id UUID REFERENCES archon_tasks(id),
    external_service VARCHAR(50), -- 'asana', 'jira'
    external_task_id VARCHAR(100),
    sync_direction VARCHAR(20), -- 'inbound', 'outbound', 'bidirectional'
    last_synced_at TIMESTAMP DEFAULT NOW(),
    sync_status VARCHAR(20) -- 'synced', 'conflict', 'failed'
);
```

**Extended archon_tasks Table**:
```sql
ALTER TABLE archon_tasks ADD COLUMN agent_assigned VARCHAR(50);
ALTER TABLE archon_tasks ADD COLUMN task_type VARCHAR(50);
ALTER TABLE archon_tasks ADD COLUMN context_summary TEXT;
ALTER TABLE archon_tasks ADD COLUMN dependencies UUID[];
ALTER TABLE archon_tasks ADD COLUMN automation_status VARCHAR(20) DEFAULT 'manual';
ALTER TABLE archon_tasks ADD COLUMN execution_metadata JSONB;
ALTER TABLE archon_tasks ADD COLUMN asana_task_id VARCHAR(100);
ALTER TABLE archon_tasks ADD COLUMN slack_thread_ts VARCHAR(100);
```

#### 1.2 Slack Integration
**Location**: `python/src/server/integrations/slack/`

**Files to Create**:
- `slack_client.py` - Slack API wrapper
- `slack_oauth.py` - OAuth flow handler
- `slack_events.py` - Event listener (webhooks)
- `slack_service.py` - Business logic

**Features**:
- OAuth 2.0 authentication
- Send messages to channels
- Create threads for tasks
- Listen to slash commands (`/aipm`, `/task`, `/status`)
- Interactive buttons and modals
- File uploads (code snippets, reports)
- Real-time notifications

**API Endpoints**:
```python
POST /api/integrations/slack/oauth/callback
POST /api/integrations/slack/events  # Webhook endpoint
GET  /api/integrations/slack/channels
POST /api/integrations/slack/link-channel
POST /api/integrations/slack/send-message
DELETE /api/integrations/slack/disconnect
```

**Slack App Permissions Needed**:
- `chat:write` - Send messages
- `channels:read` - List channels
- `channels:history` - Read message history
- `commands` - Slash commands
- `files:write` - Upload files
- `users:read` - Get user info

#### 1.3 Asana Integration
**Location**: `python/src/server/integrations/asana/`

**Files to Create**:
- `asana_client.py` - Asana API wrapper
- `asana_oauth.py` - OAuth flow handler
- `asana_sync.py` - Bidirectional sync logic
- `asana_webhook.py` - Webhook listener
- `asana_service.py` - Business logic

**Features**:
- OAuth 2.0 authentication
- Sync tasks bidirectionally
- Create tasks from Archon
- Update task status automatically
- Sync comments and attachments
- Map Asana sections to Archon statuses
- Webhook for real-time updates

**API Endpoints**:
```python
POST /api/integrations/asana/oauth/callback
GET  /api/integrations/asana/workspaces
GET  /api/integrations/asana/projects
POST /api/integrations/asana/link-project
POST /api/integrations/asana/sync-tasks
POST /api/integrations/asana/webhook  # Asana webhooks
PUT  /api/integrations/asana/task/{task_id}
DELETE /api/integrations/asana/disconnect
```

**Asana Webhook Events**:
- Task created
- Task updated
- Task completed
- Task deleted
- Comment added

---

### Phase 2: AI Agent System (Weeks 3-4)

#### 2.1 AI-PM Orchestrator Agent
**Location**: `python/src/agents/product_manager/`

**Files**:
```
product_manager/
├── __init__.py
├── orchestrator_agent.py    # Main AI-PM agent
├── task_planner.py           # Break down features into tasks
├── agent_coordinator.py      # Assign tasks to agents
├── decision_engine.py        # Priority and routing logic
├── context_builder.py        # Build context for agents
└── tools/
    ├── task_tools.py
    ├── code_analysis_tools.py
    └── integration_tools.py
```

**Orchestrator Responsibilities**:
1. Receive feature requests (from Asana, Slack, or UI)
2. Analyze requirements and context
3. Break down into atomic tasks
4. Assign tasks to specialized agents
5. Monitor execution progress
6. Handle failures and retries
7. Update external systems (Asana, Slack)
8. Generate reports and summaries

**PydanticAI Agent Structure**:
```python
from pydantic_ai import Agent
from pydantic import BaseModel

class TaskBreakdown(BaseModel):
    subtasks: list[dict]
    dependencies: dict
    estimated_effort: dict
    priority_order: list[str]

orchestrator = Agent(
    'openai:gpt-4',
    result_type=TaskBreakdown,
    system_prompt="You are an AI Product Manager..."
)
```

#### 2.2 Coding Agent
**Location**: `python/src/agents/coding_agent/`

**Files**:
```
coding_agent/
├── __init__.py
├── code_generator.py         # Generate code patches
├── mcp_connector.py          # Connect to Claude Code MCP
├── git_operations.py         # Git operations
└── tools/
    ├── file_editor.py
    ├── syntax_checker.py
    └── dependency_resolver.py
```

**Capabilities**:
- Retrieve relevant code from GitHub repos
- Generate code based on task description
- Apply changes to files
- Create git branches
- Commit changes
- Open pull requests

#### 2.3 QA Agent
**Location**: `python/src/agents/qa_agent/`

**Files**:
```
qa_agent/
├── __init__.py
├── test_runner.py            # Run automated tests
├── static_analyzer.py        # Linting, type checking
├── security_scanner.py       # Security vulnerabilities
└── tools/
    ├── pytest_runner.py
    ├── eslint_runner.py
    └── dependency_checker.py
```

**Capabilities**:
- Run unit tests (pytest, vitest)
- Run integration tests
- Static analysis (ruff, mypy, eslint)
- Security scanning
- Code coverage reports
- Performance testing

#### 2.4 Documentation Agent
**Location**: `python/src/agents/documentation_agent/`

**Files**:
```
documentation_agent/
├── __init__.py
├── doc_generator.py          # Generate documentation
├── changelog_updater.py      # Update CHANGELOG.md
└── tools/
    ├── api_doc_generator.py
    ├── readme_updater.py
    └── comment_generator.py
```

**Capabilities**:
- Generate API documentation
- Update README files
- Create code comments
- Generate changelogs
- Update user guides

---

### Phase 3: Context & Execution System (Week 5)

#### 3.1 Enhanced Context Memory
**Location**: `python/src/server/services/ai_pm/context_service.py`

**Features**:
- Retrieve relevant code from linked GitHub repos
- Search past tasks and solutions
- Load project documentation
- Build agent-specific context
- Cache frequently used context

**Context Types**:
```python
class TaskContext:
    task_description: str
    related_code: list[CodeSnippet]
    similar_past_tasks: list[Task]
    project_documentation: list[Document]
    dependencies: list[Task]
    asana_context: Optional[dict]  # Original Asana task details
    slack_context: Optional[dict]  # Slack thread context
```

#### 3.2 Execution Engine
**Location**: `python/src/server/services/ai_pm/execution_service.py`

**Workflow**:
1. Receive task assignment
2. Build context for agent
3. Execute agent with timeout
4. Monitor progress
5. Log all actions
6. Handle errors and retries
7. Update task status
8. Notify stakeholders (Slack, Asana)

---

### Phase 4: UI & Dashboard (Week 6)

#### 4.1 AI-PM Dashboard
**Location**: `archon-ui-main/src/features/ai-pm/`

**Structure**:
```
ai-pm/
├── components/
│   ├── AIPMDashboard.tsx
│   ├── TaskExecutionViewer.tsx
│   ├── AgentActivityMonitor.tsx
│   ├── IntegrationStatus.tsx
│   ├── ExecutionLogs.tsx
│   └── ContextViewer.tsx
├── hooks/
│   └── useAIPMQueries.ts
├── services/
│   └── aipmService.ts
└── types/
    └── index.ts
```

**Pages**:
1. **Overview Dashboard**
   - Active tasks being executed
   - Agent status and availability
   - Recent completions
   - Integration health (Slack, Asana, GitHub)

2. **Integrations Page**
   - Connect Slack workspace
   - Connect Asana account
   - Link channels and projects
   - Configure notifications

3. **Task Execution Viewer**
   - Real-time execution logs
   - Agent decision explanations
   - Code changes preview
   - QA results

4. **Agent Configuration**
   - Enable/disable agents
   - Configure models and settings
   - Set execution limits

---

### Phase 5: Workflow Automation (Week 7)

#### 5.1 Event-Driven Workflows

**Asana → Archon**:
```
New Asana Task Created
    ↓
Webhook received in Archon
    ↓
AI-PM analyzes task
    ↓
Breaks down into subtasks
    ↓
Assigns to agents
    ↓
Agents execute
    ↓
Updates Asana status
    ↓
Posts summary to Slack
```

**Slack → Archon**:
```
User posts in Slack: "@aipm create feature: user authentication"
    ↓
Slack event received
    ↓
AI-PM parses request
    ↓
Creates Asana task (optional)
    ↓
Creates Archon tasks
    ↓
Assigns to agents
    ↓
Responds in Slack thread with plan
```

**GitHub → Archon**:
```
PR Review Requested
    ↓
GitHub webhook received
    ↓
QA Agent triggered
    ↓
Runs automated checks
    ↓
Posts review comments
    ↓
Updates task status
    ↓
Notifies in Slack
```

#### 5.2 Failure Recovery

**Retry Logic**:
- 3 retries for transient failures
- Exponential backoff
- Different strategy per failure type
- Human escalation after max retries

**Rollback Strategy**:
- Git revert for failed deployments
- Task status rollback
- Notification of rollback

---

## 🗂️ File Structure

```
Archon/
├── migration/
│   └── ai_pm/
│       ├── 001_ai_pm_tables.sql
│       ├── 002_slack_integration.sql
│       └── 003_asana_integration.sql
│
├── python/src/
│   ├── agents/
│   │   ├── product_manager/      # AI-PM Orchestrator
│   │   ├── coding_agent/          # Code generation
│   │   ├── qa_agent/              # Testing & QA
│   │   └── documentation_agent/   # Docs generation
│   │
│   └── server/
│       ├── integrations/
│       │   ├── slack/
│       │   │   ├── slack_client.py
│       │   │   ├── slack_oauth.py
│       │   │   ├── slack_events.py
│       │   │   └── slack_service.py
│       │   │
│       │   ├── asana/
│       │   │   ├── asana_client.py
│       │   │   ├── asana_oauth.py
│       │   │   ├── asana_sync.py
│       │   │   ├── asana_webhook.py
│       │   │   └── asana_service.py
│       │   │
│       │   └── github/  # Already exists, extend
│       │
│       ├── services/
│       │   └── ai_pm/
│       │       ├── context_service.py
│       │       ├── execution_service.py
│       │       └── orchestration_service.py
│       │
│       └── api_routes/
│           ├── ai_pm_api.py
│           ├── slack_api.py
│           └── asana_api.py
│
└── archon-ui-main/src/
    └── features/
        ├── ai-pm/
        │   ├── components/
        │   │   ├── AIPMDashboard.tsx
        │   │   ├── TaskExecutionViewer.tsx
        │   │   ├── AgentActivityMonitor.tsx
        │   │   └── IntegrationSetup.tsx
        │   ├── hooks/
        │   ├── services/
        │   └── types/
        │
        └── integrations/
            ├── slack/
            └── asana/
```

---

## 📝 Detailed Todo List

### Week 1: Database & Slack Integration

- [ ] Create migration scripts for AI-PM tables
- [ ] Add agent fields to archon_tasks table
- [ ] Create ai_pm_executions table
- [ ] Create agent_configurations table
- [ ] Create integration_credentials table
- [ ] Create slack_channels table
- [ ] Run migrations on local and test databases
- [ ] Create Slack app in Slack API dashboard
- [ ] Implement Slack OAuth flow (backend)
- [ ] Create Slack client wrapper (slack_client.py)
- [ ] Implement webhook event listener (slack_events.py)
- [ ] Create Slack service layer (slack_service.py)
- [ ] Add Slack API routes to FastAPI
- [ ] Create Slack integration UI (React)
- [ ] Implement channel linking UI
- [ ] Test Slack message sending
- [ ] Test Slack event receiving

### Week 2: Asana Integration

- [ ] Create Asana tables (asana_projects, task_sync_log)
- [ ] Create Asana app in Asana developer console
- [ ] Implement Asana OAuth flow (backend)
- [ ] Create Asana client wrapper (asana_client.py)
- [ ] Implement bidirectional sync logic (asana_sync.py)
- [ ] Create Asana webhook listener (asana_webhook.py)
- [ ] Create Asana service layer (asana_service.py)
- [ ] Add Asana API routes to FastAPI
- [ ] Create Asana integration UI (React)
- [ ] Implement project linking UI
- [ ] Test task creation from Asana → Archon
- [ ] Test task updates Archon → Asana
- [ ] Test bidirectional sync
- [ ] Handle sync conflicts
- [ ] Add sync status indicators in UI

### Week 3: AI-PM Orchestrator Agent

- [ ] Set up PydanticAI agent structure
- [ ] Create orchestrator_agent.py
- [ ] Implement task breakdown logic (task_planner.py)
- [ ] Create decision engine (decision_engine.py)
- [ ] Implement agent coordination (agent_coordinator.py)
- [ ] Build context builder (context_builder.py)
- [ ] Create task analysis tools
- [ ] Create code analysis tools
- [ ] Implement integration tools (Slack, Asana)
- [ ] Add execution logging
- [ ] Test task breakdown from feature description
- [ ] Test agent assignment logic
- [ ] Create API endpoint for triggering AI-PM
- [ ] Integrate with Slack commands
- [ ] Integrate with Asana webhooks

### Week 4: Coding & QA Agents

- [ ] Create coding agent structure
- [ ] Implement code generator (code_generator.py)
- [ ] Create MCP connector for Claude Code
- [ ] Implement git operations (git_operations.py)
- [ ] Create file editor tool
- [ ] Add syntax checking
- [ ] Test code generation from task
- [ ] Create QA agent structure
- [ ] Implement test runner (test_runner.py)
- [ ] Add static analyzer (static_analyzer.py)
- [ ] Create security scanner (security_scanner.py)
- [ ] Implement pytest runner
- [ ] Implement eslint/vitest runner
- [ ] Test QA validation workflow
- [ ] Add QA results to execution logs

### Week 5: Context System & Documentation Agent

- [ ] Create context service (context_service.py)
- [ ] Implement code retrieval from GitHub repos
- [ ] Add similar task search
- [ ] Build agent-specific context
- [ ] Add context caching
- [ ] Create execution service (execution_service.py)
- [ ] Implement execution workflow
- [ ] Add timeout handling
- [ ] Implement retry logic
- [ ] Create documentation agent structure
- [ ] Implement doc generator (doc_generator.py)
- [ ] Add changelog updater
- [ ] Create API doc generator
- [ ] Test full agent execution pipeline
- [ ] Add comprehensive logging

### Week 6: UI & Dashboard

- [ ] Create ai-pm feature directory structure
- [ ] Build AIPMDashboard component
- [ ] Create TaskExecutionViewer component
- [ ] Build AgentActivityMonitor component
- [ ] Create IntegrationStatus component
- [ ] Implement ExecutionLogs component
- [ ] Build ContextViewer component
- [ ] Create useAIPMQueries hooks
- [ ] Implement aipmService API layer
- [ ] Add TypeScript types
- [ ] Create integrations setup page
- [ ] Add Slack connection UI
- [ ] Add Asana connection UI
- [ ] Add GitHub integration status
- [ ] Implement real-time updates (polling)
- [ ] Test full UI workflow

### Week 7: Automation & Workflows

- [ ] Create webhook listeners for all services
- [ ] Implement Asana → Archon workflow
- [ ] Implement Slack → Archon workflow
- [ ] Implement GitHub → Archon workflow
- [ ] Add cross-platform notifications
- [ ] Implement failure recovery logic
- [ ] Add rollback mechanisms
- [ ] Create execution reports
- [ ] Add Slack summary messages
- [ ] Update Asana tasks automatically
- [ ] Test end-to-end workflows
- [ ] Add performance monitoring
- [ ] Optimize database queries
- [ ] Add caching where needed
- [ ] Write integration tests
- [ ] Create user documentation

---

## 🔐 Security Considerations

- Encrypt OAuth tokens at rest
- Use environment variables for secrets
- Implement rate limiting
- Validate webhook signatures
- Sanitize user inputs
- Implement proper CORS policies
- Add audit logging
- Regular security scans

---

## 📊 Success Metrics

- Task completion rate (AI vs manual)
- Time from task creation to completion
- Number of successful automations
- Integration uptime
- User satisfaction scores
- Code quality metrics
- Test coverage improvements

---

## 🚀 Launch Checklist

- [ ] All migrations tested
- [ ] All integrations working
- [ ] All agents functional
- [ ] UI complete and tested
- [ ] Documentation written
- [ ] Security audit completed
- [ ] Performance tested
- [ ] User training materials ready
- [ ] Rollback plan documented
- [ ] Monitoring and alerts configured
