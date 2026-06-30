# Status

Current
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

- [ ] The Gmail companion sidebar reflects the approved warm ink-and-paper aesthetic.
- [ ] The daily dashboard visually belongs to the same product family as the sidebar.
- [ ] The teach/impact preview has clear hierarchy and emphasizes confirmation before broader changes.
- [ ] The unsubscribe review/handoff surface matches the same visual system.
- [ ] The square Threadwise app icon or equivalent extracted logo treatment appears in appropriate product/demo UI contexts.
- [ ] Existing user-visible behavior and safety boundaries are unchanged.
- [ ] Existing focused tests pass or are updated for intentional copy/structure changes.
- [ ] A browser screenshot or visual smoke check verifies the updated surfaces do not have obvious overflow, clipping, or unreadable text.

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
