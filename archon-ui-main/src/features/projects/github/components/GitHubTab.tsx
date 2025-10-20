/**
 * GitHub Tab Component
 *
 * Displays and manages GitHub repositories linked to a project.
 */

import { useState } from "react";
import { Button } from "@/features/ui/primitives/button";
import { Card } from "@/features/ui/primitives/card";
import { Badge } from "@/components/ui/Badge";
import { useProjectGitHubSources, useUnlinkGitHubRepository } from "../hooks/useGitHubQueries";
import { GitHubLinkModal } from "./GitHubLinkModal";
import { useOperationProgress } from "@/features/progress/hooks/useProgressQueries";
import type { GitHubSource } from "../types";
import { useToast } from "@/features/shared/hooks";

interface GitHubTabProps {
  projectId: string;
}

export function GitHubTab({ projectId }: GitHubTabProps) {
  const { showToast } = useToast();
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [activeProgressId, setActiveProgressId] = useState<string | null>(null);

  const { data: sources = [], isLoading } = useProjectGitHubSources(projectId);
  const unlinkMutation = useUnlinkGitHubRepository(projectId);
  const { data: progressData } = useOperationProgress(activeProgressId || null);

  const handleUnlink = async (source: GitHubSource) => {
    if (!confirm(`Are you sure you want to unlink ${source.source_display_name}?`)) {
      return;
    }

    try {
      await unlinkMutation.mutateAsync(source.source_id);
      showToast(`${source.source_display_name} has been unlinked from the project`, "success");
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail?.error || error.message || "An error occurred";
      showToast(`Failed to unlink repository: ${errorMessage}`, "error");
    }
  };

  const handleLinkSuccess = (progressId: string, sourceId: string) => {
    setActiveProgressId(progressId);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoString: string) => {
    return new Date(isoString).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading GitHub repositories...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Linked GitHub Repositories</h3>
          <p className="text-sm text-muted-foreground">
            Repositories linked to this project for context and RAG search
          </p>
        </div>
        <Button onClick={() => setIsLinkModalOpen(true)}>Link Repository</Button>
      </div>

      {/* Active Progress Indicator */}
      {activeProgressId && progressData && progressData.status !== "completed" && (
        <Card className="p-4 border-blue-500/50 bg-blue-500/5">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Indexing repository...</span>
              <span className="text-sm text-muted-foreground">{progressData.progress?.toFixed(0)}%</span>
            </div>
            <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${progressData.progress}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">{progressData.message}</p>
          </div>
        </Card>
      )}

      {/* Repository List */}
      {sources.length === 0 ? (
        <Card className="p-12 text-center">
          <div className="space-y-4">
            <div className="text-muted-foreground">No GitHub repositories linked yet</div>
            <Button onClick={() => setIsLinkModalOpen(true)}>Link Your First Repository</Button>
          </div>
        </Card>
      ) : (
        <div className="grid gap-4">
          {sources.map((source) => (
            <Card key={source.source_id} className="p-6">
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h4 className="text-lg font-semibold">{source.source_display_name}</h4>
                    <a
                      href={source.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-500 hover:underline"
                    >
                      {source.source_url}
                    </a>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleUnlink(source)}
                    disabled={unlinkMutation.isPending}
                  >
                    Unlink
                  </Button>
                </div>

                {/* Metadata */}
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" color="gray">
                    Branch: {source.metadata.branch}
                  </Badge>
                  <Badge variant="outline" color="blue">
                    {source.metadata.file_count} files
                  </Badge>
                  <Badge variant="outline" color="purple">
                    {formatFileSize(source.metadata.total_size)}
                  </Badge>
                  <Badge variant="solid" color="orange">
                    {source.metadata.knowledge_type}
                  </Badge>
                </div>

                {/* Tags */}
                {source.metadata.tags && source.metadata.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {source.metadata.tags.map((tag) => (
                      <Badge key={tag} variant="solid" color="blue">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}

                {/* Footer */}
                <div className="text-xs text-muted-foreground">
                  Indexed on {formatDate(source.metadata.indexed_at)}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Link Modal */}
      <GitHubLinkModal
        isOpen={isLinkModalOpen}
        onClose={() => setIsLinkModalOpen(false)}
        projectId={projectId}
        onSuccess={handleLinkSuccess}
      />
    </div>
  );
}
