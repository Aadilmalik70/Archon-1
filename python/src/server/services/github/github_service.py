"""
GitHub Service Module

Handles GitHub repository operations including cloning, fetching, and metadata retrieval.
"""

import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from github import Auth, Github, GithubException, RateLimitExceededException
from git import Repo as GitRepo, GitCommandError

from ...config.logfire_config import get_logger

logger = get_logger(__name__)

# File extensions to process for code extraction
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cpp", ".c", ".h",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".sql", ".html", ".css", ".scss", ".sass", ".yaml", ".yml", ".json",
    ".xml", ".md", ".txt", ".dockerfile", ".toml", ".ini", ".conf"
}

# Files/directories to always exclude
DEFAULT_EXCLUDES = {
    "node_modules", ".git", ".svn", ".hg", "__pycache__", ".pytest_cache",
    "venv", "env", ".venv", "build", "dist", ".next", "out", "target",
    "bin", "obj", "coverage", ".nyc_output", ".tox", "eggs", ".eggs"
}

# Maximum file size to process (1MB)
MAX_FILE_SIZE = 1024 * 1024


class GitHubService:
    """Service for GitHub repository operations"""

    def __init__(self, github_token: str | None = None):
        """
        Initialize GitHub service with optional token.

        Args:
            github_token: Personal Access Token for GitHub API
        """
        self.github_token = github_token
        self.github_client = None

        if github_token:
            auth = Auth.Token(github_token)
            self.github_client = Github(auth=auth)

    async def validate_token(self, token: str) -> tuple[bool, dict[str, Any]]:
        """
        Validate a GitHub Personal Access Token.

        Args:
            token: GitHub PAT to validate

        Returns:
            Tuple of (is_valid, info_dict)
        """
        try:
            auth = Auth.Token(token)
            client = Github(auth=auth)

            # Try to get user info to validate token
            user = client.get_user()
            login = user.login

            # Get rate limit info (simplified)
            try:
                rate_limit = client.get_rate_limit()
                rate_info = {
                    "remaining": rate_limit.rate.remaining,
                    "limit": rate_limit.rate.limit,
                    "reset": rate_limit.rate.reset.isoformat() if rate_limit.rate.reset else None
                }
            except Exception:
                # If rate limit fails, just skip it
                rate_info = None

            logger.info(f"Token validated for user: {login}")

            result = {
                "valid": True,
                "user": login
            }

            if rate_info:
                result["rate_limit"] = rate_info

            return True, result

        except GithubException as e:
            logger.warning(f"GitHub token validation failed: {e.status} - {e.data.get('message', 'Unknown error')}")
            return False, {
                "valid": False,
                "error": e.data.get("message", "Invalid token")
            }
        except Exception as e:
            logger.error(f"Unexpected error validating token: {str(e)}", exc_info=True)
            return False, {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }

    def parse_repository_url(self, repo_url: str) -> tuple[str, str] | None:
        """
        Parse GitHub repository URL to extract owner and repo name.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Tuple of (owner, repo) or None if invalid
        """
        # Support various GitHub URL formats
        # https://github.com/owner/repo
        # https://github.com/owner/repo.git
        # git@github.com:owner/repo.git
        # owner/repo

        # Remove .git suffix if present
        repo_url = repo_url.rstrip("/").removesuffix(".git")

        # Try HTTPS URL format
        https_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", repo_url)
        if https_match:
            return https_match.groups()

        # Try SSH format
        ssh_match = re.match(r"git@github\.com:([^/]+)/([^/]+)", repo_url)
        if ssh_match:
            return ssh_match.groups()

        # Try simple owner/repo format
        simple_match = re.match(r"^([^/]+)/([^/]+)$", repo_url)
        if simple_match:
            return simple_match.groups()

        return None

    async def list_branches(self, repo_url: str) -> tuple[bool, dict[str, Any]]:
        """
        List all branches in a repository.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Tuple of (success, result_dict)
        """
        if not self.github_client:
            return False, {"error": "GitHub token not configured"}

        try:
            parsed = self.parse_repository_url(repo_url)
            if not parsed:
                return False, {"error": "Invalid GitHub repository URL"}

            owner, repo_name = parsed

            # Get repository
            repo = self.github_client.get_repo(f"{owner}/{repo_name}")

            # Get all branches
            branches = []
            for branch in repo.get_branches():
                branches.append({
                    "name": branch.name,
                    "protected": branch.protected,
                    "commit_sha": branch.commit.sha if branch.commit else None
                })

            # Get default branch
            default_branch = repo.default_branch

            logger.info(f"Listed {len(branches)} branches for {owner}/{repo_name}")

            return True, {
                "branches": branches,
                "default_branch": default_branch,
                "total": len(branches)
            }

        except RateLimitExceededException:
            return False, {"error": "GitHub API rate limit exceeded. Please try again later."}
        except GithubException as e:
            logger.error(f"GitHub API error listing branches: {e.status} - {e.data.get('message', 'Unknown')}")
            return False, {"error": f"GitHub API error: {e.data.get('message', 'Failed to list branches')}"}
        except Exception as e:
            logger.error(f"Unexpected error listing branches: {str(e)}", exc_info=True)
            return False, {"error": f"Failed to list branches: {str(e)}"}

    async def get_repository_tree(
        self,
        repo_url: str,
        branch: str = "main",
        path: str = ""
    ) -> tuple[bool, dict[str, Any]]:
        """
        Get repository file tree structure.

        Args:
            repo_url: GitHub repository URL
            branch: Branch name (default: "main")
            path: Path within repository (default: root)

        Returns:
            Tuple of (success, result_dict with tree structure)
        """
        if not self.github_client:
            return False, {"error": "GitHub token not configured"}

        try:
            parsed = self.parse_repository_url(repo_url)
            if not parsed:
                return False, {"error": "Invalid GitHub repository URL"}

            owner, repo_name = parsed

            # Get repository
            repo = self.github_client.get_repo(f"{owner}/{repo_name}")

            # Get tree
            try:
                contents = repo.get_contents(path, ref=branch)
            except GithubException as e:
                if e.status == 404:
                    return False, {"error": f"Branch '{branch}' not found"}
                raise

            # Build tree structure
            tree = []
            if isinstance(contents, list):
                for content in contents:
                    tree.append({
                        "name": content.name,
                        "path": content.path,
                        "type": content.type,  # "file" or "dir"
                        "size": content.size if content.type == "file" else None,
                        "sha": content.sha
                    })
            else:
                # Single file
                tree.append({
                    "name": contents.name,
                    "path": contents.path,
                    "type": contents.type,
                    "size": contents.size,
                    "sha": contents.sha
                })

            logger.info(f"Retrieved tree for {owner}/{repo_name} at {path or 'root'}")

            return True, {
                "tree": tree,
                "total": len(tree)
            }

        except RateLimitExceededException:
            return False, {"error": "GitHub API rate limit exceeded. Please try again later."}
        except GithubException as e:
            logger.error(f"GitHub API error getting tree: {e.status} - {e.data.get('message', 'Unknown')}")
            return False, {"error": f"GitHub API error: {e.data.get('message', 'Failed to get repository tree')}"}
        except Exception as e:
            logger.error(f"Unexpected error getting tree: {str(e)}", exc_info=True)
            return False, {"error": f"Failed to get repository tree: {str(e)}"}

    async def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        progress_callback: Any | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Clone a GitHub repository to a temporary directory.

        Args:
            repo_url: GitHub repository URL
            branch: Branch to clone
            include_patterns: List of glob patterns to include (e.g., ["src/**/*.ts"])
            exclude_patterns: List of glob patterns to exclude
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (success, result_dict with clone_path and file_list)
        """
        clone_path = None
        try:
            # Parse repository URL
            parsed = self.parse_repository_url(repo_url)
            if not parsed:
                return False, {"error": "Invalid GitHub repository URL"}

            owner, repo_name = parsed

            if progress_callback:
                await progress_callback(f"Starting clone of {owner}/{repo_name}", 5)

            # Create temporary directory for clone
            clone_path = tempfile.mkdtemp(prefix=f"archon_github_{owner}_{repo_name}_")
            logger.info(f"Cloning {owner}/{repo_name} to {clone_path}")

            # Build clone URL with token if available
            if self.github_token:
                clone_url = f"https://{self.github_token}@github.com/{owner}/{repo_name}.git"
            else:
                clone_url = f"https://github.com/{owner}/{repo_name}.git"

            if progress_callback:
                await progress_callback(f"Cloning repository...", 10)

            # Clone repository (shallow clone for efficiency)
            repo = await asyncio.to_thread(
                GitRepo.clone_from,
                clone_url,
                clone_path,
                branch=branch,
                depth=1,  # Shallow clone
                single_branch=True
            )

            logger.info(f"Repository cloned successfully to {clone_path}")

            if progress_callback:
                await progress_callback(f"Scanning files...", 30)

            # Extract files for processing
            success, file_result = await self.extract_files_for_indexing(
                clone_path,
                include_patterns,
                exclude_patterns,
                progress_callback
            )

            if not success:
                return False, file_result

            return True, {
                "clone_path": clone_path,
                "files": file_result["files"],
                "file_count": file_result["file_count"],
                "total_size": file_result["total_size"],
                "owner": owner,
                "repo_name": repo_name,
                "branch": branch
            }

        except GitCommandError as e:
            logger.error(f"Git clone failed: {str(e)}", exc_info=True)
            if clone_path and os.path.exists(clone_path):
                shutil.rmtree(clone_path, ignore_errors=True)
            return False, {"error": f"Failed to clone repository: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error cloning repository: {str(e)}", exc_info=True)
            if clone_path and os.path.exists(clone_path):
                shutil.rmtree(clone_path, ignore_errors=True)
            return False, {"error": f"Failed to clone repository: {str(e)}"}

    async def extract_files_for_indexing(
        self,
        repo_path: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        progress_callback: Any | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Extract files from cloned repository for indexing.

        Args:
            repo_path: Path to cloned repository
            include_patterns: Glob patterns to include
            exclude_patterns: Glob patterns to exclude
            progress_callback: Optional progress callback

        Returns:
            Tuple of (success, result_dict with file list)
        """
        try:
            repo_pathlib = Path(repo_path)
            files = []
            total_size = 0
            processed = 0

            # Get all files recursively
            all_files = list(repo_pathlib.rglob("*"))
            total_files = len([f for f in all_files if f.is_file()])

            logger.info(f"Scanning {total_files} files in {repo_path}")

            for file_path in all_files:
                if not file_path.is_file():
                    continue

                # Calculate relative path
                rel_path = file_path.relative_to(repo_pathlib)
                rel_path_str = str(rel_path).replace("\\", "/")

                # Skip if in default excludes
                if any(excluded in rel_path.parts for excluded in DEFAULT_EXCLUDES):
                    continue

                # Check exclude patterns
                if exclude_patterns:
                    from fnmatch import fnmatch
                    if any(fnmatch(rel_path_str, pattern) for pattern in exclude_patterns):
                        continue

                # Check include patterns (if specified, only include matching files)
                if include_patterns:
                    from fnmatch import fnmatch
                    if not any(fnmatch(rel_path_str, pattern) for pattern in include_patterns):
                        continue

                # Check file extension
                if file_path.suffix.lower() not in CODE_EXTENSIONS:
                    continue

                # Check file size
                file_size = file_path.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    logger.debug(f"Skipping large file: {rel_path_str} ({file_size} bytes)")
                    continue

                files.append({
                    "path": rel_path_str,
                    "absolute_path": str(file_path),
                    "size": file_size,
                    "extension": file_path.suffix.lower()
                })

                total_size += file_size
                processed += 1

                # Report progress every 50 files
                if progress_callback and processed % 50 == 0:
                    progress_pct = 30 + int((processed / total_files) * 40)
                    await progress_callback(f"Scanned {processed}/{total_files} files", progress_pct)

            logger.info(f"Extracted {len(files)} files for indexing (total size: {total_size} bytes)")

            return True, {
                "files": files,
                "file_count": len(files),
                "total_size": total_size
            }

        except Exception as e:
            logger.error(f"Error extracting files: {str(e)}", exc_info=True)
            return False, {"error": f"Failed to extract files: {str(e)}"}

    def cleanup_clone(self, clone_path: str) -> None:
        """
        Clean up cloned repository directory.

        Args:
            clone_path: Path to cloned repository
        """
        try:
            if clone_path and os.path.exists(clone_path):
                shutil.rmtree(clone_path, ignore_errors=True)
                logger.info(f"Cleaned up clone directory: {clone_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up clone directory {clone_path}: {str(e)}")
