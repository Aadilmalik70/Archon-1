"""
Asana Integration API Routes

Handles:
- OAuth callback
- Workspace and project management
- Task synchronization
- Webhook management
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..config.logfire_config import get_logger
from ..integrations.asana.asana_oauth import AsanaOAuth, generate_state
from ..integrations.asana.asana_sync import AsanaSync
from ..integrations.asana.asana_webhook import (
    AsanaWebhookHandler,
    AsanaWebhookManager,
)

router = APIRouter(prefix="/api/integrations/asana", tags=["asana"])
logger = get_logger(__name__)


# Request/Response Models


class LinkProjectRequest(BaseModel):
    """Request to link Asana project to Archon project"""

    archon_project_id: str = Field(..., description="Archon project UUID")
    asana_workspace_id: str = Field(..., description="Asana workspace GID")
    asana_project_id: str = Field(..., description="Asana project GID")
    sync_direction: str = Field(
        default="bidirectional",
        description="Sync direction: bidirectional, archon_to_asana, asana_to_archon",
    )


class SyncTaskRequest(BaseModel):
    """Request to sync specific task"""

    archon_task_id: str | None = Field(
        None, description="Archon task ID (for archon→asana)"
    )
    asana_task_gid: str | None = Field(
        None, description="Asana task GID (for asana→archon)"
    )
    archon_project_id: str | None = Field(
        None, description="Required for asana→archon sync"
    )


class BatchSyncRequest(BaseModel):
    """Request to sync entire project"""

    archon_project_id: str = Field(..., description="Archon project UUID")
    direction: str = Field(
        default="bidirectional",
        description="Sync direction: bidirectional, archon_to_asana, asana_to_archon",
    )


class CreateWebhookRequest(BaseModel):
    """Request to create webhook"""

    asana_project_gid: str = Field(..., description="Asana project GID to watch")
    webhook_url: str = Field(..., description="Full HTTPS URL for webhook delivery")


# OAuth Routes


@router.get("/oauth/authorize")
async def initiate_oauth(host: str = "localhost", port: int = 8181) -> dict[str, str]:
    """
    Generate OAuth authorization URL

    Returns URL for user to visit to authorize the Asana app
    """
    try:
        # Generate CSRF protection state
        state = generate_state()

        # Generate authorization URL
        auth_url = AsanaOAuth.get_authorization_url(state, host, port)

        logger.info("Generated Asana OAuth URL", extra={"state": state})

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
    Handle OAuth callback from Asana

    Args:
        code: Authorization code from Asana
        state: State parameter for CSRF protection
        host: Host for redirect URI
        port: Port for redirect URI

    Returns:
        Success message with credential ID
    """
    try:
        # Exchange code for access token
        logger.info("Exchanging Asana OAuth code for token")
        token_data = await AsanaOAuth.exchange_code(code, host, port)

        # Store credentials securely
        credential_id = await AsanaOAuth.store_credentials(token_data)

        # Test connection
        auth_info = await AsanaOAuth.test_connection()

        if not auth_info:
            raise Exception("Failed to verify Asana connection")

        logger.info(
            "Asana OAuth completed successfully",
            extra={
                "user": auth_info.get("name"),
                "credential_id": credential_id,
            },
        )

        return {
            "success": True,
            "message": "Successfully connected to Asana",
            "credential_id": credential_id,
            "user": {
                "gid": auth_info.get("gid"),
                "name": auth_info.get("name"),
                "email": auth_info.get("email"),
            },
        }

    except Exception as e:
        logger.error(f"OAuth callback failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}",
        )


@router.delete("/disconnect")
async def disconnect_asana() -> dict[str, str]:
    """
    Disconnect Asana integration by revoking credentials

    Returns:
        Success message
    """
    try:
        success = await AsanaOAuth.revoke_credentials()

        if not success:
            raise Exception("Failed to revoke Asana credentials")

        logger.info("Asana integration disconnected")

        return {
            "success": True,
            "message": "Successfully disconnected from Asana",
        }

    except Exception as e:
        logger.error(f"Failed to disconnect Asana: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect: {str(e)}",
        )


