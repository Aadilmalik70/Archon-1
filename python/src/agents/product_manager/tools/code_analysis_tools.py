"""
Code analysis tools for AI-PM Orchestrator

Provides functions to analyze codebase structure, search for context,
and retrieve relevant code for task planning
"""

from typing import Any
from pathlib import Path

from ....server.config.logfire_config import get_logger
from ....server.utils import get_supabase_client

logger = get_logger(__name__)


async def analyze_codebase(project_id: str) -> dict[str, Any]:
    """
    Analyze codebase structure for a project

    Args:
        project_id: Project ID to analyze

    Returns:
        Dictionary with codebase analysis including file counts, structure, patterns
    """
    try:
        # Get project details
        supabase = get_supabase_client()
        project_result = supabase.table("archon_projects").select("*").eq(
            "id", project_id
        ).single().execute()

        if not project_result.data:
            logger.warning(f"Project {project_id} not found")
            return {"error": "Project not found"}

        project = project_result.data
        github_repo = project.get("github_repo")

        analysis = {
            "project_id": project_id,
            "project_title": project.get("title"),
            "github_repo": github_repo,
            "has_github_link": bool(github_repo),
            "file_structure": {},
            "patterns_detected": [],
            "tech_stack": _detect_tech_stack(project),
        }

        # If GitHub repo is linked, analyze it
        if github_repo:
            # TODO: Implement GitHub API integration to fetch file structure
            # For now, use project metadata
            analysis["file_structure"] = {
                "backend": ["python/", "src/server/", "src/agents/"],
                "frontend": ["archon-ui-main/", "src/features/"],
                "database": ["migration/"],
            }
            analysis["patterns_detected"] = [
                "Service layer pattern",
                "Vertical slice architecture",
                "PydanticAI agents",
                "TanStack Query",
            ]

        logger.info(f"Analyzed codebase for project {project_id}")
        return analysis

    except Exception as e:
        logger.error(f"Failed to analyze codebase: {str(e)}", exc_info=True)
        return {"error": str(e)}


async def search_code_context(query: str, project_id: str | None = None) -> list[dict]:
    """
    Search knowledge base for relevant code context

    Args:
        query: Search query (e.g., "authentication implementation")
        project_id: Optional project ID to scope search

    Returns:
        List of relevant code snippets and documentation
    """
    supabase = get_supabase_client()

    try:
        # Search knowledge base documents
        # This uses Archon's existing RAG search functionality
        search_query = supabase.table("documents").select(
            "id, content, metadata, source_id"
        )

        # Add basic text search (would be enhanced with vector search in production)
        # For now, use simple ILIKE search
        search_query = search_query.or_(
            f"content.ilike.%{query}%,metadata->>title.ilike.%{query}%"
        )

        # Limit results
        search_query = search_query.limit(10)

        result = search_query.execute()

        snippets = []
        for doc in result.data or []:
            snippets.append({
                "content": doc.get("content", "")[:500],  # First 500 chars
                "source": doc.get("metadata", {}).get("title", "Unknown"),
                "source_id": doc.get("source_id"),
                "relevance": "text_match",  # Would be cosine similarity in production
            })

        logger.info(f"Found {len(snippets)} code snippets for query: {query}")
        return snippets

    except Exception as e:
        logger.error(f"Failed to search code context: {str(e)}", exc_info=True)
        return []


