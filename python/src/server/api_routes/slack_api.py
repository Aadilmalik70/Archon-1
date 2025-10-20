"""
Slack Integration API Routes

Handles:
- OAuth callback
- Webhook events
- Channel management
- Connection testing
"""

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..config.logfire_config import get_logger
from ..integrations.slack.slack_events import (
    SlackCommandHandler,
    SlackEventHandler,
    SlackInteractionHandler,
)
from ..integrations.slack.slack_oauth import SlackOAuth, generate_state
from ..integrations.slack.slack_service import SlackService

router = APIRouter(prefix="/api/integrations/slack", tags=["slack"])
logger = get_logger(__name__)


# Request/Response Models


class OAuthInitiateRequest(BaseModel):
    """Request to initiate OAuth flow"""

    host: str = Field(default="localhost", description="Host for redirect URI")
    port: int = Field(default=8181, description="Port for redirect URI")


class OAuthCallbackRequest(BaseModel):
    """OAuth callback parameters"""

    code: str = Field(..., description="Authorization code from Slack")
    state: str = Field(..., description="State parameter for CSRF protection")


class LinkChannelRequest(BaseModel):
    """Request to link Slack channel to project"""

    project_id: str = Field(..., description="Archon project UUID")
    slack_channel_id: str = Field(..., description="Slack channel ID (C1234567890)")
    slack_channel_name: str = Field(..., description="Channel name (#project-updates)")
    notification_types: list[str] = Field(
        default=[
            "task_created",
            "task_completed",
            "task_failed",
            "agent_action",
            "execution_started",
        ],
        description="Types of notifications to send",
    )


class TestNotificationRequest(BaseModel):
    """Request to send test notification"""

    project_id: str = Field(..., description="Project to send notification for")
    message: str = Field(default="Test notification from Archon", description="Test message")


class SendDMRequest(BaseModel):
    """Request to send a direct message to a Slack user"""

    slack_user_id: str = Field(..., description="Slack user ID (U1234567890)")
    message: str = Field(..., description="Message text to send")


class GetDMHistoryRequest(BaseModel):
    """Request to get DM conversation history"""

    slack_user_id: str = Field(..., description="Slack user ID (U1234567890)")
    limit: int = Field(default=50, description="Number of messages to retrieve (max 100)")


# OAuth Routes


@router.get("/oauth/authorize")
async def initiate_oauth(host: str = "localhost", port: int = 8181) -> dict[str, str]:
    """
    Generate OAuth authorization URL

    Returns URL for user to visit to authorize the Slack app
    """
    try:
        # Generate CSRF protection state
        state = generate_state()
        # Generate authorization URL
        auth_url = SlackOAuth.get_authorization_url(state, host, port)

        logger.info("Generated Slack OAuth URL", extra={"state": state})

        return {
            "authorization_url": auth_url,
            "state": state,
        }

    except Exception as e:
        logger.error(f"Failed to generate OAuth URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(e)}",
        )


@router.get("/oauth/callback")
async def oauth_callback(
    code: str, state: str, host: str = "localhost", port: int = 8181
) -> dict[str, Any]:
    """
    Handle OAuth callback from Slack

    Args:
        code: Authorization code from Slack
        state: State parameter for CSRF protection
        host: Host for redirect URI
        port: Port for redirect URI

    Returns:
        Success message with credential ID
    """
    try:
        # Exchange code for access token
        logger.info("Exchanging OAuth code for token")
        token_data = await SlackOAuth.exchange_code(code, host, port)

        # Store credentials securely
        credential_id = await SlackOAuth.store_credentials(token_data)

        # Test connection
        auth_info = await SlackOAuth.test_connection()

        if not auth_info:
            raise Exception("Failed to verify Slack connection")

        logger.info(
            "Slack OAuth completed successfully",
            extra={
                "team": token_data.get("team", {}).get("name"),
                "credential_id": credential_id,
            },
        )

        return {
            "success": True,
            "message": "Successfully connected to Slack",
            "credential_id": credential_id,
            "team": auth_info.get("team"),
            "bot_user_id": auth_info.get("bot_id"),
        }

    except Exception as e:
        logger.error(f"OAuth callback failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}",
        )


