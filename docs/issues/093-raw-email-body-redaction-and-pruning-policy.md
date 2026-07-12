# Raw email body redaction and pruning policy

Status: Follow-up candidate
Type: HITL plus implementation
GitHub issue: `#21`
Parent: GitHub issue `#15`; `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md`
Depends on: `#18`

## What to build

Define and implement a dry-run-first cleanup path for old raw email content in local batches.

This slice should decide how Threadwise can remove or redact old `raw_messages` and normalized `body` fields while preserving enough compact metadata for reports, audit, dedupe, and teaching.

## Acceptance criteria

- [ ] Documents the selected retention defaults for raw email content.
- [ ] Provides a dry-run cleanup command that lists candidate counts and byte savings without printing private contents.
- [ ] Separates redaction from deletion in the plan output.
- [ ] Preserves message id, thread id, provider/account id, date, local labels, review state, action audit links, and report links.
- [ ] Refuses to mutate files without an explicit confirmation flag.
- [ ] Writes an audit artifact describing what would change or did change.
- [ ] Has tests using synthetic batches only.

## Safety boundaries

- Destructive cleanup requires explicit founder approval before any real local data mutation.
- Must not touch credential directories.
- Must not delete action-audit state.
- Must not run against live Gmail.

## Parallelization

Should wait for `#18`, because the inventory report should define the candidate set and retention classes.
