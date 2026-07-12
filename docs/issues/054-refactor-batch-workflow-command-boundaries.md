# 054 - Refactor batch workflow command boundaries

Status: Ready for agent
Current as of: 2026-06-24
Type: bounded architecture refactor

## Context

The repo now has a working provider-aware local batch model, Gmail bounded mutation paths, ProtonMail read-only daily runs, reporting, readiness checks, and browser workbench flows.

The current architecture scan found one bounded refactor worth doing before new email evidence arrives: some command modules are also acting as shared libraries. In particular, Gmail daily run, auto-apply, retry, and remove-inbox commands import private helpers from `live_gmail_review_cli.py`, and `StoredBatchReviewStore` has a generic name while containing Gmail-specific raw-message refresh behavior.

## Goal

Make command files thinner and make provider-specific review refresh behavior explicit without changing product behavior.

## In Scope

- Extract shared path helpers and Gmail client factory setup out of `live_gmail_review_cli.py`.
- Extract daily report construction/writing shared by Gmail and ProtonMail daily runs.
- Move Gmail-specific review queue refresh out of the generic-looking `StoredBatchReviewStore` interface.
- Keep command output, report JSON shape, write status files, and inbox-removal behavior unchanged.
- Add or preserve characterization tests around affected behavior.

## Out of Scope

- Classifier rewrite.
- Gmail OAuth/client refactor.
- Browser workbench redesign.
- New Gmail actions, ProtonMail writes, scheduling, deleting, trashing, or broad archiving.
- Any live inbox command execution.

## Acceptance Criteria

- Existing affected CLI tests continue to pass.
- `live_gmail_daily_run_cli.py`, `live_gmail_auto_apply_cli.py`, `live_gmail_retry_cli.py`, and `live_gmail_remove_inbox_cli.py` no longer import private helpers from `live_gmail_review_cli.py`.
- Gmail-specific stored-batch refresh is exposed through an explicitly Gmail-named module or class.
- Daily Gmail and ProtonMail report writing share one helper while preserving their current artifact schema.
- No production behavior changes are intended.

## Validation

- Run the available Python unit tests for affected modules.
- If `pytest` is unavailable, run the affected `unittest` test files directly.
