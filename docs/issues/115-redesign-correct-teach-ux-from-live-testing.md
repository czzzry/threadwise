# Redesign Correct / Teach UX from Live Testing

GitHub issue: `#42`

## What to explore

The founder's live testing showed that the current correction flow is still too form-like and too verbose. Even after label inference, the product should likely move toward a simpler intent-first teaching surface with clearer action hierarchy and less explanatory text.

## Acceptance criteria

- [ ] Review the latest founder feedback notes around Komoot/newsletter/spam correction.
- [ ] Propose a simpler correction interaction model.
- [ ] Decide whether the dropdown should be secondary, hidden until needed, or replaced by suggested label chips.
- [ ] Decide how much explanation text belongs in the first visible state versus expandable detail.
- [ ] Break the approved redesign into bounded implementation issues.

## Partial grill decisions saved 2026-07-01

Founder paused the alignment session and asked to resume later. Do not re-ask these unless the founder explicitly wants to revisit them.

- The default teaching flow should be: fix the current email first, then suggest a broader rule if one can be inferred.
- When a broader rule is suggested, Threadwise should check whether that broader rule affects existing emails.
- Broader-rule preview should show count plus a plain-English rule first, with affected email examples behind a `Show affected emails` expander.
- Broader-rule impact should distinguish emails currently visible in Gmail inbox from older stored/archive emails.
- First implementation should use Threadwise's stored Gmail snapshot/inbox status for that split, not live Gmail search.
- Future note: revisit live Gmail confirmation/search later so broader-rule impact can reflect exact current inbox state once the UX is proven.
- Applying the current-email fix should require a distinct action such as `Fix this email`; preview should never mutate Gmail or local state.
- After the current-email fix succeeds, keep a compact broader-rule suggestion visible only when Threadwise has a meaningful candidate. The success state should lead with what happened to this email, then offer `Teach future rule`, `Show affected emails`, and `Dismiss` as follow-up actions.
- When there is no meaningful broader-rule candidate, the success state should briefly say so, e.g. `No broader rule suggested from this note`, instead of silently ending after the current-email fix.
- Broader-rule suggestions and follow-up questions must use the actual email meaning/content, not default to sender-wide rules. Example: if the founder says one Wealthsimple message is `EA/Account`, Threadwise should not propose `all Wealthsimple -> EA/Account` unless the content pattern supports that. It should distinguish account notices from newsletters, promotions, tax docs, security alerts, etc.
- If Threadwise is uncertain about the semantic boundary, it should ask one short clarifying question only when the answer would materially improve the rule. Otherwise it should avoid suggesting a broader rule.
- Broader-rule candidates may be sender + semantic pattern rules or cross-sender semantic rules. The UI must name the rule type clearly. Cross-sender semantic rules are valuable for phishing, jobs/interviews, travel, bills, and urgent attention, but should require stronger evidence and clearer preview than sender-pattern rules.
- A single email can produce a broader-rule suggestion, but it should be graded as tentative unless Threadwise finds matching examples. One email may teach future behavior; it should not rewrite existing mail unless Threadwise can show what will be affected.
- Broader-rule preview should separate `Teach future rule` from `Apply to shown existing emails`. Do not combine future learning and existing-email rewrites into one ambiguous primary action.
- Affected-email preview should show count plus 1-3 representative examples by default, with the full affected list behind `Show all affected emails`.
- Revised affected-email review direction: avoid stuffing the affected list into the sidebar. The sidebar should remain the decision/control surface; Gmail should become the inspection surface where possible. Clicking an impact count such as `Review 14 in Gmail` should update Gmail to the affected subset via search/filter/navigation while Threadwise keeps the pending rule preview pinned. If Gmail cannot express the exact set, Threadwise should explain that and offer the closest search plus a fallback review list.
- When Gmail is showing the affected subset, Threadwise should enter a temporary `reviewing affected emails` mode. The pending rule preview stays pinned while the currently opened affected email can appear underneath. Clicking an affected email should not replace/lose the pending rule context.
- Exiting `reviewing affected emails` mode should be explicit. Show a persistent banner with `Done reviewing`, `Cancel rule`, and `Back to original email`. Applying or canceling the rule exits automatically. Random Gmail navigation should not silently exit the pinned review mode.
- Revised exact affected-list direction after grilling: use a Threadwise-owned affected-email review view as the exact list, with inbox-like rows and include/exclude decisions. Gmail should be used for deep inspection via `Open in Gmail` links. Threadwise remains the source of truth for final affected IDs. Temporary Gmail labels may be a later upgrade, but are not the first implementation path.
- The exact affected-email review list should not be crammed into the small sidebar. It should open a wider Threadwise review view/panel/page with dense inbox-like rows, not fat cards. Sidebar remains the compact entry/control surface.
- Approved shape for the review surface: `Expanded Threadwise review mode`, not a totally separate tab and not a tiny sidebar list. Triggered from the sidebar by `Review N`; Threadwise expands from the right into a wider panel while leaving a small Gmail inbox strip visible on the left for continuity. The panel has dense rows and a clear `Collapse`/`Back to sidebar` action. The pending review session stays active across collapse/expand.
- Excluding an email from a broader-rule affected list should create a durable exception, not merely skip the current apply. The UI should confirm this clearly, e.g. `Exception saved. This rule will not apply to this email/pattern later.`
- Excluding an email is a learning moment. Ideally Threadwise should infer why the excluded email does not belong and suggest a rule amendment/exception. If unclear, it should ask the founder why. Generalized exceptions should not happen silently.
- Excluding an email should not require an explanation. Save the exact-email exception immediately, then optionally ask for a reason or suggest a generalized amendment if Threadwise can infer one.
- If exclusions reveal a clear semantic boundary, Threadwise should suggest revising the pending broader rule before applying it. If the exclusion looks like an isolated edge case, keep the rule unchanged and store exact exceptions.
- After a pending broader rule is revised, Threadwise must recompute the affected list and show the new count/list before any apply action remains enabled.
- `Apply to included` should apply only to exact included IDs, save the future rule, save durable exceptions for excluded IDs/patterns, and report exact counts afterward: emails updated, exceptions saved, future rule saved. The decision should be logged for audit.
- Keep `apply once only` out of the primary flow for now. It adds clutter and conflicts with the goal of teaching Threadwise. Consider it later as an advanced option only if a real use case emerges.
- Correction input should lead with free-form text. Manual label selection should be secondary/expandable because the founder often knows the complaint before knowing the exact EA label. Threadwise should infer the label/rule preview from the note.
- When Threadwise has an obvious likely correction, it may show one or two contextual quick actions above the text box, but the text box should remain available. Avoid many chips/buttons.
- Instructional text before correction input should be almost none. Prefer compact labels and placeholder text; move guidance behind help/advanced disclosure.
- Correction preview should be structured around three compact consequence sections: `This email`, `Future rule`, and `Affected existing emails`, each with clear action buttons for that consequence.
- In a full preview, `Fix this email` should be the visually primary action. `Teach future rule` and `Review affected emails` should be secondary follow-ups until the current email is handled.
- `Fix this email` should not save the future rule automatically. It only updates the current email. Future rule saving should be a distinct follow-up action.
- `Teach future rule` may be used without reviewing/applying affected existing emails. It should explicitly confirm that the future rule was saved and existing affected emails were not changed.
- Approved batch decisions:
  - Wider affected-email review should be an expanded Threadwise review mode, not a separate tab, Gmail search result, modal, or cramped sidebar list.
  - Affected-email rows should be dense inbox-like rows, not cards.
  - Rule amendments from exclusions are proposals only; never silently rewrite the rule.
  - Applying included emails should also save the future rule.
  - `Apply once only` stays out of MVP.
  - Review mode persists while opening Gmail emails for inspection.
  - Raw structured rule details stay hidden by default behind an expander.

