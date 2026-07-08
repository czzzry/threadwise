# Teach / Apply Write-Through Completion PRD

Status: Current proposed bounded-slice PRD
Current as of: 2026-07-07
Builds on: `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, and founder feedback from July 7
Supersedes as current planning focus: `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md` for the next inbox-repair slice
GitHub parent issue: `#58`

## Problem Statement

Threadwise can already propose a correction rule, save future learning, and rewrite matching stored emails. The problem is that the product still does not complete the loop the founder expects: teach a rule, apply it, reload the inbox, and visibly see the affected mail relabeled.

The current system still feels split across two worlds:

1. local batch teaching and preview
2. inbox-level change the founder expects to observe after the rule is applied

That split makes the product feel like it saves intent but does not finish the job.

## Solution

Rebuild the teach/apply loop around explicit states and explicit write-through outcomes:

1. draft intent
2. proposed rule
3. accepted rule
4. scope choice
5. applying
6. compact receipt

Within that state machine, collapse execution into three explicit outcomes that the founder can understand at a glance:

1. apply once
2. apply once + future
3. apply once + future + inbox

The first option only changes the current email. The second option changes the current email and saves the rule for future matching mail. The third option also rewrites all matching existing inbox mail through Gmail write-through, not just locally stored batch examples, and makes that result obvious after refresh.

The result state must state exactly what changed and what did not change. Reloading Threadwise after the action should show the new state instead of the stale one whenever the inbox write-through path succeeded. If a write fails, the user must not lose the rule text they entered or accepted.

## User Stories

1. As the founder, I want one correction flow that ends in a visible result, so that I know Threadwise actually changed something.
2. As the founder, I want to choose between applying once, applying once plus future, and applying once plus future plus inbox, so that I can control the blast radius.
3. As the founder, I want the current-email fix path to be the simplest path, so that I can use it when I only want to correct one email.
4. As the founder, I want saving a future rule to remain available, so that I can teach Threadwise without rewriting my inbox.
5. As the founder, I want the inbox-wide option to explicitly rewrite matching existing inbox mail, so that I can clear recurring exceptions in one move.
6. As the founder, I want the inbox-wide option to clearly say that it is affecting existing mail, so that I do not confuse it with future-only learning.
7. As the founder, I want the result view to show whether the change hit the current email, future mail, and existing inbox mail, so that success and failure are easy to distinguish.
8. As the founder, I want a reload after apply to reflect the new labels, so that the product feels live rather than cached.
9. As the founder, I want stale selected-email state to clear when nothing is open, so that I do not think an old email is still active.
10. As the founder, I want the companion to tell me when a rule was saved but not yet reprocessed through the inbox, so that I understand why some items still need check.
11. As the founder, I want Threadwise to first show me the rule it thinks I mean, so that I can approve or edit the understanding before choosing scope.
12. As the founder, I want my teach text to survive failed apply attempts, so that I can retry without retyping.

## Implementation Decisions

- The teach loop should separate rule definition from scope selection.
- The correction decision surface should expose three concise scope choices only:
  - `Fix email`
  - `Fix + future`
  - `Fix + inbox`
- The teach flow should use:
  - one intent input
  - one `Proposed rule:` step
  - `Edit` / `Looks right`
  - `Use this rule` when the proposal is edited
- If an edited rule clearly states which emails it applies to and what should happen, accept it directly.
- If an edited rule is ambiguous, reformulate once and ask for confirmation.
- The inbox-wide option should use the accepted rule as the match definition and execute a full Gmail inbox backfill/write-through path.
- Matching should be conservative by default. Broad domain-level application should happen only when the accepted rule explicitly supports it.
- The result state should report exact scope effects, not generic success copy.
- Reloading the companion after apply should re-read the persisted local state and reflect the latest applied labels.
- If apply fails at any stage, preserve the draft/accepted rule text and allow retry without retyping.
- The empty home state should be minimal and should never preload a stale previously reviewed email.
- The slice should preserve the current safety boundary: no delete, trash, send, reply, or autonomous provider-wide mutation beyond the existing bounded apply paths.
- No undo is required in this slice because the flow is non-destructive.
- Large `Fix + inbox` runs should require explicit inline confirmation when the estimated match count exceeds `200`.

## Testing Decisions

- Add tests that prove the teach loop transitions through draft -> proposal -> accepted rule -> scope -> receipt.
- Add tests that prove the three scope choices map to distinct outcomes.
- Add tests that prove the result state distinguishes current-email, future-rule, and matching-inbox effects.
- Add tests that prove failed apply preserves the teach text for retry.
- Add tests that prove no stale selected email appears when nothing is open.
- Add tests that prove large inbox runs require explicit inline confirmation.
- Add tests that prove reloading the companion after apply surfaces the updated stored state.
- Use the simulator and stored-batch tests as the main seams, because they already represent the user-visible correction loop.

## Out of Scope

- Rebuilding unrelated dashboard surfaces.
- Changing the taxonomy itself.
- Adding new Gmail mutation types.
- Global inbox rewrites that are not bounded by the accepted rule-matching model.
- A standalone rule-management surface.
- Delete/archive/trash actions.

## Further Notes

This slice is the product step that moves Threadwise from "I stored a lesson" toward "I changed the inbox and can see that it happened."

The product principle for this slice is:

`Every teach action must produce an explicit contract before execution and an explicit receipt after execution.`
