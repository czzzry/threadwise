# Threadwise UI Direction: From Rule Workbench to Decision Copilot

Status: Founder-approved implementation direction
Current as of: 2026-07-11
Builds on: `docs/ui-ux-audit/ui-ux-audit.md`, `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md`, and current simulator/browser inspection
Founder approval: Direction A approved for autonomous implementation on 2026-07-11

## Decision summary

The categorical change is not a new color palette. It is a change in what the sidebar is.

Current mental model:

> Threadwise is a compact rule-authoring workbench with inbox, unsubscribe, teaching, scope, and reporting controls visible together.

Recommended mental model:

> Threadwise is a decision copilot that asks one clear question about the current email, applies that decision, and only then offers optional learning or cleanup.

The default sidebar should not ask the founder to design a rule. It should help the founder make the current-email decision. Rule creation, future learning, matching-existing review, unsubscribe cleanup, and daily reporting remain available, but they appear as sequential follow-ups or separate supporting surfaces.

This is a categorical correction to the shipped interaction model, not new product scope. The current PRD already says the compact body should show only the current job and that teaching should replace the body. The implementation drifted into a permanent stack of Agent View, unsubscribe, Correct / Teach, Today, and technical detail. The redesign should restore that single-job contract and make it testable.

## Why the prior simplification still feels complicated

The July 1 audit correctly found that too many jobs were visible together. The later state-machine work made the Correct / Teach sequence more explicit, but it kept `Rule proposed` as the conceptual center and ended in three equally visible scope actions:

- `Fix email`
- `Fix + future`
- `Fix + inbox`

That is internally precise but still asks the founder to understand Threadwise implementation scopes. The UI feels like a control panel because the product is exposing its capability model rather than the founder's immediate job.

Current browser evidence from the safe simulator:

1. The selected-email state simultaneously shows judgment, unsubscribe, Correct / Teach, and Today.
2. Auto-handled emails still show a full correction textarea and subscription controls by default.
3. The correction input can contain a request for `promotions` while the hidden/preselected target remains `job-related`; preview then proposes `EA/Work`. The visible input and effective structured state can disagree.
4. Scope confirmation presents three compound choices with similar weight.
5. The dashboard repeats emails across Provider-side changes, Needs Attention, Kept Visible, Auto-Handled, and Recent Queue.
6. The unsubscribe page repeats the same long audited-action explanation on every candidate card.
7. The root companion harness currently fails before full rendering because copied interaction helpers/state are missing. The `/simulator` route works, confirming implementation drift between parallel UI paths.
8. Current tests largely prove that feature strings exist. They do not prove that mutually exclusive jobs are absent from the wrong state.

## Product principles

These rules are binding for the proposed redesign.

1. One active job per sidebar state.
2. One visually primary action per state.
3. Current-email action happens before optional future learning.
4. Current-only is the default scope; the founder should not need to choose it.
5. Broader existing-email mutation is never bundled into the primary action.
6. Natural-language input and structured label state must never silently disagree.
7. Reporting belongs in Home/dashboard, not below every selected email.
8. Unsubscribe is a contextual secondary action, not a permanent card.
9. Technical details remain available behind `Why` or `Details`, not visible by default.
10. The simulator and extension must demonstrate the same user-visible state contract.
11. State exclusivity is a behavior, not a CSS convention: inactive jobs must not be rendered into the active workspace body.

## Target companion state model

