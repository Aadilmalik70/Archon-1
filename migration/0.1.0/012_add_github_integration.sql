-- =====================================================
-- GitHub Integration Migration
-- =====================================================
-- Adds support for GitHub repository integration with projects
-- Creates project-source junction table and GitHub settings
-- =====================================================

-- Add GitHub token to settings (encrypted)
INSERT INTO archon_settings (key, category, is_encrypted, description, value)
VALUES (
    'GITHUB_TOKEN',
    'github',
    true,
    'Personal Access Token for GitHub API access (requires repo scope for private repos)',
    NULL
)
ON CONFLICT (key) DO NOTHING;

-- Create project-source junction table for linking GitHub repos to projects
-- Note: Table may already exist from previous migrations
CREATE TABLE IF NOT EXISTS archon_project_sources (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES archon_projects(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    linked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, source_id)
);

-- Add optional columns if they don't exist (for existing tables)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'archon_project_sources'
        AND column_name = 'linked_by'
    ) THEN
        ALTER TABLE archon_project_sources ADD COLUMN linked_by TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'archon_project_sources'
        AND column_name = 'notes'
    ) THEN
        ALTER TABLE archon_project_sources ADD COLUMN notes TEXT;
    END IF;
END $$;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_project_sources_project_id ON archon_project_sources(project_id);
CREATE INDEX IF NOT EXISTS idx_project_sources_source_id ON archon_project_sources(source_id);
CREATE INDEX IF NOT EXISTS idx_project_sources_linked_at ON archon_project_sources(linked_at);

-- Add comment to table for documentation
COMMENT ON TABLE archon_project_sources IS 'Junction table linking projects to knowledge sources (including GitHub repositories)';
COMMENT ON COLUMN archon_project_sources.project_id IS 'Reference to archon_projects table';
COMMENT ON COLUMN archon_project_sources.source_id IS 'Reference to sources table (can be GitHub repo, crawled site, or document)';
COMMENT ON COLUMN archon_project_sources.linked_at IS 'Timestamp when the source was linked to the project';
COMMENT ON COLUMN archon_project_sources.linked_by IS 'Optional: username or identifier of who linked the source';
COMMENT ON COLUMN archon_project_sources.notes IS 'Optional: additional notes about the link';

-- Note: No schema changes needed for sources table
-- GitHub repositories will use existing metadata JSONB field to store:
-- - source_type: "github_repo"
-- - owner: GitHub username or organization
-- - repo_name: Repository name
-- - branch: Branch name
-- - file_count: Number of files indexed
-- - total_size: Total size of indexed files
-- - file_tree: Hierarchical structure of files
-- - indexed_at: Timestamp when repository was indexed
-- - tags: Array of tags

-- Migration tracking
-- Record this migration as applied
INSERT INTO archon_migrations (version, migration_name)
VALUES ('0.1.0', '012_add_github_integration')
ON CONFLICT (version, migration_name) DO NOTHING;
