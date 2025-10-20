-- =====================================================
-- AI-PM Core Tables Migration
-- =====================================================
-- Creates core tables for AI Product Manager functionality:
-- - ai_pm_executions: Track agent execution history
-- - agent_configurations: Store agent settings and preferences
--
-- Run this migration first before other AI-PM features
-- =====================================================

-- =====================================================
-- SECTION 1: AI-PM EXECUTIONS TABLE
-- =====================================================

-- Track all AI-PM agent executions with full context and results
CREATE TABLE IF NOT EXISTS ai_pm_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES archon_tasks(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    input_context JSONB NOT NULL DEFAULT '{}',
    output_result JSONB DEFAULT '{}',
    execution_log TEXT[] DEFAULT '{}',
    error_message TEXT,
    tokens_used INTEGER DEFAULT 0,
    cost_dollars DECIMAL(10, 4) DEFAULT 0.0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_agent_type CHECK (
        agent_type IN ('orchestrator', 'coding', 'qa', 'docs', 'security', 'performance')
    ),
    CONSTRAINT check_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')
    )
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ai_pm_executions_task ON ai_pm_executions(task_id);
CREATE INDEX IF NOT EXISTS idx_ai_pm_executions_status ON ai_pm_executions(status);
CREATE INDEX IF NOT EXISTS idx_ai_pm_executions_agent_type ON ai_pm_executions(agent_type);
CREATE INDEX IF NOT EXISTS idx_ai_pm_executions_created ON ai_pm_executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_pm_executions_agent_status ON ai_pm_executions(agent_type, status);

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER update_ai_pm_executions_updated_at
    BEFORE UPDATE ON ai_pm_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE ai_pm_executions IS 'Tracks all AI-PM agent execution history with input context, output results, and performance metrics';
COMMENT ON COLUMN ai_pm_executions.agent_type IS 'Type of agent: orchestrator, coding, qa, docs, security, performance';
COMMENT ON COLUMN ai_pm_executions.status IS 'Execution status: pending, running, completed, failed, cancelled, timeout';
COMMENT ON COLUMN ai_pm_executions.input_context IS 'Full input context provided to the agent (feature description, code context, etc.)';
COMMENT ON COLUMN ai_pm_executions.output_result IS 'Structured output from the agent (task breakdown, code changes, test results, etc.)';
COMMENT ON COLUMN ai_pm_executions.execution_log IS 'Array of log entries from agent execution for debugging';
COMMENT ON COLUMN ai_pm_executions.tokens_used IS 'Total tokens consumed by this execution (for cost tracking)';
COMMENT ON COLUMN ai_pm_executions.cost_dollars IS 'Estimated cost in USD for this execution';

-- =====================================================
-- SECTION 2: AGENT CONFIGURATIONS TABLE
-- =====================================================

-- Store configuration and settings for each agent type
CREATE TABLE IF NOT EXISTS agent_configurations (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT true,
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT check_agent_config_type CHECK (
        agent_type IN ('orchestrator', 'coding', 'qa', 'docs', 'security', 'performance')
    )
);

-- Trigger to automatically update updated_at timestamp
CREATE TRIGGER update_agent_configurations_updated_at
    BEFORE UPDATE ON agent_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE agent_configurations IS 'Configuration and settings for each AI agent type';
COMMENT ON COLUMN agent_configurations.agent_type IS 'Unique identifier for agent type';
COMMENT ON COLUMN agent_configurations.enabled IS 'Whether this agent is currently active and can be used';
COMMENT ON COLUMN agent_configurations.config IS 'Agent-specific configuration (model, temperature, max_tokens, timeout, etc.)';

-- =====================================================
-- SECTION 3: INSERT DEFAULT CONFIGURATIONS
-- =====================================================

