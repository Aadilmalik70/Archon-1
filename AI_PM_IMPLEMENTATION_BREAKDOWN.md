# AI Product Manager - Detailed Implementation Breakdown

## Executive Summary

This document provides actionable implementation details for the AI Product Manager feature, breaking down the 7-week plan into specific tasks with dependencies, acceptance criteria, and integration points.

**Architecture Context**:
- **Existing**: BaseAgent (PydanticAI), Service Layer Pattern, TanStack Query, Vertical Slice Architecture
- **Database**: Supabase (PostgreSQL + pgvector), RLS policies, migration system
- **Deployment**: Docker Compose, microservices (server:8181, mcp:8051, agents:8052)

---

## Phase 1: Foundation & Integrations (Weeks 1-2)

### 1.1 Database Schema Implementation

#### Task 1.1.1: Create AI-PM Core Tables Migration
**Priority**: P0 (Critical Path)
**Estimated Time**: 4 hours
**Dependencies**: None

**Implementation Steps**:
1. Create `migration/ai_pm/001_core_tables.sql`
2. Follow existing pattern from `migration/complete_setup.sql`
3. Add RLS policies for all tables
4. Include `updated_at` triggers

**Schema Details**:
```sql
-- ai_pm_executions: Track all agent executions
CREATE TABLE ai_pm_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES archon_tasks(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL, -- 'orchestrator', 'coding', 'qa', 'docs'
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    input_context JSONB NOT NULL DEFAULT '{}',
    output_result JSONB DEFAULT '{}',
    execution_log TEXT[] DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_pm_executions_task ON ai_pm_executions(task_id);
CREATE INDEX idx_ai_pm_executions_status ON ai_pm_executions(status);
CREATE INDEX idx_ai_pm_executions_agent_type ON ai_pm_executions(agent_type);

-- agent_configurations: Store agent settings
CREATE TABLE agent_configurations (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS Policies
ALTER TABLE ai_pm_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_configurations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access executions" ON ai_pm_executions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access configs" ON agent_configurations
    FOR ALL USING (auth.role() = 'service_role');
```

**Acceptance Criteria**:
- [ ] Migration runs without errors on fresh database
- [ ] All tables created with proper indexes
- [ ] RLS policies active and tested
- [ ] Rollback script created and tested

---

#### Task 1.1.2: Create Integration Credentials Tables
**Priority**: P0 (Critical Path)
**Estimated Time**: 3 hours
**Dependencies**: Task 1.1.1

**Implementation Steps**:
1. Create `migration/ai_pm/002_integration_tables.sql`
2. Add encryption for sensitive fields
3. Include metadata JSONB for flexible storage

**Schema Details**:
```sql
-- Store OAuth tokens and API keys securely
CREATE TABLE integration_credentials (
    credential_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL, -- 'slack', 'asana', 'github'
    credential_type VARCHAR(50) NOT NULL, -- 'oauth_token', 'api_key', 'webhook_url'
    encrypted_value TEXT, -- bcrypt encrypted
    metadata JSONB DEFAULT '{}', -- workspace_id, team_id, scopes, etc.
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_integration_creds_service ON integration_credentials(service_name);

-- Slack channel mappings
CREATE TABLE slack_channels (
    channel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES archon_projects(id) ON DELETE CASCADE,
    slack_channel_id VARCHAR(50) NOT NULL,
    slack_channel_name VARCHAR(255) NOT NULL,
    notification_types TEXT[] DEFAULT '{}', -- ['task_created', 'task_completed', 'agent_action']
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, slack_channel_id)
);

CREATE INDEX idx_slack_channels_project ON slack_channels(project_id);

-- Asana project mappings
CREATE TABLE asana_projects (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archon_project_id UUID REFERENCES archon_projects(id) ON DELETE CASCADE,
    asana_workspace_id VARCHAR(50) NOT NULL,
    asana_project_id VARCHAR(50) NOT NULL,
    sync_enabled BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(archon_project_id)
);

CREATE INDEX idx_asana_projects_archon ON asana_projects(archon_project_id);

-- Track bidirectional sync
CREATE TABLE task_sync_log (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archon_task_id UUID REFERENCES archon_tasks(id) ON DELETE CASCADE,
    external_service VARCHAR(50) NOT NULL, -- 'asana', 'jira'
    external_task_id VARCHAR(100) NOT NULL,
    sync_direction VARCHAR(20) NOT NULL, -- 'inbound', 'outbound', 'bidirectional'
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    sync_status VARCHAR(20) DEFAULT 'synced', -- 'synced', 'conflict', 'failed'
    conflict_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_task_sync_archon_task ON task_sync_log(archon_task_id);
CREATE INDEX idx_task_sync_external ON task_sync_log(external_service, external_task_id);

-- RLS
ALTER TABLE integration_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE asana_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_sync_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON integration_credentials FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON slack_channels FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON asana_projects FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON task_sync_log FOR ALL USING (auth.role() = 'service_role');
```

