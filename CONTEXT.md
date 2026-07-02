# CONTEXT.md

Status: Current repo context
Current as of: 2026-07-01

This file exists to keep agents from re-litigating old project stages or mistaking historical docs for current instructions.

## Read Order

Before doing substantial work, read these in order:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md` for the current MVP+3 Gmail sidebar interactive teaching-loop slice
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

MVP+2 alignment is archived at `docs/archive/prd-mvp-plus-two-gmail-daily-usefulness-completed-2026-07-01.md`, and implementation issues `#8` through `#14` are complete. The completed MVP+2 thesis is:

- Gmail daily usefulness before ProtonMail expansion
- a teachable LLM-backed Needs attention lane across newly processed Gmail plus bounded stored lookback
- a dashboard-first Run Gmail check flow with confirmation, duplicate protection, and existing safe Gmail mutations only
- generic local LLM usage tracking first wired to attention detection
- explicit follow-up candidates for local data retention / inbox freshness and startup / packaging model review

The latest completed bounded PRD is `docs/prd.md` for MVP+3 Slice B: Gmail companion shell polish. MVP+3 Slice A is archived at `docs/archive/prd-mvp-plus-three-slice-a-interactive-teaching-loop-completed-2026-07-01.md`. The completed Slice A thesis was:

- Gmail remains the main review surface
- Threadwise remains the reasoning, explanation, and control surface
- opening a Gmail email should show the selected email's `EA/...` classification, human-readable status, and a likely reason
- Agent View should keep an always-visible correction/explanation box for the selected email
- natural-language corrections should propose a current-email relabel, future rule, and affected-count estimate
- current-email relabel, applying to similar existing emails, and saving a future rule must be separately confirmed
- similar-email estimates use stored Threadwise data only in the first version
- dashboard and sidebar lists should become useful review launchers instead of inert reports
- full shell polish follows after the interactive core

## Current Working Rule

Do not restart first-principles Gmail-MVP discovery.

Do not infer an approved next build from `docs/v2-issue-map.md`, old handoffs, or archived V1 planning docs.

The current product direction for Threadwise is:

- first serious release target: Gmail only
- primary surface: browser-based inbox companion sidebar
- core interaction: in-inbox `Correct / Teach` loop with short agent acknowledgments
- secondary surface: dashboard/workbench for summary, unsubscribe, review, and debugging
- MVP+1 target: completed recruiter-ready portfolio README demo using synthetic Gmail-style data

The current bounded PRD exists in `docs/prd.md` and covers MVP+3 Gmail sidebar interactive teaching loop. The completed MVP+2 PRD is archived at `docs/archive/prd-mvp-plus-two-gmail-daily-usefulness-completed-2026-07-01.md` and GitHub issue `#7`. The completed MVP+1 PRD is archived at `docs/archive/prd-mvp-plus-one-portfolio-demo-completed-2026-06-30.md`, with closeout recorded in `docs/issues/073-close-mvp-plus-one-public-demo-milestone.md`.

The MVP+2 implementation briefs in `docs/issues/083` through `docs/issues/089`, mirrored to GitHub issues `#8` through `#14`, are complete. The local data retention and inbox freshness HITL review in `docs/issues/090` / GitHub `#15` is complete, with output in `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md` and follow-up candidates in GitHub issues `#17` through `#21` / `docs/issues/092` through `docs/issues/096`. The startup and packaging model HITL review in `docs/issues/091` / GitHub `#16` is complete, with output in `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`. The companion health/status follow-up in GitHub `#24` / `docs/issues/099` is complete, and the immediate startup pair `#22` / `#23` is also complete. `#25` / `#26` remain future review candidates.

MVP+2 implementation progress is `issues 7/7 => MVP+2 = 7/7 done`. Treat the `#15` and `#16` follow-ups as follow-up candidates unless the founder explicitly pulls them into a new active milestone count.

MVP+3 Slice A implementation progress is `issues 8/8 => MVP+3 Slice A = done`. GitHub parent issue `#27` and child issues `#28` through `#35` are closed. Published issue briefs:

- `#28` Selected Email Agent View - complete
- `#29` Clickable Sidebar Review Surfaces - complete
- `#30` Dashboard Review Launcher - complete
- `#31` Blocking Sidebar Usability Fixes - complete
- `#32` Correction Proposal Session - complete
- `#33` Confirm Current-Email Relabel - complete
- `#34` Similar Existing Email Review - complete
- `#35` Save Future Rule Separately - complete

MVP+3 Slice B implementation progress is `issues 4/4 => MVP+3 Slice B = done`. GitHub parent issue `#36` and child issues `#37` through `#40` are closed. Completed issue briefs:

- `#37` Logo-only minimized Gmail companion
- `#38` Brand icon fallback
- `#39` Remove technical sidebar footer
- `#40` Friendly companion error state

The next product step should be a fresh alignment cycle or a new bounded slice chosen from founder testing feedback.

Live testing tranche follow-up:

- `#41` Live testing tranche: sidebar context and teach fixes - complete
- `#42` Redesign Correct / Teach UX from live testing - implementation complete across child issues `#44`-`#50`; pending founder review/closure
- `#43` Review unsubscribe link behavior for provider error pages - open HITL follow-up

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue, when one exists
2. `AGENTS.md` for workflow and guardrails
3. `CONTEXT.md` for current stage and read order
4. `docs/v2-alignment.md` for current product direction
5. `docs/prd.md` for the completed MVP+3 Slice B Gmail companion shell polish slice
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
