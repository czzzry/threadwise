# Status

Completed
Current as of: 2026-06-30
Triage state: `completed`
Builds on: `docs/issues/079-deepen-local-artifact-registry.md`

# Title

Deepen Gmail companion product module without changing routes or behavior

## Type

AFK / Refactor / Pre-MVP+2

## What to build

Split the Gmail companion module by responsibility while preserving the existing public surface.

The current `gmail_companion_ui.py` should remain the route/server entrypoint for scripts, tests, and the extension harness. The refactor should move state-building and reusable rendering helpers behind smaller modules so future MVP+2 work can change selected-email state, daily summary state, or page rendering without reopening one large file for every concern.

This is behavior-preserving. Do not redesign the UI, change endpoint contracts, change routes, change Gmail write-through behavior, change extension behavior, or introduce a web framework.

## Acceptance criteria

- [x] `gmail_companion_ui.py` remains the public entrypoint exposing `main(...)`, `create_server(...)`, and `GmailCompanionApp`.
- [x] Current routes and JSON endpoint contracts are preserved.
- [x] State-building helpers are moved behind a dedicated Gmail companion state module.
- [x] Reusable page/rendering helpers are moved behind a dedicated Gmail companion rendering module where practical.
- [x] Teaching/memory semantics are not redesigned in this slice.
- [x] Browser extension files are unchanged unless required by existing tests.
- [x] Focused tests cover the new module boundaries and existing Gmail companion UI behavior still passes.

## Completion notes

- Added `src/gmail_companion_state.py` for selected-email state, daily summary state, runtime payloads, and local teach/apply helpers.
- Added `src/gmail_companion_rendering.py` for shared rendering helpers used by the companion pages.
- Kept `src/gmail_companion_ui.py` as the public server, routing, and large-page entrypoint.
- Did not change routes, endpoint contracts, UI copy, Gmail write-through behavior, or browser extension files.

## Blocked by

None - can start immediately.