**Acceptance Criteria**:
- [ ] All tables created successfully
- [ ] Encryption helper functions work
- [ ] Foreign key constraints validate
- [ ] Unique constraints prevent duplicates

---

#### Task 1.1.3: Extend archon_tasks Table
**Priority**: P0 (Critical Path)
**Estimated Time**: 2 hours
**Dependencies**: Task 1.1.1

**Implementation Steps**:
1. Create `migration/ai_pm/003_extend_tasks.sql`
2. Add nullable columns for backward compatibility
3. Create indexes for new fields

**Schema Details**:
```sql
-- Add AI-PM specific fields to existing tasks table
ALTER TABLE archon_tasks
    ADD COLUMN IF NOT EXISTS agent_assigned VARCHAR(50),
    ADD COLUMN IF NOT EXISTS task_type VARCHAR(50), -- 'feature', 'bug', 'refactor', 'test', 'docs'
    ADD COLUMN IF NOT EXISTS context_summary TEXT,
    ADD COLUMN IF NOT EXISTS dependencies UUID[],
    ADD COLUMN IF NOT EXISTS automation_status VARCHAR(20) DEFAULT 'manual', -- 'manual', 'pending', 'automated'
    ADD COLUMN IF NOT EXISTS execution_metadata JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS asana_task_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS slack_thread_ts VARCHAR(100);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_tasks_agent_assigned ON archon_tasks(agent_assigned);
CREATE INDEX IF NOT EXISTS idx_tasks_automation_status ON archon_tasks(automation_status);
CREATE INDEX IF NOT EXISTS idx_tasks_asana_id ON archon_tasks(asana_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_slack_thread ON archon_tasks(slack_thread_ts);

-- Add constraint for task_type
ALTER TABLE archon_tasks ADD CONSTRAINT check_task_type
    CHECK (task_type IS NULL OR task_type IN ('feature', 'bug', 'refactor', 'test', 'docs', 'other'));

-- Add constraint for automation_status
ALTER TABLE archon_tasks ADD CONSTRAINT check_automation_status
    CHECK (automation_status IN ('manual', 'pending', 'automated', 'failed'));
```

**Acceptance Criteria**:
- [ ] All columns added without breaking existing data
- [ ] Indexes improve query performance
- [ ] Constraints validate data properly
- [ ] No downtime for existing functionality

---

### 1.2 Slack Integration

#### Task 1.2.1: Create Slack App and OAuth Flow
**Priority**: P0 (Critical Path)
**Estimated Time**: 6 hours
**Dependencies**: Task 1.1.2 (integration_credentials table)

**Implementation Steps**:

**1. Slack App Setup**:
- Go to https://api.slack.com/apps
- Create new app "Archon AI-PM"
- Add OAuth scopes:
  - `chat:write` - Send messages
  - `channels:read` - List channels
  - `channels:history` - Read messages
  - `commands` - Slash commands
  - `files:write` - Upload files
  - `users:read` - Get user info
- Set redirect URL: `http://localhost:8181/api/integrations/slack/oauth/callback`

**2. Backend Implementation**:

File: `python/src/server/integrations/slack/__init__.py`
```python
"""Slack integration module for Archon AI-PM"""
from .slack_service import SlackService
from .slack_client import SlackClient

__all__ = ["SlackService", "SlackClient"]
```

