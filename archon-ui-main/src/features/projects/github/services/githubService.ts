/**
 * GitHub Service
 *
 * API service for GitHub repository integration with projects.
 */

import { callAPIWithETag } from "@/features/shared/api/apiClient";

export interface LinkGitHubRepoRequest {
  repo_url: string;
  branch?: string;
  include_patterns?: string[];
  exclude_patterns?: string[];
  knowledge_type?: string;
  tags?: string[];
  extract_code_examples?: boolean;
}

export interface LinkGitHubRepoResponse {
  success: boolean;
  progressId: string;
  sourceId: string;
  message: string;
}

export interface GitHubSource {
  source_id: string;
  source_url: string;
  source_display_name: string;
  metadata: {
    source_type: string;
    owner: string;
    repo_name: string;
    branch: string;
    file_count: number;
    total_size: number;
    tags: string[];
    knowledge_type: string;
    indexed_at: string;
  };
}

export interface GitHubBranch {
  name: string;
  protected: boolean;
  commit_sha: string | null;
}

export interface ListBranchesResponse {
  branches: GitHubBranch[];
  default_branch: string;
  total: number;
}

export const githubService = {
  /**
   * Validate GitHub Personal Access Token
   */
  async validateToken(token: string): Promise<{ valid: boolean; user?: string; rate_limit?: any; error?: string }> {
    return callAPIWithETag("/github/validate-token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
  },

  /**
   * List branches for a GitHub repository
   */
  async listBranches(owner: string, repo: string): Promise<ListBranchesResponse> {
    return callAPIWithETag(`/github/repository/${owner}/${repo}/branches`);
  },

  /**
   * Link a GitHub repository to a project
   */
  async linkRepository(projectId: string, request: LinkGitHubRepoRequest): Promise<LinkGitHubRepoResponse> {
    return callAPIWithETag(`/projects/${projectId}/github/link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  },

  /**
   * Get GitHub sources linked to a project
   */
  async getLinkedSources(projectId: string): Promise<GitHubSource[]> {
    const response = await callAPIWithETag<{ sources: GitHubSource[] }>(`/projects/${projectId}/github/sources`);
    return response.sources || [];
  },

  /**
   * Unlink a GitHub repository from a project
   */
  async unlinkRepository(projectId: string, sourceId: string): Promise<{ success: boolean; message: string }> {
    return callAPIWithETag(`/projects/${projectId}/github/${sourceId}`, {
      method: "DELETE",
    });
  },

  /**
   * Get repository statistics
   */
  async getRepositoryStats(sourceId: string): Promise<any> {
    return callAPIWithETag(`/github/sources/${sourceId}/stats`);
  },
};
