# Status

Current
Current as of: 2026-06-28
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/059-harden-shadow-suggestion-memory-and-review-loop.md`

# Title

Build memory-first runtime cascade prototype on stored corpora

## Type

AFK

## Blocked by

- `docs/issues/059-harden-shadow-suggestion-memory-and-review-loop.md`

## User stories covered

`1`, `5`, `9`, `10`, `13`, `20`, `21`, `22`

## What to build

Prototype the intended daily cascade on stored corpora before touching live inboxes:

1. deterministic/provider-safe pass
2. accepted memory pass
3. LLM escalation pass for unresolved messages
4. explicit unresolved output for remaining ambiguous messages

This slice should prove the control flow and measurement seams over stored artifacts, not broaden provider-side mutation or scheduling.

## Acceptance criteria

- [ ] A stored-corpus run can report how many messages were resolved at each cascade stage.
- [ ] The cascade distinguishes deterministic matches, memory matches, LLM escalations, and unresolved leftovers.
- [ ] The prototype can be compared against baseline corpus metrics without live provider calls.

