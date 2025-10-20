"""
Asana Sync Service

Handles bidirectional synchronization between Archon tasks and Asana tasks
Includes conflict resolution and comprehensive logging
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client
from .asana_client import AsanaClient
from .asana_oauth import AsanaOAuth

logger = get_logger(__name__)

# Status mapping between Archon and Asana sections
STATUS_MAPPING = {
    "todo": "To Do",
    "doing": "In Progress",
    "review": "Review",
    "done": "Done",
}

# Reverse mapping for Asana → Archon
SECTION_TO_STATUS = {v: k for k, v in STATUS_MAPPING.items()}


class AsanaSync:
    """
    Handles bidirectional task synchronization with conflict resolution
    """

    @classmethod
    async def get_client(cls) -> AsanaClient | None:
        """
        Get authenticated Asana client

        Returns:
            AsanaClient instance if credentials exist, None otherwise
        """
        access_token = await AsanaOAuth.get_access_token()
        if not access_token:
            logger.warning("No Asana access token available")
            return None

        return AsanaClient(access_token)

    @classmethod
    async def link_project_to_asana(
        cls,
        archon_project_id: str,
        asana_workspace_id: str,
        asana_project_id: str,
        sync_direction: str = "bidirectional",
    ) -> dict[str, Any] | None:
        """
        Link Archon project to Asana project

        Args:
            archon_project_id: Archon project UUID
            asana_workspace_id: Asana workspace GID
            asana_project_id: Asana project GID
            sync_direction: "bidirectional", "archon_to_asana", "asana_to_archon"

        Returns:
            Created mapping record or None if failed
        """
        supabase = get_supabase_client()

        try:
            # Check if mapping already exists
            existing = (
                supabase.table("asana_projects")
                .select("*")
                .eq("archon_project_id", archon_project_id)
                .execute()
            )

            if existing.data:
                # Update existing mapping
                result = (
                    supabase.table("asana_projects")
                    .update(
                        {
                            "asana_workspace_id": asana_workspace_id,
                            "asana_project_id": asana_project_id,
                            "sync_direction": sync_direction,
                            "sync_enabled": True,
                        }
                    )
                    .eq("mapping_id", existing.data[0]["mapping_id"])
                    .execute()
                )

                logger.info(
                    f"Updated Asana project mapping for Archon project {archon_project_id}"
                )
            else:
                # Create new mapping
                result = (
                    supabase.table("asana_projects")
                    .insert(
                        {
                            "archon_project_id": archon_project_id,
                            "asana_workspace_id": asana_workspace_id,
                            "asana_project_id": asana_project_id,
                            "sync_direction": sync_direction,
                            "sync_enabled": True,
                        }
                    )
                    .execute()
                )

                logger.info(
                    f"Created Asana project mapping for Archon project {archon_project_id}"
                )

            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Failed to link Asana project: {str(e)}", exc_info=True)
            return None

    @classmethod
    async def sync_task_to_asana(
        cls, archon_task: dict[str, Any], asana_project_id: str
    ) -> str | None:
        """
        Sync Archon task to Asana (create or update)

        Args:
            archon_task: Archon task dict
            asana_project_id: Asana project GID

        Returns:
            Asana task GID if successful, None if failed
        """
        try:
            client = await cls.get_client()
            if not client:
                return None

            archon_task_id = archon_task.get("id")
            existing_asana_id = archon_task.get("asana_task_id")

            # Prepare task data for Asana
            task_data = {
                "name": archon_task.get("title", "Untitled Task"),
                "notes": archon_task.get("description", ""),
                "projects": [asana_project_id],
            }

            # Map priority
            priority = archon_task.get("priority", "medium")
            if priority == "urgent":
                task_data["due_on"] = datetime.now(timezone.utc).date().isoformat()

            # Create or update task
            if existing_asana_id:
                # Update existing task
                logger.info(
                    f"Updating existing Asana task {existing_asana_id} for Archon task {archon_task_id}"
                )
                asana_task = await client.update_task(existing_asana_id, task_data)
                asana_gid = existing_asana_id
            else:
                # Create new task
                logger.info(
                    f"Creating new Asana task for Archon task {archon_task_id}"
                )
                asana_task = await client.create_task(task_data)
                asana_gid = asana_task.get("gid")

                # Update Archon task with Asana ID
                supabase = get_supabase_client()
                supabase.table("archon_tasks").update(
                    {"asana_task_id": asana_gid}
                ).eq("id", archon_task_id).execute()

            # Sync status via sections
            await cls._sync_status_to_asana(
                client, asana_gid, asana_project_id, archon_task.get("status", "todo")
            )

            # Log sync
            await cls._log_sync(
                archon_task_id=archon_task_id,
                external_service="asana",
                external_task_id=asana_gid,
                sync_direction="archon_to_asana",
                sync_status="synced",
            )

            return asana_gid

        except Exception as e:
            logger.error(
                f"Failed to sync task to Asana: {str(e)}",
                exc_info=True,
            )

            # Log failed sync
            if archon_task_id:
                await cls._log_sync(
                    archon_task_id=archon_task_id,
                    external_service="asana",
                    external_task_id=existing_asana_id or "",
                    sync_direction="archon_to_asana",
                    sync_status="failed",
                    conflict_data={"error": str(e)},
                )

            return None

    @classmethod
    async def sync_task_from_asana(
        cls, asana_task_gid: str, archon_project_id: str
    ) -> str | None:
        """
        Sync Asana task to Archon (create or update)

        Args:
            asana_task_gid: Asana task GID
            archon_project_id: Archon project UUID

        Returns:
            Archon task ID if successful, None if failed
        """
        try:
            client = await cls.get_client()
            if not client:
                return None

            supabase = get_supabase_client()

            # Get Asana task details
            asana_task = await client.get_task(asana_task_gid)

            # Check if task already exists in Archon
            existing = (
                supabase.table("archon_tasks")
                .select("*")
                .eq("asana_task_id", asana_task_gid)
                .execute()
            )

            # Prepare task data for Archon
            task_data = {
                "title": asana_task.get("name", "Untitled Task"),
                "description": asana_task.get("notes", ""),
                "project_id": archon_project_id,
                "asana_task_id": asana_task_gid,
                # Map completed status
                "status": "done" if asana_task.get("completed") else "todo",
            }

            if existing.data:
                # Update existing task
                archon_task_id = existing.data[0]["id"]

                # Check for conflicts
                conflict = await cls._detect_conflict(
                    existing.data[0], asana_task
                )

                if conflict:
                    # Log conflict and use last-write-wins
                    logger.warning(
                        f"Sync conflict detected for task {archon_task_id}",
                        extra={"conflict": conflict},
                    )

                    await cls._log_sync(
                        archon_task_id=archon_task_id,
                        external_service="asana",
                        external_task_id=asana_task_gid,
                        sync_direction="asana_to_archon",
                        sync_status="conflict",
                        conflict_data=conflict,
                    )

                    # Last-write-wins: use Asana data
                    logger.info(
                        f"Applying last-write-wins resolution for task {archon_task_id}"
                    )

                # Update task
                result = (
                    supabase.table("archon_tasks")
                    .update(task_data)
                    .eq("id", archon_task_id)
                    .execute()
                )

                logger.info(
                    f"Updated Archon task {archon_task_id} from Asana {asana_task_gid}"
                )
            else:
                # Create new task
                result = supabase.table("archon_tasks").insert(task_data).execute()

                archon_task_id = result.data[0]["id"] if result.data else None

                logger.info(
                    f"Created Archon task {archon_task_id} from Asana {asana_task_gid}"
                )

            # Log sync
            if archon_task_id:
                await cls._log_sync(
                    archon_task_id=archon_task_id,
                    external_service="asana",
                    external_task_id=asana_task_gid,
                    sync_direction="asana_to_archon",
                    sync_status="synced",
                )

            return archon_task_id

        except Exception as e:
            logger.error(
                f"Failed to sync task from Asana: {str(e)}",
                exc_info=True,
            )
            return None

    @classmethod
    async def batch_sync_project(
        cls, archon_project_id: str, direction: str = "bidirectional"
    ) -> dict[str, int]:
        """
        Perform batch sync for entire project

        Args:
            archon_project_id: Archon project UUID
            direction: "bidirectional", "archon_to_asana", "asana_to_archon"

        Returns:
            Dict with counts: {synced_to_asana, synced_from_asana, conflicts, errors}
        """
        try:
            supabase = get_supabase_client()

            # Get project mapping
            mapping = (
                supabase.table("asana_projects")
                .select("*")
                .eq("archon_project_id", archon_project_id)
                .eq("sync_enabled", True)
                .execute()
            )

            if not mapping.data:
                logger.warning(
                    f"No Asana mapping found for project {archon_project_id}"
                )
                return {"synced_to_asana": 0, "synced_from_asana": 0, "conflicts": 0, "errors": 0}

            asana_project_id = mapping.data[0]["asana_project_id"]
            sync_direction = mapping.data[0].get("sync_direction", direction)

            counts = {
                "synced_to_asana": 0,
                "synced_from_asana": 0,
                "conflicts": 0,
                "errors": 0,
            }

            # Sync Archon → Asana
            if sync_direction in ["bidirectional", "archon_to_asana"]:
                archon_tasks = (
                    supabase.table("archon_tasks")
                    .select("*")
                    .eq("project_id", archon_project_id)
                    .execute()
                )

                for task in archon_tasks.data or []:
                    result = await cls.sync_task_to_asana(task, asana_project_id)
                    if result:
                        counts["synced_to_asana"] += 1
                    else:
                        counts["errors"] += 1

            # Sync Asana → Archon
            if sync_direction in ["bidirectional", "asana_to_archon"]:
                client = await cls.get_client()
                if client:
                    asana_tasks = await client.get_tasks_for_project(asana_project_id)

                    for asana_task in asana_tasks:
                        result = await cls.sync_task_from_asana(
                            asana_task.get("gid"), archon_project_id
                        )
                        if result:
                            counts["synced_from_asana"] += 1
                        else:
                            counts["errors"] += 1

            logger.info(
                f"Batch sync completed for project {archon_project_id}",
                extra=counts,
            )

            return counts

        except Exception as e:
            logger.error(f"Batch sync failed: {str(e)}", exc_info=True)
            return {"synced_to_asana": 0, "synced_from_asana": 0, "conflicts": 0, "errors": 1}

    # Helper Methods

    @staticmethod
    async def _sync_status_to_asana(
        client: AsanaClient,
        asana_task_gid: str,
        asana_project_gid: str,
        archon_status: str,
    ) -> None:
        """
        Sync task status by moving to appropriate Asana section

        Args:
            client: Asana client
            asana_task_gid: Asana task GID
            asana_project_gid: Asana project GID
            archon_status: Archon status (todo, doing, review, done)
        """
        try:
            # Get sections for project
            sections = await client.get_sections(asana_project_gid)

            # Find matching section
            target_section_name = STATUS_MAPPING.get(archon_status, "To Do")
            target_section = next(
                (s for s in sections if s.get("name") == target_section_name),
                None,
            )

            if target_section:
                # Move task to section
                await client.add_task_to_section(
                    asana_task_gid, target_section.get("gid")
                )

                logger.debug(
                    f"Moved Asana task {asana_task_gid} to section {target_section_name}"
                )
            else:
                logger.warning(
                    f"Section '{target_section_name}' not found in Asana project"
                )

        except Exception as e:
            logger.error(f"Failed to sync status to Asana: {str(e)}", exc_info=True)

    @staticmethod
    async def _detect_conflict(
        archon_task: dict[str, Any], asana_task: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Detect sync conflicts between Archon and Asana tasks

        Args:
            archon_task: Archon task dict
            asana_task: Asana task dict

        Returns:
            Conflict details if detected, None otherwise
        """
        conflicts = {}

        # Compare timestamps if available
        archon_updated = archon_task.get("updated_at")
        asana_updated = asana_task.get("modified_at")

        if archon_updated and asana_updated:
            try:
                archon_time = datetime.fromisoformat(archon_updated)
                asana_time = datetime.fromisoformat(asana_updated)

                # If both updated within 10 seconds, potential conflict
                time_diff = abs((archon_time - asana_time).total_seconds())

                if time_diff < 10:
                    conflicts["timestamp_collision"] = {
                        "archon_updated": archon_updated,
                        "asana_updated": asana_updated,
                        "difference_seconds": time_diff,
                    }
            except (ValueError, TypeError):
                pass

        # Compare title
        if archon_task.get("title") != asana_task.get("name"):
            conflicts["title_mismatch"] = {
                "archon": archon_task.get("title"),
                "asana": asana_task.get("name"),
            }

        # Compare description
        if archon_task.get("description") != asana_task.get("notes"):
            conflicts["description_mismatch"] = {
                "archon": archon_task.get("description", "")[:100],
                "asana": asana_task.get("notes", "")[:100],
            }

        return conflicts if conflicts else None

    @staticmethod
    async def _log_sync(
        archon_task_id: str,
        external_service: str,
        external_task_id: str,
        sync_direction: str,
        sync_status: str,
        conflict_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Log sync operation to task_sync_log table

        Args:
            archon_task_id: Archon task UUID
            external_service: "asana"
            external_task_id: Asana task GID
            sync_direction: "archon_to_asana" or "asana_to_archon"
            sync_status: "synced", "conflict", "failed"
            conflict_data: Optional conflict details
        """
        supabase = get_supabase_client()

        try:
            supabase.table("task_sync_log").insert(
                {
                    "archon_task_id": archon_task_id,
                    "external_service": external_service,
                    "external_task_id": external_task_id,
                    "sync_direction": sync_direction,
                    "sync_status": sync_status,
                    "conflict_data": conflict_data or {},
                }
            ).execute()

            logger.debug(
                f"Logged sync: {sync_direction} - {sync_status}",
                extra={"task_id": archon_task_id, "external_id": external_task_id},
            )

        except Exception as e:
            logger.error(f"Failed to log sync: {str(e)}", exc_info=True)
