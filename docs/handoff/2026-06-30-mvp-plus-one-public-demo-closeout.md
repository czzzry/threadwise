# MVP+1 Public Demo Closeout

Status: Completed handoff
Current as of: 2026-06-30

## Result

MVP+1 is closed as a recruiter-facing portfolio packaging milestone.

The public repo now opens with:

- Threadwise primary logo
- one inline README GIF that explains the product loop without setup
- a synthetic-data disclaimer
- simple architecture notes for technical reviewers
- current-vs-roadmap framing so Gmail is current and multi-inbox support is not overclaimed

Primary public asset:

- `docs/assets/threadwise-recruiter-story.gif`

Supporting assets:

- `docs/assets/brand/threadwise-primary-logo.png`
- `docs/assets/demo-stage/threadwise-recruiter-story-stage.html`
- `docs/assets/threadwise-recruiter-story.png`
- `docs/assets/threadwise-recruiter-story-capture-notes.md`
- `docs/assets/threadwise-recruiter-story-variants-notes.md`
- `scripts/capture_threadwise_recruiter_story_asset.mjs`

Preserved variants:

- `docs/assets/threadwise-recruiter-story-v1-liked-baseline.gif`
- `docs/assets/threadwise-recruiter-story-v1-liked-baseline.png`
- `docs/assets/threadwise-recruiter-story-v1-liked-baseline-notes.md`
- `docs/assets/threadwise-recruiter-story-v2-slower-prominent.gif`
- `docs/assets/threadwise-recruiter-story-v2-slower-prominent.png`

The selected public GIF is the slower/prominent narration version.

## Decisions

- Use one combined recruiter GIF instead of separate daily/teach/unsubscribe/roadmap clips.
- Skip MP4 for now because GitHub README renders the GIF inline and no external video surface is required yet.
- Keep rejected combined-reel/live-demo experiments out of the public commit.
- Preserve rejected/unused generated assets outside the repo at `/private/tmp/threadwise-mvp1-rejected-assets-20260630/`.
- Mark MVP+1 PRD complete and update `CONTEXT.md` so the next step starts with MVP+2 alignment rather than more portfolio packaging.

## Validation

Passed:

- `python3 -m unittest tests.test_gmail_companion_ui tests.test_runtime_cascade tests.test_runtime_cascade_cli tests.test_unsubscribe_execution`
- `node --check scripts/capture_threadwise_recruiter_story_asset.mjs`
- `ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=width,height,duration,nb_read_frames,r_frame_rate -of json docs/assets/threadwise-recruiter-story.gif`
- `git diff --check`

GIF metadata:

- `960x600`
- `97` frames
- `14.5s`

## Current State

Completed issues:

- `077`: final recruiter GIF asset
- `072`: README and portfolio packaging
- `073`: MVP+1 closeout

Updated current-state docs:

- `CONTEXT.md`
- `docs/prd.md`

## Residual Risks

- Static screenshots remain a follow-up if the founder wants more inspectable stills below the README GIF.
- MP4 remains useful only for external portfolio/social use, not required for GitHub README.
- The public demo is deterministic synthetic capture, not a live-click recording. That is intentional for privacy and repeatability.

## Recommended Next Step

Start MVP+2 with alignment/grill before creating a new PRD.

Likely discussion branch:

- whether MVP+2 should be ProtonMail expansion, inbox-agnostic architecture, or another recruiter/public packaging refinement
- what safety boundary applies before any new provider-side mutation
- whether the next product step should improve real daily use or public demo depth
