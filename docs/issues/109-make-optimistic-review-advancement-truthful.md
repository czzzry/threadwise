# Issue 109: Make optimistic review advancement end in truthful completion

Status: Completed; final fresh critic `WIN` at `96/100`
Current as of: 2026-08-10
GitHub issue: `#109`
Parent: `#104`
Depends on: `#106`, `#107`, and `#108` (completed)
Preserves: `#98` immediate next-item transition with background provider writes
Builds on: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Outcome

Make the existing review cadence feel immediate without overstating provider work or queue completion. After an accepted current-email decision, Threadwise advances exactly once to the next eligible item in the current provider-scoped queue while the existing background write continues. The next view keeps a quiet, truthful status for the previous decision until backend activity supersedes it. After the last loaded item, Threadwise shows a checking state and says the review queue is complete only after a fresh provider-scoped state confirms that no reviewable item remains.

This is an interaction and lifecycle-truthfulness slice over the existing `/api/teach-apply`, `/api/handled-review-acknowledge`, provider-write activity, retry, refresh, and loaded-queue paths. It adds no provider route, mailbox capability, classifier call, AI writing, live-provider access, or batch action.

## Product contract

### Optimistic advancement

- Preserve issue `#98`: accepting or changing the current email does not wait for provider-write completion before moving to the next review item.
- A current-email decision receives one client request token tied to its exact provider and message identity. Repeated pointer or keyboard activation for that token cannot submit or advance twice.
- Immediately after the request is accepted locally, exclude that committed identity from candidate navigation even if the loaded queue is stale.
- Choose the next item from the current filtered, active-provider loaded queue in stable order. Never cross providers, silently clear the filter, wrap, or reopen a committed identity.
- If an eligible next item exists, open it exactly once and move focus to its fresh review navigation or primary action without changing Gmail page scroll or the companion's established scroll context.

### Truthful previous-decision status

- Advancing clears per-email correction state but does not erase the lifecycle of the just-accepted decision.
- The next review view may show one compact nonblocking status such as `Previous decision saved · updating Gmail` or the provider-neutral equivalent.
- A successful `/api/teach-apply` response means the local decision was accepted and the provider write was queued; it must not say the provider label or Inbox change is confirmed.
- Existing backend `activity_feed` and `provider_write` state remain authoritative for aggregate provider work: working, done, or retry. Do not invent per-message confirmation from aggregate state.
- Provider-write failure stays visible through existing Activity and retry while review of the next item continues. It must not jump back automatically or silently discard the new current item.
- A late response for an older request may update that request's lifecycle, but it must not render a receipt for the newly selected message, change its decision controls, or steal focus.

### Truthful queue completion

- When no eligible loaded item remains after a committed decision, show `Checking review queue…`; do not immediately say `Review queue complete` and do not synthesize an authoritative empty queue.
- Force one fresh provider-scoped state read. A completion verdict belongs to the refresh generation that followed the last committed identity.
- Show `Review queue complete` only when the fresh state has no active-provider `needs_attention_items`, its provider-scoped daily count is zero, and no relevant async follow-up is still producing a newer queue snapshot.
- If the fresh state contains another eligible item, open or offer that exact item once. Never leave a complete receipt beside a real next item.
- A non-empty query with zero matches remains `No loaded review emails match`; it never becomes a completion check or completion verdict.
- If the fresh read fails or is unavailable, show a retryable checking/error state. Absence of a response is not completion.
- This slice verifies only the current Threadwise review queue. Provider Inbox zero, sync freshness taxonomy, unsynced mail, and broader zero-state semantics remain slice 7.

### Handled review path

- `Looks right · Next` preserves its current explicit acknowledgement route.
- One activation sends one acknowledgement. Failure stays on the current handled item with the existing retry/error path; success advances exactly once using the same eligible-next/completion policy as current-email decisions.
- The handled path remains keyboard reachable and never offers `Next` when no eligible item exists.

## Implementation seams

### Pure progression policy

Add `extensions/gmail_companion/review_progression.js`, loaded before `content.js`, exposing a frozen dependency-free `globalThis.ThreadwiseReviewProgression` module. It should derive serializable results for:

- stable next-eligible selection from provider-scoped items, current identity, query-filtered items, and committed identities
- request-token acceptance and stale-response matching inputs
- completion presentation: `next-available`, `checking`, `filtered-empty`, `verified-complete`, or `retry`
- previous-decision status copy from only known lifecycle/provider facts

The module owns no DOM, routes, timers, provider adapters, subjects, senders, message bodies, or effects.

### Companion integration

In `extensions/gmail_companion/content.js`:

- retain a bounded in-memory record for the newest optimistic decision plus committed identities that still need stale-queue exclusion
- route accept/current-only apply and handled acknowledgement through one single-flight, exact-identity progression boundary
- preserve queue query, provider scope, order, existing J/K behavior, context actions, selected explanation, and explicit queue-exit semantics from issues `#106` through `#108`
- replace immediate final-item completion copy with a refresh-generation-aware checking state
- reconcile fresh `get-state` responses against the exact progression generation before showing verified completion or opening a newly available item
- render the quiet previous-decision lifecycle in existing Recent activity or an equally compact attached status; do not add a dashboard, toast system, global palette, or Gmail toolbar control
- use existing provider-write Activity and retry paths rather than duplicating recovery controls
- keep deterministic test hooks minimal and synthetic-only

### Backend and analytics

Do not add or change provider APIs, the provider-write queue, teaching semantics, retry routes, classifier behavior, or analytics schema. Existing observer-only analytics may continue; no message identity, subject, sender, label text, query, or provider URL may be emitted.

## Acceptance criteria

