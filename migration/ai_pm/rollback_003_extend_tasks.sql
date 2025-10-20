-- =====================================================
-- ROLLBACK: AI-PM Task Extensions Migration
-- =====================================================
-- Reverts changes from 003_extend_tasks.sql
--
-- WARNING: This will permanently delete:
-- - All AI-PM task assignments
-- - All task dependencies
-- - All automation status tracking
-- - All sync references (Asana, Slack)
--
-- NOTE: This does NOT delete the tasks themselves,
-- only the AI-PM specific fields
--
-- Use only if migration failed or in development
-- =====================================================

-- Confirm rollback intent
DO $$
BEGIN
    RAISE NOTICE '⚠️  WARNING: Rolling back AI-PM task extensions migration';
    RAISE NOTICE '⚠️  This will REMOVE AI-PM fields from archon_tasks table';
    RAISE NOTICE '⚠️  Task data will remain, but AI-PM metadata will be lost';
    RAISE NOTICE '⚠️  Press Ctrl+C to cancel, or wait 5 seconds to proceed...';
    PERFORM pg_sleep(5);
END $$;

-- =====================================================
-- SECTION 1: DROP TRIGGERS
-- =====================================================

DROP TRIGGER IF EXISTS trigger_auto_context_summary ON archon_tasks;
DROP FUNCTION IF EXISTS auto_generate_context_summary();

RAISE NOTICE '✓ Triggers and trigger functions dropped';

-- =====================================================
-- SECTION 2: DROP HELPER FUNCTIONS
-- =====================================================

DROP FUNCTION IF EXISTS get_aipm_task_stats(UUID, TIMESTAMPTZ);
DROP FUNCTION IF EXISTS get_ready_tasks(VARCHAR(50));
DROP FUNCTION IF EXISTS get_dependency_tree(UUID);
DROP FUNCTION IF EXISTS check_dependencies_complete(UUID);
DROP FUNCTION IF EXISTS get_tasks_by_agent(VARCHAR(50), VARCHAR(20));

RAISE NOTICE '✓ Helper functions dropped';

-- =====================================================
-- SECTION 3: DROP INDEXES
-- =====================================================

DROP INDEX IF EXISTS idx_tasks_dependencies;
DROP INDEX IF EXISTS idx_tasks_automation_agent;
DROP INDEX IF EXISTS idx_tasks_slack_thread;
DROP INDEX IF EXISTS idx_tasks_asana_id;
DROP INDEX IF EXISTS idx_tasks_automation_status;
DROP INDEX IF EXISTS idx_tasks_task_type;
DROP INDEX IF EXISTS idx_tasks_agent_assigned;

RAISE NOTICE '✓ Indexes dropped';

-- =====================================================
-- SECTION 4: DROP CONSTRAINTS
-- =====================================================

ALTER TABLE archon_tasks DROP CONSTRAINT IF EXISTS check_automation_status;
ALTER TABLE archon_tasks DROP CONSTRAINT IF EXISTS check_task_type;
ALTER TABLE archon_tasks DROP CONSTRAINT IF EXISTS check_agent_assigned;

RAISE NOTICE '✓ Constraints dropped';

-- =====================================================
-- SECTION 5: DROP COLUMNS
-- =====================================================

ALTER TABLE archon_tasks
    DROP COLUMN IF EXISTS slack_thread_ts,
    DROP COLUMN IF EXISTS asana_task_id,
    DROP COLUMN IF EXISTS execution_metadata,
    DROP COLUMN IF EXISTS automation_status,
    DROP COLUMN IF EXISTS dependencies,
    DROP COLUMN IF EXISTS context_summary,
    DROP COLUMN IF EXISTS task_type,
    DROP COLUMN IF EXISTS agent_assigned;

RAISE NOTICE '✓ Columns dropped from archon_tasks';

-- =====================================================
-- SECTION 6: VERIFICATION
-- =====================================================

DO $$
DECLARE
    column_count INTEGER;
BEGIN
    -- Check that AI-PM columns are removed
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'archon_tasks'
      AND column_name IN (
          'agent_assigned',
          'task_type',
          'context_summary',
          'dependencies',
          'automation_status',
          'execution_metadata',
          'asana_task_id',
          'slack_thread_ts'
      );

    IF column_count > 0 THEN
        RAISE EXCEPTION '❌ Some AI-PM columns still exist! Found % columns', column_count;
    END IF;

    -- Verify archon_tasks table still exists
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'archon_tasks') THEN
        RAISE EXCEPTION '❌ archon_tasks table was accidentally deleted!';
    END IF;

    RAISE NOTICE '✓ Rollback verification passed';
    RAISE NOTICE '✅ Migration 003 successfully rolled back';
    RAISE NOTICE 'ℹ️  archon_tasks table preserved with original structure';
END $$;

-- =====================================================
-- ROLLBACK COMPLETE
-- =====================================================
-- Removed from archon_tasks: 8 columns
-- Dropped: 7 indexes
-- Dropped: 3 constraints
-- Dropped: 5 helper functions
-- Dropped: 1 trigger + function
-- Table preserved: archon_tasks (with original columns)
-- =====================================================
