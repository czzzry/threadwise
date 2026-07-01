# Add Gmail attention contract to daily report

Status: Completed
Type: AFK
GitHub issue: `#8`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed in: `3b2af36`

## What to build

Add the MVP+2 attention section to the Gmail daily report contract without changing Gmail mutation behavior.

This slice should make the daily report capable of carrying a versioned, non-mutating attention payload even before the full LLM evaluator is wired in. The payload should be visibly separate from unlabeled exceptions so future work does not confuse "classification failed" with "the user should look at this."

## Acceptance criteria

- [ ] Gmail daily reports can include an `attention` section with `schema_version`, evaluated-message count, lookback metadata, grouped counts, usage metadata, and item records.
- [ ] Each attention item can represent source message identifiers, level, category, reason, evidence, source, handled state, feedback state, and `gmail_mutation: "none"`.
- [ ] Existing daily report required fields remain valid and existing report readers keep working when `attention` is absent.
- [ ] Attention counts are not treated as `unlabeled_count`.
- [ ] Tests prove the new report contract is backward-compatible and separate from unlabeled exceptions.

## Blocked by

None - can start immediately.
