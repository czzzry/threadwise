# Repo State Snapshot

Date: 2026-06-20

## Git state

- Current branch: `main`
- `origin` remote: not configured
- Commit history: none yet; `git log --oneline -5` fails because the branch has no commits
- Working tree summary: the entire project is currently untracked, including docs, source, tests, scripts, examples, data, `.github/`, `.gitignore`, `README.md`, and `AGENTS.md`

## Project purpose

This repository is exploring a local email-agent / inbox-assistant product. The current practical goal is a bounded inbox-triage workflow that labels messages, applies trusted labels automatically, removes `INBOX` only for clearly low-value mail, and leaves the remaining exceptions for manual follow-up.

## Current product state

The repo is beyond pure planning. It contains a working Python implementation, a substantial test suite, and durable workflow artifacts from a Pocock-style process.

The repo appears to have three active tracks:

1. A Gmail operating loop for one inbox:
   `fetch -> classify -> auto-apply EA labels -> remove INBOX for promotions / spam-low-value -> inspect leftovers`
2. A ProtonMail read-only path:
   fetch through Proton Mail Bridge or import a Proton export, classify into the same local batch model, and write daily/weekly reports without provider-side mutation
3. Local inspection and operations tools:
   browser review UI, status/index/reporting commands, shadow-label evaluation, and unsubscribe inventory / execution support

## Main user flows

### Gmail daily run

- Run `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 50`
- Fetches a new Gmail inbox batch
- Classifies messages into the fixed taxonomy
- Auto-approves items that already have current trusted suggestions
- Writes `EA/` labels back to Gmail
- Removes `INBOX` only for `promotions` and `spam-low-value`
- Writes a daily JSON report
- Prints the remaining unlabeled exceptions

### Gmail manual review fallback

- Run `python3 scripts/review_local_batch_in_browser.py --batch-id <batch_id> --port 8001`
- Review or inspect a stored batch locally in a browser UI
- Persist review decisions locally
- Keep Gmail writes out of that local-only review surface

### ProtonMail read-only run

- Run `python3 scripts/daily_live_protonmail_run.py --account-id founder-proton --batch-size 25`
- Fetches a live ProtonMail batch through Bridge
- Classifies into the same provider-aware local batch model
- Produces a daily report
- Performs no ProtonMail label or inbox mutation

### Weekly reporting

- Run `python3 scripts/weekly_inbox_report.py --account-id <account> --end-date 2026-06-20`
- Aggregates daily report artifacts into a weekly report window

### Unsubscribe workbench path

- The local browser UI and unsubscribe modules support inventorying mailing-list candidates, selecting candidates, and executing supported one-click unsubscribes with audit history
- Unsupported `mailto:` or non-one-click HTTP cases appear to be surfaced for manual follow-up rather than automated execution

## Current vertical slice status

Based on docs plus code:

- Docs say issues `001` through `027` established the Gmail MVP loop
- `029` weekly-report precursor work is marked complete in `docs/v2-issue-map.md`
- The codebase also contains implementation and tests for later slices that are only partially reflected in roadmap docs:
  - daily Gmail run reporting
  - weekly inbox reporting
  - provider-aware reporting
  - live ProtonMail read-only fetch and daily run
  - unsubscribe inventory / execution paths
  - manual follow-up path for unsupported unsubscribes

Best current read: the repository has working code beyond the last fully synchronized planning checkpoint, so Deep Research should treat docs and code together and note where roadmap docs lag the implementation.

## What appears complete

- Durable alignment, PRD, issue, handoff, and checkpoint docs exist
- Fixed-taxonomy classification workflow exists
- Stored-batch model exists with local persistence
- Gmail fetch path exists
- Gmail label write-back exists
- Retry of failed Gmail writes exists
- `INBOX` removal for low-value Gmail messages exists
- Local batch inspection/index/status tools exist
- Browser review / workbench UI exists
- Daily report generation exists
- Weekly report aggregation exists
- ProtonMail import and live Bridge read-only paths exist
- Shadow-label evaluation tooling exists
- Unsubscribe candidate inventory and audited execution path exist
- The test suite is broad and organized around user-visible behavior

## What appears partial or brittle

- The repo has no commits yet, so there is no clean published baseline
- There is no configured `origin` remote
- Planning docs and implementation are not perfectly synchronized
- The system is heavily local-file based; that is pragmatic, but likely brittle if the repo grows
- The browser UI is intentionally lightweight and appears to serve multiple concerns from one module
- Sensitive local data is currently present in the working tree, which blocks a safe GitHub snapshot
- The Gmail / ProtonMail provider boundary is only "provider-aware where useful," not a deliberate abstraction
- The shadow evaluation path calls the OpenAI API directly from local code and depends on env vars, which is fine for exploration but not yet hardened

## What is not implemented yet

- No committed, shareable baseline branch exists
- No remote GitHub snapshot exists from this repo state
- No background polling / sync loop
- No multi-account operating model
- No provider-side ProtonMail mutation path
- No broad metrics / eval framework beyond local reports and shadow-eval artifacts
- No hardened secret-management approach beyond `.gitignore`
- No productionized deployment or service boundary

