# email-agent

Local email-assistant repo for one-user inbox workflows.

The repo currently supports a live Gmail daily run with bounded write-back, a ProtonMail read-only path, per-inbox daily and weekly reporting, and a local review / unsubscribe / eval workbench.

## 0. Current Docs

If you are trying to understand the current state of the repo rather than its history, read:

- [AGENTS.md](AGENTS.md) for workflow and guardrails
- [CONTEXT.md](CONTEXT.md) for the current stage and doc trust order
- [docs/v2-alignment.md](docs/v2-alignment.md) for current product direction
- [docs/prd.md](docs/prd.md) for the current bounded slice
- [docs/checkpoints/current-operating-model-2026-06-22.md](docs/checkpoints/current-operating-model-2026-06-22.md) for the latest implementation checkpoint
- [docs/v2-issue-map.md](docs/v2-issue-map.md) for candidate next-slice themes only

Historical V1 docs live under [docs/archive/](docs/archive/).

## 1. What This Repo Currently Does

- Gmail: fetch a batch, classify messages, auto-apply current `EA/` labels, remove `INBOX` only for `promotions` and `spam-low-value`, and write a daily report.
- ProtonMail: fetch through Bridge or import a local export, classify into the same provider-aware batch model, and write reports without provider-side mutation.
- Reporting: build daily per-run reports and weekly per-inbox analytical reports from stored artifacts.
- Local workbench: inspect batches, review exceptions in a browser, inventory unsubscribe candidates, execute supported unsubscribes with audit history, and run shadow-label evaluation.

## 2. Quickstart: Current Preferred Workflow

For the earlier Gmail manual-review happy path, see [docs/archive/mvp-happy-path-gmail-manual-review.md](docs/archive/mvp-happy-path-gmail-manual-review.md).

Current Gmail daily workflow:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 50
```

Current ProtonMail read-only daily workflow:

```bash
python3 scripts/daily_live_protonmail_run.py --account-id founder-proton --batch-size 25
```

Generate a weekly per-inbox report from stored daily artifacts:

```bash
python3 scripts/weekly_inbox_report.py --account-id founder-test --storage-dir data/gmail_fetch --end-date 2026-06-20
```

## 3. Gmail Workflow

Preferred command:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 50
```

What it does:

- fetches a fresh Gmail batch
- classifies messages into the current taxonomy
- auto-applies all current suggested `EA/` labels
- removes `INBOX` only for `spam-low-value` and `promotions`
- prints the remaining unlabeled exceptions for manual follow-up
- writes a durable per-run report to `data/gmail_fetch/reports/<batch_id>_daily_report.json`

Lower-level Gmail review and recovery commands remain available under `scripts/` for manual fetch, browser review, explicit label write-back, retries, and batch inspection.

## 4. ProtonMail Workflow

Preferred daily read-only command:

```bash
python3 scripts/daily_live_protonmail_run.py --account-id founder-proton --batch-size 25
```

What it does:

- fetches a fresh ProtonMail batch through Bridge
- classifies messages into the existing provider-aware local batch model
- performs no provider write actions
- prints unlabeled exceptions for manual follow-up
- writes a durable per-run report to `data/gmail_fetch/reports/<batch_id>_daily_report.json`

For the import-based read-only path, ingest a ProtonMail export file with:

```bash
python3 scripts/manual_protonmail_fetch.py --account-id founder-proton --source-path /path/to/proton_export.json
```

Import contract:

- JSON array of message objects
- each message should include `id`, `sender`, `subject`, and `date`
- optional fields: `snippet`, `body`, `mailbox`, `list_unsubscribe`, `precedence`
- only messages with `mailbox: "inbox"` are imported

For the lower-level live Bridge fetch command, use:

```bash
python3 scripts/live_protonmail_fetch.py --account-id founder-proton --batch-size 25
```

Bridge setup contract for this repo:

- Proton Mail Bridge is the supported provider edge for live read-only Proton access
- Bridge requires a paid Proton Mail plan according to Proton's Bridge documentation
- default config path: `data/protonmail_credentials/protonmail_bridge/<account_id>.json`
- expected config fields: `host`, `port`, `username`, `password`, optional `ssl`
- example config: `examples/protonmail_bridge_config.example.json`

## 5. Weekly Reports

Weekly per-inbox analytical report:

```bash
python3 scripts/weekly_inbox_report.py --account-id founder-test --storage-dir data/gmail_fetch --end-date 2026-06-20
```

This writes:

- `data/gmail_fetch/reports/<account_id>_weekly_report_<start>_<end>.json`

The report rolls up stored daily artifacts for one inbox and is meant to summarize trends, category mix, exception rate, and notable changes over the week.

## 6. Local Workbench / Lower-Level Tools

Browser review / workbench:

```bash
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001
```

Other useful lower-level commands:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/retry_live_gmail_failed_writes.py --batch-id founder-test-batch-N
python3 scripts/remove_inbox_for_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-N
python3 scripts/list_local_batches.py
python3 scripts/evaluate_shadow_model_labels.py --help
```

For autonomous handling of a specific stored Gmail batch, use:

```bash
python3 scripts/auto_apply_live_gmail_batch.py --batch-id founder-test-batch-N
```

## 7. Credential / Data Paths

Local private paths used by this repo:

- Gmail credentials: `data/gmail_credentials/`
- Gmail / provider-aware run artifacts: `data/gmail_fetch/`
- ProtonMail Bridge config: `data/protonmail_credentials/protonmail_bridge/<account_id>.json`

Optional OpenAI key for shadow evaluation:

- `EMAIL_AGENT_OPENAI_API_KEY`
- `OPENAI_API_KEY`

If OAuth or token exchange fails with an SSL certificate verification error on a `python.org` macOS Python install, run:

```bash
open "/Applications/Python 3.13/Install Certificates.command"
```

## 8. Safety Notes

- Treat credentials, tokens, Bridge config, and stored inbox artifacts as private local data.
- Gmail mutation is intentionally bounded to current `EA/` label write-back plus `INBOX` removal for `promotions` and `spam-low-value`.
- ProtonMail is read-only in the current operating model.
- Unsubscribe handling is deliberately controlled: build inventory locally, execute only supported cases with audit history, and keep unsupported cases manual.
- The repo does not default to deleting, trashing, or broadly archiving mail.

## 9. Legacy or Lower-Level Commands

Older or more manual commands remain useful for debugging, controlled review, and slice-specific verification:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/retry_live_gmail_failed_writes.py --batch-id founder-test-batch-N
python3 scripts/remove_inbox_for_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/manual_protonmail_fetch.py --account-id founder-proton --source-path /path/to/proton_export.json
python3 scripts/live_protonmail_fetch.py --account-id founder-proton --batch-size 25
python3 scripts/evaluate_shadow_model_labels.py --help
```
