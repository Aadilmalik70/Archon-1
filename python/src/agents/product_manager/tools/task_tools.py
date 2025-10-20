"""
Task management tools for AI-PM Orchestrator

Provides functions to create, update, and query tasks in the database
"""

from typing import Any
from uuid import uuid4

from ....server.config.logfire_config import get_logger
from ....server.utils import get_supabase_client

logger = get_logger(__name__)


async def create_tasks_from_breakdown(
    breakdown: dict[str, Any], project_id: str, execution_id: str | None = None
) -> list[dict]:
    """
    Create tasks in database from orchestrator breakdown

    Args:
        breakdown: TaskBreakdown output from orchestrator
        project_id: Project to create tasks in
        execution_id: Optional execution ID for tracking

    Returns:
        List of created task objects with IDs
    """
    supabase = get_supabase_client()
    created_tasks = []

    try:
        subtasks = breakdown.get("subtasks", [])
        logger.info(f"Creating {len(subtasks)} tasks for project {project_id}")

        # Create tasks in database
        for idx, subtask in enumerate(subtasks):
            task_data = {
                "project_id": project_id,
                "title": subtask.get("title"),
                "description": subtask.get("description"),
                "status": "todo",
                "priority": subtask.get("priority", "medium"),
                "task_order": idx,
                # AI-PM specific fields
                "agent_assigned": subtask.get("assigned_agent"),
                "task_type": subtask.get("task_type"),
                "context_summary": subtask.get("description", "")[
                    :500
                ],  # First 500 chars
                "automation_status": "pending",  # Ready for agent execution
                "execution_metadata": {
                    "execution_id": execution_id,
                    "estimated_effort": subtask.get("estimated_effort"),
                    "acceptance_criteria": subtask.get("acceptance_criteria", []),
                    "technical_notes": subtask.get("technical_notes", []),
                    "files_affected": subtask.get("files_affected", []),
                },
            }

            result = supabase.table("archon_tasks").insert(task_data).execute()

            if result.data:
                created_task = result.data[0]
                created_tasks.append(created_task)
                logger.debug(f"Created task: {created_task['id']} - {created_task['title']}")
            else:
                logger.error(f"Failed to create task: {subtask.get('title')}")

        # Update dependencies after all tasks created
        if breakdown.get("dependencies"):
            await _update_task_dependencies(
                created_tasks, breakdown["dependencies"], breakdown["subtasks"]
            )

        logger.info(f"Successfully created {len(created_tasks)} tasks")
        return created_tasks

    except Exception as e:
        logger.error(f"Failed to create tasks from breakdown: {str(e)}", exc_info=True)
        raise


async def _update_task_dependencies(
    created_tasks: list[dict], dependency_map: dict, subtasks: list[dict]
):
    """
    Update task dependencies based on breakdown

    Args:
        created_tasks: List of created task objects with IDs
        dependency_map: Map of task titles to dependency titles
        subtasks: Original subtask list for matching
    """
    supabase = get_supabase_client()

    # Build title → ID mapping
    title_to_id = {task["title"]: task["id"] for task in created_tasks}

    for task in created_tasks:
        task_title = task["title"]

        # Get dependency titles for this task
        dep_titles = dependency_map.get(task_title, [])
        if not dep_titles:
            continue

        # Convert titles to IDs
        dep_ids = []
        for dep_title in dep_titles:
            if dep_title in title_to_id:
                dep_ids.append(title_to_id[dep_title])
            else:
                logger.warning(f"Dependency not found: {dep_title} for {task_title}")

        if dep_ids:
            # Update task with dependencies
            supabase.table("archon_tasks").update({"dependencies": dep_ids}).eq(
                "id", task["id"]
            ).execute()

            logger.debug(f"Set {len(dep_ids)} dependencies for task {task_title}")


async def get_project_tasks(
    project_id: str, include_done: bool = False
) -> list[dict]:
    """
    Get all tasks for a project

    Args:
        project_id: Project ID to query
        include_done: Whether to include completed tasks

    Returns:
        List of task objects
    """
    supabase = get_supabase_client()

    try:
        query = supabase.table("archon_tasks").select("*").eq(
            "project_id", project_id
        )

        if not include_done:
            query = query.neq("status", "done")

        result = query.order("task_order").execute()

        tasks = result.data or []
        logger.debug(f"Retrieved {len(tasks)} tasks for project {project_id}")
        return tasks

    except Exception as e:
        logger.error(f"Failed to get project tasks: {str(e)}", exc_info=True)
        return []


async def update_task_status(
    task_id: str, status: str, execution_metadata: dict | None = None
) -> dict | None:
    """
    Update task status and optional execution metadata

    Args:
        task_id: Task ID to update
        status: New status (todo, doing, review, done)
        execution_metadata: Optional metadata to merge

    Returns:
        Updated task object or None if failed
    """
    supabase = get_supabase_client()

    try:
        update_data = {"status": status}

        if execution_metadata:
            # Get current metadata
            current = supabase.table("archon_tasks").select("execution_metadata").eq(
                "id", task_id
            ).single().execute()

            current_meta = current.data.get("execution_metadata", {}) if current.data else {}

            # Merge metadata
            merged_meta = {**current_meta, **execution_metadata}
            update_data["execution_metadata"] = merged_meta

        result = supabase.table("archon_tasks").update(update_data).eq(
            "id", task_id
        ).execute()

        if result.data:
            logger.info(f"Updated task {task_id} status to {status}")
            return result.data[0]
        else:
            logger.error(f"Failed to update task {task_id}")
            return None

    except Exception as e:
        logger.error(f"Failed to update task status: {str(e)}", exc_info=True)
        return None


async def get_ready_tasks(
    project_id: str | None = None, agent_type: str | None = None
) -> list[dict]:
    """
    Get tasks that are ready to execute (dependencies complete)

    Args:
        project_id: Optional filter by project
        agent_type: Optional filter by assigned agent

    Returns:
        List of ready tasks
    """
    supabase = get_supabase_client()

    try:
        # Use the database function
        result = supabase.rpc("get_ready_tasks", {"p_agent_type": agent_type}).execute()

        tasks = result.data or []

        # Filter by project if specified
        if project_id:
            tasks = [t for t in tasks if t.get("project_id") == project_id]

        logger.debug(
            f"Found {len(tasks)} ready tasks "
            f"(project: {project_id or 'all'}, agent: {agent_type or 'all'})"
        )

        return tasks

    except Exception as e:
        logger.error(f"Failed to get ready tasks: {str(e)}", exc_info=True)
        return []
