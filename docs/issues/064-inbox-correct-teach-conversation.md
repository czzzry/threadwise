# Status

Current
Current as of: 2026-06-29
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/063-gmail-companion-sidebar-spine.md`

# Title

Build the in-inbox Correct / Teach conversation with impact preview and confirmation

## Type

Feature

## Blocked by

- `docs/issues/063-gmail-companion-sidebar-spine.md`

## User stories covered

`7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`, `20`, `21`, `22`, `34`

## What to build

Deliver the core teachable-agent loop inside Gmail.

This slice should let the user correct the currently selected email and have a short back-and-forth with the agent:

- provide `Correct / Teach`
- support fast relabel plus optional explanation
- generate a short acknowledgment that states:
  - what changed now
  - what the agent thinks it learned
  - whether the learning is current-email-only, sender/family-level, or future-rule-level
- estimate whether the feedback would change other existing emails
- show impact preview before broader change
- offer the four confirmation paths:
  - apply only to this email
  - apply to matching emails too
  - use for future emails only
  - refine this
- preserve prior interpretation during refinement so the user can compare old vs revised understanding
- apply broader confirmed changes immediately or visibly refresh right away

This slice should reuse existing memory/feedback infrastructure where possible, but it should present that capability as a product interaction rather than a review-tool workflow.

## Acceptance criteria

- [ ] The user can correct the selected email directly from the Gmail companion sidebar.
- [ ] The agent replies with a short acknowledgment that reflects the correction and inferred lesson.
- [ ] If the inferred lesson would rewrite other existing emails, the system shows impact before applying it.
- [ ] The user can choose current-only, matching-existing, future-only, or refine.
- [ ] Refinement preserves visible old vs revised interpretation.
- [ ] Confirmed broader changes apply immediately or clearly refresh in place.

## Output

- in-sidebar correction flow
- structured acknowledgment and interpretation model
- impact preview and confirmation flow

