"""
AI-PM Orchestrator Agent

Main orchestrator that analyzes feature requests, breaks them down into tasks,
and coordinates execution across specialized agents.
"""

from typing import Any
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from ..base_agent import BaseAgent, ArchonDependencies
from ...server.config.logfire_config import get_logger

logger = get_logger(__name__)


# =====================================================
# OUTPUT MODELS
# =====================================================


class SubTask(BaseModel):
    """Individual task within a breakdown"""

    title: str = Field(description="Clear, action-oriented task title")
    description: str = Field(description="Detailed task description with context")
    task_type: str = Field(
        description="Task type: feature, bug, refactor, test, docs, security, performance"
    )
    priority: str = Field(description="Priority: low, medium, high, critical")
    estimated_effort: str = Field(
        description="Effort estimate: small (1-2h), medium (2-4h), large (4-8h)"
    )
    assigned_agent: str = Field(
        description="Agent to handle task: coding, qa, docs, security, performance"
    )
    acceptance_criteria: list[str] = Field(
        description="List of acceptance criteria for task completion"
    )
    technical_notes: list[str] = Field(
        default_factory=list, description="Implementation hints and constraints"
    )
    files_affected: list[str] = Field(
        default_factory=list, description="Files expected to change"
    )


class TaskBreakdown(BaseModel):
    """Complete task breakdown output from orchestrator"""

    subtasks: list[SubTask] = Field(
        description="List of atomic subtasks with full details"
    )
    dependencies: dict[str, list[str]] = Field(
        description="Map of task_id to list of dependency task_ids (by title for matching)"
    )
    priority_order: list[str] = Field(
        description="Ordered list of task titles by execution priority"
    )
    estimated_total_effort: str = Field(
        description="Total effort estimate: small, medium, large, or XL"
    )
    technical_summary: str = Field(
        description="High-level technical approach and architecture notes"
    )
    risks: list[str] = Field(
        default_factory=list, description="Identified risks and concerns"
    )


# =====================================================
# DEPENDENCIES
# =====================================================


@dataclass
class OrchestratorDependencies(ArchonDependencies):
    """Dependencies for orchestrator agent"""

    project_id: str | None = None
    feature_description: str | None = None
    existing_tasks: list[dict] | None = None
    code_context: dict[str, Any] | None = None
    technical_constraints: list[str] | None = None


# =====================================================
# ORCHESTRATOR AGENT
# =====================================================


