# Alignment

## Product intent

The first useful version of the email agent should correctly label and categorize messages in a real, non-primary Gmail inbox, then use those labels to reduce inbox noise with bounded, reversible automation.

The current near-term goal is no longer review-everything. The goal is:

- auto-apply labels when the system already has a current suggestion
- remove `INBOX` only for low-value or promotional mail
- leave only unlabeled exceptions for manual inspection

Longer term, those labels may drive broader automation such as surfacing only actionable mail and producing a weekly audit/report.

## Candidate first Gmail-connected product slice

Build a lightweight local web app that:

- connects to one Gmail account via single-user local OAuth
- manually fetches inbox messages in batches
- classifies messages at the message level
- shows a batch review UI before any write-back
- stores predictions, review decisions, and audit history locally
- writes approved labels back to Gmail under an `EA/` namespace

This slice is approved for PRD planning, not implementation. The first implementation issue may be smaller once the PRD and issue decomposition are complete.

Out of scope for this slice:

- autonomous actions beyond writing approved labels
- background polling
- weekly report generation
- multi-provider support beyond keeping the internal model provider-agnostic where easy

## Product decisions

### Workflow

- Current control model: `fetch -> suggest -> auto-apply suggested labels -> manually inspect unlabeled exceptions`
- Manual review remains available as a fallback path, not the default path
- Review happens in a separate lightweight local web app, not inside Gmail
- A post-run summary is required

### Classification model

- Unit of classification: individual messages, not threads
- Goal: optimize for retrieval first, automation later
- Multiple labels are allowed, capped at 3 visible applied labels per message
- Ranked near-miss labels are also stored
- `unlabeled` is allowed and must still be reviewable
- Label compatibility should be explicit, not left entirely to model behavior

### Initial taxonomy

Primary labels:

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

Secondary/state label:

- `reply-needed`

Notes:

- `reply-needed` is higher-risk and review-heavy in v1
- `newsletter` stays a base content label; wanted vs unwanted is deferred to future sender-level preference/policy

### Review UI

Each review item should show:

- sender
- subject
- date
- agent interpretation
- suggested labels
- near-miss labels
- confidence band and numeric score
- approve/edit/reject controls
- a way to open the underlying email

Confidence scores in v1 are review aids and ranking heuristics, not calibrated truth probabilities.

Default review ordering:

1. `reply-needed`
2. `account-security`
3. newest first

### Gmail integration

- Current scope: read messages, write suggested labels, and remove `INBOX` for low-value or promotional mail only
- Labels are written under a dedicated Gmail namespace such as `EA/travel`
- The app may auto-create missing `EA/` labels
- One Gmail account only in v1
- Gmail output label names should be configurable
- Internal message/label/review model should remain provider-agnostic where easy
- Use neutral field names where practical, but do not design a generic multi-provider architecture in v1

### Storage and state

- Store full email content locally in v1
- Store predictions, scores, interpretations, near-misses, review outcomes, sender history, and timestamps locally
- Keep OAuth credentials separate from message data
- Track sender history by normalized sender email address
- Local email storage must be gitignored, excluded from logs, easy to delete, and stored separately from credentials
- Private email content must not be copied into Linear, Obsidian, PRD examples, or repo docs

State model:

- `processed`: the system generated a prediction
- `reviewed`: a human approved, edited, rejected, or approved `unlabeled`
- `reviewed` may also include an `auto-approve` review action when the system applied suggested labels without manual review

### Fetching and rollout

- Manual batch fetch only in v1
- Fetch inbox messages only
- Skip already processed messages by default
- Start with trial batches, then widen coverage once trust is earned
- Already reviewed messages remain frozen by default
- Reprocessing is a later explicit operation and must preserve audit history

### Failure handling

- Track Gmail write status per message
- Failed writes should be retryable without re-review if the approved labels did not change
- Do not silently rewrite history during reclassification or retries

## Success criteria

The current product is useful if:

- real Gmail batches can be fetched and auto-labeled end-to-end
- the majority of messages receive a useful label without manual review
- only a small unlabeled exception set remains for inspection
- `INBOX` is removed only for low-value or promotional mail
- false positives remain especially visible for `spam-low-value`, `account-security`, `personal`, and `reply-needed`
- retrieval is meaningfully improved
- exception volume is measurable

