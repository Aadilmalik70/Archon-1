# AI-PM Database Migrations

## Overview

This directory contains database migrations for the AI Product Manager feature. These migrations add tables, indexes, and functions required for autonomous AI-driven project management.

## Migration Files

| File | Purpose | Dependencies |
|------|---------|-------------|
| `001_core_tables.sql` | Core AI-PM tables (executions, configs) | None |
| `002_integration_tables.sql` | External service integrations (Slack, Asana) | 001 |
| `003_extend_tasks.sql` | Extend archon_tasks with AI-PM fields | 001, 002 |

## What Gets Created

### Tables

**From 001_core_tables.sql**:
- `ai_pm_executions` - Track all agent execution history
- `agent_configurations` - Store agent settings and preferences

**From 002_integration_tables.sql**:
- `integration_credentials` - Encrypted OAuth tokens and API keys
- `slack_channels` - Project → Slack channel mappings
- `asana_projects` - Project → Asana project mappings
- `task_sync_log` - Bidirectional sync history

**From 003_extend_tasks.sql**:
- Extends `archon_tasks` with 8 new columns for AI-PM functionality

### Indexes

- **23 indexes** total across all tables
- Optimized for common query patterns
- Includes composite and GIN indexes for arrays

### Functions

- **13 helper functions** for common operations
- Statistics, monitoring, and validation
- Dependency checking and task routing

### RLS Policies

- **11 Row Level Security policies**
- Service role: Full access
- Authenticated users: Read-only access (except credentials)

## Installation

### Prerequisites

1. Supabase project with admin access
2. `archon_tasks` table exists (from base Archon setup)
3. PostgreSQL 14+ (for array and JSONB features)

### Running Migrations

**Option 1: Supabase Dashboard** (Recommended)

1. Go to your Supabase project → SQL Editor
2. Run each migration in order:
   ```sql
   -- Copy and paste contents of each file in order:
   -- 1. 001_core_tables.sql
   -- 2. 002_integration_tables.sql
   -- 3. 003_extend_tasks.sql
   ```

**Option 2: psql CLI**

```bash
# Connect to your Supabase database
psql "postgresql://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT-REF].supabase.co:5432/postgres"

# Run migrations in order
\i migration/ai_pm/001_core_tables.sql
\i migration/ai_pm/002_integration_tables.sql
\i migration/ai_pm/003_extend_tasks.sql
```

**Option 3: Supabase CLI**

```bash
# Link to your project
supabase link --project-ref your-project-ref

# Run migrations
supabase db push

# Or run individually
psql $DATABASE_URL -f migration/ai_pm/001_core_tables.sql
psql $DATABASE_URL -f migration/ai_pm/002_integration_tables.sql
psql $DATABASE_URL -f migration/ai_pm/003_extend_tasks.sql
```

### Verification

After running all migrations, verify with:

```sql
-- Check all tables exist
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'ai_pm_executions',
    'agent_configurations',
    'integration_credentials',
    'slack_channels',
    'asana_projects',
    'task_sync_log'
  );
-- Should return 6 rows

-- Check archon_tasks has new columns
SELECT column_name
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
-- Should return 8 rows

-- Check helper functions exist
SELECT routine_name
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name LIKE '%ai%' OR routine_name LIKE '%sync%';
-- Should return multiple functions

-- Check RLS is enabled
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%ai_pm%' OR tablename LIKE '%integration%';
-- All should have rowsecurity = true
```

## Rollback

If you need to undo migrations (e.g., migration failed, testing in development):

### Complete Rollback (Remove Everything)

Run rollback scripts in **reverse order**:

```bash
# Reverse order is critical!
psql $DATABASE_URL -f migration/ai_pm/rollback_003_extend_tasks.sql
psql $DATABASE_URL -f migration/ai_pm/rollback_002_integration_tables.sql
psql $DATABASE_URL -f migration/ai_pm/rollback_001_core_tables.sql
```

**WARNING**: Rollback scripts have 5-second confirmation delays. Press Ctrl+C to cancel.

