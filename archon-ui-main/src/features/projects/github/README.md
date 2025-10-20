# GitHub Integration Feature

This feature provides GitHub repository integration for Archon projects, allowing users to link entire repositories for context and RAG search.

## Overview

The GitHub integration feature enables:
- Linking GitHub repositories to projects
- Automatic repository cloning and indexing
- Branch selection
- File pattern filtering (include/exclude)
- Progress tracking for indexing operations
- Repository unlinking

## Architecture

### Backend API Endpoints

```
POST   /api/github/validate-token              - Validate GitHub PAT
GET    /api/github/repository/:owner/:repo/branches - List branches
POST   /api/projects/:id/github/link           - Link repository
GET    /api/projects/:id/github/sources        - Get linked sources
DELETE /api/projects/:id/github/:sourceId      - Unlink repository
GET    /api/github/sources/:sourceId/stats     - Get repository stats
```

### Frontend Structure

```
src/features/projects/github/
├── components/
│   ├── GitHubTab.tsx          - Main tab component
│   └── GitHubLinkModal.tsx    - Repository linking modal
├── hooks/
│   └── useGitHubQueries.ts    - TanStack Query hooks
├── services/
│   └── githubService.ts       - API service layer
├── types/
│   └── index.ts               - TypeScript type definitions
└── index.ts                   - Barrel exports
```

## Usage

### 1. Save GitHub Token (Backend)

First, save your GitHub Personal Access Token via the credentials API:

```bash
POST http://localhost:8181/api/credentials
Content-Type: application/json

{
  "key": "GITHUB_TOKEN",
  "value": "ghp_your_token_here"
}
```

### 2. Link a Repository (Frontend)

Navigate to a project and click the "GitHub" tab, then click "Link Repository":

```typescript
import { GitHubTab } from "@/features/projects/github";

<GitHubTab projectId={project.id} />
```

The modal allows you to:
- Enter repository URL
- Select branch (auto-loads branches)
- Choose knowledge type (documentation/code/mixed)
- Add tags
- Configure file patterns
- Enable code example extraction

### 3. Monitor Progress

The linking operation is asynchronous. Progress is tracked via the `/api/progress/:progressId` endpoint and displayed in real-time.

## Components

### GitHubTab

Main component displaying linked repositories.

**Props:**
- `projectId: string` - The project ID

**Features:**
- Lists all linked repositories
- Shows repository metadata (file count, size, branch, tags)
- Unlink functionality
- Progress tracking for active operations
- Empty state with call-to-action

### GitHubLinkModal

Modal for linking new repositories.

**Props:**
- `isOpen: boolean` - Modal visibility
- `onClose: () => void` - Close handler
- `projectId: string` - Target project ID
- `onSuccess?: (progressId: string, sourceId: string) => void` - Success callback

**Features:**
- Repository URL input with validation
- Auto-loading branch list from GitHub API
- Knowledge type selection
- Tag management
- File pattern configuration (advanced)
- Code example extraction toggle

## Hooks

### useProjectGitHubSources

Fetches GitHub sources linked to a project.

```typescript
const { data: sources, isLoading } = useProjectGitHubSources(projectId);
```

### useRepositoryBranches

Lists branches for a repository.

```typescript
const { data: branchesData } = useRepositoryBranches(owner, repo);
```

### useLinkGitHubRepository

Mutation for linking a repository.

```typescript
const linkMutation = useLinkGitHubRepository(projectId);
await linkMutation.mutateAsync({
  repo_url: "https://github.com/owner/repo",
  branch: "main",
  knowledge_type: "documentation",
  tags: ["react", "typescript"],
  extract_code_examples: false,
});
```

### useUnlinkGitHubRepository

Mutation for unlinking a repository.

```typescript
const unlinkMutation = useUnlinkGitHubRepository(projectId);
await unlinkMutation.mutateAsync(sourceId);
```

## Query Keys

Query keys follow the established pattern:

