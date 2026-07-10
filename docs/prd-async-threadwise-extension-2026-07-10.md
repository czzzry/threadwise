# Async Threadwise Extension Behavior PRD

Status: Proposed bounded-slice PRD
Current as of: 2026-07-10
Builds on: `AGENTS.md`, `CONTEXT.md`, `docs/v2-alignment.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md`, and the implemented eval/promotion pipeline PRD at `docs/prd-eval-promotion-pipeline-2026-07-10.md`
Supersedes as next planning focus: ad hoc performance tweaks to the current extension flow without a clear response-state model

## Problem Statement

Threadwise already proves a Gmail companion sidebar, a selected-email teaching loop, a daily dashboard, and richer review/workbench support.

The founder's current user problem is not that the extension exists. The problem is that the extension can feel too slow and too silent:

1. when the founder opens an email, Threadwise can take too long to understand the current email
2. when the founder asks Threadwise to do something, the product can spend too long working before it clearly shows whether it is still running, succeeded, or got stuck
3. when the current flow blocks on understanding, preview generation, Gmail write-through, broader refresh, or reusable-change preparation, the founder is left wondering whether Threadwise is frozen or broken

From the founder's perspective, the desired behavior is:

> Threadwise should respond immediately, show me what stage it is in, and finish heavier work without leaving me guessing.

This is primarily an interaction-model problem, not yet a container-choice problem. The extension should remain the primary surface for now. A full standalone Threadwise app remains a future product branch, not the current answer to the founder's pain.

## Solution

Rebuild the Gmail companion interaction model around explicit asynchronous states while keeping the extension/sidebar as the primary product surface.

The product should stop treating one user action as one silent blocking request. Instead, Threadwise should:

1. acknowledge immediately
2. enter a visible working state
3. complete heavier work in stages
4. update the UI with progress, result, or blocked state
5. reserve broader review and audit surfaces for heavier follow-up when needed

The intended user experience is:

1. the founder opens a Gmail email
2. Threadwise quickly shows that it is reading or understanding the email
3. a first useful judgment appears before every deeper follow-up finishes
4. when the founder teaches or applies a change, Threadwise immediately confirms acceptance of the request
5. Threadwise then progresses through explicit states such as:
   - `Reading`
   - `Understanding`
   - `Preparing rule`
   - `Applying`
   - `Done`
   - `Blocked`
   - `Retry available`
6. heavier reusable-change or evaluation-side work continues without holding the founder hostage in the main sidebar turn

## User Stories

1. As the founder, I want Threadwise to react immediately when I open an email, so that the extension feels alive instead of frozen.
2. As the founder, I want a visible `Reading` or `Understanding` state for the current email, so that I know Threadwise is still working.
3. As the founder, I want a quick first judgment before all deeper reasoning finishes, so that I can keep moving through Gmail.
4. As the founder, I want Threadwise to acknowledge my action immediately when I teach or fix an email, so that I know my request was accepted.
5. As the founder, I want longer-running work to show progress states, so that I do not confuse normal waiting with a broken companion.
6. As the founder, I want Threadwise to distinguish `working`, `done`, `blocked`, and `retry` clearly, so that I know what to do next.
7. As the founder, I want current-email understanding to stay fast even when broader reusable-change preparation is slower, so that the inbox loop stays responsive.
8. As the founder, I want reusable future-rule or candidate preparation to happen without stalling the main current-email response, so that teaching remains practical during normal inbox use.
9. As the founder, I want sidebar refreshes and broader summary recomputation to stop blocking the main interaction turn, so that the extension does not feel heavier than the job requires.
10. As the founder, I want failed or stalled operations to explain whether I should retry, reconnect, or just wait, so that the product feels trustworthy under imperfect conditions.
11. As the founder, I want recent async actions to remain inspectable, so that I can tell what Threadwise just did without depending on memory.
12. As the founder, I want the richer workbench and dashboard surfaces to support deeper review when needed, so that the sidebar can stay compact and fast.
13. As the founder, I want the extension to remain the primary entry point for now, so that we solve the real slowness problem without opening a full standalone-app project.
14. As the founder, I want the architecture to leave room for a future standalone Threadwise app, so that a later v2 product can reuse the async state model instead of starting over.

## Implementation Decisions

- Keep the Gmail extension/sidebar as the primary product surface for this milestone.
- Treat the slowness problem as an interaction-model and request-lifecycle problem first, not as a standalone-app migration problem.
- Separate fast acceptance of user intent from slower completion of heavier work.
- Model selected-email understanding and teach/apply actions as explicit async state machines rather than opaque request/response turns.
- Reuse the existing local companion boundary and product surfaces where possible:
  - Gmail companion sidebar for the primary interaction
  - dashboard/workbench for heavier supporting review
- Prefer a staged response contract:
  - request accepted
  - operation status updated
  - result or blocked state published
- Keep single-email understanding and current-email mutation as the primary fast path.
- Push slower follow-up work behind that fast path where possible:
  - broader reusable-change preparation
  - candidate bookkeeping
  - richer state refresh
  - heavier summary recomputation
- Preserve the current safety boundaries:
  - bounded Gmail label write-back only
  - bounded `INBOX` removal only where already approved
  - no new destructive inbox actions
- Add durable local operation status artifacts only if needed to make retries, receipts, or progress states reliable across refreshes.
- Prefer one shared async state model that could later serve both:
  - the extension/sidebar
  - a future standalone Threadwise workspace
- The future standalone Threadwise app is a valid v2 branch, but it is explicitly out of scope for this bounded PRD.

## Testing Decisions

- Test external visible behavior rather than internal scheduling details.
- Use the highest existing seams first:
  - Gmail companion API contract
  - sidebar/harness state payloads
  - simulator/browser interaction tests
- Characterize the current synchronous pain points before shifting behavior:
  - slow selected-email understanding
  - long-running teach/apply path
  - unclear blocked or retry states
- Add tests that prove the UI receives staged states rather than one final opaque result.
- Add tests that prove current-email usefulness arrives before slower follow-up work finishes.
- Add tests that prove blocked states and retry affordances are explicit.
- Reuse existing prior art in:
  - companion UI tests
  - teaching loop tests
  - browser/simulator acceptance for sidebar states
- Avoid fragile tests that depend on specific timing values or internal coroutine structure. Prefer testing state transitions and visible contracts.

## Out of Scope

- Replacing the Gmail extension with a standalone app in this milestone.
- Rebuilding Threadwise as a desktop-native product shell.
- A full visual redesign of Threadwise UI.
- Broad provider or packaging changes.
- New inbox mutation types or relaxed safety boundaries.
- A dashboard-first or workbench-first product pivot.
- Full cross-provider unified inbox redesign.

## Further Notes

The current recommendation is:

1. implement async behavior inside the extension first
2. prove the product feels responsive in the current Gmail-adjacent surface
3. then perform the future complete UX/UI redesign on top of that improved interaction model

The future standalone Threadwise app remains a meaningful v2 or alternate-MVP candidate because:

- async job states
- richer review queues
- multi-provider operations
- audit and promotion workflows

may eventually deserve a deeper Threadwise-owned workspace than the sidebar alone. But that future branch should inherit this async state model rather than replace it.
