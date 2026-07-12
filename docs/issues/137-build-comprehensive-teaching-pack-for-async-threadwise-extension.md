# Build Comprehensive Teaching Pack for Async Threadwise Extension

Status: Triaged ready-for-agent
Type: AFK
Parent PRD: `docs/prd-async-threadwise-extension-2026-07-10.md`

## What to build

Create a comprehensive founder-facing teaching pack that explains the async Threadwise extension work at a professional developer level.

This slice should turn the implemented work and decisions from the async extension sequence into a structured learning artifact set using the repo's teaching workflow, so the founder can move from current understanding to real architectural fluency.

The teaching pack should not explain isolated functions only. It should explain:

- the user problem that drove the async redesign
- the architectural decision to keep the extension and change the interaction model first
- what `async` means in this product context
- when professional developers use async patterns and when they do not
- the state-machine and request-lifecycle changes introduced here
- how the extension, local companion, dashboard, workbench, and future standalone-app branch fit together
- the major tradeoffs and rejected alternatives
- diagrams, reference material, and memory aids that help the founder retain the model

The output should be tied to the founder's real mission in this repo: learning the product and engineering decisions well enough to speak truthfully, reason about future changes, and operate like a professional collaborator rather than memorizing scattered implementation details.

## User stories covered

- 14. As the founder, I want the architecture to leave room for a future standalone Threadwise app, so that a later v2 product can reuse the async state model instead of starting over.
- Teaching goal added by founder follow-up: as the founder, I want a comprehensive teaching pack for this slice, so that I understand the concepts, tradeoffs, architecture, and implementation decisions well enough to think like a professional developer in this area.

## Acceptance criteria

- [ ] A teaching workspace mission for this topic exists and reflects why the founder wants to learn this material.
- [ ] The teaching pack explains the async extension redesign from user problem through architecture, implementation choices, and future product branches.
- [ ] The pack includes at least one lesson, one durable reference artifact, and one learning record tied to this async Threadwise work.
- [ ] The material uses diagrams or equivalent visual explanations where they improve understanding.
- [ ] The material explains when async is the right tool, when it is not, and what alternatives were available here.
- [ ] The pack is grounded in the actual implemented Threadwise code and product decisions, not a generic async tutorial.

## Blocked by

- `docs/issues/133-add-async-selected-email-understanding-states.md`
- `docs/issues/134-add-async-action-lifecycle-for-teach-and-fix.md`
- `docs/issues/135-move-slower-follow-up-work-off-the-main-sidebar-path.md`
- `docs/issues/136-add-recent-activity-and-retry-surface-for-async-operations.md`
