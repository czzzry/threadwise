# MVP v0.1 Acceptance

## Scope Of This Checkpoint

This note records the bounded MVP v0.1 wrap-up after issues `001` through `017`.

The purpose is not to add new product scope, but to confirm the current happy path, including the local browser review surface and its handoff into approved Gmail label write-back.

## Accepted Happy Path

The current accepted operator sequence is:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/retry_live_gmail_failed_writes.py --batch-id founder-test-batch-N
python3 scripts/remove_inbox_for_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-N
python3 scripts/list_local_batches.py
```

Replace `founder-test-batch-N` with the actual stored batch id.

## What Is Proven

- one local Gmail account can be fetched manually into stored local batches
- stored batches can be reviewed locally in a browser without Gmail API calls or Gmail writes
- browser review decisions are saved into the same stored review contract used by the CLI flow
- after browser review, `review_live_gmail_batch.py` can go straight to dry-run/apply without forcing the same items through re-review
- approved `EA/` labels can be written back to Gmail only after explicit confirmation
- failed label writes can be retried without re-review when the approved labels are unchanged
- reviewed low-value/promotions messages can optionally have `INBOX` removed after label write-back
- stored batch state can be inspected locally with privacy-safe summary commands

## Validation In This Checkpoint

- browser review tests
- review/apply CLI tests
- command help sanity checks for the current happy-path commands

No live Gmail writes or OAuth flows were run in this checkpoint.

## Known Limits

- browser review is the preferred review surface, but label write-back still happens through the CLI confirmation step
- inspection remains summary-oriented and read-only by default
- there is still no explicit local feedback/reporting slice over stored review outcomes beyond counts and friction signals

## Recommended Next Issue

Title:
`018: local feedback/reporting summary from stored review outcomes`

Boundary:
Add a local-only summary/report command over existing stored batch review outcomes so the founder can see usefulness signals such as reviewed counts, label-change rate, unlabeled/rejected rates, and write-failure patterns across stored batches, without Gmail calls, without exposing private email content by default, and without turning the project into a dashboard rewrite.
