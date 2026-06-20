# Title

Write approved `EA/` labels back to Gmail after review

## Type

HITL

## User-visible goal

Let the user complete review for a real batch and have only the approved agent labels written back to Gmail under the `EA/` namespace.

## Scope

- Reuse the existing review flow and reviewed outcomes
- Map approved labels to configurable Gmail output names under an `EA/` namespace
- Create missing `EA/` labels automatically if needed
- Write labels only for reviewed messages with approved applied labels
- Record per-message write status visible enough to support later retry work

## Non-goals

- changing or deleting non-agent Gmail labels
- autonomous write-back without review
- bulk historical backfill
- retry workflow beyond basic status capture

## Acceptance criteria

- Finishing review can trigger Gmail write-back only for reviewed messages
- Approved labels are written under the configured `EA/` namespace
- Missing `EA/` labels are created automatically when required
- Rejected outcomes do not write agent labels
- `unlabeled` outcomes do not force substitute Gmail labels
- The user can tell which messages succeeded or failed during write-back

## Expected tests or verification

- Test label mapping from review outcomes to Gmail label names
- Test request construction for label creation and message label application
- Test that rejected and `unlabeled` outcomes do not produce applied agent labels
- Manual verification on one small reviewed Gmail batch after Founder approval

## Dependencies/order

- Depends on issue `003`

## Stop conditions requiring Founder review

- Any need for broader Gmail scopes than agreed
- Any ambiguity about whether existing Gmail labels should be altered or removed
- Any proposal to write labels before review completion
- Any need to write outside the `EA/` namespace