# Workspace and Project Routes


@router.get("/workspaces")
async def list_workspaces() -> list[dict[str, Any]]:
    """
    List all Asana workspaces accessible to the user

    Returns:
        List of workspaces with gid and name
    """
    try:
        client = await AsanaSync.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Asana. Please complete OAuth flow first.",
            )

        workspaces = await client.get_workspaces()

        logger.info(f"Listed {len(workspaces)} Asana workspaces")

        return workspaces

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list workspaces: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workspaces: {str(e)}",
        )


@router.get("/projects/{workspace_gid}")
async def list_projects(workspace_gid: str) -> list[dict[str, Any]]:
    """
    List all projects in a workspace

    Args:
        workspace_gid: Asana workspace GID

    Returns:
        List of projects with gid and name
    """
    try:
        client = await AsanaSync.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Asana",
            )

        projects = await client.get_projects(workspace_gid)

        logger.info(f"Listed {len(projects)} projects in workspace {workspace_gid}")

        return projects

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list projects: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}",
        )


@router.post("/link-project")
async def link_project(request: LinkProjectRequest) -> dict[str, Any]:
    """
    Link Archon project to Asana project for synchronization

    Args:
        request: Project linking configuration

    Returns:
        Created or updated project mapping
    """
    try:
        mapping = await AsanaSync.link_project_to_asana(
            archon_project_id=request.archon_project_id,
            asana_workspace_id=request.asana_workspace_id,
            asana_project_id=request.asana_project_id,
            sync_direction=request.sync_direction,
        )

        if not mapping:
            raise Exception("Failed to link project to Asana")

        logger.info(
            f"Linked Archon project {request.archon_project_id} to Asana project {request.asana_project_id}"
        )

        return mapping

    except Exception as e:
        logger.error(f"Failed to link project: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link project: {str(e)}",
        )


# Synchronization Routes


@router.post("/sync/task")
async def sync_task(request: SyncTaskRequest) -> dict[str, Any]:
    """
    Sync specific task between Archon and Asana

    Args:
        request: Task sync configuration

    Returns:
        Sync result with task IDs
    """
    try:
        if request.archon_task_id and request.asana_task_gid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide either archon_task_id OR asana_task_gid, not both",
            )

        if not request.archon_task_id and not request.asana_task_gid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either archon_task_id or asana_task_gid",
            )

        # Sync Archon → Asana
        if request.archon_task_id:
            from ...utils import get_supabase_client

            supabase = get_supabase_client()

            # Get task details
            task_result = (
                supabase.table("archon_tasks")
                .select("*, archon_projects!inner(id)")
                .eq("id", request.archon_task_id)
                .execute()
            )

            if not task_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {request.archon_task_id} not found",
                )

            archon_task = task_result.data[0]
            project_id = archon_task["project_id"]

            # Get Asana project mapping
            mapping = (
                supabase.table("asana_projects")
                .select("asana_project_id")
                .eq("archon_project_id", project_id)
                .execute()
            )

            if not mapping.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project {project_id} not linked to Asana",
                )

            asana_project_id = mapping.data[0]["asana_project_id"]

            # Perform sync
            asana_gid = await AsanaSync.sync_task_to_asana(archon_task, asana_project_id)

            if not asana_gid:
                raise Exception("Failed to sync task to Asana")

            return {
                "success": True,
                "direction": "archon_to_asana",
                "archon_task_id": request.archon_task_id,
                "asana_task_gid": asana_gid,
            }

        # Sync Asana → Archon
        else:
            if not request.archon_project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="archon_project_id required for asana→archon sync",
                )

            archon_task_id = await AsanaSync.sync_task_from_asana(
                request.asana_task_gid, request.archon_project_id
            )

            if not archon_task_id:
                raise Exception("Failed to sync task from Asana")

            return {
                "success": True,
                "direction": "asana_to_archon",
                "archon_task_id": archon_task_id,
                "asana_task_gid": request.asana_task_gid,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync task: {str(e)}",
        )


