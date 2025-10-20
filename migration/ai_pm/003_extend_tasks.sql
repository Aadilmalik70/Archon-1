-- =====================================================
-- AI-PM Task Extensions Migration
-- =====================================================
-- Extends archon_tasks table with AI-PM specific fields:
-- - agent_assigned: Which AI agent is handling this task
-- - task_type: Classification for routing
-- - context_summary: AI-generated task context
-- - dependencies: Task dependency tracking
-- - automation_status: Manual vs automated execution
-- - execution_metadata: Agent execution details
-- - asana_task_id: External sync reference
-- - slack_thread_ts: Slack thread reference
--
-- Dependencies: 001_core_tables.sql, 002_integration_tables.sql
-- =====================================================

-- =====================================================
-- SECTION 1: ADD NEW COLUMNS TO archon_tasks
-- =====================================================

-- Add AI-PM specific columns (all nullable for backward compatibility)
ALTER TABLE archon_tasks
    ADD COLUMN IF NOT EXISTS agent_assigned VARCHAR(50),
    ADD COLUMN IF NOT EXISTS task_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS context_summary TEXT,
    ADD COLUMN IF NOT EXISTS dependencies UUID[],
    ADD COLUMN IF NOT EXISTS automation_status VARCHAR(20) DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS execution_metadata JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS asana_task_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS slack_thread_ts VARCHAR(100);

-- Add comments for documentation
COMMENT ON COLUMN archon_tasks.agent_assigned IS 'AI agent assigned to this task: orchestrator, coding, qa, docs, security, performance';
COMMENT ON COLUMN archon_tasks.task_type IS 'Task classification: feature, bug, refactor, test, docs, security, performance';
COMMENT ON COLUMN archon_tasks.context_summary IS 'AI-generated summary of task context and requirements';
COMMENT ON COLUMN archon_tasks.dependencies IS 'Array of task UUIDs that must complete before this task';
COMMENT ON COLUMN archon_tasks.automation_status IS 'Execution mode: manual, pending, automated, failed';
COMMENT ON COLUMN archon_tasks.execution_metadata IS 'JSON metadata about agent execution (execution_id, cost, duration, etc.)';
COMMENT ON COLUMN archon_tasks.asana_task_id IS 'Asana task GID for bidirectional sync';
COMMENT ON COLUMN archon_tasks.slack_thread_ts IS 'Slack thread timestamp for notifications';

