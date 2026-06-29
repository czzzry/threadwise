# Status

Current
Current as of: 2026-06-28
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

# Title

Harden shadow suggestion memory and review loop

## Type

AFK

## Blocked by

- `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

## User stories covered

`5`, `6`, `12`, `13`, `14`, `15`, `21`

## What to build

Stabilize the local suggestion-memory workflow so that model-backed family candidates can be reviewed, persisted, refreshed, and exported without race conditions, silent regression, or provider leakage.

The slice should formalize:

- pending / accepted / rejected transitions
- durability across refreshes
- provider-scoped export of accepted memory
- artifact fields required for later runtime use
- projection reporting that shows whether accepted memory improves shadow corpora without regressing Gmail benchmark behavior

## Acceptance criteria

- [ ] Accepted and rejected candidates survive future suggestion-memory refreshes.
- [ ] Exported accepted rules remain provider-scoped unless explicitly widened later.
- [ ] Projection over stored corpora reports before/after deltas and does not silently regress Gmail benchmark behavior.

