# Add Rule Amendment Proposals from Exclusions

GitHub issue: `#49`

Parent: GitHub issue `#42`

Status: Complete as of 2026-07-02

## What to build

When exclusions reveal that a pending broader rule is too broad, Threadwise should propose a revised rule and recompute affected emails before apply.

Rule amendments are proposals only. Threadwise must never silently rewrite the rule.

## Acceptance criteria

- [x] Multiple or semantically clear exclusions can trigger a proposed rule amendment.
- [x] The proposal explains the revised boundary in plain English.
- [x] The founder can accept, reject, or keep reviewing before the rule changes.
- [x] Accepting an amendment recomputes the affected list and shows changed counts.
- [x] Apply actions remain disabled while recomputing.
- [x] If the boundary is unclear, Threadwise asks at most one clarifying question.
- [x] Tests cover that rule amendments are not applied silently.

## Validation

- `python3 -m py_compile src/gmail_companion_ui.py src/teaching_loop.py tests/test_teaching_loop.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- `node --check scripts/validate_gmail_companion_simulator_cdp.mjs`
- `python3 -m unittest tests.test_teaching_loop.TeachingLoopTests.test_exclusion_proposes_rule_amendment_without_applying_it_silently tests.test_gmail_companion_ui.GmailCompanionUiTests.test_teach_amendment_accepts_proposed_boundary tests.test_gmail_companion_ui.GmailCompanionUiTests.test_extension_uses_harness_state_and_clickable_summary_filters tests.test_gmail_companion_ui.GmailCompanionUiTests.test_panel_html_is_minimizable_and_contains_local_harness_controls tests.test_gmail_companion_ui.GmailCompanionUiTests.test_simulator_page_contains_inbox_and_safe_local_only_language`
- `python3 -m unittest discover -s tests`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9222 apply-included`
- `git diff --check`

## Blocked by

- GitHub issue `#48`
