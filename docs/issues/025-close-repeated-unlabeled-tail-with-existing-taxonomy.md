# Status

Historical context
Current as of: 2026-06-23
Implemented in: `src/fixture_classifier.py` and `tests/test_fixture_classifier.py`
Superseded by: current post-issue-040 slice selection should use `docs/v2-issue-map.md` plus fresh triage

# Title

Close the repeated unlabeled tail with existing taxonomy

## Type

HITL

## User-visible goal

Reduce the last repeated pockets of unlabeled review items by classifying a small set of recurring reminder, receipt, and low-value bulk-message patterns into the existing taxonomy.

## Scope

- Tighten the local classifier only
- Classify LinkedIn saved-job expiry reminders into `job-related`
- Classify Google Play order or subscription charge receipts into the existing retrieval taxonomy
- Classify explicitly solicited Steam wishlist sale reminders into the existing promo taxonomy
- Classify obvious low-value bulk reminders or digests such as apartment open-house reminders and IMF publications mail into `spam-low-value`
- Keep the slice limited to repeated patterns already seen in refreshed real batches

## Non-goals

- Handling every remaining unlabeled message type
- New labels or taxonomy expansion
- Gmail mutation behavior changes
- Broad legal, housing, commerce, or media-message policy redesign

## Acceptance criteria

- LinkedIn saved-job expiry reminders like `your saved job is expiring tomorrow` surface `EA/JobRelated`
- Google Play order or subscription receipts surface `EA/ShoppingOrder`
- Steam wishlist sale reminders surface `EA/Promotions`
- IMF publications digests and apartment open-house reminders surface `EA/LowValue`
- Existing LinkedIn direct-message and job-alert behavior continues to work

## Expected tests or verification

- Test LinkedIn saved-job expiry reminders classify to `job-related`
- Test Google Play order or subscription receipts classify to `shopping-order`
- Test Steam wishlist sale reminders classify to `promotions`
- Test IMF publications digests classify to `spam-low-value`
- Test apartment open-house reminders classify to `spam-low-value`
- Re-run the relevant classifier, stored-batch, fetcher, and local-browser suites
