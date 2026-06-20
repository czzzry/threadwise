# Title

Improve `EA/Account` suggestions for stored live Gmail batches

## Type

AFK

## User-visible goal

Let the user open a previously fetched live Gmail batch and more often find useful `EA/Account` suggestions already present on account/security/account-document messages, so review requires fewer manual edits on that concrete message class.

## Scope

- Reuse previously fetched local Gmail batch data only
- Improve suggestion generation only for the concrete gap exposed in the batch-2 acceptance run:
  - account/security alerts
  - account-access notices
  - account-related document delivery messages
- Prefer using already-fetched local fields such as sender, subject, snippet, and other stored payload data already present in local batch files
- Reuse the existing canonical taxonomy and review-item contract
- Preserve the existing review ordering, review semantics, and dry-run/write gating from issue `007`
- Keep weak-confidence cases allowed to remain unlabeled rather than forcing `EA/Account`
- Keep the work local and deterministic enough to test from stored representative live-style payloads
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail writes or live Gmail API calls
- OAuth or token changes
- retry workflow
- UI expansion beyond the current CLI review surface
- broad classifier overhaul across every label category
- taxonomy expansion or new label invention without Founder approval
- metrics/reporting utilities beyond what is needed to verify this bounded suggestion improvement

## Acceptance criteria

- A stored live Gmail batch can be reprocessed locally so representative account/security/account-document messages now receive useful `EA/Account` suggestions more often than in the batch-2 acceptance run
- The improvement uses only already-fetched local batch data rather than new Gmail API calls
- The suggestion flow keeps using only the approved fixed taxonomy from the existing product docs
- Review items still conform to the existing review-item contract expected by the review flow
- Weak or unmatched messages can still remain `unlabeled`; the slice does not force low-quality `EA/Account` guesses
- The slice performs no Gmail writes and no live Gmail API calls anywhere in its public flow

## Expected behavior

- The user reopens a stored live Gmail batch through the existing local reprocessing flow
- Representative account/security/account-document messages that previously surfaced with no suggestion can now surface `EA/Account` when the stored local evidence is strong enough
- The improvement is bounded to the concrete `EA/Account` under-suggestion pain and does not silently change review semantics or write behavior
- If a message is ambiguous or low-confidence, it can still remain unlabeled rather than receiving a forced account label
- Existing stronger suggestions for other message types should remain intact unless the bounded change clearly improves them too

## Expected tests or verification

- Test that stored live-style account/security/account-document messages now receive `EA/Account` suggestions through the public reclassification flow
- Test that ambiguous or weak account-like messages can still remain unlabeled
- Test that the improved suggestion flow preserves the existing review-item shape used by the review CLI
- Test that this slice performs no Gmail write or live Gmail API action through its public flow
- Manual verification by reopening a representative stored live batch after automated tests pass and confirming fewer manual `EA/Account` edits are needed

## Dependencies/order

- Depends on issue `008` for the existing live-batch suggestion-improvement path
- Justified by the concrete pain recorded in [docs/handoff/issue-012-second-batch-mvp-acceptance-run.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/issue-012-second-batch-mvp-acceptance-run.md)
- Should start only after the issue draft is approved for bounded local suggestion-quality work on `EA/Account`

## Stop conditions requiring Founder review

- The slice appears to require a taxonomy change rather than better use of existing stored data
- Useful `EA/Account` suggestions appear to require new external integrations, live Gmail calls, or broader model infrastructure
- The work pressures the project toward a broad suggestion-engine rewrite instead of a bounded fix for the observed account-message gap
- The improvement starts forcing low-confidence `EA/Account` labels where the safer outcome is still `unlabeled`
