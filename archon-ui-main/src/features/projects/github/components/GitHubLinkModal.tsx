/**
 * GitHub Link Modal
 *
 * Modal for linking GitHub repositories to projects.
 */

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/features/ui/primitives/dialog";
import { Button } from "@/features/ui/primitives/button";
import { Input } from "@/features/ui/primitives/input";
import { Label } from "@/features/ui/primitives/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/features/ui/primitives/select";
import { Badge } from "@/components/ui/Badge";

import { useLinkGitHubRepository, useRepositoryBranches } from "../hooks/useGitHubQueries";
import type { LinkGitHubRepoRequest } from "../types";
import { useToast } from "@/features/shared/hooks";

interface GitHubLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onSuccess?: (progressId: string, sourceId: string) => void;
}

export function GitHubLinkModal({ isOpen, onClose, projectId, onSuccess }: GitHubLinkModalProps) {
  const { showToast } = useToast();
  const linkMutation = useLinkGitHubRepository(projectId);

  // Form state
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [knowledgeType, setKnowledgeType] = useState("documentation");
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [includePatterns, setIncludePatterns] = useState<string[]>([]);
  const [excludePatterns, setExcludePatterns] = useState<string[]>([]);
  const [extractCode, setExtractCode] = useState(false);

  // Parse owner and repo from URL
  const parseRepoUrl = (url: string) => {
    try {
      const match = url.match(/github\.com\/([^/]+)\/([^/]+)/);
      if (match) {
        return { owner: match[1], repo: match[2].replace(/\.git$/, "") };
      }
    } catch (e) {
      // Invalid URL
    }
    return null;
  };

  const parsed = parseRepoUrl(repoUrl);
  const { data: branchesData } = useRepositoryBranches(parsed?.owner, parsed?.repo);

  // Update branch when default branch is loaded
  useEffect(() => {
    if (branchesData?.default_branch) {
      setBranch(branchesData.default_branch);
    }
  }, [branchesData]);

  const handleAddTag = () => {
    if (tagInput && !tags.includes(tagInput)) {
      setTags([...tags, tagInput]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!repoUrl) {
      showToast("Please enter a GitHub repository URL", "error");
      return;
    }

    const request: LinkGitHubRepoRequest = {
      repo_url: repoUrl,
      branch: branch || "main",
      knowledge_type: knowledgeType,
      tags: tags.length > 0 ? tags : undefined,
      include_patterns: includePatterns.length > 0 ? includePatterns : undefined,
      exclude_patterns: excludePatterns.length > 0 ? excludePatterns : undefined,
      extract_code_examples: extractCode,
    };

    try {
      const result = await linkMutation.mutateAsync(request);
      showToast("Repository linking started. This may take several minutes.", "success");
      onSuccess?.(result.progressId, result.sourceId);
      onClose();
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail?.error || error.message || "An error occurred";
      showToast(`Failed to link repository: ${errorMessage}`, "error");
    }
  };

  const handleClose = (open: boolean) => {
    // Only allow closing if not pending and user wants to close (open = false)
    if (!open && !linkMutation.isPending) {
      onClose();
      // Reset form
      setRepoUrl("");
      setBranch("main");
      setKnowledgeType("documentation");
      setTags([]);
      setTagInput("");
      setIncludePatterns([]);
      setExcludePatterns([]);
      setExtractCode(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Link GitHub Repository</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Repository URL */}
          <div className="space-y-2">
            <Label htmlFor="repo-url">Repository URL *</Label>
            <Input
              id="repo-url"
              type="url"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              required
            />
            {parsed && (
              <p className="text-sm text-muted-foreground">
                {parsed.owner}/{parsed.repo}
              </p>
            )}
          </div>

          {/* Branch Selection */}
          <div className="space-y-2">
            <Label htmlFor="branch">Branch</Label>
            <Select value={branch} onValueChange={setBranch}>
              <SelectTrigger id="branch">
                <SelectValue placeholder="Select branch" />
              </SelectTrigger>
              <SelectContent>
                {branchesData?.branches.map((b) => (
                  <SelectItem key={b.name} value={b.name}>
                    {b.name}
                    {b.name === branchesData.default_branch && " (default)"}
                  </SelectItem>
                ))}
                {!branchesData && <SelectItem value="main">main</SelectItem>}
              </SelectContent>
            </Select>
          </div>

          {/* Knowledge Type */}
          <div className="space-y-2">
            <Label htmlFor="knowledge-type">Knowledge Type</Label>
            <Select value={knowledgeType} onValueChange={setKnowledgeType}>
              <SelectTrigger id="knowledge-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="documentation">Documentation</SelectItem>
                <SelectItem value="code">Code</SelectItem>
                <SelectItem value="mixed">Mixed</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Tags */}
          <div className="space-y-2">
            <Label htmlFor="tags">Tags</Label>
            <div className="flex gap-2">
              <Input
                id="tags"
                type="text"
                placeholder="Add tag"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTag();
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={handleAddTag}>
                Add
              </Button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {tags.map((tag) => (
                  <Badge key={tag} variant="solid" color="blue" className="cursor-pointer" onClick={() => handleRemoveTag(tag)}>
                    {tag} ×
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Extract Code Examples */}
          <div className="flex items-center space-x-2">
            <input
              id="extract-code"
              type="checkbox"
              checked={extractCode}
              onChange={(e) => setExtractCode(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Label htmlFor="extract-code" className="cursor-pointer">
              Extract code examples for search
            </Label>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="outline" onClick={() => handleClose(false)} disabled={linkMutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={linkMutation.isPending}>
              {linkMutation.isPending ? "Linking..." : "Link Repository"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
