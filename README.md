# email-agent

Starter repository for the `email-agent` project.

## Structure

- `src/` application source code
- `tests/` automated tests
- `docs/` project notes and documentation
- `scripts/` local helper scripts
- `examples/` sample inputs, outputs, or experiments
- `data/` local project data artifacts
- `.github/workflows/` CI workflows

## Current guide

For the current proven local Gmail MVP workflow, see:

- [docs/mvp-happy-path-usage-guide.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/mvp-happy-path-usage-guide.md)

Current preferred daily workflow:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 50
```

This command:

- fetches a fresh Gmail batch
- auto-applies all current suggested `EA/` labels
- removes `INBOX` for `spam-low-value` and `promotions`
- prints the remaining unlabeled exceptions for manual follow-up
- writes a durable per-run report to `data/gmail_fetch/reports/<batch_id>_daily_report.json`

For the current ProtonMail daily read-only workflow:

```bash
python3 scripts/daily_live_protonmail_run.py --account-id founder-proton --batch-size 25
```

This command:

- fetches a fresh ProtonMail batch through Bridge
- classifies messages into the existing local batch model
- performs no provider write actions
- prints unlabeled exceptions for manual follow-up
- writes a durable per-run report to `data/gmail_fetch/reports/<batch_id>_daily_report.json`

To generate a weekly per-inbox analytical report from stored daily reports:

```bash
python3 scripts/weekly_inbox_report.py --account-id founder-test --storage-dir data/gmail_fetch --end-date 2026-06-20
```

This writes:

- `data/gmail_fetch/reports/<account_id>_weekly_report_<start>_<end>.json`

For the current bounded ProtonMail read-only slice, import a ProtonMail export file into the same local batch model with:

```bash
python3 scripts/manual_protonmail_fetch.py --account-id founder-proton --source-path /path/to/proton_export.json
```

Current ProtonMail import contract:

- JSON array of message objects
- each message should include `id`, `sender`, `subject`, and `date`
- optional fields: `snippet`, `body`, `mailbox`, `list_unsubscribe`, `precedence`
- only messages with `mailbox: "inbox"` are imported

For the live ProtonMail read-only slice, fetch from Proton Mail Bridge with:

```bash
python3 scripts/live_protonmail_fetch.py --account-id founder-proton --batch-size 25
```

Bridge setup contract for this repo:

- Proton Mail Bridge is the supported provider edge for live read-only Proton access
- Bridge requires a paid Proton Mail plan according to Proton's Bridge documentation
- default config path: `data/protonmail_credentials/protonmail_bridge/<account_id>.json`
- expected config fields: `host`, `port`, `username`, `password`, optional `ssl`
- example config: `examples/protonmail_bridge_config.example.json`

Lower-level review flow:

```bash
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001
```

Then apply approved labels with:

```bash
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-N
```

For autonomous handling of a specific stored live batch, use:

```bash
python3 scripts/auto_apply_live_gmail_batch.py --batch-id founder-test-batch-N
```

This auto-applies all current suggested `EA/` labels for pending items in the batch.

`INBOX` removal remains limited to:

- `spam-low-value`
- `promotions`

## Getting started

1. Add your implementation in `src/`.
2. Add tests in `tests/`.
3. Keep docs and decisions in `docs/`.
4. Update `.gitignore` and tooling once you choose a language/runtime.

## Manual Gmail fetch smoke test

After Founder approval for live Gmail read access, run the manual fetch CLI from the repo root:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
```

Default local paths:

- Credentials directory: `data/gmail_credentials/`
- Fetch storage directory: `data/gmail_fetch/`

OAuth client secret setup:

- Preferred filename: `data/gmail_credentials/client_secret.json`
- If that file is missing and there is exactly one `client_secret*.json` file in the credentials directory, the CLI will use it automatically
- If you want to point at a specific file, pass `--client-secret-path /path/to/client_secret.json`

If OAuth or token exchange fails with an SSL certificate verification error on a `python.org` macOS Python install, run:

```bash
open "/Applications/Python 3.13/Install Certificates.command"
```

Then retry the smoke test.
