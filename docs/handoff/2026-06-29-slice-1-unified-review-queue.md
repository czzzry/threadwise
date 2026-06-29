# Email Agent Handoff

Date: 2026-06-29
Repo: `/Users/cezarybaraniecki/Documents/AI project/email-agent`
Focus completed: Slice 1 landed as a unified review-queue contract for deterministic + memory + LLM + feedback work on stored corpora.

## Read first
1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/current-multi-agent-boundaries-2026-06-28.md`

## What changed

### 1. One canonical review queue now exists

New artifact path:
- `data/classifier_eval/unified_review_queue.json`

New implementation:
- `src/unified_review_queue.py`
- `src/unified_review_queue_cli.py`
- `scripts/build_unified_review_queue.py`

The queue now normalizes these previously separate review lanes into one item model:
- memory proposals
- shadow suggestion candidates
- safety dispositions
- runtime LLM candidates
- founder questions

### 2. Runtime cascade now refreshes the queue automatically

Updated:
- `src/runtime_cascade.py`
- `src/runtime_cascade_cli.py`

Behavior:
- stored-corpus runtime runs still write the runtime report
- the same run now also refreshes `unified_review_queue.json`
- serialized outcomes now preserve `subject_key`, `llm_rationale`, and `llm_confidence` so runtime LLM suggestions can be reviewed later without reparsing raw source batches

### 3. Accepted runtime LLM outcomes can be promoted into durable memory

Queue approval for `runtime-llm-candidate` now:
- creates provider-scoped memory proposals
- approves them into `data/classifier_eval/accepted_shadow_teachable_rules.json`
- preserves review state in the unified queue so the same candidate does not keep resurfacing as pending

### 4. Founder-question application now fits the same queue contract

Queue answer actions for `founder-question` now:
- build a founder answer decision
- apply it through the existing founder answer application path
- write resulting rules into `accepted_shadow_teachable_rules.json`
- record the queue item as applied

## Validation completed

Passed:
- `python3 -m unittest tests.test_unified_review_queue tests.test_unified_review_queue_cli tests.test_runtime_cascade tests.test_runtime_cascade_cli tests.test_memory_proposal_store tests.test_shadow_suggestion_memory tests.test_founder_answer_application tests.test_local_browser_review_ui tests.test_safety_disposition_store tests.test_safety_resolution_pack`

Result:
- `79` tests passed

## Important boundaries

- `data/classifier_eval/unified_review_queue.json` is now a single-writer artifact.
- `docs/current-multi-agent-boundaries-2026-06-28.md` was updated to mark that explicitly.
- The unified queue is implemented as a CLI/runtime contract first. The browser workbench has not yet been rewritten to natively review queue items.

## Current limitations

- Runtime LLM candidates are grouped by provider + sender key + normalized subject + suggested labels + safety lane. This is good enough for stored-corpus review, but not yet a richer family-cluster abstraction.
- Browser review still has its older dedicated proposal/disposition affordances; the queue is not yet the primary browser UX.
- Queue-driven founder answering currently routes through the existing founder-answer pack semantics rather than a new browser-native answer form.

## Recommended next slice

Take Slice 2 next:
- make the multi-inbox feedback flywheel use `unified_review_queue.json` as the canonical ranked operator surface
- rank items across providers by payoff, safety, and repeated-family leverage
- then either replace or wrap the current browser workbench around that queue
