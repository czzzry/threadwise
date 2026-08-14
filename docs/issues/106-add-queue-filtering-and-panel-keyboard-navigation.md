# Issue 106: Add queue-local filtering and panel-scoped keyboard navigation

Status: Completed; Gauntlet WIN at 85/100
Current as of: 2026-08-09
GitHub issue: `#106`
Parent: `#104`
Depends on: `#105` (completed)
Builds on: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Outcome

Make the already-loaded Threadwise review queue fast to find and traverse inside the existing provider-aware companion. The selected Gmail email remains the primary context. A compact queue finder appears only on Threadwise Home, and queue-preview navigation appears only after the user explicitly enters that queue context.

This slice is local interaction only: it must not search Gmail, fetch another page, index mailbox content, run a provider sync, or mutate mail.

## Completion evidence

- Home discloses a compact finder for the already-loaded active-provider review queue; the provider-selected first view remains finder-free.
- Case-insensitive sender, subject, displayed classification/label, and status filtering preserves active-provider order, excludes explicit cross-provider items, reports `N of M`, distinguishes filter misses, and clears in one action.
- Queue previews use the existing `manualPreviewContext` path, expose pointer Previous/Next controls, and support panel-scoped J/K without wrapping or accepting stale identities.
- Pointer entry and each async queue rerender hand focus to the fresh navigation surface only while the queue remains active and the user has not moved focus elsewhere.
- The real CDP trace sends J/K to `activeElement`, preserves nonzero Gmail-page scroll `180` and companion scroll `72` through pointer and keyboard rerenders, and proves inputs and outside-host events remain untouched.
- Explicit Home/reopen boundaries clear query, finder/help, preview, and pending-focus state; `Back to queue` preserves the active filtered context.
- Controlled acceptance passes at `1280x800`, `756x469`, and `360x800`, records every request, and reports zero forbidden provider sync, teaching, safety, unsubscribe, handled-acknowledgement, write, reply, or send requests.
- Independent critic rounds: `82/100` for missing real focus handoff; not-WIN for vacuous zero-scroll proof; not-WIN for stale queue state after explicit exit; fresh round-four critic WIN at `85/100` versus the documented `~70/100` baseline, with five of six tasks won and no hard gate triggered.
- Focused Node and browser checks pass; the repo-wide suite passes `795/795` tests.

Handoff: `docs/handoff/2026-08-09-threadwise-gauntlet-queue-navigation.md`

## Exact interaction contract

### Queue finder

- Home keeps `Review next` as the primary action.
- When the active provider has review items, Home adds one quiet `Find in review queue` disclosure. The selected-email first view does not show the finder.
- Opening the disclosure shows one search input, `N of M` count, compact matching result cards in the original queue order, a one-action clear affordance, and progressively disclosed keyboard help.
- Matching is case-insensitive and local across `sender`, `subject`, displayed classification/label fields, `status_label`, and `status`.
- Only `lastHarnessState.needs_attention_items` participates. An item carrying a different explicit `provider` value is excluded defensively; an item without a provider inherits the already provider-scoped queue.
- Empty query restores the original active-provider order.
- A filter miss says that no *loaded review emails match* and offers `Clear filter`; it must not imply Inbox zero, queue completion, stale sync, or provider unavailability.
- Result rendering may remain capped for panel performance, but the UI must disclose the cap and keyboard traversal must use the complete filtered in-memory result set.

### Queue navigation

- Entering a result or `Review next` creates the existing `manualPreviewContext`; no new preview architecture is introduced.
- A queue preview shows compact position and navigation context without exposing the search control over the selected-email judgment.
- `J` / `K` move to the next / previous still-present item in the filtered active-provider set. Navigation never wraps silently.
- Visible Previous / Next controls provide the same behavior for pointer and assistive-technology users.
- Mapped `Enter` activates exactly one visible, enabled `[data-tw-primary-action]` when focus is inside Threadwise and the event did not originate on a native interactive or editable control. Native controls keep native keyboard behavior, preventing double invocation.
- `Escape` retreats one safe level in this order: close keyboard help; clear a non-empty queue query; return from a queue preview to Home with the queue finder preserved; minimize only from top-level Threadwise Home or a provider-selected first view.
- Keyboard handling is attached to the Threadwise root, not `document` or `window`. It ignores input, textarea, select, button, link, summary, `[contenteditable]`, and any target outside the root as appropriate to the mapped key.
- No command palette or Gmail-wide shortcut is added.

