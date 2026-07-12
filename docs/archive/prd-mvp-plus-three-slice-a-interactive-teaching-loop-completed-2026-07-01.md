# PRD

Status: Completed bounded-slice PRD
Current as of: 2026-07-01
Builds on: `docs/v2-alignment.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, and founder feedback captured through the Gmail companion feedback tool
Supersedes as current planning focus: `docs/archive/prd-mvp-plus-two-gmail-daily-usefulness-completed-2026-07-01.md`
Release target: MVP+3 Gmail sidebar interactive teaching loop
GitHub issue: `#27`

This PRD describes completed MVP+3 Slice A for Threadwise: make the Gmail companion sidebar genuinely interactive before doing the next visual shell polish pass.

## Problem Statement

Threadwise now has a Gmail companion sidebar, daily dashboard, Needs attention reporting, product-triggered Gmail checks, local usage tracking, startup helper, and local founder feedback capture.

The founder's first live testing pass exposed a deeper product problem: too much of Threadwise still feels like a static report beside Gmail, not an interactive inbox companion.

The founder expects to use Gmail as the main workspace:

1. Open Gmail.
2. Scan `EA/...` labels such as `EA/Spam`, `EA/LowValue`, and `EA/NeedsAttention`.
3. Open a suspiciously misclassified email.
4. See what Threadwise decided and why.
5. Correct Threadwise in place.
6. Approve exactly what changes now, what changes for similar existing emails, and what becomes a future rule.

The current product misses that expectation in several ways:

- The `Correct / Teach` path is not consistently visible where the founder needs it.
- Agent View can show a selected email and classification, but does not yet feel like the control surface for correction.
- Dashboard and sidebar counts look clickable, but often do nothing.
- Lists of emails do not reliably route the founder into Gmail or a correction flow.
- "What changed today" lacks a clear ordering model.
- Dashboard email lists can feel inert because full correction is not available there and navigation back to Gmail is weak.
- The sidebar shell has blocking usability problems such as scroll reachability, but broader visual polish should not distract from making the core interaction real.

The core problem is:

> Can Threadwise become an inbox-native teaching companion, where opening a Gmail message shows the current `EA/...` decision, explains the likely reason, and gives the founder an always-visible way to ask why or correct the agent with controlled follow-through?

## Solution

Build a Gmail sidebar interactive teaching loop centered on the currently selected Gmail email.

When the founder opens an email in Gmail, Threadwise should show:

- the selected email identity
- its current `EA/...` label and human-readable status
- a short, honest explanation of why it was likely classified that way
- an always-visible text box that accepts either explanation questions or correction instructions
- a pending correction session when the founder teaches Threadwise

The correction session should translate natural language feedback into concrete, separately confirmed options:

- relabel this email now
- review and apply the correction to similar existing emails
- save a future rule
- cancel or refine the interpretation

Threadwise should make the difference between those options explicit.

For similar existing emails, the first version should estimate affected messages only from stored Threadwise data using conservative signals such as sender/domain, existing `EA/...` label, and subject/category similarity. The affected count must be reviewable before application. First version review can be "review all, then apply all or cancel"; checkbox-level per-email selection is out of scope.

The product target is synergy between Gmail and Threadwise:

- Gmail remains the review surface.
- Threadwise remains the reasoning and control surface.
- Clicking affected emails, metric counts, or dashboard rows should route the founder toward Gmail/sidebar review rather than creating a second competing correction workspace.

Dashboard and summary lists should therefore become useful navigation surfaces:

- Today metrics should open matching lists in Threadwise and ideally trigger Gmail search/filter when feasible.
- "What changed today" should group items by outcome/action, then sort by recency within groups.
- Dashboard rows should expose minimal `Open in Gmail` actions where rows already exist.
- Full teaching/correction stays in the Gmail sidebar for this slice.

Blocking shell fixes may be included only where they are required for the teaching loop to be usable, especially scroll reachability and keeping the correction box visible. Full shell polish belongs to the next slice.

## User Stories

