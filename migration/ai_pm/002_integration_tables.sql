-- =====================================================
-- AI-PM Integration Tables Migration
-- =====================================================
-- Creates tables for external service integrations:
-- - integration_credentials: Encrypted OAuth tokens and API keys
-- - slack_channels: Slack workspace and channel mappings
-- - asana_projects: Asana workspace and project mappings
-- - task_sync_log: Bidirectional sync tracking
--
-- Dependencies: 001_core_tables.sql
-- =====================================================

-- =====================================================
-- SECTION 1: INTEGRATION CREDENTIALS TABLE
-- =====================================================

-- Securely store OAuth tokens and API keys for external services
CREATE TABLE IF NOT EXISTS integration_credentials (
    credential_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(50) NOT NULL,
    credential_type VARCHAR(50) NOT NULL,
    encrypted_value TEXT,
    metadata JSONB DEFAULT '{}',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_service_name CHECK (
        service_name IN ('slack', 'asana', 'github', 'jira', 'linear')
    ),
    CONSTRAINT check_credential_type CHECK (
        credential_type IN ('oauth_token', 'api_key', 'webhook_url', 'refresh_token')
    ),
    -- Ensure only one credential per service/type combination
    UNIQUE(service_name, credential_type)
);

-- Indexes for lookups
CREATE INDEX IF NOT EXISTS idx_integration_creds_service ON integration_credentials(service_name);
CREATE INDEX IF NOT EXISTS idx_integration_creds_expires ON integration_credentials(expires_at);

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER update_integration_credentials_updated_at
    BEFORE UPDATE ON integration_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE integration_credentials IS 'Securely stores encrypted OAuth tokens and API keys for external service integrations';
COMMENT ON COLUMN integration_credentials.service_name IS 'External service identifier: slack, asana, github, jira, linear';
COMMENT ON COLUMN integration_credentials.credential_type IS 'Type of credential: oauth_token, api_key, webhook_url, refresh_token';
COMMENT ON COLUMN integration_credentials.encrypted_value IS 'Encrypted credential value (bcrypt hashed)';
COMMENT ON COLUMN integration_credentials.metadata IS 'Additional service-specific data (workspace_id, team_id, scopes, etc.)';
COMMENT ON COLUMN integration_credentials.expires_at IS 'Token expiration timestamp (NULL for non-expiring tokens)';

-- =====================================================
-- SECTION 2: SLACK CHANNELS TABLE
-- =====================================================

