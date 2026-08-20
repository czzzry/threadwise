# Review Semantics Preflight

Status: Partially superseded for automatic initial classification
Current as of: 2026-08-20
Superseded by: `docs/decisions/always-label-successfully-processed-mail.md` where this document treats low confidence as an automatic unlabeled outcome

Purpose: lock only the minimum review semantics needed for the first implementation slices.

## Decisions

- `unlabeled` remains a valid explicit reviewed outcome when the user rejects every Threadwise label or identifies a taxonomy gap. Automatic initial classification instead applies the best available tentative label and uses confidence to prioritize review.
- Applied labels are capped at 3 per message. Any additional ranked candidates stay visible as near-misses and are not applied.
- A near-miss means: "plausible candidate worth showing in review, but not strong enough to apply." Near-misses are for reviewer context, not hidden auto-fallback labels.
- Confidence bands are reviewer aids, not truth claims:
  - `high`: suggestion looks strong enough that approval should often be quick
  - `medium`: plausible but should receive normal scrutiny
  - `low`: weak suggestion; reviewer should expect edits, rejection, or `unlabeled`
- Review action outcomes:
  - `approve`: keep the proposed applied labels
  - `edit`: reviewer changes applied labels, including choosing `unlabeled`
  - `reject`: no agent labels should be applied from this prediction
- Obvious compatibility rules for v1:
  - `reply-needed` may co-exist with descriptive labels
  - `account-security` may co-exist with `reply-needed`
  - `newsletter` and `promotions` should not both be applied to the same message
  - `receipt-billing` and `shopping-order` may co-exist when both materially help retrieval
  - `spam-low-value` should not co-exist with `reply-needed`
  - `unlabeled` is mutually exclusive with every applied label

## Out of Scope

- broader taxonomy philosophy
- sender-level policy rules
- time-aware behavior
- automation policy
- confidence calibration work

## Founder Review Stops

Seek Founder review before implementation if any slice appears to require:

- more than 3 applied labels
- a new confidence model beyond the three review bands
- compatibility rules beyond the obvious cases above
- treating `reject` as anything other than "do not apply agent labels from this prediction"
