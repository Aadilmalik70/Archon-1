"""
Asana API Client

Low-level wrapper around Asana REST API with rate limiting
Handles direct API communication with proper error handling

Rate Limit: 150 requests per minute per token
"""

import asyncio
import httpx
import time
from typing import Any

from ...config.logfire_config import get_logger

logger = get_logger(__name__)


class AsanaRateLimiter:
    """
    Rate limiter for Asana API (150 requests/minute)
    """

    def __init__(self, max_requests: int = 150, time_window: int = 60):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed per time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make request (blocks if rate limit reached)
        """
        async with self._lock:
            current_time = time.time()

            # Remove requests outside time window
            self.requests = [
                req_time
                for req_time in self.requests
                if current_time - req_time < self.time_window
            ]

            # If at limit, wait until oldest request expires
            if len(self.requests) >= self.max_requests:
                wait_time = self.time_window - (current_time - self.requests[0]) + 0.1
                logger.warning(
                    f"Asana rate limit reached, waiting {wait_time:.2f}s",
                    extra={"requests_in_window": len(self.requests)},
                )
                await asyncio.sleep(wait_time)

                # Retry acquiring
                return await self.acquire()

            # Record this request
            self.requests.append(current_time)


class AsanaClient:
    """
    Asana API client for direct API communication

    Provides methods for:
    - Workspace and project management
    - Task CRUD operations
    - Custom field handling
    - Comments and attachments
    """

    BASE_URL = "https://app.asana.com/api/1.0"
    TIMEOUT = 30.0

    def __init__(self, access_token: str):
        """
        Initialize Asana client with access token

        Args:
            access_token: Asana OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.rate_limiter = AsanaRateLimiter()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request to Asana API with rate limiting

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body for POST/PUT
            params: Query parameters

        Returns:
            Response data from Asana API

        Raises:
            Exception: If API returns an error
        """
        # Apply rate limiting
        await self.rate_limiter.acquire()

        url = f"{self.BASE_URL}/{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json={"data": data} if data else None,
                    params=params,
                    timeout=self.TIMEOUT,
                )

                result = response.json()

                # Check for errors
                if response.status_code >= 400:
                    errors = result.get("errors", [])
                    error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
                    logger.error(
                        f"Asana API error: {error_msg}",
                        extra={"status": response.status_code, "endpoint": endpoint},
                    )
                    raise Exception(f"Asana API error: {error_msg}")

                return result.get("data", {})

            except httpx.TimeoutException:
                logger.error(f"Asana API timeout on {endpoint}")
                raise Exception(f"Asana API request timed out: {endpoint}")
            except httpx.RequestError as e:
                logger.error(f"Asana API request error: {str(e)}")
                raise Exception(f"Asana API request failed: {str(e)}")

    # Workspace Methods

    async def get_workspaces(self) -> list[dict[str, Any]]:
        """
        Get all workspaces accessible to the user

        Returns:
            List of workspace objects with gid and name
        """
        try:
            workspaces = await self._request("GET", "workspaces")

            logger.info(f"Retrieved {len(workspaces)} Asana workspaces")

            return workspaces if isinstance(workspaces, list) else []

        except Exception as e:
            logger.error(f"Failed to get workspaces: {str(e)}", exc_info=True)
            raise

    async def get_projects(
        self, workspace_gid: str, archived: bool = False
    ) -> list[dict[str, Any]]:
        """
        Get all projects in a workspace

        Args:
            workspace_gid: Workspace global ID
            archived: Include archived projects

        Returns:
            List of project objects
        """
        try:
            projects = await self._request(
                "GET",
                "projects",
                params={"workspace": workspace_gid, "archived": archived},
            )

            logger.info(
                f"Retrieved {len(projects) if isinstance(projects, list) else 0} projects from workspace {workspace_gid}"
            )

            return projects if isinstance(projects, list) else []

        except Exception as e:
            logger.error(f"Failed to get projects: {str(e)}", exc_info=True)
            raise

    # Task Methods

    async def create_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new task in Asana

        Args:
            task_data: Task properties
                - name (required): Task title
                - notes: Task description
                - projects: List of project GIDs
                - assignee: User GID
                - due_on: Due date (YYYY-MM-DD)
                - custom_fields: Dict of custom field values

        Returns:
            Created task object with gid
        """
        try:
            task = await self._request("POST", "tasks", data=task_data)

            logger.info(
                f"Created Asana task: {task.get('name')}",
                extra={"gid": task.get("gid")},
            )

            return task

        except Exception as e:
            logger.error(f"Failed to create task: {str(e)}", exc_info=True)
            raise

    async def get_task(self, task_gid: str) -> dict[str, Any]:
        """
        Get task details by GID

        Args:
            task_gid: Task global ID

        Returns:
            Task object with full details
        """
        try:
            task = await self._request("GET", f"tasks/{task_gid}")

            logger.debug(f"Retrieved task {task_gid}: {task.get('name')}")

            return task

        except Exception as e:
            logger.error(f"Failed to get task {task_gid}: {str(e)}", exc_info=True)
            raise

    async def update_task(
        self, task_gid: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update task properties

        Args:
            task_gid: Task global ID
            updates: Properties to update
                - name: New title
                - notes: New description
                - completed: Mark as complete (boolean)
                - assignee: New assignee GID
                - due_on: New due date

        Returns:
            Updated task object
        """
        try:
            task = await self._request("PUT", f"tasks/{task_gid}", data=updates)

            logger.info(f"Updated task {task_gid}")

            return task

        except Exception as e:
            logger.error(f"Failed to update task {task_gid}: {str(e)}", exc_info=True)
            raise

    async def delete_task(self, task_gid: str) -> bool:
        """
        Delete a task

        Args:
            task_gid: Task global ID

        Returns:
            True if successful
        """
        try:
            await self._request("DELETE", f"tasks/{task_gid}")

            logger.info(f"Deleted task {task_gid}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete task {task_gid}: {str(e)}", exc_info=True)
            raise

    async def get_tasks_for_project(
        self, project_gid: str, completed: bool | None = None
    ) -> list[dict[str, Any]]:
        """
        Get all tasks in a project

        Args:
            project_gid: Project global ID
            completed: Filter by completion status (None = all)

        Returns:
            List of task objects
        """
        try:
            params = {"project": project_gid}
            if completed is not None:
                params["completed_since"] = "now" if completed else "2000-01-01"

            tasks = await self._request("GET", "tasks", params=params)

            logger.info(
                f"Retrieved {len(tasks) if isinstance(tasks, list) else 0} tasks from project {project_gid}"
            )

            return tasks if isinstance(tasks, list) else []

        except Exception as e:
            logger.error(f"Failed to get project tasks: {str(e)}", exc_info=True)
            raise

    # Section Methods (for status mapping)

    async def get_sections(self, project_gid: str) -> list[dict[str, Any]]:
        """
        Get all sections in a project

        Sections are used to organize tasks (e.g., "To Do", "In Progress", "Done")

        Args:
            project_gid: Project global ID

        Returns:
            List of section objects with gid and name
        """
        try:
            sections = await self._request(
                "GET", f"projects/{project_gid}/sections"
            )

            logger.info(
                f"Retrieved {len(sections) if isinstance(sections, list) else 0} sections from project {project_gid}"
            )

            return sections if isinstance(sections, list) else []

        except Exception as e:
            logger.error(f"Failed to get sections: {str(e)}", exc_info=True)
            raise

    async def add_task_to_section(
        self, task_gid: str, section_gid: str
    ) -> dict[str, Any]:
        """
        Move task to a section (e.g., change status)

        Args:
            task_gid: Task global ID
            section_gid: Section global ID

        Returns:
            Empty response on success
        """
        try:
            result = await self._request(
                "POST",
                f"sections/{section_gid}/addTask",
                data={"task": task_gid},
            )

            logger.info(f"Moved task {task_gid} to section {section_gid}")

            return result

        except Exception as e:
            logger.error(
                f"Failed to move task to section: {str(e)}", exc_info=True
            )
            raise

    # Comment Methods

    async def add_comment(
        self, task_gid: str, text: str
    ) -> dict[str, Any]:
        """
        Add a comment to a task

        Args:
            task_gid: Task global ID
            text: Comment text

        Returns:
            Created story (comment) object
        """
        try:
            story = await self._request(
                "POST",
                f"tasks/{task_gid}/stories",
                data={"text": text},
            )

            logger.info(f"Added comment to task {task_gid}")

            return story

        except Exception as e:
            logger.error(f"Failed to add comment: {str(e)}", exc_info=True)
            raise

    async def get_comments(self, task_gid: str) -> list[dict[str, Any]]:
        """
        Get all comments (stories) for a task

        Args:
            task_gid: Task global ID

        Returns:
            List of story objects
        """
        try:
            stories = await self._request("GET", f"tasks/{task_gid}/stories")

            logger.debug(
                f"Retrieved {len(stories) if isinstance(stories, list) else 0} comments for task {task_gid}"
            )

            return stories if isinstance(stories, list) else []

        except Exception as e:
            logger.error(f"Failed to get comments: {str(e)}", exc_info=True)
            raise

    # Custom Fields

    async def get_custom_fields(
        self, workspace_gid: str
    ) -> list[dict[str, Any]]:
        """
        Get all custom fields in a workspace

        Args:
            workspace_gid: Workspace global ID

        Returns:
            List of custom field objects
        """
        try:
            fields = await self._request(
                "GET",
                "custom_fields",
                params={"workspace": workspace_gid},
            )

            logger.info(
                f"Retrieved {len(fields) if isinstance(fields, list) else 0} custom fields"
            )

            return fields if isinstance(fields, list) else []

        except Exception as e:
            logger.error(f"Failed to get custom fields: {str(e)}", exc_info=True)
            raise

    # Attachments

    async def get_attachments(self, task_gid: str) -> list[dict[str, Any]]:
        """
        Get all attachments for a task

        Args:
            task_gid: Task global ID

        Returns:
            List of attachment objects
        """
        try:
            attachments = await self._request(
                "GET", f"tasks/{task_gid}/attachments"
            )

            logger.debug(
                f"Retrieved {len(attachments) if isinstance(attachments, list) else 0} attachments for task {task_gid}"
            )

            return attachments if isinstance(attachments, list) else []

        except Exception as e:
            logger.error(f"Failed to get attachments: {str(e)}", exc_info=True)
            raise

    # Auth Test

    async def test_auth(self) -> dict[str, Any]:
        """
        Test authentication and get current user info

        Returns:
            User object with gid, name, email
        """
        try:
            user = await self._request("GET", "users/me")

            logger.info(
                f"Asana auth successful for user: {user.get('name')}",
                extra={"gid": user.get("gid"), "email": user.get("email")},
            )

            return user

        except Exception as e:
            logger.error(f"Asana auth test failed: {str(e)}", exc_info=True)
            raise
