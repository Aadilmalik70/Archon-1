# Folder Upload for Knowledge Base

## Goal

**Feature Goal**: Enable users to upload entire folders of documents to the knowledge base in a single operation, preserving folder structure and providing comprehensive progress tracking for batch processing.

**Deliverable**:
- Backend API endpoint accepting multiple files from folder uploads
- Frontend UI with folder selection and file preview
- Batch progress tracking system with per-file status
- Drag-and-drop folder support

**Success Definition**:
- Users can select a folder containing supported document types (.pdf, .docx, .txt, .md, .html, .htm)
- System processes all valid files, skips unsupported files with warnings
- Progress tracking shows overall batch progress + individual file status
- All files are chunked, embedded, and stored with metadata preserving folder structure
- Partial success scenarios handled gracefully (some files succeed, some fail)

## User Persona

**Target User**: Knowledge base administrators, documentation managers, developers organizing technical documentation

**Use Case**: Bulk import of existing documentation folders (API docs, guides, tutorials) into knowledge base

**User Journey**:
1. User clicks "Add Knowledge" → "Upload Folder" tab
2. Selects folder from file system (or drags folder into upload area)
3. Previews file list showing folder structure, file types, total size
4. Reviews/removes unwanted files from selection
5. Clicks "Upload Folder" with shared metadata (tags, knowledge type)
6. Tracks progress showing overall percentage + per-file status
7. Reviews completion summary showing successful uploads + any failures

**Pain Points Addressed**:
- Eliminates tedious one-by-one file uploads
- Preserves organizational structure of documentation
- Provides clear feedback on batch operation progress
- Handles mixed valid/invalid files gracefully

## Why

- **Business Value**: Dramatically reduces time to populate knowledge base from hours/days to minutes
- **User Experience**: Intuitive folder selection aligns with user's mental model of file organization
- **Integration**: Builds on existing single-file upload infrastructure, reuses document processing pipeline
- **Scalability**: Enables rapid knowledge base growth, especially for teams migrating from other systems
- **Problems Solved**:
  - For documentation teams: Bulk import of existing docs without manual file-by-file upload
  - For developers: Quick addition of entire API documentation folders
  - For admins: Efficient knowledge base initialization and maintenance

## What

### User-Visible Behavior

**Upload Dialog**:
- New "Upload Folder" tab alongside existing "Crawl Website" and "Upload Document" tabs
- Folder selection button using native OS folder picker
- File tree preview showing:
  - Folder structure with expandable directories
  - Individual file names with icons by type
  - File sizes and total folder size
  - Validation status (supported/unsupported file types)
  - Checkbox selection to include/exclude files
- Shared metadata inputs (tags, knowledge type) applying to all files
- Clear indication of how many files will be uploaded

**Drag-and-Drop**:
- Existing upload area supports dropping folders
- Visual feedback when dragging folder over drop zone
- Automatic file gathering from dropped folder structure
- Same preview UI as folder selection

**Progress Tracking**:
- Overall progress bar (0-100%) for entire batch
- File status list showing:
  - Current file being processed (highlighted)
  - Completed files (green checkmark)
  - Failed files (red X with error message)
  - Pending files (gray queue indicator)
- Summary stats: "Processing 15/42 files" with estimated time
- Cancellation button to stop batch operation

**Completion**:
- Success toast showing "42 files uploaded successfully"
- Partial success: "38/42 files uploaded - 4 failed" with expandable error details
- Knowledge base list automatically updates with new items
- Each file becomes separate knowledge item with folder path in metadata

### Technical Requirements

**Backend**:
- New endpoint `POST /api/documents/upload-folder` accepting `List[UploadFile]`
- File type validation (server-side, skip unsupported with warning)
- Path traversal protection for folder structures
- Single progress_id tracking all files in batch
- Aggregated progress reporting: overall percentage + per-file status
- Continue-on-error processing: one file failure doesn't stop batch
- Individual file success/failure tracking with error details

**Frontend**:
- Browser `webkitdirectory` attribute for folder selection
- DataTransfer API handling for drag-and-drop folders
- Recursive file gathering from folder structure
- FormData construction with multiple files + relative paths
- File tree preview component with checkbox selection
- Extended progress UI showing batch + individual file status
- Optimistic updates with partial success handling

**Data Model**:
- Preserve relative file paths in document metadata
- Store folder structure for future browsing features
- Track batch upload operations with file-level granularity
- Individual knowledge items per file (not one item per folder)

### Success Criteria