1. As the founder, I want Threadwise to become an interactive Gmail companion, so that it helps me while I work in my inbox.
2. As the founder, I want to open an email in Gmail and have Threadwise update to that selected email, so that I can inspect the exact message I am judging.
3. As the founder, I want Threadwise to show the concrete `EA/...` label for the selected email, so that I understand how it has organized Gmail.
4. As the founder, I want Threadwise to also show the human meaning of the `EA/...` label, so that labels remain understandable while still being concrete.
5. As the founder, I want to see a short explanation of why the selected email was likely labeled that way, so that I can quickly decide whether the classification makes sense.
6. As the founder, I want reconstructed explanations to be honest, so that Threadwise does not pretend it has exact original reasoning when it does not.
7. As the founder, I want a future upgrade noted for storing original classification rationales, so that later explanations can use first-class decision evidence.
8. As the founder, I want the correction text box always visible in Agent View for a selected email, so that I do not have to hunt for `Correct / Teach`.
9. As the founder, I want the same text box to support "why did you do this?" and "change this," so that I do not need separate chat and correction modes.
10. As the founder, I want to speak naturally when correcting Threadwise, so that I can say "this is an account email I need" instead of choosing from rigid controls first.
11. As the founder, I want Threadwise to map my natural-language correction to a concrete label change before acting, so that I can confirm the intended `EA/...` move.
12. As the founder, I want Threadwise to ideate narrowly with me when I am unsure where an email belongs, so that unclear corrections can become useful decisions.
13. As the founder, I want a correction response to propose the current-email relabel, so that the immediate mistake can be fixed.
14. As the founder, I want a correction response to propose a future rule, so that the agent can improve on later runs.
15. As the founder, I want a correction response to estimate similar existing emails affected, so that I understand whether this is one email or a broader pattern.
16. As the founder, I want Threadwise to tell me the difference between relabeling this email, applying to similar existing emails, and saving a future rule, so that I do not accidentally approve the wrong scope.
17. As the founder, I want current-email relabeling to happen immediately after confirmation, so that the correction loop feels real.
18. As the founder, I want broader existing-email application to require review and confirmation, so that Threadwise does not silently rewrite many labels.
19. As the founder, I want saving a future rule to be separately confirmed, so that one correction does not silently become policy.
20. As the founder, I want future rules to affect future runs by default, so that saving a rule is not confused with changing existing Gmail state.
21. As the founder, I want applying to similar existing emails to be a separate action, so that existing-message mutation remains explicit.
22. As the founder, I want affected existing-email counts to be based on stored Threadwise data for now, so that the first version avoids broad live Gmail scanning.
23. As the founder, I want similar-email estimates to be conservative, so that Threadwise does not invent wide impact from vague semantic similarity.
24. As the founder, I want to click an affected count and review the matching emails, so that I can inspect what would change before approving.
25. As the founder, I want the first version of affected-email review to be apply-all-or-cancel, so that I get safety without checkbox complexity.
26. As the founder, I want Gmail and Threadwise to stay in sync while reviewing affected emails, so that Gmail remains my primary email surface.
27. As the founder, I want Threadwise to preserve an active correction session while I navigate Gmail, so that clicking one affected email does not lose the broader rule review.
28. As the founder, I want the active correction session pinned until I apply, cancel, or refine it, so that I can review context without losing the decision.
29. As the founder, I want plain-English future rules shown first, so that I understand what I am approving.
30. As the founder, I want an expandable structured rule, so that I can audit the concrete interpretation when space allows.
31. As the founder, I want Threadwise to keep using visible `EA/...` labels in its UI, so that the product supports my goal that all emails eventually land in an `EA/...` category.
32. As the founder, I want taxonomy friction captured without creating labels automatically, so that recurring category problems can be reviewed later without cluttering Gmail now.
33. As the founder, I want GitHub/PR/commit-style taxonomy friction noted as likely future pressure, so that ProtonMail/GitHub categories can be considered later.
34. As the founder, I want Agent View to show a prompt plus Today summary when no email is selected, so that the default state teaches the workflow without showing stale context.
35. As the founder, I want Today metric tiles to be clickable, so that `processed`, `auto-handled`, and `kept visible` counts open useful review lists.
36. As the founder, I want metric clicks to use Gmail as the target review surface where feasible, so that Threadwise and Gmail work together.
37. As the founder, I want a sidebar-only list/filter to be acceptable as the first version when Gmail search integration is awkward, so that the UI stops feeling dead.
38. As the founder, I want "What changed today" grouped by action or outcome, so that I understand why emails appear there.
39. As the founder, I want recency sorting inside each "What changed today" group, so that the grouped lists are still easy to scan.
40. As the founder, I want "What changed today" items to be clickable, so that I can inspect the related email or label outcome.
41. As the founder, I want dashboard email rows to have `Open in Gmail`, so that the dashboard becomes a review launcher instead of an inert list.
42. As the founder, I want full correction to stay in the Gmail sidebar for this slice, so that there is one primary teaching surface.
43. As the founder, I want the daily dashboard to avoid becoming a second full correction workspace, so that the product model stays simple.
44. As the founder, I want blocking sidebar scroll problems fixed as part of this slice, so that I can always reach the teaching controls.
45. As the founder, I want broader shell polish handled after the interactive core, so that visual cleanup does not delay the main workflow.
46. As the founder, I want the always-visible feedback note tool to remain available, so that I can keep capturing testing observations with context.
47. As a future agent, I want this PRD to distinguish selected email state from active correction session state, so that navigation does not accidentally discard pending decisions.
48. As a future agent, I want this PRD to separate current-email relabel, existing-email application, and future-rule save, so that implementation preserves user control.
49. As a future agent, I want implementation issues to be vertical slices, so that each completed slice is demoable in the Gmail companion.

