# PRD

## Problem Statement

The current inbox workflow is noisy and manual. Important messages are mixed with low-value mail, and it takes too much effort to consistently label messages in a way that makes later retrieval easier. The product has now proven it can classify many real emails well enough to apply labels automatically, so the next scope checkpoint is to turn that into a practical operating model rather than continue optimizing a review-first experiment.

## Solution

Use a lightweight local Gmail workflow for one non-primary account that:

- fetches inbox messages in manual batches
- classifies them at the message level
- auto-applies any current suggested `EA/` labels
- removes `INBOX` only for low-value and promotional mail
- leaves only unlabeled exceptions for manual review
- stores outcomes and audit state locally

Manual review remains available for exception handling and spot checks, but it is no longer the default control model.

## User Stories

1. As a Gmail user, I want to fetch a bounded batch of inbox messages manually, so that I stay in control during evaluation.
2. As a Gmail user, I want the app to classify individual messages rather than whole threads, so that mixed threads do not corrupt retrieval.
3. As a Gmail user, I want suggested labels before anything is written back, so that I can review the system safely.
4. As a Gmail user, I want labels optimized for retrieval first, so that I can reliably find the right messages later.
5. As a Gmail user, I want the app to allow multiple labels on one message, so that messages with multiple useful dimensions are not flattened into one choice.
6. As a Gmail user, I want applied labels capped to a small number, so that the output remains readable and useful.
7. As a Gmail user, I want the app to keep ranked near-miss labels, so that I can see where the system was close even when a label was not applied.
8. As a Gmail user, I want `unlabeled` to be a valid outcome, so that the system does not force bad guesses.
9. As a Gmail user, I want to review unlabeled messages too, so that uncertainty is visible and correctable.
10. As a Gmail user, I want the app to show a short interpretation of what each email is, so that I can review the model's understanding faster than by labels alone.
11. As a Gmail user, I want to see sender, subject, date, labels, near-misses, and confidence cues together, so that batch review is efficient.
12. As a Gmail user, I want confidence shown as heuristics rather than false precision, so that I do not over-trust model scores.
13. As a Gmail user, I want `reply-needed` and `account-security` items prioritized in review, so that higher-risk mail gets attention first.
14. As a Gmail user, I want to edit, approve, or reject label suggestions, so that my review decisions are explicit.
15. As a Gmail user, I want corrected messages and label changes to be tracked, so that the system can measure review friction and weak spots.
16. As a Gmail user, I want the app to write labels to Gmail automatically when they are already within the trusted current operating model, so that I do not have to manually review every message.
17. As a Gmail user, I want Gmail labels namespaced under `EA/`, so that experimentation does not pollute my existing organization.
18. As a Gmail user, I want the app to create missing `EA/` labels automatically, so that setup stays lightweight.
19. As a Gmail user, I want reviewed messages to stay frozen by default, so that history does not silently change.
20. As a Gmail user, I want failed Gmail writes to be retryable without re-review, so that API failures do not create duplicate work.
21. As a Gmail user, I want local storage of review history and message content, so that the app can support fast iteration and later analysis.
22. As a Gmail user, I want private email content kept out of repo docs and product artifacts, so that planning materials remain safe to share.
23. As a product lead, I want automation to stay bounded and reversible, so that faster progress does not require perfect classification first.
24. As a product lead, I want the internal model to use provider-neutral concepts where easy, so that later provider support is possible without forcing a framework now.
25. As a product lead, I want explicit success criteria for label usefulness and review effort, so that continuation decisions are evidence-based.
26. As a product lead, I want the PRD to define testing expectations before implementation, so that slices do not backfill weak tests after code exists.

## Implementation Decisions

- Scope the product to one non-primary Gmail account in v1, using single-user local OAuth.
- Gmail OAuth and write scope are a material product risk. Request the narrowest scopes that support reading messages and writing approved labels only.
- Use a lightweight local web app as the review surface. Do not build a Gmail extension in v1.
- Treat the current slice as Gmail-connected and Gmail-specific at the integration edge, while keeping internal concepts neutral where easy: message, label, prediction, review decision, write status.
- Do not build a full multi-provider abstraction or framework in v1.
- Fetch inbox messages manually in bounded batches. Do not poll in the background yet.
- Operate at message level, not thread level.
- Optimize labels for retrieval and understanding first, then use those labels for bounded automation.
- Support a fixed initial taxonomy:
  - `travel`
  - `receipt-billing`
  - `shopping-order`
  - `newsletter`
  - `promotions`
  - `account-security`
  - `calendar-event`
  - `personal`
  - `job-related`
  - `spam-low-value`
  - `reply-needed`
