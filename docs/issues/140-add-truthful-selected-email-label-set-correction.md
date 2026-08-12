# Issue 140 — Add truthful selected-email label-set correction

Status: Ready for bounded implementation
Approved by: Founder, 2026-08-12
Parent direction: `docs/prd-threadwise-gauntlet-2026-08-09.md`

## Problem

The current Correct / Teach path collapses every correction to one `target_label` even though messages and the Gmail writer already support multiple Threadwise labels. It cannot truthfully express requests such as “keep Orders and add Receipts” or “remove NeedsAction but keep Finance.” Preview and apply may also interpret the same note separately, allowing the approved intent to drift.

## Bounded outcome

For the selected email only, support an explicit label-change contract with `only`, `add`, `remove`, and `replace` operations over one to three canonical Threadwise labels. Preview shows the ordered before/after sets, primary label, interpretation source, model name when applicable, and exact scope. Apply consumes the approved normalized preview and must not call the model again.

Gmail must preserve non-Threadwise labels, replace the `EA/` label set exactly, read it back, and report success only after verification. Failure or mismatch remains retryable. Proton remains additive-only: unsupported removal/replacement operations stop before local or provider mutation.

## Acceptance criteria

- Natural-language current-email corrections can produce exact one-, two-, or three-label results using `only`, `add`, `remove`, and `replace`.
- Legacy single-label correction maps to `only [target_label]` and remains compatible.
- Preview visibly shows labels before and after, primary label, current-email-only scope, and truthful LLM/manual/fallback provenance.
- Ambiguous, contradictory, unknown-label, stale-baseline, invalid, and no-op requests never mutate local or provider state.
- Apply uses the approved normalized label change and performs no second interpretation call.
- Gmail preserves unrelated labels and confirms that the resulting `EA/` set exactly equals the approved result before reporting provider success.
- Provider transport or readback mismatch is retryable and never appears confirmed.
- Multi-label/relative changes cannot select matching-existing or future-rule scopes in this slice.
- Proton permits only verified additive behavior; unsupported operations are blocked before mutation.
- No send, delete, Trash, Spam, archive, unsubscribe, sender blocking, or provider-filter behavior is added.
- Focused tests, controlled-browser coverage, and the repository-wide suite pass.

## Explicitly deferred

- Multi-label future rules or matching-existing rewrites.
- Migration of singular rule and memory schemas.
- Proton label removal or replacement.
- Any change to Inbox-removal policy. Live cases involving Promotions or LowValue remain excluded.
