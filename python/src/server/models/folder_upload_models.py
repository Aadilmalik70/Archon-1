"""
Folder Upload Models

Pydantic models for batch document upload operations.
"""

from pydantic import BaseModel, Field


class FolderUploadRequest(BaseModel):
    """Request model for folder upload endpoint."""

    knowledge_type: str = Field(default="technical", description="Type of knowledge")
    tags: list[str] | None = Field(default=None, description="Tags to apply to all files")
    extract_code_examples: bool = Field(
        default=True, description="Extract code examples from documents"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "knowledge_type": "technical",
                "tags": ["api-docs", "reference"],
                "extract_code_examples": True,
            }
        }


class FileProcessingResult(BaseModel):
    """Result of processing a single file in batch."""

    filename: str
    relative_path: str
    status: str  # "success", "failed", "skipped"
    source_id: str | None = None  # Only present for successful uploads
    chunks_stored: int = 0
    code_examples_stored: int = 0
    error: str | None = None


class FolderUploadResponse(BaseModel):
    """Response model for folder upload operation."""

    success: bool
    progress_id: str = Field(alias="progressId")
    message: str
    total_files: int = Field(alias="totalFiles")

    class Config:
        populate_by_name = True
