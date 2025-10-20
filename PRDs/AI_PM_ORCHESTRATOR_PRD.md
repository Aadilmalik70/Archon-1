# PRD: AI-PM Orchestrator Agent

## Overview

**Component**: Orchestrator Agent
**Priority**: P0 (Critical Path)
**Estimated Effort**: 2 weeks
**Owner**: Backend Team
**Dependencies**: Database schema, BaseAgent framework

---

## Problem Statement

Currently, software development tasks require manual planning, breakdown, and assignment. Project managers spend significant time:
- Analyzing feature requests
- Breaking down work into implementable tasks
- Identifying dependencies
- Assigning work to team members
- Estimating effort

**Goal**: Automate this process with an AI agent that can analyze feature requests and create comprehensive task breakdowns with minimal human intervention.

---

## Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Task breakdown accuracy | >85% | Human review of generated tasks |
| Dependency identification | >90% | Correctness of dependency graph |
| Agent assignment accuracy | >80% | Human agreement with assignments |
| Execution time | <30s | Time from request to breakdown |
| Cost per breakdown | <$0.50 | API costs per feature analysis |

---

## User Stories

### Story 1: Feature Request Analysis
**As a** product manager
**I want** to submit a feature request and get a task breakdown
**So that** I can quickly start implementation

**Acceptance Criteria**:
- [ ] Submit feature description via UI, Slack, or Asana
- [ ] Receive structured task breakdown within 30 seconds
- [ ] Tasks include title, description, type, priority
- [ ] Dependencies clearly identified
- [ ] Effort estimates provided

---

### Story 2: Code Context Integration
**As a** developer
**I want** task breakdowns to consider existing code
**So that** tasks align with current architecture

**Acceptance Criteria**:
- [ ] Agent retrieves relevant code from GitHub
- [ ] Tasks reference existing files/functions
- [ ] Identifies code patterns to follow
- [ ] Notes technical constraints

---

### Story 3: Iterative Refinement
**As a** project manager
**I want** to refine generated tasks
**So that** I can adjust based on business needs

**Acceptance Criteria**:
- [ ] Edit task details in UI
- [ ] Add/remove tasks
- [ ] Adjust dependencies
- [ ] Re-run agent with feedback

---

## Functional Requirements

### Core Capabilities

#### FR-1: Feature Analysis
**Description**: Analyze feature requests and extract requirements

**Input**:
```json
{
  "feature_description": "Add user authentication with OAuth",
  "project_id": "uuid",
  "context": {
    "existing_code": ["src/auth/*"],
    "technical_stack": ["React", "FastAPI", "PostgreSQL"],
    "constraints": ["Must support Google OAuth", "GDPR compliant"]
  }
}
```

**Output**:
```json
{
  "subtasks": [
    {
      "id": "task-1",
      "title": "Create OAuth configuration table",
      "description": "Add database schema for storing OAuth provider configs",
      "type": "feature",
      "priority": "high",
      "estimated_effort": "small",
      "assigned_agent": "coding",
      "acceptance_criteria": [
        "Table created with RLS policies",
        "Migration script written",
        "Rollback script created"
      ]
    }
  ],
  "dependencies": {
    "task-2": ["task-1"],
    "task-3": ["task-1", "task-2"]
  },
  "estimated_total_effort": "medium",
  "priority_order": ["task-1", "task-2", "task-3"]
}
```

**Edge Cases**:
- Empty feature description → Request clarification
- Conflicting requirements → Flag for human review
- Unknown technology stack → Ask for context

---

#### FR-2: Task Breakdown
**Description**: Generate atomic, implementable tasks

**Rules**:
- Each task 1-4 hours of work
- Clear acceptance criteria
- Single responsibility
- Testable outcomes

**Task Types**:
- `feature`: New functionality
- `bug`: Bug fixes
- `refactor`: Code improvements
- `test`: Test creation
- `docs`: Documentation

**Task Structure**:
```typescript
interface Task {
  id: string;
  title: string;               // Clear, action-oriented
  description: string;          // Detailed context
  type: TaskType;
  priority: 'low' | 'medium' | 'high' | 'critical';
  estimated_effort: 'small' | 'medium' | 'large';
  assigned_agent: 'coding' | 'qa' | 'docs';
  acceptance_criteria: string[];
  technical_notes: string[];    // Implementation hints
  files_affected: string[];     // Expected file changes
}
```