@router.delete("/disconnect")
async def disconnect_slack() -> dict[str, Any]:
    """
    Disconnect Slack integration by revoking credentials

    Returns:
        Success message
    """
    try:
        success = await SlackOAuth.revoke_credentials()

        if not success:
            raise Exception("Failed to revoke Slack credentials")

        logger.info("Slack integration disconnected")

        return {
            "success": True,
            "message": "Successfully disconnected from Slack",
        }

    except Exception as e:
        logger.error(f"Failed to disconnect Slack: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect: {str(e)}",
        )


# Channel Management Routes


@router.get("/channels")
async def list_channels() -> list[dict[str, Any]]:
    """
    List all available Slack channels in the workspace

    Returns:
        List of channels with id, name, is_private, is_member
    """
    try:
        channels = await SlackService.list_available_channels()

        logger.info(f"Listed {len(channels)} Slack channels")

        return channels

    except Exception as e:
        logger.error(f"Failed to list channels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list channels: {str(e)}",
        )


@router.post("/link-channel")
async def link_channel(request: LinkChannelRequest) -> dict[str, Any]:
    """
    Link a Slack channel to an Archon project

    Args:
        request: Channel linking configuration

    Returns:
        Created or updated channel mapping
    """
    try:
        mapping = await SlackService.link_channel_to_project(
            project_id=request.project_id,
            slack_channel_id=request.slack_channel_id,
            slack_channel_name=request.slack_channel_name,
            notification_types=request.notification_types,
        )

        if not mapping:
            raise Exception("Failed to link channel to project")

        logger.info(
            f"Linked Slack channel {request.slack_channel_name} to project {request.project_id}"
        )

        return mapping

    except Exception as e:
        logger.error(f"Failed to link channel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link channel: {str(e)}",
        )


@router.get("/channels/{project_id}")
async def get_project_channels(project_id: str) -> list[dict[str, Any]]:
    """
    Get all Slack channels linked to a project

    Args:
        project_id: Project UUID

    Returns:
        List of linked channels
    """
    try:
        channels = await SlackService.get_project_channels(project_id)

        logger.info(f"Retrieved {len(channels)} channels for project {project_id}")

        return channels

    except Exception as e:
        logger.error(f"Failed to get project channels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project channels: {str(e)}",
        )


# Webhook Routes


@router.post("/events")
async def handle_events(request: Request) -> dict[str, Any]:
    """
    Handle incoming Slack events webhook

    Verifies signature and routes events to appropriate handlers
    """
    try:
        # Get headers for signature verification
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        # Read raw body for signature verification
        body = await request.body()
        body_str = body.decode("utf-8")

        logger.info(f"Received Slack event webhook", extra={"body_preview": body_str[:200]})

        # Verify signature
        if not SlackEventHandler.verify_signature(timestamp, body_str, signature):
            logger.warning("Invalid Slack webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse JSON payload
        try:
            event_data = json.loads(body_str)
            logger.info(f"Parsed event data", extra={"type": event_data.get("type"), "event": event_data.get("event", {}).get("type")})
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Slack webhook")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        # Handle event
        response = await SlackEventHandler.handle_event(event_data)
        
        logger.info(f"Event handled successfully", extra={"response": response})

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Slack event: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing event: {str(e)}",
        )


@router.post("/commands")
async def handle_slash_command(request: Request) -> dict[str, Any]:
    """
    Handle incoming Slack slash commands

    Verifies signature and routes commands to handlers
    """
    try:
        # Get headers for signature verification
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        # Read raw body
        body = await request.body()
        body_str = body.decode("utf-8")

        # Verify signature
        if not SlackEventHandler.verify_signature(timestamp, body_str, signature):
            logger.warning("Invalid Slack command signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse form data
        form_data = {}
        for pair in body_str.split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                # URL decode
                from urllib.parse import unquote_plus

                form_data[key] = unquote_plus(value)

        # Handle command
        response = await SlackCommandHandler.handle_slash_command(form_data)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Slack command: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing command: {str(e)}",
        )


@router.post("/interactions")
async def handle_interactions(request: Request) -> dict[str, Any]:
    """
    Handle interactive component callbacks (buttons, modals, etc.)

    Verifies signature and routes interactions to handlers
    """
    try:
        # Get headers for signature verification
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        # Read raw body
        body = await request.body()
        body_str = body.decode("utf-8")

        # Verify signature
        if not SlackEventHandler.verify_signature(timestamp, body_str, signature):
            logger.warning("Invalid Slack interaction signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse form data (payload is URL-encoded JSON)
        from urllib.parse import parse_qs, unquote_plus

        parsed = parse_qs(body_str)
        payload_str = parsed.get("payload", [""])[0]

        try:
            payload = json.loads(unquote_plus(payload_str))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in interaction payload")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload format",
            )

        # Handle interaction
        response = await SlackInteractionHandler.handle_interaction(payload)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing interaction: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing interaction: {str(e)}",
        )


