# V2 Issue Map

Status: Current candidate next-slice map
Current as of: 2026-06-23
Builds on: `docs/checkpoints/current-operating-model-2026-06-22.md`
Current bounded PRD: `docs/prd.md`

This file is a candidate map, not an approved implementation sequence.

Do not treat it as authorization to code the next major slice without a focused grill, a current scope note or PRD, and triage.

## Current Position

The repo already proves the operating model through later slices beyond the original Gmail MVP, including:

- daily Gmail runs
- daily and weekly reports
- provider-aware artifacts
- ProtonMail read-only flows
- unsubscribe inventory and supported execution
- maintenance refactors for UI responsibilities and artifact contracts

The current bounded planning focus is Gmail trust hardening through `docs/prd.md` and `docs/issues/040-prove-bounded-gmail-autonomy-end-to-end.md`.

## Candidate Decision Lanes

### Trust / Safety / Evaluation

Possible focus:

- tighten the trust boundary for auto-action
- define clearer eval policy and thresholds
- make exception handling auditable and easier to inspect

### Exceptions / Review UX

Possible focus:

- improve the unlabeled-exception workflow
- reduce friction in the local review and workbench path
- make manual follow-up clearer for unsupported unsubscribe and edge cases

### Reporting / Decision Support

Possible focus:

- make daily and weekly reports more decision-useful
- add better trend, exception, and quality views
- improve operator understanding of what changed and why

### Provider Boundary

Possible focus:

- keep ProtonMail read-only and tighten that contract
- or explicitly decide what bounded ProtonMail write behavior, if any, should ever exist

### Subscription / Unsubscribe Productization

Possible focus:

- turn the inventory and execution slices into a clearer user-facing workflow
- document stronger safety rules for unsubscribe execution and manual fallback

## Selection Rule

Prefer the next slice that:

1. solves the most concrete current pain
2. improves the trustable daily operating model directly
3. does not broaden provider risk or inbox-action scope without explicit approval
4. is small enough to explain with one current PRD or scope note and one triaged issue

## Next-Step Rule

Before implementing from this map:

1. identify the actual current pain
2. run a focused grill on the smallest marketable and trustable next version
3. write one current PRD or scope note for that slice
4. triage the issue until it is ready
5. then implement
