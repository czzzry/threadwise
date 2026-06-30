# Status

Current
Current as of: 2026-06-30
Triage state: `completed`
Builds on: `docs/prd.md`, `docs/issues/072-package-readme-and-portfolio-for-mvp-plus-one.md`

# Title

Close the MVP+1 public demo milestone

## Type

Release closeout

## Blocked by

- `docs/issues/072-package-readme-and-portfolio-for-mvp-plus-one.md`

## User stories covered

`12`, `13`, `16`, `17`, `40`, `45`

## What to build

Close the MVP+1 recruiter-ready portfolio milestone so the repo is clean, documented, and publishable.

This slice should verify the final asset links, run the relevant tests and smoke checks, update any stale current-state docs, write a handoff, commit all intended files, push, and optionally tag the milestone.

## Acceptance criteria

- [x] Relevant tests and smoke checks pass.
- [x] README and portfolio asset links render correctly.
- [x] Current-state docs no longer say polished screenshots/demo assets are missing.
- [x] Any generated private/local artifacts remain ignored or uncommitted.
- [x] A handoff summarizes the MVP+1 result, validation, risks, and next recommended product step.
- [x] Git status is clean after commit.
- [x] Changes are pushed.
- [x] Optional milestone tag was deferred because the founder did not explicitly approve a tag.

## Output

- Final MVP+1 handoff
- Clean committed repo state
- Pushed branch
- Optional milestone tag

## Boundaries

- Do not start the next product expansion slice in this closeout.
- Do not introduce new demo assets after closeout validation unless a defect is found.

## Completion Notes

Completed on: 2026-06-30

Public package:

- README leads with the Threadwise primary logo, selected GIF, and synthetic-data disclaimer.
- Portfolio doc mirrors the final demo story and architecture explanation.
- `CONTEXT.md` and `docs/prd.md` now mark MVP+1 as completed and direct MVP+2 back to alignment first.

Validation:

- `python3 -m unittest tests.test_gmail_companion_ui tests.test_runtime_cascade tests.test_runtime_cascade_cli tests.test_unsubscribe_execution`
- `node --check scripts/capture_threadwise_recruiter_story_asset.mjs`
- `ffprobe` on `docs/assets/threadwise-recruiter-story.gif`: `960x600`, `97` frames, `14.5s`
- `git diff --check`

Handoff:

- `docs/handoff/2026-06-30-mvp-plus-one-public-demo-closeout.md`

Generated rejected/unused demo experiments were moved out of the repo and preserved at:

- `/private/tmp/threadwise-mvp1-rejected-assets-20260630/`
