"""
GitHub Context Service

Extracts relevant context from GitHub repositories for AI-PM orchestrator.
Provides file structure, relevant code, and dependencies to help with feature planning.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from ...config.logfire_config import get_logger
from .github_service import GitHubService

logger = get_logger(__name__)


class GitHubContextService:
    """Service for extracting GitHub repository context"""

    def __init__(self, github_token: str | None = None):
        """
        Initialize GitHub context service.

        Args:
            github_token: GitHub Personal Access Token
        """
        self.github_service = GitHubService(github_token)
        self.github_token = github_token

    async def get_repo_context(
        self,
        repo_url: str,
        feature_description: str,
        branch: str = "main",
        max_files: int = 20,
    ) -> dict[str, Any]:
        """
        Get comprehensive repository context for feature planning.

        Args:
            repo_url: GitHub repository URL
            feature_description: Description of the feature to implement
            branch: Branch to analyze (default: main)
            max_files: Maximum number of relevant files to include

        Returns:
            Dictionary with repo context:
            {
                "repo_info": {...},           # Basic repo metadata
                "file_structure": {...},      # Directory tree
                "relevant_files": [...],      # Files likely related to feature
                "dependencies": {...},        # Package dependencies
                "similar_code": [...],        # RAG search results
                "tech_stack": [...],          # Detected technologies
            }
        """
        logger.info(f"Extracting context from {repo_url} for feature: {feature_description[:100]}")

        try:
            context = {
                "repo_info": {},
                "file_structure": {},
                "relevant_files": [],
                "dependencies": {},
                "similar_code": [],
                "tech_stack": [],
            }

            # Parse repository URL
            repo_parts = self.github_service.parse_repository_url(repo_url)
            if not repo_parts:
                logger.error(f"Invalid repository URL: {repo_url}")
                return context

            owner, repo_name = repo_parts

            # Get repository metadata
            context["repo_info"] = {
                "owner": owner,
                "repo": repo_name,
                "url": repo_url,
                "branch": branch,
            }

            # Clone repository (shallow clone for speed)
            clone_result = await self.github_service.clone_repository(
                repo_url=repo_url,
                branch=branch,
                shallow=True,
            )

            if not clone_result[0]:
                logger.error(f"Failed to clone repository: {clone_result[1].get('error')}")
                return context

            clone_data = clone_result[1]
            repo_path = clone_data.get("local_path")

            if not repo_path or not os.path.exists(repo_path):
                logger.error("Repository path not found after clone")
                return context

            # Extract file structure
            context["file_structure"] = await self._get_file_structure(repo_path)

            # Detect tech stack
            context["tech_stack"] = await self._detect_tech_stack(repo_path)

            # Extract dependencies
            context["dependencies"] = await self._extract_dependencies(repo_path)

            # Find relevant files based on feature description
            context["relevant_files"] = await self._find_relevant_files(
                repo_path=repo_path,
                feature_description=feature_description,
                tech_stack=context["tech_stack"],
                max_files=max_files,
            )

            # Search for similar code patterns using RAG
            context["similar_code"] = await self._search_similar_code(feature_description)

            logger.info(
                f"Context extraction complete: {len(context['relevant_files'])} files, "
                f"{len(context['tech_stack'])} technologies detected"
            )

            return context

        except Exception as e:
            logger.error(f"Error extracting repo context: {str(e)}", exc_info=True)
            return {
                "repo_info": {},
                "file_structure": {},
                "relevant_files": [],
                "dependencies": {},
                "similar_code": [],
                "tech_stack": [],
                "error": str(e),
            }

    async def _get_file_structure(self, repo_path: str, max_depth: int = 3) -> dict:
        """
        Get directory tree structure.

        Args:
            repo_path: Path to cloned repository
            max_depth: Maximum directory depth to scan

        Returns:
            Nested dictionary representing directory structure
        """
        try:
            def build_tree(path: Path, current_depth: int = 0) -> dict:
                if current_depth >= max_depth:
                    return {"type": "dir", "name": path.name, "truncated": True}

                if path.is_file():
                    return {
                        "type": "file",
                        "name": path.name,
                        "size": path.stat().st_size,
                        "ext": path.suffix,
                    }

                children = []
                try:
                    for item in path.iterdir():
                        # Skip hidden and common ignore patterns
                        if item.name.startswith(".") or item.name in {
                            "node_modules",
                            "__pycache__",
                            "venv",
                            "build",
                            "dist",
                        }:
                            continue

                        children.append(build_tree(item, current_depth + 1))
                except PermissionError:
                    pass

                return {"type": "dir", "name": path.name, "children": children}

            return build_tree(Path(repo_path))

        except Exception as e:
            logger.error(f"Error building file structure: {str(e)}")
            return {}

    async def _detect_tech_stack(self, repo_path: str) -> list[str]:
        """
        Detect technologies used in the repository.

        Args:
            repo_path: Path to cloned repository

        Returns:
            List of detected technologies
        """
        tech_stack = []
        repo_dir = Path(repo_path)

        # Check for common tech indicators
        indicators = {
            "Python": ["requirements.txt", "pyproject.toml", "setup.py"],
            "Node.js": ["package.json"],
            "React": ["package.json"],  # Check package.json content separately
            "TypeScript": ["tsconfig.json"],
            "Docker": ["Dockerfile", "docker-compose.yml"],
            "Go": ["go.mod"],
            "Rust": ["Cargo.toml"],
            "Java": ["pom.xml", "build.gradle"],
            "Ruby": ["Gemfile"],
            "PHP": ["composer.json"],
        }

        for tech, files in indicators.items():
            if any((repo_dir / f).exists() for f in files):
                tech_stack.append(tech)

        # Check package.json for React/Vue/Angular
        package_json_path = repo_dir / "package.json"
        if package_json_path.exists():
            try:
                import json

                with open(package_json_path) as f:
                    package_data = json.load(f)
                    deps = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}

                    if "react" in deps:
                        tech_stack.append("React")
                    if "vue" in deps:
                        tech_stack.append("Vue")
                    if "@angular/core" in deps:
                        tech_stack.append("Angular")
                    if "next" in deps:
                        tech_stack.append("Next.js")
                    if "express" in deps:
                        tech_stack.append("Express")
            except Exception as e:
                logger.debug(f"Could not parse package.json: {e}")

        return list(set(tech_stack))  # Remove duplicates

    async def _extract_dependencies(self, repo_path: str) -> dict:
        """
        Extract package dependencies from the repository.

        Args:
            repo_path: Path to cloned repository

        Returns:
            Dictionary of dependencies by language/framework
        """
        dependencies = {}
        repo_dir = Path(repo_path)

        # Python dependencies
        pyproject_path = repo_dir / "pyproject.toml"
        requirements_path = repo_dir / "requirements.txt"

        if pyproject_path.exists():
            try:
                import tomli

                with open(pyproject_path, "rb") as f:
                    pyproject = tomli.load(f)
                    deps = pyproject.get("project", {}).get("dependencies", [])
                    dependencies["python"] = deps[:20]  # Limit to top 20
            except Exception as e:
                logger.debug(f"Could not parse pyproject.toml: {e}")

        elif requirements_path.exists():
            try:
                with open(requirements_path) as f:
                    deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    dependencies["python"] = deps[:20]  # Limit to top 20
            except Exception as e:
                logger.debug(f"Could not parse requirements.txt: {e}")

        # Node.js dependencies
        package_json_path = repo_dir / "package.json"
        if package_json_path.exists():
            try:
                import json

                with open(package_json_path) as f:
                    package_data = json.load(f)
                    deps = list(package_data.get("dependencies", {}).keys())
                    dependencies["node"] = deps[:20]  # Limit to top 20
            except Exception as e:
                logger.debug(f"Could not parse package.json: {e}")

        return dependencies

    async def _find_relevant_files(
        self,
        repo_path: str,
        feature_description: str,
        tech_stack: list[str],
        max_files: int = 20,
    ) -> list[dict]:
        """
        Find files relevant to the feature description.

        Args:
            repo_path: Path to cloned repository
            feature_description: Feature description to match against
            tech_stack: Detected technologies
            max_files: Maximum files to return

        Returns:
            List of relevant files with metadata
        """
        relevant_files = []
        repo_dir = Path(repo_path)

        # Keywords from feature description
        keywords = set(feature_description.lower().split())

        # File extensions to prioritize based on tech stack
        priority_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".go",
            ".rs",
            ".java",
        }

        def is_relevant(file_path: Path) -> bool:
            # Check if filename contains keywords
            filename_lower = file_path.name.lower()
            if any(keyword in filename_lower for keyword in keywords):
                return True

            # Check if parent directory contains keywords
            parent_lower = file_path.parent.name.lower()
            if any(keyword in parent_lower for keyword in keywords):
                return True

            return False

        try:
            for file_path in repo_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                # Skip excluded directories
                if any(
                    part in {"node_modules", "__pycache__", ".git", "venv", "build", "dist"}
                    for part in file_path.parts
                ):
                    continue

                # Skip files that are too large
                if file_path.stat().st_size > 500_000:  # 500KB limit
                    continue

                # Prioritize by extension
                if file_path.suffix in priority_extensions:
                    if is_relevant(file_path):
                        relative_path = file_path.relative_to(repo_dir)
                        relevant_files.append(
                            {
                                "path": str(relative_path),
                                "name": file_path.name,
                                "size": file_path.stat().st_size,
                                "ext": file_path.suffix,
                            }
                        )

                if len(relevant_files) >= max_files:
                    break

        except Exception as e:
            logger.error(f"Error finding relevant files: {str(e)}")

        # Sort by path depth (prefer files closer to root)
        relevant_files.sort(key=lambda f: f["path"].count("/"))

        return relevant_files[:max_files]

    async def _search_similar_code(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search for similar code patterns using RAG.

        Args:
            query: Search query (feature description)
            max_results: Maximum results to return

        Returns:
            List of similar code examples from knowledge base
        """
        try:
            from ...agents.mcp_client import get_mcp_client

            mcp = await get_mcp_client()

            # Search code examples
            result = await mcp.search_code_examples(query=query, match_count=max_results)

            # Parse JSON result
            import json

            if isinstance(result, str):
                result = json.loads(result)

            if isinstance(result, dict) and result.get("success"):
                return result.get("code_examples", [])

            return []

        except Exception as e:
            logger.debug(f"RAG search not available: {str(e)}")
            return []


# Singleton instance
_github_context_service: GitHubContextService | None = None


async def get_repo_context(
    repo_url: str,
    feature_description: str,
    branch: str = "main",
    github_token: str | None = None,
) -> dict[str, Any]:
    """
    Get repository context for feature planning (convenience function).

    Args:
        repo_url: GitHub repository URL
        feature_description: Feature description
        branch: Branch to analyze
        github_token: Optional GitHub token (uses env var if not provided)

    Returns:
        Dictionary with repository context
    """
    global _github_context_service

    if _github_context_service is None:
        token = github_token or os.getenv("GITHUB_TOKEN")
        _github_context_service = GitHubContextService(token)

    return await _github_context_service.get_repo_context(
        repo_url=repo_url,
        feature_description=feature_description,
        branch=branch,
    )