File: `python/src/server/integrations/slack/slack_client.py`
```python
"""
Slack API client wrapper
Handles direct API communication with Slack
"""
import httpx
from typing import Any
from ...config.logfire_config import get_logger

logger = get_logger(__name__)

class SlackClient:
    """Low-level Slack API client"""

    BASE_URL = "https://slack.com/api"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    async def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Post a message to a Slack channel

        Args:
            channel: Channel ID or name
            text: Message text (fallback)
            thread_ts: Optional thread timestamp for replies
            blocks: Optional Block Kit formatted content

        Returns:
            Slack API response with message details
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "channel": channel,
                "text": text,
            }

            if thread_ts:
                payload["thread_ts"] = thread_ts
            if blocks:
                payload["blocks"] = blocks

            response = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=self.headers,
                json=payload,
                timeout=10.0
            )

            data = response.json()
            if not data.get("ok"):
                logger.error(f"Slack API error: {data.get('error')}")
                raise Exception(f"Slack API error: {data.get('error')}")

            return data

    async def list_channels(self) -> list[dict[str, Any]]:
        """List all channels in workspace"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/conversations.list",
                headers=self.headers,
                params={"types": "public_channel,private_channel"},
                timeout=10.0
            )

            data = response.json()
            if not data.get("ok"):
                raise Exception(f"Slack API error: {data.get('error')}")

            return data.get("channels", [])

    async def upload_file(
        self,
        channels: list[str],
        content: str,
        filename: str,
        thread_ts: str | None = None
    ) -> dict[str, Any]:
        """Upload a file (code snippet, report) to Slack"""
        async with httpx.AsyncClient() as client:
            files = {"file": (filename, content, "text/plain")}
            data = {
                "channels": ",".join(channels),
                "filename": filename,
            }

            if thread_ts:
                data["thread_ts"] = thread_ts

            response = await client.post(
                f"{self.BASE_URL}/files.upload",
                headers={"Authorization": f"Bearer {self.access_token}"},
                files=files,
                data=data,
                timeout=30.0
            )

            result = response.json()
            if not result.get("ok"):
                raise Exception(f"File upload failed: {result.get('error')}")

            return result
```

File: `python/src/server/integrations/slack/slack_oauth.py`
```python
"""
Slack OAuth 2.0 flow handler
Handles authorization and token exchange
"""
import httpx
from ...config.logfire_config import get_logger
from ...utils import get_supabase_client
import bcrypt

logger = get_logger(__name__)

class SlackOAuth:
    """Handles Slack OAuth 2.0 flow"""

    CLIENT_ID = ""  # From environment
    CLIENT_SECRET = ""  # From environment
    REDIRECT_URI = "http://localhost:8181/api/integrations/slack/oauth/callback"

    @classmethod
    def get_authorization_url(cls, state: str) -> str:
        """Generate OAuth authorization URL"""
        scopes = [
            "chat:write",
            "channels:read",
            "channels:history",
            "commands",
            "files:write",
            "users:read"
        ]

        scope_string = ",".join(scopes)
        return (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={cls.CLIENT_ID}&"
            f"scope={scope_string}&"
            f"redirect_uri={cls.REDIRECT_URI}&"
            f"state={state}"
        )

    @classmethod
    async def exchange_code(cls, code: str) -> dict:
        """Exchange authorization code for access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": cls.CLIENT_ID,
                    "client_secret": cls.CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": cls.REDIRECT_URI
                },
                timeout=10.0
            )

            data = response.json()
            if not data.get("ok"):
                raise Exception(f"Token exchange failed: {data.get('error')}")

            return data

    @classmethod
    async def store_credentials(cls, token_data: dict) -> str:
        """Store OAuth tokens in database (encrypted)"""
        supabase = get_supabase_client()

        # Encrypt access token
        access_token = token_data["access_token"]
        encrypted = bcrypt.hashpw(
            access_token.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        metadata = {
            "team_id": token_data.get("team", {}).get("id"),
            "team_name": token_data.get("team", {}).get("name"),
            "bot_user_id": token_data.get("bot_user_id"),
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type")
        }

        result = supabase.table("integration_credentials").insert({
            "service_name": "slack",
            "credential_type": "oauth_token",
            "encrypted_value": encrypted,
            "metadata": metadata
        }).execute()

        return result.data[0]["credential_id"]
```

