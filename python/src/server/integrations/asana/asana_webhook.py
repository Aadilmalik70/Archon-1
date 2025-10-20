"""
Asana Webhook Handler

Handles incoming Asana webhooks for real-time sync
Includes signature verification and idempotency
"""

import hashlib
import hmac
import os
from typing import Any

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client
from .asana_sync import AsanaSync

logger = get_logger(__name__)

# Webhook secret from environment
ASANA_WEBHOOK_SECRET = os.getenv("ASANA_WEBHOOK_SECRET", "")

# Event deduplication cache (use Redis in production)
_processed_events: set[str] = set()
_MAX_CACHE_SIZE = 10000


class AsanaWebhookHandler:
    """
    Handles Asana webhook events with signature verification
    """

    @staticmethod
    def verify_signature(body: str, signature: str) -> bool:
        """
        Verify Asana webhook signature using X-Hook-Secret

        Args:
            body: Raw request body
            signature: X-Hook-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        if not ASANA_WEBHOOK_SECRET:
            logger.error("ASANA_WEBHOOK_SECRET not configured")
            return False

        # Calculate HMAC signature
        computed_signature = hmac.new(
            ASANA_WEBHOOK_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(computed_signature, signature)

    @staticmethod
    def deduplicate_event(event_id: str) -> bool:
        """
        Check if event has already been processed

        Args:
            event_id: Unique event ID from Asana

        Returns:
            True if event is new (should be processed), False if duplicate
        """
        global _processed_events

        if event_id in _processed_events:
            logger.debug(f"Duplicate Asana event ignored: {event_id}")
            return False

        # Add to cache
        _processed_events.add(event_id)

        # Prevent unbounded growth
        if len(_processed_events) > _MAX_CACHE_SIZE:
            _processed_events = set(list(_processed_events)[_MAX_CACHE_SIZE // 2 :])

        return True

    @classmethod
    async def handle_webhook(cls, events: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Handle incoming webhook events from Asana

        Args:
            events: List of event objects from Asana

        Returns:
            Response dictionary
        """
        try:
            processed_count = 0
            skipped_count = 0

            for event in events:
                # Extract event details
                event_id = event.get("id") or str(event)
                resource = event.get("resource", {})
                resource_gid = resource.get("gid")
                resource_type = resource.get("resource_type")
                action = event.get("action")

                # Deduplicate
                if not cls.deduplicate_event(event_id):
                    skipped_count += 1
                    continue

                logger.info(
                    f"Processing Asana webhook event: {action} on {resource_type} {resource_gid}"
                )

                # Route based on resource type
                if resource_type == "task":
                    await cls._handle_task_event(resource_gid, action, event)
                    processed_count += 1
                elif resource_type == "project":
                    await cls._handle_project_event(resource_gid, action, event)
                    processed_count += 1
                else:
                    logger.debug(f"Ignoring event for resource type: {resource_type}")
                    skipped_count += 1

            logger.info(
                f"Processed {processed_count} events, skipped {skipped_count}"
            )

            return {
                "ok": True,
                "processed": processed_count,
                "skipped": skipped_count,
            }

        except Exception as e:
            logger.error(f"Error handling Asana webhook: {str(e)}", exc_info=True)
            return {"ok": False, "error": str(e)}

    @staticmethod
    async def _handle_task_event(
        task_gid: str, action: str, event: dict[str, Any]
    ) -> None:
        """
        Handle task-related webhook events

        Args:
            task_gid: Asana task GID
            action: Event action (changed, added, removed, deleted, undeleted)
            event: Full event data
        """
        try:
            supabase = get_supabase_client()

            # Check if task is linked to any Archon project
            archon_task = (
                supabase.table("archon_tasks")
                .select("id, project_id")
                .eq("asana_task_id", task_gid)
                .execute()
            )

            if not archon_task.data:
                # Task not linked to Archon yet, check if parent project is linked
                resource = event.get("resource", {})
                parent_gid = resource.get("parent", {}).get("gid") if resource.get("parent") else None

                if parent_gid:
                    # Check if parent is a linked project
                    project_mapping = (
                        supabase.table("asana_projects")
                        .select("archon_project_id")
                        .eq("asana_project_id", parent_gid)
                        .eq("sync_enabled", True)
                        .execute()
                    )

                    if project_mapping.data:
                        # Sync new task from Asana
                        archon_project_id = project_mapping.data[0]["archon_project_id"]
                        logger.info(
                            f"New task {task_gid} in linked project, syncing to Archon"
                        )
                        await AsanaSync.sync_task_from_asana(task_gid, archon_project_id)
                        return

                logger.debug(f"Task {task_gid} not linked to any Archon project")
                return

            archon_task_id = archon_task.data[0]["id"]
            archon_project_id = archon_task.data[0]["project_id"]

            # Handle based on action
            if action == "changed":
                # Task was modified, sync from Asana
                logger.info(f"Task {task_gid} changed, syncing to Archon")
                await AsanaSync.sync_task_from_asana(task_gid, archon_project_id)

            elif action == "deleted":
                # Task was deleted in Asana
                logger.info(f"Task {task_gid} deleted in Asana")

                # Option 1: Delete in Archon too
                # supabase.table("archon_tasks").delete().eq("id", archon_task_id).execute()

                # Option 2: Mark as deleted but keep record
                supabase.table("archon_tasks").update(
                    {"automation_status": "deleted_in_asana"}
                ).eq("id", archon_task_id).execute()

                # Log the event
                await AsanaSync._log_sync(
                    archon_task_id=archon_task_id,
                    external_service="asana",
                    external_task_id=task_gid,
                    sync_direction="asana_to_archon",
                    sync_status="synced",
                    conflict_data={"action": "deleted"},
                )

            elif action == "removed":
                # Task removed from project (but not deleted)
                logger.info(f"Task {task_gid} removed from project")
                # Could update status or flag

            elif action == "undeleted":
                # Task was restored
                logger.info(f"Task {task_gid} undeleted, syncing to Archon")
                await AsanaSync.sync_task_from_asana(task_gid, archon_project_id)

        except Exception as e:
            logger.error(
                f"Error handling task event for {task_gid}: {str(e)}", exc_info=True
            )

    @staticmethod
    async def _handle_project_event(
        project_gid: str, action: str, event: dict[str, Any]
    ) -> None:
        """
        Handle project-related webhook events

        Args:
            project_gid: Asana project GID
            action: Event action
            event: Full event data
        """
        try:
            logger.info(f"Project {project_gid} event: {action}")

            # Could trigger batch sync if project was updated
            if action == "changed":
                supabase = get_supabase_client()

                # Check if project is linked
                mapping = (
                    supabase.table("asana_projects")
                    .select("archon_project_id")
                    .eq("asana_project_id", project_gid)
                    .eq("sync_enabled", True)
                    .execute()
                )

                if mapping.data:
                    archon_project_id = mapping.data[0]["archon_project_id"]
                    logger.info(
                        f"Project {project_gid} changed, could trigger batch sync"
                    )
                    # Optionally trigger batch sync
                    # await AsanaSync.batch_sync_project(archon_project_id)

        except Exception as e:
            logger.error(
                f"Error handling project event for {project_gid}: {str(e)}",
                exc_info=True,
            )


