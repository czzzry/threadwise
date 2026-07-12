# Local data retention and inbox freshness review

Status: Completed
Type: HITL
GitHub issue: `#15`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed by: `docs/local-data-retention-and-inbox-freshness-review-2026-07-01.md`

## What to build

Run a focused architecture review of Threadwise local artifacts, email-body retention, and real Gmail freshness.

This is not part of the MVP+2 implementation path. It exists because local artifacts are useful for audit, retries, reports, and teaching, but the product should not accidentally become a stale local mailbox mirror or retain too much private email data indefinitely.

## Acceptance criteria

- [x] The review documents what local data Threadwise stores and why.
- [x] The review distinguishes raw message bodies, compact metadata, reports, feedback, rules, audit state, and credentials.
- [x] The review recommends retention expectations for each data class.
- [x] The review identifies what can be pruned safely and what must remain for audit, retry, or teaching.
- [x] The review explains how local state should reconcile with real Gmail state.
- [x] The review recommends whether active Gmail lookback fetch belongs in a future slice.
- [x] The review produces follow-up implementation issues if cleanup tooling, retention policy, schema versioning, or inbox-state refresh is needed.

## Blocked by

- MVP+2 attention queue should be usable enough to inform the review.

## Follow-up issues

- `#18` / `092`: Local artifact inventory and retention report
- `#21` / `093`: Raw email body redaction and pruning policy
- `#17` / `094`: Gmail current-state refresh for attention dashboard
- `#20` / `095`: Schema-version local artifact registry for MVP+2 artifacts
- `#19` / `096`: Bounded active Gmail lookback for time-sensitive attention
