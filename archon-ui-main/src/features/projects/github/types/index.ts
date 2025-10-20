/**
 * GitHub Integration Types
 *
 * Type definitions for GitHub repository integration.
 */

export interface GitHubSource {
  source_id: string;
  source_url: string;
  source_display_name: string;
  metadata: GitHubSourceMetadata;
}

export interface GitHubSourceMetadata {
  source_type: "github_repo";
  owner: string;
  repo_name: string;
  branch: string;
  file_count: number;
  total_size: number;
  tags: string[];
  knowledge_type: string;
  indexed_at: string;
  file_tree?: FileTreeNode;
}

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  path: string;
  size?: number;
  children?: FileTreeNode[];
}

export interface GitHubBranch {
  name: string;
  protected: boolean;
  commit_sha: string | null;
}

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

export interface ListBranchesResponse {
  branches: GitHubBranch[];
  default_branch: string;
  total: number;
}

export interface ValidateTokenResponse {
  valid: boolean;
  user?: string;
  rate_limit?: {
    remaining: number;
    limit: number;
    reset: string;
  };
  error?: string;
}

export interface UnlinkRepositoryResponse {
  success: boolean;
  message: string;
}

export interface RepositoryStats {
  source_id: string;
  total_documents: number;
  total_chunks: number;
  total_code_examples: number;
  file_types: Record<string, number>;
  total_size: number;
}
