# CLAUDE.md - Project Rules for Claude Code

## OPERATIONAL MODES - ACTIVE AT ALL TIMES

These modes govern all Claude Code behavior in this project. Default is read-only.

### Mode 1: Analyze / Look (DEFAULT)
- **Strictly read-only**
- May read files, search code, answer questions
- NO file writes, NO shell commands, NO network calls
- This is the default mode at conversation start

### Mode 2: Plan
- **Read-only** except for daily handoff markdown
- Present plans as phased execution steps
- After presenting a plan, **STOP and wait** for user instruction
- Do NOT execute anything - provide diffs/commands as text preview only

### Mode 3: Execute (Phase-Specific)
- **Only active after the exact phrase "Make It So"** and the phase is specified
- During authorized phase: commands and file writes are allowed
- Confine all changes to the authorized phase ONLY
- Must ask for another release phrase for additional phases
- Update daily handoff log during execution

**PRECEDENCE:** These mode rules override default Claude Code behavior. When in doubt, remain read-only.

---

## RELEASE PHRASE PROTOCOL

### The Release Phrase
The exact phrase **"Make It So"** is REQUIRED to authorize any execution.

### Rules
1. **No execution without release** - Without "Make It So", remain in read-only mode
2. **Phase must be specified** - User must indicate which phase(s) to execute
3. **One release per phase** - Each phase requires its own authorization unless user authorizes multiple
4. **Scope is strict** - Only perform work within the authorized phase
5. **Ask for next release** - After completing a phase, stop and wait for next authorization

### Examples
- "Make It So" (after a single-phase plan) → Execute that phase
- "Make It So Phase 2" → Execute only Phase 2
- "Make It So Phases 1-3" → Execute Phases 1, 2, and 3
- "Do it" / "Go ahead" / "Yes" → **NOT SUFFICIENT** - must use exact phrase

### Outside Execution Mode
When not in an authorized Execute phase:
- Do NOT run shell commands
- Do NOT run scripts
- Do NOT make web/network calls
- Do NOT write files
- Provide diffs and commands as **text preview only**

---

## QUE REPO / MERGE DONE PROTOCOL
→ See `.claude/workflows/git_protocol.md` for full details.

**Quick Reference:**
- **"Que Repo"** → Stage, commit, push to `main`
- **"Merge Done"** → Acknowledge completion, no further git actions

---

## PLANNING OUTPUT FORMAT
→ See `.claude/workflows/planning_protocol.md` for full details.

**Quick Reference:**
- All plans use numbered phases
- After presenting: STOP and WAIT for "Make It So"
- Never execute without release phrase

---

## SWARM PROTOCOL
→ See `.claude/workflows/swarm_protocol.md` for full details.

**Quick Reference:**

### Activation
- Swarms follow the same mode protocol: Plan first, "Make It So" to execute
- Agent definitions in `.claude/agents/` (engineer, reviewer, researcher, verifier, fixer)
- Slash commands: `/swarm-status`, `/swarm-cleanup`

### Default Team Composition
- **Lead** (you): Orchestrator. Spawns teammates, assigns tasks, synthesizes results.
- **Researcher** (optional, but required for extraction tasks): Pre-flight `Explore` subagent for context gathering. Not a team member — spawned via Task tool before the swarm.
- **Engineers** (2): `general-purpose` with `bypassPermissions`. Produce deliverables (parallel if non-overlapping files, sequential if shared).
- **Verifier** (1): `general-purpose` with `bypassPermissions`. Runs pytest + import checks after Engineers complete. On Windows, Lead-as-Verifier fallback is the expected path.
- **Fixer** (as needed): `general-purpose` with `bypassPermissions`. Targeted fixes when Verifier reports failures. Max ~10 edits.
- **Reviewers** (2): `Explore` subagent type (read-only). Verify quality in parallel. Split scope to stay under context limits.

