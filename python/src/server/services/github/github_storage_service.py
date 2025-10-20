"""
GitHub Storage Service

Handles storage and indexing of GitHub repository files with hybrid approach:
- Preserves file hierarchy in metadata
- Chunks files for embeddings
- Extracts code examples separately
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client
from ..storage.storage_services import DocumentStorageService
from ..storage.code_storage_service import add_code_examples_to_supabase

logger = get_logger(__name__)


class GitHubStorageService:
    """Service for storing and indexing GitHub repository files"""

    def __init__(self, supabase_client=None):
        """Initialize with optional supabase client"""
        self.supabase_client = supabase_client or get_supabase_client()
        self.doc_storage = DocumentStorageService(self.supabase_client)

    async def index_repository(
        self,
        source_id: str,
        repo_info: dict[str, Any],
        files: list[dict[str, Any]],
        knowledge_type: str = "documentation",
        tags: list[str] | None = None,
        extract_code_examples: bool = True,
        progress_callback: Any | None = None,
        cancellation_check: Any | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Index a GitHub repository with hybrid storage approach.

        Args:
            source_id: Unique source identifier
            repo_info: Repository metadata (owner, repo_name, branch, etc.)
            files: List of files to index
            knowledge_type: Type of knowledge
            tags: Optional tags
            extract_code_examples: Whether to extract code examples
            progress_callback: Optional progress callback
            cancellation_check: Optional cancellation check function

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            if progress_callback:
                await progress_callback("Initializing repository indexing...", 70)

            # Create source record
            source_data = {
                "source_id": source_id,
                "source_url": f"https://github.com/{repo_info['owner']}/{repo_info['repo_name']}",
                "source_display_name": f"{repo_info['owner']}/{repo_info['repo_name']}",
                "metadata": {
                    "source_type": "github_repo",
                    "owner": repo_info["owner"],
                    "repo_name": repo_info["repo_name"],
                    "branch": repo_info.get("branch", "main"),
                    "clone_path": repo_info.get("clone_path"),
                    "file_count": len(files),
                    "total_size": repo_info.get("total_size", 0),
                    "tags": tags or [],
                    "knowledge_type": knowledge_type,
                    "indexed_at": datetime.now().isoformat(),
                    # Store file tree structure
                    "file_tree": self._build_file_tree(files)
                }
            }

            # Insert source record
            self.supabase_client.table("archon_sources").insert(source_data).execute()
            logger.info(f"Created source record for GitHub repo: {source_id}")

            # Process files in batches
            total_chunks = 0
            total_code_examples = 0
            batch_size = 10  # Process 10 files at a time

            for i in range(0, len(files), batch_size):
                # Check for cancellation
                if cancellation_check:
                    cancellation_check()

                batch = files[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(files) + batch_size - 1) // batch_size

                if progress_callback:
                    progress_pct = 70 + int((i / len(files)) * 25)
                    await progress_callback(
                        f"Processing batch {batch_num}/{total_batches}",
                        progress_pct,
                        {"currentBatch": batch_num, "totalBatches": total_batches}
                    )

                # Process batch
                batch_results = await self._process_file_batch(
                    batch,
                    source_id,
                    knowledge_type,
                    extract_code_examples
                )

                total_chunks += batch_results["chunks_stored"]
                total_code_examples += batch_results["code_examples_stored"]

            if progress_callback:
                await progress_callback("Repository indexed successfully", 95)

            logger.info(
                f"Repository indexed: {source_id} | "
                f"Files: {len(files)} | Chunks: {total_chunks} | Code: {total_code_examples}"
            )

            return True, {
                "source_id": source_id,
                "files_processed": len(files),
                "chunks_stored": total_chunks,
                "code_examples_stored": total_code_examples,
                "repository": f"{repo_info['owner']}/{repo_info['repo_name']}",
                "branch": repo_info.get("branch", "main")
            }

        except Exception as e:
            logger.error(f"Failed to index repository: {str(e)}", exc_info=True)
            return False, {"error": f"Failed to index repository: {str(e)}"}

    async def _process_file_batch(
        self,
        files: list[dict[str, Any]],
        source_id: str,
        knowledge_type: str,
        extract_code: bool
    ) -> dict[str, Any]:
        """
        Process a batch of files for indexing.

        Args:
            files: List of file info dicts
            source_id: Source identifier
            knowledge_type: Type of knowledge
            extract_code: Whether to extract code examples

        Returns:
            Dict with chunks_stored and code_examples_stored counts
        """
        total_chunks = 0
        total_code = 0

        for file_info in files:
            try:
                # Read file content
                file_path = Path(file_info["absolute_path"])
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    logger.warning(f"Failed to read file {file_info['path']}: {str(e)}")
                    continue

                if not content.strip():
                    logger.debug(f"Skipping empty file: {file_info['path']}")
                    continue

                # Store file content with chunking
                file_url = f"github://{source_id}/{file_info['path']}"

                # Chunk file content
                chunks = await self.doc_storage.smart_chunk_text_async(
                    content,
                    chunk_size=3000  # Smaller chunks for code
                )

                if not chunks:
                    continue

                # Prepare chunk data
                urls = []
                chunk_numbers = []
                contents = []
                metadatas = []
                url_to_full_document = {}

                for i, chunk in enumerate(chunks):
                    urls.append(file_url)
                    chunk_numbers.append(i)
                    contents.append(chunk)

                    # Extract metadata for chunk
                    metadata = self.doc_storage.extract_metadata(
                        chunk,
                        {
                            "chunk_index": i,
                            "url": file_url,
                            "source": source_id,
                            "source_id": source_id,
                            "knowledge_type": knowledge_type,
                            "source_type": "github_repo",
                            "file_path": file_info["path"],
                            "file_extension": file_info["extension"],
                            "file_size": file_info["size"]
                        }
                    )
                    metadatas.append(metadata)

                # Store full document for contextual retrieval
                url_to_full_document[file_url] = content

                # Store chunks
                from ..storage.document_storage_service import add_documents_to_supabase

                store_result = await add_documents_to_supabase(
                    client=self.supabase_client,
                    urls=urls,
                    chunk_numbers=chunk_numbers,
                    contents=contents,
                    metadatas=metadatas,
                    url_to_full_document=url_to_full_document
                )

                if store_result:
                    total_chunks += store_result.get("chunks_stored", 0)
                    logger.debug(f"Stored {len(chunks)} chunks for {file_info['path']}")

                # TODO: Add code example extraction back later
                # For now, skip code extraction to simplify initial implementation

            except Exception as e:
                logger.error(f"Error processing file {file_info.get('path', 'unknown')}: {str(e)}")
                continue

        return {
            "chunks_stored": total_chunks,
            "code_examples_stored": total_code
        }

    def _build_file_tree(self, files: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Build a hierarchical file tree structure from flat file list.

        Args:
            files: List of file info dicts

        Returns:
            Nested dict representing file tree
        """
        tree: dict[str, Any] = {}

        for file_info in files:
            path_parts = file_info["path"].split("/")
            current = tree

            # Navigate/create tree structure
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    # Leaf node (file)
                    current[part] = {
                        "type": "file",
                        "size": file_info["size"],
                        "extension": file_info["extension"]
                    }
                else:
                    # Directory node
                    if part not in current:
                        current[part] = {"type": "dir", "children": {}}
                    elif current[part].get("type") != "dir":
                        # Convert to dir if it was a file (edge case)
                        current[part] = {"type": "dir", "children": {}}

                    current = current[part].get("children", {})

        return tree

    async def unlink_repository(self, source_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Unlink and delete a GitHub repository source.

        Args:
            source_id: Source identifier

        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Use source management service for deletion
            from ..source_management_service import SourceManagementService

            source_service = SourceManagementService(self.supabase_client)
            success, result = source_service.delete_source(source_id)

            if success:
                logger.info(f"Unlinked GitHub repository: {source_id}")
                return True, {
                    "message": f"Successfully unlinked repository {source_id}",
                    **result
                }
            else:
                return False, result

        except Exception as e:
            logger.error(f"Failed to unlink repository: {str(e)}", exc_info=True)
            return False, {"error": f"Failed to unlink repository: {str(e)}"}

    async def get_repository_stats(self, source_id: str) -> tuple[bool, dict[str, Any]]:
        """
        Get statistics for a linked GitHub repository.

        Args:
            source_id: Source identifier

        Returns:
            Tuple of (success, stats_dict)
        """
        try:
            # Get source record
            source_result = self.supabase_client.table("archon_sources").select("*").eq("source_id", source_id).execute()

            if not source_result.data:
                return False, {"error": "Repository not found"}

            source = source_result.data[0]

            # Get chunk count
            chunks_result = (
                self.supabase_client.table("archon_crawled_pages")
                .select("id", count="exact", head=True)
                .eq("source_id", source_id)
                .execute()
            )
            chunk_count = chunks_result.count if hasattr(chunks_result, "count") else 0

            # Get code examples count
            code_result = (
                self.supabase_client.table("archon_code_examples")
                .select("id", count="exact", head=True)
                .eq("source_id", source_id)
                .execute()
            )
            code_count = code_result.count if hasattr(code_result, "count") else 0

            metadata = source.get("metadata", {})

            return True, {
                "source_id": source_id,
                "repository": f"{metadata.get('owner')}/{metadata.get('repo_name')}",
                "branch": metadata.get("branch", "main"),
                "file_count": metadata.get("file_count", 0),
                "total_size": metadata.get("total_size", 0),
                "chunk_count": chunk_count,
                "code_examples_count": code_count,
                "indexed_at": metadata.get("indexed_at"),
                "tags": metadata.get("tags", [])
            }

        except Exception as e:
            logger.error(f"Failed to get repository stats: {str(e)}", exc_info=True)
            return False, {"error": f"Failed to get repository stats: {str(e)}"}