### Partial Rollback

You can rollback individual migrations:

```bash
# Only remove task extensions (keeps core tables and integrations)
psql $DATABASE_URL -f migration/ai_pm/rollback_003_extend_tasks.sql

# Only remove integrations (keeps core tables)
psql $DATABASE_URL -f migration/ai_pm/rollback_002_integration_tables.sql
```

**Note**: Rolling back 001 or 002 will CASCADE delete dependent data.

## Testing

### Smoke Tests

After migration, run these queries to ensure everything works:

```sql
-- Test 1: Insert test agent configuration
INSERT INTO agent_configurations (agent_type, enabled, config)
VALUES ('test_agent', true, '{"model": "gpt-4o", "temp": 0.5}')
RETURNING *;

-- Test 2: Check default configurations exist
SELECT agent_type, enabled FROM agent_configurations;
-- Should show: orchestrator, coding, qa, docs, security, performance

-- Test 3: Insert test execution
INSERT INTO ai_pm_executions (agent_type, status, input_context)
VALUES ('orchestrator', 'pending', '{"test": true}')
RETURNING execution_id;

-- Test 4: Test helper functions
SELECT * FROM get_active_executions();
SELECT * FROM get_execution_stats(NOW() - INTERVAL '1 day');

-- Test 5: Test task extensions
UPDATE archon_tasks
SET agent_assigned = 'coding',
    task_type = 'feature',
    automation_status = 'automated'
WHERE id = (SELECT id FROM archon_tasks LIMIT 1)
RETURNING *;

-- Test 6: Check dependencies work
SELECT check_dependencies_complete((SELECT id FROM archon_tasks LIMIT 1));

-- Test 7: Verify RLS policies
SET ROLE authenticated;
SELECT COUNT(*) FROM ai_pm_executions; -- Should work (read-only)
SET ROLE postgres; -- Reset
```

### Load Testing

```sql
-- Insert 1000 test executions
INSERT INTO ai_pm_executions (agent_type, status, input_context, tokens_used, cost_dollars)
SELECT
    (ARRAY['orchestrator', 'coding', 'qa', 'docs'])[floor(random() * 4 + 1)],
    (ARRAY['completed', 'failed', 'running'])[floor(random() * 3 + 1)],
    '{"test": true}',
    floor(random() * 5000)::INTEGER,
    (random() * 2)::DECIMAL(10, 4)
FROM generate_series(1, 1000);

-- Test query performance
EXPLAIN ANALYZE
SELECT * FROM get_execution_stats(NOW() - INTERVAL '7 days');

-- Cleanup
DELETE FROM ai_pm_executions WHERE input_context = '{"test": true}';
```

## Schema Details

### ai_pm_executions

```sql
execution_id       UUID PRIMARY KEY
task_id            UUID (FK to archon_tasks)
agent_type         VARCHAR(50) - orchestrator, coding, qa, docs, security, performance
status             VARCHAR(20) - pending, running, completed, failed, cancelled, timeout
input_context      JSONB - Full input provided to agent
output_result      JSONB - Structured agent output
execution_log      TEXT[] - Log entries for debugging
error_message      TEXT - Error details if failed
tokens_used        INTEGER - Token consumption tracking
cost_dollars       DECIMAL(10,4) - Cost tracking
started_at         TIMESTAMPTZ
completed_at       TIMESTAMPTZ
created_at         TIMESTAMPTZ
updated_at         TIMESTAMPTZ
```

### agent_configurations

```sql
config_id          UUID PRIMARY KEY
agent_type         VARCHAR(50) UNIQUE - Agent identifier
enabled            BOOLEAN - Active status
config             JSONB - {model, temperature, max_tokens, timeout_seconds, ...}
created_at         TIMESTAMPTZ
updated_at         TIMESTAMPTZ
```

### integration_credentials