async def get_file_structure(project_id: str) -> dict[str, Any]:
    """
    Get file and directory structure for a project

    Args:
        project_id: Project ID

    Returns:
        Dictionary with file structure organized by category
    """
    try:
        # Get project info
        supabase = get_supabase_client()
        project_result = supabase.table("archon_projects").select("*").eq(
            "id", project_id
        ).single().execute()

        if not project_result.data:
            return {"error": "Project not found"}

        project = project_result.data

        # Get linked knowledge sources
        technical_sources = project.get("technical_sources", [])
        business_sources = project.get("business_sources", [])

        # Query sources for file information
        all_source_ids = technical_sources + business_sources

        structure = {
            "technical_docs": [],
            "business_docs": [],
            "code_examples": [],
            "api_specs": [],
        }

        if all_source_ids:
            sources_result = supabase.table("sources").select("*").in_(
                "id", all_source_ids
            ).execute()

            for source in sources_result.data or []:
                source_info = {
                    "id": source.get("id"),
                    "url": source.get("url"),
                    "type": source.get("source_type"),
                    "page_count": source.get("page_count", 0),
                }

                if source["id"] in technical_sources:
                    structure["technical_docs"].append(source_info)
                else:
                    structure["business_docs"].append(source_info)

        # Get code examples if agentic RAG is enabled
        code_examples = supabase.table("code_examples").select("*").in_(
            "source_id", all_source_ids
        ).limit(20).execute()

        structure["code_examples"] = [
            {
                "language": ex.get("language"),
                "summary": ex.get("summary"),
                "relevance_score": ex.get("relevance_score", 0),
            }
            for ex in code_examples.data or []
        ]

        logger.info(f"Retrieved file structure for project {project_id}")
        return structure

    except Exception as e:
        logger.error(f"Failed to get file structure: {str(e)}", exc_info=True)
        return {"error": str(e)}


def _detect_tech_stack(project: dict) -> list[str]:
    """
    Detect technology stack from project metadata

    Args:
        project: Project object

    Returns:
        List of detected technologies
    """
    stack = []

    # Check project features for hints
    features = project.get("features", [])
    if features:
        # Common patterns
        if any("react" in str(f).lower() for f in features):
            stack.append("React")
        if any("python" in str(f).lower() for f in features):
            stack.append("Python")
        if any("fastapi" in str(f).lower() for f in features):
            stack.append("FastAPI")
        if any("postgres" in str(f).lower() for f in features):
            stack.append("PostgreSQL")

    # Default Archon stack if nothing detected
    if not stack:
        stack = ["React", "TypeScript", "Python", "FastAPI", "Supabase", "PostgreSQL"]

    return stack


async def get_similar_implementations(
    task_description: str, limit: int = 5
) -> list[dict]:
    """
    Find similar past task implementations to learn from

    Args:
        task_description: Description of the task
        limit: Maximum number of similar tasks to return

    Returns:
        List of similar tasks with implementation details
    """
    supabase = get_supabase_client()

    try:
        # Search for completed tasks with similar descriptions
        # In production, this would use embeddings for semantic search
        result = supabase.table("archon_tasks").select(
            "id, title, description, status, execution_metadata"
        ).eq("status", "done").ilike(
            "description", f"%{task_description[:50]}%"
        ).limit(limit).execute()

        similar_tasks = []
        for task in result.data or []:
            similar_tasks.append({
                "title": task.get("title"),
                "description": task.get("description", "")[:200],
                "execution_metadata": task.get("execution_metadata", {}),
                "similarity": "keyword_match",  # Would be cosine similarity
            })

        logger.info(f"Found {len(similar_tasks)} similar implementations")
        return similar_tasks

    except Exception as e:
        logger.error(f"Failed to find similar implementations: {str(e)}", exc_info=True)
        return []


async def extract_dependencies_from_code(
    project_id: str,
) -> dict[str, list[str]]:
    """
    Extract dependency information from project code

    Args:
        project_id: Project to analyze

    Returns:
        Dictionary mapping file types to their dependencies
    """
    # This would integrate with package.json, requirements.txt, etc.
    # For now, return structure based on Archon's known dependencies

    return {
        "python": [
            "fastapi",
            "pydantic-ai",
            "supabase",
            "httpx",
            "bcrypt",
        ],
        "javascript": [
            "react",
            "typescript",
            "@tanstack/react-query",
            "tailwindcss",
        ],
        "database": [
            "postgresql",
            "pgvector",
        ],
    }