## Implementation Decisions

- MVP+3 Slice A prioritizes interaction over polish.
- The primary surface is the Gmail companion sidebar.
- Gmail remains the main email review surface.
- Threadwise remains the reasoning, explanation, and control surface.
- The selected Gmail email and the active correction session are separate state concepts.
- Selected email state can change as the founder navigates Gmail.
- Active correction session state should stay pinned until the founder applies, cancels, or refines it.
- Agent View should show the selected email identity, current `EA/...` label, human-readable status, likely reason, and always-visible input.
- `EA/...` labels are first-class user-facing concepts, not hidden backend implementation details.
- Human-readable status should supplement, not replace, the concrete Gmail label.
- Explanations are reconstructed for now and should be worded as likely reasons.
- Future upgrade candidate: store original classification rationales at classification time.
- One visible text box handles both explanation questions and correction instructions.
- Natural-language corrections are mapped to concrete proposed label/status moves before confirmation.
- If the user is unclear, Threadwise may offer a small set of plausible label/status options.
- A valid correction proposal includes:
  - current label/status
  - proposed new label/status
  - plain-English future rule
  - expandable structured rule
  - estimated affected existing-email count
  - separate confirmations for current email, affected existing emails, and future rule
- Current-email relabel may happen immediately after explicit confirmation.
- Applying changes to similar existing emails requires affected-list review and confirmation.
- Saving future rules requires separate confirmation.
- Saved future rules affect future runs by default.
- Applying to existing emails is separate from saving a future rule.
- Similar existing-email estimates use stored Threadwise data only for the first version.
- Similar existing-email matching should be conservative, using signals such as sender/domain, current label/category, and obvious subject patterns.
- LLM semantic similarity may help explain or draft the rule, but must not be the sole basis for wide affected-count claims in the first version.
- First version affected-email review is apply-all-or-cancel; per-email checkbox selection is out of scope.
- Clicking affected counts should show the affected emails in the sidebar and ideally route Gmail to a search/filter view when feasible.
- Today metric tiles should be clickable.
- Metric clicks should update the sidebar list at minimum and can route Gmail to search/filter when reliable.
- "What changed today" should group by action/outcome, with recency inside each group.
- Dashboard lists should be actionable as navigation/review launchers.
- Dashboard rows should include `Open in Gmail` where the needed link/search information exists.
- Full correction/teaching should not be duplicated in the dashboard for this slice.
- When no Gmail email is selected, Agent View should prompt the founder to open an email and show Today summary below.
- Blocking scroll/layout issues may be fixed in this slice only where they affect the teaching loop.
- Full shell polish is deferred to Slice B.
- New `EA/...` label creation is out of scope.
- Taxonomy friction should be captured as future-review input, not acted on automatically.
- Delete, trash, broad archive, send, reply, unsubscribe execution changes, and broad autonomous Gmail actions remain out of scope.

