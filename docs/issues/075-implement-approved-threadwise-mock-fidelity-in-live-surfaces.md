# Status

Current
Current as of: 2026-06-30
Triage state: `needs-triage`
Builds on: `docs/prd.md`, `docs/issues/074-lock-approved-threadwise-mock-as-final-fidelity-target.md`

# Title

Implement approved Threadwise mock fidelity in live surfaces

## Type

HITL / Feature / Design implementation

## Blocked by

- `docs/issues/074-lock-approved-threadwise-mock-as-final-fidelity-target.md`

## User stories covered

`21`, `25`, `26`, `44`

## What to build

Apply the approved mock's visual system to the real Threadwise-controlled product and demo surfaces.

The implementation should make the actual simulator, Gmail companion sidebar, daily dashboard, unsubscribe review, and teach/impact preview visually match the approved mock as closely as practical while preserving existing behavior and safety boundaries.

This is a fidelity pass, not a loose restyle. The implemented surfaces should carry over the mock's compact Gmail-like context, bold ink-and-paper Threadwise panel, chunky borders, warm paper backgrounds, button hierarchy, stats layout, card rhythm, app icon, and tagline treatment.

## Acceptance criteria

- [ ] The simulator uses the approved mock's Gmail-left / Threadwise-right composition.
- [ ] The Gmail companion sidebar uses the approved Threadwise panel styling where Gmail constraints allow.
- [ ] The selected-email / agent-view card matches the mock's hierarchy and copy density.
- [ ] The `Correct / Teach` preview matches the mock's visual hierarchy, button treatment, and confirmation emphasis.
- [ ] The `Today` stats card matches the mock's grid treatment and visual weight.
- [ ] The daily dashboard and unsubscribe review feel like the same product family as the sidebar.
- [ ] The Threadwise threaded-`T` app icon and `CLEAR THREADS. BETTER INBOX.` tagline appear in appropriate product/demo UI contexts.
- [ ] Existing product behavior and safety boundaries are unchanged.
- [ ] Focused tests or smoke checks cover the changed rendering surfaces.
- [ ] Browser screenshots are captured side-by-side against the approved mock.
- [ ] Founder approval is received before demo capture work resumes.

## Output

- Mock-faithful live Threadwise UI surfaces
- Visual smoke screenshots for review
- Updated tests where user-visible structure changed

## Boundaries

- Do not add new inbox actions.
- Do not redesign real Gmail outside Threadwise-controlled demo/simulator context.
- Do not capture final recruiter GIFs or MP4s in this slice.
- Do not imply ProtonMail or Outlook support is shipped.

