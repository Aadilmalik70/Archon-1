"""
Slack Event Handlers

Handles incoming Slack webhooks including:
- Event subscriptions (messages, reactions, etc.)
- Slash commands (/aipm)
- Interactive components (buttons, modals)
- Webhook signature verification
"""

import hashlib
import hmac
import json
import os
import time
from typing import Any

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client
from .slack_service import SlackService

logger = get_logger(__name__)

# Environment configuration
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")

# Event deduplication cache (in production, use Redis)
_processed_events: set[str] = set()
_MAX_CACHE_SIZE = 10000


class SlackEventHandler:
    """
    Handles Slack webhook events with signature verification
    """

    @staticmethod
    def verify_signature(
        timestamp: str, body: str, signature: str
    ) -> bool:
        """
        Verify Slack webhook signature using HMAC-SHA256

        Args:
            timestamp: X-Slack-Request-Timestamp header
            body: Raw request body
            signature: X-Slack-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        if not SLACK_SIGNING_SECRET:
            logger.error("SLACK_SIGNING_SECRET not configured")
            return False

        # Check timestamp to prevent replay attacks (max 5 minutes old)
        try:
            request_timestamp = int(timestamp)
            current_timestamp = int(time.time())

            if abs(current_timestamp - request_timestamp) > 300:
                logger.warning(
                    "Slack webhook timestamp too old",
                    extra={"age_seconds": current_timestamp - request_timestamp},
                )
                return False
        except (ValueError, TypeError):
            logger.error("Invalid timestamp in Slack webhook")
            return False

        # Calculate HMAC signature
        sig_basestring = f"v0:{timestamp}:{body}"
        computed_signature = (
            "v0="
            + hmac.new(
                SLACK_SIGNING_SECRET.encode("utf-8"),
                sig_basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_signature, signature)

    @staticmethod
    def deduplicate_event(event_id: str) -> bool:
        """
        Check if event has already been processed

        Args:
            event_id: Unique event ID from Slack

        Returns:
            True if event is new (should be processed), False if duplicate
        """
        global _processed_events

        if event_id in _processed_events:
            logger.debug(f"Duplicate event ignored: {event_id}")
            return False

        # Add to cache
        _processed_events.add(event_id)

        # Prevent unbounded growth
        if len(_processed_events) > _MAX_CACHE_SIZE:
            # Remove oldest half (simple approach, use Redis in production)
            _processed_events = set(list(_processed_events)[_MAX_CACHE_SIZE // 2 :])

        return True

    @classmethod
    async def handle_event(cls, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Route Slack events to appropriate handlers

        Args:
            event_data: Parsed Slack event payload

        Returns:
            Response dictionary for Slack
        """
        event_type = event_data.get("type")

        try:
            # URL verification challenge (app setup)
            if event_type == "url_verification":
                return {"challenge": event_data.get("challenge")}

            # Event callback
            if event_type == "event_callback":
                event = event_data.get("event", {})
                event_id = event_data.get("event_id")

                # Deduplicate
                if event_id and not cls.deduplicate_event(event_id):
                    return {"ok": True, "message": "Duplicate event"}

                # Route to event-specific handler
                event_subtype = event.get("type")

                if event_subtype == "message":
                    await cls._handle_message_event(event)
                elif event_subtype == "reaction_added":
                    await cls._handle_reaction_event(event)
                elif event_subtype == "app_mention":
                    await cls._handle_mention_event(event)

                return {"ok": True}

            logger.warning(f"Unhandled Slack event type: {event_type}")
            return {"ok": True}

        except Exception as e:
            logger.error(f"Error handling Slack event: {str(e)}", exc_info=True)
            return {"ok": False, "error": str(e)}

    @staticmethod
    async def _handle_message_event(event: dict[str, Any]) -> None:
        """
        Handle message events in channels and DMs

        Args:
            event: Message event data
        """
        # Ignore bot messages and message changes
        if event.get("bot_id") or event.get("subtype") in ["message_changed", "message_deleted"]:
            return

        channel = event.get("channel")
        channel_type = event.get("channel_type")
        text = event.get("text", "")
        user = event.get("user")
        ts = event.get("ts")

        logger.info(
            f"Message received in {channel_type or 'channel'} {channel}",
            extra={"user": user, "text": text[:100]},
        )

        # Get Slack client
        client = await SlackService.get_client()
        if not client:
            logger.error("Slack client not available")
            return

        # Handle DM messages (channel type is 'im')
        if channel_type == "im":
            # This is a direct message to the bot
            logger.info(f"DM received from user {user}: {text}")
            
            # Simple echo response (you can enhance this with AI)
            response_text = f"👋 Hi! You said: '{text}'\n\nI'm the Archon AI-PM bot. How can I help you today?"
            
            try:
                await client.send_dm(
                    user_id=user,
                    text=response_text,
                )
                logger.info(f"Replied to DM from user {user}")
            except Exception as e:
                logger.error(f"Failed to reply to DM: {str(e)}", exc_info=True)
            return

        # Handle channel messages with commands
        if text.lower().startswith("aipm ") or text.lower().startswith("/aipm "):
            await SlackCommandHandler.handle_aipm_command(
                command_text=text, channel_id=channel, user_id=user, response_url=None
            )

    @staticmethod
    async def _handle_reaction_event(event: dict[str, Any]) -> None:
        """
        Handle reaction_added events

        Args:
            event: Reaction event data
        """
        reaction = event.get("reaction")
        item = event.get("item", {})
        user = event.get("user")

        logger.debug(
            f"Reaction {reaction} added by {user} to message {item.get('ts')}"
        )

        # Example: Use reactions for task approval workflows
        # If reaction is 'white_check_mark' on a task message, mark task as approved

    @staticmethod
    async def _handle_mention_event(event: dict[str, Any]) -> None:
        """
        Handle app_mention events (when bot is @mentioned)

        Args:
            event: Mention event data
        """
        channel = event.get("channel")
        text = event.get("text", "")
        user = event.get("user")

        logger.info(f"Bot mentioned in {channel} by {user}: {text}")

        # Respond with help message or process command
        client = await SlackService.get_client()
        if client:
            help_text = (
                "👋 Hi! I'm the Archon AI-PM bot.\n\n"
                "Use `/aipm <command>` to interact with me:\n"
                "• `/aipm create feature: <description>` - Create new feature tasks\n"
                "• `/aipm status` - Show project status\n"
                "• `/aipm help` - Show this help message"
            )
            await client.post_message(channel=channel, text=help_text)


