-- =====================================================
-- ROLLBACK: AI-PM Integration Tables Migration
-- =====================================================
-- Reverts changes from 002_integration_tables.sql
--
-- WARNING: This will permanently delete:
-- - All integration credentials (OAuth tokens, API keys)
-- - All Slack channel mappings
-- - All Asana project mappings
-- - All task sync history
--
-- Use only if migration failed or in development
-- =====================================================

-- Confirm rollback intent
DO $$
BEGIN
    RAISE NOTICE '⚠️  WARNING: Rolling back AI-PM integration tables migration';
    RAISE NOTICE '⚠️  This will DELETE all integration credentials and sync data';
    RAISE NOTICE '⚠️  You will need to reconnect all external services';
    RAISE NOTICE '⚠️  Press Ctrl+C to cancel, or wait 5 seconds to proceed...';
    PERFORM pg_sleep(5);
END $$;

-- =====================================================
-- SECTION 1: DROP HELPER FUNCTIONS
-- =====================================================

DROP FUNCTION IF EXISTS get_expiring_tokens(INTEGER);
DROP FUNCTION IF EXISTS get_integrated_projects();
DROP FUNCTION IF EXISTS get_sync_statistics(TIMESTAMPTZ);
DROP FUNCTION IF EXISTS is_service_connected(VARCHAR(50));

RAISE NOTICE '✓ Helper functions dropped';

-- =====================================================
-- SECTION 2: DROP TABLES (CASCADE to remove dependencies)
-- =====================================================

DROP TABLE IF EXISTS task_sync_log CASCADE;
DROP TABLE IF EXISTS asana_projects CASCADE;
DROP TABLE IF EXISTS slack_channels CASCADE;
DROP TABLE IF EXISTS integration_credentials CASCADE;

RAISE NOTICE '✓ Integration tables dropped';

-- =====================================================
-- SECTION 3: VERIFICATION
-- =====================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'integration_credentials') THEN
        RAISE EXCEPTION '❌ Table integration_credentials still exists!';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'slack_channels') THEN
        RAISE EXCEPTION '❌ Table slack_channels still exists!';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'asana_projects') THEN
        RAISE EXCEPTION '❌ Table asana_projects still exists!';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'task_sync_log') THEN
        RAISE EXCEPTION '❌ Table task_sync_log still exists!';
    END IF;

    RAISE NOTICE '✓ Rollback verification passed';
    RAISE NOTICE '✅ Migration 002 successfully rolled back';
END $$;

-- =====================================================
-- ROLLBACK COMPLETE
-- =====================================================
-- Dropped: integration_credentials, slack_channels,
--          asana_projects, task_sync_log
-- Removed: 4 helper functions
-- Removed: All RLS policies (automatically via CASCADE)
-- =====================================================
