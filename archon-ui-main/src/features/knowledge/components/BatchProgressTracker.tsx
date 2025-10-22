/**
 * Batch Progress Tracker Component
 * Displays per-file upload progress for folder uploads
 */

import { CheckCircle2, FileText, Loader2, XCircle } from "lucide-react";
import type { BatchProgress, FileProcessingResult } from "../types/folder-upload";
import { cn, glassCard } from "../../ui/primitives/styles";

interface BatchProgressTrackerProps {
	progress: BatchProgress;
	className?: string;
}

export const BatchProgressTracker: React.FC<BatchProgressTrackerProps> = ({ progress, className }) => {
	const { totalFiles, processedFiles, fileResults, status, currentFile } = progress;
	const percentComplete = Math.round((processedFiles / totalFiles) * 100);

	const successCount = fileResults.filter((r) => r.status === "success").length;
	const failedCount = fileResults.filter((r) => r.status === "failed").length;
	const skippedCount = fileResults.filter((r) => r.status === "skipped").length;

	return (
		<div className={cn("space-y-3", className)}>
			{/* Overall Progress Bar */}
			<div className={cn("p-4 rounded-xl border", glassCard.blur.md, glassCard.transparency.medium, glassCard.tints.orange.light, "border-orange-400/60")}>
				<div className="space-y-2">
					<div className="flex items-center justify-between text-sm">
						<span className="font-medium text-orange-700 dark:text-orange-300">
							{status === "completed" ? "Upload Complete" : status === "processing" ? "Uploading Files" : "Initializing"}
						</span>
						<span className="text-orange-600 dark:text-orange-400">
							{processedFiles} / {totalFiles}
						</span>
					</div>

					{/* Progress Bar */}
					<div className="h-2 bg-gray-200/50 dark:bg-gray-700/50 rounded-full overflow-hidden">
						<div
							className="h-full bg-gradient-to-r from-orange-400 to-orange-500 transition-all duration-300 ease-out"
							style={{ width: `${percentComplete}%` }}
						/>
					</div>

					{/* Current File */}
					{currentFile && status === "processing" && (
						<div className="flex items-center gap-2 text-xs text-orange-600 dark:text-orange-400 mt-2">
							<Loader2 className="w-3 h-3 animate-spin" />
							<span className="truncate">{currentFile}</span>
						</div>
					)}
				</div>
			</div>

			{/* Summary Stats */}
			{fileResults.length > 0 && (
				<div className="grid grid-cols-3 gap-2">
					<div className={cn("p-2 rounded-lg text-center", glassCard.blur.sm, "bg-green-500/10 border border-green-400/30")}>
						<div className="text-lg font-bold text-green-600 dark:text-green-400">{successCount}</div>
						<div className="text-xs text-green-600 dark:text-green-400">Success</div>
					</div>
					<div className={cn("p-2 rounded-lg text-center", glassCard.blur.sm, "bg-red-500/10 border border-red-400/30")}>
						<div className="text-lg font-bold text-red-600 dark:text-red-400">{failedCount}</div>
						<div className="text-xs text-red-600 dark:text-red-400">Failed</div>
					</div>
					<div className={cn("p-2 rounded-lg text-center", glassCard.blur.sm, "bg-gray-500/10 border border-gray-400/30")}>
						<div className="text-lg font-bold text-gray-600 dark:text-gray-400">{skippedCount}</div>
						<div className="text-xs text-gray-600 dark:text-gray-400">Skipped</div>
					</div>
				</div>
			)}

			{/* File Details List */}
			{fileResults.length > 0 && (
				<div className={cn("max-h-[200px] overflow-y-auto space-y-1 p-3 rounded-lg", glassCard.blur.sm, glassCard.transparency.high, "border border-gray-300/40 dark:border-gray-600/40")}>
					{fileResults.map((result, index) => (
						<FileResultItem key={`${result.filename}-${index}`} result={result} />
					))}
				</div>
			)}
		</div>
	);
};

interface FileResultItemProps {
	result: FileProcessingResult;
}

const FileResultItem: React.FC<FileResultItemProps> = ({ result }) => {
	const getStatusIcon = () => {
		switch (result.status) {
			case "success":
				return <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />;
			case "failed":
				return <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />;
			case "skipped":
				return <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />;
			default:
				return <Loader2 className="w-4 h-4 text-orange-500 animate-spin flex-shrink-0" />;
		}
	};

	const getStatusColor = () => {
		switch (result.status) {
			case "success":
				return "text-green-600 dark:text-green-400";
			case "failed":
				return "text-red-600 dark:text-red-400";
			case "skipped":
				return "text-gray-500 dark:text-gray-400";
			default:
				return "text-orange-600 dark:text-orange-400";
		}
	};

	return (
		<div className="flex items-start gap-2 py-1">
			{getStatusIcon()}
			<div className="flex-1 min-w-0">
				<div className="flex items-center justify-between gap-2">
					<span className={cn("text-sm truncate", getStatusColor())}>{result.filename}</span>
					{result.status === "success" && result.chunksStored > 0 && (
						<span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
							{result.chunksStored} chunks
						</span>
					)}
				</div>
				{result.error && <div className="text-xs text-red-500 mt-0.5">{result.error}</div>}
			</div>
		</div>
	);
};
