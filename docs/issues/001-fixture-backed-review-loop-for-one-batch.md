# Title

Fixture-backed review loop for one batch

## Type

AFK

## User-visible goal

Let the user review one bounded batch of fixture review items end to end, record explicit approve/edit/reject outcomes, see a minimal batch summary, and trust that reviewed items stay frozen by default, before any Gmail integration or model-generated suggestions exist.

## Scope

- Use fixture or sample messages only; no Gmail, OAuth, or write-back
- Show one review queue for one batch using the agreed review semantics
- Use hand-authored fixture review items that already contain the review-ready fields this slice needs
- Include sender, subject, date, short interpretation, suggested applied labels, near-misses, confidence band, and review controls
- Support `approve`, `edit`, `reject`, and reviewed `unlabeled`
- Apply review ordering rules within the fixture batch
- End the batch with a minimal summary: reviewed count, labeled count, unlabeled count, per-label counts, and reviewer label-change count
- Keep reviewed fixture items frozen by default so rerunning the same batch does not silently reopen or mutate them
- Define expected behavior and tests before implementation begins

## Non-goals

- real inbox access
- classification-generated suggestions
- Gmail label creation or write-back
- production OAuth
- background fetching
- weekly reporting
- broad persistence or architecture work beyond what this slice needs

## Acceptance criteria

- A fixture batch can be opened and reviewed without any external service dependency
- Each review item shows the fields promised in the PRD and follows the preflight review semantics
- Messages are ordered with `reply-needed` first, then `account-security`, then recency
- The reviewer can approve, edit, reject, or approve as `unlabeled` for every item in the batch
- The 3-label cap and near-miss behavior are visible in the review flow
- Completing the batch produces the minimum post-batch summary defined in the PRD
- Reopening or rerunning the same fixture batch does not silently re-review or rewrite already reviewed items
- The slice includes a written expected-behavior and test list before code implementation starts

## Expected tests or verification

- Fixture-driven test for review ordering across mixed labels and dates
- Test that rendered review data includes sender, subject, date, interpretation, applied labels, near-misses, and confidence band
- Test approve/edit/reject/`unlabeled` state transitions through the public review flow
- Test that incompatible or over-cap label outcomes are not exposed as applied labels
- Test that batch summary counts reflect approvals, edits, rejections, unlabeled outcomes, and label changes
- Test that already reviewed fixture items remain frozen by default on rerun
- Manual verification on one representative fixture batch

## Dependencies/order

- Depends on `docs/decisions/review-semantics.md`
- First real implementation slice

## Stop conditions requiring Founder review

- The fixture review loop seems to need new taxonomy terms or changed label semantics
- The minimum review fields no longer feel sufficient for safe review
- The slice starts to require real inbox data, classification generation, OAuth, or Gmail behavior to prove value
