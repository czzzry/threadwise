# Correct / Teach State-Machine Simplification PRD

Status: Current proposed bounded-slice PRD
Current as of: 2026-07-07
Builds on: `docs/v2-alignment.md`, `docs/prd.md`, `docs/ui-ux-audit/ui-ux-audit.md`, GitHub issues `#42`, `#51`, `#52`, and founder feedback from July 7
Supersedes as current planning focus: the completed three-consequence Correct / Teach preview model from the July 2 UX batch
GitHub parent issue: `#58`

## Problem Statement

Threadwise can already inspect a Gmail email, accept a correction, preview broader learning, and apply bounded changes. The problem is that the Correct / Teach loop still feels like a dense control panel instead of a clear conversation with an agent.

The founder's latest feedback identifies two connected failures:

1. `Fix this email` is not trustworthy enough in real use. It may be failing, appearing to fail, or being obscured by refresh/result-state behavior.
2. The teaching UI exposes too many internal concepts at once: current-email fix, wider rule, future rule, broader rule, affected emails, manual label choice, and refinement.

From the user's perspective, the desired loop is simpler:

> Threadwise proposes the rule it thinks it should follow. I approve it or correct it. Then I choose where that understood rule applies.

The current UI asks the founder to reason about implementation scopes before Threadwise has clearly shown what it understood.

## Solution

Rebuild Correct / Teach around explicit states and clean transitions rather than another patch to the existing stacked sidebar.

The compact Gmail companion should show one current job at a time:

1. `Viewing email`: show the current judgment and one correction entry point.
2. `Teaching`: capture the founder's correction in plain language.
3. `Rule proposed`: show one plain-English rule Threadwise thinks it learned.
4. `Refining`: let the founder change the rule without losing context.
5. `Scope confirmation`: after the rule is accepted, choose where it applies.
6. `Applying`: show immediate progress and block duplicate actions.
7. `Result`: say exactly what changed and what did not.
8. `Blocked`: explain why the current email cannot be fixed yet and offer one recovery action.

The first implementation must diagnose and harden `Fix this email` at the same time as it introduces the state model. If the primary current-email correction is unreliable, no broader teaching UI should be considered shippable.

## User Stories

1. As the founder, I want the Correct / Teach flow to show one state at a time, so that I know what decision I am making.
2. As the founder, I want Threadwise to first tell me the rule it thinks it learned, so that I can approve or refine its understanding.
3. As the founder, I want to approve or change the proposed rule before choosing scope, so that I am not asked to apply something I have not understood.
4. As the founder, I want `Fix this email` to visibly and reliably update the current email, so that correction feels trustworthy.
5. As the founder, I want the result state to say whether the current email changed locally, in Gmail, both, or neither, so that I do not mistake hidden state for failure.
6. As the founder, I want the UI to avoid showing current-email, future-rule, and existing-email rewrite controls all at once, so that I am not comparing internal product concepts.
7. As the founder, I want future learning to be described as applying the accepted rule to future emails, so that it feels like teaching rather than saving an internal artifact.
8. As the founder, I want existing-email rewrites to remain a separate confirmation, so that Threadwise never silently changes many emails.
9. As the founder, I want the compact sidebar to stay sparse during correction, so that Gmail remains the main reading surface.
10. As the founder, I want advanced rule details, affected examples, manual label override, and debug/source details hidden until requested, so that the main flow stays understandable.
11. As the founder, I want blocked/unsynced states to offer one clear recovery path, so that I know whether to sync, retry, or move on.
12. As the founder, I want the visual design to support the state transitions instead of making an overloaded screen look finished, so that polish does not hide workflow confusion.

## Implementation Decisions

- Correct / Teach should be modeled as a small state machine, not as a single sidebar section with all controls always present.
- The first state-machine implementation should cover the selected-current-email path before expanded affected-review or unresolved queue flows.
- The primary diagnostic question is whether `Fix this email` fails to mutate state, fails to write through to Gmail, fails to refresh visible context, or reports success unclearly.
- `Rule proposed` should be the conceptual center of the flow. Scope choices come after rule approval.
- Scope choices should use user language:
  - this email
  - future emails like this
  - matching emails Threadwise has already seen
- Existing-email application remains separately confirmed and should not be bundled into the first approval.
- Manual label selection remains secondary/advanced. The founder's natural-language correction drives the proposed rule by default.
- Aesthetic work should follow interaction clarity. For this slice, the UI should prefer plain, stable states over decorative density.
- The existing extension plus local companion architecture remains in place.
- No new Gmail mutation type is introduced.

## Testing Decisions

- Start with tests that characterize the current `Fix this email` behavior before changing the flow.
- Tests should verify visible state transitions, not internal component structure.
- The highest-value test seam is the companion API/rendering contract plus browser simulator acceptance, because this is a user-visible workflow bug.
- Unit tests should prove current-email correction reports exact local and Gmail write outcomes.
- Browser acceptance should prove:
  - a correction moves from `Teaching` to `Rule proposed`
  - approving a rule moves to `Scope confirmation`
  - fixing the current email moves to `Applying` and then `Result`
  - no duplicate apply occurs while pending
  - the result state reports exact scope changed
  - the compact sidebar does not show all scopes and advanced details at once
- Regression tests should preserve the safety boundary that broader existing-email rewrites require explicit confirmation.

## Out of Scope

- Multi-label teaching semantics.
- A standalone rule-management screen.
- Redesigning the daily dashboard.
- Redesigning unsubscribe review.
- New Gmail mutation types.
- Delete, trash, send, reply, broad archive, or autonomous unsubscribe behavior.
- ProtonMail write behavior.
- A full visual redesign of Threadwise branding.
- Rebuilding the whole companion shell outside the Correct / Teach loop.

## Further Notes

The founder's aesthetic concern is valid: imposing a strong look before the interaction model stabilized likely made the UI feel more complete than the workflow deserved. For this next slice, state clarity should lead. Once the state machine feels right in a plain interface, the Threadwise aesthetic can be reapplied deliberately to emphasize state, hierarchy, and trust instead of density.

The PostHog AI wizard is a useful reference for the simpler direction. It leads with one default journey, keeps advanced/audit commands separate from the main path, and presents the tool as a guided flow instead of a dense control surface. Threadwise should borrow that structural lesson for Correct / Teach without copying the developer-tool context or CLI-specific presentation.

Recommended vertical slices:

1. Diagnose and rebuild current-email correction as a state-machine loop.
2. Add accepted-rule future-learning scope after the current email path is trustworthy.
3. Reintroduce existing-email impact as an optional confirmed branch.
4. Reapply the visual system to the simplified states and run screenshot/browser acceptance.
