# Add Future-Email Scope After Rule Acceptance

Status: Complete locally
Type: AFK
Parent PRD: `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md`
GitHub parent issue: `#58`

## What to build

Add the next scope option to the simplified Correct / Teach state machine: after Threadwise proposes a rule and the founder accepts it, the scope confirmation state may offer `Use for future emails`.

This must stay separate from the current-email fix and from existing-email rewrites.

## Acceptance criteria

- [x] `Rule proposed` still shows only the proposed rule plus `Looks right` / `Change rule`.
- [x] `Use for future emails` appears only in `Scope confirmation`, after the rule is accepted.
- [x] Clicking `Use for future emails` uses the existing `save-future-rule` behavior.
- [x] The result state says a future rule was saved and that the current/existing stored emails were not rewritten.
- [x] Current-email `Fix this email` remains available as its own separate action.
- [x] Matching existing-email rewrites and affected-review controls remain out of the primary state-machine path.
- [x] Browser/simulator acceptance proves the future scope is not visible before rule acceptance.

## Completion evidence

- `python3 -m unittest tests.test_gmail_companion_ui tests.test_teaching_loop`
- `python3 -m unittest discover -s tests`
- `python3 -m py_compile src/gmail_companion_ui.py src/teaching_loop.py tests/test_gmail_companion_ui.py tests/test_teaching_loop.py`
- `node --check extensions/gmail_companion/content.js scripts/validate_gmail_companion_simulator_cdp.mjs scripts/validate_gmail_companion_pending_states_cdp.mjs`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8031/simulator http://127.0.0.1:9333`
- `git diff --check`

## Out of scope

- Applying the accepted rule to matching existing stored emails.
- Combining current-email fix and future-rule save into one default action.
- New Gmail mutation types.