@router.post("/sync/batch")
async def batch_sync(request: BatchSyncRequest) -> dict[str, Any]:
    """
    Perform batch synchronization for entire project

    Args:
        request: Batch sync configuration

    Returns:
        Sync statistics
    """
    try:
        counts = await AsanaSync.batch_sync_project(
            archon_project_id=request.archon_project_id,
            direction=request.direction,
        )

        logger.info(
            f"Batch sync completed for project {request.archon_project_id}",
            extra=counts,
        )

        return {
            "success": True,
            "project_id": request.archon_project_id,
            "direction": request.direction,
            **counts,
        }

    except Exception as e:
        logger.error(f"Batch sync failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch sync failed: {str(e)}",
        )


# Webhook Routes


@router.post("/webhooks")
async def handle_webhook(request: Request) -> dict[str, Any]:
    """
    Handle incoming Asana webhook events

    Verifies signature and routes events to handlers
    """
    try:
        # Get signature header
        signature = request.headers.get("X-Hook-Signature", "")

        # Read raw body
        body = await request.body()
        body_str = body.decode("utf-8")

        # Verify signature
        if not AsanaWebhookHandler.verify_signature(body_str, signature):
            logger.warning("Invalid Asana webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse JSON payload
        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in Asana webhook")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        # Handle events
        events = payload.get("events", [])
        response = await AsanaWebhookHandler.handle_webhook(events)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Asana webhook: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}",
        )


@router.post("/webhooks/create")
async def create_webhook(request: CreateWebhookRequest) -> dict[str, Any]:
    """
    Create webhook subscription for Asana project

    Args:
        request: Webhook configuration

    Returns:
        Created webhook object
    """
    try:
        webhook = await AsanaWebhookManager.create_webhook(
            asana_project_gid=request.asana_project_gid,
            webhook_url=request.webhook_url,
        )

        if not webhook:
            raise Exception("Failed to create webhook")

        logger.info(
            f"Created webhook for project {request.asana_project_gid}",
            extra={"webhook_gid": webhook.get("gid")},
        )

        return webhook

    except Exception as e:
        logger.error(f"Failed to create webhook: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create webhook: {str(e)}",
        )


@router.get("/webhooks")
async def list_webhooks() -> list[dict[str, Any]]:
    """
    List all webhook subscriptions

    Returns:
        List of webhook objects
    """
    try:
        webhooks = await AsanaWebhookManager.list_webhooks()

        logger.info(f"Listed {len(webhooks)} webhooks")

        return webhooks

    except Exception as e:
        logger.error(f"Failed to list webhooks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhooks: {str(e)}",
        )


@router.delete("/webhooks/{webhook_gid}")
async def delete_webhook(webhook_gid: str) -> dict[str, str]:
    """
    Delete webhook subscription

    Args:
        webhook_gid: Webhook GID to delete

    Returns:
        Success message
    """
    try:
        success = await AsanaWebhookManager.delete_webhook(webhook_gid)

        if not success:
            raise Exception("Failed to delete webhook")

        logger.info(f"Deleted webhook {webhook_gid}")

        return {
            "success": True,
            "message": f"Successfully deleted webhook {webhook_gid}",
        }

    except Exception as e:
        logger.error(f"Failed to delete webhook: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete webhook: {str(e)}",
        )


# Testing Routes


@router.get("/test")
async def test_connection() -> dict[str, Any]:
    """
    Test Asana connection

    Returns user information if connected
    """
    try:
        auth_info = await AsanaOAuth.test_connection()

        if not auth_info:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not connected to Asana. Please complete OAuth flow first.",
            )

        return {
            "connected": True,
            "user": {
                "gid": auth_info.get("gid"),
                "name": auth_info.get("name"),
                "email": auth_info.get("email"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}",
        )
