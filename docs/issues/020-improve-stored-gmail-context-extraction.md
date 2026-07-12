# Title

Improve stored Gmail context extraction for ambiguous review work

## Type

HITL

## User-visible goal

Let the founder review ambiguous Gmail messages with richer local context, so the next fresh `50`-message experiment can improve acceptance consistency without expanding Gmail mutation scope.

## Scope

- Improve local normalization of fetched Gmail messages so stored review items capture more useful context from raw Gmail payloads when available
- Prefer readable text extracted from raw payload parts over relying only on the short Gmail API `snippet`
- Keep the richer context stored in the existing local batch artifacts used by browser and CLI review
- Reuse the existing browser review UI support for expandable context when `snippet` or `body` is present
- Keep the slice local and read-only with respect to Gmail
- Preserve enough stored review data that reviewed `EA/` label decisions can be applied live later in a separate approved slice without re-reviewing old batches
- Focus context improvement on the message classes currently causing review friction:
  - empty or weak current context
  - edited messages
  - unlabeled messages
  - account/security/code-style messages
  - travel and order-lifecycle messages

## Non-goals

- Adding a new taxonomy label such as `financial-account`
- Gmail label write-back from the browser UI
- Retroactive mandatory re-review of old stored batches
- Inbox-removal replay or any other Gmail visibility mutation
- Background syncing, subscription management, or unsubscribe automation
- A broad email parsing framework beyond what the current review workflow needs

## Acceptance criteria

- Newly fetched Gmail messages store more useful review context locally when the raw Gmail payload contains readable text parts
- The normalized review item can preserve both short preview text and richer extracted body text when available
- Browser and CLI review flows can benefit from the richer stored context without changing their bounded local review contract
- The slice performs no Gmail writes, no inbox-removal mutations, and no delete/trash behavior
- The next fresh `50`-message experiment can be run against the same success metrics:
  - `spam-low-value` false positives remain at `0`
  - unchanged acceptance improves from the current `74%` toward `>= 80%`
  - unlabeled rate does not worsen, ideally improves

## Expected behavior

- When a Gmail payload includes `text/plain` content in message parts, the local normalizer extracts that readable text into the stored review item body
- When only `text/html` is available, the local normalizer extracts a readable text fallback rather than storing only the Gmail snippet
- The short Gmail snippet remains available as lightweight preview context
- The browser review page can keep showing `More context` when richer stored context exists
- The local CLI review flow can also benefit from richer stored context through the same normalized item fields
- Old stored batches may be enriched locally later if useful, but success for this slice is measured only on a fresh `50`-message batch

## Expected tests or verification

- Test that multipart Gmail payloads with `text/plain` parts normalize into readable review-item body text
- Test that `text/html` payloads fall back to readable extracted text when no plain-text part exists
- Test that the normalized item preserves the Gmail snippet separately from the richer body text
- Test that the fetch flow persists the improved normalized context into stored batch items
- Run the relevant unit test suites for normalizer, fetcher, and local browser review UI

## Dependencies/order

- Follows issue `019` after the founder reached the `200`-message checkpoint
- Reuses the existing stored batch artifact format and review UI rather than introducing a new review store
- Keeps later live `EA/` replay support as a separate follow-up slice

## Stop conditions requiring Founder review

- The slice starts drifting into live Gmail mutation or inbox-policy automation
- The context extraction work pressures the taxonomy to expand before the next fresh batch is reviewed
- The implementation requires broad parsing infrastructure instead of a bounded improvement to the current review workflow
