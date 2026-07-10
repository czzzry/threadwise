# Add Recent Activity and Retry Surface for Async Operations

Status: Triaged ready-for-agent
Type: AFK
Parent PRD: `docs/prd-async-threadwise-extension-2026-07-10.md`

## What to build

Add a compact way for the founder to see what Threadwise just did and whether any async operation needs a retry, without turning the sidebar into a debug console.

This slice should prove a small recent-activity or operation-receipt surface that can show:

- last accepted action
- current in-progress action
- last completed result
- blocked or retryable action

with the richer workbench or dashboard remaining available for deeper inspection later.

## User stories covered

- 11. As the founder, I want recent async actions to remain inspectable, so that I can tell what Threadwise just did without depending on memory.
- 12. As the founder, I want the richer workbench and dashboard surfaces to support deeper review when needed, so that the sidebar can stay compact and fast.
- 13. As the founder, I want the extension to remain the primary entry point for now, so that we solve the real slowness problem without opening a full standalone-app project.
- 14. As the founder, I want the architecture to leave room for a future standalone Threadwise app, so that a later v2 product can reuse the async state model instead of starting over.

## Acceptance criteria

- [ ] The sidebar exposes a compact recent-activity or operation-receipt view for async actions.
- [ ] Retryable or blocked actions are visible after the main action moment passes.
- [ ] The sidebar stays compact and does not become a full debug surface.
- [ ] The activity model can be reused later by a richer Threadwise-owned workspace without rewriting the state semantics.
- [ ] Tests cover recent-activity and retry visibility through the product-facing contract.

## Blocked by

- `docs/issues/135-move-slower-follow-up-work-off-the-main-sidebar-path.md`