- [ ] User can select folder using native folder picker
- [ ] File tree preview displays before upload with accurate file count and sizes
- [ ] Server validates file types and processes only supported formats
- [ ] Unsupported files are skipped with clear warnings, not errors
- [ ] All supported files are processed individually (chunked, embedded, stored)
- [ ] Progress tracking shows both overall batch progress and per-file status
- [ ] Cancellation stops processing immediately and reports partial results
- [ ] Partial success scenarios display clearly (X successful, Y failed)
- [ ] Failed files show specific error messages for debugging
- [ ] Knowledge base updates optimistically and reconciles with server state
- [ ] Folder structure is preserved in document metadata
- [ ] Drag-and-drop folder upload works identically to folder selection
- [ ] Large folders (100+ files) process efficiently without browser/server timeout
- [ ] Memory usage stays reasonable for large batches (streaming processing)

## All Needed Context

### Context Completeness Check

_This PRP provides everything needed for someone unfamiliar with the codebase to implement folder upload successfully, including:_
- _Exact file paths to pattern files for services, components, and hooks_
- _Specific browser API documentation with implementation examples_
- _Backend multi-file upload patterns with FastAPI best practices_
- _Existing progress tracking integration points_
- _File type validation approach matching current implementation_

### Documentation & References

```yaml
# Browser APIs - MUST READ for frontend implementation
- url: https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory
  why: Core API for folder selection, understand webkitRelativePath property
  critical: Must include 'multiple' attribute for browser compatibility fallback
  example: |
    <input type="file" webkitdirectory multiple />
    // Files have .webkitRelativePath preserving folder structure

- url: https://developer.mozilla.org/en-US/docs/Web/API/DataTransferItem/webkitGetAsEntry
  why: Required for drag-and-drop folder support
  critical: Recursive traversal needed for nested folders
  example: |
    Use FileSystemDirectoryEntry.createReader() for folder contents

# FastAPI Patterns - MUST READ for backend implementation
- url: https://fastapi.tiangolo.com/tutorial/request-files/#multiple-file-uploads
  why: Pattern for List[UploadFile] endpoint definition
  critical: Each file processed independently, use BackgroundTasks for async
  example: |
    @router.post("/upload-folder")
    async def upload_folder(files: List[UploadFile] = File(...)):

# Existing Patterns - Follow these exactly
- file: python/src/server/api_routes/knowledge_api.py
  why: Single file upload endpoint pattern (lines 894-973)
  pattern: UploadFile handling, FormData parsing, progress tracker initialization
  gotcha: Must read file content immediately (line 933) to avoid closed file issues
  critical: Progress tracker initialized BEFORE background task starts

- file: python/src/server/services/storage/storage_services.py
  why: DocumentStorageService.upload_document method (lines 20-233)
  pattern: Document processing flow, progress callbacks, code extraction
  gotcha: Progress callbacks use percentage mapping (line 1008-1012)
  critical: Cancellation checks prevent zombie background tasks

- file: archon-ui-main/src/features/knowledge/components/AddKnowledgeDialog.tsx
  why: Current upload UI structure (lines 216-301)
  pattern: File input, form state, mutation hooks, toast notifications
  gotcha: Reset form after successful upload (line 117)
  critical: Show toast immediately, don't wait for background completion

- file: archon-ui-main/src/features/knowledge/hooks/useKnowledgeQueries.ts
  why: useUploadDocument mutation hook (lines 303-476)
  pattern: Optimistic updates, progress tracking, error handling
  gotcha: Temporary progress ID replaced with server ID (lines 413-451)
  critical: Rollback optimistic updates on error (lines 460-474)

- file: python/src/server/utils/document_processing.py
  why: File type detection and text extraction (lines 158-222)
  pattern: Content type checking, format support
  gotcha: HTML files need cleaning (line 192), PDFs use multiple libraries
  critical: Supported formats: .pdf, .docx, .doc, .html, .htm, .txt, .md, .markdown, .rst

- file: python/src/server/utils/progress/progress_tracker.py
  why: Progress tracking implementation (search for ProgressTracker class)
  pattern: start(), update(), complete(), error() methods
  gotcha: Progress must only increase, never decrease
  critical: Use separate progress_id for batch operations
```

### Current Codebase Tree (relevant sections)

```
archon-ui-main/src/features/knowledge/
├── components/
│   ├── AddKnowledgeDialog.tsx          # Upload UI - add folder tab here
│   ├── KnowledgeCard.tsx                # List item display
│   └── ...
├── hooks/
│   ├── useKnowledgeQueries.ts           # Add useUploadFolder mutation
│   └── ...
├── services/
│   └── knowledgeService.ts              # Add uploadFolder method
└── types/
    └── index.ts                          # Add folder upload types

python/src/server/
├── api_routes/
│   └── knowledge_api.py                 # Add /api/documents/upload-folder endpoint
├── services/
│   └── storage/
│       └── storage_services.py          # Extend DocumentStorageService for batch
└── utils/
    ├── document_processing.py           # Reuse existing extraction logic
    └── progress/
        └── progress_tracker.py          # Extend for batch progress tracking
```