class SlackCommandHandler:
    """
    Handles Slack slash commands
    """

    @classmethod
    async def handle_slash_command(
        cls, form_data: dict[str, str]
    ) -> dict[str, Any]:
        """
        Handle incoming slash command

        Args:
            form_data: Parsed form data from Slack

        Returns:
            Response for Slack (in_channel or ephemeral)
        """
        command = form_data.get("command", "")
        text = form_data.get("text", "")
        user_id = form_data.get("user_id", "")
        channel_id = form_data.get("channel_id", "")
        response_url = form_data.get("response_url")

        logger.info(
            f"Slash command received: {command} {text}",
            extra={"user": user_id, "channel": channel_id},
        )

        try:
            if command == "/aipm":
                return await cls.handle_aipm_command(
                    command_text=text,
                    channel_id=channel_id,
                    user_id=user_id,
                    response_url=response_url,
                )
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"Unknown command: {command}",
                }

        except Exception as e:
            logger.error(f"Error handling slash command: {str(e)}", exc_info=True)
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error: {str(e)}",
            }

    @classmethod
    async def handle_aipm_command(
        cls,
        command_text: str,
        channel_id: str,
        user_id: str,
        response_url: str | None,
    ) -> dict[str, Any]:
        """
        Handle /aipm command with subcommands

        Args:
            command_text: Command arguments
            channel_id: Slack channel ID
            user_id: Slack user ID
            response_url: URL for delayed responses

        Returns:
            Response dictionary for Slack
        """
        # Parse command
        parts = command_text.strip().split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1] if len(parts) > 1 else ""

        # Route to subcommand handler
        if subcommand == "create":
            return await cls._handle_create_command(args, channel_id, user_id)
        elif subcommand == "status":
            return await cls._handle_status_command(channel_id, user_id)
        elif subcommand == "help":
            return await cls._handle_help_command()
        else:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Unknown subcommand: {subcommand}\nUse `/aipm help` for available commands.",
            }

    @staticmethod
    async def _handle_create_command(
        args: str, channel_id: str, user_id: str
    ) -> dict[str, Any]:
        """
        Handle create feature command

        Args:
            args: Command arguments (e.g., "feature: Add user authentication")
            channel_id: Slack channel ID
            user_id: Slack user ID

        Returns:
            Response for Slack
        """
        # Parse feature description
        if not args or ":" not in args:
            return {
                "response_type": "ephemeral",
                "text": "❌ Usage: `/aipm create feature: <description>`",
            }

        feature_type, description = args.split(":", 1)
        description = description.strip()

        if not description:
            return {
                "response_type": "ephemeral",
                "text": "❌ Please provide a feature description",
            }

        # Find project linked to this channel
        supabase = get_supabase_client()
        try:
            result = (
                supabase.table("slack_channels")
                .select("project_id")
                .eq("slack_channel_id", channel_id)
                .execute()
            )

            if not result.data:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ This channel is not linked to any Archon project.\nPlease link it first in the Archon UI.",
                }

            project_id = result.data[0]["project_id"]

            # Send immediate response
            response = {
                "response_type": "in_channel",
                "text": f"🤖 Creating tasks for: *{description}*\n\nThe AI-PM is analyzing your request...",
            }

            # TODO: Trigger orchestrator agent asynchronously
            # This would call OrchestratorAgent.analyze_feature(description, project_id)
            # and create tasks in the database

            logger.info(
                f"Feature creation requested: {description}",
                extra={"project_id": project_id, "user": user_id},
            )

            return response

        except Exception as e:
            logger.error(f"Error creating feature: {str(e)}", exc_info=True)
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error: {str(e)}",
            }

    @staticmethod
    async def _handle_status_command(
        channel_id: str, user_id: str
    ) -> dict[str, Any]:
        """
        Handle status command - show project tasks

        Args:
            channel_id: Slack channel ID
            user_id: Slack user ID

        Returns:
            Response with task status
        """
        supabase = get_supabase_client()
        try:
            # Find project for channel
            channel_result = (
                supabase.table("slack_channels")
                .select("project_id, archon_projects(name)")
                .eq("slack_channel_id", channel_id)
                .execute()
            )

            if not channel_result.data:
                return {
                    "response_type": "ephemeral",
                    "text": "❌ This channel is not linked to any project.",
                }

            project_id = channel_result.data[0]["project_id"]
            project_name = channel_result.data[0]["archon_projects"]["name"]

            # Get task counts by status
            tasks_result = (
                supabase.table("archon_tasks")
                .select("status")
                .eq("project_id", project_id)
                .execute()
            )

            tasks = tasks_result.data or []
            status_counts = {"todo": 0, "doing": 0, "review": 0, "done": 0}

            for task in tasks:
                status = task.get("status", "todo")
                if status in status_counts:
                    status_counts[status] += 1

            # Format response
            response_text = f"📊 *{project_name}* Status\n\n"
            response_text += f"📋 To Do: {status_counts['todo']}\n"
            response_text += f"🔄 In Progress: {status_counts['doing']}\n"
            response_text += f"👀 In Review: {status_counts['review']}\n"
            response_text += f"✅ Done: {status_counts['done']}\n"

            return {
                "response_type": "ephemeral",
                "text": response_text,
            }

        except Exception as e:
            logger.error(f"Error getting status: {str(e)}", exc_info=True)
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error: {str(e)}",
            }

    @staticmethod
    async def _handle_help_command() -> dict[str, Any]:
        """
        Return help message with available commands

        Returns:
            Help text response
        """
        help_text = """
🤖 *Archon AI-PM Bot Commands*

*Creating Tasks:*
`/aipm create feature: <description>` - Create feature tasks
Example: `/aipm create feature: Add user authentication with OAuth`

*Project Status:*
`/aipm status` - Show task counts by status

*Help:*
`/aipm help` - Show this help message

_Note: This channel must be linked to an Archon project to use these commands._
        """

        return {
            "response_type": "ephemeral",
            "text": help_text,
        }


