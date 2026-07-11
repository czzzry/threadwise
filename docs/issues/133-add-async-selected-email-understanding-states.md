# Add Async Selected-Email Understanding States

Status: Completed
Current as of: 2026-07-11
Triage state: `completed`
Type: AFK
Parent PRD: `docs/prd-async-threadwise-extension-2026-07-10.md`

## What to build

Make the extension show explicit staged understanding for the currently reviewed Gmail email instead of waiting silently for one final selected-email state.

This slice should prove that opening or switching to a Gmail email can show a fast visible progression such as:

1. `Reading`
2. `Understanding`
3. `Ready`

before every deeper sidebar detail is fully resolved.

The founder should be able to tell that Threadwise is alive and working even when selected-email understanding takes noticeable time.

## User stories covered

- 1. As the founder, I want Threadwise to react immediately when I open an email, so that the extension feels alive instead of frozen.
- 2. As the founder, I want a visible `Reading` or `Understanding` state for the current email, so that I know Threadwise is still working.
- 3. As the founder, I want a quick first judgment before all deeper reasoning finishes, so that I can keep moving through Gmail.

## Acceptance criteria

- [x] Opening a selected Gmail email can enter an immediate visible working state before full selected-email understanding completes.
- [x] The sidebar exposes explicit selected-email understanding states such as `Reading`, `Understanding`, and `Ready`, or equivalent clear user-facing wording.
- [x] The first useful selected-email response appears without waiting for every secondary sidebar detail to finish.
- [x] Refreshing or switching emails does not leave the previous email's final state silently pinned while new understanding is in progress.
- [x] Tests cover the staged selected-email contract through the companion state/API seam and at least one browser/simulator flow.

## Blocked by

None - can start immediately.
