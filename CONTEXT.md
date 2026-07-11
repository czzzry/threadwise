# CONTEXT.md

Status: Current repo context
Current as of: 2026-07-11

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
5. the relevant current issue, if one exists
6. older checkpoints only when historical operating context is needed

Do not infer approval from `docs/v2-issue-map.md`, archived PRDs, or old handoffs alone.

## Current Stage

Threadwise is past basic MVP proof.

The repo already proves:

- Gmail daily run flows with bounded Gmail mutation
- browser-based Gmail companion flows
- dashboard and workbench surfaces
- unsubscribe review and explicit execution support
- ProtonMail read-only paths
- local artifact, reporting, and review tooling

The current repo state has completed the eval / promotion slices `129` through `132` and the async Gmail companion extension slices `133` through `137`, including:

- visible selected-email understanding states
- explicit async teach / fix lifecycle states
- background follow-up refresh off the main response path
- compact recent-activity and retry visibility
- a founder-facing teaching pack for this async architecture

The founder-approved Decision Copilot UI/UX redesign is implemented on `codex/decision-copilot-ui`. The Gmail companion now presents one current-email job at a time, with future learning and matching-existing review after the current decision; the dashboard and unsubscribe review remain separate supporting surfaces. See `docs/handoff/2026-07-11-decision-copilot-ui.md` for implementation and verification evidence.

The next stage is real-product observation: use the Gmail workflow, observe the existing privacy-safe analytics and concrete interaction friction, then choose a new bounded slice. There is no active bounded PRD. Do not infer further work from historical UI issues or completed implementation plans.

The branch also now contains a bounded, privacy-first PostHog product analytics slice for the Gmail companion workflow. Its current source of truth is `docs/analytics/tracking-plan.md`; implementation and dashboard evidence is summarized in `docs/handoff/2026-07-10-posthog-analytics-integration.md`.

The Gmail mutation reliability slice tracked in GitHub issue `#62` is also complete. Companion whole-inbox backfill now uses the same durable, bounded mutation implementation as daily automation, preserves partial label/inbox outcomes, and supports retrying failed inbox removal without repeating a successful label write. See `docs/handoff/2026-07-11-gmail-mutation-boundary.md`.

## Current Source Of Truth

For the latest completed eval / promotion work, use:

1. `docs/prd-eval-promotion-pipeline-2026-07-10.md`
2. `docs/issues/129-formalize-candidate-change-state-and-sources.md`
3. `docs/issues/130-add-batched-candidate-evaluation-and-recommendations.md`
4. `docs/issues/131-add-per-candidate-promotion-override-and-audit-flow.md`
5. `docs/issues/132-add-minimal-product-status-and-workbench-eval-review.md`

For the latest completed async extension work, use:

1. `docs/prd-async-threadwise-extension-2026-07-10.md`
2. `docs/issues/133-add-async-selected-email-understanding-states.md`
3. `docs/issues/134-add-async-action-lifecycle-for-teach-and-fix.md`
4. `docs/issues/135-move-slower-follow-up-work-off-the-main-sidebar-path.md`
5. `docs/issues/136-add-recent-activity-and-retry-surface-for-async-operations.md`
6. `docs/issues/137-build-comprehensive-teaching-pack-for-async-threadwise-extension.md`

For repo workflow and guardrails, use `AGENTS.md`.

For broader product direction, use `docs/v2-alignment.md`.

For the PostHog analytics boundary and event contract, use `docs/analytics/tracking-plan.md` and `docs/analytics/case-study.md`.

For the latest Gmail mutation reliability evidence, use `docs/handoff/2026-07-11-gmail-mutation-boundary.md` and GitHub issue `#62`.

For the completed Decision Copilot UI/UX implementation, use:

1. `docs/ui-ux-audit/2026-07-11-decision-copilot-direction.md`
2. `docs/handoff/2026-07-11-decision-copilot-ui.md`
3. `docs/prd-async-threadwise-extension-2026-07-10.md` for the async behavior preserved by the redesign

## What Is Historical

Treat these as historical unless explicitly pulled back into an active slice:

- `docs/v2-issue-map.md`
- old handoffs in `docs/handoff/`
- archived PRDs and planning docs in `docs/archive/`
- older completed slice docs that describe already-shipped states rather than the current bounded task

Historical docs are still useful context. They are not approval.

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue, if one exists
2. `AGENTS.md`
3. `CONTEXT.md`
4. `docs/v2-alignment.md`
5. completed PRDs and checkpoints as historical implementation evidence
6. archived docs and handoffs as background only

## Current Trust Boundaries

- Gmail mutation must stay bounded and auditable
- ProtonMail remains read-only
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