| State | User question | Required visible content | Primary action | Secondary actions | Must not be visible |
| --- | --- | --- | --- | --- | --- |
| Minimized | Is Threadwise available? | Brand icon, optional count badge | Open | None | Email details, metrics |
| Home | What needs me? | `N emails need review`, latest-run summary line | Review next | View activity, run sync when stale | Selected-email form, full report |
| Understanding | Is Threadwise working? | Subject, sender, short progress state | None | Minimize | Old judgment, teaching controls |
| Review | Is this suggested label right? | Subject, sender, `Threadwise suggests <label>`, one reason | Accept `<label>` | Change label, Why, contextual Unsubscribe | Textarea, daily metrics, scope choices |
| Change | What should this email be? | Visible label picker/search, optional instruction field | Preview change | Cancel | Hidden preselected label, future/inbox scope |
| Preview | Is this current-email change correct? | `Change this email to <label>`, concise effect | Apply change | Edit | Three compound scope buttons |
| Receipt | What happened? | Exact current-email outcome | Next email | Teach future emails, review similar existing emails when meaningful | Original form, duplicate apply |
| Future learning | Should Threadwise remember this? | Plain-English future rule and evidence strength | Save future rule | Edit rule, Not now | Existing-email mutation bundled in save |
| Existing review | Which existing matches should change? | Count, dense rows, include/exclude, pinned rule | Apply to included | Back/cancel | Fat cards, silent broadening |
| Auto-handled | What did Threadwise do? | One-line receipt: label + inbox handling | None | Change, Why | Open correction form, Today report |
| Blocked | What failed and what can I do? | Exact failed step and preserved successful steps | Retry failed step | Details | Generic failure or repeat of successful work |

## Exact first-pass copy

### Review

- Eyebrow: `Needs your review`
- Suggestion line: `Threadwise suggests Work`
- Reason: one sentence, maximum 160 characters before `Why`
- Primary button: `Accept Work`
- Secondary button: `Change label`
- Contextual quiet action when available: `Unsubscribe…`

Do not show both `Uncategorized` and `Needs attention` as unexplained peer pills. The state heading already communicates that review is needed.

### Change

- Heading: `What should this email be?`
- Label field: always visible in this state
- Optional text label: `Anything Threadwise should remember? (optional)`
- Primary button: `Preview change`
- Quiet action: `Cancel`

If natural language implies a different label than the selected label, block preview and show:

> Your note sounds like Promotions, but Work is selected. Choose which one you mean.

Never silently choose one source over the other.

### Preview

- Heading: `Change this email to Promotions`
- Effect line: `This updates the current email only.`
- Primary button: `Apply change`
- Secondary action: `Edit`

Do not show future or existing-email scope until the current-email action succeeds.

### Receipt

- Success heading: `Changed to Promotions`
- Outcome lines:
  - `Gmail label updated.`
  - `Removed from Inbox.` or `Kept in Inbox.`
- Primary button when a queue exists: `Next email`
- Optional follow-up: `Teach Threadwise for future emails`
- Optional follow-up when matches exist: `Review 3 similar emails`

### Auto-handled

- Heading: `<label> · Auto-handled`
- Receipt: `Threadwise applied Newsletter and kept this email in Inbox.`
- Quiet actions: `Change`, `Why`

### Home

- Heading when work exists: `3 emails need your review`
- Primary button: `Review next`
- Summary line: `12 processed · 2 auto-handled · 7 kept visible`
- Quiet links: `Activity`, `Subscription cleanup`

## Visual hierarchy specification

Preserve Threadwise's warm paper identity, brand mark, dark ink, amber, and green. Reduce the visual pressure.

### Tokens

- Page/panel background: `#FFFDF7`
- Warm secondary surface: `#F5EFE2`
- Teaching/attention tint: `#FFF4DD`
- Safe action: `#2EB67D`
- Ink: `#241812`
- Muted text: `#6B6255`
- Hairline: `rgba(36, 24, 18, 0.16)`
- Error tint: `#FDE8E6`
- Card radius: `14px`
- Control radius: `10px`
- Pill radius: `999px`
- Sidebar padding: `16px`
- Standard vertical gap: `12px`
- Primary control minimum height: `44px`

### Weight rules

