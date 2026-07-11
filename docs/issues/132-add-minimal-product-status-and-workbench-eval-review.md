# Add Minimal Product Status and Workbench Eval Review

Status: Completed
Current as of: 2026-07-11
Triage state: `completed`
Parent PRD: `docs/prd-eval-promotion-pipeline-2026-07-10.md`
Blocked by: `docs/issues/131-add-per-candidate-promotion-override-and-audit-flow.md`

## Type

AFK

## User stories covered

- As the founder, I want the everyday product UI to show only lightweight evaluation state, so that the inbox surface stays simple.
- As the founder, I want a fuller workbench review surface for pending candidates, metrics, deltas, and overrides, so that the evaluation workflow is inspectable without cluttering the primary product.
- As the founder, I want single-email teaching to stay fast, so that the inbox workflow does not stall on full-corpus evaluation.

## What to build

Add the minimal product-side signals plus a fuller workbench review surface.

### Product-side behavior

Allow only small evaluation state signals such as:

- `Candidate saved`
- `Pending evaluation`
- `Recommended for promotion`
- `Needs review`

Do not expose the full benchmark/shadow metrics table in the normal Gmail companion flow.

### Workbench behavior

Add a fuller review surface for:

- pending candidate list
- candidate source and description
- latest recommendation
- baseline versus candidate deltas
- benchmark metrics
- shadow metrics by provider and split
- attention/action safety metrics
- promote / keep pending / reject / override-promote actions

This slice should keep the product UI intentionally sparse while making the evaluation workflow inspectable where it belongs.

## Acceptance criteria

- [x] Saving a reusable future rule can surface a minimal product-side candidate status without opening a dense evaluation panel.
- [x] Single-email corrections remain fast and do not automatically render a full evaluation review UI.
- [x] The product UI does not expose split-by-split benchmark and shadow tables in the primary companion flow.
- [x] A workbench view can list pending evaluated candidates and their current recommendations.
- [x] A workbench view can show enough per-candidate detail to support promote / keep pending / reject / override-promote decisions.
- [x] Tests prove minimal product copy remains decoupled from the fuller workbench details.
- [x] Tests prove the workbench can surface mixed recommendations across candidates from the same batch.
