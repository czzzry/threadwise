# Status

Completed
Current as of: 2026-06-30
Triage state: `completed`
Builds on: `docs/handoff/2026-06-30-mvp-plus-one-public-demo-closeout.md`

# Title

Deepen local artifact registry without changing stored artifact behavior

## Type

AFK / Refactor / Pre-MVP+2

## What to build

Introduce a small local artifact registry so Threadwise has one central module for local artifact names, existing path patterns, JSON read/write behavior, and minimal validation for core artifacts.

The slice must be behavior-preserving. It must not move existing files, rename JSON artifacts, migrate stored data, change CLI behavior, or change product behavior. Existing helper functions such as `daily_report_path(...)` and `memory_proposals_path(...)` should remain available and delegate to the registry.

## Acceptance criteria

- [x] Every current path helper in `src/local_artifacts.py` is represented by a descriptor in the registry.
- [x] Existing helper functions return the same paths as before.
- [x] Existing JSON read/write helpers still behave the same for callers.
- [x] Minimal validation exists for core artifacts: batches, daily reports, weekly reports, write status, inbox removal status, teachable rules, memory proposals, unsubscribe selections/audit, and unified review queue.
- [x] Validation is opt-in and does not migrate or rewrite historical artifacts.
- [x] Focused tests cover registry coverage, path compatibility, JSON read/write compatibility, and core-artifact validation.

## Completion notes

- Added `ARTIFACT_REGISTRY`, artifact descriptors, opt-in JSON artifact read/write helpers, and minimal core-artifact validation.
- Preserved all existing helper functions and path patterns.
- Did not migrate, rename, or rewrite stored artifacts.

## Blocked by

None - can start immediately.
