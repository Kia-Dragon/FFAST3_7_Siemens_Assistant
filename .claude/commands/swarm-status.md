# Swarm Status Check

Check the health and progress of the currently running swarm.

## Instructions

1. Read the team config file to discover all teammates:
   - Look for `~/.claude/teams/*/config.json` (use Glob to find active teams)
   - List each teammate's name, type, and current state

2. Read the task list to assess progress:
   - Look for `~/.claude/tasks/*/` (use Glob to find task files)
   - Count: total tasks, completed, in_progress, pending, blocked

3. Identify problems:
   - Any teammate idle with incomplete assigned tasks? → Flag as potentially stuck
   - Any task in_progress for an unusually long time? → Flag for investigation
   - Any blocked tasks where the blocker is already complete? → Flag stale dependency

4. Report in this format:

```
## Swarm Status

**Team:** {team-name}
**Teammates:** N active

| Teammate | Type | State | Current Task |
|----------|------|-------|-------------|
| name     | role | active/idle | task or "none" |

**Task Progress:** N/M completed (X%)

| Status | Count |
|--------|-------|
| Completed | N |
| In Progress | N |
| Pending | N |
| Blocked | N |

**Alerts:**
- [any issues found, or "None"]
```

5. If no active team is found, report: "No active swarm found. Teams directory is empty."
