# Remove Unsubscribe and Destructive Suspicious-Sender Flows

Status: Complete; automated acceptance passed
Current as of: 2026-08-13
Founder approval: Explicitly approved in the active Codex task
Builds on: `CONTEXT.md`, `docs/v2-alignment.md`, and `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Problem

At approval time, Threadwise still exposed unsubscribe as a core product workflow in the Gmail companion and legacy local workbench. It also diverted a Gmail correction to `suspicious` into a destructive provider action that created a Gmail filter and moved the current message to Trash. These flows are no longer part of the approved product direction.

## Bounded outcome

- Remove every user-reachable unsubscribe surface and route from the Gmail companion and local workbench.
- Remove the Gmail destructive suspicious-sender preview/apply diversion, routes, filter/Trash client methods, and expanded Gmail settings scope.
- Preserve `List-Unsubscribe` normalization as classification evidence.
- Preserve `suspicious` as a classification and review label.
- Route a Gmail correction to `suspicious` through the ordinary non-destructive label-only correction path.
- Keep future durable rules for `suspicious` blocked.
- Preserve historical local unsubscribe artifacts; do not execute or delete them.

## Acceptance criteria

1. No companion or workbench UI renders an unsubscribe action, count, review link, or execution control.
2. Former unsubscribe routes and `/api/safety-preview` / `/api/safety-apply` return the normal not-found response and perform no write or outbound request.
3. Companion health capabilities do not advertise unsubscribe.
4. The extension never requests the removed unsubscribe or safety routes.
5. A correction interpreted as `suspicious` uses the ordinary label-only teaching path and cannot create a Gmail filter, Trash mail, or widen OAuth to Gmail settings.
6. Durable suspicious rules remain blocked by the existing teachable-memory boundary.
7. `List-Unsubscribe` metadata continues to normalize and inform classification.
8. Focused and repository-wide tests pass.

## Out of scope

- Removing `suspicious` from the taxonomy or safety-review reporting.
- Removing `List-Unsubscribe` from provider normalization or classifier inputs.
- Deleting historical unsubscribe artifacts from disk.
- New provider actions, dependencies, frameworks, or architecture rewrites.

## Completion evidence

See `docs/handoff/2026-08-12-core-flow-redesign-and-model-labeling.md` for the validation record shared with issues `#140` and `#141`.
