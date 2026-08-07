# M⊕ Markdown Document Control Index

**Owner:** primary Jarvis session
**Workspace:** `C:\Users\Drew\Documents\Jarvis_Context\Projects\ai-workspace`
**Last inventory:** 2026-08-06 23:33 CDT

This file defines how project Markdown is coordinated when multiple branches or sessions edit the workspace. It is a control document, not a replacement for the canonical tracker.

## Document roles

| Path | Role | Authority | Edit rule |
|---|---|---|---|
| `PROJECT_TRACKER.md` | Canonical project state, roadmap, decisions, handoffs, blockers, and verification receipts | Highest | Append-preserving. Re-read from disk before every edit. Never rewrite from a stale partial copy. |
| `README.md` | User-facing setup, run, safety, and troubleshooting guide | Operational guidance | Update when commands or behavior change. Keep historical receipts in `PROJECT_TRACKER.md`. |
| `MARKDOWN_INDEX.md` | Markdown ownership, classification, and branch synchronization rules | Document control | Update when project-owned Markdown is added, removed, reclassified, or its edit protocol changes. |

## Excluded Markdown

The following trees may contain Markdown supplied by dependencies or tools. They are inventory-only and must not be edited or copied into project documentation:

- `backend/.venv/`
- `frontend/node_modules/`
- Hermes/tool caches
- Downloaded model repositories and third-party runtime trees
- Generated build, coverage, or temporary directories

## Branch synchronization protocol

1. Read `PROJECT_TRACKER.md` and this index from disk before making a Markdown change.
2. Inventory project-owned Markdown if the branch may have added a file.
3. Patch a unique section or row; do not overwrite the whole tracker from a stale snapshot.
4. Preserve unfamiliar branch entries, timestamps, ownership labels, and historical decisions.
5. Resolve conflicts by adding a newer decision/correction that links back to the older entry; do not silently delete history.
6. Record every meaningful code, scope, blocker, handoff, or verification change in `PROJECT_TRACKER.md`.
7. After editing, re-read the settled section and note any sibling-write warning or concurrent modification in the tracker.
8. A branch receipt is proposed state until the parent session verifies the actual files or runs a parent-owned check.

## Current project-owned inventory

- `PROJECT_TRACKER.md`
- `README.md`
- `MARKDOWN_INDEX.md`

The project currently has no separate branch-specific Markdown directory. If one is introduced, list it here with an owner and merge rule before relying on it for coordination.
