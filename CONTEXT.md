# CONTEXT.md

Status: Current repo context
Current as of: 2026-06-23

This file exists to keep agents from re-litigating old project stages or mistaking historical docs for current instructions.

## Read Order

Before doing substantial work, read these in order:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md` when a current bounded slice is active
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/v2-issue-map.md`
6. then only the specific current issue, handoff, or code relevant to the task

## What This Repo Currently Is

The repo is past the original Gmail MVP and already proves:

- a Gmail daily run with bounded label write-back
- bounded `INBOX` removal for low-value Gmail mail
- daily and weekly reporting
- provider-aware local artifacts
- ProtonMail read-only import, live fetch, and daily run paths
- unsubscribe inventory, supported execution, and manual follow-up
- local browser review and workbench tools

The repo is no longer blocked on basic implementation.

## Current Stage

This is a post-MVP, post-proven-slices repo.

The main uncertainty is no longer "can this be built?" It is "which next product version are we actually finishing?"

There is now one current bounded PRD for Gmail trust hardening at `docs/prd.md`.

## Current Working Rule

Do not restart first-principles Gmail-MVP discovery.

Do not infer an approved next build from `docs/v2-issue-map.md`, old handoffs, or archived V1 planning docs.

Before broadening the product further, do a focused grill on the next smallest marketable and trustable version, then write one current PRD or scope note for that slice.

## Trust Order When Docs Differ

Use this order:

1. current task-specific PRD or triaged issue, when one exists
2. `AGENTS.md` for workflow and guardrails
3. `CONTEXT.md` for current stage and read order
4. `docs/prd.md` for the current bounded slice
5. `docs/checkpoints/current-operating-model-2026-06-22.md` for what the repo currently proves
6. `docs/v2-alignment.md` for product direction
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

If a task changes product scope, chooses the next major slice, or pushes beyond the current trust boundary, stop and align first.
