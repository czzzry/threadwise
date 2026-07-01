# Local data retention and inbox freshness review

Status: Follow-up candidate
Type: HITL
GitHub issue: `#15`
Parent: GitHub issue `#7`; `docs/prd.md`

## What to build

Run a focused architecture review of Threadwise local artifacts, email-body retention, and real Gmail freshness.

This is not part of the MVP+2 implementation path. It exists because local artifacts are useful for audit, retries, reports, and teaching, but the product should not accidentally become a stale local mailbox mirror or retain too much private email data indefinitely.

## Acceptance criteria

- [ ] The review documents what local data Threadwise stores and why.
- [ ] The review distinguishes raw message bodies, compact metadata, reports, feedback, rules, audit state, and credentials.
- [ ] The review recommends retention expectations for each data class.
- [ ] The review identifies what can be pruned safely and what must remain for audit, retry, or teaching.
- [ ] The review explains how local state should reconcile with real Gmail state.
- [ ] The review recommends whether active Gmail lookback fetch belongs in a future slice.
- [ ] The review produces follow-up implementation issues if cleanup tooling, retention policy, schema versioning, or inbox-state refresh is needed.

## Blocked by

- MVP+2 attention queue should be usable enough to inform the review.
