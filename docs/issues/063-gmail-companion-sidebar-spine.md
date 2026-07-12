# Status

Completed
Current as of: 2026-06-29
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`

# Title

Build the Gmail companion sidebar spine and selected-email context contract

## Type

Feature

## Blocked by

- none

## User stories covered

`1`, `2`, `3`, `4`, `5`, `6`, `23`, `24`, `25`, `36`, `38`, `39`, `40`

## What to build

Deliver the foundational Gmail companion surface as one end-to-end vertical slice.

This slice should create the product shell that later slices build on:

- render a browser-based companion sidebar attached to Gmail
- make it minimizable
- detect the currently selected email
- show current classification first
- show handling status
- show a short plain-English reason
- provide a compact default state that is still useful when no correction is happening
- show a compact daily summary block sourced from existing report/runtime artifacts
- define the selected-email data contract and sidebar state contract other slices will consume

This slice should not yet implement the full correction conversation or unsubscribe product flow. It should freeze the shared UI spine and context contract so later work can move quickly without conflicting assumptions.

## Acceptance criteria

- [x] The Gmail companion sidebar can render beside Gmail and be minimized and restored.
- [x] The sidebar updates when the selected email changes.
- [x] The selected-email panel shows current classification, handling status, and a short reason in that order.
- [x] The sidebar has a safe compact state when no selected-email context is available.
- [x] The sidebar shows a compact daily summary that makes sense without leaving Gmail.
- [x] A documented selected-email contract exists for downstream slices.

## Output

- Gmail companion sidebar shell
- selected-email context contract
- sidebar state contract

## Completion note

Completed as part of the Gmail companion release tranche. See `docs/handoff/2026-06-29-slice-063-gmail-companion-sidebar-spine.md` and the later Gmail release closeout handoffs for the live sidebar and selected-email contract validation.
