# Live Testing Tranche: Sidebar Context and Teach Fixes

GitHub issue: `#41`

## What changed

Addressed the latest live Gmail companion feedback tranche with bounded fixes to context detection, queue preview wording, sidebar item navigation, target-label behavior, logo loading, post-apply refresh behavior, feedback-note length, and technical-detail labeling.

## Acceptance criteria

- [x] Sender-only Gmail state is not treated as a selected email.
- [x] Queue preview uses `Close preview` instead of unclear inbox-back wording.
- [x] Sidebar list items expose explicit `Open in Gmail` links.
- [x] Correct / Teach starts with a blank label selector.
- [x] Clear notes such as `this is spam` can infer `EA/LowValue` when the dropdown is blank.
- [x] The extension logo is packaged with the extension instead of loaded from the local companion server.
- [x] Successful teach/apply no longer immediately triggers a second refresh that can make success look like failure.
- [x] Details are labeled as technical details.
- [x] Longer founder notes can be saved locally.

## Blocked by

None - completed.
