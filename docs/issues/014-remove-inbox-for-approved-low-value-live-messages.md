# Title

Remove `INBOX` for approved low-value live Gmail messages after label write-back

## Type

HITL

## User-visible goal

Let the user explicitly confirm that already reviewed live Gmail messages with approved low-value `EA/` labels should be removed from the main Gmail inbox view by removing the Gmail `INBOX` label, while keeping the messages and their approved `EA/` labels intact.

## Scope

- Reuse one existing reviewed live Gmail batch that has already completed the approved `EA/` label write-back path
- Keep this as a separate explicit post-label step rather than merging it into initial label write-back confirmation
- Limit inbox removal eligibility in this first version to reviewed messages whose approved final labels include:
  - `EA/Promotions`
  - `EA/LowValue`
- Implement the Gmail-native action precisely as removing the `INBOX` label while preserving approved `EA/` labels already applied
- Reuse the existing `gmail.modify` scope rather than broadening permissions
- Surface a dry-run style summary that shows exactly how many eligible messages would be removed from inbox
- Require a second explicit local confirmation before any `INBOX` removal occurs
- Persist enough local per-message status or history so successful, failed, skipped, and ineligible outcomes remain visible after the command completes
- Keep the action bounded to one stored live batch at a time
- Define expected behavior and tests before implementation begins

## Non-goals

- deleting or trashing messages
- removing messages from “All Mail”
- removing or changing approved `EA/` labels
- applying inbox removal to labels outside the approved first-version subset
- autonomous inbox cleanup
- background processing or scheduled cleanup
- multi-account handling
- relay/forward/copy into other mailboxes or systems

## Acceptance criteria

- A reviewed live Gmail batch with successful approved `EA/` label write-back can be opened for a separate inbox-removal confirmation step
- Only messages approved into `EA/Promotions` or `EA/LowValue` are eligible for inbox removal in this slice
- No Gmail inbox mutation is attempted until the user sees the eligible-message summary and explicitly confirms the action
- The Gmail action in this slice is limited to removing `INBOX`; messages are not deleted, trashed, or otherwise removed from the mailbox
- Approved `EA/` labels remain intact on messages that have `INBOX` removed
- Messages with non-eligible approved labels such as `EA/ReplyNeeded`, `EA/Account`, `EA/Personal`, or `EA/Work` are not touched by this slice
- Per-message local status/history is persisted for success, failure, skipped, and ineligible outcomes
- The slice performs no delete, trash, send, reply, or non-bounded Gmail mutation behavior anywhere in its public flow

## Expected behavior

- The user runs a dedicated inbox-removal command against one stored reviewed live batch
- The command loads the reviewed items plus whatever stored local write status/history is needed to determine whether the batch has already completed the approved label write-back path
- The command identifies inbox-removal candidates only from reviewed messages whose approved final labels include `promotions` or `spam-low-value`
- Messages with no approved final labels, rejected outcomes, or non-eligible final labels are reported as skipped or ineligible and are not mutated
- Before any Gmail mutation, the command prints a dry-run style summary of:
  - eligible messages
  - skipped or ineligible messages
  - the exact Gmail action to be taken: remove `INBOX` only
- The command proceeds only after a second explicit local confirmation
- For each eligible confirmed message, the command removes `INBOX` while leaving previously approved `EA/` labels intact
- The command ends with a minimal visible summary covering inbox removals applied, failed, skipped, and ineligible
- The command does not delete, trash, relabel, retry write-back, reopen review, or broaden to other categories in this slice

## Expected tests or verification

- Test that only reviewed messages with approved `promotions` or `spam-low-value` final labels are eligible for inbox removal
- Test that the command blocks Gmail mutation until explicit confirmation is provided after the dry-run summary
- Test that the Gmail action removes `INBOX` only and preserves approved `EA/` labels
- Test that non-eligible labels such as `reply-needed`, `account-security`, `personal`, or `job-related` are not mutated
- Test that per-message local inbox-removal status/history is persisted for applied, failed, skipped, and ineligible outcomes
- Test that the slice performs no delete, trash, send, reply, or non-bounded Gmail mutation through its public flow
- Manual verification on one small reviewed live Gmail batch after Founder approval

## Dependencies/order

- Depends on issue `007` for confirmed approved `EA/` label write-back
- Should be treated as a separate follow-on mutation slice after labeling, not as part of the original review/write confirmation
- Should start only after Founder approval for bounded Gmail inbox removal on low-value categories

## Stop conditions requiring Founder review

- Any proposal to delete, trash, or otherwise permanently remove messages
- Any proposal to mutate messages outside removing `INBOX` while preserving approved `EA/` labels
- Any pressure to include high-risk categories such as `EA/ReplyNeeded`, `EA/Account`, `EA/Personal`, or `EA/Work` in the first version
- Any proposal to make inbox removal automatic, backgrounded, or multi-batch/multi-account by default
