# Title

Read-only local batch index for stored batches

## Type

AFK

## User-visible goal

Let the user repeat the proven live batch workflow on a second real batch and then quickly see both the old and new stored batches with useful high-level status through one dedicated read-only local command, so they can decide which batch to inspect next without opening each batch individually and without making Gmail API calls or printing private email content.

## Scope

- Add a dedicated local CLI that lists stored batches from the existing local batch store
- Keep new code limited to the local batch index only; reuse the existing live fetch/review/write/retry workflow as already proven
- Read only from existing local batch artifacts such as stored batch files, persisted write status, and persisted write-attempt history
- Show one privacy-safe summary row per stored batch
- Reuse the existing batch and write-status contracts rather than creating parallel index metadata
- Keep the command fully local and deterministic enough to test from fixture-like stored batch files
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail API calls of any kind
- Gmail writes or retries
- printing private email content by default
- per-message detail views
- cross-account aggregation beyond what is already present in local stored batch files
- dashboard UI, server process, or background monitoring

## Acceptance criteria

- A user can run one dedicated local command and get a useful list of stored batches
- A second live batch exists through the already-proven workflow before this slice is accepted
- The batch index shows both the older and newer stored live batches with useful status for each
- The default output makes it easy to spot which batches are pending review, partially reviewed, written, retried, or otherwise incomplete
- The output remains privacy-safe by default and does not print snippets, bodies, sender lines, or subject lines
- The command performs no Gmail API calls and no Gmail writes anywhere in its public flow
- The slice includes a written expected-behavior and test list before implementation begins

## Expected behavior

- The user runs a dedicated batch-index command against the local storage directory
- The command is useful in the real two-batch case produced by rerunning the already-proven live workflow on a fresh batch
- The command discovers stored batch files from the existing batch storage location
- The default output shows one summary line per batch
- The default output avoids printing message snippets, bodies, raw headers, sender lines, or subject lines
- Each batch summary includes at least:
  - batch id
  - account id
  - item count
  - review-state summary
  - final labeled vs unlabeled counts
  - write-status summary
  - retry-attempt visibility derived from stored write-attempt history
  - fetch-failure count
- Batches are presented in a stable, predictable order
- If optional write-status or write-attempt files are missing for a batch, the command reports that cleanly rather than failing
- If no stored batches exist, the command exits cleanly with an explicit no-batches message
- The command performs no network activity and no state mutation

## Expected tests or verification

- Test that the batch-index command runs from the repo root without requiring `PYTHONPATH`
- Test that the default output lists multiple stored batches with correct summary counts
- Test that missing optional write-status or write-attempt files are handled cleanly per batch
- Test that empty storage produces a clean no-batches result
- Test that default output does not print subject lines, senders, snippets, or bodies from stored batch data
- Test that the command performs no Gmail API calls or Gmail writes through its public flow
- Manual verification after producing a second live batch through the existing workflow and confirming both old/new batches appear with useful status

## Dependencies/order

- Follows issue `010` as the next local visibility slice
- Reuses the already-proven live workflow from issues `006` through `009` to create the second-batch acceptance scenario
- Should start only after the issue draft is approved for a bounded read-only batch-index workflow

## Stop conditions requiring Founder review

- The slice starts to require message-level detail by default rather than staying batch-level and privacy-safe
- The work pressures the project toward a broader dashboard, reporting system, or multi-account management UX
- The work appears to require new persistent index metadata rather than reading the existing stored contracts
