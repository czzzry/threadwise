# Persist attention feedback

Status: Completed
Type: AFK
GitHub issue: `#11`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed in: `c6719c9`

## What to build

Add per-email feedback for attention candidates so Threadwise starts learning whether the Needs attention lane is useful.

The first feedback loop should be intentionally simple: Good catch, Not attention, Wrong reason, and Mark as needs attention for emails that were not surfaced. Feedback should affect the local product state and audit trail for that email, but must not silently create broader rules.

## Acceptance criteria

- [x] Attention items expose feedback actions for Good catch, Not attention, and Wrong reason.
- [x] The product supports marking a non-surfaced stored email as Needs attention.
- [x] Feedback persists per email and is reflected in the attention item state.
- [x] A dismissed Not attention item does not keep reappearing in the same daily attention view.
- [x] Good catch is stored as a positive signal but does not create or apply a broader rule.
- [x] Wrong reason can capture corrected reason/category context without changing Gmail labels.
- [x] Feedback is local and auditable.
- [x] Tests cover all feedback actions and persistence.

## Blocked by

- GitHub issue `#10`; `docs/issues/085-show-needs-attention-in-daily-dashboard.md`