class AsanaWebhookManager:
    """
    Manages webhook subscriptions with Asana API
    """

    @classmethod
    async def create_webhook(
        cls, asana_project_gid: str, webhook_url: str
    ) -> dict[str, Any] | None:
        """
        Create webhook subscription for Asana project

        Args:
            asana_project_gid: Asana project GID to watch
            webhook_url: Full URL for webhook delivery (e.g., https://example.com/api/integrations/asana/webhooks)

        Returns:
            Webhook object with gid, resource, target

        Note: Webhooks require HTTPS in production!
        """
        try:
            from .asana_client import AsanaClient
            from .asana_oauth import AsanaOAuth

            access_token = await AsanaOAuth.get_access_token()
            if not access_token:
                logger.error("No Asana access token available")
                return None

            client = AsanaClient(access_token)

            # Create webhook via Asana API
            webhook_data = {
                "resource": asana_project_gid,
                "target": webhook_url,
            }

            webhook = await client._request("POST", "webhooks", data=webhook_data)

            logger.info(
                f"Created Asana webhook for project {asana_project_gid}",
                extra={"webhook_gid": webhook.get("gid")},
            )

            return webhook

        except Exception as e:
            logger.error(f"Failed to create webhook: {str(e)}", exc_info=True)
            return None

    @classmethod
    async def delete_webhook(cls, webhook_gid: str) -> bool:
        """
        Delete webhook subscription

        Args:
            webhook_gid: Webhook GID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            from .asana_client import AsanaClient
            from .asana_oauth import AsanaOAuth

            access_token = await AsanaOAuth.get_access_token()
            if not access_token:
                logger.error("No Asana access token available")
                return False

            client = AsanaClient(access_token)

            await client._request("DELETE", f"webhooks/{webhook_gid}")

            logger.info(f"Deleted Asana webhook {webhook_gid}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete webhook: {str(e)}", exc_info=True)
            return False

    @classmethod
    async def list_webhooks(cls) -> list[dict[str, Any]]:
        """
        List all webhook subscriptions for current workspace

        Returns:
            List of webhook objects
        """
        try:
            from .asana_client import AsanaClient
            from .asana_oauth import AsanaOAuth

            access_token = await AsanaOAuth.get_access_token()
            if not access_token:
                logger.error("No Asana access token available")
                return []

            client = AsanaClient(access_token)

            # Get current workspace
            workspaces = await client.get_workspaces()
            if not workspaces:
                return []

            workspace_gid = workspaces[0].get("gid")

            # List webhooks
            webhooks = await client._request(
                "GET", "webhooks", params={"workspace": workspace_gid}
            )

            logger.info(
                f"Retrieved {len(webhooks) if isinstance(webhooks, list) else 0} webhooks"
            )

            return webhooks if isinstance(webhooks, list) else []

        except Exception as e:
            logger.error(f"Failed to list webhooks: {str(e)}", exc_info=True)
            return []
