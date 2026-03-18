# Swarm Protocol — Detailed Workflow

Complete operational guide for running agent team (swarm) operations on this project.

---

## Pre-Flight Checklist

Before spawning any agents, complete these steps:

| # | Check | How |
|---|-------|-----|
| 1 | **Define the task clearly** | Write a 1-2 sentence goal. What are the inputs? What are the outputs? |
| 2 | **Inventory the files** | List all source files with approximate line counts. Total them. |
| 3 | **Assess parallelizability** | Can the work be split so no two agents touch the same file? If not, reconsider. |
| 4 | **Decide team composition** | Default: 2 Engineers + 2 Reviewers. Adjust based on scope. |
| 5 | **Plan scope splits** | Each Engineer: max ~15,000 lines. Each Reviewer: max ~15 files. |
| 6 | **Prepare output format template** | Define the exact format deliverables should follow. Paste into spawn prompts. |
| 7 | **Need context gathering?** | If Engineers need architectural context, spawn a Researcher first (see below). |

---

## Spawn Sequence

### Step 1: Researcher (Optional)

Spawn a Researcher subagent *before* creating the team. This is a Task subagent, not a team member.

```
Task tool:
  subagent_type: Explore
  prompt: [paste from .claude/agents/researcher.md spawn template]
```

The Researcher returns a context brief. Inject relevant sections into Engineer spawn prompts.

### Step 2: Create the Team

```
TeamCreate:
  team_name: "{descriptive-name}"
  description: "{what this swarm is doing}"
```

### Step 3: Spawn Engineers (Parallel)

Spawn all Engineers simultaneously using multiple Task tool calls in a single message.

```
Task tool (for each Engineer):
  subagent_type: general-purpose
  mode: bypassPermissions
  team_name: "{team-name}"
  name: "engineer-N"
  prompt: [paste from .claude/agents/engineer.md spawn template, filled in with specific files and instructions]
```

**Critical:** Each Engineer's file list must be non-overlapping. No shared output files.

### Step 4: Monitor Progress

While Engineers work:
- Messages from teammates are delivered automatically
- Use `/swarm-status` to check progress if needed
- Do not interfere unless a teammate messages you with a problem

### Step 4.5: Verify (After Engineers Complete)

Before spawning Reviewers, run verification to catch runtime failures that read-only Reviewers cannot detect.

**Option A — Spawn Verifier Agent:**
```
Task tool:
  subagent_type: general-purpose
  mode: bypassPermissions
  team_name: "{team-name}"
  name: "verifier-1"
  prompt: [paste from .claude/agents/verifier.md spawn template, filled in with modified files and import paths]
```

**Option B — Lead-as-Verifier Fallback (Windows):**

On Windows, Verifier agents frequently get stuck on Bash permission prompts despite `bypassPermissions` mode. The Lead-as-Verifier fallback is the expected path:

1. Run pytest directly as Lead:
   ```
   python -m pytest --tb=short -q
   ```
2. Run import checks: `python -c "from X import Y"` for each new import path
3. Grep for stale references to old module paths
4. If failures found, spawn a Fixer agent (see `.claude/agents/fixer.md`)

**Verification must pass before proceeding to Reviewers.**

### Step 5: Spawn Reviewers (After Verification Passes)

Wait for verification to pass, then spawn Reviewers.

```
Task tool (for each Reviewer):
  subagent_type: Explore
  team_name: "{team-name}"
  name: "reviewer-N"
  prompt: [paste from .claude/agents/reviewer.md spawn template, filled in with deliverables and sources]
```

**Critical:** Split review scope across Reviewers. Each Reviewer handles a subset of deliverables + their corresponding source files.

### Step 6: Synthesize Results

After Reviewers report:
- Combine review scorecards into a single report
- Flag any issues that need correction
- If corrections needed: either fix them yourself (Lead) or re-spawn an Engineer for targeted fixes
- Produce the final consolidated output

### Step 7: Shutdown

Use `/swarm-cleanup` or manually:
1. Send `shutdown_request` to each teammate
2. Wait for acknowledgments
3. Call `TeamDelete` to clean up

---

## Agent Type Reference

| Role | Subagent Type | Mode | Tools Available | Cost |
|------|--------------|------|-----------------|------|
| Engineer | `general-purpose` | `bypassPermissions` | All (Read, Write, Edit, Bash, Glob, Grep, etc.) | Higher |
| Verifier | `general-purpose` | `bypassPermissions` | All (needs Bash for pytest) | Higher |
| Fixer | `general-purpose` | `bypassPermissions` | All (targeted edits + verification) | Medium |
| Reviewer | `Explore` | default | Read-only (Read, Glob, Grep, WebFetch) | Lower |
| Researcher | `Explore` | default | Read-only (Read, Glob, Grep, WebFetch) | Lower |

**Why Explore for Reviewers/Researchers:** In past swarm runs, a `general-purpose` Reviewer attempted a Bash command, got stuck on a permission prompt, and could not process shutdown requests. `Explore` type has no Bash access, preventing this entirely.

**Why general-purpose for Verifier:** The Verifier must run pytest and import checks via Bash. However, on Windows, Bash permission prompts may still block despite `bypassPermissions` mode. See "Lead-as-Verifier Fallback" above.

**Model selection:** Consider using Sonnet (`model: "sonnet"`) for Reviewers, Researchers, and Fixers. Read-heavy verification and targeted fixes don't need Opus-level reasoning, and Sonnet is faster and cheaper.

---

## Windows-Specific Operations

### PowerShell Variables Get Stripped

