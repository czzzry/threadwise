# Handoff: Issue 014 Remove `INBOX` For Approved Low-Value Live Messages

## Context

This note records the implementation checkpoint for [docs/issues/014-remove-inbox-for-approved-low-value-live-messages.md](docs/issues/014-remove-inbox-for-approved-low-value-live-messages.md).

This follows the bounded account-suggestion improvement in [docs/handoff/issue-013-improve-account-email-suggestions.md](docs/handoff/issue-013-improve-account-email-suggestions.md).

## What Changed

- Added a dedicated inbox-removal CLI in `src/live_gmail_remove_inbox_cli.py`
- Added a repo-root script entrypoint in `scripts/remove_inbox_for_live_gmail_batch.py`
- Extended the Gmail client in `src/live_gmail_client.py` with a bounded `remove_inbox_label(...)` mutation that removes `INBOX` only
- Extended `src/gmail_writer.py` with bounded inbox-removal persistence:
  - per-message inbox-removal status
  - per-message inbox-removal attempt history
- Kept the first-version eligibility narrow:
  - `promotions`
  - `spam-low-value`
- Kept the step separate from initial label write-back confirmation

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors in the implemented slice:

- the command shows a dry-run summary before any inbox mutation
- the command requires explicit `REMOVE` confirmation
- only reviewed messages with eligible final labels and successful prior label write-back are candidates
- the Gmail action removes `INBOX` only
- non-eligible labels are left untouched
- local inbox-removal status/history persists applied, failed, skipped, and ineligible outcomes
- one bounded live Gmail verification completed successfully against a fully reviewed and fully labeled real stored batch

## Validation

Focused new-slice verification:

```bash
python3 -m unittest tests.test_gmail_writer tests.test_live_gmail_client tests.test_live_gmail_remove_inbox_cli -v
```

Broader related-path regression verification:

```bash
python3 -m unittest \
  tests.test_gmail_writer \
  tests.test_live_gmail_client \
  tests.test_live_gmail_review_cli \
  tests.test_live_gmail_retry_cli \
  tests.test_local_batch_status_cli \
  tests.test_local_batch_index_cli \
  tests.test_live_gmail_remove_inbox_cli -v
```

Result at the latest checkpoint: `51 tests passed`.

Manual live verification:

Command run:

```bash
python3 scripts/remove_inbox_for_live_gmail_batch.py --batch-id founder-test-batch-2
```

Observed dry run:

```text
INBOX removal dry run:
Eligible for INBOX removal: 7
Skipped until label write-back is applied: 0
Ineligible: 3
This removes INBOX only. It does not delete or trash messages.
Type REMOVE to remove INBOX from eligible messages.
```

Observed live result after explicit confirmation:

```text
Removed from INBOX: 7
Failed to remove from INBOX: 0
Skipped until label write-back is applied: 0
Ineligible: 3
```

Observed persisted local status for `founder-test-batch-2`:

```text
applied: 7
ineligible: 3
failed: 0
skipped: 0
```

This confirms the bounded live behavior:

- `7` reviewed low-value/promotions messages were removed from the main Gmail inbox view
- `3` non-eligible `EA/Account` messages were left untouched
- no delete/trash behavior was involved

## Important Constraints

- The Gmail mutation is bounded to removing `INBOX` only; it does not delete or trash messages
- The slice does not relabel, reopen review, retry label write-back, or broaden to higher-risk categories
- The first version only considers `EA/Promotions` and `EA/LowValue` style outcomes eligible
- Messages whose label write-back did not reach `applied` are skipped rather than mutated

## Risks Or Open Questions

- Local read-only inspection tools do not yet summarize inbox-removal status files; the command persists them correctly, but visibility is currently through command output and stored artifacts rather than the inspection/index CLIs

## Recommended Next Step

- Resume the normal issue-first process and ask what the current concrete pain is now
- If inbox-removal visibility becomes the next pain, consider a separate read-only status slice rather than broadening this mutation slice implicitly
