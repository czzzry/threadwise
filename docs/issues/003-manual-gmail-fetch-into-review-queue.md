# Title

Manual Gmail fetch into the existing review queue

## Type

HITL

## User-visible goal

Let the user fetch one bounded batch from a non-primary Gmail inbox and review those real messages in the same queue proven by the fixture slice, still without writing labels back to Gmail.

## Scope

- Connect one non-primary Gmail account with the narrowest approved read capability needed for this slice
- Manually fetch a bounded inbox batch on demand
- Normalize fetched messages into the same review flow used by issue `001`
- Skip already processed messages by default
- Store fetched message content and review-relevant metadata locally in a gitignored location
- Keep write-back disabled in this slice

## Non-goals

- Gmail label write-back
- auto-fetch or background polling
- multi-account support
- provider abstraction work
- sender-level automation

## Acceptance criteria

- A user can manually fetch a bounded inbox batch from one approved Gmail account
- Fetched messages appear in the existing review queue with the same visible fields and ordering as fixture-backed messages
- Already processed messages are skipped by default during later manual fetches
- No Gmail label changes are attempted anywhere in this slice
- Local message storage is easy to delete, gitignored, and kept separate from credentials

## Expected tests or verification

- Test normalization of representative Gmail message payloads into review items
- Test that manual fetch excludes already processed messages by default
- Test that this slice performs no write-back action through its public flow
- Manual verification on one small real Gmail batch after Founder approval

## Dependencies/order

- Depends on issues `001` and `002`
- Should start only after `docs/decisions/review-semantics.md` is approved

## Stop conditions requiring Founder review

- Any OAuth scope broader than the minimum expected for bounded inbox reads
- Any need to store message content outside the approved local gitignored area
- Any change that would fetch more than the intended inbox batch or other mailbox areas
- Any proposal to expand beyond one non-primary Gmail account
