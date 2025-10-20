"""
Integration tools for AI-PM Orchestrator

Provides functions to send notifications to Slack and Asana
when tasks are created, updated, or completed by agents
"""

from typing import Any

from ....server.config.logfire_config import get_logger

logger = get_logger(__name__)


async def notify_slack_task_created(
    project_id: str,
    task: dict[str, Any],
    breakdown_summary: str | None = None,
) -> bool:
    """
    Send Slack notification when tasks are created by AI-PM

    Args:
        project_id: Project ID
        task: Task object created
        breakdown_summary: Optional summary of full breakdown

    Returns:
        True if notification sent successfully
    """
    try:
        from ....server.integrations.slack.slack_service import SlackService

        # Send task creation notification
        responses = await SlackService.send_task_notification(
            project_id=project_id,
            task=task,
            notification_type="task_created",
        )

        if responses:
            logger.info(
                f"Sent Slack notification for task: {task.get('title')} to {len(responses)} channels"
            )
            return True
        else:
            logger.debug(f"No Slack channels configured for project {project_id}")
            return False

    except Exception as e:
        logger.error(f"Failed to send Slack notification: {str(e)}", exc_info=True)
        return False


async def notify_slack_task_completed(
    project_id: str,
    task: dict[str, Any],
    execution_result: dict[str, Any] | None = None,
) -> bool:
    """
    Send Slack notification when task is completed by agent

    Args:
        project_id: Project ID
        task: Completed task object
        execution_result: Optional execution result details

    Returns:
        True if notification sent successfully
    """
    try:
        from ....server.integrations.slack.slack_service import SlackService

        # Send task completion notification
        responses = await SlackService.send_task_notification(
            project_id=project_id,
            task=task,
            notification_type="task_completed",
        )

        if responses:
            logger.info(
                f"Sent Slack completion notification for task: {task.get('title')}"
            )
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to send Slack completion notification: {str(e)}", exc_info=True)
        return False


async def notify_slack_agent_action(
    project_id: str,
    agent_type: str,
    action: str,
    details: dict[str, Any],
) -> bool:
    """
    Send Slack notification for important agent actions

    Args:
        project_id: Project ID
        agent_type: Type of agent (orchestrator, coding, qa, docs)
        action: Action taken (started, completed, failed, etc.)
        details: Action details

    Returns:
        True if notification sent successfully
    """
    try:
        from ....server.integrations.slack.slack_service import SlackService

        # Send agent action notification
        responses = await SlackService.send_agent_notification(
            project_id=project_id,
            agent_type=agent_type,
            action=action,
            details=details,
        )

        if responses:
            logger.info(
                f"Sent Slack agent notification: {agent_type} - {action}"
            )
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to send agent action notification: {str(e)}", exc_info=True)
        return False


async def create_asana_task(
    project_id: str,
    task: dict[str, Any],
) -> str | None:
    """
    Create corresponding task in Asana when AI-PM creates a task

    Args:
        project_id: Archon project ID
        task: Task object to create in Asana

    Returns:
        Asana task GID if successful, None otherwise
    """
    try:
        from ....server.integrations.asana.asana_sync import AsanaSync
        from ....server.utils import get_supabase_client

        supabase = get_supabase_client()

        # Check if project has Asana mapping
        mapping = (
            supabase.table("asana_projects")
            .select("asana_project_id")
            .eq("archon_project_id", project_id)
            .eq("sync_enabled", True)
            .execute()
        )

        if not mapping.data:
            logger.debug(f"Project {project_id} not linked to Asana")
            return None

        asana_project_id = mapping.data[0]["asana_project_id"]

        # Sync task to Asana
        asana_gid = await AsanaSync.sync_task_to_asana(task, asana_project_id)

        if asana_gid:
            logger.info(
                f"Created Asana task {asana_gid} for: {task.get('title')}"
            )

        return asana_gid

    except Exception as e:
        logger.error(f"Failed to create Asana task: {str(e)}", exc_info=True)
        return None


