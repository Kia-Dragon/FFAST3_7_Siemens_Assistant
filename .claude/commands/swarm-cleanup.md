# Swarm Cleanup

Safely tear down a swarm and clean up all team infrastructure.

## Instructions

### Step 1: Discover Active Team

Read the team config to identify all teammates:
- Glob for `~/.claude/teams/*/config.json`
- List all registered teammates by name

If no active team is found, report "No active swarm to clean up" and stop.

### Step 2: Graceful Shutdown

Send shutdown requests to each teammate:

```
For each teammate in the team:
  SendMessage type: "shutdown_request" to teammate
  Wait for acknowledgment
```

**Important:** Teammates that are stuck on a permission prompt or mid-turn CANNOT process shutdown requests. If a shutdown request is not acknowledged within ~30 seconds, note it as stuck.

### Step 3: Verify All Teammates Stopped

Check that all teammates have acknowledged shutdown. If any remain active:
- Try sending the shutdown request again (one retry)
- If still stuck after retry, report which teammates are unresponsive

### Step 4: Clean Up Team Resources

If all teammates have shut down:
- Use TeamDelete to remove the team

If TeamDelete fails because teammates are still "active":
- Report the failure
- Provide the manual cleanup commands:

```
Manual cleanup (use only if TeamDelete fails):
  rm -rf ~/.claude/teams/{team-name}
  rm -rf ~/.claude/tasks/{team-name}
```

- Ask for user confirmation before running manual cleanup

### Step 5: Report

```
## Swarm Cleanup Report

**Team:** {team-name}
**Teammates shut down:** N/M
**Stuck teammates:** [list or "none"]
**Team resources cleaned:** YES/NO
**Manual cleanup required:** YES/NO
```

## Known Issues

- A teammate blocked on a Bash permission prompt cannot receive or process shutdown requests
- TeamDelete will refuse to clean up while any member shows as "active" even if they are stuck
- The safest prevention is to use `Explore` subagent type for read-only roles (no Bash access = no permission freezes)
- If manual cleanup is needed, the directories to delete are:
  - `~/.claude/teams/{team-name}/` (team config and member registry)
  - `~/.claude/tasks/{team-name}/` (shared task list)
