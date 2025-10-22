"""
Slack API Client

Low-level wrapper around Slack Web API
Handles direct API communication with proper error handling
"""

import httpx
from typing import Any

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class SlackClient:
    """
    Slack API client for direct API communication

    Provides methods for:
    - Posting messages to channels
    - Uploading files
    - Listing channels
    - Managing threads
    """

    BASE_URL = "https://slack.com/api"
    TIMEOUT = 30.0  # 30 second timeout for API calls

    def __init__(self, access_token: str):
        """
        Initialize Slack client with access token

        Args:
            access_token: Slack OAuth access token (bot token)
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    async def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Post a message to a Slack channel

        Args:
            channel: Channel ID (e.g., C1234567890) or name (e.g., #general)
            text: Message text (used as fallback for notifications)
            thread_ts: Optional thread timestamp to reply in thread
            blocks: Optional Block Kit formatted content for rich messages
            attachments: Optional legacy attachments

        Returns:
            Slack API response with message details including ts (timestamp)

        Raises:
            Exception: If Slack API returns an error
        """
        async with httpx.AsyncClient() as client:
            payload: dict[str, Any] = {
                "channel": channel,
                "text": text,
            }

            if thread_ts:
                payload["thread_ts"] = thread_ts

            if blocks:
                payload["blocks"] = blocks

            if attachments:
                payload["attachments"] = attachments

            try:
                response = await client.post(
                    f"{self.BASE_URL}/chat.postMessage",
                    headers=self.headers,
                    json=payload,
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Slack API error: {error_msg}", extra={"response": data})
                    raise Exception(f"Slack API error: {error_msg}")

                logger.info(
                    f"Posted message to {channel}",
                    extra={"ts": data.get("ts"), "is_thread_reply": bool(thread_ts)},
                )

                return data

            except httpx.TimeoutException:
                logger.error(f"Slack API timeout posting to {channel}")
                raise Exception("Slack API request timed out")
            except httpx.RequestError as e:
                logger.error(f"Slack API request error: {str(e)}")
                raise Exception(f"Slack API request failed: {str(e)}")

    async def list_channels(
        self, types: str = "public_channel,private_channel", limit: int = 200
    ) -> list[dict[str, Any]]:
        """
        List all channels in the workspace

        Args:
            types: Comma-separated list of channel types
            limit: Maximum number of channels to return (max 1000)

        Returns:
            List of channel objects with id, name, is_private, etc.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/conversations.list",
                    headers=self.headers,
                    params={"types": types, "limit": min(limit, 1000)},
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Failed to list channels: {error_msg}")
                    raise Exception(f"Slack API error: {error_msg}")

                channels = data.get("channels", [])
                logger.info(f"Retrieved {len(channels)} channels")

                return channels

            except Exception as e:
                logger.error(f"Failed to list channels: {str(e)}", exc_info=True)
                raise

    async def upload_file(
        self,
        channels: list[str],
        content: str | bytes,
        filename: str,
        title: str | None = None,
        thread_ts: str | None = None,
        filetype: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file (code snippet, report, logs) to Slack

        Args:
            channels: List of channel IDs to share file in
            content: File content (string or bytes)
            filename: Name of the file
            title: Optional title for the file
            thread_ts: Optional thread timestamp to post in thread
            filetype: Optional file type hint (e.g., 'python', 'javascript', 'text')

        Returns:
            Slack API response with file details
        """
        async with httpx.AsyncClient() as client:
            try:
                # Prepare multipart form data
                files = {
                    "file": (filename, content, "text/plain" if isinstance(content, str) else "application/octet-stream")
                }

                form_data = {
                    "channels": ",".join(channels),
                    "filename": filename,
                }

                if title:
                    form_data["title"] = title

                if thread_ts:
                    form_data["thread_ts"] = thread_ts

                if filetype:
                    form_data["filetype"] = filetype

                response = await client.post(
                    f"{self.BASE_URL}/files.upload",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    files=files,
                    data=form_data,
                    timeout=60.0,  # Longer timeout for file uploads
                )

                result = response.json()

                if not result.get("ok"):
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"File upload failed: {error_msg}")
                    raise Exception(f"File upload failed: {error_msg}")

                logger.info(f"Uploaded file {filename} to channels: {', '.join(channels)}")

                return result

            except Exception as e:
                logger.error(f"Failed to upload file: {str(e)}", exc_info=True)
                raise

    async def add_reaction(
        self, channel: str, timestamp: str, reaction: str
    ) -> dict[str, Any]:
        """
        Add emoji reaction to a message

        Args:
            channel: Channel ID where message is
            timestamp: Message timestamp
            reaction: Emoji name (without colons, e.g., 'thumbsup', 'white_check_mark')

        Returns:
            Slack API response
        """
        async with httpx.AsyncClient() as client:
            try:
                payload = {
                    "channel": channel,
                    "timestamp": timestamp,
                    "name": reaction,
                }

                response = await client.post(
                    f"{self.BASE_URL}/reactions.add",
                    headers=self.headers,
                    json=payload,
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    # Ignore if reaction already exists
                    if data.get("error") == "already_reacted":
                        logger.debug(f"Reaction {reaction} already exists on message")
                        return data

                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Failed to add reaction: {error_msg}")
                    raise Exception(f"Failed to add reaction: {error_msg}")

                logger.debug(f"Added reaction {reaction} to message {timestamp}")

                return data

            except Exception as e:
                logger.error(f"Failed to add reaction: {str(e)}", exc_info=True)
                raise

    async def get_channel_info(self, channel_id: str) -> dict[str, Any]:
        """
        Get information about a specific channel

        Args:
            channel_id: Channel ID

        Returns:
            Channel information dict
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/conversations.info",
                    headers=self.headers,
                    params={"channel": channel_id},
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Failed to get channel info: {error_msg}")
                    raise Exception(f"Failed to get channel info: {error_msg}")

                return data.get("channel", {})

            except Exception as e:
                logger.error(f"Failed to get channel info: {str(e)}", exc_info=True)
                raise

    async def test_auth(self) -> dict[str, Any]:
        """
        Test authentication and get workspace/bot info

        Returns:
            Auth test response with team, user, bot info
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/auth.test",
                    headers=self.headers,
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Auth test failed: {error_msg}")
                    raise Exception(f"Slack authentication failed: {error_msg}")

                logger.info(
                    f"Slack auth successful for workspace: {data.get('team')}",
                    extra={"bot_id": data.get("bot_id")},
                )

                return data

            except Exception as e:
                logger.error(f"Auth test failed: {str(e)}", exc_info=True)
                raise

    async def open_dm_channel(self, user_id: str) -> str:
        """
        Open a DM channel with a user

        Args:
            user_id: Slack user ID (e.g., U1234567890)

        Returns:
            DM channel ID (e.g., D1234567890)

        Raises:
            Exception: If opening DM fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/conversations.open",
                    headers=self.headers,
                    json={"users": user_id},
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Failed to open DM channel: {error_msg}")
                    raise Exception(f"Failed to open DM: {error_msg}")

                channel_id = data.get("channel", {}).get("id")
                logger.info(f"Opened DM channel {channel_id} with user {user_id}")

                return channel_id

            except Exception as e:
                logger.error(f"Failed to open DM channel: {str(e)}", exc_info=True)
                raise

    async def send_dm(
        self,
        user_id: str,
        text: str,
        blocks: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Send a direct message to a user

        Args:
            user_id: Slack user ID (e.g., U1234567890)
            text: Message text
            blocks: Optional Block Kit formatted content

        Returns:
            Slack API response with message details

        Raises:
            Exception: If sending DM fails
        """
        try:
            # First, open DM channel
            dm_channel_id = await self.open_dm_channel(user_id)

            # Then send message to the DM channel
            result = await self.post_message(
                channel=dm_channel_id,
                text=text,
                blocks=blocks,
            )

            logger.info(f"Sent DM to user {user_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to send DM: {str(e)}", exc_info=True)
            raise

    async def get_dm_history(
        self,
        channel_id: str,
        limit: int = 100,
        oldest: str | None = None,
        latest: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history from a DM channel

        Args:
            channel_id: DM channel ID (D1234567890)
            limit: Maximum number of messages to retrieve (max 1000)
            oldest: Only messages after this timestamp
            latest: Only messages before this timestamp

        Returns:
            List of message objects

        Raises:
            Exception: If retrieving history fails
        """
        async with httpx.AsyncClient() as client:
            try:
                params: dict[str, Any] = {
                    "channel": channel_id,
                    "limit": min(limit, 1000),
                }

                if oldest:
                    params["oldest"] = oldest
                if latest:
                    params["latest"] = latest

                response = await client.get(
                    f"{self.BASE_URL}/conversations.history",
                    headers=self.headers,
                    params=params,
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Failed to get DM history: {error_msg}")
                    raise Exception(f"Failed to get DM history: {error_msg}")

                messages = data.get("messages", [])
                logger.info(f"Retrieved {len(messages)} messages from DM {channel_id}")

                return messages

            except Exception as e:
                logger.error(f"Failed to get DM history: {str(e)}", exc_info=True)
                raise

    async def list_workspace_users(self, limit: int = 200) -> list[dict[str, Any]]:
        """
        List all users in the workspace

        Args:
            limit: Maximum number of users to return (max 1000)

        Returns:
            List of user objects with id, name, real_name, is_bot, etc.

        Raises:
            Exception: If listing users fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/users.list",
                    headers=self.headers,
                    params={"limit": min(limit, 1000)},
                    timeout=self.TIMEOUT,
                )

                data = response.json()

                if not data.get("ok"):
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"Failed to list users: {error_msg}")
                    raise Exception(f"Failed to list users: {error_msg}")

                # Filter out bots and deleted users
                users = [
                    user
                    for user in data.get("members", [])
                    if not user.get("is_bot", False)
                    and not user.get("deleted", False)
                ]

                logger.info(f"Retrieved {len(users)} active users")
                return users

            except Exception as e:
                logger.error(f"Failed to list users: {str(e)}", exc_info=True)
                raise


# Helper function to format message blocks
def create_task_message_blocks(
    task_title: str,
    task_description: str,
    agent_assigned: str,
    estimated_effort: str,
    priority: str,
) -> list[dict]:
    """
    Create Block Kit formatted message for task notifications

    Args:
        task_title: Task title
        task_description: Task description
        agent_assigned: Agent handling the task
        estimated_effort: Effort estimate
        priority: Task priority

    Returns:
        List of Block Kit blocks
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🤖 New Task: {task_title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": task_description[:3000],  # Slack max text length
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Agent:*\n{agent_assigned}"},
                {"type": "mrkdwn", "text": f"*Effort:*\n{estimated_effort}"},
                {"type": "mrkdwn", "text": f"*Priority:*\n{priority}"},
            ],
        },
        {"type": "divider"},
    ]
