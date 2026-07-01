# PRD

Status: Completed bounded-slice PRD
Current as of: 2026-07-01
Builds on: `docs/archive/prd-mvp-plus-three-slice-a-interactive-teaching-loop-completed-2026-07-01.md`
Release target: MVP+3 Slice B Gmail companion shell polish
GitHub issue: `#36`

This PRD describes completed MVP+3 Slice B for Threadwise: polish the Gmail companion shell after the interactive teaching loop landed.

## Problem Statement

After MVP+3 Slice A, Threadwise became a more useful Gmail-side teaching companion, but several shell-level issues still made it feel rough during real use:

- minimized mode still occupied too much visual space and showed text/status chrome
- the brand/logo area could appear as an empty box if the image did not load
- a technical implementation footer was visible in the product UI
- disconnected/error states exposed raw plumbing more than a short useful recovery path

The core problem was:

> Can Threadwise stay minimally present in Gmail when not needed, while still giving a clear recovery path when the companion is disconnected?

## Solution

Polish the Gmail companion shell without changing product scope or adding new email actions.

The completed slice:

- makes minimized mode a compact logo-only reopen button
- adds a text fallback if the brand icon image fails to load
- removes the internal technical footer from the live extension UI
- improves disconnected/error presentation with friendly copy, technical detail behind an expander, concrete remediation, and a `Check again` action

## User Stories

1. As the founder, I want minimized Threadwise to collapse into a very small logo-only control, so that it does not cover Gmail when I am not actively using it.
2. As the founder, I want the Threadwise logo area to show a fallback mark if the image fails, so that the companion does not look broken.
3. As the founder, I do not want internal harness/server implementation text in the Gmail sidebar, so that the product UI feels clean.
4. As the founder, I want disconnected states to tell me what happened and what to try next, so that failures are recoverable without raw error noise.
5. As the founder, I want a quick `Check again` action, so that I can retry after restarting or reconnecting the companion.

## Implementation Decisions

- Slice B keeps the current extension plus local companion delivery model.
- Minimized mode hides content, footer, feedback capture, title, status, and minimize button.
- The minimized logo remains clickable and reopens Threadwise.
- The brand image keeps using the existing local companion asset endpoint.
- A text fallback is shown if the image fails to load.
- The internal "stored inbox snapshot / local harness" footer is removed from the extension UI.
- Error states keep technical details available, but behind an expandable detail block.
- The error state includes a `Check again` action that forces a fresh state request.
- No new Gmail mutation, live Gmail fetch, delete, archive, send, reply, or unsubscribe behavior is introduced.

## Testing Decisions

- Good tests protect the user-visible extension shell contract rather than internal CSS minutiae.
- JavaScript syntax checks protect the content script.
- Companion UI tests assert logo-only minimized mode markers, brand fallback markers, absence of the technical footer string, and the `Check again` recovery action.
- Full test discovery remains the regression gate.

## Out of Scope

- Full installer or menubar app.
- Native Gmail DOM-perfect controls.
- New delivery model exploration.
- Dashboard visual redesign.
- New classification, teaching, or Gmail mutation behavior.

## Further Notes

- MVP+3 Slice B implementation progress is `issues 4/4 => MVP+3 Slice B = done`.
- GitHub parent issue `#36` and child issues `#37` through `#40` are closed.
- Published MVP+3 Slice B issue briefs:
  - `#37` Logo-only minimized Gmail companion - complete
  - `#38` Brand icon fallback - complete
  - `#39` Remove technical sidebar footer - complete
  - `#40` Friendly companion error state - complete
- Slice A is archived at `docs/archive/prd-mvp-plus-three-slice-a-interactive-teaching-loop-completed-2026-07-01.md`.
