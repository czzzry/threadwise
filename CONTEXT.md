# CONTEXT.md

Status: Current repo context
Current as of: 2026-06-30

This file exists to keep agents from re-litigating old project stages or mistaking historical docs for current instructions.

## Read Order

Before doing substantial work, read these in order:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md` for the completed MVP+1 portfolio demo release slice
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/v2-issue-map.md`
7. then only the specific current issue, handoff, or code relevant to the task

## What This Repo Currently Is

The repo is past the original Gmail MVP and already proves:

- a Gmail daily run with bounded label write-back
- bounded `INBOX` removal for low-value Gmail mail
- daily and weekly reporting
- provider-aware local artifacts
- ProtonMail read-only import, live fetch, and daily run paths
- unsubscribe inventory, supported execution, and manual follow-up
- local browser review and workbench tools
- a memory-first runtime cascade with founder feedback
- a unified review queue and operational readiness loop
- a supervised classifier state that has already reached under `10%` unresolved on the current stored corpora

The repo is no longer blocked on basic implementation.

## Current Stage

This is a post-MVP, post-proof repo that has completed the Gmail release state and the MVP+1 recruiter-facing portfolio packaging pass.

The main uncertainty is no longer "can this be built?", no longer "can the classifier get under the current unresolved threshold?", and no longer "can a recruiter understand the product without setup?"

The main uncertainty is now what MVP+2 should be:

- product expansion planning after the Gmail-first portfolio demo
- likely inbox-agnostic / multi-inbox direction, starting from the same supervised loop
- preserving the existing safety boundaries before any new provider-side action is approved

## Current Working Rule

Do not restart first-principles Gmail-MVP discovery.

Do not infer an approved next build from `docs/v2-issue-map.md`, old handoffs, or archived V1 planning docs.

The current product direction for Threadwise is:

- first serious release target: Gmail only
- primary surface: browser-based inbox companion sidebar
- core interaction: in-inbox `Correct / Teach` loop with short agent acknowledgments
- secondary surface: dashboard/workbench for summary, unsubscribe, review, and debugging
- MVP+1 target: completed recruiter-ready portfolio README demo using synthetic Gmail-style data

The completed bounded PRD exists in `docs/prd.md` and covers the MVP+1 recruiter-ready portfolio demo release. The closeout slice is `docs/issues/073-close-mvp-plus-one-public-demo-milestone.md`.

The next product step should start with alignment for MVP+2. Do not infer the next approved build from the roadmap GIF, archived docs, or old issue maps.

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue, when one exists
2. `AGENTS.md` for workflow and guardrails
3. `CONTEXT.md` for current stage and read order
4. `docs/v2-alignment.md` for current product direction
5. `docs/prd.md` for the completed MVP+1 portfolio demo release slice
6. `docs/checkpoints/current-operating-model-2026-06-22.md` for what the repo currently proves
7. `docs/v2-issue-map.md` for candidate next-slice themes only
8. `docs/archive/`, `docs/handoff/`, and `docs/deep-research/` as historical context only

## Current Trust Boundaries

- Gmail mutation is bounded to current `EA/` label write-back and limited `INBOX` removal.
- ProtonMail remains read-only.
- Unsubscribe execution must stay explicit, selected, and auditable.
- Delete, trash, broad archive, and broad autonomous inbox actions are still out of scope by default.
- Private email, credentials, OAuth material, and live inbox data remain sensitive.

## Practical Next-Step Rule

If a task is implementation work on an already-triaged bounded slice, proceed.

If a task is about the Gmail inbox companion release, in-inbox teaching loop, sidebar UX, daily dashboard, unsubscribe review handoff, or the recruiter-ready portfolio demo, treat the completed MVP+1 docs and handoff as the source of truth.

If the task is about MVP+2, start with alignment/grill before writing a PRD or implementation issues.

If a task changes product scope, chooses the next major slice, or pushes beyond the current trust boundary, stop and align first.
