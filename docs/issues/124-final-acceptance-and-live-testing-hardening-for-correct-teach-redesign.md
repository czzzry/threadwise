# Final Acceptance and Live-Testing Hardening for Correct / Teach Redesign

GitHub issue: `#50`

Parent: GitHub issue `#42`

Status: Complete as of 2026-07-02

## What to build

Validate and harden the full inspect/correct/teach/review/apply loop before closing the redesign.

This slice should close gaps discovered across simulator, extension harness, and live-style browser flows.

## Acceptance criteria

- [x] Browser acceptance covers current-email fix, future-rule save, expanded affected review, exclusions, apply-included, and amendment proposal flows.
- [x] Regression checks cover sidebar overflow and expanded-panel layout.
- [x] Regression checks cover pinned review-session behavior while opening Gmail emails.
- [x] Error states explain whether anything changed and provide recovery actions.
- [x] Relevant docs/current-state notes are updated.
- [x] Parent issue `#42` is ready to close after founder review.

## Validation

- `python3 -m py_compile src/gmail_companion_ui.py src/teaching_loop.py tests/test_teaching_loop.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- `node --check scripts/validate_gmail_companion_simulator_cdp.mjs`
- `python3 -m unittest discover -s tests`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9222 apply-included`
- `git diff --check`

## Founder review note

Parent issue `#42` should be reviewed in the live Gmail sidebar before closure. The implementation is pushed through child issue `#50`; no additional implementation blocker is known.

## Blocked by

- GitHub issue `#44`
- GitHub issue `#45`
- GitHub issue `#46`
- GitHub issue `#47`
- GitHub issue `#48`
- GitHub issue `#49`