```sql
credential_id      UUID PRIMARY KEY
service_name       VARCHAR(50) - slack, asana, github, jira, linear
credential_type    VARCHAR(50) - oauth_token, api_key, webhook_url, refresh_token
encrypted_value    TEXT - Bcrypt encrypted
metadata           JSONB - Service-specific data
expires_at         TIMESTAMPTZ
created_at         TIMESTAMPTZ
updated_at         TIMESTAMPTZ
```

### Extended archon_tasks Columns

```sql
agent_assigned     VARCHAR(50) - Agent handling this task
task_type          VARCHAR(50) - feature, bug, refactor, test, docs, etc.
context_summary    TEXT - AI-generated summary
dependencies       UUID[] - Array of task IDs
automation_status  VARCHAR(20) - manual, pending, automated, failed
execution_metadata JSONB - Execution details
asana_task_id      VARCHAR(100) - External sync reference
slack_thread_ts    VARCHAR(100) - Slack thread reference
```

## Common Queries

### Get Agent Performance

```sql
SELECT * FROM get_execution_stats(NOW() - INTERVAL '7 days');
```

### Find Ready-to-Execute Tasks

```sql
SELECT * FROM get_ready_tasks('coding');
```

### Check Task Dependencies

```sql
SELECT * FROM get_dependency_tree('your-task-uuid');
```

### Monitor Token Usage

```sql
SELECT
    agent_type,
    SUM(tokens_used) as total_tokens,
    SUM(cost_dollars) as total_cost,
    AVG(cost_dollars) as avg_cost
FROM ai_pm_executions
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY agent_type;
```

### Check Expiring OAuth Tokens

```sql
SELECT * FROM get_expiring_tokens(7); -- Next 7 days
```

### Get Sync Statistics

```sql
SELECT * FROM get_sync_statistics(NOW() - INTERVAL '24 hours');
```

## Troubleshooting

### Migration Fails with "relation does not exist"

**Cause**: Dependencies not met (e.g., archon_tasks doesn't exist)

**Solution**: Ensure base Archon schema is installed first

```sql
-- Check if archon_tasks exists
SELECT tablename FROM pg_tables WHERE tablename = 'archon_tasks';
```

### "function update_updated_at_column() does not exist"

**Cause**: Base Archon migrations not run

**Solution**: Run `migration/complete_setup.sql` first

### RLS Policies Block Access

**Cause**: Using wrong role

**Solution**: Ensure backend uses `service_role`, not `authenticated`

```javascript
// Correct - backend
const supabase = createClient(url, SERVICE_KEY);

// Incorrect - frontend (can't write to ai_pm tables)
const supabase = createClient(url, ANON_KEY);
```

### Slow Query Performance

**Cause**: Missing indexes or large dataset

**Solution**: Run VACUUM and ANALYZE

```sql
VACUUM ANALYZE ai_pm_executions;
VACUUM ANALYZE task_sync_log;
```

## Next Steps

After migrations complete:

1. **Backend Integration**:
   - Implement service layer (`python/src/server/services/ai_pm/`)
   - Create API routes (`python/src/server/api_routes/ai_pm_api.py`)
   - Build orchestrator agent (`python/src/agents/product_manager/`)

2. **External Integrations**:
   - Set up Slack OAuth
   - Set up Asana OAuth
   - Configure webhook endpoints

3. **Frontend**:
   - Create AI-PM dashboard (`archon-ui-main/src/features/ai-pm/`)
   - Add integration setup UI
   - Build execution viewer

## Support

For issues or questions:
- Review error messages in migration output
- Check Supabase logs for detailed errors
- Verify PostgreSQL version (14+ required)
- Ensure all dependencies are met

## Migration History

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 001 | 2025-10-20 | AI-PM Team | Core tables and agent configs |
| 002 | 2025-10-20 | AI-PM Team | Integration tables for Slack/Asana |
| 003 | 2025-10-20 | AI-PM Team | Extended archon_tasks for AI-PM |

---

**Database Migrations Complete** ✅

Total: 6 new tables, 8 extended columns, 23 indexes, 13 functions, 11 RLS policies
