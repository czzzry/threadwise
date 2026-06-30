# Status

Current
Current as of: 2026-06-30
Triage state: `ready-for-agent`
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

- [ ] Three short GIFs are captured: daily briefing/report, teach safely, unsubscribe with approval.
- [ ] Each GIF is roughly 10-20 seconds or shorter where practical.
- [ ] Optional MP4 versions are produced if they materially improve quality or later embedding.
- [ ] Static screenshots are captured for the key product states.
- [ ] Assets use only synthetic Gmail/demo data.
- [ ] Assets do not reveal private email, credentials, browser profile data, or sensitive account details.
- [ ] Captions are readable and do not overclaim current functionality.
- [ ] Assets are saved under `docs/assets/` with stable names.
- [ ] A visual QA pass verifies no obvious clipping, unreadable text, or awkward framing.

## Output

- README-ready GIFs
- Optional MP4 versions
- Static screenshots
- Capture notes

## Boundaries

- Do not change product behavior in this slice except for tiny capture-only fixes discovered during visual QA.
- Do not use private inbox data.
- Do not show roadmap states as current shipped behavior.
