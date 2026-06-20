# Title

Review one live Gmail batch locally and explicitly confirm `EA/` label write-back

## Type

HITL

## User-visible goal

Let the user open one previously fetched live Gmail batch, review it locally, see a dry-run summary of the exact `EA/` labels that would be applied, explicitly confirm the action, and then apply only those approved `EA/` labels back to Gmail.

## Scope

- Reuse one existing live Gmail batch that was fetched through the approved live read path
- Review the batch locally using the existing review semantics before any Gmail mutation
- Escalate Gmail OAuth from read-only access to the minimum approved write scope needed for label application, specifically `gmail.modify`
- Detect when the stored token does not include the required write scope and require a re-auth flow before any write attempt
- Preserve or refresh local token storage safely when the scope changes, without broadening permissions beyond what this slice needs
- Produce a dry-run summary before write-back showing which reviewed messages will receive which `EA/` labels
- Require an explicit local confirmation step after review and dry-run, before any Gmail API mutation occurs
- Map approved final labels to Gmail output labels under the `EA/` namespace only
- Create missing `EA/` labels automatically when needed for approved outcomes
- Apply approved `EA/` labels only to reviewed messages with non-empty final labels
- Persist local per-message write status for the batch so success and failure remain visible after the command completes
- Record enough local write-attempt history to support the follow-up retry slice
- Keep all Gmail mutations limited to agent-created `EA/` labels in this slice

## Non-goals

- retrying failed writes in the same slice
- archiving, deleting, sending, replying, or marking messages read/unread
- removing existing non-agent Gmail labels
- writing labels before local review completes
- background syncing or automatic write-back
- multi-account support
- expanding beyond one explicitly confirmed live batch

## Acceptance criteria

- A previously fetched live Gmail batch can be opened and reviewed locally using the existing review flow
- No Gmail write is attempted until the user completes review and explicitly confirms the dry-run summary
- If the stored Gmail token is read-only or otherwise lacks `gmail.modify`, the write path stops cleanly and requires a re-auth flow for the narrower approved write scope
- After successful re-auth, the write path can continue using locally stored credentials without requiring unnecessary repeated consent
- The dry-run summary shows the messages selected for write-back and the exact `EA/` labels that will be applied
- Only reviewed messages with approved final labels are included in Gmail write-back
- `unlabeled` and rejected outcomes do not force substitute Gmail labels
- Missing agent labels under the `EA/` namespace are created automatically when needed
- Gmail mutations in this slice are limited to creating `EA/` labels and applying approved `EA/` labels to the reviewed messages
- Per-message local write status is persisted for success, failure, and skipped outcomes
- The slice performs no archive, delete, send, reply, or non-`EA/` label mutation behavior anywhere in its public flow

## Expected tests or verification

- Test that a stored live-style reviewed batch can flow through dry-run and confirmed write-back without changing the review contract
- Test that write-back is blocked until explicit confirmation is provided after the dry-run summary
- Test that tokens missing `gmail.modify` trigger the expected re-auth requirement before any write attempt
- Test that approved labels are mapped only into the `EA/` namespace and that non-agent labels are not altered or removed
- Test that rejected and `unlabeled` outcomes do not produce Gmail label application requests
- Test that missing `EA/` labels are created before label application requests are sent
- Test that per-message write status is persisted locally for applied, failed, and skipped outcomes
- Manual verification on one small reviewed live Gmail batch after Founder approval for write scope escalation

## Dependencies/order

- Depends on issue `006`
- Should start only after Founder approval for escalating Gmail access from read-only to `gmail.modify` for agent-label write-back
- Follow with a separate live retry slice for retrying failed writes without re-review, reusing the bounded retry behavior proven in issue `005`

## Stop conditions requiring Founder review

- Any proposed Gmail scope broader than `gmail.modify`
- Any need to mutate message state beyond agent `EA/` label creation and application
- Any attempt to archive, delete, send, reply, or touch non-agent labels
- Any need to bypass local review or the explicit confirmation step
- Any proposal to broaden this slice into multi-account handling, background sync, or bulk historical write-back
