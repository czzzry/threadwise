# Status

Current
Current as of: 2026-06-30
Triage state: `needs-triage`
Builds on: `docs/prd.md`, `docs/issues/076-rebuild-demo-capture-around-final-implemented-ui.md`

# Title

Recapture final recruiter demo assets from approved UI

## Type

HITL / Demo / Media production

## Blocked by

- `docs/issues/076-rebuild-demo-capture-around-final-implemented-ui.md`

## User stories covered

`1`, `2`, `5`, `6`, `7`, `8`, `9`, `10`, `27`, `28`, `29`, `30`, `31`, `32`, `37`, `38`

## What to build

Replace the current recruiter demo assets with final assets generated from the approved, mock-faithful UI.

The first review output should be GIFs only, so the founder can judge motion, pacing, cursor visibility, captions, and visual fidelity quickly. MP4 versions should be generated only after the GIF direction is approved.

## Acceptance criteria

- [ ] First pass produces GIFs for daily briefing/report, teach safely, unsubscribe approval, and optional roadmap/next.
- [ ] GIFs are generated before MP4s so the founder can approve the direction quickly.
- [ ] GIFs use the final implemented visual design from `075`.
- [ ] GIFs are roughly 10-20 seconds or shorter where practical.
- [ ] Captions are readable and do not overclaim current functionality.
- [ ] Cursor movement, text-field caret visibility, and typed text entry are slow and clear enough to follow in the teach demo.
- [ ] Assets use only synthetic Gmail/demo data.
- [ ] Assets do not reveal private email, credentials, browser profile data, or sensitive account details.
- [ ] Founder approval is received on the GIF set before MP4 generation.
- [ ] MP4 versions are generated after GIF approval.
- [ ] Static screenshots are captured for the key product states after the final visual direction is accepted.
- [ ] Final assets are saved under `docs/assets/` with stable README-ready names.

## Output

- Founder-approved GIF set
- MP4 versions after GIF approval
- Static screenshots
- Updated capture notes

## Boundaries

- Do not proceed to README packaging before GIF approval.
- Do not generate MP4s before the founder approves the GIF direction.
- Do not use private inbox data.
- Do not show roadmap states as current shipped behavior.

