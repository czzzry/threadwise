# Eval / Promotion Pipeline PRD

Status: Completed bounded-slice PRD
Current as of: 2026-07-11
Builds on: `AGENTS.md`, `CONTEXT.md`, `docs/v2-alignment.md`, `docs/current-multi-inbox-eval-contract-2026-06-28.md`, `docs/issues/056-read-only-two-inbox-shadow-classifier-evaluation.md`, and `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`
Supersedes as next planning focus: ad hoc eval scaffolds and one-off corpus runs for classifier-change decisions

## Problem Statement

Threadwise already has pieces of an evaluation story:

1. a reviewed Gmail benchmark
2. shadow corpora for ProtonMail and Outlook/Hotmail
3. a documented eval contract
4. local corpus-eval and shadow-eval tooling
5. a growing in-product teaching loop that can produce reusable future rules

What it does not yet have is one coherent promotion workflow that answers the founder's real decision:

> Should this proposed rule or classifier-behavior change become part of the system?

Right now, the repo can produce evaluation artifacts, but it still relies on manual interpretation and developer judgment to connect:

- taught future rules
- broader deterministic classifier logic changes
- benchmark stability
- shadow improvements
- attention-safety regressions
- final promote / review / reject decisions

That gap weakens both the product-development loop and the story the founder can honestly tell about how Threadwise improves over time.

## Solution

Build one evaluation and promotion pipeline for classification-behavior changes.

The pipeline should cover two sources of proposed reusable change:

1. in-product reusable rule candidates such as future rules and rule amendments
2. broader classifier-behavior changes such as deterministic classifier logic or label-decision code updates

The system should separate fast product interaction from slower evaluation:

1. single-email teaching remains immediate
2. reusable changes enter a `candidate` state
3. candidates are evaluated in an explicit batch checkpoint
4. the system compares the candidate set against a baseline on reviewed and shadow corpora
5. the system produces per-candidate and batch-level recommendations
6. the founder can promote, defer, reject, or override-promote individual candidates

The core evaluation path should remain local and deterministic by default. Optional LLM assistance may help cluster failures, compare against a shadow model, or suggest rule directions, but it must not be required for the core recommendation flow.

## User Stories

1. As the founder, I want single-email teaching to stay fast, so that the inbox workflow does not stall on full-corpus evaluation.
2. As the founder, I want reusable future rules to enter a candidate state first, so that broad behavior changes are reviewed before promotion.
3. As the founder, I want broader classifier-behavior changes to use the same evaluation lens, so that product teaching and code-level improvements do not follow incompatible trust models.
4. As the founder, I want the eval system to tell me whether reviewed Gmail behavior stayed stable, so that I do not quietly regress known-good behavior.
5. As the founder, I want the eval system to tell me whether shadow coverage improved, so that I can see whether a change helps on harder real-world data.
6. As the founder, I want attention misses and unsafe action suggestions surfaced explicitly, so that I do not accept improvements that make the system less trustworthy.
7. As the founder, I want candidates evaluated in batches, so that several small teachings can be judged together without slowing daily use.
8. As the founder, I want per-candidate recommendations inside a batch, so that one risky rule does not block several safe ones.
9. As the founder, I want the final output to recommend `Promote`, `Review`, or `Reject`, so that the eval supports a real decision rather than dumping raw metrics.
10. As the founder, I want to retain final override authority, so that product judgment can still overrule the eval when needed.
11. As the founder, I want overrides recorded with a reason, so that future review can distinguish accepted risk from silent drift.
12. As the founder, I want the everyday product UI to show only lightweight evaluation state, so that the inbox surface stays simple.
13. As the founder, I want a fuller workbench review surface for pending candidates, metrics, deltas, and overrides, so that the evaluation workflow is inspectable without cluttering the primary product.

## Proposed Workflow

### Product-side flow

1. Teach or correct a single email.
2. If the change is one-off, apply it locally and stop there.
3. If the change is reusable, save it as a `candidate` future rule or amendment.
4. Show a minimal status such as:
   - `Candidate saved`
   - `Pending evaluation`
   - `Recommended for promotion`
   - `Needs review`

### Evaluation-side flow

1. The founder or operator chooses `Evaluate pending changes`.
2. Threadwise builds a candidate batch from:
   - pending future rules
   - pending reusable rule amendments
   - optionally declared classifier-behavior code changes
3. Threadwise runs local deterministic evaluation against:
   - reviewed Gmail benchmark
   - shadow corpora by provider and split
4. Threadwise computes:
   - reviewed Gmail exact-match rate
   - reviewed Gmail overlap rate
   - shadow unlabeled rate by provider and split
   - attention miss count or attention recall
   - unsafe-action count
   - per-change delta versus baseline
