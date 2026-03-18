# Git Protocol - Que Repo / Merge Done

## Trigger Phrases
- **"Que Repo"** - Initiates commit and push workflow
- **"Merge Done"** - Signals user has completed manual merge/action on GitHub

---

## Que Repo Workflow

This project pushes directly to `main`. No feature branch or PR is required.

| Step | Action |
|------|--------|
| 1 | Run `git status` and `git diff` to review changes |
| 2 | Stage changes to current branch |
| 3 | Generate commit message and present for user approval |
| 4 | **STOP and WAIT** for user to approve commit message |
| 5 | After approval: commit to current branch |
| 6 | Push to remote (`origin/main`) |
| 7 | Report success with summary of what was pushed |

---

## Merge Done Workflow

| Step | Action |
|------|--------|
| 1 | Acknowledge that user has completed action on GitHub |
| 2 | Stay on current branch |
| 3 | **No further git actions** |

---

## What This Protocol Does NOT Do
- **NO** automatic PR creation (user must explicitly request)
- **NO** auto-merging PRs (user must approve on GitHub)
- **NO** switching branches
- **NO** deleting branches
- **NO** pulling from remote
- **NO** merging locally

---

## Branch Rules
- Pushing to `main` is allowed in this project
- Always stay on current working branch unless explicitly told otherwise
- Never force push
