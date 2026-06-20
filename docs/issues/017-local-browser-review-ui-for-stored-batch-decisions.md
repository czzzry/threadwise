# Title

Local browser review UI for stored batch decisions

## Type

AFK

## User-visible goal

Let the user open a local browser UI for one already-stored Gmail batch, review items there, choose labels by clicking the fixed approved `EA/` taxonomy, and save the same review decisions the CLI review flow would persist, with a small local feedback summary and no live Gmail activity.

## Scope

- Add a local browser review surface for one stored batch at a time
- Load review items only from already-persisted local batch artifacts
- Let the user choose from the existing fixed approved taxonomy by clicking
- Persist the same review decisions and final labels the current CLI review flow would persist for that batch
- Show a small local feedback summary such as reviewed count and label distribution
- Reuse the existing review state model where possible rather than inventing a separate browser-only review format
- Keep the slice local-only and suitable for manual founder use on stored batches
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail fetches, Gmail API calls, or Gmail writes of any kind
- `remove INBOX` behavior
- failed-write retry behavior
- background sync, polling, or long-running automation
- multi-batch dashboarding or cross-batch analytics
- taxonomy expansion or editing
- replacing the CLI flow entirely

## Acceptance criteria

- A user can launch a local browser UI for one stored batch
- The UI shows reviewable stored items for that batch and the fixed approved label choices
- Clicking a label updates the stored review decision in the same persisted shape expected by the current review workflow
- The UI shows a small feedback summary for the current batch
- The slice performs no Gmail fetches, no Gmail writes, no inbox removal, and no background sync
- The slice stays bounded to one-batch local review rather than growing into a broader dashboard

## Expected behavior

- The user starts a local command that opens or serves a browser-accessible review page for one `--batch-id`
- The page loads review items from stored local batch data only
- Each review item shows only the data needed for the existing human review task
- The available label controls match the current fixed approved `EA/` taxonomy exactly
- When the user chooses or changes a label, the decision is saved in the same local review artifacts the CLI would use or produce
- The UI provides a small batch-level summary such as:
  - total items
  - reviewed items
  - remaining items
  - current label counts
- Reopening the same batch reflects previously saved decisions
- The public flow remains offline with no network dependency beyond local browser access to the local process

## Expected tests or verification

- Test launching the local review UI for a stored fixture or stored local batch
- Test that one label click persists the expected decision in the existing review artifact shape
- Test reopening the batch and seeing the saved decision
- Test batch summary counts updating as decisions are saved
- Test invalid or missing batch ids fail clearly without starting Gmail-related work
- Test that the slice performs no Gmail client/API/write path activity in its public flow

## Dependencies/order

- Depends on the existing stored-batch review artifacts and fixed taxonomy from issues `001` through `016`
- Should begin only after this issue boundary is approved and the implementation is done test-first

## Stop conditions requiring Founder review

- The UI needs to expose substantially more private email content than the existing review flow
- The implementation pressures the project toward a general dashboard or app shell rather than one-batch review
- The browser flow cannot reuse the current review-decision persistence shape and would require a second divergent review model
- The slice starts pulling in live Gmail behavior instead of remaining local-only
