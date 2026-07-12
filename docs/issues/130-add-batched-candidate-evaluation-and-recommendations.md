# Add Batched Candidate Evaluation and Recommendations

Status: Proposed
Current as of: 2026-07-10
Triage state: `proposed`
Parent PRD: `docs/prd-eval-promotion-pipeline-2026-07-10.md`
Blocked by: `docs/issues/129-formalize-candidate-change-state-and-sources.md`

## Type

AFK

## User stories covered

- As the founder, I want candidates evaluated in batches, so that several small teachings can be judged together without slowing daily use.
- As the founder, I want the eval system to tell me whether reviewed Gmail behavior stayed stable, so that I do not quietly regress known-good behavior.
- As the founder, I want the eval system to tell me whether shadow coverage improved, so that I can see whether a change helps on harder real-world data.
- As the founder, I want attention misses and unsafe action suggestions surfaced explicitly, so that I do not accept improvements that make the system less trustworthy.
- As the founder, I want the final output to recommend `Promote`, `Review`, or `Reject`, so that the eval supports a real decision rather than dumping raw metrics.

## What to build

Add the core batched evaluation engine for pending candidate changes.

The evaluation path should:

1. gather pending candidates into one explicit batch
2. run local deterministic evaluation against the existing reviewed and shadow corpora
3. compare candidate results against a baseline
4. compute per-candidate and batch-level deltas
5. emit advisory recommendations:
   - `Promote`
   - `Review`
   - `Reject`

The metric set for v1 should include:

- reviewed Gmail exact-match rate
- reviewed Gmail overlap rate
- shadow unlabeled rate by provider and split
- attention miss count or attention recall
- unsafe-action count
- delta versus baseline

This slice should keep LLM-assisted analysis out of the core decision path. Optional LLM analysis can remain a later layer.

## Acceptance criteria

- [ ] Pending candidates can be evaluated together in one explicit batch run.
- [ ] The evaluation uses the current reviewed-versus-shadow trust boundary rather than collapsing all evidence into one score.
- [ ] The output includes both batch-level and per-candidate metric deltas versus baseline.
- [ ] The output computes recommendations using explicit policy logic rather than one opaque aggregate score.
- [ ] A candidate that improves discovery only but weakens validation or holdout can be recommended `Review` or `Reject`.
- [ ] A candidate that regresses reviewed Gmail behavior beyond the agreed threshold is not recommended `Promote`.
- [ ] A candidate that worsens attention misses or unsafe-action count is not recommended `Promote`.
- [ ] Tests prove one good candidate and one risky candidate in the same batch can receive different recommendations.

