/**
 * Folder Upload Tab Component
 * Handles folder selection and batch upload of documents
 */

import { FolderOpen, Loader2, Upload } from "lucide-react";
import { useId, useState, useMemo } from "react";
import { useToast } from "@/features/shared/hooks/useToast";
import { Button, Label } from "../../ui/primitives";
import { cn, glassCard } from "../../ui/primitives/styles";
import { useFolderUpload } from "../hooks/useKnowledgeQueries";
import type { FolderStructure, FolderUploadMetadata } from "../types/folder-upload";
import { KnowledgeTypeSelector } from "./KnowledgeTypeSelector";
import { TagInput } from "./TagInput";
import { FileTreePreview } from "./FileTreePreview";
import { BatchProgressTracker } from "./BatchProgressTracker";
import { useActiveOperations } from "../../progress/hooks";
import type { BatchProgress } from "../types/folder-upload";

interface FolderUploadTabProps {
	onSuccess: () => void;
}

export const FolderUploadTab: React.FC<FolderUploadTabProps> = ({ onSuccess }) => {
	const folderId = useId();
	const { showToast } = useToast();
	const folderUploadMutation = useFolderUpload();
	const { data: activeOpsData } = useActiveOperations(true);

	const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
	const [uploadType, setUploadType] = useState<"technical" | "business">("technical");
	const [uploadTags, setUploadTags] = useState<string[]>([]);
	const [currentProgressId, setCurrentProgressId] = useState<string | null>(null);
	const [batchProgress, setBatchProgress] = useState<{
		current: number;
		total: number;
		isUploading: boolean;
	} | null>(null);

	// Use all selected files (no filtering)
	const supportedFiles = useMemo(() => {
		return selectedFiles;
	}, [selectedFiles]);

	// Batch upload configuration
	const MAX_FILES_PER_BATCH = 500;
	const needsBatching = selectedFiles.length > MAX_FILES_PER_BATCH;
	const totalBatches = needsBatching ? Math.ceil(selectedFiles.length / MAX_FILES_PER_BATCH) : 1;

	// Build folder structure for preview
	const folderStructure = useMemo((): FolderStructure | null => {
		if (selectedFiles.length === 0) return null;

		const root: FolderStructure = {
			name: "Root",
			path: "",
			type: "directory",
			children: [],
			fileCount: selectedFiles.length,
		};

		const dirMap = new Map<string, FolderStructure>();
		dirMap.set("", root);

		for (const file of selectedFiles) {
			const relativePath = (file as any).webkitRelativePath || file.name;
			const parts = relativePath.split("/");
			const fileName = parts[parts.length - 1];
			const dirParts = parts.slice(0, -1);

			let currentPath = "";
			let currentDir = root;

			// Create directory structure
			for (let i = 0; i < dirParts.length; i++) {
				const dirName = dirParts[i];
				const nextPath = currentPath ? `${currentPath}/${dirName}` : dirName;

				if (!dirMap.has(nextPath)) {
					const newDir: FolderStructure = {
						name: dirName,
						path: nextPath,
						type: "directory",
						children: [],
						fileCount: 0,
					};
					currentDir.children = currentDir.children || [];
					currentDir.children.push(newDir);
					dirMap.set(nextPath, newDir);
				}

				currentDir = dirMap.get(nextPath)!;
				currentDir.fileCount = (currentDir.fileCount || 0) + 1;
				currentPath = nextPath;
			}

			// Add file
			currentDir.children = currentDir.children || [];
			currentDir.children.push({
				name: fileName,
				path: relativePath,
				type: "file",
			});
		}

		return root;
	}, [selectedFiles]);

	// Check if there's an active folder upload for current progressId
	const activeProgress = useMemo((): BatchProgress | null => {
		if (!currentProgressId || !activeOpsData?.operations) return null;

		const operation = activeOpsData.operations.find(
			(op) => op.operation_id === currentProgressId && op.operation_type === "folder_upload",
		);

		if (!operation) return null;

		return {
			totalFiles: (operation as any).total_files || 0,
			processedFiles: (operation as any).processed_files || 0,
			fileResults: (operation as any).file_results || [],
			currentFile: (operation as any).current_file,
			status: operation.status as "initializing" | "processing" | "completed" | "failed" | "cancelled",
			progress: operation.progress || 0,
			log: operation.message || "",
		};
	}, [currentProgressId, activeOpsData]);

	const handleFolderSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
		const files = Array.from(event.target.files || []);
		setSelectedFiles(files);
		setCurrentProgressId(null);
	};

	const resetForm = () => {
		setSelectedFiles([]);
		setUploadType("technical");
		setUploadTags([]);
		setCurrentProgressId(null);
		setBatchProgress(null);
		// Reset file input
		const input = document.getElementById(folderId) as HTMLInputElement;
		if (input) input.value = "";
	};

	const handleUpload = async () => {
		if (supportedFiles.length === 0) {
			showToast("No files selected", "error");
			return;
		}

		try {
			const metadata: FolderUploadMetadata = {
				knowledge_type: uploadType,
				tags: uploadTags.length > 0 ? uploadTags : undefined,
				extract_code_examples: true,
			};

			// Split files into batches
			const batches: File[][] = [];
			for (let i = 0; i < supportedFiles.length; i += MAX_FILES_PER_BATCH) {
				batches.push(supportedFiles.slice(i, i + MAX_FILES_PER_BATCH));
			}

			setBatchProgress({
				current: 0,
				total: batches.length,
				isUploading: true,
			});

			// Upload batches sequentially
			for (let i = 0; i < batches.length; i++) {
				setBatchProgress({
					current: i + 1,
					total: batches.length,
					isUploading: true,
				});

				showToast(
					`Uploading batch ${i + 1} of ${batches.length} (${batches[i].length} files)...`,
					"info"
				);

				const response = await folderUploadMutation.mutateAsync({
					files: batches[i],
					metadata,
				});

				if (response?.progressId && i === batches.length - 1) {
					// Only track progress for the last batch
					setCurrentProgressId(response.progressId);
				}
			}

			setBatchProgress(null);
			showToast(
				`All ${batches.length} batches uploaded successfully! Total: ${supportedFiles.length} files.`,
				"success"
			);
		} catch (error) {
			setBatchProgress(null);
			const message = error instanceof Error ? error.message : "Failed to upload folder";
			showToast(message, "error");
		}
	};

	const isProcessing = folderUploadMutation.isPending || batchProgress?.isUploading || false;
	const hasActiveProgress = activeProgress !== null;

	return (
		<div className="space-y-6 mt-6">
			{/* Folder Input Section */}
			<div className="space-y-3">
				<Label htmlFor={folderId} className="text-sm font-medium text-gray-900 dark:text-white/90">
					Select Folder
				</Label>

				{/* Custom Folder Upload Area */}
				<div className="relative">
					<input
						id={folderId}
						type="file"
						// @ts-ignore - webkitdirectory is not in TypeScript definitions yet
						webkitdirectory=""
						multiple
						onChange={handleFolderSelect}
						disabled={isProcessing}
						className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed z-10"
					/>
					<div
						className={cn(
							"relative h-20 rounded-xl border-2 border-dashed transition-all duration-200",
							"flex flex-col items-center justify-center gap-2 text-center p-4",
							glassCard.blur.md,
							selectedFiles.length > 0 ? glassCard.tints.orange.light : glassCard.transparency.medium,
							selectedFiles.length > 0 ? "border-orange-400/70" : "border-gray-300/60 dark:border-gray-600/60",
							selectedFiles.length === 0 && "hover:border-orange-400/50",
							isProcessing && "opacity-50 cursor-not-allowed",
						)}
					>
						<FolderOpen
							className={cn("w-6 h-6", selectedFiles.length > 0 ? "text-orange-500" : "text-gray-400 dark:text-gray-500")}
						/>
						<div className="text-sm">
							{selectedFiles.length > 0 ? (
								<div className="space-y-1">
									<p className="font-medium text-orange-700 dark:text-orange-400">
										{selectedFiles.length} files selected
									</p>
									<p className="text-xs text-orange-600 dark:text-orange-400">
										Ready to upload
									</p>
								</div>
							) : (
								<div className="space-y-1">
									<p className="font-medium text-gray-700 dark:text-gray-300">Click to select folder</p>
									<p className="text-xs text-gray-500 dark:text-gray-400">
										All text-based files accepted (code, docs, configs, etc.)
									</p>
								</div>
							)}
						</div>
					</div>
				</div>
			</div>

			{/* Info about batch uploading */}
			{needsBatching && (
				<div className={cn(
					"p-3 rounded-lg border",
					glassCard.blur.sm,
					"bg-blue-500/10 border-blue-400/50"
				)}>
					<div className="flex items-start gap-2">
						<span className="text-blue-500 font-bold text-lg">ℹ️</span>
						<div className="flex-1">
							<p className="text-sm font-medium text-blue-700 dark:text-blue-400">
								Batch upload mode
							</p>
							<p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
								{selectedFiles.length} files will be uploaded in {totalBatches} batches of up to {MAX_FILES_PER_BATCH} files each.
								Each batch will be processed sequentially.
							</p>
						</div>
					</div>
				</div>
			)}

			{/* Folder Preview */}
			{folderStructure && folderStructure.children && folderStructure.children.length > 0 && (
				<FileTreePreview structure={folderStructure} totalFiles={selectedFiles.length} />
			)}

			{/* Progress Tracker */}
			{hasActiveProgress && activeProgress && <BatchProgressTracker progress={activeProgress} />}

			{/* Knowledge Type Selector */}
			<KnowledgeTypeSelector value={uploadType} onValueChange={setUploadType} disabled={isProcessing} />

			{/* Tags Input */}
			<TagInput
				tags={uploadTags}
				onTagsChange={setUploadTags}
				disabled={isProcessing}
				placeholder="Add tags like 'documentation', 'guide', 'reference'..."
			/>

			{/* Upload Button */}
			<div className="flex gap-2">
				<Button
					onClick={handleUpload}
					disabled={isProcessing || supportedFiles.length === 0}
					className={[
						"flex-1 bg-gradient-to-r from-orange-500 to-orange-600",
						"hover:from-orange-600 hover:to-orange-700",
						"backdrop-blur-md border border-orange-400/50",
						"shadow-[0_0_20px_rgba(249,115,22,0.25)] hover:shadow-[0_0_30px_rgba(249,115,22,0.35)]",
						"transition-all duration-200",
					].join(" ")}
				>
					{batchProgress?.isUploading ? (
						<>
							<Loader2 className="w-4 h-4 mr-2 animate-spin" />
							Batch {batchProgress.current} of {batchProgress.total}...
						</>
					) : folderUploadMutation.isPending ? (
						<>
							<Loader2 className="w-4 h-4 mr-2 animate-spin" />
							Starting Upload...
						</>
					) : needsBatching ? (
						<>
							<Upload className="w-4 h-4 mr-2" />
							Upload {supportedFiles.length} Files ({totalBatches} Batches)
						</>
					) : (
						<>
							<Upload className="w-4 h-4 mr-2" />
							Upload {supportedFiles.length} Files
						</>
					)}
				</Button>

				{selectedFiles.length > 0 && (
					<Button
						onClick={resetForm}
						disabled={isProcessing}
						variant="outline"
						className="border-gray-300/60 dark:border-gray-600/60"
					>
						Clear
					</Button>
				)}
			</div>
		</div>
	);
};
