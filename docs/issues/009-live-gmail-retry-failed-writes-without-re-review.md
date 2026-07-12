# Title

Retry failed live Gmail label writes without re-review

## Type

HITL

## User-visible goal

Let the user retry failed `EA/` Gmail label writes for already reviewed live messages without forcing those messages back through review, as long as the approved final labels have not changed since the failed attempt.

## Scope

- Reuse the existing live Gmail write-back path and stored per-message write status from issue `007`
- Reuse the bounded retry rules already proven locally in issue `005` as design precedent only
- Surface which reviewed live messages are currently retryable because their latest write attempt failed
- Allow retry only for messages whose current approved `final_labels` exactly match the labels recorded on the failed attempt
- Block retry when the approved labels have changed since the failed attempt and require the normal review flow before any later write
- Preserve per-message write-attempt history instead of overwriting prior failure records
- Keep Gmail mutations limited to agent-created `EA/` label creation and application only
- Keep the retry action local, explicit, and bounded to one stored live batch at a time
- Define expected behavior and tests before implementation begins

## Non-goals

- re-running review for the whole batch
- background or automatic retry scheduling
- silent mutation of approved labels or review state
- retrying messages that never reached a failed write state
- non-Gmail provider support
- archive, delete, send, reply, or non-`EA/` Gmail mutations
- broad reconciliation tooling across multiple batches or accounts

## Acceptance criteria

- A reviewed live batch with one or more failed Gmail writes clearly exposes which messages are retryable
- The user can retry a failed live Gmail write without re-review when the message's approved final labels are unchanged
- If the approved final labels changed after the failed attempt, retry is blocked until the message goes back through the normal review flow
- A successful retry updates per-message write status from failed to applied
- A repeated failed retry remains visible as failed rather than silently disappearing
- Retry attempts append to the stored per-message write-attempt history rather than overwriting prior attempts
- The slice performs no archive, delete, send, reply, or non-`EA/` label mutation behavior anywhere in its public flow

## Expected behavior

- The user runs a dedicated retry command against one stored live batch
- The command loads that batch's reviewed items, persisted write status, and persisted write-attempt history
- The command identifies retry candidates only from messages whose latest persisted write status is `failed`
- For each failed message, the command compares the current reviewed `final_labels` with the labels recorded on the latest failed attempt
- If the labels exactly match, the message is treated as retryable
- If the labels differ, the message is reported as blocked and skipped without mutating Gmail or local review state
- Messages without a failed latest status are not retried and are not reported as retryable
- The command attempts Gmail write-back only for retryable failed messages in the specified batch
- Gmail writes stay limited to creating missing `EA/` labels if needed and applying approved `EA/` labels only
- After each retry attempt, the command persists updated per-message write status
- After each retry attempt, the command appends a new per-message write-attempt record rather than replacing prior history
- The command ends with a minimal visible summary covering retried successes, retried failures, and blocked/skipped messages
- The command does not reopen review, change approved labels, or offer inline relabeling in this slice

## Expected tests or verification

- Test that the live retry flow only offers messages whose latest persisted write status is `failed`
- Test that retry uses the current reviewed `final_labels` and allows retry only when they exactly match the labels recorded on the failed attempt
- Test that changed approved labels block retry and require normal review before another write attempt
- Test that retry appends write-attempt history and updates write status correctly for both success and repeated failure
- Test that the retry flow reuses the existing `EA/` label mapping and does not alter non-agent Gmail labels
- Manual verification against an induced or simulated live Gmail write failure after Founder approval

## Dependencies/order

- Depends on issue `007`
- Reuses the bounded retry semantics proven in issue `005` as precedent, without reopening that issue
- Should start only after Founder approval for one bounded live retry verification path against stored live batch state

## Stop conditions requiring Founder review

- The retry flow appears to need hidden review-state changes or silent label mutation
- Failure handling appears to require broader Gmail permissions than `gmail.modify`
- The UX starts expanding into broad batch reconciliation, dashboards, or background retry machinery
- The slice pressures the project toward multi-account coordination or historical backfill rather than one bounded live retry path
