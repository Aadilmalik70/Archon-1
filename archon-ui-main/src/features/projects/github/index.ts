/**
 * GitHub Integration Module
 *
 * Barrel export for GitHub repository integration feature.
 */

export { GitHubTab } from "./components/GitHubTab";
export { GitHubLinkModal } from "./components/GitHubLinkModal";
export { githubService } from "./services/githubService";
export {
  githubKeys,
  useProjectGitHubSources,
  useRepositoryBranches,
  useRepositoryStats,
  useLinkGitHubRepository,
  useUnlinkGitHubRepository,
  useValidateGitHubToken,
} from "./hooks/useGitHubQueries";
export type {
  GitHubSource,
  GitHubSourceMetadata,
  GitHubBranch,
  LinkGitHubRepoRequest,
  LinkGitHubRepoResponse,
  ListBranchesResponse,
  ValidateTokenResponse,
  UnlinkRepositoryResponse,
  RepositoryStats,
  FileTreeNode,
} from "./types";
