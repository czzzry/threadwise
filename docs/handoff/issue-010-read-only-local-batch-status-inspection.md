# Handoff: Issue 010 Read-Only Local Batch Status Inspection

## Context

This note records the implementation checkpoint for [docs/issues/010-read-only-local-batch-status-inspection.md](docs/issues/010-read-only-local-batch-status-inspection.md).

This follows the live fetch, review/write, suggestion-quality, and retry checkpoints in:

- [docs/handoff/issue-006-live-gmail-readonly-smoke.md](docs/handoff/issue-006-live-gmail-readonly-smoke.md)
- [docs/handoff/issue-007-live-review-and-ea-writeback.md](docs/handoff/issue-007-live-review-and-ea-writeback.md)
- [docs/handoff/issue-008-improve-live-gmail-label-suggestions.md](docs/handoff/issue-008-improve-live-gmail-label-suggestions.md)
- [docs/handoff/issue-009-live-gmail-retry-failed-writes-without-re-review.md](docs/handoff/issue-009-live-gmail-retry-failed-writes-without-re-review.md)

## What Changed

- Added a dedicated read-only local batch inspection CLI in `src/local_batch_status_cli.py`
- Added a repo-root script entrypoint in `scripts/inspect_local_batch_status.py`
- The command reads only stored local batch artifacts:
  - batch items
  - fetch failures
  - persisted write status
  - persisted write-attempt history
- The default output is privacy-safe and summary-only:
  - no snippets
  - no bodies
  - no sender lines
  - no subject lines
- The summary reports batch-level visibility across fetch, review, final labels, write status, and retry history using the existing stored contracts
- Missing optional write-status or write-attempt files are handled cleanly instead of failing

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors:

- A dedicated public inspection entrypoint exists for one stored local batch
- Default output summarizes stored batch state without printing private email content by default
- Final label counts are derived from reviewed `final_labels`, not suggested `applied_labels`
- Missing optional write-status and write-attempt files are surfaced cleanly
- The command performs no Gmail API calls, no Gmail writes, and no local state mutation

## Validation

Focused regression verification:

```bash
python3 -m unittest tests.test_local_batch_status_cli -v
```

Related-path regression verification:

```bash
python3 -m unittest tests.test_local_batch_status_cli tests.test_live_gmail_review_cli tests.test_live_gmail_retry_cli -v
```

Result at the latest checkpoint: `19 tests passed`.

Manual local verification:

Command run:

```bash
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-1
```

Observed summary:

- `Batch ID: founder-test-batch-1`
- `Account ID: founder-test`
- `Items: 10`
- `Fetch failures: 0`
- `Review states: pending=1, reviewed=9`
- `Review actions: approve=2, edit=7`
- `Final labels: labeled=7, unlabeled=2`
- `Label counts: EA/LowValue=5, EA/Promotions=2`
- `Write status: applied=7, missing=3`
- `Write attempts: messages_with_history=7, total_attempts=9, retried_messages=1`

This confirms the default summary is useful on the real stored batch while remaining privacy-safe.

## Important Constraints

- This slice is strictly local and read-only
- The command does not perform Gmail fetch, review, write, or retry actions
- The default output intentionally avoids message content and message-identifying detail beyond batch/account level summary
- No broader dashboard, multi-batch reporting, or detail view was added in this slice

## Risks Or Open Questions

- The current command is intentionally summary-only; if later needed, any more detailed inspection mode should be treated as a separate bounded slice because it affects privacy/data-exposure decisions
- The summary is batch-scoped only and does not yet help compare multiple batches over time

## Recommended Next Step

Choose the next bounded slice only if a new concrete operational pain is now clear. If the next need is deeper inspection, treat that as a separate privacy-sensitive alignment step rather than extending this command implicitly.