- Treat `reply-needed` as a stateful, higher-risk label that can co-exist with descriptive labels.
- Allow multiple applied labels with a visible cap of 3; store additional ranked candidates as near-misses.
- Allow `unlabeled` as an explicit outcome and support taxonomy-gap marking during review.
- Define basic compatibility rules between labels rather than leaving all combinations to the model.
- Exact label compatibility rules must be resolved in the relevant implementation slice before implementation begins.
- Present each review item with sender, subject, date, interpretation, suggested labels, near-misses, confidence heuristics, and review controls, plus a way to open the underlying email.
- Order review items by priority first for `reply-needed` and `account-security`, then by recency.
- Treat confidence numbers as ranking aids, not calibrated truth probabilities.
- Write current suggested labels only to a dedicated Gmail namespace such as `EA/travel`.
- Make Gmail output label names configurable, but keep the taxonomy itself fixed for this slice.
- Permit the app to create missing Gmail labels under the agent namespace automatically.
- Store message content, predictions, interpretations, near-misses, review outcomes, sender history, and timestamps locally.
- Keep local message storage gitignored, separate from credentials, easy to delete, and excluded from logs.
- Do not place private email content in repo docs, PRD examples, issue trackers, or knowledge tools such as Obsidian.
- Treat private email content, OAuth credentials, inbox access, and label write-back as privacy/security-sensitive constraints throughout implementation.
- Track sender history by normalized sender email address to support later sender-level preference features.
- Distinguish processing state from review state:
  - `processed`: prediction created
  - `reviewed`: approved, edited, rejected, approved as `unlabeled`, or `auto-approve`
- Skip already processed messages by default during manual fetches.
- Keep reviewed messages frozen by default; if reprocessing is added later, it must preserve audit history and produce reviewable diffs before Gmail label changes.
- Track Gmail write status per message and allow retry without re-review when the approved labels have not changed.
- Require a minimal post-batch summary covering: messages reviewed, messages labeled, unlabeled count, per-label counts, and reviewer label changes.
- Structure batch summaries as the precursor to later weekly reporting, but do not build weekly reporting in this slice.

## Testing Decisions

- Good tests verify public behavior and user-visible outcomes, not private implementation details.
- Each implementation slice must define expected behavior and tests before implementation begins.
- Use `/tdd` or a red-green-refactor workflow where practical for implementation slices.
- Codex must not write tests after implementation merely to bless code it already wrote.
- If tests change after implementation begins, the reason must be explained and the acceptance criteria must not be weakened.
- Testing should prefer the highest practical seam:
  - classification input/output behavior
  - batch review state transitions
  - Gmail write-back behavior at the integration boundary
  - user-visible summaries and status reporting
- Likely modules/seams to test in implementation slices:
  - message ingestion and normalization from Gmail responses
  - classification result shaping, including applied labels, near-misses, and unlabeled outcomes
  - review decision handling and state transitions
  - Gmail label mapping and write-back request construction
  - failure handling and retry behavior for write-back
  - batch summary generation
- Tests should focus on externally observable outcomes such as:
  - which messages appear in a review batch
  - how labels and near-misses are exposed
  - whether reviewed messages can be written back correctly
  - whether failed writes remain retryable without re-review
  - whether summaries reflect counts and review changes correctly
- The first implementation slice may include only the minimum test setup required for that slice. Do not spin up a standalone testing-infrastructure project.

## Testing and Verification Strategy

- Before implementation of any slice, define:
  - the slice boundary
  - expected user-visible behavior
  - the tests that will prove it
- Prefer tests through public interfaces such as UI-visible state, persisted review outcomes, request/response boundaries, and provider-facing write behavior.
- Avoid tests that assert internal helper structure, private methods, or incidental implementation details.
- Favor small, slice-specific tests over broad framework work.
- End each implementation slice with a verification summary covering:
  - tests run
  - behavior verified
  - manual checks performed
  - known gaps

## Out of Scope

- deleting, trashing, or archiving mail
- background polling or live inbox monitoring
- weekly report generation
- sender preference automation such as wanted vs unwanted newsletters
- time-aware expiration logic for security-code messages
- multi-provider support beyond neutral naming where easy
- a generic provider abstraction layer
- large-scale backfill or automatic reclassification of previously reviewed mail
- broad standalone testing-infrastructure work

## Further Notes

- Success for this slice should be judged on whether real Gmail batches can be reviewed end-to-end, whether at least roughly 80% of messages get at least one useful label across trial batches, whether per-label quality is measurable, and whether retrieval improves.
- Sensitive false positives matter especially for `spam-low-value`, `account-security`, and `reply-needed`.
- Review effort should be measured with reviewer label changes, not only message counts.
- This PRD should lead to small vertical implementation slices rather than one large build.
- Because this product handles private email, slices should preserve least-privilege access and avoid broadening Gmail permissions or write capabilities without explicit approval.
