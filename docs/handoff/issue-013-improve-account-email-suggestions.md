# Handoff: Issue 013 Improve `EA/Account` Suggestions

## Context

This note records the implementation and verification checkpoint for [docs/issues/013-improve-account-email-suggestions-for-stored-live-batches.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/issues/013-improve-account-email-suggestions-for-stored-live-batches.md).

This follows the second-batch MVP validation in [docs/handoff/issue-012-second-batch-mvp-acceptance-run.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/issue-012-second-batch-mvp-acceptance-run.md).

## What Changed

- Narrowly improved stored live-batch suggestion detection for `EA/Account` in `src/fixture_classifier.py`
- Added one bounded account-message detection seam that now recognizes:
  - strong account/security alerts
  - account-access notices from clear sender/body evidence
  - account-document delivery messages from strong stored local signals
- Kept the change local-only:
  - no Gmail API calls
  - no Gmail writes
  - no OAuth or scope changes
  - no taxonomy changes
- Improved the user-visible review explanation text for the newly recognized account-message cases so suggestion and explanation now agree
- Added regression coverage in `tests/test_live_gmail_review_cli.py` for:
  - strong account/security/account-document suggestions
  - weak account-like updates staying unlabeled

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors:

- stored live Gmail batches can now surface useful `EA/Account` suggestions for the concrete account-message gap observed in issue `012`
- weak account-like updates are still allowed to remain unlabeled rather than being forced into `EA/Account`
- the existing review-item contract and live review reprocessing flow remain unchanged
- the slice performs no Gmail writes and no live Gmail API calls in its public flow

## Validation

Focused tracer-bullet coverage:

```bash
python3 -m unittest \
  tests.test_live_gmail_review_cli.LiveGmailReviewCliTests.test_main_reprocesses_account_style_live_messages_into_ea_account_suggestions_before_review -v
```

Guardrail coverage:

```bash
python3 -m unittest \
  tests.test_live_gmail_review_cli.LiveGmailReviewCliTests.test_main_keeps_weak_account_like_updates_unlabeled_before_review -v
```

Related regression verification:

```bash
python3 -m unittest tests.test_live_gmail_review_cli tests.test_gmail_fetcher tests.test_fixture_classifier -v
```

Result at the latest checkpoint: `27 tests passed`.

AFK-safe local reclassification check on the stored second live batch:

```text
19ecf8ed0a6789f2 ['account-security'] Account-related document delivery that likely belongs with other account notices.
19ecc983470942f1 ['account-security'] Account security or account-access alert that likely needs to stay easy to find.
19eca401dc4973b3 [] Social notification that looks low priority unless you are actively tracking it.
```

This confirms the bounded goal:

- the two concrete missed account-style messages from the batch-2 acceptance run now surface `EA/Account`
- the weaker LinkedIn security-style notification remains unlabeled rather than being over-classified

## Important Constraints

- The change is intentionally narrow and should not be treated as a broad classifier rewrite
- Detection still relies only on already-stored local fields such as sender, subject, snippet/body, and Gmail category labels already present in batch data
- The slice preserves the current fixed taxonomy and existing review/write workflow

## Risks Or Open Questions

- The account-message improvement is grounded in the real batch-2 misses, but future live batches may surface adjacent account cases that still need refinement
- Suggestion quality outside the bounded `EA/Account` gap was not expanded in this slice

## Recommended Next Step

- Resume the normal issue-first process and ask what the next concrete pain is now
- Do not assume the next slice is another classifier improvement unless a new live batch or review pass shows that it is the current bottleneck
