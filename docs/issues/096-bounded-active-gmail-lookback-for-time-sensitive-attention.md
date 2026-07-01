# Bounded active Gmail lookback for time-sensitive attention

Status: Follow-up candidate
Type: HITL plus implementation
GitHub issue: `#19`
Parent: GitHub issue `#15`; `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md`
Depends on: `#17`

## What to build

Design and implement a bounded read-only Gmail lookback for time-sensitive attention candidates that may not be in the latest daily batch or stored local lookback.

This exists for cases such as travel tomorrow, bill due soon, appointment reminders, account-risk warnings, security notices, and hiring/interview next steps that became important after the original email arrived.

## Acceptance criteria

- [ ] Defines a small set of approved Gmail search queries and date windows.
- [ ] Fetches only bounded candidate messages needed for attention evaluation.
- [ ] Stores compact attention candidate metadata by default.
- [ ] Does not create a broad local Gmail mirror.
- [ ] Records why each lookback item was fetched and evaluated.
- [ ] Has fake-client tests for query construction, caps, dedupe, and no-mutation guarantees.
- [ ] Requires explicit founder approval before live Gmail execution.

## Safety boundaries

- Read-only Gmail access only.
- No Gmail label writes, archive changes, delete/trash, send/reply, or unsubscribe actions.
- Do not retain full message bodies beyond the agreed retention policy.

## Parallelization

Should wait for `#17`, because active lookback needs a clear freshness model first.