5. Threadwise generates:
   - batch summary
   - per-candidate summary
   - recommendation for each candidate:
     - `Promote`
     - `Review`
     - `Reject`
6. The founder can then:
   - promote candidate
   - keep candidate pending
   - reject candidate
   - override-promote candidate with recorded reason

## Implementation Decisions

- The core eval path must remain local and deterministic by default.
- LLM-based analysis is optional and secondary:
  - allowed uses: failure clustering, shadow-model comparison, candidate-rule suggestion
  - disallowed use: replacing the deterministic eval recommendation path
- Single-email teaching must not trigger a full corpus run.
- Reusable changes should default to `candidate` rather than immediate global promotion.
- Batch evaluation should be the default checkpoint model; continuous per-save full eval is out of scope.
- Per-candidate decisions must be preserved even when evaluation runs in batch.
- The system should support both:
  - product-originated candidates such as future rules
  - developer-originated classifier-behavior candidates
- The founder keeps final authority. Eval recommendations are advisory, not hard-blocking.
- Overrides should be explicit and durable.
- The recommendation model should be legible and policy-based rather than hidden behind one aggregate score.
- The current eval contract remains the trust boundary for reviewed vs shadow evidence and for discovery/validation/holdout interpretation.

## Metrics

### Reviewed benchmark metrics

- Gmail exact-match rate
- Gmail overlap rate

These protect known-good behavior.

### Shadow improvement metrics

- unlabeled rate by provider
- unlabeled rate by split:
  - discovery
  - validation
  - holdout

These show whether proposed changes improve broader coverage without overclaiming unseen generalization.

### Safety and prioritization metrics

- attention miss count or attention recall
- unsafe-action count

These keep the system focused on prioritization and action safety rather than label accuracy alone.

### Decision metrics

- per-candidate delta versus baseline
- batch delta versus baseline

These turn the output into an accept/review/reject workflow instead of a static report.

## Recommendation Policy

The system should produce both a batch-level summary and per-candidate recommendations.

Recommended default logic:

- `Promote`
  - benchmark stable within agreed threshold
  - no safety regression
  - shadow results improve or remain acceptably stable
- `Review`
  - mixed deltas
  - unclear tradeoff
  - localized benefit with broader uncertainty
- `Reject`
  - benchmark regressed beyond threshold
  - unsafe-action count worsened
  - attention misses worsened materially
  - discovery improved but validation/holdout evidence weakens materially

These recommendations are advisory. The founder may override them.

## UI Model

### Everyday product UI

Keep the product UI minimal.

Allowed surface area:

- candidate saved
- pending evaluation
- recommended for promotion
- needs review

Avoid exposing the full evaluation table in the primary Gmail companion flow.

### Workbench / internal review UI

This is where the richer workflow should live:

- pending candidate list
- candidate source and description
- baseline versus candidate deltas
- reviewed benchmark metrics
- shadow metrics by provider and split
- attention/action safety metrics
- recommendation
- override reason
- promote / keep pending / reject controls

## Testing Decisions

- Start with tests that characterize the current candidate-rule and corpus-eval behavior before introducing promotion logic.
- Add tests for candidate state transitions:
  - saved -> pending eval -> recommended -> promoted / kept / rejected / override-promoted
- Add tests that prove single-email teaching does not trigger full evaluation.
- Add tests that prove batch evaluation preserves per-candidate recommendations.
- Add tests that prove overrides are recorded durably.
- Add tests that prove benchmark/shadow metrics are computed against the correct evidence buckets.
- Add tests that prove the recommendation output changes when:
  - benchmark regresses
  - shadow improves
  - attention misses worsen
  - unsafe actions worsen
- Add tests that prove minimal product UI copy stays decoupled from the full workbench detail view.

## Out of Scope

- Replacing the existing deterministic classifier with an LLM-first classifier.
- Using an LLM as the core evaluator.
- Requiring live provider fetches for promotion decisions.
- Redesigning the full companion UI around evaluation surfaces.
- Forcing all developer code changes through one CI gate in the first slice.
- Background autonomous promotion without founder review.
- Fully automated rollback or undo behavior for promoted changes.

## Recommended Vertical Slices

1. Formalize candidate change types and durable state.
2. Add batched candidate evaluation with baseline deltas and advisory recommendations.
3. Add per-candidate promote / keep pending / reject / override-promote actions.
4. Add minimal product-side status plus fuller workbench review surface.
5. Add optional LLM-assisted failure clustering and shadow-model comparison as secondary tools.
