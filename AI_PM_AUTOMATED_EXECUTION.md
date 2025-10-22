# AI-PM Automated Execution System

## Overview

The AI-PM Automated Execution System enables **fully autonomous feature implementation** by automatically executing tasks using Claude Code CLI immediately after they are created through Slack commands.

## Architecture

```
User sends /aipm create in Slack
         ↓
Orchestrator Agent breaks down feature into tasks
         ↓
Tasks saved to database
         ↓
Breakdown summary posted to Slack
         ↓
🚀 Feature Executor auto-triggers (if AUTO_EXECUTE_TASKS=true)
         ↓
For each task (sequential execution):
  - Update status to "executing"
  - Send "Task X/Y started" to Slack
  - Call Claude Code CLI with task prompt
  - Wait for Claude Code to complete
  - Parse execution result (success/failed)
  - Update task status to "done" or "review"
  - Send "Task X/Y complete" to Slack with details
  - Retry up to 3 times if failed
         ↓
Send "Feature complete" summary to Slack
```

## Components

### 1. **ClaudeCodeExecutor** (`python/src/agents/claude_code_executor/claude_agent.py`)

Executes individual tasks by running Claude Code CLI as a subprocess.

**Key Responsibilities:**
- Build comprehensive prompts from task details
- Execute Claude Code CLI with subprocess management
- Parse Claude Code output to extract:
  - Success/failure status
  - Files modified
  - Test results
  - Error messages
- Handle timeouts and errors gracefully

**Prompt Format:**
```
You are implementing a task for the Archon project.

TASK: [task title]

DESCRIPTION: [task description with acceptance criteria]

ACCEPTANCE CRITERIA:
  1. [criterion 1]
  2. [criterion 2]
  ...

FILES TO MODIFY:
  - [file 1]
  - [file 2]
  ...

EXECUTION REQUIREMENTS:
1. Implement solution following acceptance criteria
2. Create/modify files as specified
3. Run all relevant tests
4. Output "ARCHON_TASK_COMPLETE" when done
5. Output "ARCHON_TASK_FAILED: [reason]" if error
```

### 2. **FeatureExecutor** (`python/src/agents/product_manager/feature_executor.py`)

Orchestrates execution of all tasks for a feature.

**Key Responsibilities:**
- Fetch all tasks for feature from database (sorted by task_order)
- Execute tasks sequentially to handle dependencies
- Implement retry logic (3 attempts with exponential backoff)
- Update task status in database (todo → executing → done/review)
- Coordinate with ProgressReporter for Slack notifications
- Track overall execution statistics

**Retry Logic:**
- Attempt 1: Immediate
- Attempt 2: Wait 2 seconds
- Attempt 3: Wait 4 seconds
- If all fail: Mark task as "review"

### 3. **ProgressReporter** (Enhanced)

Sends real-time progress updates to Slack.

**New Notification Methods:**
- `notify_task_execution_started()` - "🤖 Executing task 1/6"
- `notify_task_execution_completed()` - "✅ Task 1/6 complete" with file list and test results
- `notify_feature_execution_complete()` - "🎉 Feature complete: 6/6 tasks successful"

**Slack Message Details:**
- Progress bar (visual representation)
- Files modified (up to 5, then "... and X more")
- Test pass/fail status
- Error details if failed
- Task number (e.g., "Task 3/8")

### 4. **Auto-Trigger Integration** (`python/src/server/integrations/slack/slack_events.py`)

Automatically triggers feature execution after tasks are created.

**Trigger Conditions:**
1. `AUTO_EXECUTE_TASKS=true` in environment
2. Tasks successfully created in database
3. No errors during orchestrator phase

**Execution Mode:**
- Asynchronous (fire-and-forget)
- Runs in background thread
- Does not block Slack command response

## Setup Instructions

### Prerequisites

1. **Claude Code CLI installed:**
   ```bash
   # Install Claude Code CLI (adjust based on your installation method)
   npm install -g claude-code
   # OR
   pip install claude-code
   ```

2. **Anthropic API Key:**
   Required for Claude Code to work.

3. **Working Directory:**
   Ensure Claude Code has write access to your workspace directory.

### Configuration

1. **Update `.env` file:**

```bash
# Enable automated execution
AUTO_EXECUTE_TASKS=true

# Path to Claude Code CLI (optional, uses PATH if empty)
CLAUDE_CODE_PATH=/usr/local/bin/claude-code

# Working directory (optional, uses current directory if empty)
WORKSPACE_PATH=/path/to/your/workspace

# Execution timeout in seconds (optional, default: 600)
CLAUDE_CODE_TIMEOUT=600

# Required: Anthropic API key (for Claude Code)
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

2. **Restart Archon server:**

```bash
docker compose restart archon-server
```

3. **Verify configuration:**

Check server logs for confirmation:
```bash
docker compose logs archon-server | grep "Auto-execution"
```

You should see:
```
Auto-execution enabled, triggering feature executor for 6 tasks
Feature executor triggered in background
```

## Usage

### Automated Workflow

1. **Create feature via Slack:**

```
/aipm create feature: Add user profile page with avatar upload
```

2. **Orchestrator responds immediately:**

```
🤖 Creating tasks for: Add user profile page with avatar upload

The AI-PM is analyzing your request...
```

3. **Within 30-40 seconds, you'll see:**

```
✅ Created 8 tasks for user profile feature

📋 Task Breakdown:
1. Create database schema for user profiles
2. Implement backend API for profile management
3. Create profile page UI component
... [and 5 more]

🎯 MCP Command for Claude Code:
find_tasks(project_id="...")
```

4. **If AUTO_EXECUTE_TASKS=true, automated execution starts:**

```
🤖 Automated Execution: Task 1/8
Create database schema for user profiles
Assignee: coding
Status: todo → executing
Progress: ░░░░░░░░░░ 0%
```

5. **After each task completes:**

```
✅ Task 1/8 Complete

