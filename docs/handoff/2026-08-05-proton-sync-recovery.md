# Proton Sync Recovery Handoff

Status: Implemented and installed; live mailbox catch-up not executed
Current as of: 2026-08-05

## Failure

Fresh Proton messages appeared unlabeled and the shared panel displayed “Threadwise has not synced this email yet.” Its **Check again** button only reread the stale local ledger because Proton explicitly disabled manual provider sync. Separately, the recurring task was a feedback reminder, not an installed Proton run schedule. Obvious delivery, job, project, order, account, and agreement messages therefore never reached either the classifier or learned rules.

The extension also contained an unrelated stale apply-flow reference in `refreshSelection` that raised `ReferenceError: mode is not defined` after every state request.

## Fix

- Gmail and Proton now use one `/api/provider-sync-run` action.
- Proton invokes the existing incremental daily pipeline with a maximum of 25 new messages; processed identities are skipped before message fetch and classification.
- Medium/high confidence suggestions retain the existing additive, read-back-verified, Inbox-preserving Proton label boundary.
- Proton selected-email matching normalizes sender addresses and whitespace, then permits a unique-subject fallback when the page cannot expose a reliable sender.
- The dead refresh reference was removed.
- Extension version `0.3.2` retires already injected stale content scripts when the unpacked extension is reloaded.
- `com.threadwise.proton-daily` now schedules the incremental run for 6:00 a.m. and is enabled, disabled, loaded, and unloaded with Threadwise Start/Stop.
- LaunchAgent installation retries the brief macOS post-unload transition instead of leaving Threadwise stopped when `launchctl` initially rejects an immediate reload.
- Privacy-allowlisted PostHog events record provider sync started, completed, or failed using only provider, count buckets, outcome, and coarse error category.

## Evidence

- Regression tests first reproduced the disabled Proton action, missing provider endpoint, and sender-format mismatch.
- A real browser click-through used the production content script: the panel began in “not synced,” clicked **Run Proton Mail sync**, sent `provider=protonmail` and `batch_size=25`, then rendered the selected message as an Orders review item with no browser errors.
- The installed schedule reports a 6:00 calendar trigger, `RunAtLoad=false`, and zero executions after installation.
- The final installed helper reports **Running**, Proton Mail Bridge reports **Available**, and the schedule still reports zero executions.
- The complete automated suite passes: 792 tests, plus JavaScript syntax/provider checks and Swift type-checking.
- No live Proton fetch or label write was performed during implementation or verification.

## Founder Action

Reload the unpacked Threadwise extension once so Brave activates version `0.3.2`. A live catch-up sync remains separately approval-gated because it reads and may apply verified labels to the Proton inbox.
