# V2 Issue Map

This is a lightweight roadmap, not a commitment to implement everything in order without re-checking product direction.

## Current Position

Completed:

- `029`: daily per-run operational report for one inbox

Approved next:

- `030`: weekly per-inbox analytical report from daily run artifacts

## Candidate Next Issues

### Reporting

- `029`: daily per-run operational report for one inbox
- `030`: weekly per-inbox analytical report from daily run artifacts
- candidate later: cross-run report inspection helpers

### Provider / Inbox Model

- candidate: make reports and run artifacts explicitly provider-aware
- candidate: introduce separate per-inbox workflow primitives that are reusable across Gmail and ProtonMail
- candidate: ProtonMail live integration for the existing operating model

### Subscription / Unsubscribe Management

- candidate: inventory mailing lists and newsletters across one inbox
- candidate: user-reviewed unsubscribe selection flow
- candidate: explicit unsubscribe execution with confirmation and audit trail

### Exceptions / Quality

- candidate: tighter unlabeled-exception workflow
- candidate: repeated-unlabeled pattern reporting
- candidate: quality checkpoint over auto-applied vs unlabeled outcomes

## Sequencing Principle

Prefer slices that:

1. build on already-proven artifacts and workflows
2. improve the daily operating loop directly
3. avoid provider-integration risk until the workflow shape is clearer
4. keep outbound actions explicit and auditable
