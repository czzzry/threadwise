# CONTEXT.md

Status: Current repo context
Current as of: 2026-07-01

This file exists to keep agents from re-litigating old project stages or mistaking historical docs for current instructions.

## Read Order

Before doing substantial work, read these in order:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md` for the completed MVP+2 Gmail daily usefulness slice
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

MVP+2 alignment is captured in `docs/prd.md`, and implementation issues `#8` through `#14` are complete. The completed MVP+2 thesis is:

- Gmail daily usefulness before ProtonMail expansion
- a teachable LLM-backed Needs attention lane across newly processed Gmail plus bounded stored lookback
- a dashboard-first Run Gmail check flow with confirmation, duplicate protection, and existing safe Gmail mutations only
- generic local LLM usage tracking first wired to attention detection
- explicit follow-up candidates for local data retention / inbox freshness and startup / packaging model review

## Current Working Rule

Do not restart first-principles Gmail-MVP discovery.

Do not infer an approved next build from `docs/v2-issue-map.md`, old handoffs, or archived V1 planning docs.

The current product direction for Threadwise is:

- first serious release target: Gmail only
- primary surface: browser-based inbox companion sidebar
- core interaction: in-inbox `Correct / Teach` loop with short agent acknowledgments
- secondary surface: dashboard/workbench for summary, unsubscribe, review, and debugging
- MVP+1 target: completed recruiter-ready portfolio README demo using synthetic Gmail-style data

The completed bounded PRD exists in `docs/prd.md` and GitHub issue `#7`. It covers MVP+2 Gmail daily usefulness. The completed MVP+1 PRD is archived at `docs/archive/prd-mvp-plus-one-portfolio-demo-completed-2026-06-30.md`, with closeout recorded in `docs/issues/073-close-mvp-plus-one-public-demo-milestone.md`.

The MVP+2 implementation briefs in `docs/issues/083` through `docs/issues/089`, mirrored to GitHub issues `#8` through `#14`, are complete. The local data retention and inbox freshness HITL review in `docs/issues/090` / GitHub `#15` is complete, with output in `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md` and follow-up candidates in GitHub issues `#17` through `#21` / `docs/issues/092` through `docs/issues/096`. The next product step should choose whether to run the remaining startup/packaging HITL review candidate in `docs/issues/091` / GitHub `#16`, triage one of the new retention/freshness follow-ups, or begin the next alignment cycle.

MVP+2 implementation progress is `issues 7/7 => MVP+2 = 7/7 done`. Treat `#16` and the new `#15` follow-ups as follow-up candidates unless the founder explicitly pulls them into a new active milestone count.

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue, when one exists
2. `AGENTS.md` for workflow and guardrails
3. `CONTEXT.md` for current stage and read order
4. `docs/v2-alignment.md` for current product direction
5. `docs/prd.md` for the current MVP+2 Gmail daily usefulness slice
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

If a task is about the completed Gmail inbox companion release, completed in-inbox teaching loop, completed sidebar UX, completed MVP+1 daily dashboard, completed unsubscribe review handoff, or the recruiter-ready portfolio demo, treat the completed MVP+1 docs and handoff as historical source of truth for that shipped behavior.

If the task is about MVP+2 implementation, use `docs/prd.md` and the relevant issue brief as the source of truth.

If a task changes product scope, chooses the next major slice, or pushes beyond the current trust boundary, stop and align first.