### Desired Codebase Tree (new files to add)

```
archon-ui-main/src/features/knowledge/
├── components/
│   ├── FolderUploadTab.tsx              # NEW: Folder selection and preview UI
│   ├── FileTreePreview.tsx              # NEW: Hierarchical file list display
│   └── BatchProgressTracker.tsx         # NEW: Multi-file progress visualization
└── types/
    └── folder-upload.ts                  # NEW: Folder upload TypeScript types

python/src/server/
└── models/
    └── folder_upload_models.py           # NEW: Pydantic models for batch upload

No new service files needed - extend existing DocumentStorageService
No new progress files needed - extend existing ProgressTracker
```

### Known Gotchas & Library Quirks

```python
# CRITICAL: FastAPI UploadFile behavior
# UploadFile.file is a SpooledTemporaryFile - files >1MB written to disk
# MUST read file content immediately in endpoint before background task
# File handles close after endpoint returns - content becomes inaccessible

# GOTCHA: Progress tracking for batch operations
# Progress percentage must ONLY INCREASE, never decrease
# Use ProgressMapper to ensure monotonic progress
# Example: File 1: 0-50%, File 2: 50-75%, File 3: 75-100%

# CRITICAL: Browser webkitdirectory compatibility
# Property is non-standard but widely supported (Chrome, Firefox, Edge 14+, Safari 11.1+)
# MUST include 'multiple' attribute for fallback support
# Files may arrive in any order - use webkitRelativePath for sorting

# GOTCHA: FormData file upload with multiple files
# Cannot use single 'files' field for all files (overwrites)
# Append each file with unique field name: files[0], files[1], etc.
# OR append to same field name multiple times: files, files, files (FastAPI handles as List)

# CRITICAL: Async file processing memory management
# Don't load all files into memory simultaneously
# Process files sequentially or with concurrency limit (max 5 concurrent)
# Use asyncio.Semaphore for controlled concurrency

# GOTCHA: Document processing text extraction
# extract_text_from_document may raise ValueError for unsupported formats
# DON'T fail entire batch - catch exception, log error, continue to next file
# Preserve error details in progress tracking for user feedback

# CRITICAL: Path traversal security
# Validate file paths don't contain '..' or absolute paths
# webkitRelativePath is relative but could be manipulated
# Use os.path.normpath and check result starts with expected folder name

# GOTCHA: Progress callback cancellation
# cancellation_check callable should raise asyncio.CancelledError
# Check cancellation BEFORE starting each file, not just at batch start
# Cleanup partial results if cancellation occurs mid-batch
```

## Implementation Blueprint

### Data Models and Structure

```python
# python/src/server/models/folder_upload_models.py

from pydantic import BaseModel, Field
from typing import List, Optional

class FolderUploadRequest(BaseModel):
    """Request model for folder upload endpoint."""
    knowledge_type: str = Field(default="technical", description="Type of knowledge")
    tags: Optional[List[str]] = Field(default=None, description="Tags to apply to all files")
    extract_code_examples: bool = Field(default=True, description="Extract code examples from documents")

    class Config:
        schema_extra = {
            "example": {
                "knowledge_type": "technical",
                "tags": ["api-docs", "reference"],
                "extract_code_examples": True
            }
        }

class FileProcessingResult(BaseModel):
    """Result of processing a single file in batch."""
    filename: str
    relative_path: str
    status: str  # "success", "failed", "skipped"
    source_id: Optional[str] = None  # Only present for successful uploads
    chunks_stored: int = 0
    code_examples_stored: int = 0
    error: Optional[str] = None

class FolderUploadResponse(BaseModel):
    """Response model for folder upload operation."""
    success: bool
    progress_id: str = Field(alias="progressId")
    message: str
    total_files: int = Field(alias="totalFiles")

    class Config:
        populate_by_name = True

# Frontend TypeScript types
# archon-ui-main/src/features/knowledge/types/folder-upload.ts

export interface FilePreview {
  file: File;
  relativePath: string;
  supported: boolean;
  selected: boolean;
  error?: string;
}

export interface FolderUploadMetadata {
  knowledge_type: "technical" | "business";
  tags?: string[];
  extract_code_examples?: boolean;
}

export interface BatchProgress {
  total_files: number;
  processed_files: number;
  successful_files: number;
  failed_files: number;
  current_file?: string;
  file_results: FileProcessingResult[];
  overall_progress: number; // 0-100
}
```