-- Insert default configurations for all agent types
INSERT INTO agent_configurations (agent_type, enabled, config) VALUES
(
    'orchestrator',
    true,
    '{
        "model": "openai:gpt-4o",
        "temperature": 0.7,
        "max_tokens": 4000,
        "timeout_seconds": 120,
        "retries": 3,
        "max_tasks_per_breakdown": 20,
        "cost_limit_per_execution": 1.0
    }'
),
(
    'coding',
    true,
    '{
        "model": "openai:gpt-4o",
        "temperature": 0.3,
        "max_tokens": 8000,
        "timeout_seconds": 180,
        "retries": 3,
        "max_files_per_change": 10,
        "enable_code_review": true
    }'
),
(
    'qa',
    true,
    '{
        "model": "openai:gpt-4o",
        "temperature": 0.2,
        "max_tokens": 4000,
        "timeout_seconds": 300,
        "retries": 3,
        "run_unit_tests": true,
        "run_integration_tests": true,
        "enable_security_scan": true,
        "min_coverage_threshold": 80
    }'
),
(
    'docs',
    true,
    '{
        "model": "openai:gpt-4o",
        "temperature": 0.5,
        "max_tokens": 6000,
        "timeout_seconds": 120,
        "retries": 3,
        "update_readme": true,
        "update_api_docs": true,
        "generate_comments": true
    }'
),
(
    'security',
    false,
    '{
        "model": "openai:gpt-4o",
        "temperature": 0.1,
        "max_tokens": 4000,
        "timeout_seconds": 180,
        "retries": 3,
        "scan_dependencies": true,
        "check_owasp_top_10": true,
        "severity_threshold": "medium"
    }'
),
(
    'performance',
    false,
    '{
        "model": "openai:gpt-4o",
        "temperature": 0.3,
        "max_tokens": 4000,
        "timeout_seconds": 180,
        "retries": 3,
        "benchmark_threshold_ms": 500,
        "check_memory_usage": true,
        "enable_profiling": true
    }'
)
ON CONFLICT (agent_type) DO NOTHING;

-- =====================================================
-- SECTION 4: ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on both tables
ALTER TABLE ai_pm_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_configurations ENABLE ROW LEVEL SECURITY;

-- Policy for service role (backend) - full access
CREATE POLICY "Service role full access to executions" ON ai_pm_executions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access to agent configs" ON agent_configurations
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy for authenticated users - read-only access
CREATE POLICY "Authenticated users can read executions" ON ai_pm_executions
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can read agent configs" ON agent_configurations
    FOR SELECT
    TO authenticated
    USING (true);

-- =====================================================
-- SECTION 5: HELPER FUNCTIONS
-- =====================================================

-- Function to get active agent executions
CREATE OR REPLACE FUNCTION get_active_executions()
RETURNS TABLE (
    execution_id UUID,
    agent_type VARCHAR(50),
    status VARCHAR(20),
    started_at TIMESTAMPTZ,
    duration_seconds INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.execution_id,
        e.agent_type,
        e.status,
        e.started_at,
        EXTRACT(EPOCH FROM (NOW() - e.started_at))::INTEGER AS duration_seconds
    FROM ai_pm_executions e
    WHERE e.status IN ('pending', 'running')
    ORDER BY e.started_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to get execution statistics
CREATE OR REPLACE FUNCTION get_execution_stats(
    since_timestamp TIMESTAMPTZ DEFAULT NOW() - INTERVAL '24 hours'
)
RETURNS TABLE (
    agent_type VARCHAR(50),
    total_executions BIGINT,
    successful_executions BIGINT,
    failed_executions BIGINT,
    avg_duration_seconds NUMERIC,
    total_tokens_used BIGINT,
    total_cost_dollars NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.agent_type,
        COUNT(*) AS total_executions,
        COUNT(*) FILTER (WHERE e.status = 'completed') AS successful_executions,
        COUNT(*) FILTER (WHERE e.status = 'failed') AS failed_executions,
        ROUND(AVG(EXTRACT(EPOCH FROM (e.completed_at - e.started_at)))::NUMERIC, 2) AS avg_duration_seconds,
        SUM(e.tokens_used) AS total_tokens_used,
        SUM(e.cost_dollars) AS total_cost_dollars
    FROM ai_pm_executions e
    WHERE e.created_at >= since_timestamp
    GROUP BY e.agent_type
    ORDER BY total_executions DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- =====================================================
-- SECTION 6: VERIFICATION
-- =====================================================

-- Verify tables exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ai_pm_executions') THEN
        RAISE EXCEPTION 'Table ai_pm_executions was not created';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'agent_configurations') THEN
        RAISE EXCEPTION 'Table agent_configurations was not created';
    END IF;

    RAISE NOTICE 'AI-PM core tables created successfully!';
END $$;

-- Verify default configurations inserted
DO $$
DECLARE
    config_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO config_count FROM agent_configurations;

    IF config_count < 4 THEN
        RAISE WARNING 'Expected at least 4 default agent configurations, found %', config_count;
    ELSE
        RAISE NOTICE 'Default agent configurations inserted: %', config_count;
    END IF;
END $$;

-- =====================================================
-- MIGRATION COMPLETE
-- =====================================================
-- Tables created:
--   - ai_pm_executions (with 6 indexes)
--   - agent_configurations
-- RLS policies: 4 policies created
-- Helper functions: 2 functions created
-- Default data: 6 agent configurations
-- =====================================================
