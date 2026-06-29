# Threadwise

Human-in-the-loop AI inbox triage before provider-side action.

Threadwise is a local-first prototype for AI-assisted inbox triage. It combines deterministic rules, model-assisted classification, a browser-side inbox companion, and explicit human review before broader provider-side changes.

This repo is meant to show practical AI workflow building and product judgment, not polished SaaS infrastructure. The interesting part is the loop: the agent classifies email, explains itself briefly, accepts correction in context, previews wider impact, and waits for confirmation before changing more than the current message.

Start here if you want the public project story:

- [Portfolio overview](docs/portfolio.md)
- [Current product direction](docs/v2-alignment.md)
- [Current bounded PRD](docs/prd.md)
- [Current operating checkpoint](docs/checkpoints/current-operating-model-2026-06-22.md)

## What It Does Today

- Gmail-first companion flow with a browser sidebar attached to the inbox
- Selected-email classification, short rationale, and teaching preview
- Daily run workflow with bounded Gmail label write-back
- Limited Gmail `INBOX` removal for already-approved low-value categories only
- ProtonMail read-only fetch and reporting path
- Daily and weekly reporting from local run artifacts
- Unsubscribe inventory plus explicit, auditable follow-up flows

## Why It Exists

Email is full of repetitive triage work, but fully autonomous inbox action is easy to over-claim and hard to trust.

Threadwise explores a narrower product bet:

- let automation do the repetitive first pass
- keep the human in the loop for corrections and broader changes
- make learning visible instead of silent
- keep provider-side actions bounded and explicit

## Safety Boundaries

- This repo does not claim full inbox autonomy.
- It does not default to deleting, trashing, broadly archiving, or sending email.
- It does not claim phishing or security-grade detection.
- ProtonMail is currently read-only.
- Broader existing-message rewrites are previewed first and require confirmation.

## Repo Guide

- `src/`: core classification, provider adapters, review/runtime logic, companion UI server
- `scripts/`: runnable entrypoints for Gmail, ProtonMail, reports, harnesses, and local tools
- `extensions/`: browser companion code
- `tests/`: behavior and contract tests
- `docs/`: product docs, PRDs, checkpoints, issues, handoffs, and portfolio framing
- `examples/`: safe sample inputs and config examples

## Demo And Screenshots

This repo does not yet include polished public screenshots.

Planned public demo assets:

- Gmail companion sidebar on a selected message
- `Correct / Teach` preview showing confirmation before broader changes
- Daily summary view
- Unsubscribe inventory / follow-up flow

Use [docs/portfolio.md](docs/portfolio.md) for the exact capture checklist.

## Running It Locally

Current preferred commands stay here, lower in the README because this repo is also a portfolio artifact.

Gmail daily workflow:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 50
```

ProtonMail read-only daily workflow:

```bash
python3 scripts/daily_live_protonmail_run.py --account-id founder-proton --batch-size 25
```

Weekly per-inbox report:

```bash
python3 scripts/weekly_inbox_report.py --account-id founder-test --storage-dir data/gmail_fetch --end-date 2026-06-20
```

Local browser review / workbench:

```bash
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001
```

Operational readiness check:

```bash
python3 scripts/check_operational_readiness.py
```

More operational detail:

- [Current operational readiness note](docs/current-operational-readiness-2026-06-29.md)
- [Current operating model checkpoint](docs/checkpoints/current-operating-model-2026-06-22.md)
- [Historical Gmail MVP guide](docs/archive/mvp-happy-path-gmail-manual-review.md)

## Private Local Data

This repo uses local private data paths such as:

- `data/gmail_credentials/`
- `data/gmail_fetch/`
- `data/protonmail_credentials/protonmail_bridge/<account_id>.json`

These paths are local-only and should not be committed.

