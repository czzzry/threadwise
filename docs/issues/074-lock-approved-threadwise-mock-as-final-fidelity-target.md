# Status

Completed
Current as of: 2026-06-30
Triage state: `completed`
Builds on: `docs/prd.md`, `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

# Title

Lock approved Threadwise mock as final fidelity target

## Type

HITL / Design checkpoint

## Blocked by

None - can start immediately.

## User stories covered

`21`, `24`, `25`, `26`, `41`, `44`

## What to build

Record the current design-reference mock as the final visual target for the MVP+1 implementation pass.

The approved target is `docs/design ideas/Threadwise_design.html`, with `docs/design ideas/Threadwise_design_preview.png` used as the quick visual reference. The header should use the Threadwise threaded-`T` app icon and the tagline `CLEAR THREADS. BETTER INBOX.`

This slice exists because the earlier visual implementation and demo capture treated the mock as loose direction instead of a fidelity target. Issue `069` and issue `071` are historical completed work, but they are not the final visual baseline for MVP+1. Future agents should treat the mock as the source of truth for visual structure, hierarchy, typography, borders, spacing, color, button styling, and the Gmail-left / Threadwise-right composition.

## Acceptance criteria

- [x] The approved mock HTML and PNG preview are present in the repo.
- [x] The mock uses the Threadwise threaded-`T` app icon in the header.
- [x] The mock header tagline reads `CLEAR THREADS. BETTER INBOX.`
- [x] The issue explicitly records that `069` and `071` are not the final visual baseline.
- [x] The founder approves this mock as the fidelity target before product implementation resumes.

## Output

- Approved design-fidelity checkpoint
- Clear dependency target for the implementation pass

## Boundaries

- Do not implement product UI changes in this slice.
- Do not recapture GIFs or screenshots in this slice.
- Do not change product scope or add new interactions.

## Completion Note

Completed on: 2026-06-30

Approved fidelity target:

- `docs/design ideas/Threadwise_design.html`
- `docs/design ideas/Threadwise_design_preview.png`

Founder direction captured:

- use the Threadwise app icon with the threaded `T`
- use the header tagline `CLEAR THREADS. BETTER INBOX.`
- implement the mock faithfully before regenerating demo materials