- The sidebar shell may keep a `2px` ink outline.
- Content cards use a `1px` hairline or background contrast, not repeated heavy outlines.
- No nested card uses a hard black drop shadow.
- Only the primary action may use the raised ink-shadow treatment.
- Secondary buttons are flat outline/soft-fill controls.
- Tertiary actions are text links.
- Use at most one uppercase eyebrow in the first viewport.
- Use the system sans-serif stack for product content. The brand wordmark may retain its display treatment.
- Remove the tagline from the expanded 420px sidebar header; keep it on marketing surfaces.

### Narrow-panel rules

- Target width: `420px`.
- No horizontal scrolling at `360px`, `390px`, or `420px` viewport widths.
- Sender and subject wrap or truncate without overlapping controls.
- Primary actions stack when two controls cannot retain 44px height and readable labels.
- The first complete decision should fit within approximately `640px` vertical space at 420px width.

## Surface-specific recommendations

### Gmail companion — first implementation priority

Replace the permanent vertical stack with a single state body. Header stays fixed; state body changes. Home/reporting is not rendered beneath a selected email. Unsubscribe becomes a quiet contextual action that opens its own compact confirmation state or queues cleanup.

### Daily dashboard — later independent slice

Keep the top summary. Then show only:

1. `Needs review` — actionable emails.
2. `Activity` — one chronological, deduplicated list of actions Threadwise took.
3. `Subscriptions` — queued cleanup summary.

Move `Run Gmail check` into the header/action area. Remove the standalone `Recent Queue` section. An email must not appear in multiple default sections. Detailed label distribution and attention diagnostics belong behind expandable details.

### Unsubscribe review — later independent slice

Replace wide repeated cards with a compact selectable list or table:

- selection
- subscription name/sender
- evidence count
- execution readiness
- latest attempt

Show the audited-action explanation once at page level. Add a sticky batch action bar after at least one item is selected. Long sender addresses must wrap without colliding with adjacent columns.

## Implementation sequence

### Slice 0 — Repair the visual acceptance surface

Goal: make the root companion harness render without injected browser fixes and prevent immediate drift.

Required behavior:

- Declare/provide every state/helper used by the harness renderer.
- Add a browser acceptance test that fails on any uncaught error.
- Confirm the default selected-email, Today, and inbox fixture list render together.

Do not redesign the UI in this slice.

### Slice 1 — Introduce the single-job companion shell

Goal: make Home and Selected Email mutually exclusive bodies under one header.

Required behavior:

- Introduce one top-level companion mode/state that chooses the complete workspace body. Teaching substates may remain nested beneath it.
- Home appears only when no email is selected or the user explicitly opens Home.
- Selected-email states do not render Today metrics below them.
- Auto-handled state is a receipt with `Change` and `Why`, not an open form.
- Needs-review state renders one suggestion decision.
- Render one workspace body per state; do not preserve the permanent stack by adding more `<details>` elements or CSS-only hiding.

Preserve API contracts and Gmail mutation behavior.

### Slice 2 — Current-email decision flow

Goal: implement `Review → Change → Preview → Applying → Receipt`.

Required behavior:

- Accept uses the visible suggested label.
- Change exposes the selected label explicitly.
- Natural-language/label disagreement blocks preview.
- Apply changes the current email only.
- Receipt reports local/Gmail/inbox outcomes exactly.

### Slice 3 — Optional learning after receipt

Goal: move future learning and existing-email review out of the primary correction decision.

Required behavior:

- Future rule is offered only after current-email success or by an explicit advanced path.
- Existing-email review is a separate action and confirmation.
- The three compound buttons `Fix email`, `Fix + future`, `Fix + inbox` are removed from the primary UI.
- Existing backend modes may remain as adapter commands; do not remove supported behavior.

### Slice 4 — Reapply the visual system

Goal: normalize hierarchy after state behavior is stable.

Required behavior:

- Use the tokens and weight rules above.
- One raised primary action per state.
- Screenshot coverage at 360px, 420px, and expanded review width.
- No layout or console warnings.

### Slice 5 — Dashboard and unsubscribe cleanup

Treat dashboard deduplication and unsubscribe list redesign as separate issues. Do not combine them with the companion state rewrite.