1. Accepting the first of three review items sends one `/api/teach-apply`, advances once to the second filtered active-provider item, and leaves a truthful nonblocking previous-decision status.
2. Enter on the same primary action cannot create a duplicate request or a second advancement; native button activation remains single-fire.
3. A late successful apply response never renders the first message's receipt, label, or controls on the second message. It says only what local acceptance/background queuing proves.
4. Provider-write working, done, and retry states are surfaced from existing backend activity without blocking the second review or claiming per-message confirmation that is not available.
5. Provider-write failure exposes the existing retry action while the current review identity, queue filter, focus ownership, Gmail scroll, and companion scroll remain stable.
6. J/K, pointer navigation, and progression use only the complete filtered active-provider in-memory queue, keep stable order, and exclude committed identities even when a stale state response still contains them.
7. A filter miss remains filtered-empty and never triggers or displays queue completion.
8. Accepting the last eligible item immediately displays `Checking review queue…`, performs a fresh allowed state read, and displays completion only after the exact fresh generation confirms an empty provider-scoped review queue and zero count.
9. If the completion refresh returns a new eligible item, Threadwise offers or opens it once and displays no complete verdict. If the refresh fails, Threadwise shows a retryable non-complete state.
10. `Looks right · Next` sends one acknowledgement, advances once only on success, stays on the same item on failure, and uses the same checking/verified-complete policy for the last item.
11. Primary actions and completion/retry controls remain reachable by pointer and keyboard at `1280x800`, `756x469`, and `360x800`; no control escapes the companion and the Gmail page remains unaffected.
12. Controlled browser acceptance records exact request order, request tokens/identities, advancement counts, current message identity, focus, Gmail scroll, companion scroll, and completion generation.
13. The validator fails on duplicate or unexpected teaching, handled-acknowledgement, sync, safety, unsubscribe, provider-write, compose, reply, draft, forward, send, or mailbox mutation routes. Only fixture state reads, existing observer analytics, one action route for the tested decision, and an explicitly tested retry are allowed.
14. Node tests cover the pure progression policy. Focused extension checks, prior queue/context/explanation browser validators, and `python3 -m unittest discover -s tests` remain green.
15. A fresh-context critic inspects the real screenshots, source, focus/scroll/request trace, and fixed task pack. When practical, it compares shuffled A/B evidence against the pre-slice `b47e7a8` surface without being told which is the challenger. A failure returns only the single largest bounded gap for the next builder round.

## Fixed critic task pack

1. Accept the first of three items with Enter and prove exactly one request, one advance, and a truthful still-working previous-decision status.
2. Receive provider success while reviewing the next item and distinguish local acceptance, queued/background work, and provider completion without wrong-message UI.
3. Receive provider failure while reviewing the next item, discover retry, and continue without losing the current item or filter.
4. Review inside a filter with pointer and J/K, then reach zero matches without any false completion claim.
5. Accept the final item, distinguish checking from verified complete, then repeat with a refresh that adds a new item and prove no nonexistent `Next` or false complete verdict.
6. Complete and fail `Looks right · Next` keyboard-only, proving one acknowledgement, exact advancement, and truthful last-item completion.

## Expected files

- `extensions/gmail_companion/review_progression.js` (new)
- `extensions/gmail_companion/manifest.json`
- `extensions/gmail_companion/content.js`
- `tests/gmail_companion_review_progression_test.js` (new)
- `tests/test_gmail_companion_ui.py`
- `scripts/validate_threadwise_review_progression_cdp.mjs` (new)

The builder may narrow this set when an existing seam proves behavior more directly. It may not broaden the slice into backend/provider architecture, new routes, batch mutation, sync taxonomy, or separate inbox UI.

## Hard boundaries

- preserve the approved Threadwise logo
- remain a Gmail/Proton overlay; no separate inbox or replacement email client
- no AI email writing, compose, draft, reply, forward, send, or auto-response
- no live inbox, private email, credentials, OAuth, provider sync trigger, new provider route, provider adapter change, mailbox capability, service, or dependency
- preserve the shared provider-neutral workflow; Gmail is only the controlled synthetic acceptance host
- preserve issue `#98` optimistic advancement and the existing bounded/auditable provider-write and retry paths
- do not call aggregate provider activity a per-message confirmation
- do not claim completion from a stale, filtered, failed, missing, or locally synthesized empty queue

## Implementation checkpoint

The bounded implementation is complete on `codex/threadwise-gauntlet` and passed the controlled synthetic gates. It preserves immediate optimistic advancement, adds exact-identity duplicate protection, keeps a truthful previous-decision lifecycle visible on the next item, and requires a fresh provider-scoped state before declaring the review queue complete.

Every direct and chained late-response boundary now validates a captured live-host anchor before it can mutate UI or lifecycle state. The anchor covers provider, message, thread, page URL, and host route. This protects teach success and failure, handled acknowledgement success and failure, transport-failure reconciliation, and completion refreshes.

The final fresh-context critic scored the complete slice `96/100` versus an estimated `~70/100` baseline and declared `WIN`. Five controlled host-navigation races proved unchanged new-message UI, controls, lifecycle, receipts, errors, focus, and nonzero Gmail/companion scroll; they also proved no duplicate reads or stale analytics and safe release of the old action flight.

Validation passed with `42/42` contained dedicated screenshots, zero forbidden routes, `121/121` focused extension tests, `797/797` repository tests, and all prior queue-navigation, contextual-action, and selected-explanation browser validators. No live inbox, private email, OAuth, provider mutation, AI writing, logo, or overlay-architecture boundary changed.

Per the founder's instruction, the Gauntlet stops after this slice. Do not begin slice 6 until the founder explicitly resumes it.
