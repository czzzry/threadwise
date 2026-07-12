# Teach / Apply Write-Through Completion

Status: Complete locally
Type: AFK
Parent PRD: `docs/prd-teach-apply-write-through-2026-07-07.md`
GitHub parent issue: `#58`

## What to build

Move the correction flow from local batch teaching into a visible apply-and-reload loop that the founder can trust.

The correction loop should become a small explicit state machine:

1. draft intent
2. proposed rule
3. accepted rule
4. scope choice
5. applying
6. compact receipt

Within that loop, the correction decision should expose three explicit outcomes:

1. apply once
2. apply once + future
3. apply once + future + inbox

The first option only changes the current email. The second option also saves the rule for future matching mail. The third option also rewrites matching existing inbox mail through Gmail write-through.

The visible result should make it clear what changed locally and what changed in the inbox after refresh. Failed actions must preserve the draft/accepted rule text so the founder can retry without retyping.

## Acceptance criteria

- [x] The correction path presents the three scope choices as the primary outcomes using concise CTAs:
  - `Fix email`
  - `Fix + future`
  - `Fix + inbox`
- [x] The correction path first shows `Proposed rule:` and requires accept/edit before scope selection.
- [x] `Edit` changes the proposed rule itself, not a separate hint prompt.
- [x] Clear edited rules are accepted directly; ambiguous edited rules are reformulated once for confirmation.
- [x] `Fix email` updates only the current email result.
- [x] `Fix + future` also saves the rule for future mail.
- [x] `Fix + inbox` rewrites matching existing inbox mail through Gmail write-through using the accepted rule as the match definition.
- [x] Matching remains conservative by default and does not broaden to all domain mail unless the accepted rule explicitly does so.
- [x] The result state states exactly which scope changed using compact operational copy.
- [x] Failed apply preserves the draft/accepted rule text for retry.
- [x] Reloading the companion after apply reflects the updated local state instead of the stale email.
- [x] The empty home state is minimal and does not preload a previously reviewed email.
- [x] Large inbox runs show the estimated match count before execution.
- [x] Large inbox runs require explicit inline confirmation when the estimate exceeds `200`.
- [x] The current-email path remains the simplest path and does not require the founder to think about inbox scope unless they choose it.

## Completion evidence

- `python3 -m unittest tests.test_gmail_companion_ui`
- `python3 -m unittest tests.test_teaching_loop`
- `python3 -m py_compile src/live_gmail_client.py src/gmail_writer.py src/teaching_loop.py src/gmail_companion_ui.py tests/test_gmail_companion_ui.py`
- `node --check extensions/gmail_companion/content.js`
- Commits: `e8bf867`, `b3d5e4e`, `ff0b887`

## Notes

This slice intentionally moves the product toward the founder's desired end state: teach a rule, apply it, clear the `needs check` items, reload, and see the inbox reflect the rule.