Create database schema for user profiles
Status: executing → done

Files Modified:
  • migrations/user_profile.sql
  • migrations/20250121_add_profiles.sql

Tests: ✅ Passed
Progress: █░░░░░░░░░ 10%
```

6. **Final summary after all tasks:**

```
🎉 Feature Implementation Complete!

Feature: Add user profile page with avatar upload

Total Tasks: 8
Successful: ✅ 8
Failed: ❌ 0
Success Rate: 100%

Files Modified: 12
Execution: Automated via Claude Code
```

### Manual Mode (AUTO_EXECUTE_TASKS=false)

If auto-execution is disabled, you can manually execute tasks via Claude Code:

1. **In Claude Code, ask:**

```
List all todo tasks for project [project-id]
```

2. **Implement tasks manually:**

```
Implement task: "Create database schema for user profiles"
```

## Task Execution Details

### Success Criteria

A task is marked "done" if:
1. Claude Code completes without errors
2. Output contains "ARCHON_TASK_COMPLETE"
3. Tests pass (if tests are run)

### Failure Handling

A task is marked "review" if:
1. Claude Code returns error
2. Output contains "ARCHON_TASK_FAILED"
3. Tests fail
4. All 3 retry attempts fail

### Retry Behavior

- **Attempt 1:** Immediate execution
- **Attempt 2:** Wait 2 seconds, retry
- **Attempt 3:** Wait 4 seconds, retry
- **After 3 failures:** Mark as "review" and continue to next task

## Monitoring

### Server Logs

Monitor execution in real-time:

```bash
# Watch all execution logs
docker compose logs -f archon-server | grep -E "(Executing|Task complete|Feature executor)"

# Watch specific task
docker compose logs -f archon-server | grep "Task 1/6"
```

### Slack Notifications

All progress updates are sent to the linked Slack channel:
- Task started notifications
- Task completed notifications (with files modified, test results)
- Feature complete summary
- Error notifications if failures occur

### Database

Check task status directly:

```sql
SELECT id, title, status, assignee, updated_at
FROM archon_tasks
WHERE project_id = 'your-project-id'
ORDER BY task_order;
```

## Troubleshooting

### Issue: Tasks not auto-executing

**Solution:**

1. Check environment variable:
   ```bash
   docker compose exec archon-server env | grep AUTO_EXECUTE_TASKS
   ```

2. Check server logs:
   ```bash
   docker compose logs archon-server | grep "Auto-execution"
   ```

3. Verify configuration in `.env`:
   ```
   AUTO_EXECUTE_TASKS=true  # Make sure it's lowercase "true"
   ```

4. Restart server:
   ```bash
   docker compose restart archon-server
   ```

### Issue: Claude Code not found

**Solution:**

1. Verify Claude Code is installed:
   ```bash
   docker compose exec archon-server which claude-code
   ```

2. Set explicit path in `.env`:
   ```
   CLAUDE_CODE_PATH=/usr/local/bin/claude-code
   ```

3. Restart server

### Issue: Tasks failing with "timeout"

**Solution:**

1. Increase timeout in `.env`:
   ```
   CLAUDE_CODE_TIMEOUT=1200  # 20 minutes
   ```

2. Check if tasks are too complex (consider breaking down)

3. Review server logs for actual error

### Issue: No Slack notifications

**Solution:**

1. Verify Slack channel is linked to project:
   ```sql
   SELECT * FROM slack_channels WHERE project_id = 'your-project-id';
   ```

2. Check AIPM bot is in channel:
   - In Slack, type: `/invite @aipm`

3. Verify Slack credentials in `.env`

## Performance Considerations

### Execution Time

Typical execution times per task:
- **Simple task** (1-2 files): 30-60 seconds
- **Medium task** (3-5 files): 1-3 minutes
- **Complex task** (6+ files, tests): 3-10 minutes

Total feature time: Number of tasks × Average task time

### Resource Usage

- **Memory:** ~500MB per Claude Code subprocess
- **CPU:** Moderate (parsing, file I/O)
- **Network:** Minimal (Anthropic API calls only)

### Optimization Tips

1. **Break down large features into smaller tasks**
   - Faster individual task execution
   - Better progress visibility
   - Easier retry on failure

2. **Use specific file paths in tasks**
   - Helps Claude Code find relevant files faster
   - Reduces execution time

3. **Include clear acceptance criteria**
   - Claude Code understands requirements better
   - Fewer retry attempts needed

## Security Considerations

### Code Execution

Claude Code executes arbitrary code generated by AI:
- **Risk:** Potential for unintended file modifications
- **Mitigation:** Review tasks marked "review" before deployment
- **Recommendation:** Use in development/staging environments only

### API Key Security

Anthropic API key grants code generation capabilities:
- Store in environment variables only
- Never commit to source control
- Rotate regularly
- Monitor usage in Anthropic dashboard

### Workspace Isolation

Claude Code has write access to workspace:
- Use dedicated workspace directory
- Run in isolated container (Docker)
- Review file modifications before committing

## Future Enhancements

- [ ] Parallel task execution (for independent tasks)
- [ ] Smart dependency detection (auto-detect task order)
- [ ] Code review agent (validates Claude Code output)
- [ ] Rollback mechanism (undo failed tasks)
- [ ] Human-in-the-loop mode (ask for approval before each task)
- [ ] Integration testing (run full test suite after feature)
- [ ] GitHub PR automation (auto-create PR when feature complete)

## Support

For issues or questions:
- Check server logs first
- Review this documentation
- Open GitHub issue with logs and configuration
