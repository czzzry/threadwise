# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

Read in this order:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md` when a current bounded slice is active
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/v2-issue-map.md`

Read `docs/adr/` too when it exists and is relevant.

## Trust order

When docs disagree, use this order:

1. current task-specific PRD or triaged issue
2. `AGENTS.md`
3. `CONTEXT.md`
4. `docs/prd.md` when it is the current bounded slice
5. current checkpoint
6. current alignment
7. candidate issue map
8. archive, handoff, and deep-research docs as historical context only

## File structure

This repo is treated as a single-context repo.

## Use the glossary's vocabulary

When output names a domain concept, use the terms defined in `CONTEXT.md` if present.

## Flag ADR conflicts

If a proposal conflicts with an ADR, surface that conflict explicitly instead of silently overriding it.