```typescript
githubKeys.all                   // ["github"]
githubKeys.sources(projectId)    // ["projects", projectId, "github", "sources"]
githubKeys.branches(owner, repo) // ["github", "branches", owner, repo]
githubKeys.stats(sourceId)       // ["github", "stats", sourceId]
```

## Types

### GitHubSource

```typescript
interface GitHubSource {
  source_id: string;
  source_url: string;
  source_display_name: string;
  metadata: GitHubSourceMetadata;
}
```

### LinkGitHubRepoRequest

```typescript
interface LinkGitHubRepoRequest {
  repo_url: string;
  branch?: string;
  include_patterns?: string[];
  exclude_patterns?: string[];
  knowledge_type?: string;
  tags?: string[];
  extract_code_examples?: boolean;
}
```

## Backend Integration

### Database Schema

**archon_sources table:**
- Stores repository metadata
- JSONB column for flexible metadata (owner, repo_name, branch, file_count, etc.)
- File tree preserved in metadata

**archon_project_sources junction table:**
- Links projects to sources (many-to-many)
- Tracks linking timestamp and notes

**documents table:**
- Stores document chunks with embeddings
- Each chunk linked to source via metadata

### Indexing Process

1. **Clone**: Shallow clone of repository (depth=1, single branch)
2. **Scan**: Extract files matching supported extensions
3. **Filter**: Apply include/exclude patterns if specified
4. **Chunk**: Split files into chunks for embeddings
5. **Embed**: Generate embeddings using configured provider (OpenAI by default)
6. **Store**: Save chunks to database with metadata
7. **Link**: Create junction record linking source to project

### Progress Tracking

The indexing operation reports progress:
- 0-10%: Cloning repository
- 10-30%: Scanning files
- 30-95%: Indexing files (chunking + embeddings)
- 95-100%: Linking to project

## Configuration

### GitHub Token Setup

1. Create a GitHub Personal Access Token at https://github.com/settings/tokens
2. Required scopes:
   - `repo` (for private repositories)
   - Or no scopes required for public repositories only
3. Save token via credentials API

### Supported File Types

The backend indexes files with these extensions:
- Code: .js, .ts, .jsx, .tsx, .py, .java, .cpp, .c, .go, .rs, .rb, .php
- Markup: .md, .html, .xml, .json, .yaml, .yml
- Documentation: .txt, .rst

### File Patterns

Use glob patterns for include/exclude:
```typescript
include_patterns: ["src/**/*.ts", "docs/**/*.md"]
exclude_patterns: ["**/node_modules/**", "**/*.test.ts"]
```

## Error Handling

All API errors are caught and displayed via toast notifications:
- Invalid GitHub token
- Repository not found
- Network errors
- Server errors

Optimistic updates are used for unlinking operations with automatic rollback on error.

## Performance Considerations

- Branch list is cached with `STALE_TIMES.rare` (5 minutes)
- Sources list cached with `STALE_TIMES.normal` (30 seconds)
- Repository indexing is asynchronous and tracked via progress endpoint
- Large repositories (>10K files) may take several minutes to index

## Future Enhancements

- Incremental updates (detect changes and re-index only modified files)
- Webhook integration for automatic updates
- Repository statistics dashboard
- File tree browser
- Search within specific repositories
- Selective file re-indexing

## Testing

Run frontend tests:
```bash
npm run test src/features/projects/github
```

Run backend tests:
```bash
uv run pytest tests/test_github_integration.py
```

## Troubleshooting

### Token Not Working
- Verify token has correct scopes
- Check token expiration
- Validate via `/api/github/validate-token` endpoint

### Indexing Stuck
- Check progress endpoint for error messages
- Review server logs for details
- Verify Supabase connection

### Large Repository Timeout
- Use include_patterns to filter files
- Disable code example extraction
- Check server timeout settings

## Related Features

- **Projects**: Main container for linked repositories
- **Documents**: Stores chunked repository content
- **Knowledge Base**: Provides RAG search across linked repositories
- **Progress Tracking**: Monitors long-running operations
