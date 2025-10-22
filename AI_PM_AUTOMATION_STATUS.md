# AI-PM Automation Status

## ✅ INSTALLATION COMPLETE

### What's Installed & Working

1. **Node.js v20.19.5** - Installed in archon-server container
2. **Claude CLI v2.0.25** - Installed via `@anthropic-ai/claude-code` npm package
3. **Binary Path**: `/usr/bin/claude` (command: `claude`)
4. **Configuration**:
   - `AUTO_EXECUTE_TASKS=true`
   - `CLAUDE_CODE_PATH=claude`
   - `CLAUDE_CODE_TIMEOUT=600` (10 minutes)
   - `WORKSPACE_PATH=/app`

5. **Code Fixes Applied**:
   - Fixed import error in `feature_executor.py`
   - Fixed empty environment variable handling in `claude_agent.py`
   - Updated `.env` configuration

### ⚠️ REQUIRED: Set Anthropic API Key

The automation requires an Anthropic API key to function:

1. Get your API key from: https://console.anthropic.com/
2. Add to `.env` file:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```
3. Restart server:
   ```bash
   docker compose restart archon-server
   ```

## How Automated Execution Works

### Workflow

1. User sends `/aipm create feature: Add logout button` in Slack
2. AI-PM Product Manager creates structured tasks in database
3. **FeatureExecutor automatically starts** (if `AUTO_EXECUTE_TASKS=true`)
4. For each task (in order by `task_order`):
   - Status updated: `todo` → `executing`
   - **ClaudeCodeExecutor invokes Claude CLI**
   - Claude CLI reads task prompt and implements code
   - Files are modified in `/app` directory
   - Status updated: `executing` → `done` (success) or `review` (needs attention)
   - Slack notification sent with progress
5. Final summary sent to Slack with all results

### Retry Logic

- Each task gets 3 attempts maximum
- Exponential backoff: 2s, 4s, 8s between retries
- Failed tasks marked as `review` for human attention

## Testing Automation

### Test with Simple Feature

```bash
# In Slack
/aipm create feature: Add a simple hello world function

# Expected behavior:
# 1. Product Manager creates 4-6 tasks
# 2. Automated execution starts immediately
# 3. Slack notifications show progress
# 4. Code appears in /app directory
# 5. All tasks complete or move to review
```

### Monitoring Execution

```bash
# Watch server logs
docker compose logs -f archon-server | grep -E "(Claude Code|Task|ARCHON_TASK)"

# Check task status
# View in Slack or query database directly
```

## Configuration Reference

### Environment Variables (.env)

```bash
# Enable/disable automation
AUTO_EXECUTE_TASKS=true

# Claude CLI command (installed at /usr/bin/claude)
CLAUDE_CODE_PATH=claude

# Working directory for code execution
WORKSPACE_PATH=  # Empty = /app (container default)

# Max execution time per task
CLAUDE_CODE_TIMEOUT=600  # 10 minutes

# REQUIRED: Your Anthropic API key
ANTHROPIC_API_KEY=  # ⚠️ MUST BE SET
```

### Key Files

- **Executor**: `python/src/agents/product_manager/feature_executor.py`
- **Claude Agent**: `python/src/agents/claude_code_executor/claude_agent.py`
- **Slack Integration**: `python/src/server/integrations/slack/slack_events.py`
- **Progress Reporting**: `python/src/agents/product_manager/progress_reporter.py`

## Troubleshooting

### Check Claude CLI

```bash
docker compose exec archon-server which claude
docker compose exec archon-server claude --help
```

### Check Environment

```bash
docker compose exec archon-server env | grep CLAUDE_CODE
docker compose exec archon-server env | grep ANTHROPIC
```

### Check Python Configuration

```bash
docker compose exec archon-server python -c "from src.agents.claude_code_executor.claude_agent import ClaudeCodeExecutor; executor = ClaudeCodeExecutor(); print(f'Path: {executor.claude_code_path}'); print(f'Workspace: {executor.workspace_path}')"
```

### Common Issues

1. **"No such file or directory: 'claude'"**
   - Solution: Run `docker compose exec archon-server which claude` to verify installation
   - If missing, Node.js or npm package wasn't installed properly

2. **"Claude Code execution failed: API key not set"**
   - Solution: Set `ANTHROPIC_API_KEY` in `.env` and restart

3. **"Task execution timed out"**
   - Solution: Increase `CLAUDE_CODE_TIMEOUT` for complex tasks

4. **"Permission denied"**
   - Solution: Check file permissions in `/app` directory

## Docker Build Issue (Separate Problem)

The Docker build is currently failing during Python dependency installation (UV stage). This is UNRELATED to Claude Code CLI installation.

**Current Workaround**: Claude CLI was installed directly in the running container using:
```bash
docker compose exec archon-server apt-get install -y curl nodejs npm
docker compose exec archon-server npm install -g @anthropic-ai/claude-code
```

**Note**: This installation is temporary and will be lost if container is rebuilt. The Dockerfile.server has been updated to include Node.js and Claude CLI installation for future builds.

## Next Steps

1. ✅ Set `ANTHROPIC_API_KEY` in `.env`
2. ✅ Restart server: `docker compose restart archon-server`
3. ✅ Test with simple feature via `/aipm create feature: ...`
4. ✅ Monitor logs and Slack notifications
5. ✅ Review generated code
6. ⏸️ Fix Docker build issue (optional, for permanent installation)

## Success Criteria

When everything is working, you should see:
- ✅ Tasks created in database
- ✅ Auto-execution starts immediately
- ✅ Slack progress notifications
- ✅ Code files modified in workspace
- ✅ Task status updates (todo → executing → done/review)
- ✅ Final summary in Slack

**The automation is ready to test once the Anthropic API key is set!**
