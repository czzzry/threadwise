# Issue 107: Add a contextual action panel to the companion

Status: Completed; third fresh critic WIN at 94/100
Current as of: 2026-08-09
GitHub issue: `#107`
Parent: `#104`
Depends on: `#106` (completed)
Builds on: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Outcome

Give the current Threadwise object one compact, Raycast-style entry point for secondary actions. Keep the state’s single primary action visible. Keep the one-click correction visible in review and handled-receipt states. Move only safe, already-existing, state-valid secondary actions into a short panel inside the provider companion.

This is an interaction-hierarchy slice, not a new capability layer. It adds no provider API, action, write path, Gmail toolbar, global command palette, or mailbox search.

## Completion evidence

- A frozen, dependency-free policy derives at most four allowlisted secondary actions from the exact workspace state; actionless states render no trigger.
- Primary actions and one-click `Change label` / `Change` corrections remain inline. Displaced actions reuse their existing `data-ea-action` handlers or safe Activity link.
- A root-scoped `.` shortcut opens the menu only from a non-editable Threadwise target. Roving arrows, Home/End, Enter/Space, and Escape are menu-scoped; closed-panel J/K behavior remains intact.
- Every rerender increments an action generation. A deliberately reattached stale item is rejected without state change or request.
- The menu is a root-level non-flow popover, so opening, roving, closing, explaining `Why`, and a keyboard-only state transition preserve nonzero Gmail-page scroll `180` and companion scroll `72`.
- Collision-aware placement avoids visible primary and correction controls. At `756x469` and `360x800`, the menu has zero intersection with Accept and Change label; the correction center remains hit-testable and enters the existing change state exactly once.
- Controlled acceptance captures 30 real screenshots, records 27 allowed state-read/analytics requests, and reports zero unexpected routes.
- Independent critics: round one `78/100` for incomplete continuity evidence; round two `83/100` for short-viewport correction collision; round three **WIN at `94/100`**, approximately `+24` over baseline, six of six tasks, and no hard gate.
- Focused Node/browser checks pass; the repo-wide suite passes `795/795` tests.

Handoff: `docs/handoff/2026-08-09-threadwise-gauntlet-contextual-actions.md`

## Exact action policy

The action list is derived from the resolved workspace mode and explicit state flags. It is allowlisted, ordered, capped at four items, and rebuilt on every render. If the exact current state has no valid secondary action, the `Actions` trigger is absent.

| Exact state | Keep inline | Contextual panel |
| --- | --- | --- |
| `review` | Accept/apply suggestion; `Change label` | `Open email in <provider>`; `Back to queue` only during a queue preview |
| `handled-receipt` | `Looks right · Next`; `Change` | `Open email`; `Why` / `Hide why` |
| `future-learning` | `Save future rule` | `Not now` |
| `current-apply-error` | `Retry` | `Edit` |
| `current-receipt` / `partial-receipt` | `Next email` or truthful completion | `Teach future emails` when the provider change succeeded; `Back to Home` only when the queue is complete; `Open Activity` only for a failed receipt |
| `change` | `Preview change` | `Cancel` |
| `preview` | `Apply change` | `Edit` |
| `teach-preview` / `teach-scope` | Current scope/apply/confirm controls and one-click scope choices | `Open email` and/or `Keep discussing` / `Edit` only when the corresponding existing action is valid in that exact state |
| `safety-preview` / `safety-error` | Existing explicit safety confirmation or retry | `Back` |
| `blocked` | Existing retry/check/sync action | No panel unless a separately rendered, non-mutating existing handoff is present; do not invent one |
| `home`, `understanding`, onboarding, loading, applying, success-only receipts, minimized | Existing state UI | No panel |

The builder may narrow this matrix when the real render proves an action is not present or not state-safe. It may not broaden the matrix without a product decision. `Ask LLM to review this`, scope choices, amendment decisions, affected-email review, and other controls embedded in progressive explanation remain where they are; this slice does not turn the panel into a catch-all.

## Interaction contract

- Render one quiet `Actions` trigger only when the current policy returns at least one item. Include a compact shortcut hint, but do not add a permanent toolbar.
- Use `.` as the panel-open shortcut only while focus is already inside the Threadwise root and the target is not editable/native interactive. Do not listen on `document` or `window` and do not intercept Gmail’s `.` behavior outside Threadwise.
- On pointer or keyboard open, focus the first enabled menu item with `preventScroll`. The panel uses `role="menu"`; items use `role="menuitem"` and roving `tabindex`.
- While open, Arrow Up/Down and Home/End move through enabled items without scrolling the host. Enter or Space invokes exactly one current item. Escape closes the panel and restores focus to the trigger with `preventScroll`.
- The open panel gets first priority over the queue key classifier. J/K must not change queue items while the panel is open. When closed, issue `#106` queue J/K, Enter, and Escape behavior remains unchanged.
- Re-render, selected-message change, workspace-mode change, explicit Home, minimize, or loss of the owning action set closes and invalidates the panel. No menu item may survive by referencing hidden or detached DOM.
- Panel execution uses the same existing `data-ea-action` handler or exact safe link destination that the displaced visible control used. Do not synthesize a provider request and do not execute by clicking a hidden stale element.
- The trigger and items meet the existing 44px pointer target policy. The panel must remain inside the companion at `360px`, compact desktop, and short viewport sizes.

