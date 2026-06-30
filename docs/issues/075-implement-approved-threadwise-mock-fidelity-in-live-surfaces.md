# Status

Current
Current as of: 2026-06-30
Triage state: `ready-for-human`
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

- [x] The simulator uses the approved mock's Gmail-left / Threadwise-right composition.
- [x] The Gmail companion sidebar uses the approved Threadwise panel styling where Gmail constraints allow.
- [x] The selected-email / agent-view card matches the mock's hierarchy and copy density.
- [x] The `Correct / Teach` preview matches the mock's visual hierarchy, button treatment, and confirmation emphasis.
- [x] The `Today` stats card matches the mock's grid treatment and visual weight.
- [x] The daily dashboard and unsubscribe review feel like the same product family as the sidebar.
- [x] The Threadwise threaded-`T` app icon and `CLEAR THREADS. BETTER INBOX.` tagline appear in appropriate product/demo UI contexts.
- [x] Existing product behavior and safety boundaries are unchanged.
- [x] Focused tests or smoke checks cover the changed rendering surfaces.
- [x] Browser screenshots are captured side-by-side against the approved mock.
- [ ] Founder approval is received before demo capture work resumes.

## Implementation notes

- Updated the simulator to use the approved two-column composition with a Gmail-like left inbox, the warm paper Threadwise panel, the threaded-`T` app icon, and the `CLEAR THREADS. BETTER INBOX.` tagline.
- Updated the selected email surface so `Agent View`, `Correct / Teach`, and `Today` are visible in the same demo frame. The live implementation intentionally keeps editable teaching controls where the static mock shows a staged correction preview.
- Updated the Gmail companion extension panel, daily dashboard, and unsubscribe review page to share the same chunky ink-and-paper visual system.
- Captured the side-by-side review image at `docs/assets/demo-stage/threadwise-075-mock-vs-live.png`.

## Validation

- `python3 -m py_compile src/gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- `python3 -m unittest tests.test_gmail_companion_ui`
- Browser screenshots captured for `/simulator`, `/daily-dashboard`, and `/unsubscribe-review`.

## Output

- Mock-faithful live Threadwise UI surfaces
- Visual smoke screenshots for review
- Updated tests where user-visible structure changed

## Boundaries

- Do not add new inbox actions.
- Do not redesign real Gmail outside Threadwise-controlled demo/simulator context.
- Do not capture final recruiter GIFs or MP4s in this slice.
- Do not imply ProtonMail or Outlook support is shipped.
