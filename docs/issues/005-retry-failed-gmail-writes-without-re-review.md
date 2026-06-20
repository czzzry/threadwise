# Title

Retry failed Gmail writes without re-review

## Type

HITL

## User-visible goal

Let the user retry failed Gmail label writes for already reviewed messages without forcing the batch back through review, as long as the approved labels have not changed.

## Scope

- Surface failed write status at the message level
- Allow retry for messages whose approved labels are unchanged
- Prevent silent re-review bypass when approved labels have changed
- Keep audit history of the original review outcome and later write attempts

## Non-goals

- automatic retry scheduling
- broad reconciliation tooling
- reclassification of reviewed messages
- non-Gmail provider support

## Acceptance criteria

- A failed Gmail write is clearly distinguishable from a successful one
- The user can retry a failed write without re-review when the approved labels are unchanged
- If approved labels changed after the original review, retry is blocked until the message is reviewed again through the normal flow
- Retry attempts preserve prior review history rather than overwriting it

## Expected tests or verification

- Test write-status transitions for success, failure, and retry
- Test that unchanged approved labels are retryable without re-review
- Test that changed approved labels require normal review before another write
- Manual verification against an induced or simulated Gmail write failure after Founder approval

## Dependencies/order

- Depends on issue `004`

## Stop conditions requiring Founder review

- The retry flow appears to need silent label mutation or hidden review-state changes
- Failure handling requires broader Gmail permissions or background jobs
- The audit trail becomes materially more complex than simple per-message write attempts
