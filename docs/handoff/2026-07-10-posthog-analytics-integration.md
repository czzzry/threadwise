# Handoff: PostHog Analytics Integration

Status: Implemented and locally validated
Current as of: 2026-07-10

## Source of truth

- Event and privacy contract: `docs/analytics/tracking-plan.md`
- Architecture case study: `docs/analytics/case-study.md`
- Dashboard definition: `posthog/threadwise-dashboard.json`
- Runtime wrapper: `src/product_analytics.py`

## What changed

Threadwise now has nine allowlisted product events spanning companion activation, review, suggestion decisions, rule scope, authoritative Gmail write results, retries, and batch completion. The MV3 service worker maintains one anonymous installation ID. Frontend events pass through the local companion, while Gmail write and retry outcomes originate from their Python execution paths.

The Python wrapper rejects unknown events and properties, sensitive key names and representative sensitive values. It disables person profiles, exception autocapture, and GeoIP. Development and test stay offline by default; explicit synthetic validation is isolated from production metrics.

## Dashboard evidence

The authenticated PostHog EU project contains the pinned `Threadwise Product Analytics` dashboard, ID `809649`, with five executable insights:

- activation funnel
- approval/edit/reject breakdown
- successful versus failed writes
- retry outcomes
- time to first successful label write

All five filter to `environment=production`. The fixed synthetic fixture was sent as `environment=development`, `synthetic=true`, and PostHog schema discovery confirmed all nine event names.

## Validation

- `env -u OPENAI_API_KEY -u THREADWISE_TEACHING_MODEL python3 -m unittest discover -s tests` — 589 tests passed.
- `python3 scripts/validate_posthog_analytics.py` — 9 synthetic contracts validated offline.
- Python compile checks passed for changed Python modules and scripts.
- Node syntax checks passed for the analytics transport, content script, and MV3 service worker.
- PostHog CLI dry-run validated the dashboard and five insight definitions.
- Reapplying the dashboard command is idempotent and found dashboard `809649`.

An unrestricted shell that exposes an optional live teaching-model key can make four pre-existing teaching-loop tests call the model and become nondeterministic. The repository/CI-safe command above explicitly removes those optional variables; the standard sandboxed suite also passed.

## Remaining manual step

Before collecting real usage, put the PostHog project token in local `.env`, source it, set `THREADWISE_ANALYTICS_ENABLED=true` and `THREADWISE_ENVIRONMENT=production`, then restart the local companion. Do not commit `.env`. No real email was processed and no real analytics were sent during this implementation.