-- Map Archon projects to Slack channels for notifications
CREATE TABLE IF NOT EXISTS slack_channels (
    channel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES archon_projects(id) ON DELETE CASCADE,
    slack_channel_id VARCHAR(50) NOT NULL,
    slack_channel_name VARCHAR(255) NOT NULL,
    notification_types TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique mapping per project
    UNIQUE(project_id, slack_channel_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_slack_channels_project ON slack_channels(project_id);
CREATE INDEX IF NOT EXISTS idx_slack_channels_slack_id ON slack_channels(slack_channel_id);

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER update_slack_channels_updated_at
    BEFORE UPDATE ON slack_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE slack_channels IS 'Maps Archon projects to Slack channels for AI-PM notifications';
COMMENT ON COLUMN slack_channels.project_id IS 'Reference to Archon project';
COMMENT ON COLUMN slack_channels.slack_channel_id IS 'Slack channel ID (e.g., C1234567890)';
COMMENT ON COLUMN slack_channels.slack_channel_name IS 'Human-readable channel name (e.g., #ai-pm-updates)';
COMMENT ON COLUMN slack_channels.notification_types IS 'Array of notification types to send: task_created, task_completed, agent_action, execution_failed';

-- =====================================================
-- SECTION 3: ASANA PROJECTS TABLE
-- =====================================================

-- Map Archon projects to Asana projects for bidirectional sync
CREATE TABLE IF NOT EXISTS asana_projects (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archon_project_id UUID REFERENCES archon_projects(id) ON DELETE CASCADE,
    asana_workspace_id VARCHAR(50) NOT NULL,
    asana_project_id VARCHAR(50) NOT NULL,
    sync_enabled BOOLEAN DEFAULT true,
    sync_direction VARCHAR(20) DEFAULT 'bidirectional',
    last_sync_at TIMESTAMPTZ,
    sync_errors INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_sync_direction CHECK (
        sync_direction IN ('inbound', 'outbound', 'bidirectional', 'disabled')
    ),
    -- Ensure one-to-one mapping
    UNIQUE(archon_project_id),
    UNIQUE(asana_project_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_asana_projects_archon ON asana_projects(archon_project_id);
CREATE INDEX IF NOT EXISTS idx_asana_projects_asana ON asana_projects(asana_project_id);
CREATE INDEX IF NOT EXISTS idx_asana_projects_sync_enabled ON asana_projects(sync_enabled);

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER update_asana_projects_updated_at
    BEFORE UPDATE ON asana_projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments
COMMENT ON TABLE asana_projects IS 'Maps Archon projects to Asana projects for bidirectional task synchronization';
COMMENT ON COLUMN asana_projects.archon_project_id IS 'Reference to Archon project (one-to-one mapping)';
COMMENT ON COLUMN asana_projects.asana_workspace_id IS 'Asana workspace GID';
COMMENT ON COLUMN asana_projects.asana_project_id IS 'Asana project GID (unique across all workspaces)';
COMMENT ON COLUMN asana_projects.sync_enabled IS 'Whether automatic sync is active for this mapping';
COMMENT ON COLUMN asana_projects.sync_direction IS 'Sync direction: inbound (Asana→Archon), outbound (Archon→Asana), bidirectional, or disabled';
COMMENT ON COLUMN asana_projects.last_sync_at IS 'Timestamp of last successful sync operation';
COMMENT ON COLUMN asana_projects.sync_errors IS 'Count of consecutive sync errors (resets to 0 on success)';

-- =====================================================
-- SECTION 4: TASK SYNC LOG TABLE
-- =====================================================

-- Track all task synchronization operations between Archon and external systems
CREATE TABLE IF NOT EXISTS task_sync_log (
    sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    archon_task_id UUID REFERENCES archon_tasks(id) ON DELETE CASCADE,
    external_service VARCHAR(50) NOT NULL,
    external_task_id VARCHAR(100) NOT NULL,
    sync_direction VARCHAR(20) NOT NULL,
    sync_status VARCHAR(20) DEFAULT 'synced',
    conflict_data JSONB DEFAULT '{}',
    changes_applied JSONB DEFAULT '{}',
    error_message TEXT,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_external_service CHECK (
        external_service IN ('asana', 'jira', 'linear', 'github')
    ),
    CONSTRAINT check_sync_direction CHECK (
        sync_direction IN ('inbound', 'outbound', 'bidirectional')
    ),
    CONSTRAINT check_sync_status CHECK (
        sync_status IN ('synced', 'pending', 'conflict', 'failed', 'skipped')
    )
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_task_sync_archon_task ON task_sync_log(archon_task_id);
CREATE INDEX IF NOT EXISTS idx_task_sync_external ON task_sync_log(external_service, external_task_id);
CREATE INDEX IF NOT EXISTS idx_task_sync_status ON task_sync_log(sync_status);
CREATE INDEX IF NOT EXISTS idx_task_sync_created ON task_sync_log(created_at DESC);

-- Add comments
COMMENT ON TABLE task_sync_log IS 'Tracks all task synchronization operations with external project management systems';
COMMENT ON COLUMN task_sync_log.archon_task_id IS 'Reference to Archon task being synced';
COMMENT ON COLUMN task_sync_log.external_service IS 'External service name: asana, jira, linear, github';
COMMENT ON COLUMN task_sync_log.external_task_id IS 'Task ID in external system';
COMMENT ON COLUMN task_sync_log.sync_direction IS 'Direction of sync operation: inbound, outbound, or bidirectional';
COMMENT ON COLUMN task_sync_log.sync_status IS 'Result of sync: synced, pending, conflict, failed, skipped';
COMMENT ON COLUMN task_sync_log.conflict_data IS 'Details of any sync conflicts detected (competing changes)';
COMMENT ON COLUMN task_sync_log.changes_applied IS 'JSON object describing what fields were changed during sync';

-- =====================================================
-- SECTION 5: ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE integration_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE slack_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE asana_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_sync_log ENABLE ROW LEVEL SECURITY;

-- Policies for service role (backend) - full access
CREATE POLICY "Service role full access to credentials" ON integration_credentials
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access to slack channels" ON slack_channels
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access to asana projects" ON asana_projects
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access to task sync log" ON task_sync_log
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policies for authenticated users - read-only access (credentials are hidden)
CREATE POLICY "Authenticated users can read slack channels" ON slack_channels
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can read asana projects" ON asana_projects
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can read task sync log" ON task_sync_log
    FOR SELECT
    TO authenticated
    USING (true);

-- Note: integration_credentials should NOT be readable by authenticated users (sensitive data)

-- =====================================================
-- SECTION 6: HELPER FUNCTIONS
-- =====================================================

-- Function to check if a service is connected
CREATE OR REPLACE FUNCTION is_service_connected(p_service_name VARCHAR(50))
RETURNS BOOLEAN AS $$
DECLARE
    cred_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO cred_count
    FROM integration_credentials
    WHERE service_name = p_service_name
      AND credential_type = 'oauth_token'
      AND (expires_at IS NULL OR expires_at > NOW());

    RETURN cred_count > 0;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get sync statistics
CREATE OR REPLACE FUNCTION get_sync_statistics(
    since_timestamp TIMESTAMPTZ DEFAULT NOW() - INTERVAL '24 hours'
)
RETURNS TABLE (
    external_service VARCHAR(50),
    total_syncs BIGINT,
    successful_syncs BIGINT,
    failed_syncs BIGINT,
    conflict_count BIGINT,
    last_sync TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tsl.external_service,
        COUNT(*) AS total_syncs,
        COUNT(*) FILTER (WHERE tsl.sync_status = 'synced') AS successful_syncs,
        COUNT(*) FILTER (WHERE tsl.sync_status = 'failed') AS failed_syncs,
        COUNT(*) FILTER (WHERE tsl.sync_status = 'conflict') AS conflict_count,
        MAX(tsl.last_synced_at) AS last_sync
    FROM task_sync_log tsl
    WHERE tsl.created_at >= since_timestamp
    GROUP BY tsl.external_service
    ORDER BY total_syncs DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get projects with active integrations
CREATE OR REPLACE FUNCTION get_integrated_projects()
RETURNS TABLE (
    project_id UUID,
    project_title VARCHAR(255),
    slack_connected BOOLEAN,
    asana_connected BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id AS project_id,
        p.title AS project_title,
        EXISTS(SELECT 1 FROM slack_channels sc WHERE sc.project_id = p.id) AS slack_connected,
        EXISTS(SELECT 1 FROM asana_projects ap WHERE ap.archon_project_id = p.id AND ap.sync_enabled = true) AS asana_connected
    FROM archon_projects p
    ORDER BY p.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to check for expiring tokens (monitoring)
CREATE OR REPLACE FUNCTION get_expiring_tokens(
    days_ahead INTEGER DEFAULT 7
)
RETURNS TABLE (
    credential_id UUID,
    service_name VARCHAR(50),
    expires_at TIMESTAMPTZ,
    days_until_expiry INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ic.credential_id,
        ic.service_name,
        ic.expires_at,
        EXTRACT(DAY FROM (ic.expires_at - NOW()))::INTEGER AS days_until_expiry
    FROM integration_credentials ic
    WHERE ic.expires_at IS NOT NULL
      AND ic.expires_at > NOW()
      AND ic.expires_at < NOW() + (days_ahead || ' days')::INTERVAL
    ORDER BY ic.expires_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- =====================================================
-- SECTION 7: VERIFICATION
-- =====================================================

-- Verify all tables exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'integration_credentials') THEN
        RAISE EXCEPTION 'Table integration_credentials was not created';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'slack_channels') THEN
        RAISE EXCEPTION 'Table slack_channels was not created';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'asana_projects') THEN
        RAISE EXCEPTION 'Table asana_projects was not created';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'task_sync_log') THEN
        RAISE EXCEPTION 'Table task_sync_log was not created';
    END IF;

    RAISE NOTICE 'AI-PM integration tables created successfully!';
END $$;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
-- Tables created:
--   - integration_credentials (encrypted storage)
--   - slack_channels (project → Slack mapping)
--   - asana_projects (project → Asana mapping)
--   - task_sync_log (sync history tracking)
-- RLS policies: 7 policies created
-- Helper functions: 4 functions created
-- =====================================================
