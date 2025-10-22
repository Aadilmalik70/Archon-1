/**
 * File Tree Preview Component
 * Displays folder structure before upload
 */

import { ChevronDown, ChevronRight, File, Folder, FolderOpen } from "lucide-react";
import { useState } from "react";
import type { FolderStructure } from "../types/folder-upload";
import { cn, glassCard } from "../../ui/primitives/styles";

interface FileTreePreviewProps {
	structure: FolderStructure;
	totalFiles: number;
}

export const FileTreePreview: React.FC<FileTreePreviewProps> = ({ structure, totalFiles }) => {
	return (
		<div
			className={cn(
				"p-4 rounded-xl border",
				glassCard.blur.md,
				glassCard.transparency.medium,
				"border-gray-300/60 dark:border-gray-600/60",
				"max-h-[300px] overflow-y-auto",
			)}
		>
			<div className="space-y-2">
				<div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200/30 dark:border-gray-700/30">
					<span className="text-sm font-medium text-gray-700 dark:text-gray-300">Folder Preview</span>
					<span className="text-xs text-gray-500 dark:text-gray-400">
						{totalFiles} files total
					</span>
				</div>
				<TreeNode node={structure} level={0} />
			</div>
		</div>
	);
};

interface TreeNodeProps {
	node: FolderStructure;
	level: number;
}

const TreeNode: React.FC<TreeNodeProps> = ({ node, level }) => {
	const [expanded, setExpanded] = useState(level < 2);
	const isDirectory = node.type === "directory";
	const hasChildren = node.children && node.children.length > 0;

	const paddingLeft = `${level * 1.5}rem`;

	if (!isDirectory) {
		return (
			<div className="flex items-center gap-2 py-1 text-sm" style={{ paddingLeft }}>
				<File className="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0" />
				<span className="text-gray-600 dark:text-gray-400 truncate">{node.name}</span>
			</div>
		);
	}

	return (
		<div>
			<button
				type="button"
				onClick={() => setExpanded(!expanded)}
				className={cn(
					"flex items-center gap-2 py-1 text-sm w-full hover:bg-gray-100/50 dark:hover:bg-gray-800/50 rounded transition-colors",
				)}
				style={{ paddingLeft }}
			>
				{hasChildren ? (
					expanded ? (
						<ChevronDown className="w-4 h-4 text-gray-500 flex-shrink-0" />
					) : (
						<ChevronRight className="w-4 h-4 text-gray-500 flex-shrink-0" />
					)
				) : (
					<div className="w-4" />
				)}
				{expanded ? (
					<FolderOpen className="w-4 h-4 text-orange-500 flex-shrink-0" />
				) : (
					<Folder className="w-4 h-4 text-orange-400 flex-shrink-0" />
				)}
				<span className="text-gray-700 dark:text-gray-300 font-medium truncate">{node.name}</span>
				{node.fileCount !== undefined && (
					<span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">({node.fileCount})</span>
				)}
			</button>

			{expanded && hasChildren && (
				<div className="mt-1">
					{node.children?.map((child, index) => <TreeNode key={`${child.path}-${index}`} node={child} level={level + 1} />)}
				</div>
			)}
		</div>
	);
};
