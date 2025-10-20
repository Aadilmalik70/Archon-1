"""
Slack Service Layer

Business logic for Slack integration including:
- Channel management
- Message sending with formatting
- File uploads
- Project-channel mappings
"""

from typing import Any

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client
from .slack_client import SlackClient, create_task_message_blocks
from .slack_oauth import SlackOAuth

logger = get_logger(__name__)


class SlackService:
    """
    High-level service for Slack operations

    Handles business logic and database operations for Slack integration
    """

    @classmethod
    async def get_client(cls) -> SlackClient | None:
        """
        Get authenticated Slack client

        Returns:
            SlackClient instance if credentials exist, None otherwise
        """
        access_token = await SlackOAuth.get_access_token()
        if not access_token:
            logger.warning("No Slack access token available")
            return None

        return SlackClient(access_token)

    @classmethod
    async def link_channel_to_project(
        cls,
        project_id: str,
        slack_channel_id: str,
        slack_channel_name: str,
        notification_types: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Link a Slack channel to an Archon project

        Args:
            project_id: Archon project UUID
            slack_channel_id: Slack channel ID (e.g., C1234567890)
            slack_channel_name: Human-readable channel name (e.g., #ai-pm-updates)
            notification_types: Types of notifications to send (default: all)

        Returns:
            Created mapping record or None if failed
        """
        supabase = get_supabase_client()

        try:
            # Default notification types
            if notification_types is None:
                notification_types = [
                    "task_created",
                    "task_completed",
                    "task_failed",
                    "agent_action",
                    "execution_started",
                ]

            # Check if mapping already exists
            existing = supabase.table("slack_channels").select("*").eq(
                "project_id", project_id
            ).eq("slack_channel_id", slack_channel_id).execute()

            if existing.data:
                # Update existing mapping
                result = supabase.table("slack_channels").update({
                    "slack_channel_name": slack_channel_name,
                    "notification_types": notification_types,
                }).eq("channel_id", existing.data[0]["channel_id"]).execute()

                logger.info(f"Updated Slack channel mapping for project {project_id}")
            else:
                # Create new mapping
                result = supabase.table("slack_channels").insert({
                    "project_id": project_id,
                    "slack_channel_id": slack_channel_id,
                    "slack_channel_name": slack_channel_name,
                    "notification_types": notification_types,
                }).execute()

                logger.info(f"Created Slack channel mapping for project {project_id}")

            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Failed to link Slack channel: {str(e)}", exc_info=True)
            return None

    @classmethod
    async def get_project_channels(cls, project_id: str) -> list[dict]:
        """
        Get all Slack channels linked to a project

        Args:
            project_id: Archon project UUID

        Returns:
            List of channel mapping records
        """
        supabase = get_supabase_client()

        try:
            result = supabase.table("slack_channels").select("*").eq(
                "project_id", project_id
            ).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to get project channels: {str(e)}", exc_info=True)
            return []

    @classmethod
    async def send_task_notification(
        cls,
        project_id: str,
        task: dict[str, Any],
        notification_type: str = "task_created",
    ) -> list[dict]:
        """
        Send task notification to all configured Slack channels for a project

        Args:
            project_id: Project ID
            task: Task object with details
            notification_type: Type of notification (task_created, task_completed, etc.)

        Returns:
            List of message responses from Slack
        """
        try:
            # Get Slack client
            client = await cls.get_client()
            if not client:
                logger.warning("No Slack client available, skipping notification")
                return []

            # Get channels for this project
            channels = await cls.get_project_channels(project_id)
            if not channels:
                logger.debug(f"No Slack channels configured for project {project_id}")
                return []

            responses = []

            for channel_mapping in channels:
                # Check if this notification type is enabled for this channel
                if notification_type not in channel_mapping.get("notification_types", []):
                    continue

                channel_id = channel_mapping["slack_channel_id"]

                try:
                    # Format message based on notification type
                    if notification_type == "task_created":
                        message = await cls._format_task_created_message(task)
                    elif notification_type == "task_completed":
                        message = await cls._format_task_completed_message(task)
                    elif notification_type == "task_failed":
                        message = await cls._format_task_failed_message(task)
                    else:
                        message = {
                            "text": f"Task update: {task.get('title')}",
                            "blocks": None,
                        }

                    # Send message
                    response = await client.post_message(
                        channel=channel_id,
                        text=message["text"],
                        blocks=message.get("blocks"),
                    )

                    # Store thread_ts in task for future updates
                    if response.get("ts"):
                        await cls._update_task_slack_thread(
                            task.get("id"), response["ts"]
                        )

                    responses.append(response)

                    logger.info(
                        f"Sent {notification_type} notification to {channel_mapping['slack_channel_name']}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to send notification to channel {channel_id}: {str(e)}"
                    )
                    continue

            return responses

        except Exception as e:
            logger.error(f"Failed to send task notifications: {str(e)}", exc_info=True)
            return []

    @classmethod
    async def send_agent_notification(
        cls,
        project_id: str,
        agent_type: str,
        action: str,
        details: dict[str, Any],
    ) -> list[dict]:
        """
        Send agent action notification to Slack

        Args:
            project_id: Project ID
            agent_type: Type of agent (orchestrator, coding, qa, docs)
            action: Action taken (started, completed, failed)
            details: Additional details about the action

        Returns:
            List of message responses
        """
        try:
            client = await cls.get_client()
            if not client:
                return []

            channels = await cls.get_project_channels(project_id)
            if not channels:
                return []

            responses = []

            for channel_mapping in channels:
                if "agent_action" not in channel_mapping.get("notification_types", []):
                    continue

                channel_id = channel_mapping["slack_channel_id"]

                # Format agent notification
                emoji_map = {
                    "orchestrator": "🎯",
                    "coding": "💻",
                    "qa": "🧪",
                    "docs": "📝",
                    "security": "🔒",
                    "performance": "⚡",
                }

                emoji = emoji_map.get(agent_type, "🤖")
                text = f"{emoji} Agent {agent_type}: {action}"

                blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *{agent_type.title()} Agent* - {action}",
                        },
                    },
                ]

                # Add details if available
                if details:
                    detail_text = "\n".join([f"*{k}:* {v}" for k, v in details.items()])
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": detail_text},
                    })

                try:
                    response = await client.post_message(
                        channel=channel_id, text=text, blocks=blocks
                    )
                    responses.append(response)
                except Exception as e:
                    logger.error(f"Failed to send agent notification: {str(e)}")
                    continue

            return responses

        except Exception as e:
            logger.error(f"Failed to send agent notifications: {str(e)}", exc_info=True)
            return []

    @classmethod
    async def upload_execution_log(
        cls,
        project_id: str,
        execution_id: str,
        log_content: str,
        filename: str = "execution_log.txt",
    ) -> bool:
        """
        Upload agent execution log to Slack

        Args:
            project_id: Project ID
            execution_id: Execution ID
            log_content: Log content to upload
            filename: Name of the file

        Returns:
            True if uploaded successfully
        """
        try:
            client = await cls.get_client()
            if not client:
                return False

            channels = await cls.get_project_channels(project_id)
            if not channels:
                return False

            channel_ids = [ch["slack_channel_id"] for ch in channels]

            await client.upload_file(
                channels=channel_ids,
                content=log_content,
                filename=filename,
                title=f"Execution Log - {execution_id[:8]}",
                filetype="text",
            )

            logger.info(f"Uploaded execution log to Slack for {execution_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload execution log: {str(e)}", exc_info=True)
            return False

    @classmethod
    async def list_available_channels(cls) -> list[dict]:
        """
        List all available Slack channels in the workspace

        Returns:
            List of channel objects
        """
        try:
            client = await cls.get_client()
            if not client:
                return []

            channels = await client.list_channels()

            # Filter to only include channels the bot is in or public channels
            return [
                {
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "is_private": ch.get("is_private", False),
                    "is_member": ch.get("is_member", False),
                }
                for ch in channels
            ]

        except Exception as e:
            logger.error(f"Failed to list channels: {str(e)}", exc_info=True)
            return []

    # Helper methods

    @staticmethod
    async def _format_task_created_message(task: dict) -> dict:
        """Format task creation message"""
        blocks = create_task_message_blocks(
            task_title=task.get("title", "Unknown"),
            task_description=task.get("description", "No description"),
            agent_assigned=task.get("agent_assigned", "unassigned"),
            estimated_effort=task.get("execution_metadata", {}).get(
                "estimated_effort", "unknown"
            ),
            priority=task.get("priority", "medium"),
        )

        return {"text": f"New task created: {task.get('title')}", "blocks": blocks}

    @staticmethod
    async def _format_task_completed_message(task: dict) -> dict:
        """Format task completion message"""
        exec_meta = task.get("execution_metadata", {})

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"✅ Task Completed: {task.get('title')}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Agent:* {task.get('agent_assigned')}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Duration:* {exec_meta.get('duration', 'N/A')}",
                    },
                ],
            },
        ]

        return {"text": f"Task completed: {task.get('title')}", "blocks": blocks}

    @staticmethod
    async def _format_task_failed_message(task: dict) -> dict:
        """Format task failure message"""
        exec_meta = task.get("execution_metadata", {})
        error = exec_meta.get("error_message", "Unknown error")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"❌ Task Failed: {task.get('title')}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Error:* {error[:500]}"},
            },
        ]

        return {"text": f"Task failed: {task.get('title')}", "blocks": blocks}

    @staticmethod
    async def _update_task_slack_thread(task_id: str, thread_ts: str) -> bool:
        """Update task with Slack thread timestamp"""
        supabase = get_supabase_client()

        try:
            supabase.table("archon_tasks").update(
                {"slack_thread_ts": thread_ts}
            ).eq("id", task_id).execute()

            return True
        except Exception as e:
            logger.error(f"Failed to update task slack_thread_ts: {str(e)}")
            return False
