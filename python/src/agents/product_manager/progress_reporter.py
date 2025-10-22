"""
Progress Reporter

Sends progress updates to Slack as tasks are executed by agents.
Provides real-time feedback to users about task execution status.
"""

from typing import Any

from ...server.config.logfire_config import get_logger
from ...server.integrations.slack.slack_service import SlackService
from ...server.utils import get_supabase_client

logger = get_logger(__name__)


class ProgressReporter:
    """Reports task execution progress to Slack"""

    @staticmethod
    async def notify_task_started(project_id: str, task: dict[str, Any]) -> None:
        """
        Send 'Task started by Claude Code' notification to Slack.

        Args:
            project_id: Project ID
            task: Task object that was started
        """
        try:
            # Get linked Slack channels
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                logger.debug(f"No Slack channels linked for project {project_id}")
                return

            client = await SlackService.get_client()
            if not client:
                logger.error("Slack client not available")
                return

            # Build message
            agent_emoji = {
                "coding": "⚙️",
                "qa": "🧪",
                "docs": "📝",
                "security": "🔒",
                "performance": "⚡",
            }.get(task.get("metadata", {}).get("assigned_agent", "coding"), "📌")

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{agent_emoji} *Task Started*\n\n"
                                f"*{task.get('title')}*\n"
                                f"Status: `todo` → `doing`\n"
                                f"Agent: Claude Code ({task.get('metadata', {}).get('assigned_agent', 'unknown')})"
                    }
                }
            ]

            # Send to all linked channels
            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"Task started: {task.get('title')}",
                    blocks=blocks,
                )

            logger.info(f"Sent task started notification for: {task.get('title')}")

        except Exception as e:
            logger.error(f"Error sending task started notification: {str(e)}", exc_info=True)

    @staticmethod
    async def notify_task_progress(
        project_id: str,
        task: dict[str, Any],
        old_status: str,
        new_status: str,
    ) -> None:
        """
        Send task status update notification.

        Args:
            project_id: Project ID
            task: Task object
            old_status: Previous status
            new_status: New status
        """
        try:
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                return

            client = await SlackService.get_client()
            if not client:
                return

            # Status emoji
            status_emoji = {
                "todo": "📋",
                "doing": "🔄",
                "review": "👀",
                "done": "✅",
            }

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🔄 *Task Progress Update*\n\n"
                                f"*{task.get('title')}*\n"
                                f"Status: {status_emoji.get(old_status, '•')} `{old_status}` → "
                                f"{status_emoji.get(new_status, '•')} `{new_status}`"
                    }
                }
            ]

            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"Task update: {task.get('title')} ({old_status} → {new_status})",
                    blocks=blocks,
                )

            logger.info(f"Sent progress update for task: {task.get('title')}")

        except Exception as e:
            logger.error(f"Error sending progress update: {str(e)}", exc_info=True)

    @staticmethod
    async def notify_task_completed(project_id: str, task: dict[str, Any]) -> None:
        """
        Send task completion notification with checkmark.

        Args:
            project_id: Project ID
            task: Completed task object
        """
        try:
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                return

            client = await SlackService.get_client()
            if not client:
                return

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ *Task Completed*\n\n"
                                f"*{task.get('title')}*\n"
                                f"Status: `review` → `done`\n"
                                f"Completed by: Claude Code"
                    }
                }
            ]

            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"✅ Task completed: {task.get('title')}",
                    blocks=blocks,
                )

            logger.info(f"Sent completion notification for task: {task.get('title')}")

        except Exception as e:
            logger.error(f"Error sending completion notification: {str(e)}", exc_info=True)

    @staticmethod
    async def notify_all_tasks_complete(
        project_id: str,
        summary: dict[str, Any],
    ) -> None:
        """
        Send final summary when all tasks are done.

        Args:
            project_id: Project ID
            summary: Summary dict with task counts and statistics
        """
        try:
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                return

            client = await SlackService.get_client()
            if not client:
                return

            total_tasks = summary.get("total_tasks", 0)
            completed_tasks = summary.get("completed_tasks", 0)
            failed_tasks = summary.get("failed_tasks", 0)

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🎉 All Tasks Complete!",
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total Tasks:*\n{total_tasks}"},
                        {"type": "mrkdwn", "text": f"*Completed:*\n✅ {completed_tasks}"},
                        {"type": "mrkdwn", "text": f"*Failed:*\n❌ {failed_tasks}"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Success Rate:*\n{(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%"
                        },
                    ]
                },
            ]

            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"All tasks complete! {completed_tasks}/{total_tasks} successful",
                    blocks=blocks,
                )

            logger.info(f"Sent final summary for project {project_id}")

        except Exception as e:
            logger.error(f"Error sending final summary: {str(e)}", exc_info=True)

    @staticmethod
    async def notify_task_execution_started(
        project_id: str,
        task: dict[str, Any],
        task_number: int,
        total_tasks: int,
    ) -> None:
        """
        Send notification when automated execution starts a task.

        Args:
            project_id: Project ID
            task: Task being executed
            task_number: Current task number (1-indexed)
            total_tasks: Total number of tasks in feature
        """
        try:
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                return

            client = await SlackService.get_client()
            if not client:
                return

            # Build progress bar
            progress_pct = ((task_number - 1) / total_tasks) * 100
            progress_bar = "█" * int(progress_pct / 10) + "░" * (10 - int(progress_pct / 10))

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🤖 *Automated Execution: Task {task_number}/{total_tasks}*\n\n"
                        f"*{task.get('title')}*\n"
                        f"Assignee: {task.get('assignee', 'Unknown')}\n"
                        f"Status: `todo` → `executing`",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Progress: {progress_bar} {progress_pct:.0f}%",
                        }
                    ],
                },
            ]

            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"🤖 Executing task {task_number}/{total_tasks}: {task.get('title')}",
                    blocks=blocks,
                )

            logger.info(f"Sent execution started notification for task: {task.get('title')}")

        except Exception as e:
            logger.error(f"Error sending execution started notification: {str(e)}", exc_info=True)

    @staticmethod
    async def notify_task_execution_completed(
        project_id: str,
        task: dict[str, Any],
        result: dict[str, Any],
        task_number: int,
        total_tasks: int,
    ) -> None:
        """
        Send notification when automated execution completes a task.

        Args:
            project_id: Project ID
            task: Task that was executed
            result: Execution result dict with success, files_modified, tests_passed, error
            task_number: Current task number (1-indexed)
            total_tasks: Total number of tasks in feature
        """
        try:
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                return

            client = await SlackService.get_client()
            if not client:
                return

            success = result.get("success", False)
            files_modified = result.get("files_modified", [])
            tests_passed = result.get("tests_passed", False)
            error = result.get("error")

            # Build status message
            if success:
                status_text = f"✅ *Task {task_number}/{total_tasks} Complete*"
                status_detail = f"Status: `executing` → `done`"
            else:
                status_text = f"⚠️ *Task {task_number}/{total_tasks} Needs Review*"
                status_detail = f"Status: `executing` → `review`"

            # Build details
            details = []
            if files_modified:
                file_list = "\n".join(f"  • `{f}`" for f in files_modified[:5])
                if len(files_modified) > 5:
                    file_list += f"\n  • ... and {len(files_modified) - 5} more"
                details.append(f"*Files Modified:*\n{file_list}")

            if tests_passed:
                details.append("*Tests:* ✅ Passed")
            elif not success:
                details.append("*Tests:* ❌ Failed or not run")

            if error:
                details.append(f"*Error:* {error[:200]}")

            # Build progress bar
            progress_pct = (task_number / total_tasks) * 100
            progress_bar = "█" * int(progress_pct / 10) + "░" * (10 - int(progress_pct / 10))

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_text}\n\n*{task.get('title')}*\n{status_detail}",
                    },
                }
            ]

            if details:
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "\n\n".join(details)},
                    }
                )

            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Progress: {progress_bar} {progress_pct:.0f}%",
                        }
                    ],
                }
            )

            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"{'✅' if success else '⚠️'} Task {task_number}/{total_tasks}: {task.get('title')}",
                    blocks=blocks,
                )

            logger.info(f"Sent execution completed notification for task: {task.get('title')}")

        except Exception as e:
            logger.error(f"Error sending execution completed notification: {str(e)}", exc_info=True)

    @staticmethod
    async def notify_feature_execution_complete(
        project_id: str,
        feature_description: str,
        total_tasks: int,
        successful: int,
        failed: int,
        results: list[dict[str, Any]],
    ) -> None:
        """
        Send final summary when feature execution completes.

        Args:
            project_id: Project ID
            feature_description: Feature that was implemented
            total_tasks: Total number of tasks
            successful: Number of successful tasks
            failed: Number of failed tasks
            results: List of execution results
        """
        try:
            channels = await ProgressReporter._get_slack_channels(project_id)
            if not channels:
                return

            client = await SlackService.get_client()
            if not client:
                return

            # Calculate statistics
            success_rate = (successful / total_tasks * 100) if total_tasks > 0 else 0
            all_files = []
            for result in results:
                all_files.extend(result.get("files_modified", []))
            unique_files = len(set(all_files))

            # Determine overall status
            if failed == 0:
                header_text = "🎉 Feature Implementation Complete!"
                summary_emoji = "✅"
            elif successful > failed:
                header_text = "⚠️ Feature Partially Complete"
                summary_emoji = "⚠️"
            else:
                header_text = "❌ Feature Implementation Failed"
                summary_emoji = "❌"

            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header_text,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Feature:* {feature_description[:100]}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total Tasks:*\n{total_tasks}"},
                        {"type": "mrkdwn", "text": f"*Successful:*\n✅ {successful}"},
                        {"type": "mrkdwn", "text": f"*Failed:*\n❌ {failed}"},
                        {"type": "mrkdwn", "text": f"*Success Rate:*\n{success_rate:.0f}%"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Files Modified:* {unique_files}\n"
                        f"*Execution:* Automated via Claude Code",
                    },
                },
            ]

            # Add action recommendation
            if failed > 0:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⚠️ *{failed} task(s) need review*\n"
                            f"Check the Archon UI for details and review failed tasks.",
                        },
                    }
                )

            for channel in channels:
                await client.post_message(
                    channel=channel["slack_channel_id"],
                    text=f"{summary_emoji} Feature complete: {successful}/{total_tasks} tasks successful",
                    blocks=blocks,
                )

            logger.info(f"Sent feature execution complete notification for: {feature_description}")

        except Exception as e:
            logger.error(f"Error sending feature execution complete notification: {str(e)}", exc_info=True)

    @staticmethod
    async def _get_slack_channels(project_id: str) -> list[dict]:
        """Get Slack channels linked to project."""
        try:
            supabase = get_supabase_client()
            result = (
                supabase.table("slack_channels")
                .select("slack_channel_id, slack_channel_name")
                .eq("project_id", project_id)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"Error getting Slack channels: {str(e)}")
            return []
