# Add Apply-Included Flow for Reviewed Affected Emails

GitHub issue: `#48`

Parent: GitHub issue `#42`

Status: Complete as of 2026-07-02

## What to build

After affected emails have been reviewed, let the founder apply the broader rule only to exact included IDs, while saving the future rule and durable exceptions.

The apply result should report exactly what changed.

## Acceptance criteria

- [x] Expanded review mode exposes `Apply to included` only when the affected set is current.
- [x] `Apply to included` applies only to exact included message IDs.
- [x] The future rule is saved as part of the normal apply-included flow.
- [x] Durable exceptions for excluded emails are preserved.
- [x] The success state reports counts for emails updated, exceptions saved, and future rule saved.
- [x] Applying is disabled while affected emails are stale or recomputing.
- [x] The decision is recorded in the local audit trail.
- [x] No `apply once only` primary flow is introduced.

## Validation

- `python3 -m py_compile src/gmail_companion_ui.py src/teaching_loop.py src/teaching_exclusions.py src/gmail_batch_review_store.py tests/test_teaching_loop.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- `node --check scripts/validate_gmail_companion_simulator_cdp.mjs`
- `python3 -m unittest tests.test_teaching_loop.TeachingLoopTests.test_apply_included_relabels_only_included_matches_and_saves_future_rule tests.test_gmail_companion_ui.GmailCompanionUiTests.test_extension_uses_harness_state_and_clickable_summary_filters tests.test_gmail_companion_ui.GmailCompanionUiTests.test_panel_html_is_minimizable_and_contains_local_harness_controls tests.test_gmail_companion_ui.GmailCompanionUiTests.test_simulator_page_contains_inbox_and_safe_local_only_language`
- `python3 -m unittest discover -s tests`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9222 apply-included`
- `git diff --check`

## Blocked by

- GitHub issue `#47`