## Implementation seams

### New pure interaction module

Add `extensions/gmail_companion/queue_navigation.js`, loaded before `content.js`, with dependency-free functions for:

- query normalization and searchable text construction
- defensive active-provider filtering that preserves source order
- current/next/previous item lookup by stable `message_id`
- editable/native-interactive target detection
- panel-scoped key-command classification

Expose the frozen module as `globalThis.ThreadwiseQueueNavigation` and unit-test it directly in Node.

### Companion integration

In `extensions/gmail_companion/content.js`:

- add explicit queue UI state (`query`, finder/help disclosure, current queue identity)
- render the compact Home finder and honest count/no-results/cap states
- render queue-preview position and Previous / Next controls
- route result clicks and navigation through a single stale-safe lookup against the current queue
- add one root-scoped `keydown` listener and remove it on teardown if teardown support is introduced
- preserve queue state across a queue preview and reset it when the active provider changes or the user explicitly leaves the queue flow
- expose only the minimum state/test hooks needed for deterministic acceptance

Do not change provider adapters, background provider APIs, backend state contracts, or write routes.

### Privacy-safe product analytics

Use the existing observer-only analytics path for explicit queue-filter commits and navigation, if instrumented. Only low-cardinality outcome/count buckets and navigation direction/origin are allowed. Never emit the query, sender, subject, label text, message/thread ID, email address, or provider URL. Analytics failure must remain non-blocking.

## Acceptance criteria

1. The companion still mounts minimized and never auto-expands.
2. The queue finder is absent from the provider-selected first view and appears only after explicit Home/queue context.
3. Sender, subject, classification/label, and status queries match case-insensitively within the loaded active-provider `needs_attention_items` only.
4. Clearing restores the original queue order and safe current identity.
5. A filter miss is visually and semantically distinct from an empty, complete, stale, unavailable, or unsynced queue.
6. J/K and Previous/Next never cross providers, never wrap silently, and refuse an item removed from the current queue.
7. Mapped Enter invokes one visible enabled primary Threadwise action without duplicating native button activation.
8. Escape follows the defined retreat stack and never triggers a mailbox action.
9. Gmail typing, Gmail shortcuts, Threadwise editable fields, and events outside the root cause no Threadwise navigation.
10. Keyboard help is compact, contextual, and progressively disclosed.
11. Synthetic browser acceptance runs at compact desktop, `756x469`, and `360x800`; the companion remains contained and does not displace the host.
12. Synthetic acceptance records every request and fails on provider sync, teaching apply, safety apply, unsubscribe execution, handled acknowledgement, or any other write/API path not needed to read the existing fixture state.
13. Node tests cover the pure module; focused Python/Node extension suites and repo-wide unit tests remain green.
14. A fresh-context critic inspects real pixels and keyboard traces against the fixed Gauntlet rubric. A failure returns only the largest bounded gap for the next builder round.

## Expected files

- `extensions/gmail_companion/manifest.json`
- `extensions/gmail_companion/queue_navigation.js` (new)
- `extensions/gmail_companion/content.js`
- `extensions/gmail_companion/analytics.js` and `src/product_analytics.py` only if the privacy-safe events above are added
- `tests/gmail_companion_queue_navigation_test.js` (new)
- focused analytics tests only if analytics changes
- `scripts/validate_threadwise_queue_navigation_cdp.mjs` (new)

## Hard boundaries

- preserve the approved Threadwise logo
- remain a Gmail/Proton overlay; no separate inbox
- no AI email writing, compose, draft, reply, forward, send, or auto-response
- no live inbox, credentials, OAuth, provider search, sync trigger, mailbox mutation, or new service/dependency
- no raw query or email-derived value in analytics, logs, screenshots intended for publication, or test failure output
- keep the implementation shared/provider-neutral; Gmail is only the first synthetic acceptance host
