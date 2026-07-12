# Status

Completed
Current as of: 2026-06-28
Triage state: `completed`
GitHub issue: `#3`
Builds on: `docs/prd.md`, `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

# Title

Harden shadow suggestion memory and review loop

## Type

AFK

## Blocked by

- `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

## User stories covered

`5`, `6`, `12`, `13`, `14`, `15`, `21`

## What to build

Stabilize the local suggestion-memory workflow so that model-backed family candidates can be reviewed, persisted, refreshed, and exported without race conditions, silent regression, or provider leakage.

The slice should formalize:

- pending / accepted / rejected transitions
- durability across refreshes
- provider-scoped export of accepted memory
- artifact fields required for later runtime use
- projection reporting that shows whether accepted memory improves shadow corpora without regressing Gmail benchmark behavior

## Acceptance criteria

- [x] Accepted and rejected candidates survive future suggestion-memory refreshes.
- [x] Exported accepted rules remain provider-scoped unless explicitly widened later.
- [x] Projection over stored corpora reports before/after deltas and does not silently regress Gmail benchmark behavior.

## Implemented

- `ShadowSuggestionMemory.merge_candidates` preserves accepted/rejected review state across refreshes.
- Accepted shadow exports write provider-scoped `TeachableRule` entries.
- Classifier corpus eval reports accepted-rule projection deltas and matched shadow-rule counts.
- Focused coverage lives in `tests/test_shadow_suggestion_memory.py`, `tests/test_classifier_corpus_eval.py`, and `tests/test_classifier_corpus_eval_cli.py`.

Completed in repo before GitHub issue closeout sync on 2026-07-01.
