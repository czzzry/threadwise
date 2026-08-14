# Issue 108: Attach truthful explanation and one-click correction to the selected email

Status: Completed; first fresh critic WIN at 87/100
Current as of: 2026-08-09
GitHub issue: `#108`
Parent: `#104`
Depends on: `#107` (completed)
Builds on: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Outcome

Make the current classification understandable at the selected-email seam without turning the companion into an analytics dashboard. In review, show the suggested label, the exact reason this item needs attention, the stored confidence band, and one concise stored rationale next to the email. Keep the single correction entry point visible and one click away. Put secondary evidence behind a compact disclosure. Reuse that explanation in the handled-receipt `Why` path.

This is a truthful presentation slice over existing stored classification artifacts. It adds no classifier call, provider request, mailbox action, AI writing, global chat, or new decision policy.

## Completion evidence

- Selected-email state now exposes only normalized stored rationale, confidence band, canonical near misses, and the existing matched-rule count/provider confirmation facts.
- A frozen, dependency-free presentation policy derives review and handled-`Why` copy without routes, DOM, message identity, or effects.
- Review replaces the generic yellow rationale with one compact selected-email explanation, while `Accept` / `Apply`, `Change label`, and the contextual `Actions` hierarchy remain in their established order.
- Missing confidence and rationale are named explicitly. `write-unconfirmed` names the provider confirmation problem separately from the stored confidence band.
- Evidence is collapsed by default and limited to other labels considered, saved-rule count, and relevant provider confirmation facts; opaque rule IDs never render in this surface.
- Selected-message changes close evidence and replace label, confidence, rationale, and evidence without stale content. Handled-receipt `Why` reuses the same explanation model.
- Controlled browser acceptance captures 18 real screenshots across six states and three viewports, preserves Gmail-page scroll `180` and companion scroll `72`, records 22 allowed state-read/observer requests, and records zero unexpected routes.
- Prior queue and contextual-action browser validators pass after loading the new pure policy module; their existing scroll, focus, collision, and request-denylist evidence remains green.
- Focused Node and Python checks pass. The repo-wide suite passes `797/797` tests.
- The first fresh-context critic declared **WIN at `87/100`**, `+17` over the `~70/100` baseline, with five of six fixed tasks and every hard gate clear.

Handoff: `docs/handoff/2026-08-09-threadwise-gauntlet-selected-email-explanation.md`

## Product contract

### Visible review summary

The review state renders one compact explanation block attached directly to the selected subject/sender and before its actions:

- the current suggestion, or an explicit statement that Threadwise needs the user to choose a label
- a status-specific queue reason:
  - pending suggestion: `Waiting for your review`
  - no suggestion: `Threadwise needs your label`
  - `write-unconfirmed`: `<Provider> has not confirmed this label update`
- the normalized stored uncertainty label: `High confidence`, `Medium confidence`, `Low confidence`, or `Confidence not recorded`
- one concise stored rationale; if none exists, say `No classification rationale was stored for this email`

Never infer a confidence band from the existence of a label, near miss, queue state, matched rule, write result, wording of the rationale, or any other proxy. Provider confirmation and model uncertainty are separate concepts.

Keep `Accept` / `Apply` and `Change label` exactly where they are. `Change label` remains visible and directly hit-testable; it does not move into `Actions` or the evidence disclosure.

### Progressive evidence

Show a quiet native-feeling `Evidence` disclosure only when at least one secondary evidence row exists. It may show:

- other canonical labels actually stored in `near_misses`, presented as `Also considered`
- the count of saved rules actually stored in `matched_teachable_rules`, presented as `Saved rules matched`
- write and Inbox confirmation facts only when they explain a provider-confirmation state

Do not expose opaque rule IDs as primary UI. Do not repeat the subject, sender, suggestion, or visible rationale inside the disclosure. Opening it must not issue a request, move the host page, change the queue item, or change classification state.

### Handled receipt

The existing contextual `Why` action expands the same truthful presentation model for the handled email. It may include the stored confidence and secondary evidence, but it must not replace the exact handling receipt or weaken the visible one-click `Change` correction.

### Missing and stale data

- Unknown or absent confidence is `Confidence not recorded`; it is never promoted to low, medium, or high.
- Missing rationale is named as missing; generic claims about unspecified “signals” are prohibited.
- Unknown near misses, malformed rule entries, and blank strings are omitted.
- Every render derives the explanation from the current `selected_email.message_id`. A selected-message change closes the evidence disclosure and no text from the previous message may survive.
- `write-unconfirmed` is a provider recovery state. It must not say or imply that the classifier was uncertain.

## Implementation seams

### Selected-email state

In `src/gmail_companion_state.py`, extend the existing selected-email details with only normalized stored evidence:

- `confidence_band`: one of `high`, `medium`, `low`, or an empty string
- `near_misses`: unique canonical label IDs in stable order
- retain the existing `matched_rule_count`, `write_status`, and `inbox_status`

Do not add message body, snippet, evidence terms, raw rule objects, confidence scores, or new state reads. Keep provider-neutral naming and preserve existing contract fields.

