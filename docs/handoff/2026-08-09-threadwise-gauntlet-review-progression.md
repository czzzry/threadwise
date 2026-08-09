# Threadwise Gauntlet handoff: truthful review progression

Status: Implemented and validated; paused for founder review after fresh critic `PASS_NOT_WIN` at `82/100`
Current as of: 2026-08-09
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
- focused Python extension checks: PASS, `126/126`
- full repository suite: PASS, `797/797`
- dedicated controlled browser validator: PASS
  - `42` screenshots
  - every viewport contained
  - zero forbidden requests
  - stale completion after DOM plus route mutation is discarded
  - exactly one current-context read follows navigation
  - focus and Gmail/companion scroll remain stable
- prior queue navigation, contextual actions, and selected-explanation browser validators: PASS

Synthetic evidence:

- `/private/tmp/threadwise-review-progression/review-progression-trace.json`
- `/private/tmp/threadwise-review-progression/review-next-1280x800.png`
- `/private/tmp/threadwise-review-progression/provider-failure-1280x800.png`
- `/private/tmp/threadwise-review-progression/checking-1280x800.png`
- `/private/tmp/threadwise-review-progression/queue-complete-1280x800.png`

## Critic result

The final separate fresh-context Luna critic inspected the current source diff, real PNGs, controlled trace, tests, and prior validator outputs.

- Verdict: **PASS_NOT_WIN**
- Score: `82/100`
- Estimated baseline: `~70/100`
- Delta: `+12`
- Fixed tasks: `5/6`
- Safety and host-containment gates: clear
- Former response-time completion race: closed
- Blind A/B: not practical because the baseline commit has no matching progression screenshots or trace; the critic compared current pixels, traces, and source directly to the documented baseline

The critic withheld `WIN` because `/api/teach-apply` and `/api/handled-review-acknowledge` callbacks still use cached request/display identities before response-driven UI mutation. A valid same-token response arriving after the real host has navigated may update stale cached UI. The same direct live-host anchor validation now protecting completion-state responses should guard these callbacks.

Secondary visual polish noted by the critic: narrow screenshots expose horizontal overflow, filter-miss copy is duplicated, and handled failures can stack competing status messages. These did not trigger a hard gate, but should be considered after the response boundary is correct.

## Boundaries preserved

- approved logo unchanged
- Gmail/Proton overlay architecture unchanged
- no separate inbox or replacement mail client
- no compose, draft, reply, forward, send, AI writing, or auto-response
- no live inbox, credentials, OAuth, sync trigger, provider adapter change, new route, or external dependency
- all browser acceptance uses synthetic host content and local fixtures

## Resume brief

Do not begin another Gauntlet loop until the founder explicitly resumes it.

When resumed, keep the correction inside issue `#109`:

1. centralize direct current-host anchor validation before every teach-apply and handled-acknowledgement response-driven mutation;
2. add controlled cases for valid same-token success and failure after real DOM plus route navigation;
3. prove stale callbacks schedule no duplicate current-context read, change no new-message controls or lifecycle, and preserve focus and scroll;
4. run the same focused, full, prior-validator, and fresh-critic gates;
5. only after `WIN`, close `#109` and consider triaging slice 6.
