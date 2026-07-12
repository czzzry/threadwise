# Status

Completed
Current as of: 2026-06-30
Triage state: `ready-for-agent`
Builds on: `docs/issues/080-deepen-gmail-companion-product-module.md`

# Title

Deepen teaching loop module without changing learning behavior

## Type

AFK / Refactor / Pre-MVP+2

## What to build

Extract the Gmail companion teaching workflow into a dedicated teaching-loop module while preserving current product behavior.

The new module should own the orchestration from selected email correction through preview, current-message apply, optional matching-existing rewrite, optional future rule approval, acknowledgment text, and Gmail write-through item selection. Existing rule parsing/matching and proposal persistence modules should remain separate.

This is behavior-preserving. Do not add new teaching modes, change rule-matching semantics, alter labels, change Gmail write-through rules, change UI copy, or touch browser extension files.

## Acceptance criteria

- [x] The teaching-loop module exposes a clear interface for previewing and applying a sidebar teaching correction.
- [x] `teachable_rule_memory.py` remains responsible for rule data, parsing, matching, and rule persistence.
- [x] `memory_proposal_store.py` remains responsible for proposal data, proposal review, and rule creation.
- [x] Current-only, matching-existing, and future-only teaching behavior is unchanged.
- [x] Gmail write-through item selection is unchanged.
- [x] Existing Gmail companion routes and UI behavior are unchanged.
- [x] Focused tests cover the new teaching-loop interface and existing Gmail companion teaching tests still pass.

## Blocked by

None - can start immediately.
