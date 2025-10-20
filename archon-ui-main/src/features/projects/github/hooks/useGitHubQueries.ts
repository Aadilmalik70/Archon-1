/**
 * GitHub Query Hooks
 *
 * TanStack Query hooks for GitHub repository integration.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { githubService } from "../services/githubService";
import type {
  GitHubSource,
  LinkGitHubRepoRequest,
  LinkGitHubRepoResponse,
} from "../types";
import { DISABLED_QUERY_KEY, STALE_TIMES } from "@/features/shared/config/queryPatterns";

/**
 * Query key factory for GitHub operations
 */
export const githubKeys = {
  all: ["github"] as const,
  sources: (projectId: string) => ["projects", projectId, "github", "sources"] as const,
  branches: (owner: string, repo: string) => [...githubKeys.all, "branches", owner, repo] as const,
  stats: (sourceId: string) => [...githubKeys.all, "stats", sourceId] as const,
};

/**
 * Hook to get GitHub sources linked to a project
 */
export function useProjectGitHubSources(projectId: string | undefined) {
  return useQuery({
    queryKey: projectId ? githubKeys.sources(projectId) : DISABLED_QUERY_KEY,
    queryFn: () => projectId
      ? githubService.getLinkedSources(projectId)
      : Promise.reject("No project ID provided"),
    enabled: !!projectId,
    staleTime: STALE_TIMES.normal,
  });
}

/**
 * Hook to list branches for a repository
 */
export function useRepositoryBranches(owner: string | undefined, repo: string | undefined) {
  return useQuery({
    queryKey: owner && repo ? githubKeys.branches(owner, repo) : DISABLED_QUERY_KEY,
    queryFn: () => owner && repo
      ? githubService.listBranches(owner, repo)
      : Promise.reject("No owner or repo provided"),
    enabled: !!owner && !!repo,
    staleTime: STALE_TIMES.rare, // Branches don't change often
  });
}

/**
 * Hook to get repository statistics
 */
export function useRepositoryStats(sourceId: string | undefined) {
  return useQuery({
    queryKey: sourceId ? githubKeys.stats(sourceId) : DISABLED_QUERY_KEY,
    queryFn: () => sourceId
      ? githubService.getRepositoryStats(sourceId)
      : Promise.reject("No source ID provided"),
    enabled: !!sourceId,
    staleTime: STALE_TIMES.normal,
  });
}

/**
 * Hook to link a GitHub repository to a project
 */
export function useLinkGitHubRepository(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: LinkGitHubRepoRequest) =>
      githubService.linkRepository(projectId, request),

    onMutate: async (request: LinkGitHubRepoRequest) => {
      // Cancel in-flight queries
      await queryClient.cancelQueries({ queryKey: githubKeys.sources(projectId) });

      // Snapshot for rollback
      const previous = queryClient.getQueryData<GitHubSource[]>(githubKeys.sources(projectId));

      // Parse repo URL to extract owner and repo name
      const urlMatch = request.repo_url.match(/github\.com\/([^/]+)\/([^/]+)/);
      const owner = urlMatch?.[1] || "unknown";
      const repoName = urlMatch?.[2]?.replace(/\.git$/, "") || "unknown";

      // Create optimistic source entry
      const optimisticSource: GitHubSource = {
        source_id: `temp_${Date.now()}`, // Temporary ID
        source_url: request.repo_url,
        source_display_name: `${owner}/${repoName}`,
        metadata: {
          source_type: "github_repo",
          owner,
          repo_name: repoName,
          branch: request.branch || "main",
          file_count: 0,
          total_size: 0,
          tags: request.tags || [],
          knowledge_type: request.knowledge_type || "documentation",
          indexed_at: new Date().toISOString(),
        },
      };

      // Optimistically add to list
      queryClient.setQueryData<GitHubSource[]>(
        githubKeys.sources(projectId),
        (old = []) => [...old, optimisticSource]
      );

      return { previous, optimisticSource };
    },

    onSuccess: (data: LinkGitHubRepoResponse, variables, context) => {
      // Replace optimistic entry with real data
      const sources = queryClient.getQueryData<GitHubSource[]>(githubKeys.sources(projectId));
      if (sources && context?.optimisticSource) {
        const updatedSources = sources.map((source) =>
          source.source_id === context.optimisticSource.source_id
            ? { ...context.optimisticSource, source_id: data.sourceId }
            : source
        );
        queryClient.setQueryData(githubKeys.sources(projectId), updatedSources);
      }

      // Invalidate to fetch actual data after indexing
      queryClient.invalidateQueries({ queryKey: githubKeys.sources(projectId) });
    },

    onError: (err, variables, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(githubKeys.sources(projectId), context.previous);
      }
    },
  });
}

/**
 * Hook to unlink a GitHub repository from a project
 */
export function useUnlinkGitHubRepository(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sourceId: string) =>
      githubService.unlinkRepository(projectId, sourceId),

    onMutate: async (sourceId: string) => {
      // Cancel in-flight queries
      await queryClient.cancelQueries({ queryKey: githubKeys.sources(projectId) });

      // Snapshot for rollback
      const previous = queryClient.getQueryData<GitHubSource[]>(githubKeys.sources(projectId));

      // Optimistically remove from list
      if (previous) {
        queryClient.setQueryData(
          githubKeys.sources(projectId),
          previous.filter((source) => source.source_id !== sourceId)
        );
      }

      return { previous };
    },

    onError: (err, variables, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(githubKeys.sources(projectId), context.previous);
      }
    },

    onSuccess: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: githubKeys.sources(projectId) });
    },
  });
}

/**
 * Hook to validate GitHub token
 */
export function useValidateGitHubToken() {
  return useMutation({
    mutationFn: (token: string) => githubService.validateToken(token),
  });
}
