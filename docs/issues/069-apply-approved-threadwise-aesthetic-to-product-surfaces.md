# Status

Completed
Current as of: 2026-06-30
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

# Title

Apply the approved Threadwise aesthetic to the demo-facing product surfaces

## Type

Feature / Design implementation

## Blocked by

- `docs/issues/068-mvp-plus-one-design-review-and-aesthetic-direction.md`

## User stories covered

`21`, `25`, `26`, `41`, `44`

## What to build

Apply the approved warm ink-and-paper Threadwise aesthetic to the actual demo-facing product surfaces.

This slice should use the design reference and logo direction from issue `068` to restyle the Threadwise-controlled UI without changing product scope or behavior. The goal is to make the Gmail companion sidebar, daily dashboard, teach preview, and unsubscribe review cohesive and portfolio-ready before demo capture begins.

The current logo sheet should be treated as a brand source. Extract or prepare the square app icon for use in tight UI contexts, but do not turn this slice into a full brand-system rebuild.

## Acceptance criteria

- [x] The Gmail companion sidebar reflects the approved warm ink-and-paper aesthetic.
- [x] The daily dashboard visually belongs to the same product family as the sidebar.
- [x] The teach/impact preview has clear hierarchy and emphasizes confirmation before broader changes.
- [x] The unsubscribe review/handoff surface matches the same visual system.
- [x] The square Threadwise app icon or equivalent extracted logo treatment appears in appropriate product/demo UI contexts.
- [x] Existing user-visible behavior and safety boundaries are unchanged.
- [x] Existing focused tests pass or are updated for intentional copy/structure changes.
- [x] A browser screenshot or visual smoke check verifies the updated surfaces do not have obvious overflow, clipping, or unreadable text.

## Output

- Updated demo-facing Threadwise UI surfaces.
- Extracted/usable app-icon asset if needed for the UI.
- Validation notes for the visual smoke check.

## Boundaries

- Do not capture final README GIFs or screenshots in this slice.
- Do not seed or operate a real Gmail test account in this slice.
- Do not add new inbox actions.
- Do not redesign Gmail itself.
- Do not make the roadmap multi-inbox state look shipped.

## Completion note

Completed with a scoped visual pass over the demo-facing Threadwise surfaces:

- Gmail companion sidebar
- local simulator / harness panel
- daily dashboard
- unsubscribe review

The square app icon was extracted from `docs/design ideas/threadwise logo.png` into `docs/assets/brand/threadwise-app-icon.png` and used as the compact product mark.

Validation:

- `node --check extensions/gmail_companion/content.js`
- `python3 -m py_compile src/gmail_companion_ui.py`
- `python3 -m unittest tests.test_gmail_companion_ui`
- Browser smoke screenshots:
  - `/tmp/threadwise-simulator-069-loaded.png`
  - `/tmp/threadwise-dashboard-069.png`
  - `/tmp/threadwise-unsubscribe-069.png`
