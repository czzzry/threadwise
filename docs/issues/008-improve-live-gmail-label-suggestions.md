# Title

Improve label suggestions for stored live Gmail batches

## Type

AFK

## User-visible goal

Let the user open a previously fetched live Gmail batch and usually find useful suggested `EA/` labels already present on the review items, so manual review is mostly approving or lightly editing suggestions rather than classifying each message from scratch.

## Scope

- Reuse previously fetched local Gmail batch data only
- Improve suggestion generation for stored live Gmail review items before any write-back step
- Prefer using already-fetched local message fields such as snippet, subject, sender, headers, and other stored payload data already available in local batch files
- Reuse the existing canonical taxonomy and review-item contract
- Preserve the existing review ordering, review semantics, and dry-run/write gating from issue `007`
- Improve interpretation text only where it materially helps review the label suggestion
- Keep the work local and deterministic enough to test through stored representative live-style payloads
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail writes or live Gmail API calls
- OAuth or token changes
- retry workflow
- UI expansion beyond the current CLI review surface
- background fetching or re-fetching messages from Gmail
- taxonomy expansion or new label invention without Founder approval
- model platform work or broad classifier infrastructure unrelated to this slice

## Acceptance criteria

- A stored live Gmail batch can be reprocessed locally so its review items usually contain useful suggested `EA/` labels before review begins
- Suggestion quality improves using already-fetched local batch data rather than new Gmail API calls
- The suggestion flow keeps using only the approved fixed taxonomy from the existing product docs
- Review items still conform to the existing review-item contract expected by the review flow
- Weak-confidence or no-fit cases can still remain `unlabeled`; the slice does not force low-quality guesses
- The slice performs no Gmail writes and no live Gmail API calls anywhere in its public flow

## Expected tests or verification

- Test that stored live-style Gmail batch items are reclassified locally into review-ready suggestions without any Gmail client dependency
- Test that representative live-style messages now receive the expected useful `EA/` label suggestions through the public suggestion flow
- Test that weak or unmatched messages can still remain `unlabeled`
- Test that the improved suggestion flow preserves the existing review-item shape used by the review CLI
- Test that this slice performs no Gmail write or live Gmail API action through its public flow
- Manual verification on one stored live batch after automated tests pass

## Dependencies/order

- Depends on issue `007`
- Should start only after the issue draft is approved for bounded local suggestion-quality work
- Follow with the retry/write-status follow-up slice after suggestion quality is no longer the dominant review pain point

## Stop conditions requiring Founder review

- The slice appears to require a taxonomy change rather than better use of existing stored data
- Useful live suggestions appear to require new external integrations, live Gmail calls, or broader model infrastructure
- The work pressures the project toward UI expansion or retry/write workflow scope instead of bounded local suggestion improvement
