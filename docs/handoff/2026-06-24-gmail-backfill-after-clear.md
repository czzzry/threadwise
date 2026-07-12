# Handoff

Current as of: 2026-06-24

## Read first

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/handoff/2026-06-24-gmail-backfill-runtime-hardening.md`
7. this handoff

## Current state

- Gmail historical backfill has now reached `founder-test-batch-36`.
- Stored replay is currently `PASS`.
- Current replay summary:
  - `36` stored batches
  - `2440` stored messages
  - `36` replay-pass batches
  - `0` replay-warn batches
  - `0` replay-pause batches
  - `0` frontier remaining unlabeled
  - `20` batches with verified mutation evidence
  - `0` mutation-policy violations

## Decision made

- The founder approved treating repeated University of Europe admissions / study-enquiry follow-up mail as `spam-low-value`.
- Rationale: schooling is not expected to be a real ongoing inbox category for this workflow, so these follow-ups should not block whole-inbox readiness.

## What changed in the final step

- Added a narrow classifier rule in `src/fixture_classifier.py` for:
  - `Jordan Example <university.contact@example.test>`
  - subject family `Your enquiry with University of Europe for Applied Sciences`
  - follow-up language about joining, discussing studies, or student recruitment
  - mapped to `spam-low-value`
- Added regression coverage in `tests/test_fixture_classifier.py`.
- This closes the last `3` replay unlabeled items from `founder-test-batch-36`.

## Validation

- `python3 -m unittest tests.test_fixture_classifier`
- Passed with `95` tests.
- `python3 -m unittest tests.test_live_gmail_client tests.test_fixture_classifier tests.test_live_gmail_daily_run_cli tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli`
- Passed with `140` tests.
- `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- Result: `PASS`, including `founder-test-batch-36` at `0` replay unlabeled.

## Exact next step after `/clear`

1. Resume live backfill:
   - `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 100`
2. If new run-time unlabeled exceptions appear:
   - inspect `data/gmail_fetch/batches/founder-test-batch-<N>.json`
   - add narrow tests first in `tests/test_fixture_classifier.py`
   - add the smallest corresponding rules in `src/fixture_classifier.py`
   - rerun:
     - `python3 -m unittest tests.test_live_gmail_client tests.test_fixture_classifier tests.test_live_gmail_daily_run_cli tests.test_gmail_readiness_replay_cli tests.test_gmail_readiness_check_cli tests.test_weekly_inbox_report_cli tests.test_local_batch_status_cli tests.test_unlabeled_exception_report_cli`
     - `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
3. Keep going autonomously until the next real product ambiguity or hard runtime blocker.

## User preference

- Minimize interruptions.
- Live Gmail access and bounded Gmail mutations for this workflow are already approved.