### Implementation Tasks (ordered by dependencies)

```yaml
# BACKEND IMPLEMENTATION

Task 1: CREATE python/src/server/models/folder_upload_models.py
  - IMPLEMENT: FolderUploadRequest, FileProcessingResult, FolderUploadResponse models
  - FOLLOW pattern: python/src/server/models/progress_models.py (Pydantic BaseModel structure)
  - NAMING: CamelCase classes, snake_case fields, use Field() with aliases for camelCase API
  - VALIDATION: tags must be Optional[List[str]], knowledge_type enum validation
  - PLACEMENT: Domain models in python/src/server/models/

Task 2: EXTEND python/src/server/api_routes/knowledge_api.py
  - IMPLEMENT: New endpoint POST /api/documents/upload-folder
  - SIGNATURE: async def upload_folder_batch(files: List[UploadFile] = File(...), metadata: str = Form(...))
  - FOLLOW pattern: Existing /api/documents/upload endpoint (lines 894-973)
  - CRITICAL: Read ALL file contents immediately before background task (line 933 pattern)
  - METADATA: Parse JSON string from Form data (same as single upload, line 920-930)
  - PROGRESS: Initialize ProgressTracker with type="folder_upload" before background task
  - BACKGROUND: Use _perform_folder_upload_with_progress similar to _perform_upload_with_progress
  - PLACEMENT: Add after existing /api/documents/upload endpoint (~line 974)

Task 3: CREATE _perform_folder_upload_with_progress helper function
  - LOCATION: python/src/server/api_routes/knowledge_api.py (after _perform_upload_with_progress)
  - SIGNATURE: async def _perform_folder_upload_with_progress(progress_id, file_contents_list, metadata_dict, tracker)
  - LOOP: Iterate through file_contents_list sequentially (not parallel)
  - PROGRESS MAPPING: Map each file to percentage range (file N: N/total*100 to (N+1)/total*100)
  - ERROR HANDLING: Try/except per file, log errors, continue to next file (don't fail batch)
  - VALIDATION: Skip unsupported file types, update progress with "skipped" status
  - CANCELLATION: Check cancellation before processing each file
  - FOLLOW pattern: _perform_upload_with_progress (lines 975-1093) for individual file processing
  - REUSE: DocumentStorageService.upload_document for each file
  - AGGREGATION: Collect FileProcessingResult for each file, return batch summary

Task 4: EXTEND python/src/server/utils/progress/progress_tracker.py
  - MODIFY: ProgressTracker.update method to accept file_results parameter
  - NEW FIELD: file_results: List[dict] in progress state
  - BACKWARD COMPATIBLE: Make file_results optional, default to empty list
  - PATTERN: Follow existing update() method signature, add to state dict
  - CRITICAL: Ensure progress only increases (use max(current, new) if needed)

# FRONTEND IMPLEMENTATION

Task 5: CREATE archon-ui-main/src/features/knowledge/types/folder-upload.ts
  - IMPLEMENT: FilePreview, FolderUploadMetadata, BatchProgress interfaces
  - FOLLOW pattern: archon-ui-main/src/features/knowledge/types/index.ts (existing type definitions)
  - NAMING: PascalCase interfaces, camelCase properties
  - ALIGNMENT: Match backend FolderUploadResponse field names (use camelCase)
  - PLACEMENT: Feature-specific types in types/ subdirectory

Task 6: EXTEND archon-ui-main/src/features/knowledge/services/knowledgeService.ts
  - IMPLEMENT: uploadFolder method
  - SIGNATURE: async uploadFolder(files: File[], metadata: FolderUploadMetadata)
  - FORMDATA: Append each file to FormData with field name "files" (repeated)
  - FORMDATA: Append metadata as JSON string with field name "metadata"
  - FORMDATA: Preserve webkitRelativePath in custom field per file for folder structure
  - FOLLOW pattern: Existing uploadDocument method for FormData construction
  - API CALL: POST to /api/documents/upload-folder with FormData
  - RETURN: Promise<{ progressId: string; message: string; totalFiles: number }>
  - PLACEMENT: Add method to existing knowledgeService object

Task 7: CREATE archon-ui-main/src/features/knowledge/hooks/useFolderUpload.ts
  - IMPLEMENT: useFolderUpload mutation hook
  - FOLLOW pattern: archon-ui-main/src/features/knowledge/hooks/useKnowledgeQueries.ts (useUploadDocument, lines 303-476)
  - OPTIMISTIC: Create optimistic knowledge items for entire batch (all files)
  - PROGRESS: Add optimistic progress operation for batch
  - ERROR HANDLING: Rollback all optimistic items on error
  - SUCCESS: Replace temporary progress IDs with server response
  - QUERY INVALIDATION: Invalidate knowledgeKeys.summariesPrefix() and progressKeys.active()
  - RETURN: Mutation object with mutateAsync for component usage

Task 8: CREATE archon-ui-main/src/features/knowledge/components/FileTreePreview.tsx
  - PURPOSE: Display folder structure with file selection
  - PROPS: files: FilePreview[], onSelectionChange: (files: FilePreview[]) => void
  - DISPLAY: Hierarchical tree view with folders and files
  - INTERACTION: Checkboxes for file selection, expand/collapse folders
  - VALIDATION: Show unsupported files with warning icon and disabled checkbox
  - STATS: Display total files, selected files, total size
  - FOLLOW pattern: archon-ui-main/src/features/ui/primitives/ (Radix UI components)
  - STYLING: Use glassCard styling from src/features/ui/primitives/styles
  - ACCESSIBILITY: Proper ARIA labels, keyboard navigation
  - PLACEMENT: archon-ui-main/src/features/knowledge/components/

Task 9: CREATE archon-ui-main/src/features/knowledge/components/BatchProgressTracker.tsx
  - PURPOSE: Display batch upload progress with per-file status
  - PROPS: progressId: string
  - POLLING: Use useProgressDetail(progressId) hook for smart polling
  - DISPLAY: Overall progress bar + file list with status icons
  - FILE STATUS: Pending (gray), Processing (blue spinner), Success (green check), Failed (red X)
  - ERROR DETAILS: Expandable error messages for failed files
  - FOLLOW pattern: archon-ui-main/src/features/progress/components/ (existing progress components)
  - STYLING: Tron-inspired glassmorphism, consistent with existing progress UI
  - PLACEMENT: archon-ui-main/src/features/knowledge/components/

Task 10: CREATE archon-ui-main/src/features/knowledge/components/FolderUploadTab.tsx
  - PURPOSE: Folder selection and upload UI
  - SECTIONS: Folder input, file preview, metadata inputs (tags, knowledge type)
  - INPUT: <input type="file" webkitdirectory multiple /> with custom styling
  - FILE GATHERING: Read files from FileList, create FilePreview objects
  - VALIDATION: Check file types against supported formats, mark unsupported
  - PREVIEW: Render FileTreePreview component with gathered files
  - METADATA: Reuse KnowledgeTypeSelector and TagInput components
  - SUBMIT: Call useFolderUpload mutation with selected files and metadata
  - FOLLOW pattern: AddKnowledgeDialog.tsx Upload tab (lines 216-301)
  - STYLING: Match existing tab styling with purple gradient for folder upload
  - PLACEMENT: archon-ui-main/src/features/knowledge/components/

Task 11: MODIFY archon-ui-main/src/features/knowledge/components/AddKnowledgeDialog.tsx
  - ADD: New "Upload Folder" tab to existing Tabs component
  - IMPORT: FolderUploadTab component
  - TABS: ["Crawl Website", "Upload Document", "Upload Folder"]
  - FOLLOW pattern: Existing tab structure (lines 136-148)
  - ICON: Use Folder icon from lucide-react for tab
  - COLOR: Purple theme for folder upload tab (consistent with file upload)
  - PLACEMENT: Add after "Upload Document" TabsContent section
  - CRITICAL: Pass onSuccess, onCrawlStarted props to FolderUploadTab

# ENHANCEMENT TASKS (after core functionality)

Task 12: ADD drag-and-drop folder support
  - LOCATION: archon-ui-main/src/features/knowledge/components/FolderUploadTab.tsx
  - IMPLEMENT: onDrop, onDragOver, onDragLeave handlers
  - API: Use DataTransferItem.webkitGetAsEntry() for folder detection
  - RECURSION: Traverse FileSystemDirectoryEntry to gather all files
  - FOLLOW pattern: Existing file input drag-and-drop UI styling (AddKnowledgeDialog lines 224-265)
  - CRITICAL: Maintain webkitRelativePath equivalent when gathering files manually
  - FALLBACK: If folder drop not supported, show message to use folder button

Task 13: OPTIMIZE progress polling for large batches
  - LOCATION: BatchProgressTracker component
  - STRATEGY: Use smart polling with adaptive intervals based on batch size
  - SMALL BATCH (<10 files): 2 second polling interval
  - MEDIUM BATCH (10-50 files): 5 second polling interval
  - LARGE BATCH (>50 files): 10 second polling interval
  - FOLLOW pattern: archon-ui-main/src/features/shared/hooks/useSmartPolling.ts
```