# Testing Routes


@router.get("/test")
async def test_connection() -> dict[str, Any]:
    """
    Test Slack connection

    Returns workspace and bot information if connected
    """
    try:
        auth_info = await SlackOAuth.test_connection()

        if not auth_info:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Slack. Please complete OAuth flow first.",
            )

        return {
            "connected": True,
            "team": auth_info.get("team"),
            "team_id": auth_info.get("team_id"),
            "user": auth_info.get("user"),
            "user_id": auth_info.get("user_id"),
            "bot_id": auth_info.get("bot_id"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}",
        )


@router.post("/test-notification")
async def send_test_notification(request: TestNotificationRequest) -> dict[str, Any]:
    """
    Send test notification to project channels

    Args:
        request: Test notification configuration

    Returns:
        Number of messages sent
    """
    try:
        # Create test task object
        test_task = {
            "id": "00000000-0000-0000-0000-000000000000",
            "title": "Test Notification",
            "description": request.message,
            "agent_assigned": "system",
            "priority": "low",
            "execution_metadata": {"estimated_effort": "test"},
        }

        # Send notification
        responses = await SlackService.send_task_notification(
            project_id=request.project_id,
            task=test_task,
            notification_type="task_created",
        )

        logger.info(f"Sent {len(responses)} test notifications")

        return {
            "success": True,
            "messages_sent": len(responses),
            "channels": [r.get("channel") for r in responses if r.get("channel")],
        }

    except Exception as e:
        logger.error(f"Failed to send test notification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}",
        )


# Direct Message Routes


@router.get("/users")
async def list_workspace_users() -> list[dict[str, Any]]:
    """
    List all users in the Slack workspace

    Returns:
        List of users with id, name, real_name, profile info
    """
    try:
        access_token = await SlackOAuth.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Slack. Please complete OAuth flow first.",
            )

        from ..integrations.slack.slack_client import SlackClient

        client = SlackClient(access_token)
        users = await client.list_workspace_users()

        # Format user data for frontend
        formatted_users = [
            {
                "id": user.get("id"),
                "name": user.get("name"),
                "real_name": user.get("real_name"),
                "display_name": user.get("profile", {}).get("display_name"),
                "email": user.get("profile", {}).get("email"),
                "image": user.get("profile", {}).get("image_48"),
                "is_admin": user.get("is_admin", False),
            }
            for user in users
        ]

        logger.info(f"Listed {len(formatted_users)} workspace users")
        return formatted_users

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}",
        )


@router.post("/dm/send")
async def send_direct_message(request: SendDMRequest) -> dict[str, Any]:
    """
    Send a direct message to a Slack user

    Args:
        request: DM send configuration

    Returns:
        Message details including timestamp and channel
    """
    try:
        access_token = await SlackOAuth.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Slack. Please complete OAuth flow first.",
            )

        from ..integrations.slack.slack_client import SlackClient

        client = SlackClient(access_token)
        result = await client.send_dm(
            user_id=request.slack_user_id,
            text=request.message,
        )

        logger.info(f"Sent DM to user {request.slack_user_id}")

        return {
            "success": True,
            "message": "DM sent successfully",
            "timestamp": result.get("ts"),
            "channel": result.get("channel"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send DM: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send DM: {str(e)}",
        )


@router.post("/dm/history")
async def get_dm_history(request: GetDMHistoryRequest) -> list[dict[str, Any]]:
    """
    Get conversation history with a Slack user

    Args:
        request: History request configuration

    Returns:
        List of messages from the conversation
    """
    try:
        access_token = await SlackOAuth.get_access_token()
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Slack. Please complete OAuth flow first.",
            )

        from ..integrations.slack.slack_client import SlackClient

        client = SlackClient(access_token)

        # First open DM channel to get channel ID
        dm_channel_id = await client.open_dm_channel(request.slack_user_id)

        # Get history
        messages = await client.get_dm_history(
            channel_id=dm_channel_id,
            limit=min(request.limit, 100),
        )

        logger.info(
            f"Retrieved {len(messages)} messages from DM with {request.slack_user_id}"
        )

        return messages

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get DM history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get DM history: {str(e)}",
        )
