# Status

Current
Current as of: 2026-06-30
Triage state: `completed`
Builds on: `docs/prd.md`, `docs/issues/077-recapture-final-recruiter-demo-assets-from-approved-ui.md`

# Title

Package README and portfolio docs for the MVP+1 recruiter demo

## Type

Docs / Portfolio packaging

## Blocked by

- `docs/issues/077-recapture-final-recruiter-demo-assets-from-approved-ui.md`

## User stories covered

`1`, `2`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `36`, `37`, `38`, `45`

## What to build

Update the public repo reading experience so Threadwise is understandable and impressive without local setup.

The README should lead with the product story, the Threadwise logo, the short demo assets, and an explicit synthetic-data disclaimer. Deeper technical architecture, safety boundaries, and process evidence should remain available below the fold or in linked docs.

The founder-provided primary logo should be made prominent in README/portfolio packaging. The current logo sheet may need extraction into separate public assets before embedding.

This slice must use the final assets from `077`, not the earlier asset pass from `071`, because `071` was generated before the approved mock was fully implemented.

## Acceptance criteria

- [x] The README first screen shows the Threadwise identity and product loop without requiring setup.
- [x] The primary Threadwise logo appears prominently in README or an appropriate hero section.
- [x] The founder-approved single GIF is embedded near the top with a concise synthetic-data caption.
- [x] Static screenshots remain a follow-up because the approved recruiter hook is the single GIF.
- [x] The README clearly states that demo assets use synthetic Gmail-style data.
- [x] The README distinguishes current behavior from roadmap/multi-inbox direction.
- [x] `docs/portfolio.md` is updated to match the final demo story and asset set.
- [x] Asset references work through relative GitHub paths.
- [x] Historical/process docs remain linkable but do not dominate the recruiter-facing path.

## Output

- Updated README
- Updated portfolio doc
- Extracted public logo assets if not already created
- Verified asset links

## Boundaries

- Do not add new product capabilities in this slice.
- Do not bury safety boundaries.
- Do not claim ProtonMail/Outlook support as part of the current demo.

## Completion Notes

Completed on: 2026-06-30

Founder-approved packaging change:

- Use one combined recruiter-facing GIF at the top of the README instead of separate daily/teach/unsubscribe clips.
- The selected asset is `docs/assets/threadwise-recruiter-story.gif`, generated from the slower/prominent narration variant.
- MP4 generation was intentionally deferred because GitHub README renders GIFs inline and the founder chose not to pursue video unless needed for external portfolio/social surfaces.

Updated files:

- `README.md`
- `docs/portfolio.md`
- `docs/assets/brand/threadwise-primary-logo.png`
- `docs/assets/threadwise-recruiter-story.gif`
- `docs/assets/threadwise-recruiter-story-capture-notes.md`
- `docs/assets/threadwise-recruiter-story-variants-notes.md`
- `scripts/capture_threadwise_recruiter_story_asset.mjs`
