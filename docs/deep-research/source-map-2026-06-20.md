# Source Map For Deep Research

Date: 2026-06-20

Deep Research should inspect docs and code together. The codebase appears slightly ahead of some planning docs, so missing synchronization is itself useful signal.

## Product / alignment docs

- `AGENTS.md`: defines the intended working method, scope control, sensitive areas, and artifact expectations for the repo
- `README.md`: best short operational overview of the current Gmail and ProtonMail flows
- `docs/alignment.md`: current product intent, control model, taxonomy, review semantics, and success criteria
- `docs/prd.md`: fuller requirements and testing decisions for the Gmail-centered product slice
- `docs/mvp-checkpoint.md`: best checkpoint summary of what the Gmail MVP proved and what gaps remained at that stage
- `docs/mvp-happy-path-usage-guide.md`: concrete human workflow for running the current MVP
- `docs/v2-issue-map.md`: latest lightweight roadmap, useful mainly to compare against the implementation

## Pocock-style workflow docs

- `docs/issues/001-fixture-backed-review-loop-for-one-batch.md`: shows the original smallest vertical-slice shape
- `docs/issues/027-auto-apply-all-suggested-live-gmail-labels.md`: useful checkpoint for the current Gmail operating model
- `docs/issues/029-daily-per-run-operational-report-for-one-inbox.md`: reporting slice that turns the workflow into an operating loop
- `docs/issues/030-weekly-per-inbox-analytical-report-from-daily-run-artifacts.md`: weekly reporting intent
- `docs/issues/034-daily-live-protonmail-read-only-run-with-report.md`: clearest ProtonMail slice statement
- `docs/issues/035-gmail-unsubscribe-inventory-and-selection-workbench.md`: unsubscribe workbench scope
- `docs/issues/036-execute-selected-gmail-unsubscribes-with-audit.md`: unsubscribe execution scope
- `docs/issues/037-manual-follow-up-path-for-unsupported-unsubscribes.md`: manual follow-up scope for unsupported unsubscribes

## Source code

- `src/live_gmail_daily_run_cli.py`: best Gmail end-to-end entrypoint
- `src/live_protonmail_daily_run_cli.py`: best ProtonMail end-to-end entrypoint
- `src/gmail_fetcher.py`: Gmail fetch seam into the stored-batch model
- `src/live_gmail_client.py`: live Gmail integration edge and OAuth surface
- `src/live_protonmail_client.py`: live Proton Mail Bridge integration edge
- `src/review_loop.py`: review-state and prioritization logic
- `src/stored_batch_review_store.py`: local persistence contract for stored batches and review decisions
- `src/gmail_writer.py`: Gmail label write-back, retries, and bounded `INBOX` removal
- `src/local_browser_review_ui.py`: local UI / workbench surface tying together review, eval, and unsubscribe workflows
- `src/weekly_inbox_report_cli.py`: report aggregation seam
- `src/shadow_label_eval.py`: OpenAI-based shadow-eval path over reviewed historical batches
- `src/unsubscribe_inventory_store.py`: unsubscribe-candidate derivation from stored data
- `src/unsubscribe_execution.py`: audited execution and manual/unsupported distinctions
- `src/fixture_classifier.py`: current classification heuristic spine used throughout the repo
- `src/label_taxonomy.py`: canonical taxonomy and label naming rules

## Tests / evals

- `tests/test_live_gmail_daily_run_cli.py`: most compact proof of the Gmail operating loop
- `tests/test_live_protonmail_daily_run_cli.py`: most compact proof of the ProtonMail read-only loop
- `tests/test_weekly_inbox_report_cli.py`: proof that daily artifacts become analytical weekly artifacts
- `tests/test_local_browser_review_ui.py`: proof of privacy-minded workbench behavior and multi-surface local UI behavior
- `tests/test_gmail_writer.py`: proof of bounded Gmail mutation behavior
- `tests/test_live_protonmail_client.py`: proof of Bridge-config-based live ProtonMail reading
- `tests/test_unsubscribe_execution.py`: proof of audited unsubscribe execution semantics
- `tests/test_shadow_label_eval.py`: proof of shadow-eval report construction

## Scripts / runners

- `scripts/daily_live_gmail_run.py`: runnable Gmail daily loop wrapper
- `scripts/daily_live_protonmail_run.py`: runnable ProtonMail daily loop wrapper
- `scripts/weekly_inbox_report.py`: runnable weekly report wrapper
- `scripts/review_local_batch_in_browser.py`: runnable local UI wrapper
- `scripts/manual_gmail_fetch.py`: lower-level Gmail fetch entrypoint
- `scripts/live_protonmail_fetch.py`: lower-level live ProtonMail fetch entrypoint
- `scripts/auto_apply_live_gmail_batch.py`: lower-level Gmail auto-apply wrapper
- `scripts/retry_live_gmail_failed_writes.py`: lower-level retry wrapper

## Handoff docs

- `docs/handoff/issues-001-005-mocked-spine.md`: shows the original implementation spine and early workflow
- `docs/handoff/mvp-v0.1-acceptance.md`: useful checkpoint on what was accepted as real progress
- `docs/handoff/next-session-start.md`: likely useful context on what the next session was expected to do
- `docs/handoff/issue-014-remove-inbox-for-approved-low-value-live-messages.md`: explains one major bounded-autonomy decision in practice
- `docs/handoff/issue-016-mvp-happy-path-usage-guide.md`: explains why the usage guide exists and what behavior was validated

## Decision / ADR docs

- `docs/decisions/review-semantics.md`: minimum explicit semantics for review outcomes, confidence bands, and label compatibility

## Missing but potentially useful

- `CONTEXT.md`: not present; would help a research reader understand high-level current state fast
- `docs/adr/`: not present as a folder; could help if hard-to-reverse technical decisions start accumulating
- `docs/product/`: not present as a folder; may not be needed yet, but Deep Research should note the absence
- `docs/agent-handoffs/`: not present; handoffs currently live under `docs/handoff/`
- A single repo-level architecture or state-model note: not present, which partly explains why code and roadmap drift takes effort to reconcile
- A sanitized public-demo dataset: not present, but would be useful for safe sharing and external review