## Proposed vertical slices

Published as GitHub child issues `#44`-`#50`.

1. Simplify sidebar correction entry and current-email fix
   - GitHub issue: `#44`
   - Type: AFK
   - Blocked by: none
   - Goal: Make the compact sidebar correction loop free-form-first, low-instruction, and centered on `Fix this email`.
   - Includes: contextual quick actions, secondary manual label selection, three-part preview shell, current-email-only fix, clear no-broader-rule success state.

2. Add semantic future-rule preview and save flow
   - GitHub issue: `#45`
   - Type: AFK
   - Blocked by: slice 1
   - Goal: Propose future rules from the actual email meaning rather than sender alone, and let the founder save future learning without touching existing emails.
   - Includes: rule type labeling, tentative vs matched rule language, one clarifying question only when useful, `Teach future rule` success copy that says existing emails were not changed.

3. Add read-only expanded affected-email review mode
   - GitHub issue: `#46`
   - Type: AFK
   - Blocked by: slice 2
   - Goal: Let the founder inspect the exact affected set in a wider Threadwise-owned view before any broader apply path exists.
   - Includes: `Review N`, expanded right-side panel, Gmail continuity strip, dense rows, collapse/back-to-sidebar, `Open in Gmail`, pinned review session state.

4. Add durable exclusion decisions in affected review
   - GitHub issue: `#47`
   - Type: AFK
   - Blocked by: slice 3
   - Goal: Let the founder exclude affected emails and guarantee the same rule will not hit those excluded emails later.
   - Includes: exact-email exception persistence, visible exception confirmation, optional reason capture, audit trail, no required explanation.

5. Add apply-included flow for reviewed affected emails
   - GitHub issue: `#48`
   - Type: AFK
   - Blocked by: slice 4
   - Goal: Apply the broader rule only to exact included IDs, save the future rule, save durable exceptions, and report exact outcomes.
   - Includes: `Apply to included`, counts for updated emails/exceptions/future rule, disabled stale apply when affected set is outdated, audit logging.

6. Add rule amendment proposals from exclusions
   - GitHub issue: `#49`
   - Type: AFK
   - Blocked by: slice 5
   - Goal: When exclusions reveal a clear boundary, propose a revised rule and recompute affected emails before apply.
   - Includes: proposed amendment, optional clarification when unclear, recompute changed count/list, no silent rule rewrite.

7. Final acceptance and live-testing hardening
   - GitHub issue: `#50`
   - Type: AFK
   - Blocked by: slices 1-6
   - Goal: Validate the full inspect/correct/teach/review/apply loop across simulator and extension harness before closing #42.
   - Includes: browser acceptance coverage, overflow checks, pinned-mode regression checks, final docs/update of #42.

## Current status

Implementation complete across child issues `#44` through `#50` as of 2026-07-02.

The redesign is ready for founder review before closing parent GitHub issue `#42`.

## Validation summary

- Current-email fix and future-rule save are covered by unit tests and simulator acceptance.
- Expanded affected review, row exclusions, `Apply to included`, and amendment proposal visibility are covered by `scripts/validate_gmail_companion_simulator_cdp.mjs`.
- Durable exact exclusions are covered by teaching-loop tests and local artifact registry coverage.
- Full regression suite passed after the final implementation slice.
