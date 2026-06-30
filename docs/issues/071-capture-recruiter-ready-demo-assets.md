# Status

Current
Current as of: 2026-06-30
Triage state: `completed`
Builds on: `docs/prd.md`, `docs/issues/069-apply-approved-threadwise-aesthetic-to-product-surfaces.md`, `docs/issues/070-build-demo-script-and-synthetic-gmail-seed-plan.md`

# Title

Capture recruiter-ready Threadwise demo assets

## Type

Demo / Media production

## Blocked by

- `docs/issues/069-apply-approved-threadwise-aesthetic-to-product-surfaces.md`
- `docs/issues/070-build-demo-script-and-synthetic-gmail-seed-plan.md`

## User stories covered

`1`, `2`, `5`, `6`, `7`, `8`, `9`, `10`, `27`, `28`, `29`, `30`, `31`, `32`, `37`, `38`

## What to build

Capture the public demo assets for the recruiter-ready Threadwise portfolio release.

This slice should use the approved UI aesthetic and the demo script to produce short, committed visual assets that show the product loop without requiring a recruiter to run local setup.

## Acceptance criteria

- [x] Three short GIFs are captured: daily briefing/report, teach safely, unsubscribe with approval.
- [x] Each GIF is roughly 10-20 seconds or shorter where practical.
- [x] Optional MP4 versions are produced if they materially improve quality or later embedding.
- [x] Static screenshots are captured for the key product states.
- [x] Assets use only synthetic Gmail/demo data.
- [x] Assets do not reveal private email, credentials, browser profile data, or sensitive account details.
- [x] Captions are readable and do not overclaim current functionality.
- [x] Cursor movement, text-field caret visibility, and typed text entry are slow and clear enough to follow in the teach demo GIF.
- [x] Assets are saved under `docs/assets/` with stable names.
- [x] A visual QA pass verifies no obvious clipping, unreadable text, or awkward framing.

## Output

- README-ready GIFs
- Optional MP4 versions
- Static screenshots
- Capture notes

## Boundaries

- Do not change product behavior in this slice except for tiny capture-only fixes discovered during visual QA.
- Do not use private inbox data.
- Do not show roadmap states as current shipped behavior.

## Completion Notes

Completed on: 2026-06-30

Generated assets:

- `docs/assets/threadwise-daily-briefing.gif` and `docs/assets/threadwise-daily-briefing.mp4` (`18.125s`)
- `docs/assets/threadwise-teach-safely.gif` and `docs/assets/threadwise-teach-safely.mp4` (`20.125s`)
- `docs/assets/threadwise-unsubscribe-approval.gif` and `docs/assets/threadwise-unsubscribe-approval.mp4` (`16.125s`)
- `docs/assets/threadwise-roadmap-next.gif` and `docs/assets/threadwise-roadmap-next.mp4` (`9.125s`)
- `docs/assets/threadwise-daily-dashboard.png`
- `docs/assets/threadwise-teach-preview.png`
- `docs/assets/threadwise-unsubscribe-review.png`
- `docs/assets/threadwise-roadmap-next.png`
- `docs/assets/threadwise-capture-notes.md`

Implementation:

- Added deterministic capture stage at `docs/assets/demo-stage/threadwise-demo-stage.html`.
- Added repeatable capture script at `scripts/capture_threadwise_demo_assets.mjs`.
- Used a controlled Gmail-like synthetic surface rather than a real Gmail account, so the first critique pass is safe, deterministic, and free of private inbox/OAuth risk.

Validation:

- Ran `node --check scripts/capture_threadwise_demo_assets.mjs`.
- Ran `git diff --check`.
- Verified MP4 durations with `ffprobe`.
- Visually inspected representative frames and static screenshots, including corrected unsubscribe-card focus framing.