## Main source files and what they do

- `src/live_gmail_daily_run_cli.py`: end-to-end Gmail fetch / auto-apply / inbox-removal / daily-report command
- `src/live_protonmail_daily_run_cli.py`: end-to-end ProtonMail read-only fetch / classify / daily-report command
- `src/gmail_fetcher.py`: Gmail inbox fetch adapter that feeds the stored-batch flow
- `src/live_gmail_client.py`: live Gmail OAuth/API integration edge
- `src/live_protonmail_client.py`: Proton Mail Bridge IMAP integration edge
- `src/review_loop.py`: review-state handling, ordering, label normalization, and batch completion summary
- `src/gmail_writer.py`: Gmail label write-back, retry status, and `INBOX` removal audit
- `src/stored_batch_review_store.py`: local persistence for stored batches and review decisions
- `src/local_browser_review_ui.py`: local HTTP review/workbench UI, including stored-batch workbench, evaluations, and unsubscribe surfaces
- `src/weekly_inbox_report_cli.py`: aggregation of daily artifacts into weekly account reports
- `src/shadow_label_eval.py`: reviewed-corpus loading, OpenAI shadow-model comparison, and evaluation report writing
- `src/unsubscribe_inventory_store.py`: derive unsubscribe candidates from stored batches
- `src/unsubscribe_execution.py`: preview and execute supported one-click unsubscribes with audit logging

## Main tests and what they prove

- `tests/test_live_gmail_daily_run_cli.py`: Gmail daily run works from the repo root, auto-applies current suggestions, removes `INBOX` when eligible, and writes a daily report
- `tests/test_live_protonmail_daily_run_cli.py`: ProtonMail daily run stays read-only while still classifying and writing a daily report
- `tests/test_weekly_inbox_report_cli.py`: weekly report aggregation works for both Gmail and ProtonMail daily artifacts
- `tests/test_local_browser_review_ui.py`: local review/workbench UI starts, hides private message bodies from workbench views, and exposes evaluation / unsubscribe surfaces
- `tests/test_gmail_writer.py`: Gmail write-back behavior, retries, namespacing, and bounded `INBOX` removal logic
- `tests/test_live_protonmail_client.py`: Proton Mail Bridge config loading and read-only IMAP fetch behavior
- `tests/test_unsubscribe_execution.py`: one-click unsubscribe execution is audited and unsupported cases remain non-automated
- `tests/test_shadow_label_eval.py`: shadow-eval prompt/report logic and report persistence

## How to run the app locally

Primary documented commands:

- Gmail daily run:
  `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 50`
- ProtonMail daily run:
  `python3 scripts/daily_live_protonmail_run.py --account-id founder-proton --batch-size 25`
- Weekly report:
  `python3 scripts/weekly_inbox_report.py --account-id founder-test --storage-dir data/gmail_fetch --end-date 2026-06-20`
- Browser review UI:
  `python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001`
- Manual Gmail fetch:
  `python3 scripts/manual_gmail_fetch.py --account-id founder-test --batch-size 10`
- Live ProtonMail fetch:
  `python3 scripts/live_protonmail_fetch.py --account-id founder-proton --batch-size 25`

Environment / local prerequisites inferred from the repo:

- Python 3
- Gmail OAuth client secret and token files under `data/gmail_credentials/`
- Proton Mail Bridge config JSON under `data/protonmail_credentials/protonmail_bridge/`
- Optional OpenAI API key for shadow evaluation via `EMAIL_AGENT_OPENAI_API_KEY` or `OPENAI_API_KEY`

## How to run tests / evals

- Safest broad check:
  `python3 -m unittest discover -s tests`
- Shadow evaluation path:
  code exists via `src/shadow_label_eval.py` and CLI support, but it requires a local OpenAI API key and reviewed stored batches

## Current checks

- Ran `python3 -m unittest discover -s tests`
- Result: `Ran 187 tests in 2.437s` and `OK`
- This is the safest clear repo-wide check I found from the current layout

## Known risks

- Privacy risk: real inbox artifacts and live credentials are present in `data/`
- Git hygiene risk: the repo has no commit history yet
- Publishing risk: ProtonMail Bridge credentials are not currently ignored by `.gitignore`
- Documentation drift: roadmap docs do not perfectly match implementation state
- Architecture risk: local JSON artifacts are doing many jobs at once
- Workflow risk: the product is meaningful, but the next training slice is not obvious because the repo mixes product discovery, live integrations, local tooling, and evaluation work

## Open questions

- Should the next week focus on tightening this repo or stepping down to a smaller training project first?
- Which current pain matters most: unlabeled exceptions, eval quality, unsubscribe workflow, reporting UX, or repo hygiene?
- Which product decisions need to be written down before further implementation, especially around provider boundaries, storage contracts, and sensitive-data handling?
- Which artifacts should be sanitized or replaced before any public or semi-public sharing workflow?