**Problem:** Inline PowerShell in the Bash tool strips `$_`, `$f`, `$src` and other variables.

**Solution:** Always write PowerShell to a `.ps1` file first, then execute it:
```
1. Write tool → create script.ps1
2. Bash tool → powershell -ExecutionPolicy Bypass -File script.ps1
3. (optional) Bash tool → rm script.ps1
```

### Join-Path With 3 Arguments Fails

**Problem:** `Join-Path $a $b $c` throws ParameterBindingException on older PowerShell.

**Solution:** Use intermediate variables:
```powershell
$intermediate = Join-Path $a $b
$full = Join-Path $intermediate $c
```

### Windows Commands Don't Work in Bash Shell

**Problem:** `copy`, `del`, `move`, `dir` are Windows CMD builtins, not available in the Bash tool's shell.

**Solution:** Use Unix equivalents (`cp`, `rm`, `mv`, `ls`) or PowerShell scripts.

### No Unix `timeout` or `sleep`

**Problem:** `timeout` on Windows is interactive. `sleep` doesn't exist.

**Solution:** `ping -n N 127.0.0.1 >nul` (waits N-1 seconds).

---

## Shared File Strategy (Sequential Engineers)

When two or more Engineers must modify the same file, they **cannot work in parallel**. Use sequential execution:

1. **Engineer-1** makes their changes to the shared file
2. **Verifier** (or Lead) confirms Engineer-1's changes pass
3. **Lead provides Engineer-2** with updated line numbers (the file has shifted after Engineer-1's edits)
4. **Engineer-2** makes their changes
5. **Verifier** (or Lead) confirms Engineer-2's changes pass

**Critical:** Always re-read the file and provide updated line numbers to Engineer-2. If Engineer-1 added 50 lines, every line number in Engineer-2's scope has shifted by +50.

**When to use this pattern:**
- Method extraction from a single large file
- Refactoring that touches shared configuration or init files

**When to avoid this pattern:**
- If the shared file changes are independent and in different regions, consider having one Engineer handle both scopes
- If the file is an `__init__.py` with only import additions, the risk of conflict is low — parallel may be acceptable

---

## Error Recovery

### Stuck Teammate (Permission Prompt)

**Symptoms:** Teammate goes idle but has incomplete tasks. Cannot process shutdown requests.

**Cause:** `general-purpose` teammate attempted a Bash command that triggered a permission gate.

**Fix:**
1. Try sending shutdown request (may not work if blocked on prompt)
2. If shutdown fails, manually clean up:
   ```
   rm -rf ~/.claude/teams/{team-name}
   rm -rf ~/.claude/tasks/{team-name}
   ```
3. Re-spawn the team without the stuck agent

**Prevention:** Use `Explore` subagent type for all read-only roles.

### Teammate Hits Context Limit

**Symptoms:** Teammate produces partial output or stops mid-task.

**Cause:** Too many files or too much source material for a single agent's context window.

**Fix:**
1. Shut down the affected teammate
2. Split their scope into two smaller assignments
3. Spawn two replacement teammates with the split scope

**Prevention:** Enforce scope caps (~15K lines per Engineer, ~15 files per Reviewer).

### TeamDelete Fails

**Symptoms:** `TeamDelete` returns "Cannot cleanup team with N active member(s)."

**Cause:** Teammates that are stuck or haven't acknowledged shutdown still show as "active."

**Fix:**
1. Retry shutdown requests
2. If still stuck, manually delete team files:
   ```
   rm -rf ~/.claude/teams/{team-name}
   rm -rf ~/.claude/tasks/{team-name}
   ```

### Incomplete Task Marking

**Symptoms:** Tasks show as in_progress but the work is actually done.

**Cause:** Teammates sometimes forget to mark tasks complete, especially under heavy load.

**Fix:** Manually update task status.

---

## Cost Awareness

| Team Size | Approximate Token Cost | Best For |
|-----------|----------------------|----------|
| Lead only (no swarm) | 1x baseline | Simple tasks, single-file changes |
| Lead + 2 Engineers | ~3-5x baseline | Parallel implementation (non-overlapping files) |
| Lead + 2 Engineers + Verifier + 2 Reviewers | ~6-10x baseline | Full quality-gated workflow |
| Lead + Researcher + 2 Engineers + Verifier + 2 Reviewers | ~7-12x baseline | Complex tasks needing context gathering |
| Lead + Researcher + 2 Sequential Engineers + Verifier + 2 Reviewers | ~8-14x baseline | Shared file extraction (highest cost, sequential) |

**When NOT to use a swarm:**
- Task touches fewer than 3 files
- Work cannot be parallelized (sequential dependencies)
- The Lead already has full context and could do it faster alone
- Token budget is limited

---

## Checklist: Quick Launch Reference

```
[ ] Task defined with clear inputs and outputs
[ ] File inventory complete with line counts
[ ] Scope split: no file overlap between Engineers (or sequential plan if shared file)
[ ] Scope cap: <15K lines per Engineer, <15 files per Reviewer
[ ] Output format template prepared
[ ] (Optional) Researcher spawned for context brief (REQUIRED for method extraction)
[ ] TeamCreate called
[ ] Engineers spawned (parallel if non-overlapping, sequential if shared file)
[ ] Engineers completed — deliverables present
[ ] Verification passed (Verifier agent or Lead-as-Verifier fallback)
[ ] If verification failed: Fixer spawned and re-verified
[ ] Reviewers spawned as Explore type with split scope
[ ] Reviews synthesized — issues addressed
[ ] Teammates shut down — TeamDelete called
[ ] Results committed (if applicable)
```
