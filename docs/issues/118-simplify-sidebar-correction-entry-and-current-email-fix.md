# Simplify Sidebar Correction Entry and Current-Email Fix

GitHub issue: `#44`

Parent: GitHub issue `#42`

## What to build

Make the compact Gmail sidebar correction loop free-form-first, low-instruction, and centered on fixing the currently selected email before any broader learning.

The founder should be able to type a natural correction, preview what Threadwise understood, and apply `Fix this email` without accidentally saving a future rule or rewriting other existing emails.

## Acceptance criteria

- [x] The correction area leads with a free-form text input; manual label selection is secondary or expandable.
- [x] Visible instructional copy before typing is minimal.
- [x] The preview is structured around `This email`, `Future rule`, and `Affected existing emails`.
- [x] `Fix this email` is the primary action when the current-email fix is available.
- [x] `Fix this email` updates only the current email and does not save the future rule automatically.
- [x] If no meaningful broader rule is available, success briefly says so.
- [x] Existing simulator/browser validation covers the current-email fix path and sidebar overflow.

## Completion notes

Implemented in commit pending from the #42 slice-1 pass:

- The Gmail extension and simulator now lead correction with `What should Threadwise understand?`.
- Manual label selection moved behind `Choose label manually`.
- Preview cards now use `This email`, `Future rule`, and `Affected existing emails`.
- `Fix this email` remains current-email-only; future learning is still a separate action.
- Browser simulator acceptance verifies the preview structure and sidebar overflow behavior.

## Blocked by

None - can start immediately.