**Acceptance Criteria**:
- [ ] Slack app created with correct permissions
- [ ] OAuth flow completes successfully
- [ ] Tokens stored encrypted in database
- [ ] Test message sent to test channel
- [ ] Error handling for expired tokens

---

#### Task 1.2.2: Implement Slack Service Layer
**Priority**: P0 (Critical Path)
**Estimated Time**: 4 hours
**Dependencies**: Task 1.2.1

**Implementation**: See next section...

---

### 1.3 Asana Integration

(Detailed breakdown continues...)

---

## Phase 2: AI Agent System (Weeks 3-4)

### 2.1 AI-PM Orchestrator Agent

#### Task 2.1.1: Create Orchestrator Agent Structure
**Priority**: P0 (Critical Path)
**Estimated Time**: 6 hours
**Dependencies**: Task 1.1.1 (database), existing BaseAgent

**File Structure**:
```
python/src/agents/product_manager/
├── __init__.py
├── orchestrator_agent.py      # Main AI-PM agent
├── task_planner.py             # Break down features
├── agent_coordinator.py        # Assign to specialists
├── decision_engine.py          # Priority logic
├── context_builder.py          # Build agent context
└── tools/
    ├── __init__.py
    ├── task_tools.py           # Task CRUD operations
    ├── code_analysis_tools.py  # Analyze code context
    └── integration_tools.py    # Slack/Asana notifications
```

**Implementation**:

File: `python/src/agents/product_manager/__init__.py`
```python
"""AI Product Manager orchestrator agent"""
from .orchestrator_agent import OrchestratorAgent

__all__ = ["OrchestratorAgent"]
```

