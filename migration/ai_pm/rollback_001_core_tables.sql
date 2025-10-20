-- =====================================================
-- ROLLBACK: AI-PM Core Tables Migration
-- =====================================================
-- Reverts changes from 001_core_tables.sql
--
-- WARNING: This will permanently delete:
-- - All AI-PM execution history
-- - All agent configurations
-- - All associated data
--
-- Use only if migration failed or in development
-- =====================================================

-- Confirm rollback intent
DO $$
BEGIN
    RAISE NOTICE '⚠️  WARNING: Rolling back AI-PM core tables migration';
    RAISE NOTICE '⚠️  This will DELETE all execution history and agent configs';
    RAISE NOTICE '⚠️  Press Ctrl+C to cancel, or wait 5 seconds to proceed...';
    PERFORM pg_sleep(5);
END $$;

-- =====================================================
-- SECTION 1: DROP HELPER FUNCTIONS
-- =====================================================

DROP FUNCTION IF EXISTS get_execution_stats(TIMESTAMPTZ);
DROP FUNCTION IF EXISTS get_active_executions();

RAISE NOTICE '✓ Helper functions dropped';

-- =====================================================
-- SECTION 2: DROP TABLES (CASCADE to remove dependencies)
-- =====================================================

DROP TABLE IF EXISTS ai_pm_executions CASCADE;
DROP TABLE IF EXISTS agent_configurations CASCADE;

RAISE NOTICE '✓ Core tables dropped';

-- =====================================================
-- SECTION 3: VERIFICATION
-- =====================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ai_pm_executions') THEN
        RAISE EXCEPTION '❌ Table ai_pm_executions still exists!';
    END IF;

    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'agent_configurations') THEN
        RAISE EXCEPTION '❌ Table agent_configurations still exists!';
    END IF;

    RAISE NOTICE '✓ Rollback verification passed';
    RAISE NOTICE '✅ Migration 001 successfully rolled back';
END $$;

-- =====================================================
-- ROLLBACK COMPLETE
-- =====================================================
-- Dropped: ai_pm_executions, agent_configurations
-- Removed: 2 helper functions
-- Removed: All RLS policies (automatically via CASCADE)
-- =====================================================