---

#### FR-3: Dependency Management
**Description**: Identify and manage task dependencies

**Dependency Types**:
1. **Sequential**: Task B requires Task A completion
2. **Blocking**: Task A prevents Task B start
3. **Informational**: Task B benefits from Task A knowledge

**Algorithm**:
```python
def identify_dependencies(tasks: list[Task]) -> dict[str, list[str]]:
    """
    Analyze tasks and build dependency graph

    Rules:
    1. Database migrations before code changes
    2. API endpoints before frontend integration
    3. Tests after implementation
    4. Docs after feature complete
    """
    dependencies = {}

    # Sort by type priority
    priority_order = ['migration', 'feature', 'test', 'docs']

    for task in tasks:
        deps = []

        # Check for schema dependencies
        if task.type == 'feature' and references_db(task):
            migration_tasks = find_tasks_by_type(tasks, 'migration')
            deps.extend([t.id for t in migration_tasks])

        # Check for API dependencies
        if task.files_affected contains frontend files:
            api_tasks = find_tasks_affecting(tasks, 'api')
            deps.extend([t.id for t in api_tasks])

        dependencies[task.id] = deps

    return dependencies
```

---

#### FR-4: Agent Assignment
**Description**: Route tasks to specialized agents

**Assignment Logic**:
```python
def assign_agent(task: Task, code_context: dict) -> str:
    """
    Determine which agent should handle task

    Coding Agent:
    - Implements features
    - Fixes bugs
    - Writes migrations

    QA Agent:
    - Creates tests
    - Runs validation
    - Security scans

    Docs Agent:
    - Updates documentation
    - Writes API specs
    - Generates changelogs
    """
    if task.type in ['feature', 'bug', 'refactor']:
        return 'coding'

    elif task.type == 'test':
        return 'qa'

    elif task.type == 'docs':
        return 'docs'

    else:
        # Default to coding for unknown types
        return 'coding'
```

---

#### FR-5: Effort Estimation
**Description**: Estimate time required for tasks

**Estimation Model**:
```python
class EffortEstimator:
    """Estimate task effort based on complexity signals"""

    SMALL = "1-2 hours"   # Simple changes, single file
    MEDIUM = "2-4 hours"  # Moderate complexity, multiple files
    LARGE = "4-8 hours"   # Complex features, cross-cutting

    def estimate(self, task: Task, code_context: dict) -> str:
        """Calculate effort estimate"""
        complexity_score = 0

        # File count
        if len(task.files_affected) > 5:
            complexity_score += 2
        elif len(task.files_affected) > 2:
            complexity_score += 1

        # New code vs modification
        if task.type == 'feature':
            complexity_score += 2
        elif task.type == 'refactor':
            complexity_score += 1

        # Database changes
        if requires_migration(task):
            complexity_score += 1

        # External integrations
        if has_external_api(task):
            complexity_score += 2

        # Map score to estimate
        if complexity_score <= 2:
            return self.SMALL
        elif complexity_score <= 4:
            return self.MEDIUM
        else:
            return self.LARGE
```

---

### Non-Functional Requirements

#### NFR-1: Performance
- Task breakdown completes in <30 seconds
- Supports up to 20 subtasks per feature
- Handles concurrent requests (5 simultaneous)

#### NFR-2: Reliability
- 95% uptime SLA
- Graceful degradation on API failures
- Automatic retry on transient errors (3 attempts)

#### NFR-3: Cost Efficiency
- <$0.50 per task breakdown
- Token usage optimized (<5K tokens avg)
- Caching for similar requests