### Implementation Patterns & Key Details

```typescript
// Frontend: Folder file gathering from webkitdirectory input
function gatherFilesFromInput(fileList: FileList): FilePreview[] {
  const files: FilePreview[] = [];
  const supportedExtensions = ['.pdf', '.docx', '.doc', '.txt', '.md', '.markdown', '.html', '.htm', '.rst'];

  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i];
    const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    const supported = supportedExtensions.includes(extension);

    files.push({
      file,
      relativePath: (file as any).webkitRelativePath || file.name,
      supported,
      selected: supported, // Auto-select supported files
      error: supported ? undefined : `Unsupported file type: ${extension}`
    });
  }

  return files;
}

// Frontend: FormData construction for batch upload
async function uploadFolder(files: File[], metadata: FolderUploadMetadata) {
  const formData = new FormData();

  // Append each file - FastAPI will receive as List[UploadFile]
  files.forEach(file => {
    formData.append('files', file);
  });

  // Append metadata as JSON string (FormData only supports strings)
  formData.append('metadata', JSON.stringify(metadata));

  // CRITICAL: Don't set Content-Type header - browser sets multipart/form-data automatically
  const response = await apiClient.post<FolderUploadResponse>('/documents/upload-folder', formData);
  return response;
}

// Backend: Batch upload endpoint pattern
@router.post("/documents/upload-folder")
async def upload_folder_batch(
    files: List[UploadFile] = File(...),
    metadata: str = Form(...)
):
    """Upload multiple documents from a folder with progress tracking."""

    # Parse metadata JSON
    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid metadata JSON")

    # CRITICAL: Read ALL file contents immediately
    # UploadFile.file closes after endpoint returns
    file_contents_list = []
    for upload_file in files:
        content = await upload_file.read()
        file_contents_list.append({
            'content': content,
            'filename': upload_file.filename,
            'content_type': upload_file.content_type,
            'relative_path': upload_file.filename  # Extract from filename if needed
        })

    # Generate progress ID
    progress_id = str(uuid.uuid4())

    # Initialize progress tracker
    tracker = ProgressTracker(progress_id, operation_type="folder_upload")
    await tracker.start({
        "total_files": len(files),
        "processed_files": 0,
        "status": "initializing",
        "progress": 0,
        "log": f"Starting folder upload with {len(files)} files"
    })

    # Start background task
    asyncio.create_task(_perform_folder_upload_with_progress(
        progress_id, file_contents_list, metadata_dict, tracker
    ))

    return FolderUploadResponse(
        success=True,
        progress_id=progress_id,
        message="Folder upload started",
        total_files=len(files)
    ).model_dump(by_alias=True)

// Backend: Batch processing with error isolation
async def _perform_folder_upload_with_progress(
    progress_id: str,
    file_contents_list: List[dict],
    metadata_dict: dict,
    tracker: ProgressTracker
):
    """Process folder upload with per-file error isolation."""

    total_files = len(file_contents_list)
    file_results = []
    successful = 0
    failed = 0

    for idx, file_data in enumerate(file_contents_list):
        try:
            # Update progress for current file
            current_progress = int((idx / total_files) * 100)
            await tracker.update(
                status="processing",
                progress=current_progress,
                processed_files=idx,
                current_file=file_data['filename'],
                log=f"Processing {file_data['filename']} ({idx+1}/{total_files})"
            )

            # VALIDATION: Check file type
            filename = file_data['filename']
            if not is_supported_file_type(filename):
                file_results.append({
                    'filename': filename,
                    'status': 'skipped',
                    'error': f'Unsupported file type'
                })
                continue

            # CRITICAL: Extract text (may raise ValueError)
            try:
                extracted_text = extract_text_from_document(
                    file_data['content'],
                    filename,
                    file_data['content_type']
                )
            except ValueError as e:
                # User error (unsupported format or empty file)
                file_results.append({
                    'filename': filename,
                    'status': 'failed',
                    'error': str(e)
                })
                failed += 1
                continue

            # PROCESS: Use existing DocumentStorageService
            doc_service = DocumentStorageService(get_supabase_client())
            source_id = f"file_{filename.replace(' ', '_')}_{uuid.uuid4().hex[:8]}"

            # Create per-file progress callback (maps to overall range)
            async def file_progress_callback(message: str, percentage: int):
                # Map file's 0-100% to this file's overall range
                file_start = int((idx / total_files) * 100)
                file_end = int(((idx + 1) / total_files) * 100)
                mapped = file_start + int((percentage / 100) * (file_end - file_start))

                await tracker.update(
                    progress=mapped,
                    log=message
                )

            success, result = await doc_service.upload_document(
                file_content=extracted_text,
                filename=filename,
                source_id=source_id,
                knowledge_type=metadata_dict.get('knowledge_type', 'technical'),
                tags=metadata_dict.get('tags', []),
                extract_code_examples=metadata_dict.get('extract_code_examples', True),
                progress_callback=file_progress_callback
            )

            if success:
                file_results.append({
                    'filename': filename,
                    'relative_path': file_data.get('relative_path', filename),
                    'status': 'success',
                    'source_id': source_id,
                    'chunks_stored': result.get('chunks_stored', 0),
                    'code_examples_stored': result.get('code_examples_stored', 0)
                })
                successful += 1
            else:
                file_results.append({
                    'filename': filename,
                    'status': 'failed',
                    'error': result.get('error', 'Unknown error')
                })
                failed += 1

        except Exception as e:
            # System error - log with full context
            logger.error(f"Unexpected error processing {file_data['filename']}: {e}", exc_info=True)
            file_results.append({
                'filename': file_data['filename'],
                'status': 'failed',
                'error': f"System error: {str(e)}"
            })
            failed += 1

    # Complete with summary
    await tracker.complete({
        "log": f"Folder upload complete: {successful} successful, {failed} failed",
        "total_files": total_files,
        "processed_files": total_files,
        "successful_files": successful,
        "failed_files": failed,
        "file_results": file_results
    })

// CRITICAL: Path traversal validation
def validate_file_path(relative_path: str, expected_prefix: str = "") -> bool:
    """Validate file path doesn't escape expected directory."""
    import os

    # Normalize path (resolve .., ., etc.)
    normalized = os.path.normpath(relative_path)

    # Check for absolute path
    if os.path.isabs(normalized):
        return False

    # Check for path traversal
    if normalized.startswith('..'):
        return False

    # If expected prefix provided, ensure path starts with it
    if expected_prefix and not normalized.startswith(expected_prefix):
        return False

    return True
```

