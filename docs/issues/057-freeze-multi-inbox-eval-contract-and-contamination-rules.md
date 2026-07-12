# Status

Completed
Current as of: 2026-06-28
Triage state: `completed`
GitHub issue: `#1`
Builds on: `docs/prd.md`, `docs/issues/056-read-only-two-inbox-shadow-classifier-evaluation.md`

# Title

Freeze multi-inbox eval contract and contamination rules

## Type

AFK

## Blocked by

None - can start immediately

## User stories covered

`7`, `8`, `16`, `17`, `18`, `21`

## What to build

Write and enforce the current evaluation contract for Gmail, ProtonMail, and Hotmail stored corpora.

The slice should define:

- what each corpus is allowed to prove
- what counts as discovery, validation, and holdout usage
- what kinds of inspection contaminate a set
- which claims are still honest after current exploratory work
- what artifact fields must exist so later slices can rely on one stable contract

The output should be a durable current doc and any bounded code/test changes needed so future eval runs encode the contract explicitly rather than relying on memory.

## Acceptance criteria

- [x] A current doc states the trust level and contamination rules for Gmail, ProtonMail, and Hotmail corpora.
- [x] The distinction between discovery, validation, and holdout is explicit and consistent with current artifacts.
- [x] Future agents can tell whether a proposed improvement is allowed to use a given evidence bucket without re-reading old handoffs.

## Implemented

- Added the current contract note at `docs/current-multi-inbox-eval-contract-2026-06-28.md`.
- Extended `classifier_corpus_eval` reports with:
  - top-level `eval_contract`
  - explicit named corpus policies
  - shadow split policy and salt
  - per-provider `evidence_bucket_counts`
- Updated the corpus-eval CLI to print the active eval-contract doc path.
- Added test coverage for the new report and CLI contract fields.

Completed in repo before GitHub issue closeout sync on 2026-07-01.