class OrchestratorAgent(BaseAgent[OrchestratorDependencies, TaskBreakdown]):
    """
    AI Product Manager Orchestrator

    Responsibilities:
    - Analyze feature requests and requirements
    - Break down features into atomic, implementable tasks
    - Identify dependencies between tasks
    - Assign tasks to specialized agents (coding, qa, docs)
    - Estimate effort for each task
    - Prioritize tasks based on dependencies and value
    """

    def __init__(self):
        super().__init__(
            model="openai:gpt-4o",
            name="OrchestratorAgent",
            retries=3,
            enable_rate_limiting=True,
        )

    def _create_agent(self, **kwargs) -> Agent:
        """Create PydanticAI agent with tools and system prompt"""
        agent = Agent(
            self.model,
            result_type=TaskBreakdown,
            system_prompt=self.get_system_prompt(),
            retries=self.retries,
        )

        # Register tools
        self._register_tools(agent)

        return agent

    def get_system_prompt(self) -> str:
        return """You are an AI Product Manager orchestrating software development for Archon, a knowledge management system.

Your responsibilities:
1. Analyze feature requests and extract clear requirements
2. Break down features into atomic, implementable tasks (1-4 hours each)
3. Identify dependencies between tasks (database before code, API before frontend, implementation before tests)
4. Assign tasks to the most appropriate specialized agent
5. Estimate effort realistically
6. Prioritize based on dependencies and business value
7. Consider existing architecture and patterns

Guidelines for task breakdown:
- Tasks should be SMALL and FOCUSED (1-4 hours maximum)
- Always include testing tasks for new features
- Documentation should follow implementation
- Consider code quality, security, and performance
- Identify clear, measurable acceptance criteria
- Note external dependencies (APIs, libraries, services)
- Follow Archon's existing patterns (service layer, vertical slices, TanStack Query)

Agent Assignment Rules:
- **coding**: Implements features, fixes bugs, writes migrations, creates API endpoints
- **qa**: Creates tests, runs validation, performs security scans, checks coverage
- **docs**: Updates documentation, API specs, README files, generates code comments

Task Types:
- **feature**: New functionality or capability
- **bug**: Bug fixes and corrections
- **refactor**: Code improvements and cleanup
- **test**: Test creation and updates
- **docs**: Documentation updates
- **security**: Security improvements and audits
- **performance**: Performance optimization

Effort Estimation:
- **small** (1-2 hours): Simple changes, single file modifications, straightforward implementations
- **medium** (2-4 hours): Moderate complexity, multiple files, some integration work
- **large** (4-8 hours): Complex features, cross-cutting changes, significant integration

Archon Architecture Context:
- **Backend**: Python + FastAPI + Supabase (PostgreSQL + pgvector)
- **Frontend**: React + TypeScript + TanStack Query + Tailwind CSS
- **Agents**: PydanticAI framework with BaseAgent pattern
- **Database**: Service layer pattern, RLS policies, migration system
- **UI**: Vertical slice architecture in `features/` directory

Always provide:
1. Comprehensive task breakdown with all required fields
2. Clear dependency mapping (implementation → testing → documentation)
3. Realistic effort estimates
4. Specific acceptance criteria
5. Technical notes for implementation guidance
6. Risk identification

Remember: Tasks must be atomic and independently testable. Each task should have a clear definition of "done"."""

    def _register_tools(self, agent: Agent):
        """Register tools for the orchestrator agent"""

        @agent.tool
        async def get_existing_tasks(
            ctx: RunContext[OrchestratorDependencies],
        ) -> list[dict]:
            """
            Get existing tasks for the project to avoid duplication and understand current work

            Returns:
                List of existing task objects with title, status, and description
            """
            if ctx.deps.existing_tasks:
                logger.info(
                    f"Retrieved {len(ctx.deps.existing_tasks)} existing tasks"
                )
                return ctx.deps.existing_tasks

            logger.info("No existing tasks provided")
            return []

        @agent.tool
        async def get_code_context(
            ctx: RunContext[OrchestratorDependencies],
        ) -> dict[str, Any]:
            """
            Get relevant code context from the project (files, structure, dependencies)

            Returns:
                Dictionary with code context including files, patterns, and architecture info
            """
            if ctx.deps.code_context:
                logger.info("Retrieved code context for planning")
                return ctx.deps.code_context

            logger.info("No code context provided, using defaults")
            return {
                "files": [],
                "dependencies": [],
                "patterns": "Follow Archon service layer and vertical slice patterns",
            }

        @agent.tool
        async def get_technical_constraints(
            ctx: RunContext[OrchestratorDependencies],
        ) -> list[str]:
            """
            Get technical constraints and requirements for this feature

            Returns:
                List of constraint strings
            """
            if ctx.deps.technical_constraints:
                logger.info(
                    f"Retrieved {len(ctx.deps.technical_constraints)} technical constraints"
                )
                return ctx.deps.technical_constraints

            return [
                "Follow Archon's beta development principles (fail fast and loud)",
                "Use existing BaseAgent framework for new agents",
                "Follow service layer pattern for backend",
                "Use TanStack Query for frontend data fetching",
                "Implement proper error handling and logging",
            ]

        @agent.tool
        async def search_similar_features(
            ctx: RunContext[OrchestratorDependencies], query: str
        ) -> list[dict]:
            """
            Search for similar past features or tasks to learn from previous implementations

            Args:
                query: Search query describing the feature or problem

            Returns:
                List of similar features with implementation details
            """
            # TODO: Implement similarity search using embeddings from knowledge base
            logger.info(f"Searching for similar features: {query}")

            # Placeholder - would integrate with knowledge base search
            return [
                {
                    "title": "Similar feature pattern available in knowledge base",
                    "suggestion": "Use existing patterns when available",
                }
            ]


