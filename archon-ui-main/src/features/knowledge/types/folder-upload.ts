/**
 * Folder Upload Types
 *
 * Type definitions for batch folder upload functionality.
 */

export interface FilePreview {
	file: File;
	relativePath: string;
	supported: boolean;
	selected: boolean;
	error?: string;
}

export interface FolderUploadMetadata {
	knowledge_type: string;
	tags?: string[];
	extract_code_examples: boolean;
}

export interface FileProcessingResult {
	filename: string;
	relativePath: string;
	status: "success" | "failed" | "skipped";
	sourceId?: string;
	chunksStored: number;
	codeExamplesStored: number;
	error?: string;
}

export interface BatchProgress {
	totalFiles: number;
	processedFiles: number;
	fileResults: FileProcessingResult[];
	currentFile?: string;
	status: "initializing" | "processing" | "completed" | "failed" | "cancelled";
	progress: number;
	log: string;
}

export interface FolderUploadResponse {
	success: boolean;
	progressId: string;
	message: string;
	totalFiles: number;
}

export interface FolderStructure {
	name: string;
	path: string;
	type: "file" | "directory";
	children?: FolderStructure[];
	fileCount?: number;
}
