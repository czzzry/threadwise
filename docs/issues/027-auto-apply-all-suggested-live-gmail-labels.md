# Title

Auto-apply all suggested live Gmail labels

## Type

HITL

## User-visible goal

Make the tool usable without manual review by auto-applying all current suggested labels to a stored live Gmail batch, while keeping `INBOX` removal limited to low-value and promotional mail.

## Scope

- Expand the stored-batch auto-apply CLI to approve every pending item that already has suggested labels
- Write all corresponding `EA/` labels back to Gmail
- Keep `INBOX` removal limited to `spam-low-value` and `promotions` after successful label write-back
- Persist local audit state through the existing stored batch and write/inbox-removal status files

## Non-goals

- Deleting, trashing, or archiving mail
- Inferring labels for messages that still have no suggestion
- Replacing the existing ability to review or edit manually when needed

## Acceptance criteria

- Pending items with any current suggested labels can be auto-approved and written to Gmail from one stored batch command
- `INBOX` removal still runs only for `spam-low-value` and `promotions`
- Pending items with no suggested labels remain pending and are not written
- The stored batch preserves auditable review state for auto-approved items across all labels

## Expected tests or verification

- Test the auto-apply CLI auto-approves all pending items with suggested labels and writes their Gmail labels
- Test `INBOX` removal runs only for `spam-low-value` and `promotions` after successful write-back
- Test pending items with no suggestions remain pending and are not written
- Re-run the relevant Gmail writer, stored-batch, and live-CLI suites
