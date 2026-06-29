# Handoff

Status: Current handoff
Current as of: 2026-06-29
Builds on: `docs/v2-alignment.md`, `docs/prd.md`, `docs/current-multi-agent-boundaries-2026-06-28.md`

## What changed

The repo docs were realigned away from the completed memory/runtime milestone and toward the next product milestone: the Gmail inbox companion release.

Current source-of-truth docs now point to:

- `docs/v2-alignment.md` for mature-product direction
- `docs/prd.md` for the current Gmail release brief
- `docs/issues/063-gmail-companion-sidebar-spine.md` as the first implementation slice

The old milestone PRD was preserved at:

- `docs/archive/prd-memory-runtime-milestone-completed-2026-06-29.md`

## Current product position

The backend trust milestone is complete enough to stop treating classifier leverage as the main product risk.

The main product risk is now productization:

- the product must live in Gmail
- the sidebar is the primary surface
- `Correct / Teach` must happen in inbox context
- broader reclassification requires confirmation first
- dashboard and unsubscribe flows support the inbox surface instead of replacing it

## Approved big slices

1. `063` sidebar spine and selected-email contract
2. `064` in-inbox `Correct / Teach` with impact preview and confirmation
3. `065` sidebar daily summary and unsubscribe handoff
4. `066` Gmail release hardening and supervised acceptance

## Multi-agent recommendation

- Do `063` alone first.
- After `063` freezes the shared contracts, `064` and `065` are the best parallel pair.
- Do `066` only after `064` and `065` merge.

See `docs/current-multi-agent-boundaries-2026-06-28.md` for the current coordination rule.

## What is now historical

Treat these as historical for current planning:

- `docs/archive/prd-memory-runtime-milestone-completed-2026-06-29.md`
- older handoffs focused on unresolved-rate reduction, queue drain, and compiled-rule hardening
- `docs/v2-issue-map.md` as candidate mapping only, not implementation authority

## Recommended next step

Start implementation on `docs/issues/063-gmail-companion-sidebar-spine.md`.
