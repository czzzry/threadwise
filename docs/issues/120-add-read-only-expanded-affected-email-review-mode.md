# Add Read-Only Expanded Affected-Email Review Mode

GitHub issue: `#46`

Parent: GitHub issue `#42`

Status: Complete as of 2026-07-02

## What to build

Add an expanded Threadwise review mode for exact affected-email inspection.

From the sidebar, `Review N` should expand Threadwise into a wider right-side panel while leaving a small Gmail inbox strip visible for continuity. The expanded view should show exact affected emails in dense inbox-like rows and keep the pending rule session pinned.

## Acceptance criteria

- [x] Sidebar impact count exposes `Review N` when affected emails exist.
- [x] `Review N` opens an expanded Threadwise-owned review mode, not a new tab, Gmail search result, modal, or tiny sidebar list.
- [x] Expanded mode leaves some Gmail surface visible on the left for continuity.
- [x] Affected emails render as dense rows with sender, subject, current label, proposed label, and status.
- [x] Each row has `Open in Gmail` for deep inspection.
- [x] Expanded mode has clear `Collapse` / `Back to sidebar` behavior.
- [x] The pending rule session remains pinned across collapse/expand and Gmail email opening.
- [x] This slice is read-only: no broader apply or exclusion persistence yet.

## Validation

- `python3 -m py_compile src/gmail_companion_ui.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- `python3 -m unittest tests.test_gmail_companion_ui.GmailCompanionUiTests.test_extension_uses_harness_state_and_clickable_summary_filters tests.test_gmail_companion_ui.GmailCompanionUiTests.test_panel_html_is_minimizable_and_contains_local_harness_controls tests.test_gmail_companion_ui.GmailCompanionUiTests.test_simulator_page_contains_inbox_and_safe_local_only_language`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9222 save-future-rule`
- `python3 -m unittest discover -s tests`
- `git diff --check`

## Blocked by

- GitHub issue `#45`
