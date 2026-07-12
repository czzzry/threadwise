# Status

Current
Current as of: 2026-06-30
Triage state: `completed`
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

- [x] Founder-approved GIF direction produced as one combined recruiter story asset instead of four separate clips.
- [x] GIF was generated before any MP4 work so motion, pacing, narration, and fidelity could be approved quickly.
- [x] GIF uses the final implemented Threadwise visual design language from `075`.
- [x] GIF is short enough for the README hero at `14.5s`.
- [x] Captions/narration are readable and do not overclaim current functionality.
- [x] Teach moment shows typed correction text clearly enough to follow.
- [x] Asset uses only synthetic Gmail/demo data.
- [x] Asset does not reveal private email, credentials, browser profile data, or sensitive account details.
- [x] Founder approval was received on the GIF direction before MP4 generation.
- [x] MP4 generation was intentionally deferred because the README uses the inline GIF.
- [x] Static screenshots remain a follow-up after README context review.
- [x] Final asset is saved under `docs/assets/` with a stable README-ready name.

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

## Completion Notes

Completed on: 2026-06-30

Founder-approved outcome:

- The four-GIF plan was superseded by one combined recruiter-facing GIF.
- The selected public asset is `docs/assets/threadwise-recruiter-story.gif`.
- The liked baseline is preserved at `docs/assets/threadwise-recruiter-story-v1-liked-baseline.gif`.
- The selected slower/prominent variant is preserved at `docs/assets/threadwise-recruiter-story-v2-slower-prominent.gif`.
- MP4 was skipped for now because GitHub README renders GIFs inline and the founder chose not to pursue video unless needed for external portfolio/social use.

Validation:

- `ffprobe` verified `docs/assets/threadwise-recruiter-story.gif` at `960x600`, `97` frames, and `14.5s`.
- `node --check scripts/capture_threadwise_recruiter_story_asset.mjs` passed.
- `git diff --check` passed.