class SlackInteractionHandler:
    """
    Handles Slack interactive components (buttons, modals, etc.)
    """

    @classmethod
    async def handle_interaction(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle interactive component payload

        Args:
            payload: Parsed interaction payload from Slack

        Returns:
            Response for Slack
        """
        interaction_type = payload.get("type")

        try:
            if interaction_type == "block_actions":
                return await cls._handle_block_actions(payload)
            elif interaction_type == "view_submission":
                return await cls._handle_modal_submission(payload)
            else:
                logger.warning(f"Unhandled interaction type: {interaction_type}")
                return {"response_action": "errors", "errors": {"base": "Unknown interaction type"}}

        except Exception as e:
            logger.error(f"Error handling interaction: {str(e)}", exc_info=True)
            return {"response_action": "errors", "errors": {"base": str(e)}}

    @staticmethod
    async def _handle_block_actions(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle button clicks and other block actions

        Args:
            payload: Block action payload

        Returns:
            Response for Slack
        """
        actions = payload.get("actions", [])

        for action in actions:
            action_id = action.get("action_id")
            value = action.get("value")

            logger.info(f"Block action: {action_id} = {value}")

            # Example: Handle task approval buttons
            if action_id == "approve_task":
                # Update task status to approved
                pass
            elif action_id == "reject_task":
                # Update task status to rejected
                pass

        return {"response_action": "update", "text": "Action processed ✅"}

    @staticmethod
    async def _handle_modal_submission(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Handle modal form submissions

        Args:
            payload: Modal submission payload

        Returns:
            Response for Slack
        """
        view = payload.get("view", {})
        callback_id = view.get("callback_id")
        values = view.get("state", {}).get("values", {})

        logger.info(f"Modal submitted: {callback_id}")

        # Example: Handle task creation modal
        if callback_id == "create_task_modal":
            # Extract form values and create task
            pass

        return {"response_action": "clear"}
