# Future full installer and menubar app packaging review

Status: Follow-up candidate
Type: HITL
GitHub issue: `#25`
Parent: GitHub issue `#16`; `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`

## What to build

After the personal startup loop has been used, review whether Threadwise should graduate to a full macOS installer, packaged helper, or menubar app.

This is not part of the immediate personal startup implementation.

## Acceptance criteria

- [ ] Compares full installer, menubar app, native messaging host, and current LaunchAgent path after real use.
- [ ] Identifies whether repo-path dependence is causing real friction.
- [ ] Recommends whether to move runtime config/data into `~/Library/Application Support/Threadwise/`.
- [ ] Recommends whether signing/notarization/update flow is worth doing.
- [ ] Produces implementation issues only if the packaging escalation is approved.

## Safety boundaries

- Do not build installer infrastructure during this review.
- Do not move private local artifacts without explicit approval.

## Parallelization

Wait until `#22`, `#23`, and `#24` have been used enough to evaluate.