#### NFR-4: Security
- Input sanitization prevents prompt injection
- Rate limiting per user (10 requests/minute)
- Audit logging for all executions

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────┐
│           Orchestrator Agent Service            │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────────┐      ┌──────────────────┐  │
│  │ Task Planner  │──────│ Context Builder  │  │
│  └───────────────┘      └──────────────────┘  │
│         │                        │             │
│         │                        │             │
│  ┌──────▼──────────┐    ┌───────▼──────────┐  │
│  │ Decision Engine │    │ Code Analyzer    │  │
│  └─────────────────┘    └──────────────────┘  │
│         │                                      │
│         │                                      │
│  ┌──────▼────────────────────┐                │
│  │  Agent Coordinator        │                │
│  │  (Routes to Specialists)  │                │
│  └───────────────────────────┘                │
│                                                 │
└─────────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
┌────────────────┐    ┌──────────────────┐
│  Coding Agent  │    │    QA Agent      │
└────────────────┘    └──────────────────┘
```

### Database Schema

**Tables Used**:
- `ai_pm_executions`: Track all orchestrator runs
- `archon_tasks`: Store generated tasks
- `agent_configurations`: Agent settings

**Queries**:
```sql
-- Create execution record
INSERT INTO ai_pm_executions (task_id, agent_type, status, input_context)
VALUES ($1, 'orchestrator', 'running', $2)
RETURNING execution_id;

-- Store generated tasks
INSERT INTO archon_tasks (
  project_id, title, description, task_type,
  agent_assigned, automation_status, dependencies
)
VALUES ($1, $2, $3, $4, $5, 'automated', $6);

-- Update execution on completion
UPDATE ai_pm_executions
SET status = 'completed',
    output_result = $1,
    completed_at = NOW()
WHERE execution_id = $2;
```

---

### API Integration

#### Endpoint: Create Task Breakdown
```
POST /api/ai-pm/orchestrate
```

**Request**:
```json
{
  "project_id": "uuid",
  "feature_description": "Add user authentication",
  "source": "ui|slack|asana",
  "context": {
    "github_repo": "owner/repo",
    "technical_stack": ["React", "FastAPI"],
    "constraints": []
  }
}
```

**Response**:
```json
{
  "execution_id": "uuid",
  "status": "completed",
  "tasks": [...],
  "dependencies": {...},
  "estimated_duration": "8-16 hours",
  "cost": 0.42
}
```

---

#### Endpoint: Get Execution Status
```
GET /api/ai-pm/executions/{execution_id}
```

**Response**:
```json
{
  "execution_id": "uuid",
  "status": "running|completed|failed",
  "progress": 0.75,
  "current_step": "Analyzing dependencies",
  "logs": [
    "Started task breakdown",
    "Retrieved code context",
    "Generated 8 tasks"
  ]
}
```

---

### PydanticAI Agent Implementation

```python
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field

class TaskBreakdown(BaseModel):
    """Structured output from orchestrator"""
    subtasks: list[dict] = Field(description="List of atomic tasks")
    dependencies: dict[str, list[str]] = Field(description="Task dependency graph")
    priority_order: list[str] = Field(description="Execution order")
    estimated_effort: dict[str, str] = Field(description="Effort per task")
    agent_assignments: dict[str, str] = Field(description="Agent routing")

# Create agent
orchestrator = Agent(
    'openai:gpt-4o',
    result_type=TaskBreakdown,
    system_prompt="""You are an AI Product Manager...""",
    retries=3
)

# Register tools
@orchestrator.tool
async def search_codebase(ctx: RunContext, query: str) -> list[str]:
    """Search existing code for context"""
    # Use knowledge base RAG search
    results = await knowledge_service.search(query)
    return [r.content for r in results]

@orchestrator.tool
async def get_similar_tasks(ctx: RunContext, description: str) -> list[dict]:
    """Find similar past tasks"""
    # Use task embeddings for similarity
    similar = await task_service.search_similar(description)
    return similar
```

---

## Testing Strategy

### Unit Tests
```python
# test_orchestrator_agent.py
async def test_task_breakdown():
    """Test basic task breakdown"""
    agent = OrchestratorAgent()

    result = await agent.run(
        "Add user authentication with OAuth",
        deps=OrchestratorDependencies(project_id="test")
    )

    assert len(result.subtasks) > 0
    assert "oauth" in result.subtasks[0]["title"].lower()
    assert result.dependencies is not None

async def test_dependency_detection():
    """Test dependency graph generation"""
    agent = OrchestratorAgent()

    result = await agent.run(
        "Create API endpoint and frontend form",
        deps=OrchestratorDependencies(project_id="test")
    )

    # Frontend task should depend on API task
    frontend_tasks = [t for t in result.subtasks if "frontend" in t["title"].lower()]
    api_tasks = [t for t in result.subtasks if "api" in t["title"].lower()]

    assert len(frontend_tasks) > 0
    assert len(api_tasks) > 0

    # Check dependency
    frontend_id = frontend_tasks[0]["id"]
    api_id = api_tasks[0]["id"]

    assert api_id in result.dependencies.get(frontend_id, [])
