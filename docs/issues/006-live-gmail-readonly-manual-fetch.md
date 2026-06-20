# Title

Live Gmail read-only manual fetch into the existing review queue

## Type

HITL

## User-visible goal

Let the user manually fetch a bounded batch of real messages from one non-primary Gmail inbox and review them in the existing queue, still with no Gmail write-back.

## Scope

- Connect one non-primary Gmail account via single-user local OAuth on first run, then reuse the stored local token on later runs
- Trigger fetch through a manual CLI command
- Fetch inbox messages only, with a small default batch size and optional override
- Read full Gmail message payloads
- Persist raw Gmail payloads locally in a gitignored store separate from credentials
- Normalize fetched messages into the existing review-item contract
- Classify fetched messages immediately in the same manual run
- Insert review-ready items into the existing review queue using the same persisted shape as fixture-backed items
- Add only minimal source metadata needed for live Gmail messages, such as `source`, `account_id`, and Gmail `message_id`
- Skip already queued or reviewed messages by default using `account_id + message_id`
- Allow partial success: successful messages continue into the queue even if some message fetches fail
- Record per-message fetch failures locally
- Mark messages as processed only after fetch, classification, and review-queue persistence succeed for those messages
- Keep Gmail write-back disabled in this slice

## Non-goals

- Gmail label write-back
- background polling or auto-fetch
- multi-account support
- payload text extraction beyond using `snippet` for classification/review in this slice
- re-ingestion or override flags for already queued or reviewed messages
- provider abstraction work beyond the small Gmail client seam needed for this slice
- sender-level automation

## Acceptance criteria

- First run can complete local browser OAuth for one approved Gmail account and persist a reusable read-only token locally
- A manual CLI command can fetch a bounded inbox batch from the configured Gmail account
- Fetched messages appear in the existing review queue with the same visible fields and ordering semantics as mocked Gmail messages
- Already queued or reviewed messages are skipped by default during later manual fetches
- Raw Gmail payloads and normalized review records are stored locally in a gitignored location separate from credentials
- If some messages fail during fetch, successfully fetched messages still appear in the review queue and failures are recorded locally
- If no new unprocessed inbox messages are found, the command exits cleanly and creates no new batch
- No Gmail label changes are attempted anywhere in this slice

## Expected tests or verification

- Test that the fetch flow can consume a Gmail client seam and normalize representative live-style payloads into review-ready items
- Test that manual fetch excludes already queued or reviewed messages by default using `account_id + message_id`
- Test that fetched live Gmail items persist in the same review-item shape expected by the existing review queue, with only minimal source metadata added
- Test that per-message fetch failures are recorded while successful messages still proceed into the queue
- Test that processed status is recorded only after successful persistence of the relevant message records
- Test that this slice performs no write-back action through its public flow
- Manual verification on one small real Gmail batch after Founder approval

## Dependencies/order

- Depends on issues `001` and `002`
- Reuses the mocked Gmail seam proven in issue `003`
- Should start only after Founder approval for live Gmail read access, local OAuth credential storage, and local raw message storage

## Stop conditions requiring Founder review

- Any OAuth scope broader than the minimum expected for bounded inbox reads
- Any need to store credentials or message content outside the approved local gitignored areas
- Any change that would fetch more than the intended inbox batch or other mailbox areas
- Any proposal to expand beyond one non-primary Gmail account
- Any proposal to add Gmail write-back, re-ingestion overrides, or broader provider architecture in this slice
