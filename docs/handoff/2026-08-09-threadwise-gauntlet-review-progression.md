# Threadwise Gauntlet handoff: truthful review progression

Status: Completed; final fresh critic `WIN` at `96/100`
Current as of: 2026-08-10
Issue: `#109`
Parent: `#104`
Branch: `codex/threadwise-gauntlet`
Starting implementation commit: `d3ac1fb`

## Outcome

Threadwise now advances immediately after a locally accepted review decision while keeping the previous decision's real provider lifecycle visible on the next item. Exact provider, message, and thread identities protect against duplicate submission and stale loaded queues. The last item enters a checking state and cannot become `Review queue complete` until a fresh provider-scoped state reports an explicitly numeric zero and no eligible item.

This remains the existing Gmail/Proton companion overlay. It adds no inbox application, compose/reply/draft/forward/send behavior, AI writing, provider route, provider adapter capability, live inbox access, or mailbox mutation.

## What changed

- `extensions/gmail_companion/review_progression.js`
  - adds a dependency-free policy for exact identities, request tokens, eligible-next selection, previous-decision copy, and completion verdicts
- `extensions/gmail_companion/content.js`
  - adds optimistic single-flight progression for current-email decisions and handled acknowledgements
  - excludes committed identities from stale queues without blocking provider work
  - renders compact working, done, and retry lifecycle states without claiming per-message provider confirmation
  - replaces immediate final-item completion with generation-bound checking, retry, next-available, or verified-complete behavior
  - directly re-samples the host selected context and route before accepting completion-state responses
  - captures the live provider, message, thread, URL, and route for teach and handled flights
  - discards late direct or chained responses before they can mutate a newly navigated host surface
  - invalidates checks on route, DOM, and click context changes; teardown removes listeners and observers
- `extensions/gmail_companion/manifest.json`
  - loads the pure progression policy before the content script
- `tests/gmail_companion_review_progression_test.js`
  - protects identity, next-item, count, async-state, and truthful-copy policy
- `scripts/validate_threadwise_review_progression_cdp.mjs`
  - records real desktop, short, and mobile pixels plus request, focus, scroll, lifecycle, response-boundary, and navigation-race evidence
- the three earlier controlled browser validators now load the progression policy and remain green

## Validation

- Node syntax and pure progression tests: PASS
- `git diff --check`: PASS
- focused Python extension checks: PASS, `121/121`
- full repository suite: PASS, `797/797`
- dedicated controlled browser validator: PASS
  - `42` screenshots
  - every viewport contained
  - zero forbidden requests
  - stale completion after DOM plus route mutation is discarded
  - exactly one current-context read follows navigation
  - focus and Gmail/companion scroll remain stable
  - teach success/failure, handled success/failure, and chained reconciliation responses remain inert after live-host navigation
  - all five navigation races emit no duplicate reads or stale analytics and release their old action flights safely
- prior queue navigation, contextual actions, and selected-explanation browser validators: PASS

Synthetic evidence:

- `/private/tmp/threadwise-review-progression/review-progression-trace.json`
- `/private/tmp/threadwise-review-progression/review-next-1280x800.png`
- `/private/tmp/threadwise-review-progression/provider-failure-1280x800.png`
- `/private/tmp/threadwise-review-progression/checking-1280x800.png`
- `/private/tmp/threadwise-review-progression/queue-complete-1280x800.png`

## Critic result

The final separate fresh-context critic inspected the current source diff, real PNGs, controlled trace, tests, and prior validator outputs.

- Verdict: **WIN**
- Score: `96/100`
- Estimated baseline: `~70/100`
- Delta: `+26`
- Fixed tasks: `6/6`
- Safety and host-containment gates: clear
- Direct and chained response-time host-navigation races: closed
- Blind A/B: not practical because the baseline commit has no matching progression screenshots or trace; the critic compared current pixels, traces, and source directly to the documented baseline

The winning correction centralizes live-host anchor validation and applies it before teach, handled acknowledgement, transport-reconciliation, and completion-refresh response mutations. Controlled success and failure races after real DOM plus route navigation leave the new message's UI, lifecycle, focus, and scroll untouched.

This is a score for issue `#109` behavior, not for Threadwise's whole-product visual design. The broader companion remains visually card-heavy and wordy; that should be handled as a separately approved visual-system and information-architecture slice rather than folded into this behavior fix.

## Boundaries preserved

- approved logo unchanged
- Gmail/Proton overlay architecture unchanged
- no separate inbox or replacement mail client
- no compose, draft, reply, forward, send, AI writing, or auto-response
- no live inbox, credentials, OAuth, sync trigger, provider adapter change, new route, or external dependency
- all browser acceptance uses synthetic host content and local fixtures

## Stop point

Issue `#109` is complete and may close. Its founder pause was satisfied on 2026-08-11: the founder resumed the Gauntlet, approved the Variant C production milestone, and separately authorized Slice 7's truthful read-only Gmail coverage implementation. Keep this slice's live-host anchoring and real-queue progress semantics locked while implementing coverage.