### Integration Points

```yaml
DATABASE:
  - no changes: Uses existing sources and archon_crawled_pages tables
  - metadata: Preserve folder structure in metadata.relative_path field
  - indexing: Existing indexes sufficient for batch operations

CONFIG:
  - no changes: Reuses existing upload configuration
  - optional: Add MAX_FOLDER_FILES env var to limit batch size (default: 1000)
  - optional: Add MAX_CONCURRENT_FILE_PROCESSING env var (default: 1 for sequential)

API:
  - add to: python/src/server/api_routes/knowledge_api.py
  - endpoint: POST /api/documents/upload-folder
  - response: FolderUploadResponse with progressId for tracking

PROGRESS:
  - extend: python/src/server/utils/progress/progress_tracker.py
  - new field: file_results array in progress state
  - backward compatible: Existing progress polls work unchanged
```

## Validation Loop

### Level 1: Syntax & Style (Immediate Feedback)

```bash
# Backend validation
cd python
uv run ruff check src/server/api_routes/knowledge_api.py src/server/models/folder_upload_models.py --fix
uv run mypy src/server/api_routes/knowledge_api.py src/server/models/folder_upload_models.py
uv run ruff format src/server/

# Frontend validation
cd archon-ui-main
npm run biome:fix  # Auto-fix features directory
npm run lint  # ESLint for legacy code if needed
npx tsc --noEmit  # Type checking

# Expected: Zero errors before proceeding
```

