# Gmail current-state refresh for attention dashboard

Status: Follow-up candidate
Type: Implementation
GitHub issue: `#17`
Parent: GitHub issue `#15`; `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md`

## What to build

Add a read-only Gmail freshness refresh for visible dashboard and attention items.

The goal is to distinguish local snapshot state from current Gmail state without mutating the inbox.

## Acceptance criteria

- [ ] Adds a compact local freshness artifact keyed by provider/account/message id.
- [ ] Records `local_snapshot_at` and `gmail_verified_at` where available.
- [ ] Refreshes current Gmail `labelIds`, thread id, existence/missing status, and whether `INBOX` is currently present for selected visible items.
- [ ] Shows stale/missing/current state in the dashboard or dashboard state model.
- [ ] Uses fake Gmail clients in tests.
- [ ] Does not change Gmail labels, archive status, deletion status, unsubscribe state, or message content.

## Safety boundaries

- Live Gmail execution requires explicit founder approval.
- Default tests must not call live Gmail.
- This slice is read-only and must not expand Gmail mutation scope.

## Parallelization

Can run in parallel with `#18` and `#20` if it uses fake clients and isolated files. `#19` should wait for this slice.
