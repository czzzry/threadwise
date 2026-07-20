# Async Threadwise Extension Resources

## Knowledge

- Local: `docs/prd-async-threadwise-extension-2026-07-10.md`
  Use for: the product problem, the approved scope, and the vertical-slice sequence behind this redesign.
- Local: `docs/issues/133-add-async-selected-email-understanding-states.md`
  Use for: why the selected email now moves through `reading -> understanding -> ready`.
- Local: `docs/issues/134-add-async-action-lifecycle-for-teach-and-fix.md`
  Use for: why teach/fix now shows `accepted -> working -> result` instead of one opaque wait.
- Local: `docs/issues/135-move-slower-follow-up-work-off-the-main-sidebar-path.md`
  Use for: the fast-path vs slower-follow-up architectural split.
- Local: `docs/issues/136-add-recent-activity-and-retry-surface-for-async-operations.md`
  Use for: the compact activity model and retry visibility.
- Local: `src/gmail_companion_state.py`
  Use for: the current-email understanding state contract and the state timing thresholds.
- Local: `src/gmail_companion_ui.py`
  Use for: the companion-side architecture, async follow-up model, and sidebar contract.
- Local: `src/teaching_loop.py`
  Use for: the teaching/apply backend behavior and the reusable rule data produced during teach/apply.
- Local: `extensions/gmail_companion/content.js`
  Use for: the product-facing state machine, recent activity surface, and extension behavior the founder actually sees.
- Local: `tests/test_gmail_companion_ui.py`
  Use for: the executable proof of the architecture and the intended product semantics.
- Local: `src/product_analytics.py`
  Use for: the authoritative event schema, privacy boundary, anonymous identity, PostHog client configuration, and fail-open behavior.
- Local: `extensions/gmail_companion/analytics.js`
  Use for: the extension-side manual event vocabulary, count bucketing, timing, and first privacy check.
- Local: `extensions/gmail_companion/background.js`
  Use for: the anonymous installation ID and the extension-to-local-companion analytics transport.
- Local: `scripts/run_gmail_companion_simulator.py`
  Use for: the controlled simulator boundary, including its deliberate disabling of live Gmail checks and write-through.
- Local: `scripts/live_gmail_companion_acceptance_cdp.mjs`
  Use for: the automated live-Gmail actions and evidence checks exercised by the acceptance harness.
- Local: `docs/handoff/2026-06-29-live-gmail-acceptance-harness-and-trusted-types-hardening.md`
  Use for: the authoritative distinction between live harness evidence and normal installed-extension parity.
- External primary: [PostHog — Capturing events](https://posthog.com/docs/product-analytics/capture-events)
  Use for: the upstream model of custom events, event properties, and distinct IDs that Threadwise deliberately narrows.
- External primary: [PostHog — Python SDK](https://posthog.com/docs/libraries/python)
  Use for: the official SDK mechanism used by Threadwise's local companion.

## Wisdom (Communities)

- Deferred for now.
  Use for: later external perspective, once the internal architecture is fluent enough that outside discussion will be high-signal instead of confusing.

## Gaps

- We do not yet have a curated external reading list for browser extension UX latency, async state-machine design, or queue/job architectures. PostHog sources now cover the observability slice.
- When this teaching workspace expands, add a small set of high-trust external resources instead of relying on generic internet takes.
