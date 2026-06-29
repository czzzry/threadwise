# Email Agent Handoff

Date: 2026-06-29
Repo: `.`
Focus completed: drained the pending review queue, fixed a compiled-rule overwrite bug, and restored the loop to a stable `PASS` state with zero pending queue items.

## Read first
1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/handoff/2026-06-29-pass-threshold-via-hotspot-sender-memory.md`

## What changed

### 1. Remaining pending queue items were resolved

Behavior:
- approved the two pending memory proposals
- approved or rejected the remaining shadow suggestions
- queue summary is now `pending_count = 0`

### 2. Fixed shadow-rule export so it no longer clobbers broader memory

Updated:
- `src/shadow_suggestion_memory.py`
- `tests/test_shadow_suggestion_memory.py`

Bug:
- exporting accepted shadow suggestions rewrote `accepted_shadow_teachable_rules.json`
- that dropped previously approved hotspot/memory rules and caused runtime regression

Fix:
- shadow export now preserves non-shadow rules and only refreshes shadow-exported rules

### 3. Added deterministic rebuild for compiled rules

Added:
- `src/compiled_rule_rebuild.py`
- `src/compiled_rule_rebuild_cli.py`
- `scripts/rebuild_compiled_rules.py`
- `tests/test_compiled_rule_rebuild.py`

Behavior:
- rebuilds the compiled rule file from approved memory proposals
- then merges accepted shadow suggestion rules on top
- gives the repo a deterministic recovery path if compiled rules ever drift again

### 4. Preserved approved rule ids when reconstructing proposal-backed rules

Updated:
- `src/memory_proposal_store.py`

Behavior:
- proposal-backed rule reconstruction now reuses `approved_rule_id` when available instead of inventing a fresh id

## Validation completed

Passed:
- `python3 -m unittest tests.test_compiled_rule_rebuild tests.test_shadow_suggestion_memory tests.test_hotspot_sender_memory_backfill tests.test_unified_review_queue`

Ran:
- `python3 scripts/rebuild_compiled_rules.py --output-storage-dir data/classifier_eval`
- `python3 scripts/run_runtime_cascade.py --output-storage-dir data/classifier_eval --gmail-storage-dir data/gmail_fetch --protonmail-storage-dir data/protonmail_fetch --outlookmail-storage-dir data/outlookmail_fetch --accepted-shadow-rules-path data/classifier_eval/accepted_shadow_teachable_rules.json`
- `python3 scripts/build_unified_review_queue.py build --output-storage-dir data/classifier_eval --gmail-storage-dir data/gmail_fetch --protonmail-storage-dir data/protonmail_fetch --outlookmail-storage-dir data/outlookmail_fetch`
- `python3 scripts/check_operational_readiness.py --output-storage-dir data/classifier_eval`
- `python3 scripts/check_unresolved_gap.py --output-storage-dir data/classifier_eval`

## Current measured state

Latest runtime:
- run: `runtime-cascade-20260629T080445Z`
- unresolved: `494 / 5398`
- unresolved rate: `9.15%`
- deterministic: `2874`
- memory: `2030`
- LLM: `0`

Latest readiness:
- status: `PASS`
- queue pending count: `0`
- founder-question count: `0`

Latest gap report:
- remaining gap: `0`
- top remaining action is optional next leverage, not a threshold blocker:
  - `gmail | mailer@certs.knowledgehut.com | expected gain 22`

## Important note

Two bad runtime runs were generated during this tranche while the compiled-rule overwrite bug was still present:
- `runtime-cascade-20260629T075956Z`
- `runtime-cascade-20260629T080214Z`

They are historical artifacts from a known bug window, not the current stable state.

The latest trustworthy state is:
- `runtime-cascade-20260629T080445Z`
- `operational-readiness-20260629T080556Z`

## Recommended next step

Treat the current bounded goal as complete:
- queue drained
- compiled rules hardened
- supervised loop back at `PASS`

If work continues, the next slice should be optional refinement:
- compress the remaining unresolved tail further from `9.15%`
- starting with `mailer@certs.knowledgehut.com` and a few remaining Outlook/Proton hotspot families
