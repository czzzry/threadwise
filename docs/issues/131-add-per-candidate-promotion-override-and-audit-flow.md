# Add Per-Candidate Promotion, Override, and Audit Flow

Status: Proposed
Current as of: 2026-07-10
Triage state: `proposed`
Parent PRD: `docs/prd-eval-promotion-pipeline-2026-07-10.md`
Blocked by: `docs/issues/130-add-batched-candidate-evaluation-and-recommendations.md`

## Type

AFK

## User stories covered

- As the founder, I want per-candidate recommendations inside a batch, so that one risky rule does not block several safe ones.
- As the founder, I want to retain final override authority, so that product judgment can still overrule the eval when needed.
- As the founder, I want overrides recorded with a reason, so that future review can distinguish accepted risk from silent drift.

## What to build

Add the decision flow on top of evaluated candidates.

After a batch evaluation, the system should allow per-candidate actions:

- promote candidate
- keep candidate pending
- reject candidate
- override-promote candidate

This slice should persist:

- chosen action
- who made the decision
- when it happened
- the latest evaluation recommendation
- an override reason when a `Reject` recommendation is overruled

This is the slice that turns the eval system from “numbers generator” into a real promotion workflow.

## Acceptance criteria

- [ ] Evaluated candidates can be promoted individually without forcing an all-or-nothing batch decision.
- [ ] Candidates can remain pending after evaluation instead of being forced into immediate promote/reject.
- [ ] Candidates recommended `Reject` can still be override-promoted by the founder.
- [ ] Override-promoted candidates persist a non-empty override reason.
- [ ] Promoted, rejected, kept-pending, and override-promoted states are durable and reloadable.
- [ ] The system preserves the latest recommendation alongside the final human decision.
- [ ] Tests prove one safe candidate can be promoted while another candidate from the same batch remains pending or is rejected.
- [ ] Tests prove override promotion is explicit and audited rather than silent.