```

### Integration Tests
```python
async def test_full_orchestration_flow():
    """Test end-to-end orchestration"""
    # Submit feature request
    response = await client.post("/api/ai-pm/orchestrate", json={
        "project_id": test_project_id,
        "feature_description": "Add dark mode support"
    })

    assert response.status_code == 200
    execution_id = response.json()["execution_id"]

    # Wait for completion (with timeout)
    result = await wait_for_completion(execution_id, timeout=60)

    assert result["status"] == "completed"
    assert len(result["tasks"]) > 0

    # Verify tasks created in database
    tasks = await db.get_tasks_by_project(test_project_id)
    assert len(tasks) == len(result["tasks"])
```

---

## Rollout Plan

### Phase 1: Internal Testing (Week 1)
- Deploy to staging environment
- Test with 5 sample feature requests
- Validate task quality with team
- Fix critical bugs

**Success Criteria**:
- [ ] All 5 tests produce valid task breakdowns
- [ ] No critical errors in logs
- [ ] Avg execution time <30s

### Phase 2: Limited Beta (Week 2)
- Enable for 2 real projects
- Monitor execution metrics
- Gather user feedback
- Iterate on prompts

**Success Criteria**:
- [ ] 80% user satisfaction
- [ ] 90% task accuracy
- [ ] <$1 avg cost per breakdown

### Phase 3: General Availability (Week 3)
- Enable for all projects
- Add to UI prominently
- Integrate with Slack/Asana
- Monitor scaling

**Success Criteria**:
- [ ] 100 successful executions
- [ ] 95% uptime
- [ ] Positive user feedback

---

## Monitoring & Observability

### Metrics to Track
```python
# Execution metrics
- executions_total (counter)
- execution_duration_seconds (histogram)
- execution_errors_total (counter)
- tasks_generated_total (counter)
- api_cost_dollars (gauge)

# Quality metrics
- task_accuracy_score (gauge) # From human review
- dependency_correctness (gauge)
- agent_assignment_agreement (gauge)
```

### Logging
```python
logger.info("Orchestrator started", extra={
    "execution_id": execution_id,
    "project_id": project_id,
    "feature": feature_description[:100]
})

logger.info("Tasks generated", extra={
    "execution_id": execution_id,
    "task_count": len(tasks),
    "duration_seconds": duration
})

logger.error("Orchestration failed", extra={
    "execution_id": execution_id,
    "error": str(e),
    "stack_trace": traceback.format_exc()
})
```

---

## Open Questions

1. **Should orchestrator auto-execute tasks or require approval?**
   - Option A: Auto-execute, allow cancellation
   - Option B: Require explicit approval
   - **Recommendation**: Start with approval, add auto-execute later

2. **How to handle feedback loops?**
   - User modifies tasks, should orchestrator re-analyze?
   - **Recommendation**: Track modifications, offer re-analysis

3. **Cost optimization strategy?**
   - Use cheaper models for simple breakdowns?
   - **Recommendation**: Start with GPT-4o, optimize later

---

## Success Criteria

**Launch Requirements**:
- [ ] Generates valid task breakdowns for 10 test cases
- [ ] 90% accuracy on dependency detection
- [ ] <30s execution time (95th percentile)
- [ ] <$0.50 avg cost per breakdown
- [ ] Zero data loss or corruption
- [ ] Comprehensive error handling
- [ ] Full test coverage (>80%)
- [ ] Documentation complete
- [ ] Security review passed

**Post-Launch (30 days)**:
- [ ] 100 successful orchestrations
- [ ] 85% user satisfaction (survey)
- [ ] <5% error rate
- [ ] Positive cost/benefit analysis

---

## References

- [PydanticAI Documentation](https://ai.pydantic.dev)
- [Archon BaseAgent](../python/src/agents/base_agent.py)
- [Task Service](../python/src/server/services/projects/task_service.py)
- [Database Schema](../migration/complete_setup.sql)