### Critical Rules
1. **File ownership is absolute** — no two agents edit the same file simultaneously
2. **Shared files require sequential Engineers** — E1 first, verify, then E2 with updated line numbers
3. **Engineers: `general-purpose` + `bypassPermissions`** — full tool access, no approval friction
4. **Reviewers: `Explore` subagent type** — read-only, prevents Bash permission freezes
5. **Verification before review** — Verifier (or Lead) must confirm pytest passes before spawning Reviewers
6. **Scope cap: ~15K lines per Engineer, ~15 files per Reviewer** — beyond this, split the scope
7. **Windows: PowerShell in script files only** — never inline `$_` variables in Bash tool
8. **Windows: use `cp`/`rm`, not `copy`/`del`** — Windows commands don't work in Bash shell

### Spawn Sequence
1. (Optional) Researcher subagent → produces context brief (REQUIRED for method extraction)
2. TeamCreate → establishes team
3. Engineers (parallel or sequential) → produce deliverables
4. Verification → Verifier agent or Lead-as-Verifier fallback (pytest + import checks)
5. (If needed) Fixer agent → targeted fixes from Verifier report, then re-verify
6. Reviewers in parallel → verify quality (split scope across reviewers)
7. Lead synthesizes review reports → final output
8. Shutdown teammates → TeamDelete

---

## CRITICAL SAFETY RULES - NEVER VIOLATE THESE

### Git Operations - FORBIDDEN WITHOUT EXPLICIT USER CONFIRMATION
- **NEVER** run `git push --force` or `git push -f`
- **NEVER** run `git reset --hard`
- **NEVER** run `git clean -f` or `git clean -fd`
- **NEVER** run `git checkout .` or `git restore .` (discards all changes)
- **NEVER** run `git branch -D` (force delete branch)
- **NEVER** run `git rebase` without explicit user request
- **NEVER** delete remote branches without explicit confirmation
- **NEVER** modify git history on main/master branch

### File Operations - FORBIDDEN WITHOUT EXPLICIT USER CONFIRMATION
- **NEVER** delete files or directories without explicit user confirmation
- **NEVER** use `rm -rf` or equivalent destructive commands
- **NEVER** overwrite files without reading them first
- **NEVER** bulk delete or bulk overwrite operations

## WORKFLOW REQUIREMENTS

### Before Making Changes
1. Always read files before editing them
2. Show the user what changes will be made before applying
3. For multi-file changes, list all affected files first

### Testing Protocol
1. **Run tests after code changes** - Execute `pytest` after any code modification
2. **Fix before proceeding** - If tests fail, fix failures before moving to next phase
3. **New features need coverage** - New functionality requires corresponding test coverage
4. **Report results** - Include test results in handoff log entries
5. **No broken commits** - Never commit code that breaks existing tests

**Test Commands:**
```bash
pytest                          # Run all tests
pytest tests/test_specific.py   # Run specific test file
pytest -v                       # Verbose output
pytest --tb=short               # Short traceback on failures
```

## PROJECT CONTEXT

**Summary:** Windows desktop GUI application for extracting data from Siemens TIA Portal V17/V18 projects via the Openness API.

### Architecture Layers
| Layer | Location | Purpose |
|-------|----------|---------|
| Openness Bridge | `openness_bridge.py`, `loader_multi.py` | CLR/.NET integration with Siemens assemblies |
| Discovery & Config | `discovery.py`, `validation.py`, `config_store.py`, `settings.py` | DLL scanning, candidate ranking, profile persistence |
| Session & Extraction | `session.py`, `tag_extractor.py`, `block_exporter.py`, `hmi_exporter.py`, `devices_networks_exporter.py` | TIA Portal attachment and data extraction |
| Writers | `excel_writer.py`, `block_writer.py`, `hmi_flatteners.py` | Export to Excel/CSV/Google Sheets |
| GUI | `gui/main_window.py`, `gui/wizard.py`, `gui/dll_wizard_window.py`, `gui/hmi_export_window.py` | PySide6 desktop interface |
| Boot | `app.py`, `app_boot.py` | Entry points and CLR pre-loading |
| Tests | `tests/` | pytest suite |

### Quick Reference
- **Entry point (recommended):** `python -m tia_tags_exporter.app_boot`
- **Entry point (direct):** `python -m tia_tags_exporter.app`
- **Virtual env:** `.venv`
- **Run tests:** `pytest`
- **Key dependencies:** pythonnet, PySide6, openpyxl, gspread, google-auth

---

## ERROR RECOVERY PROTOCOL

