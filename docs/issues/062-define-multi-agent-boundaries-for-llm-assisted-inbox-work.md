# Status

Current
Current as of: 2026-06-28
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

# Title

Define multi-agent boundaries for LLM-assisted inbox work

## Type

AFK

## Blocked by

- `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

## User stories covered

`18`, `19`, `21`

## What to build

Write a durable coordination note for which slices are safe to parallelize, which shared artifacts require serialization, and which classes of work should stay single-agent.

This slice should not introduce new product behavior. It should reduce coordination mistakes by making the concurrency boundaries explicit for:

- corpora and evaluation artifacts
- suggestion-memory refreshes
- accepted-memory exports
- runtime cascade prototype work
- security-lane experiments

## Acceptance criteria

- [x] The repo has one current note stating which slices are safe for parallel work and which are not.
- [x] Shared local artifacts that require serialized writes are named explicitly.
- [x] Later agents can tell whether a proposed parallel slice is safe without reconstructing this conversation.

## Output

- Current coordination note: `docs/current-multi-agent-boundaries-2026-06-28.md`
