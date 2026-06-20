# Handoff: Issue 011 Read-Only Local Batch Index

## Context

This note records the implementation and live acceptance checkpoint for [docs/issues/011-read-only-local-batch-index.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/issues/011-read-only-local-batch-index.md).

This follows the local batch inspection checkpoint in [docs/handoff/issue-010-read-only-local-batch-status-inspection.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/issue-010-read-only-local-batch-status-inspection.md).

## What Changed

- Added a dedicated read-only local batch-index CLI in `src/local_batch_index_cli.py`
- Added a repo-root script entrypoint in `scripts/list_local_batches.py`
- Extracted shared local summary logic into `src/local_batch_summary.py` so batch summary and batch index read the same stored contracts
- Kept new code limited to local visibility only:
  - no Gmail API calls
  - no Gmail writes
  - no retry actions
  - no message-content output by default

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors:

- A dedicated public batch-index entrypoint exists
- The index lists multiple stored batches with useful high-level status
- The output remains privacy-safe by default
- Missing optional local write-status/history files are handled cleanly
- A second real live batch now exists and is visible alongside the original batch in the local index

## Validation

Focused regression verification:

```bash
python3 -m unittest tests.test_local_batch_index_cli -v
```

Related-path regression verification:

```bash
python3 -m unittest tests.test_local_batch_status_cli tests.test_local_batch_index_cli tests.test_live_gmail_fetch_cli tests.test_live_gmail_review_cli tests.test_live_gmail_retry_cli -v
```

Result at the latest checkpoint: `31 tests passed`.

Manual live verification:

Command run to create the second real batch:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
```

Observed result:

```text
Fetched 10 new messages into founder-test-batch-2.
```

Command run to inspect stored batches:

```bash
python3 scripts/list_local_batches.py
```

Observed result:

```text
Stored batches: 2
founder-test-batch-1 | account=founder-test | items=10 | review=pending=1,reviewed=9 | labels=labeled=7,unlabeled=2 | writes=applied=7,missing=3 | retries=1 | fetch_failures=0
founder-test-batch-2 | account=founder-test | items=10 | review=pending=10 | labels=labeled=0,unlabeled=0 | writes=missing=10 | retries=0 | fetch_failures=0
```

This confirms the user-visible `011` slice:

- the proven live workflow can now produce a second stored batch
- the local batch index makes both old and new batches visible together
- the index provides useful next-step status without exposing private email content

## Important Constraints

- This slice is strictly local and read-only from the new-code perspective
- The second-batch acceptance scenario reused the already-proven live fetch workflow and did not add new Gmail mutation scope
- The index is batch-level only and intentionally avoids deeper message detail

## Risks Or Open Questions

- The new second batch currently exists in a pre-review state; the next slice should only extend the workflow if a new concrete pain is clear
- If deeper inspection is needed later, treat it as a separate privacy-sensitive slice rather than extending this index implicitly

## Recommended Next Step

Clear context, resume from the latest handoffs and [docs/mvp-checkpoint.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/mvp-checkpoint.md), then choose the next bounded slice through the normal issue-first process.