### When Execution Fails Mid-Phase
1. **STOP immediately** - Do not attempt to continue or auto-fix
2. **Report the error** - Provide full error context (command, output, traceback)
3. **Assess the state** - Describe what was completed vs. what failed
4. **Wait for instruction** - Do NOT attempt automatic fixes without new authorization

### What NOT to Do on Error
- Do NOT retry failed commands automatically
- Do NOT attempt workarounds without user approval
- Do NOT proceed to next phase
- Do NOT assume what the user wants

### Recovery Options to Present
When reporting an error, offer clear options:
- "Retry the failed step"
- "Skip this step and continue"
- "Rollback changes made in this phase"
- "Abort and return to Plan mode"

### Partial Completion
If a phase partially completes before failure:
- Document what was successfully done
- Document what remains incomplete
- Note any files left in intermediate states

---

## UNCERTAINTY PROTOCOL

### When Unsure About Requirements
- **ASK before assuming** - If requirements are ambiguous, ask for clarification
- **Don't guess** - Never fill in missing details with assumptions
- **Present options** - When multiple interpretations exist, present them for user choice

### When a Change Seems Risky
- **FLAG explicitly** - Call out "This change is risky because..."
- **Explain the risk** - What could go wrong, what's the blast radius
- **Suggest alternatives** - If a safer approach exists, present it

### When Task Scope is Large
- **Recommend breaking up** - If task exceeds single session, say so
- **Propose phases** - Suggest logical break points
- **Identify dependencies** - Note what must be done in sequence vs. parallel

### Confidence Signals
Use explicit confidence language:
- "I'm confident this will work because..."
- "I'm uncertain about X - should I proceed or investigate first?"
- "This is outside my expertise - consider verifying with..."

### When to Say "I Don't Know"
- Missing context about project-specific decisions
- Unfamiliar libraries or frameworks
- Ambiguous user intent
- Questions about business logic or domain rules

---

## ROLLBACK PROTOCOL

### Trigger Phrases
- **"Rollback"** or **"Undo"** - Initiates rollback assessment

### Rollback Workflow
1. **Show what would be reverted** - Run `git diff HEAD~1` to display changes
2. **Confirm scope** - "This will revert: [list of changes]"
3. **WAIT for confirmation** - Do NOT execute rollback without explicit approval
4. **Use safe methods only** - Use `git revert` to create a new commit that undoes changes

### Safe Rollback Commands
```bash
git diff HEAD~1                 # Preview what would be undone
git revert HEAD --no-edit       # Revert last commit (creates new commit)
git checkout HEAD~1 -- <file>   # Revert specific file only
```

### FORBIDDEN Rollback Methods
- **NEVER** use `git reset --hard`
- **NEVER** use `git checkout .` (discards all uncommitted changes)
- **NEVER** force push after rollback

### Uncommitted Changes
If user wants to discard uncommitted work:
1. Show `git status` and `git diff`
2. List exactly what will be lost
3. Require explicit confirmation: "Confirm you want to discard these uncommitted changes"
4. Use `git checkout -- <specific-file>` for targeted discard (not bulk)

---

## RULE PRECEDENCE AND OVERRIDES

### Precedence Order (Highest to Lowest)
1. **Critical Safety Rules** - Always apply, cannot be overridden
2. **Operational Modes** - Control all behavior unless safety rule applies
3. **Release Phrase Protocol** - Gates all execution
4. **Workflow Requirements** - Apply during authorized execution
5. **Default Claude Code behavior** - Only when not superseded by above

### Override Rules
- These guardrails **take precedence** over default Claude Code behavior
- If multiple rules conflict, higher precedence wins
- Safety rules CANNOT be suspended or overridden
- Mode rules can only be suspended with **explicit user statement** for the current turn only

### Explicit Suspension
User may temporarily suspend non-safety rules by stating explicitly:
- "Suspend guardrails for this turn" → Allows execution without release phrase (one turn only)
- "Skip the plan" → Allows immediate execution (still requires "Make It So")

**What CANNOT be suspended:**
- Critical Safety Rules (git destructive commands, file deletion confirmations)
- Required Confirmations for destructive operations

### When In Doubt
- Default to **read-only** mode
- Ask for clarification rather than assume permission
- Never interpret ambiguous statements as authorization to execute
