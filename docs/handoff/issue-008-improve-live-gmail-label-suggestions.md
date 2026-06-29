# Handoff: Issue 008 Improve Live Gmail Label Suggestions

## Context

This note records the implementation checkpoint for [docs/issues/008-improve-live-gmail-label-suggestions.md](docs/issues/008-improve-live-gmail-label-suggestions.md).

This follows the live review and write-back checkpoint in [docs/handoff/issue-007-live-review-and-ea-writeback.md](docs/handoff/issue-007-live-review-and-ea-writeback.md).

## What Changed

- Stored live Gmail batches are now reprocessed locally from `raw_messages` before review when the existing item has weak or absent suggestions
- Reprocessing uses only already-stored Gmail data: snippet, subject, sender, Gmail category labels, `List-Unsubscribe`, and `Precedence`
- A shared Gmail message normalizer now feeds both fetch-time classification and stored-batch reclassification
- The live classifier now recognizes stronger low-value promotional, social-notification, and bulk-update patterns while keeping the existing fixed taxonomy
- Stored reviewed items remain frozen when a batch is reopened; reprocessing only targets unreviewed weak-suggestion items

## Acceptance Status

Automated acceptance for the bounded local slice is met.

Covered behaviors:

- Stored live-style Gmail batches can be reprocessed locally into review-ready suggestions without any Gmail client dependency
- Representative live-style promotional messages now surface useful `EA/Promotions` and `EA/LowValue` suggestions through the public fetch/review flow
- Review item shape remains compatible with the existing review CLI
- Reopened reviewed items keep their frozen state instead of being overwritten by reclassification
- Public flow still performs no Gmail writes unless the explicit confirmed write path is used

## Validation

Focused regression verification:

```bash
python3 -m unittest tests.test_fixture_classifier tests.test_gmail_fetcher tests.test_live_gmail_review_cli tests.test_fixture_review_loop -v
```

Full regression verification:

```bash
python3 -m unittest discover -s tests -v
```

Result at the latest checkpoint: `67 tests passed`.

## Important Constraints

- This slice stays local to stored data and does not add Gmail API reads, Gmail writes, OAuth changes, retry workflow, or UI expansion
- The classifier still uses only the approved fixed taxonomy from [docs/archive/alignment-v1-gmail-mvp.md](docs/archive/alignment-v1-gmail-mvp.md) and [docs/archive/prd-v1-gmail-mvp.md](docs/archive/prd-v1-gmail-mvp.md)
- Manual verification against the real stored batch was not run in this session because that would involve private email content and should be explicitly approved first

## Risks Or Open Questions

- The new live-suggestion heuristics are intentionally narrow and deterministic; some real messages will still remain `unlabeled`
- The current rules are strongest for promotional and low-value bulk mail; if the next pain point is setup/onboarding or nuanced social mail, that should be handled as a separate bounded follow-up rather than broad classifier infrastructure
- Manual verification on one real stored batch is still desirable before closing the issue operationally

## Recommended Next Step

Ask for approval to run one manual local review pass on the existing stored live batch to confirm the improved suggestions are materially better on real inbox data without triggering Gmail writes.
