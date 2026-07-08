# Diagnose and Rebuild Correct / Teach as a State-Machine Loop

Status: Complete locally
Type: AFK
Parent PRD: `docs/prd-correct-teach-state-machine-simplification-2026-07-07.md`
GitHub parent issue: `#58`
GitHub issue: `#59`

## What to build

Diagnose the reported `Fix this email` failure and rebuild the selected-current-email Correct / Teach flow around explicit states instead of the current stacked consequence preview.

This slice should prove the core path end to end:

1. The founder opens a Gmail email Threadwise knows about.
2. The founder starts correction.
3. Threadwise proposes one plain-English rule.
4. The founder approves or refines the rule.
5. The founder applies the accepted rule to the current email.
6. Threadwise reports exactly what changed locally and in Gmail.

Do not reintroduce future-rule saving, affected-email review, exclusions, or broad existing-email apply as primary controls in this first slice. Those are follow-up branches after the current-email fix is trustworthy.

## Acceptance criteria

- [x] Existing `Fix this email` behavior is characterized with a failing or diagnostic test that distinguishes local-state failure, Gmail write-through failure, refresh failure, and unclear result copy.
- [x] Correct / Teach uses explicit visible states: `Viewing email`, `Teaching`, `Rule proposed`, `Refining`, `Scope confirmation`, `Applying`, `Result`, and `Blocked` where relevant.
- [x] The first proposed-rule screen shows one plain-English rule and only the next decision: approve it or change it.
- [x] Scope choices appear only after the rule is accepted.
- [x] Current-email apply is the only mutation path in this slice.
- [x] The result state reports whether the current email changed locally, in Gmail, both, or neither.
- [x] Pending apply disables duplicate submission and shows a working state.
- [x] Advanced details, manual label override, affected examples, and debug/source wording are hidden from the default correction path.
- [x] Browser/simulator acceptance proves the compact sidebar does not display all correction consequences at once.
- [x] Broader existing-email rewrites remain unavailable or explicitly out of the primary path.

## Completion evidence

- `python3 -m unittest tests.test_gmail_companion_ui tests.test_teaching_loop`
- `python3 -m py_compile src/live_gmail_client.py src/gmail_writer.py src/teaching_loop.py src/gmail_companion_ui.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- Commits: `b3d5e4e`, `ff0b887`
