# Add Durable Exclusion Decisions in Affected Review

GitHub issue: `#47`

Parent: GitHub issue `#42`

Status: Complete as of 2026-07-02

## What to build

Let the founder exclude emails from an affected-rule review and save durable exceptions so the same rule does not hit excluded emails later.

Exclusion should be quick and not require an explanation, but Threadwise may optionally ask why or suggest a generalized exception if it can infer a useful boundary.

## Acceptance criteria

- [x] Each affected row can be excluded from the pending rule apply set.
- [x] Excluding an email immediately saves an exact durable exception for that rule/email.
- [x] The UI confirms: `Exception saved. This rule will not apply to this email/pattern later.`
- [x] Exclusion does not require a text explanation.
- [x] Optional reason capture is available after exclusion.
- [x] Generalized exception/pattern proposals require explicit approval and are never silent.
- [x] Tests prove excluded emails are protected from the same rule in future runs.

## Validation

- `python3 -m py_compile src/gmail_companion_ui.py src/teaching_loop.py src/teaching_exclusions.py src/gmail_batch_review_store.py tests/test_teaching_loop.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- `node --check scripts/validate_gmail_companion_simulator_cdp.mjs`
- `python3 -m unittest tests.test_teaching_loop.TeachingLoopTests.test_excluded_matching_email_is_saved_and_protected_from_same_rule tests.test_gmail_companion_ui.GmailCompanionUiTests.test_teach_exclude_saves_exception_and_refreshes_preview`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9222 save-future-rule`
- `python3 -m unittest discover -s tests`
- `git diff --check`

## Blocked by

- GitHub issue `#46`