### Level 2: Unit Tests (Component Validation)

```bash
# Backend tests - create new test file
cd python

# Test folder upload endpoint
uv run pytest tests/server/api_routes/test_knowledge_api.py::test_upload_folder_batch -v

# Test batch processing logic
uv run pytest tests/server/api_routes/test_knowledge_api.py::test_folder_upload_with_mixed_files -v

# Test error isolation
uv run pytest tests/server/api_routes/test_knowledge_api.py::test_folder_upload_continues_on_error -v

# Frontend tests - create new test files
cd archon-ui-main

# Test folder upload mutation
npm run test src/features/knowledge/hooks/useFolderUpload.test.ts

# Test file tree preview component
npm run test src/features/knowledge/components/FileTreePreview.test.tsx

# Expected: All tests pass with >80% coverage
```

### Level 3: Integration Testing (System Validation)

```bash
# Start services
cd python
uv run python -m src.server.main &
BACKEND_PID=$!
sleep 5  # Allow startup

# Frontend dev server
cd archon-ui-main
npm run dev &
FRONTEND_PID=$!
sleep 3

# Test folder upload endpoint with actual files
# Create test folder structure
mkdir -p /tmp/test-folder/docs
echo "Test document 1" > /tmp/test-folder/test1.txt
echo "Test document 2" > /tmp/test-folder/docs/test2.md

# Upload via curl (simulating FormData)
curl -X POST http://localhost:8181/api/documents/upload-folder \
  -F "files=@/tmp/test-folder/test1.txt" \
  -F "files=@/tmp/test-folder/docs/test2.md" \
  -F 'metadata={"knowledge_type":"technical","tags":["test"]}' \
  | jq .

# Verify progress tracking
PROGRESS_ID=$(curl -s http://localhost:8181/api/documents/upload-folder -F "files=@/tmp/test-folder/test1.txt" -F 'metadata={}' | jq -r '.progressId')
sleep 2
curl http://localhost:8181/api/progress/$PROGRESS_ID | jq .

# Verify knowledge items created
curl http://localhost:8181/api/knowledge-items | jq '.items[] | select(.metadata.source_type=="file")'

# Cleanup
kill $BACKEND_PID $FRONTEND_PID
rm -rf /tmp/test-folder

# Expected: 200 OK responses, progress tracking works, knowledge items created
```

