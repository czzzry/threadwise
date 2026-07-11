# Async Threadwise Extension Resources

## Knowledge

- External: `https://posthog.com/docs/product-analytics/funnels`
  Use for: how PostHog funnels represent ordered product flows, conversion, drop-off, and time to convert.
- External: `https://posthog.com/docs/product-analytics/trends/overview`
  Use for: event counts, comparisons, property breakdowns, and monitoring change over time.
- External: `https://posthog.com/docs/product-analytics/dashboards`
  Use for: operating saved insights together as a recurring product dashboard.
- External: `https://posthog.com/docs/product-analytics/capture-events`
  Use for: PostHog's event and property capture model.
- Local: `docs/analytics/tracking-plan.md`
  Use for: the exact nine Threadwise events, their properties, and which runtime emits them.
- Local: `posthog/threadwise-dashboard.json`
  Use for: the five dashboard insights currently installed in PostHog.
- Local: `src/product_analytics.py`
  Use for: the enforced event vocabulary, environment controls, and Python SDK boundary.
- Local: `extensions/gmail_companion/analytics.js`
  Use for: the frontend review lifecycle and what the extension currently records.

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

## Wisdom (Communities)

- Deferred for now.
  Use for: later external perspective, once the internal architecture is fluent enough that outside discussion will be high-signal instead of confusing.

## Gaps

- We do not yet have a curated external reading list for browser extension UX latency, async state-machine design, or queue/job architectures.
- When this teaching workspace expands, add a small set of high-trust external resources instead of relying on generic internet takes.