async def update_asana_task_status(
    task_id: str,
    new_status: str,
    execution_metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Update Asana task status when Archon task status changes

    Args:
        task_id: Archon task ID
        new_status: New status (todo, doing, review, done)
        execution_metadata: Optional metadata about execution

    Returns:
        True if Asana updated successfully
    """
    try:
        from ....server.integrations.asana.asana_sync import AsanaSync
        from ....server.utils import get_supabase_client

        supabase = get_supabase_client()

        # Get full task details
        task_result = (
            supabase.table("archon_tasks")
            .select("*")
            .eq("id", task_id)
            .single()
            .execute()
        )

        if not task_result.data:
            logger.error(f"Task {task_id} not found")
            return False

        task = task_result.data

        if not task.get("asana_task_id"):
            logger.debug(f"Task {task_id} not synced with Asana")
            return False

        # Get Asana project mapping
        mapping = (
            supabase.table("asana_projects")
            .select("asana_project_id")
            .eq("archon_project_id", task["project_id"])
            .eq("sync_enabled", True)
            .execute()
        )

        if not mapping.data:
            logger.debug(f"Project not linked to Asana")
            return False

        asana_project_id = mapping.data[0]["asana_project_id"]

        # Sync updated task to Asana
        asana_gid = await AsanaSync.sync_task_to_asana(task, asana_project_id)

        if asana_gid:
            logger.info(
                f"Updated Asana task status for: {task.get('title')}"
            )
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to update Asana task: {str(e)}", exc_info=True)
        return False


async def sync_task_comments(
    task_id: str,
    comment: str,
    source: str = "archon",
) -> bool:
    """
    Sync comments between Archon and Asana

    Args:
        task_id: Archon task ID
        comment: Comment text
        source: Source of comment (archon or asana)

    Returns:
        True if comment synced successfully
    """
    try:
        # TODO: Implement bidirectional comment sync
        # This will:
        # - If source=archon: Post comment to Asana
        # - If source=asana: Store in Archon (execution_metadata?)
        # - Prevent infinite loops with sync tracking

        logger.info(f"Comment sync queued for task {task_id} from {source}")

        return True

    except Exception as e:
        logger.error(f"Failed to sync comment: {str(e)}", exc_info=True)
        return False


async def notify_all_integrations(
    event_type: str,
    project_id: str,
    data: dict[str, Any],
) -> dict[str, bool]:
    """
    Send notifications to all configured integrations for a project

    Args:
        event_type: Type of event (task_created, task_completed, agent_action, etc.)
        project_id: Project ID
        data: Event data

    Returns:
        Dictionary of integration -> success status
    """
    from ....server.utils import get_supabase_client

    supabase = get_supabase_client()
    results = {}

    try:
        # Check which integrations are configured for this project
        slack_configured = supabase.table("slack_channels").select("*").eq(
            "project_id", project_id
        ).execute()

        asana_configured = supabase.table("asana_projects").select("*").eq(
            "archon_project_id", project_id
        ).eq("sync_enabled", True).execute()

        # Send to Slack if configured
        if slack_configured.data:
            if event_type == "task_created":
                results["slack"] = await notify_slack_task_created(
                    project_id, data.get("task", {}), data.get("summary")
                )
            elif event_type == "task_completed":
                results["slack"] = await notify_slack_task_completed(
                    project_id, data.get("task", {}), data.get("execution_result")
                )
            elif event_type == "agent_action":
                results["slack"] = await notify_slack_agent_action(
                    project_id,
                    data.get("agent_type", ""),
                    data.get("action", ""),
                    data.get("details", {}),
                )

        # Send to Asana if configured
        if asana_configured.data:
            if event_type == "task_created":
                asana_id = await create_asana_task(project_id, data.get("task", {}))
                results["asana"] = asana_id is not None
            elif event_type == "task_status_changed":
                results["asana"] = await update_asana_task_status(
                    data.get("task_id", ""),
                    data.get("new_status", ""),
                    data.get("execution_metadata"),
                )

        logger.info(
            f"Sent {event_type} notifications for project {project_id}: {results}"
        )

        return results

    except Exception as e:
        logger.error(f"Failed to notify integrations: {str(e)}", exc_info=True)
        return {"error": str(e)}