# =====================================================
# HELPER FUNCTIONS
# =====================================================


async def plan_feature(
    feature_description: str,
    project_id: str | None = None,
    existing_tasks: list[dict] | None = None,
    code_context: dict | None = None,
    constraints: list[str] | None = None,
) -> TaskBreakdown:
    """
    Plan a feature using the orchestrator agent

    Args:
        feature_description: Natural language description of the feature
        project_id: Optional project ID for context
        existing_tasks: Optional list of existing tasks to avoid duplication
        code_context: Optional code context from knowledge base
        constraints: Optional technical constraints

    Returns:
        TaskBreakdown with subtasks, dependencies, and execution plan
    """
    orchestrator = OrchestratorAgent()

    deps = OrchestratorDependencies(
        project_id=project_id,
        feature_description=feature_description,
        existing_tasks=existing_tasks or [],
        code_context=code_context or {},
        technical_constraints=constraints or [],
        request_id=f"feature-plan-{project_id or 'unknown'}",
    )

    prompt = f"""Analyze this feature request and create a comprehensive task breakdown:

Feature Request: {feature_description}

Context:
- Project ID: {project_id or "Not specified"}
- Existing Tasks: {len(existing_tasks) if existing_tasks else 0} tasks already exist
- Technical Stack: Python/FastAPI backend, React/TypeScript frontend, Supabase database
- Architecture: Service layer pattern, vertical slice frontend, PydanticAI agents

Please provide:
1. Complete breakdown of all implementation tasks
2. Testing tasks for each feature component
3. Documentation tasks
4. Clear dependency relationships (database → backend → frontend → tests → docs)
5. Realistic effort estimates
6. Specific acceptance criteria
7. Technical implementation notes
8. Identified risks or challenges

Remember to keep tasks atomic (1-4 hours) and assign to appropriate agents."""

    logger.info(f"Planning feature: {feature_description[:100]}...")

    try:
        result = await orchestrator.run(prompt, deps)
        logger.info(
            f"Generated {len(result.subtasks)} tasks, "
            f"total effort: {result.estimated_total_effort}"
        )
        return result
    except Exception as e:
        logger.error(f"Failed to plan feature: {str(e)}", exc_info=True)
        raise


# =====================================================
# EXAMPLE USAGE
# =====================================================

if __name__ == "__main__":
    import asyncio

    async def test_orchestrator():
        """Test the orchestrator with a sample feature"""

        result = await plan_feature(
            feature_description="Add user authentication with OAuth support for Google and GitHub",
            project_id="test-project-123",
            existing_tasks=[
                {
                    "title": "Set up database schema",
                    "status": "done",
                    "description": "Created archon_tasks and archon_projects tables",
                }
            ],
            constraints=[
                "Must support GDPR compliance",
                "Use Supabase Auth where possible",
                "Implement proper session management",
            ],
        )

        print("\n" + "=" * 60)
        print("ORCHESTRATOR TASK BREAKDOWN")
        print("=" * 60)
        print(f"\nTotal Tasks: {len(result.subtasks)}")
        print(f"Total Effort: {result.estimated_total_effort}")
        print(f"\nTechnical Summary:\n{result.technical_summary}")

        print(f"\n{'='*60}")
        print("SUBTASKS")
        print("=" * 60)

        for i, task in enumerate(result.subtasks, 1):
            print(f"\n{i}. {task.title}")
            print(f"   Type: {task.task_type} | Agent: {task.assigned_agent}")
            print(f"   Effort: {task.estimated_effort} | Priority: {task.priority}")
            print(f"   Description: {task.description[:100]}...")

        print(f"\n{'='*60}")
        print("DEPENDENCIES")
        print("=" * 60)
        for task_title, deps in result.dependencies.items():
            if deps:
                print(f"\n{task_title}")
                print(f"  Depends on: {', '.join(deps)}")

        if result.risks:
            print(f"\n{'='*60}")
            print("IDENTIFIED RISKS")
            print("=" * 60)
            for risk in result.risks:
                print(f"  - {risk}")

    # Run test
    asyncio.run(test_orchestrator())
