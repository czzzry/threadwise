# Status

Current
Current as of: 2026-06-28
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

# Title

Generate family review packs and preference questions from shadow corpora

## Type

HITL

## Blocked by

- `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

## User stories covered

`2`, `3`, `4`, `5`, `12`, `18`, `20`

## What to build

Create a bounded review artifact that turns large shadow corpora into family-level decisions and compact founder questions.

The slice should:

- cluster recurring shadow families into a founder-reviewable pack
- separate taxonomy-like questions from founder-preference questions
- prioritize the smallest number of questions that unlock the largest number of messages
- preserve provider/account context and a few representative examples per family

This slice is HITL because its value comes from founder answers, not just artifact generation.

## Acceptance criteria

- [x] A local artifact can summarize recurring families as review units rather than individual emails.
- [x] The artifact distinguishes preference questions from likely objective category mappings.
- [x] The pack is small enough that the founder can answer it in a bounded session without reviewing the full inbox.

## Implemented

- Added `src/shadow_review_pack.py`, `src/shadow_review_pack_cli.py`, and `scripts/build_shadow_review_pack.py`.
- Added local artifact helpers for review-pack storage under `data/classifier_eval/review_packs/`.
- The pack now:
  - consumes the current eval-contract report
  - uses shadow-only discovery families rather than reviewed Gmail disagreements
  - preserves provider and account context in representative examples
  - separates:
    - `objective_reviews`
    - `preference_questions`
    - `taxonomy_questions`
  - sorts by family message count so the highest-leverage families appear first
- Current generated artifact:
  - `data/classifier_eval/review_packs/shadow-review-pack-20260628T062146Z.json`
  - `18` review units total
  - `87` messages covered
  - lane split: `2` objective, `4` preference, `12` taxonomy
