# Title

Browser workbench fetch-more-batches action for stored review workflow

## Type

HITL

## User-visible goal

Let the founder request another bounded Gmail inbox batch from inside the existing local browser workbench, so reviewing multiple trial batches does not require leaving the simple UI, while keeping Gmail mutation behavior unchanged.

## Scope

- Extend the existing browser workbench with one explicit `Fetch another batch` action
- Reuse the already-proven live Gmail manual fetch behavior and stored batch contracts
- Keep fetch bounded to one configured Gmail account and inbox-only messages
- Keep the same skip-already-processed default used by the current CLI fetch flow
- Let the workbench surface the newly created stored batch in the local batch list after a successful fetch
- Keep the browser-triggered fetch as a foreground, founder-initiated action rather than background sync
- Keep browser review, actionability capture, and threshold summaries working against the same stored local data after fetch
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail label write-back from the browser UI
- inbox-removal mutation from the browser UI
- background polling or automatic periodic sync
- multi-account support
- changing Gmail scopes beyond what the existing fetch path already requires
- broad dashboarding or mailbox management UX

## Acceptance criteria

- A founder using the browser workbench can explicitly request another bounded inbox batch without dropping to the CLI
- The action reuses the existing live Gmail fetch rules, including skipping already processed messages by default
- A successful fetch creates a new stored batch that becomes visible in the browser workbench
- If no new messages are available, the workbench reports that cleanly without creating an empty batch
- Fetch failures are surfaced locally without breaking the existing stored review workbench
- The public flow performs no Gmail writes, no inbox-removal mutations, and no delete/trash behavior

## Expected behavior

- The workbench shows a visible fetch action such as `Fetch another batch`
- Triggering that action runs the existing bounded live Gmail fetch flow for the configured account
- The action remains founder-initiated and local; there is no background polling
- On success, the workbench refreshes or returns a visible status showing the new stored batch id and its pending-review count
- On partial success, successfully fetched messages still become a stored batch and fetch failures remain locally visible
- On no-new-mail, the workbench shows an explicit no-new-batch result
- The slice does not apply labels, remove `INBOX`, or enable automation from the browser UI

## Expected tests or verification

- Test that the browser workbench exposes the fetch action without requiring a selected stored batch
- Test that invoking the action uses the existing fetch seam and creates a new stored batch on success
- Test that no-new-mail results are rendered cleanly without creating an empty batch
- Test that fetch failures are surfaced locally while preserving any successful fetch results
- Test that the workbench still performs no Gmail write-back, inbox-removal mutation, or delete/trash behavior through its public flow
- Manual verification on the founder test account after Founder approval

## Dependencies/order

- Follows issue `018` as the next browser-workbench extension
- Reuses the existing live Gmail fetch path from issues `003` and `006`
- Should be approved before implementation because it introduces live Gmail read behavior into the browser UI

## Stop conditions requiring Founder review

- The slice pressures the workbench toward background syncing instead of an explicit fetch action
- The browser fetch path appears to require broader Gmail scopes or broader mailbox access than the existing fetch flow
- The slice starts mixing in Gmail label write-back or inbox-removal mutation
- The workbench begins drifting into a broad mailbox dashboard instead of a bounded review workbench
