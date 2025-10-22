"""
Feature Executor Orchestrator

Manages automated execution of all tasks for a feature.
Coordinates with ClaudeCodeExecutor and ProgressReporter.
"""

import asyncio
import logging
from typing import Any

from ...server.services.client_manager import get_supabase_client
from ..claude_code_executor.claude_agent import ClaudeCodeExecutor
from .progress_reporter import ProgressReporter

logger = logging.getLogger(__name__)


class FeatureExecutor:
    """Orchestrates automated execution of feature tasks."""

    def __init__(
        self,
        claude_executor: ClaudeCodeExecutor | None = None,
        progress_reporter: ProgressReporter | None = None,
    ):
        """
        Initialize Feature Executor.

        Args:
            claude_executor: Claude Code executor instance (creates default if None)
            progress_reporter: Progress reporter instance (creates default if None)
        """
        self.claude_executor = claude_executor or ClaudeCodeExecutor()
        self.progress_reporter = progress_reporter or ProgressReporter()
        self.supabase = get_supabase_client()

        logger.info("FeatureExecutor initialized")

    async def execute_feature(
        self, project_id: str, feature_description: str, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Execute all tasks for a feature automatically.

        Args:
            project_id: Project UUID
            feature_description: Feature description to filter tasks
            max_retries: Max retry attempts per task (default: 3)

        Returns:
            Summary of execution results:
            {
                "total_tasks": int,
                "successful": int,
                "failed": int,
                "results": list[dict],
            }
        """
        logger.info(f"Starting automated execution for feature: {feature_description}")

        try:
            # 1. Get all tasks for this feature
            tasks = await self._get_feature_tasks(project_id, feature_description)

            if not tasks:
                logger.warning(f"No tasks found for feature: {feature_description}")
                return {
                    "total_tasks": 0,
                    "successful": 0,
                    "failed": 0,
                    "results": [],
                    "error": "No tasks found",
                }

            # 2. Sort by task_order to execute in correct sequence
            tasks = sorted(tasks, key=lambda t: t.get("task_order", 0))

            logger.info(f"Found {len(tasks)} tasks to execute")

            # 3. Execute each task sequentially
            results = []
            successful_count = 0
            failed_count = 0

            for idx, task in enumerate(tasks):
                task_num = idx + 1
                total_tasks = len(tasks)

                logger.info(f"Processing task {task_num}/{total_tasks}: {task['title']}")

                # Update status to "doing"
                await self._update_task_status(task["id"], "doing")

                # Send start notification to Slack
                await self.progress_reporter.notify_task_execution_started(
                    project_id=project_id,
                    task=task,
                    task_number=task_num,
                    total_tasks=total_tasks,
                )

                # Execute task with retry logic
                result = await self._execute_with_retry(task, max_retries)

                # Update task status based on result
                new_status = "done" if result["success"] else "review"
                await self._update_task_status(task["id"], new_status)

                # Track success/failure
                if result["success"]:
                    successful_count += 1
                else:
                    failed_count += 1

                # Send completion notification to Slack
                await self.progress_reporter.notify_task_execution_completed(
                    project_id=project_id,
                    task=task,
                    result=result,
                    task_number=task_num,
                    total_tasks=total_tasks,
                )

                results.append(
                    {
                        "task_id": task["id"],
                        "task_title": task["title"],
                        "success": result["success"],
                        "files_modified": result.get("files_modified", []),
                        "tests_passed": result.get("tests_passed", False),
                        "error": result.get("error"),
                    }
                )

            # 4. Send final summary to Slack
            await self.progress_reporter.notify_feature_execution_complete(
                project_id=project_id,
                feature_description=feature_description,
                total_tasks=len(tasks),
                successful=successful_count,
                failed=failed_count,
                results=results,
            )

            logger.info(
                f"Feature execution complete: {successful_count}/{len(tasks)} successful, "
                f"{failed_count}/{len(tasks)} failed"
            )

            return {
                "total_tasks": len(tasks),
                "successful": successful_count,
                "failed": failed_count,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Feature execution failed: {str(e)}", exc_info=True)
            return {
                "total_tasks": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
                "error": str(e),
            }

    async def _get_feature_tasks(self, project_id: str, feature_description: str) -> list[dict[str, Any]]:
        """
        Get all tasks for a feature from database.

        Args:
            project_id: Project UUID
            feature_description: Feature description (stored in task.feature field)

        Returns:
            List of task dicts
        """
        try:
            # Query tasks by project_id and feature (using LIKE for partial match)
            # Feature field contains first 100 chars of feature description
            feature_prefix = feature_description[:100]

            result = (
                self.supabase.table("archon_tasks")
                .select("*")
                .eq("project_id", project_id)
                .ilike("feature", f"{feature_prefix}%")
                .eq("archived", False)
                .execute()
            )

            tasks = result.data or []
            logger.info(f"Retrieved {len(tasks)} tasks for feature")
            return tasks

        except Exception as e:
            logger.error(f"Failed to get feature tasks: {str(e)}", exc_info=True)
            return []

    async def _execute_with_retry(
        self, task: dict[str, Any], max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Execute task with retry logic.

        Args:
            task: Task dict
            max_retries: Maximum number of retry attempts

        Returns:
            Execution result dict
        """
        last_result = None

        for attempt in range(1, max_retries + 1):
            logger.info(f"Attempt {attempt}/{max_retries} for task: {task['title']}")

            try:
                # Execute task using Claude Code
                result = await self.claude_executor.execute_task(task)

                if result["success"]:
                    logger.info(f"Task succeeded on attempt {attempt}")
                    return result

                logger.warning(
                    f"Task failed on attempt {attempt}: {result.get('error', 'Unknown error')}"
                )
                last_result = result

                # Wait before retry (exponential backoff: 2s, 4s, 8s)
                if attempt < max_retries:
                    wait_time = 2**attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Exception on attempt {attempt}: {str(e)}", exc_info=True)
                last_result = {
                    "success": False,
                    "output": "",
                    "files_modified": [],
                    "tests_passed": False,
                    "test_output": "",
                    "error": str(e),
                }

                if attempt < max_retries:
                    wait_time = 2**attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        logger.error(f"Task failed after {max_retries} attempts: {task['title']}")
        return last_result or {
            "success": False,
            "error": f"Failed after {max_retries} attempts",
        }

    async def _update_task_status(self, task_id: str, status: str) -> None:
        """
        Update task status in database.

        Args:
            task_id: Task UUID
            status: New status (todo/doing/review/done)
        """
        try:
            self.supabase.table("archon_tasks").update({"status": status}).eq("id", task_id).execute()

            logger.info(f"Updated task {task_id} status to: {status}")

        except Exception as e:
            logger.error(f"Failed to update task status: {str(e)}", exc_info=True)


# Global async wrapper for background execution
async def execute_feature_async(
    project_id: str, feature_description: str, max_retries: int = 3
) -> dict[str, Any]:
    """
    Async wrapper for feature execution (for background tasks).

    Args:
        project_id: Project UUID
        feature_description: Feature description
        max_retries: Max retry attempts per task

    Returns:
        Execution summary
    """
    executor = FeatureExecutor()
    return await executor.execute_feature(project_id, feature_description, max_retries)
