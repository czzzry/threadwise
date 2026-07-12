# Propose attention rules from feedback

Status: Completed
Type: AFK
GitHub issue: `#14`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed in: `800084b`

## What to build

Use accumulated attention feedback to propose broader attention rules with consequence previews.

This completes MVP+2's teachable attention loop. Threadwise may infer a broader lesson from per-email feedback, but it must show the proposed rule and preview affected messages before the founder approves any broader application.

## Acceptance criteria

- [x] Feedback can produce a proposed broader attention rule.
- [x] Proposed rules distinguish attention priority from classification labels.
- [x] Proposed rules preview matching existing stored emails before approval.
- [x] The founder can apply only to this email, future emails, or matching existing stored emails where supported.
- [x] No broader rule is created or applied silently from a single feedback action.
- [x] Learned rules may auto-promote into attention because promotion is non-mutating.
- [x] Learned rules promote to Needs attention now only with concrete time or consequence evidence.
- [x] Learned rules otherwise promote to Possible attention.
- [x] Tests cover proposal generation, preview, approval, rejection, and application boundaries.

## Blocked by

- GitHub issue `#11`; `docs/issues/086-persist-attention-feedback.md`
