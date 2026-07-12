# Status

Current
Current as of: 2026-06-30
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/075-implement-approved-threadwise-mock-fidelity-in-live-surfaces.md`

# Title

Rebuild demo capture around final implemented UI

## Type

AFK / Demo infrastructure

## Blocked by

- `docs/issues/075-implement-approved-threadwise-mock-fidelity-in-live-surfaces.md`

## User stories covered

`18`, `19`, `27`, `28`, `29`, `30`, `37`, `38`, `43`

## What to build

Correct the capture architecture so final demo assets are generated from the implemented mock-faithful UI, or from a deterministic capture route/stage that shares the same styling and structure closely enough that it cannot drift into a separate design.

The previous asset pass produced useful motion experiments, but the capture stage diverged from the approved mock. This slice should prevent that from recurring before final assets are regenerated.

## Acceptance criteria

- [ ] Capture uses the implemented final UI directly, or a capture harness that shares the same CSS/component source as the final UI.
- [ ] The capture path can render the daily briefing, teach safely, unsubscribe approval, and roadmap/next states.
- [ ] Overlay captions, cursor motion, text-entry caret, and zoom/pan controls remain available for GIF capture.
- [ ] The capture path uses only synthetic demo data.
- [ ] The capture path does not reference private inbox data, credentials, OAuth screens, or real account identifiers.
- [ ] A smoke check verifies each planned capture state loads without obvious clipping or missing assets.
- [ ] The roadmap state is clearly marked as future direction, not shipped scope.

## Output

- Updated deterministic capture path for final UI
- Smoke-verified capture states
- Notes explaining how the capture path avoids design drift

## Boundaries

- Do not generate final MP4s in this slice.
- Do not replace README assets in this slice.
- Do not use private email or live account data.
- Do not add new product behavior solely for the capture path.