## Testing Decisions

- Good tests should prove user-visible behavior at the highest practical seam.
- Existing Gmail companion UI tests should remain the main regression anchor for sidebar behavior.
- Existing dashboard/server tests should remain the main regression anchor for dashboard navigation changes.
- Selected-email tests should prove Agent View renders the concrete `EA/...` label, human-readable status, likely reason, and visible input.
- Empty-state tests should prove Agent View prompts the founder to open an email and keeps Today summary available below.
- Correction-proposal tests should use fake model/rule clients and prove natural-language input yields separate proposed actions.
- Confirmation tests should prove current-email relabel, affected-existing-email application, and future-rule save are distinct operations.
- Affected-count tests should prove estimates come from stored Threadwise data and conservative matching.
- Active-session tests should prove Gmail selected-email changes do not discard a pending correction session.
- Metric/list tests should prove sidebar counts and "What changed today" items are clickable and produce useful review state.
- Dashboard tests should prove existing email rows expose `Open in Gmail` or an equivalent navigation action where data exists.
- Safety tests should prove no delete, trash, send, reply, broad archive, unsubscribe, or unconfirmed multi-email mutation is introduced.
- No default test should call live Gmail or the live OpenAI API.

## Out of Scope

- Full visual shell polish.
- Logo-only minimized mode.
- Missing logo/mark polish unless it blocks the teaching loop.
- Technical footer cleanup unless it blocks the teaching loop.
- Polished daily-run error rendering.
- Full dashboard teaching/correction.
- Per-email checkbox selection for affected-email review.
- Live Gmail scanning for affected-count estimates.
- New `EA/...` label creation.
- Original classification rationale storage.
- ProtonMail behavior changes.
- AI OS integration.
- Native Gmail DOM-perfect selection.
- Full installer, menubar app, or packaged delivery model.
- Delete, trash, broad archive, send, reply, or broad autonomous Gmail actions.

## Further Notes

- The founder explicitly chose Slice A before Slice B: interactive Gmail sidebar first, shell polish second.
- MVP+3 Slice A implementation progress is `issues 8/8 => MVP+3 Slice A = done`.
- GitHub parent issue `#27` is closed.
- Published MVP+3 Slice A issue briefs:
  - `#28` Selected Email Agent View - complete
  - `#29` Clickable Sidebar Review Surfaces - complete
  - `#30` Dashboard Review Launcher - complete
  - `#31` Blocking Sidebar Usability Fixes - complete
  - `#32` Correction Proposal Session - complete
  - `#33` Confirm Current-Email Relabel - complete
  - `#34` Similar Existing Email Review - complete
  - `#35` Save Future Rule Separately - complete
- Parallelization plan:
  - Batch 1: `#28` and `#31` can run in parallel.
  - Batch 2 after `#28`: `#29`, `#30`, and `#32` can run in parallel if agents coordinate through Agent View selected-email state.
  - Batch 3 after `#32`: `#33`, `#34`, and `#35` can run in parallel if agents coordinate through the correction proposal session contract.
- The founder expects `EA/...` labels to become a long-term organizing model for Gmail.
- The founder's concrete example is an email in `EA/Spam` such as "Google Account Closure Notice" that should be corrected to a more important category, with Threadwise proposing both a one-email relabel and a broader future rule.
- The founder wants affected counts to be inspectable before approving broad application.
- The founder wants Gmail/Threadwise synergy: clicking affected emails or review lists should ideally change what Gmail shows on the left while Threadwise preserves the active correction session on the right.
- The dashboard should not become useless; it should act as a review launcher with `Open in Gmail` actions.
- Slice B should follow this PRD and cover scroll polish not already handled, minimized logo-only mode, missing logo, technical footer cleanup, and improved error presentation.