## Implementation seams

### Pure action-policy module

Add `extensions/gmail_companion/context_actions.js`, loaded before `content.js`, and expose a frozen `globalThis.ThreadwiseContextActions` module. It should remain dependency-free and cover:

- a frozen action descriptor allowlist (`id`, compact label, existing `data-ea-action` or safe-link kind)
- derivation and ordering from workspace mode plus narrow boolean state flags
- a maximum of four unique, enabled secondary actions
- editable/native-interactive target detection for the panel-open shortcut
- deterministic menu key classification and next-index calculation

It must not know sender, subject, message/thread identity, raw label text, provider URLs, or backend routes.

### Companion integration

In `extensions/gmail_companion/content.js`:

- add explicit open/active-index/restore-focus state and reset it at every invalidation boundary
- render the trigger and menu after the current-state markup has established the policy inputs
- remove only the visible controls listed in the matrix from their current locations; keep primary and correction controls inline
- use current menu-item markup with the existing action IDs so `handlePanelClick` remains the execution authority
- handle panel keys before the queue classifier and leave all closed-panel queue behavior intact
- preserve page and companion scroll during open, traversal, close, execution, and rerender
- expose only minimal deterministic test hooks if the synthetic fixture cannot otherwise enter all required modes

Do not refactor provider adapters, backend state, or write routes.

### Analytics

Analytics is optional in this slice. If instrumented, use the existing observer-only path and only low-cardinality `workspace_mode`, allowlisted `action_id`, and `entry_method`. Never emit sender, subject, query, label text, message/thread ID, email address, draft content, or provider URL. Analytics failure must remain non-blocking.

## Acceptance criteria

1. Review keeps one visible primary action and one-click `Change label`; `Open email` appears once in the panel and queue `Back` appears only for a real queue preview.
2. Handled receipt keeps `Looks right · Next` and `Change` inline; `Open email` and `Why` appear only in the panel and execute the existing behavior once.
3. Teaching, correction, safety, blocked, and receipt fixtures match the matrix with no stale, destructive, or provider-inapplicable entry.
4. Loading, applying, onboarding, Home, minimized, and actionless blocked states render no trigger or hidden menu.
5. `.` opens only from the non-editable Threadwise root. Gmail, textarea, input, select, button, link, summary, and contenteditable targets retain native behavior.
6. Pointer open and keyboard open focus the first item; Arrow Up/Down and Home/End rove; Enter/Space single-fire; Escape closes and restores trigger focus.
7. While the panel is open, its key handling wins over queue J/K. Once closed, queue J/K, Previous/Next, primary Enter, and retreat Escape behave as in issue `#106`.
8. A state or selected-message rerender invalidates the old action set; detached or stale items cannot be executed.
9. Nonzero Gmail-page scroll and companion-content scroll remain unchanged across open, roving, close, and a state-changing action.
10. `role`, accessible label, focus order, `aria-expanded`, menu-item semantics, 44px targets, contrast, and reduced-motion behavior are verified.
11. Synthetic browser acceptance captures real pixels for review, queue preview, actionless blocked, teaching preview/scope, and receipt at `1280x800`, `756x469`, and `360x800` without host displacement or overflow.
12. Acceptance records every request and fails on unexpected sync, teaching apply, safety apply, unsubscribe, handled acknowledgement, provider write, reply, compose, draft, or send paths.
13. Node tests cover the pure policy and key reducer. Focused extension suites and the repo-wide `python3 -m unittest discover -s tests` suite remain green.
14. A fresh-context critic inspects actual screenshots, focus/scroll/request traces, and the source policy against the fixed Gauntlet rubric. A failure returns only the largest bounded gap for the next builder round.

## Fixed critic task pack

1. Find and open the valid secondary action for a selected review email without losing the current message.
2. Correct a suggested label in one click without opening the action panel.
3. Enter a queue preview, open/close the panel, then navigate J/K without wrong-message movement.
4. Open `Why` on a handled receipt and return focus without host scroll.
5. Inspect a teaching scope and a failed/blocked state; identify only actions valid for each exact state.
6. Complete the panel path keyboard-only, then change context and prove stale actions are gone.

## Expected files

- `extensions/gmail_companion/context_actions.js` (new)
- `extensions/gmail_companion/manifest.json`
- `extensions/gmail_companion/content.js`
- `tests/gmail_companion_context_actions_test.js` (new)
- `scripts/validate_threadwise_context_actions_cdp.mjs` (new)
- analytics files/tests only if optional instrumentation is added

## Hard boundaries

- preserve the approved Threadwise logo
- remain a Gmail/Proton overlay; no separate inbox or global command palette
- no AI email writing, compose, draft, reply, forward, send, or auto-response
- no new mailbox action, provider endpoint, service, dependency, credential, live inbox access, or mutation
- no destructive email action moved behind a less explicit confirmation path
- keep the implementation shared/provider-neutral; Gmail is only the controlled synthetic acceptance host
