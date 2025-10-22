"""
Task Execution Orchestrator

Coordinates task execution workflow:
1. Monitors task status changes
2. Reports progress to Slack
3. Manages task dependencies and execution order
4. Sends final summary when all tasks complete
"""

import asyncio
from typing import Any

from ...server.config.logfire_config import get_logger
from ...server.utils import get_supabase_client
from .progress_reporter import ProgressReporter

logger = get_logger(__name__)


class TaskExecutor:
    """Manages task execution workflow and progress monitoring"""

    def __init__(self, project_id: str, notify_slack: bool = True):
        """
        Initialize task executor.

        Args:
            project_id: Project ID to monitor
            notify_slack: Whether to send Slack notifications
        """
        self.project_id = project_id
        self.notify_slack = notify_slack
        self.reporter = ProgressReporter() if notify_slack else None
        self.task_status_cache: dict[str, str] = {}

    async def monitor_task_execution(
        self,
        poll_interval: int = 30,
        max_iterations: int = 200,  # 100 minutes max
    ) -> dict[str, Any]:
        """
        Monitor task execution and report progress.

        This method polls the database for task status changes and sends
        Slack notifications when tasks transition between states.

        Args:
            poll_interval: Seconds between status checks
            max_iterations: Maximum number of polling iterations

        Returns:
            Summary dict with task execution statistics
        """
        logger.info(f"Starting task execution monitoring for project {self.project_id}")

        summary = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "in_progress_tasks": 0,
            "iterations": 0,
        }

        try:
            for iteration in range(max_iterations):
                summary["iterations"] = iteration + 1

                # Get current task status
                tasks = await self._get_project_tasks()
                if not tasks:
                    logger.warning(f"No tasks found for project {self.project_id}")
                    break

                summary["total_tasks"] = len(tasks)

                # Check for status changes
                for task in tasks:
                    task_id = task["id"]
                    current_status = task["status"]
                    old_status = self.task_status_cache.get(task_id)

                    # First time seeing this task
                    if old_status is None:
                        self.task_status_cache[task_id] = current_status
                        continue

                    # Status changed
                    if old_status != current_status:
                        logger.info(
                            f"Task '{task['title']}' status changed: {old_status} → {current_status}"
                        )

                        await self._handle_status_change(
                            task=task,
                            old_status=old_status,
                            new_status=current_status,
                        )

                        self.task_status_cache[task_id] = current_status

                # Calculate current counts
                summary["completed_tasks"] = sum(
                    1 for t in tasks if t["status"] == "done"
                )
                summary["failed_tasks"] = 0  # Could track failed tasks separately
                summary["in_progress_tasks"] = sum(
                    1 for t in tasks if t["status"] in ("doing", "review")
                )

                # Check if all tasks are complete
                if summary["completed_tasks"] >= summary["total_tasks"]:
                    logger.info("All tasks completed!")
                    if self.notify_slack:
                        await self.reporter.notify_all_tasks_complete(
                            project_id=self.project_id,
                            summary=summary,
                        )
                    break

                # Wait before next poll
                await asyncio.sleep(poll_interval)

            logger.info(
                f"Task monitoring complete. "
                f"{summary['completed_tasks']}/{summary['total_tasks']} tasks finished "
                f"in {summary['iterations']} iterations"
            )

            return summary

        except Exception as e:
            logger.error(f"Error in task execution monitoring: {str(e)}", exc_info=True)
            summary["error"] = str(e)
            return summary

    async def _get_project_tasks(self) -> list[dict]:
        """Get all tasks for the project."""
        try:
            supabase = get_supabase_client()
            result = (
                supabase.table("archon_tasks")
                .select("*")
                .eq("project_id", self.project_id)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting project tasks: {str(e)}")
            return []

    async def _handle_status_change(
        self,
        task: dict,
        old_status: str,
        new_status: str,
    ) -> None:
        """
        Handle task status change with appropriate notifications.

        Args:
            task: Task object
            old_status: Previous status
            new_status: New status
        """
        try:
            if not self.notify_slack:
                return

            # Task started (todo → doing)
            if old_status == "todo" and new_status == "doing":
                await self.reporter.notify_task_started(
                    project_id=self.project_id,
                    task=task,
                )

            # Task completed (review → done)
            elif old_status == "review" and new_status == "done":
                await self.reporter.notify_task_completed(
                    project_id=self.project_id,
                    task=task,
                )

            # Other status transitions (doing → review, etc.)
            else:
                await self.reporter.notify_task_progress(
                    project_id=self.project_id,
                    task=task,
                    old_status=old_status,
                    new_status=new_status,
                )

        except Exception as e:
            logger.error(f"Error handling status change: {str(e)}", exc_info=True)

    async def get_execution_summary(self) -> dict[str, Any]:
        """
        Get current execution summary without monitoring.

        Returns:
            Summary dict with current task counts
        """
        try:
            tasks = await self._get_project_tasks()

            return {
                "total_tasks": len(tasks),
                "completed_tasks": sum(1 for t in tasks if t["status"] == "done"),
                "in_progress_tasks": sum(1 for t in tasks if t["status"] in ("doing", "review")),
                "todo_tasks": sum(1 for t in tasks if t["status"] == "todo"),
            }

        except Exception as e:
            logger.error(f"Error getting execution summary: {str(e)}")
            return {
                "error": str(e),
                "total_tasks": 0,
                "completed_tasks": 0,
                "in_progress_tasks": 0,
                "todo_tasks": 0,
            }


# Convenience function
async def start_task_monitoring(
    project_id: str,
    notify_slack: bool = True,
    poll_interval: int = 30,
) -> dict[str, Any]:
    """
    Start monitoring task execution for a project (convenience function).

    Args:
        project_id: Project ID to monitor
        notify_slack: Whether to send Slack notifications
        poll_interval: Seconds between status checks

    Returns:
        Summary dict with execution statistics
    """
    executor = TaskExecutor(project_id=project_id, notify_slack=notify_slack)
    return await executor.monitor_task_execution(poll_interval=poll_interval)
