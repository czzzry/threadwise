# Make Correct / Teach Action Results Unmistakable

Status: Complete locally
Type: AFK
Parent PRD: `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md`

## What to build

Make the result state after `Fix this email` and `Use for future emails` explicit enough that the founder can tell what happened without interpreting prose.

## Acceptance criteria

- [x] Successful current-email fix shows `What changed` with current-email, Gmail, existing-email, and future-rule rows.
- [x] Successful future-rule save shows `What changed` with future-rule, current-email, existing-email, and Gmail rows.
- [x] Failed apply distinguishes checking/reconnecting the companion from retrying the same fix.
- [x] Browser acceptance covers both current-email result and future-rule result.
- [x] Existing-email rewrite controls remain out of the primary result state.

## Completion evidence

- `python3 -m unittest tests.test_gmail_companion_ui tests.test_teaching_loop`
- `python3 -m unittest discover -s tests`
- `python3 -m py_compile src/gmail_companion_ui.py src/teaching_loop.py tests/test_gmail_companion_ui.py tests/test_teaching_loop.py`
- `node --check extensions/gmail_companion/content.js scripts/validate_gmail_companion_simulator_cdp.mjs scripts/validate_gmail_companion_pending_states_cdp.mjs`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9333`
- `git diff --check`