-- =====================================================
-- SECTION 2: ADD INDEXES
-- =====================================================

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_tasks_agent_assigned ON archon_tasks(agent_assigned);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON archon_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_automation_status ON archon_tasks(automation_status);
CREATE INDEX IF NOT EXISTS idx_tasks_asana_id ON archon_tasks(asana_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_slack_thread ON archon_tasks(slack_thread_ts);

-- Composite index for AI-PM dashboard queries
CREATE INDEX IF NOT EXISTS idx_tasks_automation_agent ON archon_tasks(automation_status, agent_assigned) WHERE agent_assigned IS NOT NULL;

-- GIN index for array dependencies
CREATE INDEX IF NOT EXISTS idx_tasks_dependencies ON archon_tasks USING GIN(dependencies);

-- =====================================================
-- SECTION 3: ADD CONSTRAINTS
-- =====================================================

-- Constraint for valid agent types
ALTER TABLE archon_tasks
    ADD CONSTRAINT IF NOT EXISTS check_agent_assigned
    CHECK (
        agent_assigned IS NULL OR
        agent_assigned IN ('orchestrator', 'coding', 'qa', 'docs', 'security', 'performance')
    );

-- Constraint for valid task types
ALTER TABLE archon_tasks
    ADD CONSTRAINT IF NOT EXISTS check_task_type
    CHECK (
        task_type IS NULL OR
        task_type IN ('feature', 'bug', 'refactor', 'test', 'docs', 'security', 'performance', 'other')
    );

-- Constraint for valid automation status
ALTER TABLE archon_tasks
    ADD CONSTRAINT IF NOT EXISTS check_automation_status
    CHECK (
        automation_status IN ('manual', 'pending', 'automated', 'failed', 'cancelled')
    );

-- =====================================================
-- SECTION 4: HELPER FUNCTIONS
-- =====================================================

-- Function to get tasks by agent
CREATE OR REPLACE FUNCTION get_tasks_by_agent(
    p_agent_type VARCHAR(50),
    p_status VARCHAR(20) DEFAULT NULL
)
RETURNS TABLE (
    task_id UUID,
    title VARCHAR(255),
    status VARCHAR(20),
    automation_status VARCHAR(20),
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id AS task_id,
        t.title,
        t.status,
        t.automation_status,
        t.created_at
    FROM archon_tasks t
    WHERE t.agent_assigned = p_agent_type
      AND (p_status IS NULL OR t.status = p_status)
    ORDER BY t.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to check task dependencies
CREATE OR REPLACE FUNCTION check_dependencies_complete(p_task_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    incomplete_count INTEGER;
    task_dependencies UUID[];
BEGIN
    -- Get dependencies for this task
    SELECT dependencies INTO task_dependencies
    FROM archon_tasks
    WHERE id = p_task_id;

    -- If no dependencies, return true
    IF task_dependencies IS NULL OR array_length(task_dependencies, 1) IS NULL THEN
        RETURN true;
    END IF;

    -- Count incomplete dependencies
    SELECT COUNT(*) INTO incomplete_count
    FROM archon_tasks
    WHERE id = ANY(task_dependencies)
      AND status NOT IN ('done', 'completed');

    RETURN incomplete_count = 0;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get dependency tree
CREATE OR REPLACE FUNCTION get_dependency_tree(p_task_id UUID)
RETURNS TABLE (
    task_id UUID,
    task_title VARCHAR(255),
    task_status VARCHAR(20),
    dependency_level INTEGER
) AS $$
WITH RECURSIVE dep_tree AS (
    -- Base case: the task itself
    SELECT
        id,
        title,
        status,
        dependencies,
        0 AS level
    FROM archon_tasks
    WHERE id = p_task_id

    UNION ALL

    -- Recursive case: dependencies
    SELECT
        t.id,
        t.title,
        t.status,
        t.dependencies,
        dt.level + 1
    FROM archon_tasks t
    INNER JOIN dep_tree dt ON t.id = ANY(dt.dependencies)
    WHERE dt.level < 10  -- Prevent infinite loops
)
SELECT
    id AS task_id,
    title AS task_title,
    status AS task_status,
    level AS dependency_level
FROM dep_tree
ORDER BY level DESC, title;
$$ LANGUAGE sql STABLE;

-- Function to get ready-to-execute tasks
CREATE OR REPLACE FUNCTION get_ready_tasks(p_agent_type VARCHAR(50) DEFAULT NULL)
RETURNS TABLE (
    task_id UUID,
    title VARCHAR(255),
    task_type VARCHAR(50),
    agent_assigned VARCHAR(50),
    priority VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id AS task_id,
        t.title,
        t.task_type,
        t.agent_assigned,
        t.priority
    FROM archon_tasks t
    WHERE t.automation_status IN ('pending', 'automated')
      AND t.status IN ('todo', 'doing')
      AND (p_agent_type IS NULL OR t.agent_assigned = p_agent_type)
      AND check_dependencies_complete(t.id) = true
    ORDER BY
        CASE t.priority
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
            ELSE 5
        END,
        t.created_at ASC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get AI-PM task statistics
CREATE OR REPLACE FUNCTION get_aipm_task_stats(
    p_project_id UUID DEFAULT NULL,
    since_timestamp TIMESTAMPTZ DEFAULT NOW() - INTERVAL '7 days'
)
RETURNS TABLE (
    total_tasks BIGINT,
    automated_tasks BIGINT,
    pending_automation BIGINT,
    completed_by_agent BIGINT,
    failed_automation BIGINT,
    avg_completion_time_hours NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) AS total_tasks,
        COUNT(*) FILTER (WHERE t.automation_status = 'automated') AS automated_tasks,
        COUNT(*) FILTER (WHERE t.automation_status = 'pending') AS pending_automation,
        COUNT(*) FILTER (WHERE t.automation_status = 'automated' AND t.status = 'done') AS completed_by_agent,
        COUNT(*) FILTER (WHERE t.automation_status = 'failed') AS failed_automation,
        ROUND(AVG(
            EXTRACT(EPOCH FROM (t.updated_at - t.created_at)) / 3600
        )::NUMERIC, 2) AS avg_completion_time_hours
    FROM archon_tasks t
    WHERE t.created_at >= since_timestamp
      AND (p_project_id IS NULL OR t.project_id = p_project_id);
END;
$$ LANGUAGE plpgsql STABLE;

-- =====================================================
-- SECTION 5: UPDATE EXISTING TASKS (DATA MIGRATION)
-- =====================================================

-- Set default values for existing tasks
DO $$
BEGIN
    -- Set automation_status to 'manual' for all existing tasks
    UPDATE archon_tasks
    SET automation_status = 'manual'
    WHERE automation_status IS NULL;

    -- Set empty execution_metadata for tasks that don't have it
    UPDATE archon_tasks
    SET execution_metadata = '{}'
    WHERE execution_metadata IS NULL;

    RAISE NOTICE 'Updated existing tasks with default values';
END $$;

-- =====================================================
-- SECTION 6: TRIGGERS
-- =====================================================

-- Trigger function to auto-populate context_summary from description
CREATE OR REPLACE FUNCTION auto_generate_context_summary()
RETURNS TRIGGER AS $$
BEGIN
    -- Only generate if context_summary is NULL and description exists
    IF NEW.context_summary IS NULL AND NEW.description IS NOT NULL THEN
        -- Take first 500 characters of description as summary
        NEW.context_summary := LEFT(NEW.description, 500);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (only on INSERT, not UPDATE to avoid overwriting AI-generated summaries)
CREATE TRIGGER trigger_auto_context_summary
    BEFORE INSERT ON archon_tasks
    FOR EACH ROW
    EXECUTE FUNCTION auto_generate_context_summary();

-- =====================================================
-- SECTION 7: VERIFICATION
-- =====================================================

-- Verify all columns exist
DO $$
DECLARE
    column_count INTEGER;
BEGIN
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

    IF column_count < 8 THEN
        RAISE EXCEPTION 'Not all columns were added to archon_tasks (found %, expected 8)', column_count;
    END IF;

    RAISE NOTICE 'All AI-PM columns added to archon_tasks successfully!';
END $$;

-- Verify indexes exist
DO $$
DECLARE
    index_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'archon_tasks'
      AND indexname LIKE 'idx_tasks_%';

    RAISE NOTICE 'Found % indexes on archon_tasks', index_count;
END $$;

-- =====================================================
-- SECTION 8: EXAMPLE QUERIES
-- =====================================================

-- Example: Get all tasks ready for automation
-- SELECT * FROM get_ready_tasks('coding');

-- Example: Check if task can start (dependencies complete)
-- SELECT check_dependencies_complete('task-uuid-here');

-- Example: Get full dependency tree for a task
-- SELECT * FROM get_dependency_tree('task-uuid-here');

-- Example: Get AI-PM statistics for a project
-- SELECT * FROM get_aipm_task_stats('project-uuid-here');

-- Example: Get tasks by agent and status
-- SELECT * FROM get_tasks_by_agent('qa', 'doing');

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
-- Columns added: 8 new fields to archon_tasks
-- Indexes created: 7 indexes (including composite and GIN)
-- Constraints added: 3 check constraints
-- Helper functions: 5 functions created
-- Triggers: 1 trigger for auto-context summary
-- Data migration: Existing tasks updated with defaults
-- =====================================================