### Level 4: Manual Testing (User Experience Validation)

```bash
# Manual test scenarios in browser at http://localhost:3737

# Test 1: Folder selection
# - Click "Add Knowledge" → "Upload Folder" tab
# - Click folder selection button
# - Select test folder with mixed file types
# - Verify: File tree preview shows all files with correct support status

# Test 2: File filtering
# - In file preview, uncheck some files
# - Click "Upload Folder"
# - Verify: Only selected files are uploaded

# Test 3: Progress tracking
# - Upload folder with 10+ files
# - Watch progress UI update in real-time
# - Verify: Overall progress bar + per-file status indicators
# - Verify: Current file being processed is highlighted

# Test 4: Partial success
# - Create folder with mix of supported (.txt) and unsupported (.xyz) files
# - Upload folder
# - Verify: Supported files succeed, unsupported files show as skipped/failed
# - Verify: Completion toast shows "X successful, Y failed"

# Test 5: Large folder
# - Create folder with 50+ small text files
# - Upload folder
# - Verify: No browser timeout, progress updates smoothly
# - Verify: All files processed without memory issues

# Test 6: Drag-and-drop (if implemented)
# - Drag folder from file explorer onto upload area
# - Verify: Files gathered correctly with folder structure
# - Verify: Same behavior as folder selection button

# Test 7: Cancellation
# - Start uploading large folder
# - Click cancel button mid-upload
# - Verify: Processing stops immediately
# - Verify: Partial results reported correctly

# Expected: All scenarios work smoothly, no errors, good UX
```

## Final Validation Checklist

### Technical Validation

- [ ] Level 1 completed: No linting, type, or formatting errors
- [ ] Level 2 completed: All unit tests pass with >80% coverage
- [ ] Level 3 completed: Integration tests pass, endpoints work correctly
- [ ] Level 4 completed: Manual testing scenarios all successful

### Feature Validation

- [ ] User can select folder using native OS folder picker
- [ ] File tree preview displays accurately before upload
- [ ] Unsupported files are skipped with clear warnings
- [ ] All supported files process successfully
- [ ] Progress tracking shows batch + per-file status correctly
- [ ] Cancellation works and reports partial results
- [ ] Partial success scenarios display clearly
- [ ] Knowledge base updates with all uploaded files
- [ ] Folder structure preserved in document metadata
- [ ] Large folders (100+ files) process without timeout

### Code Quality Validation

- [ ] Follows existing patterns from AddKnowledgeDialog and upload endpoint
- [ ] File placement matches desired codebase tree
- [ ] Reuses DocumentStorageService without duplication
- [ ] Error handling isolates failures per file
- [ ] Progress tracking monotonically increases
- [ ] Path traversal validation prevents security issues
- [ ] Memory usage reasonable for large batches

### Documentation & Deployment

- [ ] Code is self-documenting with clear function/variable names
- [ ] Progress logs provide actionable information
- [ ] Error messages are user-friendly and specific
- [ ] No new environment variables required (optional ones documented)

---

## Anti-Patterns to Avoid

- ❌ Don't fail entire batch on single file error - isolate failures
- ❌ Don't process files in parallel without concurrency limit - causes memory exhaustion
- ❌ Don't skip file type validation on server - client-side only is insufficient
- ❌ Don't allow progress percentage to decrease - breaks user expectation
- ❌ Don't load all file contents into memory - process sequentially
- ❌ Don't forget to read UploadFile content before background task - file handles close
- ❌ Don't ignore webkitRelativePath - folder structure is valuable metadata
- ❌ Don't create new document storage logic - reuse DocumentStorageService
- ❌ Don't skip cancellation checks during batch - zombie processes waste resources
- ❌ Don't use synchronous file I/O in async context - blocks event loop
