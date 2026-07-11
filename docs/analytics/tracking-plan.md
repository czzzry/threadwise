# Threadwise Product Analytics Tracking Plan

Status: Current implementation
Current as of: 2026-07-10
Cloud region: PostHog EU Cloud
Workflow version: `gmail-companion-v1`

## Business questions

1. Do people who open Threadwise reach the unresolved review queue and make a decision?
2. Which decisions are approvals, edits, or rejections?
3. Which confirmed rule scopes lead to successful Gmail label writes?
4. How often do authoritative Gmail writes fail, and do retries recover?
5. How long does it take an anonymous installation to reach its first successful label write?

## Event definitions

Every event requires `app_version`, `workflow_version`, and `source`. The Python wrapper rejects unknown events, missing fields, extra fields, invalid enum values, email-like values, authorization-like values, and prohibited property names.

| Event | When | Source of truth | Required event properties |
| --- | --- | --- | --- |
| `extension opened` | The minimized Gmail companion is opened | Extension UI | `surface` |
| `review queue opened` | Needs-attention review is opened | Extension UI | `queue_size_bucket` |
| `email review started` | A selected or queued email enters review | Extension UI | `review_origin`, `queue_size_bucket` |
| `suggestion decision made` | The proposal is approved, edited, or rejected | Extension UI | `decision_type`, `duration_ms` |
| `rule confirmed` | A current, broader-existing, or future scope is confirmed | Extension UI | `rule_scope`, `affected_count_bucket`, `dry_run` |
| `label write completed` | Gmail confirms one or more label writes | Local companion service | `rule_scope`, `write_count_bucket`, `retry_count` |
| `label write failed` | The authoritative Gmail write path reports failure | Local companion service | `rule_scope`, `error_category`, `retry_count` |
| `label write retried` | The retry command completes, fails again, or is blocked | Retry CLI | `rule_scope`, `retry_count`, `retry_outcome`; optional `error_category` |
| `review batch completed` | A non-empty needs-attention queue reaches zero after review | Extension UI | `reviewed_count_bucket`, `duration_ms` |

Allowed properties are deliberately low-cardinality. Counts use `0`, `1`, `2-5`, `6-10`, `11-25`, `26-50`, or `51+`. Error values are categories, never exception strings.

## Identity and context boundaries

- The extension creates one random `tw_anon_<uuid>` value in `chrome.storage.local`.
- The service worker adds it as `X-PostHog-Distinct-Id` when calling the local companion.
- The companion validates and stores the same anonymous value locally so retry outcomes use the same ID.
- No `identify()` call is made and `$process_person_profile` is false.
- Gmail addresses, account IDs, message IDs, and thread IDs are never identity inputs.

The content script contains only a typed, allowlisted event transport. The PostHog SDK runs in the local Python service, not in Gmail, avoiding MV3 remote-code/CSP problems and ensuring no PostHog code inspects the Gmail DOM.

## Prohibited data

Never send email bodies, snippets/previews, subjects, sender or recipient addresses, Gmail message/thread/account IDs, OAuth or authorization data, user-entered rule text, generated/model text, raw exceptions, stack traces, or page URLs. Autocapture, session replay, exception autocapture, GeoIP enrichment, and person profiles are disabled.

## Environment policy

- Production sends only when `THREADWISE_ANALYTICS_ENABLED=true`, `THREADWISE_ENVIRONMENT=production`, and a project token is present.
- Development and test send nothing by default, even if a token is accidentally present.
- Explicit synthetic validation additionally requires `THREADWISE_ANALYTICS_ALLOW_SYNTHETIC=true`; every event is tagged `environment=development` and `synthetic=true`.
- The dashboard filters to `environment=production`, so synthetic validation cannot affect product metrics.

## Dashboard definitions

The source-controlled definition is `posthog/threadwise-dashboard.json` and contains:

1. Activation funnel: `extension opened` → `review queue opened` → `suggestion decision made` → `label write completed`.
2. Approval/edit/reject breakdown by `decision_type`.
3. Successful versus failed label writes.
4. Retry outcomes by `retry_outcome`.
5. Time-to-convert funnel from `extension opened` to `label write completed`.

Apply it with:

```bash
python3 scripts/apply_posthog_dashboard.py
```
