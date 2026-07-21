# CONTEXT.md

Status: Current repo context
Current as of: 2026-07-21

This file is the short "you are here" guide for the repo.

Its job is to stop agents or future sessions from treating old planning docs as current instructions.

If this file becomes stale, update it or remove it. Do not keep it as ceremonial documentation.

## What This File Is For

Use `CONTEXT.md` to answer four questions quickly:

1. What stage is the repo in now?
2. Which docs are current?
3. Which docs are historical?
4. What trust boundaries still matter?

## Read Order

Before substantial planning or implementation work, read:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. the current bounded PRD, if one exists
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. the relevant current issue, if one exists

Do not infer approval from `docs/v2-issue-map.md`, archived PRDs, or old handoffs alone.

## Current Stage

Threadwise is past basic MVP proof.

The repo already proves:

- Gmail daily run flows with bounded Gmail mutation
- browser-based Gmail companion flows
- dashboard and workbench surfaces
- unsubscribe review and explicit execution support
- ProtonMail read paths plus a bounded Bridge-backed, label-only review console
- local artifact, reporting, and review tooling
- a public no-login demo that runs entirely on synthetic browser-local data

The current branch state includes the completed async Gmail companion extension slices `133` through `137`, including:

- visible selected-email understanding states
- explicit async teach / fix lifecycle states
- background follow-up refresh off the main response path
- compact recent-activity and retry visibility
- a founder-facing teaching pack for this async architecture

The current architecture checkpoint on `codex/runtime-a042b03` also completes a behavior-preserving refactor of the companion application. Rendering, teaching, Gmail teaching writes, and cached runtime state now live in deep modules with narrow interfaces. See `docs/handoff/2026-07-20-architecture-refactor-closeout.md`.

## Current Source Of Truth

For the just-completed async extension work, use:

1. `docs/prd-async-threadwise-extension-2026-07-10.md`
2. `docs/issues/133-add-async-selected-email-understanding-states.md`
3. `docs/issues/134-add-async-action-lifecycle-for-teach-and-fix.md`
4. `docs/issues/135-move-slower-follow-up-work-off-the-main-sidebar-path.md`
5. `docs/issues/136-add-recent-activity-and-retry-surface-for-async-operations.md`
6. `docs/issues/137-build-comprehensive-teaching-pack-for-async-threadwise-extension.md`

For the founder-approved bounded Proton review-console experiment, use `docs/issues/138-add-proton-bridge-review-console.md`. It is the authority for the narrow label-only Proton write boundary.

For the current implementation architecture, use `docs/handoff/2026-07-20-architecture-refactor-closeout.md` and the linked bounded handoffs.

For repo workflow and guardrails, use `AGENTS.md`.

For broader product direction, use `docs/v2-alignment.md`.

## What Is Historical

Treat these as historical unless explicitly pulled back into an active slice:

- `docs/v2-issue-map.md`
- old handoffs in `docs/handoff/`
- archived PRDs and planning docs in `docs/archive/`
- older completed slice docs that describe already-shipped states rather than the current bounded task

Historical docs are still useful context. They are not approval.

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue
2. `AGENTS.md`
3. `CONTEXT.md`
4. `docs/v2-alignment.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. archived docs and handoffs as background only

## Current Trust Boundaries

- Gmail mutation must stay bounded and auditable
- ProtonMail mutation is limited to the founder-approved review-console slice: add one `EA/` label, verify it through Bridge, and preserve Inbox; no label replacement, move, archive, Trash, Spam, send, or provider rule changes
- unsubscribe execution must remain explicit and reviewable
- broad autonomous inbox actions remain out of scope by default
- private email, credentials, OAuth, and live inbox data remain sensitive

## Maintenance Rule

Update this file when one of these changes:

- the active bounded PRD changes
- the current milestone or implementation slice changes
- the trust order changes
- the file starts pointing at stale "current" work

If nobody is willing to maintain it, delete it and remove the read-order dependency from `AGENTS.md`.
