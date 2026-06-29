# Handoff: Issue 015 Show Inbox-Removal Status In Local Inspection

## Context

This note records the implementation checkpoint for [docs/issues/015-show-inbox-removal-status-in-local-inspection.md](docs/issues/015-show-inbox-removal-status-in-local-inspection.md).

This follows the live-verified inbox-removal slice in [docs/handoff/issue-014-remove-inbox-for-approved-low-value-live-messages.md](docs/handoff/issue-014-remove-inbox-for-approved-low-value-live-messages.md).

## What Changed

- Extended the shared read-only summary logic in `src/local_batch_summary.py` to load persisted inbox-removal status and attempt history from issue `014`
- Extended the one-batch inspection CLI in `src/local_batch_status_cli.py` to show:
  - inbox-removal status counts
  - inbox-removal attempt-history counts
- Extended the multi-batch index CLI in `src/local_batch_index_cli.py` to include a compact `inbox_removal=` summary field per batch
- Kept the slice strictly local and read-only:
  - no Gmail API calls
  - no Gmail writes
  - no local state mutation
  - no private email content in default output

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors:

- one-batch local inspection now shows inbox-removal summary state
- multi-batch local index now shows compact inbox-removal state
- missing optional inbox-removal files are handled cleanly
- default output remains privacy-safe

## Validation

Focused verification:

```bash
python3 -m unittest tests.test_local_batch_status_cli tests.test_local_batch_index_cli -v
```

Related-path regression verification:

```bash
python3 -m unittest \
  tests.test_local_batch_status_cli \
  tests.test_local_batch_index_cli \
  tests.test_live_gmail_remove_inbox_cli \
  tests.test_live_gmail_retry_cli \
  tests.test_live_gmail_review_cli -v
```

Result at the latest checkpoint:

- focused: `7 tests passed`
- related-path: `29 tests passed`

Manual local read-only verification:

```bash
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-2
python3 scripts/list_local_batches.py
```

Observed one-batch status output for `founder-test-batch-2`:

```text
Batch ID: founder-test-batch-2
Account ID: founder-test
Items: 10
Fetch failures: 0
Review states: reviewed=10
Review actions: approve=6, edit=4
Final labels: labeled=10, unlabeled=0
Label counts: EA/Account=3, EA/LowValue=7, EA/Promotions=4
Write status: applied=10
Write attempts: messages_with_history=10, total_attempts=10, retried_messages=0
Inbox removal: applied=7, ineligible=3
Inbox removal attempts: messages_with_history=10, total_attempts=10, retried_messages=0
```

Observed multi-batch index output:

```text
Stored batches: 2
founder-test-batch-1 | account=founder-test | items=10 | review=pending=1,reviewed=9 | labels=labeled=7,unlabeled=2 | writes=applied=7,missing=3 | inbox_removal=missing=10 | retries=1 | fetch_failures=0
founder-test-batch-2 | account=founder-test | items=10 | review=reviewed=10 | labels=labeled=10,unlabeled=0 | writes=applied=10 | inbox_removal=applied=7,ineligible=3 | retries=0 | fetch_failures=0
```

## Important Constraints

- The new visibility is summary-only and read-only
- The commands still avoid subjects, senders, snippets, bodies, and raw headers by default
- The slice reuses the existing `014` persistence contracts rather than adding new storage

## Risks Or Open Questions

- Inbox-removal visibility is now present, but there is still no opt-in deeper per-message inspection for surprising cases

## Recommended Next Step

- If AFK-safe onboarding and repeatability now look like the biggest gap, add a concise MVP usage guide based only on the already-proven command set
