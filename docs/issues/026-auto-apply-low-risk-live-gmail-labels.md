# Title

Auto-apply low-risk live Gmail labels

## Type

HITL

## User-visible goal

Make the tool usable without reviewing every message by auto-applying a bounded allowlist of low-risk labels to a stored live Gmail batch, while keeping higher-risk labels in the existing manual review flow.

## Scope

- Add a stored-batch CLI that auto-approves a bounded allowlist of pending labels
- Initial allowlist:
  - `spam-low-value`
  - `shopping-order`
  - `job-related`
- Write the corresponding `EA/` labels back to Gmail for those auto-approved messages
- Remove `INBOX` only for auto-approved `spam-low-value` messages after successful label write-back
- Persist local audit state through the existing stored batch and write/inbox-removal status files

## Non-goals

- Full autonomous handling for every label
- Autonomy for `personal`, `reply-needed`, `account-security`, or `financial-account`
- Deleting, trashing, or archiving mail
- Replacing the existing manual review flow

## Acceptance criteria

- Pending `spam-low-value`, `shopping-order`, and `job-related` items can be auto-approved and written to Gmail from one stored batch command
- Auto-approved `spam-low-value` items also have `INBOX` removed after successful write-back
- Non-allowlisted labels remain pending and are not written
- The stored batch preserves auditable review state for auto-approved items

## Expected tests or verification

- Test the auto-apply CLI auto-approves allowlisted pending items and writes their Gmail labels
- Test `INBOX` removal runs only for auto-approved `spam-low-value` items after successful write-back
- Test non-allowlisted pending items remain pending and are not written
- Re-run the relevant Gmail writer, stored-batch, and live-CLI suites