`Useful` means: a label you would want present later for search, filtering, or review.

## Lightweight reuse/build-vs-buy questions

- Gmail API and OAuth scopes: keep scopes as narrow as possible for reading messages and writing approved labels only
- Local web UI: prefer a lightweight local app over a Gmail extension in v1
- Local storage: use a simple local store that is easy to inspect and delete; do not over-design persistence yet
- Email parsing and message fields: reuse Gmail message fields and headers where practical before building custom parsing layers
- Classification approach: start with a practical workflow that supports review, metrics, and iteration before more complex training or automation systems

## Future direction

Now that bounded autonomy has been accepted, later slices may add:

- sender-level preferences such as wanted vs unwanted newsletters
- more direct daily-run automation
- time-aware handling for expiring/security-code messages
- reclassification jobs for explicit backfills
- a hybrid weekly scorecard covering outcomes, quality, and exceptions
- broader inbox-clearing workflows toward zero inbox
- additional providers such as Hotmail and ProtonMail

## Appendix: Compressed Grill-Me Record

1. V1 promise: correctly label and categorize messages.
2. Labels will eventually drive workflow, but only after a staged rollout.
3. First real-inbox slice uses a non-primary Gmail account.
4. Control model: suggest, review in batch, then apply approved labels.
5. Feedback in v1 is stored for evaluation, structured for later reuse.
6. Classification is message-level.
7. Optimize for retrieval first.
8. Taxonomy should be mostly descriptive with limited state/context labels.
9. Multi-labeling is allowed with a 3-label visible cap.
10. Store applied labels and near-miss predictions.
11. Success target: test in batches such as 5 x 50 and aim for about 80% useful labeling, while tracking label-specific quality.
12. A useful label is one worth having later for search/filter/review.
13. Long-term inbox policy: only actionable mail stays visible.
14. Actionable means unresolved human decision, response, or time-bound awareness.
15. Time-sensitivity should be inferred later by policy.
16. Review items should show sender, subject, date, interpretation, labels, near-misses, confidence, controls, and open-email action.
17. Review should happen in a lightweight local web app.
18. Gmail scope: read messages plus write approved labels only.
19. Gmail write-back should use an `EA/` namespace.
20. One Gmail account in v1; internals stay provider-agnostic.
21. Keep taxonomy fixed for v1; only Gmail output names are configurable.
22. `unlabeled` is allowed.
23. `unlabeled` outcomes must still be reviewed and may be marked as taxonomy gaps.
24. Show confidence bands and rankings, with optional numeric scores.
25. Order review newest-first with priority overrides.
26. Priority overrides start with `reply-needed` and `account-security`.
27. `reply-needed` is a careful, review-heavy label in v1.
28. Apply multiple labels only when they add independent value; otherwise use near-misses.
29. Define compatibility rules explicitly.
30. Record sender-level review history for future preference handling.
31. Sender history key: normalized sender email address.
32. Start with manual batches, then widen coverage later.
33. Process only unreviewed mail by default; reprocessing comes later.
34. Taxonomy/classifier changes create new records, not overwritten history.
35. Reviewed messages stay frozen unless explicitly reprocessed later.
36. Keep `processed` and `reviewed` separate, with room for `auto-applied`.
37. No extra final confirmation is needed, but a post-batch summary is.
38. Batch summary should include reviewed/labeled/unlabeled totals and per-label counts.
39. Track reviewer label changes as the main review-friction metric.
40. First slice reviews inbox messages only.
41. The app may create missing Gmail labels automatically.
42. Broad local storage is acceptable.
43. Full email bodies may be stored locally in v1.
44. Auth model: single-user local OAuth.
45. Fetching is manual only in v1.
46. Manual fetch skips already processed messages by default.
47. Failed Gmail writes are retryable without re-review.
48. Weekly reporting should eventually be a hybrid scorecard.
49. Weekly reporting itself is deferred to a later slice.
50. Candidate first Gmail-connected product slice for PRD planning: a lightweight local web app that fetches Gmail batches, classifies messages, supports batch review, stores audit history locally, and writes approved `EA/` labels back. The first implementation issue may be smaller after PRD and issue decomposition.
