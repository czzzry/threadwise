# Title

Read-only local batch status inspection for one stored batch

## Type

AFK

## User-visible goal

Let the user inspect what happened in one stored local batch after fetch, review, write, and retry work through a dedicated read-only command that summarizes batch state without making Gmail API calls, without performing Gmail writes, and without printing private email content by default.

## Scope

- Add a dedicated local CLI for inspecting one stored batch by `batch_id`
- Read only from existing local stored batch artifacts such as batch items, persisted write status, persisted write-attempt history, and fetch-failure records
- Show a safe default summary view that does not print message content, snippets, or full subject lines by default
- Summarize the current batch state across fetch, review, write, and retry outcomes using only stored local data
- Reuse the existing stored review-item and write-status contracts rather than creating parallel inspection data
- Keep the command fully local and deterministic enough to test from fixture-like stored batch files
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail API calls of any kind
- Gmail writes or retries
- printing private email content by default
- review, relabel, retry, or fetch actions from the inspection command
- dashboard UI, server process, or background monitoring
- cross-batch reporting or multi-account reconciliation

## Acceptance criteria

- A user can run one dedicated local command against one stored batch and get a useful summary of batch state
- The default output makes it easy to understand the batch without printing private email content by default
- The summary reflects stored review state, final label outcomes, write status, retry history, and fetch failures when present
- The command performs no Gmail API calls and no Gmail writes anywhere in its public flow
- The slice includes a written expected-behavior and test list before implementation begins

## Expected behavior

- The user runs a dedicated inspection command against one stored batch
- The command loads the stored batch file and any associated local write-status and write-attempt files if present
- The default output shows batch-level summary information only
- The default output avoids printing message snippets, bodies, raw headers, or other private email content
- The summary includes at least:
  - batch id
  - account id
  - item count
  - review-state counts
  - review-action counts
  - final labeled vs unlabeled counts
  - per-label counts for final approved labels
  - write-status counts such as applied, failed, skipped, or missing
  - retry-attempt visibility derived from stored write-attempt history
  - fetch-failure count when present
- If the batch has no write-status or write-attempt files yet, the command reports that cleanly rather than failing
- The command exits cleanly when the batch exists but some optional local artifacts are absent
- The command performs no network activity and no state mutation

## Expected tests or verification

- Test that the inspection command runs from the repo root without requiring `PYTHONPATH`
- Test that the default output summarizes stored batch counts correctly from local batch data
- Test that final label counts are derived from reviewed final labels rather than suggested labels
- Test that write-status and write-attempt summaries are surfaced when local files exist
- Test that missing optional write-status or write-attempt files are handled cleanly
- Test that fetch failures are counted when present
- Test that default output does not print message snippets or bodies from stored batch data
- Test that the command performs no Gmail API calls or Gmail writes through its public flow
- Manual verification on one representative stored live batch

## Dependencies/order

- Follows issues `006`, `007`, `008`, and `009` as a local visibility slice over already-stored batch state
- Should start only after the issue draft is approved for a bounded read-only inspection workflow

## Stop conditions requiring Founder review

- The slice starts to require printing private email content by default rather than via an explicit future opt-in
- The command pressures the project toward a broader dashboard, reporting system, or multi-batch operations UX
- The work appears to require changing existing review/write contracts rather than reading them
