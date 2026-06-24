# MVP Happy-Path Usage Guide

Status: Historical Gmail manual-review happy-path guide
Current default workflow: `scripts/daily_live_gmail_run.py`
Current implementation checkpoint: `docs/checkpoints/current-operating-model-2026-06-22.md`

This guide covers the earlier Gmail manual-review MVP flow that preceded the current one-command daily run.

It uses the existing commands and the already-proven workflow:

1. fetch a batch
2. review the stored batch locally
3. apply approved `EA/` labels
4. retry failed writes if needed
5. remove `INBOX` for approved low-value/promotions messages if wanted
6. inspect one batch or list all batches

## Historical MVP

The historical MVP was:

- one local Gmail account
- manual batch fetch
- local human review before any Gmail mutation
- local browser review UI for one stored batch
- approved `EA/` label write-back only
- optional retry of failed label writes
- optional explicit `remove INBOX` for approved low-value/promotions messages
- local privacy-safe inspection of stored batch state

## What The Tool Will Not Do

The current MVP will not:

- auto-delete messages
- trash messages
- send or reply to email
- run background polling or syncing
- support multiple accounts or providers
- expose private email content by default in the inspection/index commands
- mutate Gmail without an explicit confirmation step

## One-Time Setup Notes

Put the Google Desktop OAuth client secret in:

```bash
data/gmail_credentials/client_secret.json
```

Default local paths:

```bash
data/gmail_credentials/
data/gmail_fetch/
```

If your OAuth client secret lives somewhere else, most live Gmail commands also accept:

```bash
--client-secret-path /path/to/client_secret.json
```

If you are using a `python.org` macOS Python install and OAuth/token exchange fails with SSL certificate verification errors, run:

```bash
open "/Applications/Python 3.13/Install Certificates.command"
```

## Happy Path

Command types used below:

- Gmail-read-only:
  - `manual_gmail_fetch.py` fetches live Gmail messages into local stored batch files
- local-only:
  - `review_local_batch_in_browser.py` serves a local review UI and saves decisions to the stored batch only
  - `inspect_local_batch_status.py` and `list_local_batches.py` are read-only local inspection commands
- Gmail-mutating:
  - `review_live_gmail_batch.py` applies approved `EA/` labels only after explicit `APPLY`
  - `retry_live_gmail_failed_writes.py` retries failed Gmail label writes
  - `remove_inbox_for_live_gmail_batch.py` removes the Gmail `INBOX` label for eligible reviewed messages only after explicit `REMOVE`

Fetch a new batch:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
```

Review the stored batch locally in the browser. This is the preferred review surface:

```bash
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-2 --port 8001
```

In the browser review UI:

- review one pending stored item at a time
- approve suggested labels, save selected labels, mark unlabeled, or reject
- all decisions are saved locally to the stored batch only
- no Gmail API calls or Gmail writes happen in this step

Open the local URL printed by the command, usually:

```bash
http://127.0.0.1:8001
```

If you prefer or need the older fallback flow, you can still review in CLI instead:

```bash
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-2
```

Apply approved labels after browser review:

```bash
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-2
```

During the label-apply command:

- if the batch was already fully reviewed in the browser, the command does not make you re-review those same items
- instead, it goes straight to the dry-run summary for the stored reviewed decisions
- type `APPLY` only if the proposed `EA/` label write-back is correct
- this is the first Gmail-mutating step in the normal flow

Retry failed label writes for an already reviewed batch if needed:

```bash
python3 scripts/retry_live_gmail_failed_writes.py --batch-id founder-test-batch-2
```

Optionally remove `INBOX` for reviewed low-value/promotions messages after label write-back:

```bash
python3 scripts/remove_inbox_for_live_gmail_batch.py --batch-id founder-test-batch-2
```

During the inbox-removal command:

- the command shows a dry-run summary first
- only approved `promotions` or `spam-low-value` messages are eligible
- type `REMOVE` only if you want those messages removed from the main Gmail inbox view

Inspect one stored batch locally:

```bash
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-2
```

List all stored batches locally:

```bash
python3 scripts/list_local_batches.py
```

## Read-Only Inspection Output

The read-only commands are privacy-safe by default.

They summarize stored state such as:

- review counts
- final label counts
- write status and retry history
- inbox-removal status and attempt history

They do not print:

- subjects
- senders
- snippets
- bodies
- raw headers

## Safety Rules

Use these rules when operating the MVP:

- treat browser review as local-only state editing, and treat label write-back, retry, and `remove INBOX` as explicit human-confirmed Gmail mutation steps
- do not assume an unlabeled or rejected message will be mutated
- do not assume `remove INBOX` deletes or trashes a message; it removes the Gmail `INBOX` label only
- prefer inspecting stored state before rerunning live commands if you are unsure what already happened

## Troubleshooting

No OAuth client secret found:

```text
Put your Google Desktop OAuth JSON at data/gmail_credentials/client_secret.json
```

Stored token lacks the needed scope:

- rerun the relevant command
- complete the narrower approved re-auth flow when prompted

OAuth loopback or browser callback problems:

- rerun from a normal local shell session rather than a restricted sandboxed session

SSL certificate verification failure on macOS `python.org` Python:

```bash
open "/Applications/Python 3.13/Install Certificates.command"
```

Batch state is confusing:

```bash
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-2
python3 scripts/list_local_batches.py
```

Browser review page cannot be reached:

- rerun the local browser review command from a normal local shell session
- make sure you open the exact local URL printed by the command
- if the batch has no pending items left, the browser page should show a clear empty state rather than actionable review cards

Failed label writes remain after review:

```bash
python3 scripts/retry_live_gmail_failed_writes.py --batch-id founder-test-batch-2
```

Want to confirm what `remove INBOX` did:

- inspect the stored inbox-removal summary for that batch with `inspect_local_batch_status`
- list all stored batches with `list_local_batches`

## Recommended Operator Sequence

For a normal manual session, use this order:

```bash
python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/retry_live_gmail_failed_writes.py --batch-id founder-test-batch-N
python3 scripts/remove_inbox_for_live_gmail_batch.py --batch-id founder-test-batch-N
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-N
python3 scripts/list_local_batches.py
```

Replace `founder-test-batch-N` with the actual stored batch id.
