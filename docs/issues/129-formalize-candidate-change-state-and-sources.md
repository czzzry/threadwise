# Formalize Candidate Change State and Sources

Status: Proposed
Current as of: 2026-07-10
Triage state: `proposed`
Parent PRD: `docs/prd-eval-promotion-pipeline-2026-07-10.md`

## Type

AFK

## Blocked by

None - can start immediately

## User stories covered

- As the founder, I want reusable future rules to enter a candidate state first, so that broad behavior changes are reviewed before promotion.
- As the founder, I want broader classifier-behavior changes to use the same evaluation lens, so that product teaching and code-level improvements do not follow incompatible trust models.
- As the founder, I want single-email teaching to stay fast, so that the inbox workflow does not stall on full-corpus evaluation.

## What to build

Create one durable candidate-change model for classification-behavior changes.

The slice should define and persist:

- candidate change kinds:
  - future rule
  - rule amendment
  - compiled teaching batch
  - classifier-behavior code change
- candidate lifecycle states:
  - pending
  - evaluated
  - recommended-promote
  - recommended-review
  - recommended-reject
  - promoted
  - rejected
  - override-promoted
- candidate metadata:
  - source
  - created_at
  - description
  - affected scope summary
  - baseline reference
  - latest evaluation reference
  - optional override reason

The model should clearly separate:

- one-off single-email correction
- reusable change candidate

This slice is about durable state and source-of-change modeling only. It should not yet implement the evaluation engine or the promotion recommendation logic.

## Acceptance criteria

- [ ] Reusable future rules can be stored as durable candidates instead of being treated as immediately promoted global logic.
- [ ] Rule amendments can be represented as reusable candidates with source metadata.
- [ ] A classifier-behavior code change can be declared as a candidate using the same durable model.
- [ ] Single-email corrections remain outside the candidate pipeline by default.
- [ ] Candidate lifecycle states are explicit and durable.
- [ ] Candidate records can point to their latest evaluation artifact without embedding the full evaluation result.
- [ ] Tests prove one-off corrections do not become candidates automatically.
- [ ] Tests prove at least one product-originated candidate and one code-originated candidate can be persisted and reloaded.

