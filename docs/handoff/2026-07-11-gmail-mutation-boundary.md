# Handoff: Durable Gmail Mutation Boundary

Status: Implemented and locally validated
Current as of: 2026-07-11
GitHub issue: `#62`

## What changed

The Gmail writer now exposes one bounded mutation operation that owns EA label replacement followed by eligible `INBOX` removal. Daily automation, auto-apply, stored-message companion writes, and companion whole-inbox backfill all use that implementation.

Remote companion backfill creates a content-free operation batch containing only the account identifier, Gmail message identifiers, the reviewed state, and selected canonical labels. Mutation batches have their own artifact family, so they cannot replace the latest fetched inbox snapshot used by the companion and dashboard. The operation id gives the existing writer a durable key for label-write status, inbox-removal status, and attempt history without copying email subject, sender, body, or preview text.

## Partial-outcome behavior

- A label-write failure is recorded as `failed`; inbox removal is recorded as `skipped` and is not attempted.
- A successful label write followed by a failed inbox removal remains a successful label write plus a separate failed inbox-removal status.
- Complete success records both operations as `applied`.
- Ineligible labels retain the applied label status and record inbox removal as `ineligible`.

The companion response remains compatible and adds the remote operation batch id plus separate remote inbox-removal counts.

## Retry behavior

The existing Gmail retry command now also discovers failed inbox removals. It retries inbox removal only when the label write is already applied and the reviewed labels have not changed, so a successful label write is not repeated:

```bash
python3 scripts/retry_live_gmail_failed_writes.py --batch-id <remote_batch_id>
```

No retry was executed against a live Gmail account during implementation.

## Validation

- Red/green tests covered durable remote success, label-applied/inbox-removal-failed partial success, label-write failure with no inbox-removal attempt, and inbox-removal-only retry.
- Affected Gmail writer, automation, retry CLI, and companion tests passed: 91 tests.
- Repository-wide suite passed: 594 tests.
- Python compilation, extension JavaScript syntax checks, and diff whitespace checks passed.

## Next step

Use Threadwise normally and collect real workflow evidence. PostHog should identify interaction friction; reviewed corrections and the eval pipeline should identify correctness problems. Do not infer the next product slice from this maintenance change alone.
