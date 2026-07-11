# Case Study: Privacy-First Product Analytics for Threadwise

Status: Implemented; no user-impact claims
Current as of: 2026-07-10

## Objective

Threadwise needed enough product analytics to understand whether its human-in-the-loop review flow reaches a real Gmail outcome. The integration deliberately stops at nine events covering activation, proposal decisions, rule scope, authoritative label writes, retries, and batch completion.

## Tracking design

The taxonomy uses static object-verb names with low-cardinality properties. Interaction events answer what the user chose. Write events answer what Gmail actually did. Separating those sources prevents a button click from being mistaken for a successful provider mutation.

The activation funnel follows the product's central value path: open Threadwise, enter review, decide, and complete a Gmail label write. Supporting charts explain decision mix, reliability, retry recovery, and time to first successful write.

## Architecture decisions

Threadwise is a plain Manifest V3 extension backed by a local Python HTTP service, not a bundled React application. The extension therefore uses a small local analytics transport rather than loading a remote SDK into Gmail. The MV3 service worker maintains an anonymous installation ID and forwards allowlisted events to the companion. The companion owns the only PostHog SDK wrapper and also emits the authoritative write outcomes.

This design keeps analytics out of the Gmail DOM, avoids extension CSP and remote-code issues, correlates frontend and backend events with one anonymous ID, and preserves the existing local-first architecture.

## Privacy controls

The analytics module is deny-by-default: each event has exact required and optional properties, enums constrain every descriptive string, counts are bucketed, and raw errors become safe categories. Additional checks reject sensitive key names, email-like strings, authorization-like strings, and representative free-form rule text. Person profiles, identify calls, autocapture, session replay, exception capture, and GeoIP enrichment are disabled.

Production analytics is opt-in. Development and test environments remain offline unless explicit synthetic mode is enabled. Synthetic events are fixed, contain no email data, and are excluded from the production dashboard.

## Testing and validation

Python tests cover event emission, required fields, prohibited names, representative sensitive values, environment gating, synthetic-only behavior, stable anonymous IDs, authoritative write outcomes, and retry outcomes. A Node contract test executes the extension transport and proves that the local review key never appears in emitted events. Existing extension syntax and repository tests remain part of the validation gate.

The safe validation command reads no inbox data:

```bash
python3 scripts/validate_posthog_analytics.py
```

Adding `--send` requires explicit synthetic environment variables and sends only the fixed synthetic fixture.

## Dashboard

The dashboard is managed through the official PostHog CLI from a source-controlled JSON definition. Every insight filters to `environment=production`. The time-to-first-write metric is implemented as PostHog's time-to-convert funnel rather than a custom timestamp pipeline.

## Trade-offs

- The local companion must be running for extension interaction events to reach PostHog. This matches Threadwise's current operating model and fails safely without affecting the product flow.
- A strict schema makes adding properties slower, but it gives privacy review a single auditable boundary.
- Counts are bucketed, reducing precision in exchange for lower cardinality and less accidental disclosure.
- This first slice does not track experiments, flags, surveys, replays, pageviews, or generic exceptions.

## Lessons learned

For browser extensions handling private content, analytics architecture is primarily a data-boundary problem. Capturing provider outcomes at the execution point, sharing only an anonymous installation ID across contexts, and making unsafe payloads structurally unrepresentable produced a smaller and more trustworthy integration than general web autocapture would have.

Any events used during validation are synthetic. No adoption, conversion, retention, reliability, or business-impact result is claimed.