## Acceptance screenshot matrix

A weaker implementation model must capture and compare all of these states with synthetic fixtures:

1. Home with review work.
2. Home with no review work.
3. Understanding.
4. Needs-review suggestion.
5. Auto-handled receipt.
6. Change label.
7. Natural-language/selected-label conflict.
8. Current-email preview.
9. Applying/duplicate-submit-disabled.
10. Complete success receipt.
11. Label-applied/inbox-removal-failed partial receipt.
12. Retry success without repeated label write.
13. Future-rule suggestion after receipt.
14. Minimized.
15. Unsynced with one recovery action.

Each capture must be generated from the simulator or browser acceptance harness. Do not implement from a screenshot alone; the screenshot is evidence after the state contract passes.

## Test contract

- Test user-visible transitions through public companion state/API behavior.
- Do not assert large source-code strings as the primary proof of UX.
- Browser tests must fail on uncaught exceptions, stale state after selection changes, horizontal overflow, clipped primary actions, or duplicate apply.
- At `420px × 900px`, the normal Review state has no internal vertical scroll and all of its decision content is visible.
- Every interactive state has at most one visible element marked `data-tw-primary-action`.
- Entering Change, Preview, or Future learning proves that Agent View detail, unsubscribe controls, Today metrics, and unrelated notes are absent from the workspace body.
- Preserve product analytics events at equivalent user moments even if DOM structure changes.
- Preserve Gmail write, bounded inbox removal, retry, and candidate-evaluation behavior.
- Run the relevant browser acceptance flow and the full Python test suite.

## Files and ownership

Likely implementation surfaces:

- `extensions/gmail_companion/content.js` — real Gmail DOM adapter and current rendering/event wiring.
- `src/gmail_companion_state.py` — product-facing selected-email and UI-state vocabulary.
- `src/gmail_companion_ui.py` — companion API plus simulator/harness and supporting pages.
- `tests/test_gmail_companion_ui.py` — API/visible contract tests.
- `scripts/validate_gmail_companion_simulator_cdp.mjs` — browser-state acceptance.

Do not independently redesign both extension and simulator by copying markup twice. Establish one shared interaction-state vocabulary first. A follow-up architecture slice may extract shared JavaScript transitions; until then, every state/copy change must have parity acceptance across both adapters.

## Explicit non-goals

- Do not redesign Gmail itself.
- Do not change label taxonomy or classifier semantics.
- Do not add chat history as the primary interface.
- Do not add more chips, metrics, tabs, or explanation cards to solve density.
- Do not introduce a design framework solely for this redesign.
- Do not expose raw candidate-eval or PostHog data in the companion.
- Do not remove auditability, explicit broader-change confirmation, or retry visibility.
- Do not rebuild the dashboard and unsubscribe page in the same slice as the companion.

## Weak-model implementation prompt

Use the following as the top-level instruction after this direction is approved:

> Implement one bounded Threadwise companion slice from `docs/ui-ux-audit/2026-07-11-decision-copilot-direction.md`. Read `AGENTS.md`, `CONTEXT.md`, the full UI direction, the current companion state contract, and the relevant current issue before editing. Do not redesign from screenshots alone. Preserve Gmail mutation, analytics, eval, and safety behavior. Implement only the named slice using red-green-refactor: first add one browser-visible failing behavior test, then the smallest implementation, then repeat. The target mental model is one active job and one primary action per state. Current-email action comes before optional future learning; existing-email changes remain separately confirmed. Verify extension/simulator parity, no console errors, no horizontal overflow at 360/390/420px, exact partial-outcome copy, analytics event continuity, the affected browser acceptance flow, and the full Python test suite. Do not opportunistically change other surfaces.

## Founder decision recorded

The founder approved this categorical statement on 2026-07-11:

> The compact Threadwise sidebar is a current-email decision copilot. It is not the daily dashboard, unsubscribe manager, or rule workbench. Those capabilities appear only when the current decision calls for them.