File: `python/src/agents/product_manager/orchestrator_agent.py`
```python
"""
AI-PM Orchestrator Agent
Coordinates task planning, agent assignment, and execution monitoring
"""
from typing import Any
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from ..base_agent import BaseAgent, ArchonDependencies
from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class TaskBreakdown(BaseModel):
    """Structured output for task planning"""
    subtasks: list[dict[str, Any]] = Field(
        description="List of atomic subtasks with title, description, type, priority"
    )
    dependencies: dict[str, list[str]] = Field(
        description="Map of task_id to list of dependency task_ids"
    )
    estimated_effort: dict[str, str] = Field(
        description="Map of task_id to effort estimate (small/medium/large)"
    )
    priority_order: list[str] = Field(
        description="Ordered list of task_ids by priority"
    )
    agent_assignments: dict[str, str] = Field(
        description="Map of task_id to recommended agent (coding/qa/docs)"
    )


class OrchestratorDependencies(ArchonDependencies):
    """Dependencies for orchestrator agent"""
    project_id: str | None = None
    feature_description: str | None = None
    existing_tasks: list[dict] | None = None
    code_context: dict[str, Any] | None = None


class OrchestratorAgent(BaseAgent[OrchestratorDependencies, TaskBreakdown]):
    """
    AI Product Manager Orchestrator

    Responsibilities:
    - Analyze feature requests
    - Break down into atomic tasks
    - Assign tasks to specialized agents
    - Monitor execution progress
    - Update external systems (Slack, Asana)
    """

    def __init__(self):
        super().__init__(
            model="openai:gpt-4o",
            name="OrchestratorAgent",
            retries=3,
            enable_rate_limiting=True,
        )

    def _create_agent(self, **kwargs) -> Agent:
        """Create PydanticAI agent with tools"""
        agent = Agent(
            self.model,
            result_type=TaskBreakdown,
            system_prompt=self.get_system_prompt(),
            retries=self.retries
        )

        # Register tools
        self._register_tools(agent)

        return agent

    def get_system_prompt(self) -> str:
        return """You are an AI Product Manager orchestrating software development.

Your responsibilities:
1. Analyze feature requests and requirements
2. Break down features into atomic, implementable tasks
3. Identify dependencies between tasks
4. Assign tasks to specialized agents (coding, qa, docs)
5. Estimate effort for each task
6. Prioritize tasks based on dependencies and value

Guidelines:
- Tasks should be small and focused (1-4 hours each)
- Always include testing tasks for features
- Document tasks should follow implementation
- Consider code quality and security
- Identify clear acceptance criteria
- Note external dependencies (APIs, libraries)

Agent Types:
- coding: Implements features, fixes bugs, writes code
- qa: Runs tests, static analysis, security scans
- docs: Updates documentation, API specs, comments

Task Types:
- feature: New functionality
- bug: Bug fixes
- refactor: Code improvements
- test: Test creation/updates
- docs: Documentation updates

Effort Estimates:
- small: 1-2 hours (simple changes)
- medium: 2-4 hours (moderate complexity)
- large: 4-8 hours (complex features)

Always provide structured output with clear dependencies and priorities."""

    def _register_tools(self, agent: Agent):
        """Register tools for orchestrator"""

        @agent.tool
        async def get_existing_tasks(ctx: RunContext[OrchestratorDependencies]) -> list[dict]:
            """Get existing tasks for the project"""
            if ctx.deps.existing_tasks:
                return ctx.deps.existing_tasks
            return []

        @agent.tool
        async def get_code_context(ctx: RunContext[OrchestratorDependencies]) -> dict:
            """Get relevant code context for planning"""
            if ctx.deps.code_context:
                return ctx.deps.code_context
            return {"files": [], "dependencies": []}

        @agent.tool
        async def search_similar_tasks(ctx: RunContext[OrchestratorDependencies], query: str) -> list[dict]:
            """Search for similar past tasks to learn from"""
            # TODO: Implement similarity search using embeddings
            logger.info(f"Searching similar tasks for: {query}")
            return []


# Example usage
async def plan_feature(feature_description: str, project_id: str) -> TaskBreakdown:
    """Plan a feature using the orchestrator agent"""
    orchestrator = OrchestratorAgent()

    deps = OrchestratorDependencies(
        project_id=project_id,
        feature_description=feature_description,
        request_id="test-request"
    )

    prompt = f"""Analyze this feature request and create a detailed task breakdown:

Feature: {feature_description}

Provide a comprehensive task breakdown with:
1. All required implementation tasks
2. Testing tasks
3. Documentation tasks
4. Clear dependencies
5. Effort estimates
6. Priority ordering
7. Agent assignments"""

    result = await orchestrator.run(prompt, deps)
    return result
```

**Acceptance Criteria**:
- [ ] Agent creates structured task breakdowns
- [ ] Dependencies correctly identified
- [ ] Agent assignments logical
- [ ] Effort estimates reasonable
- [ ] Integration with BaseAgent working
- [ ] Rate limiting functional

---

## Technical Dependencies & Risks

### Critical Dependencies
1. **Database Migrations** → All features depend on schema
2. **Slack/Asana OAuth** → Integration features blocked until complete
3. **BaseAgent Framework** → All agents inherit from this
4. **Supabase Client** → All data operations require this

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| OAuth token expiration | High | Medium | Implement refresh token flow, monitor expiration |
| Agent rate limiting | High | High | Implement exponential backoff, queue system |
| Sync conflicts (Asana) | Medium | Medium | Last-write-wins with conflict logging |
| Schema breaking changes | Low | High | Comprehensive migration testing, rollback scripts |
| External API downtime | Medium | Medium | Graceful degradation, retry logic, user notifications |

---

## Next Steps

Would you like me to:

1. **Continue Phase 1 breakdown** - Complete Slack/Asana service implementations
2. **Create specific PRDs** - Detailed PRDs for each component
3. **Generate migration scripts** - Ready-to-run SQL migrations
4. **Build API endpoint specs** - OpenAPI specs for all routes
5. **Create test plans** - Unit/integration test strategies
6. **Start implementation** - Begin coding specific components

Choose your priority and I'll provide the detailed breakdown!