### Pure presentation policy

Add `extensions/gmail_companion/selected_explanation.js`, loaded before `content.js`, exposing a frozen dependency-free `globalThis.ThreadwiseSelectedExplanation` module. It should derive a serializable presentation model from:

- exact workspace mode
- selected status and provider name
- suggested label / classification
- stored reason
- normalized details listed above

The module owns copy selection, confidence normalization, evidence-row allowlisting, deduplication, and whether the disclosure is available. It must not know routes, DOM nodes, sender, subject, message/thread IDs, provider URLs, or perform effects.

### Companion integration

In `extensions/gmail_companion/content.js`:

- render the compact summary in `review`
- render the same model when handled-receipt `Why` is expanded
- use semantic disclosure controls with keyboard support and honest accessible names
- reset explanation disclosure state at selected-message and workspace invalidation boundaries
- keep the issue `#107` contextual-action hierarchy and issue `#106` queue keyboard ownership unchanged
- preserve page and companion scroll across disclosure open/close and correction entry

Minimal deterministic test hooks are allowed only where the controlled synthetic harness cannot otherwise enter a required state.

### Analytics

Do not add a new analytics event in this slice. Existing observer-only events remain unchanged.

## Acceptance criteria

1. Review with stored high, medium, or low confidence displays exactly that band beside the status-specific queue reason and never a fabricated score.
2. Missing or invalid confidence displays `Confidence not recorded`; missing rationale displays the explicit no-rationale fallback.
3. `write-unconfirmed` names the provider confirmation problem separately and never presents it as low model confidence.
4. The visible summary is compact and attached to the selected email. It does not repeat Gmail metadata or create a dashboard/card stack.
5. Secondary evidence is restricted to canonical near misses, matched-rule count, and relevant provider confirmation facts. It is collapsed by default and contains no raw rule IDs.
6. Opening and closing evidence works by pointer and keyboard, preserves focus and nonzero Gmail/companion scroll, and makes no network request.
7. `Accept` / `Apply` remains the obvious primary action. `Change label` remains visible, 44px, and enters the existing correction flow in one click at `1280x800`, `756x469`, and `360x800`.
8. Handled-receipt `Why` uses the same truthful explanation model while `Looks right · Next`, `Change`, and the exact handling receipt retain their current hierarchy.
9. Switching selected message immediately replaces label, queue reason, confidence, rationale, and evidence; the old disclosure closes and no stale text/action remains.
10. Queue preview Previous/Next and J/K still operate on the current filtered queue; opening explanation never changes the queue cursor.
11. The contextual `Actions` panel remains collision-free and no new global shortcut or Gmail toolbar control appears.
12. Controlled browser acceptance captures real pixels for high-confidence review, low-confidence/no-label review, missing-evidence review, `write-unconfirmed`, queue preview, and handled `Why` at the three target viewports.
13. Acceptance records every request and fails on unexpected classification, sync, teaching apply, safety apply, unsubscribe, handled acknowledgement, provider write, compose, reply, draft, forward, or send paths.
14. Node tests cover the pure explanation policy. Python tests cover selected-email evidence normalization. Focused extension checks and `python3 -m unittest discover -s tests` remain green.
15. A fresh-context critic inspects the real screenshots, source, focus/scroll/request traces, and fixed task pack. When practical, it compares shuffled A/B captures against the pre-slice `49c12fe` surface without being told which is the challenger. A failure returns only the largest bounded gap for the next builder round.

## Fixed critic task pack

1. Identify the suggested label and why the selected email is waiting without opening technical detail.
2. Determine the stored uncertainty, including the missing-confidence case, without mistaking provider recovery for uncertainty.
3. Inspect secondary evidence, close it, and retain selected-message context and scroll.
4. Correct the suggestion in one click at desktop, compact, and narrow widths.
5. Move to a different queue email and prove no prior label, rationale, confidence, or evidence remains.
6. Open handled-receipt `Why`, understand the earlier decision, and complete the path keyboard-only.

## Expected files

- `src/gmail_companion_state.py`
- `extensions/gmail_companion/selected_explanation.js` (new)
- `extensions/gmail_companion/manifest.json`
- `extensions/gmail_companion/content.js`
- `tests/gmail_companion_selected_explanation_test.js` (new)
- `tests/test_gmail_companion_ui.py`
- `scripts/validate_threadwise_selected_explanation_cdp.mjs` (new)

The builder may narrow this set if an existing test seam proves the behavior more directly. It may not broaden the slice into classifier, provider-adapter, teaching, or write-path changes.

## Hard boundaries

- preserve the approved Threadwise logo
- remain a Gmail/Proton overlay; no separate inbox or replacement mail client
- no AI email writing, compose, draft, reply, forward, send, or auto-response
- no new classifier call, mailbox action, provider endpoint, service, dependency, credential, live inbox access, or mutation
- no body/snippet/raw-rule expansion in selected-email state
- keep shared/provider-neutral behavior; Gmail is only the controlled synthetic acceptance host
