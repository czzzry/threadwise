# Handoff: Issue 009 Live Gmail Retry Failed Writes Without Re-Review

## Context

This note records the implementation checkpoint for [docs/issues/009-live-gmail-retry-failed-writes-without-re-review.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/issues/009-live-gmail-retry-failed-writes-without-re-review.md).

This follows the confirmed live review and write-back checkpoint in [docs/handoff/issue-007-live-review-and-ea-writeback.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/issue-007-live-review-and-ea-writeback.md) and the later suggestion-quality checkpoint in [docs/handoff/issue-008-improve-live-gmail-label-suggestions.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/issue-008-improve-live-gmail-label-suggestions.md).

## What Changed

- Added a dedicated live Gmail retry CLI for one stored batch in `src/live_gmail_retry_cli.py`
- Added a repo-root script entrypoint in `scripts/retry_live_gmail_failed_writes.py`
- Reused the existing persisted write status and write-attempt history from the `007` write-back path
- Reused the bounded retry rule from the closed mocked seam in issue `005` without reopening that issue
- The retry command now retries only messages whose latest persisted write status is `failed`
- Failed messages whose current approved `final_labels` no longer match the latest failed-attempt labels are reported and skipped
- Repeated failed retries preserve `failed` status and append attempt history rather than overwriting prior records
- The retry command requests `gmail.modify` and keeps Gmail mutation limited to the existing `EA/` label creation/application path

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors:

- A dedicated public retry entrypoint exists for one stored live batch
- Only latest-`failed` messages are retried through the live retry command
- Changed-label failed messages are blocked and reported instead of being retried
- Repeated retry failures remain visible as failed and append to attempt history
- The retry path uses the existing `EA/` label mapping and `gmail.modify` scope
- One bounded live retry verification completed successfully against stored batch state using a synthetic latest failure with unchanged labels

## Validation

Focused regression verification:

```bash
python3 -m unittest tests.test_live_gmail_retry_cli -v
```

Related-path regression verification:

```bash
python3 -m unittest tests.test_live_gmail_retry_cli tests.test_live_gmail_review_cli tests.test_gmail_retry tests.test_gmail_writer -v
```

Result at the latest checkpoint: `27 tests passed`.

Manual live verification:

- One previously applied live-batch message was marked locally as a synthetic latest failure with unchanged approved labels
- The retry command was run once against `founder-test-batch-1`
- The command reported:
  - `Retryable failed writes: 1`
  - `Retried successfully: 1`
  - `Still failed after retry: 0`
  - `Blocked by changed labels: 0`
- Persisted local write status for the chosen message returned to `applied`
- Persisted write-attempt history for the chosen message became `applied -> failed -> applied`

## Important Constraints

- This checkpoint does not add background retrying, multi-batch reconciliation, re-review UX, label mutation outside the existing review flow, or any non-`EA/` Gmail behavior
- The retry command is intentionally batch-scoped and retries all retryable failures in that batch by default
- The manual verification in this checkpoint reused the existing `EA/` label write path only and did not broaden Gmail scope or mutation type

## Risks Or Open Questions

- The current command reports blocked changed-label messages, but does not yet offer any convenience UX beyond the bounded scope approved for this slice

## Recommended Next Step

Choose the next bounded slice before adding more Gmail workflow scope. A follow-up is only needed if blocked changed-label retries or broader retry ergonomics become a meaningful user pain point.
