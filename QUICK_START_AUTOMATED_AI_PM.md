# Quick Start: Automated AI-PM System

## 🚀 Enable Automation in 3 Steps

### Step 1: Update Configuration

Edit `python/.env`:

```bash
# Enable automated execution
AUTO_EXECUTE_TASKS=true

# Required: Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

### Step 2: Restart Server

```bash
docker compose restart archon-server
```

### Step 3: Test in Slack

In your Slack #test-channle:

```
/aipm create feature: Add logout button
```

## ✅ What Happens Next (Automatically)

```
13:00:00 | You: /aipm create feature: Add logout button

13:00:05 | Slack: ✅ Created 4 tasks for logout button feature
           1. Add logout API endpoint
           2. Create logout button component
           3. Wire up button to API
           4. Add tests

13:00:10 | Slack: 🤖 Automated Execution: Task 1/4
           Add logout API endpoint
           Status: todo → executing
           Progress: ░░░░░░░░░░ 0%

13:01:30 | Slack: ✅ Task 1/4 Complete
           Files Modified:
             • services/auth_service.py
             • api_routes/auth_api.py
           Tests: ✅ Passed
           Progress: ██░░░░░░░░ 25%

... continues automatically for all 4 tasks ...

13:05:00 | Slack: 🎉 Feature Implementation Complete!
           Total Tasks: 4
           Successful: ✅ 4
           Failed: ❌ 0
           Success Rate: 100%
           Files Modified: 8
```

**Total time: ~5 minutes (fully automated)**
**Your effort: ZERO (just watch Slack notifications)**

## 📊 Monitor Execution

### Watch Real-Time Logs

```bash
docker compose logs -f archon-server | grep -E "(Task|Feature executor)"
```

### Check Task Status in UI

Visit: http://localhost:3737/projects/your-project

You'll see tasks moving through statuses:
- `todo` → `executing` → `done`

### Slack Notifications

All updates sent to your Slack channel:
- Task started (with progress bar)
- Task completed (with files modified and test results)
- Feature complete (with summary)

## 🛠️ Advanced Configuration

### Adjust Timeout

For complex tasks, increase timeout:

```bash
# In python/.env
CLAUDE_CODE_TIMEOUT=1200  # 20 minutes
```

### Set Custom Workspace

```bash
WORKSPACE_PATH=/path/to/your/workspace
```

### Disable Automation

To go back to manual mode:

```bash
AUTO_EXECUTE_TASKS=false
```

Then restart:

```bash
docker compose restart archon-server
```

## 🐛 Troubleshooting

### Issue: No auto-execution happening

**Check environment:**
```bash
docker compose exec archon-server env | grep AUTO_EXECUTE_TASKS
```

Should return: `AUTO_EXECUTE_TASKS=true`

If not, update `.env` and restart.

### Issue: Tasks failing

**Check logs:**
```bash
docker compose logs archon-server | tail -100
```

Look for error messages with details.

**Common causes:**
- Claude Code not installed
- Invalid Anthropic API key
- Timeout too short for complex tasks
- File permission issues

### Issue: No Slack notifications

**Verify bot is in channel:**
```
/invite @aipm
```

**Check channel is linked:**

Visit Archon UI → Projects → Your Project → Settings → Check Slack channel link

## 📖 Full Documentation

For complete details, see:
- `AI_PM_AUTOMATED_EXECUTION.md` - Full documentation
- `AI_PM_PHASE_2_COMPLETE.md` - Implementation summary
- `CLAUDE.md` - General Archon documentation

## 🎯 Example Use Cases

### Create a Login Feature

```
/aipm create feature: Add login form with email and password validation
```

Result: 6-8 tasks automatically implemented in 5-15 minutes

### Add a New API Endpoint

```
/aipm create feature: Add /api/users/search endpoint with filters
```

Result: 4-6 tasks automatically implemented in 3-8 minutes

### Build a UI Component

```
/aipm create feature: Create user profile card component with avatar
```

Result: 5-7 tasks automatically implemented in 4-10 minutes

## ✅ Success Checklist

After your first automated execution:

- [ ] Received "Created X tasks" message in Slack
- [ ] Received "Task 1/X started" notification
- [ ] Received "Task 1/X complete" with file list
- [ ] Received "Feature complete" summary
- [ ] Files modified in workspace
- [ ] Tests passed (if tests exist)
- [ ] Tasks marked "done" in Archon UI

If all checkboxes ticked: **Success!** 🎉

## 🚀 What's Next?

1. **Test more features** - Try different types of tasks
2. **Review code quality** - Check AI-generated code
3. **Adjust configuration** - Fine-tune timeout, workspace
4. **Report issues** - Help improve the system
5. **Phase 3** - Stay tuned for parallel execution, code review, and more!

---

**Ready to automate your development workflow!**
**Questions? Check `AI_PM_AUTOMATED_EXECUTION.md` for details.**
