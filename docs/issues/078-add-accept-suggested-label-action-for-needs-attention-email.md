# Status

Current
Current as of: 2026-06-30
Triage state: `needs-triage`
Builds on: `docs/issues/075-implement-approved-threadwise-mock-fidelity-in-live-surfaces.md`

# Title

Add accept suggested label action for needs-attention email

## Type

HITL / UX / Follow-up

## Problem

When Threadwise already has a likely label for a needs-attention email, the current UI makes the user treat the moment as a correction/teaching flow. In the demo case, the agent says the email looks work-adjacent and defaults the teach target to `EA/Work`, but there is no simple “I agree” action.

That makes approval feel more complicated than it should be. The user should be able to confirm the suggested label directly when the agent is asking for approval rather than correction.

## Acceptance criteria

- [ ] Needs-attention emails with a suggested label expose a clear accept/approve action.
- [ ] Accepting the suggestion applies the suggested label to the current stored email without requiring free-form teaching text.
- [ ] The action copy distinguishes “approve this email” from broader rule teaching.
- [ ] The existing Correct / Teach flow remains available for changing the label or teaching broader behavior.
- [ ] Safety boundaries remain unchanged: no real Gmail write-through unless that mode is explicitly enabled.
- [ ] Focused tests cover the accept-suggested-label path.

## Notes

- This is separate from the 075 visual-fidelity pass.
- The current suggested-label defaulting is handled by `suggested_label` from the selected-email payload.
