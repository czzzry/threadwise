# Title

Gmail unsubscribe inventory and selection workbench

## Type

HITL

## User-visible goal

Show a Gmail-first inventory of unsubscribe candidates in the existing local workbench, grouped one row per sender or list identity, and let the founder mark which lists are selected for later unsubscribe execution without performing any real unsubscribe actions yet.

## Scope

- Aggregate unsubscribe candidates from stored Gmail batches already fetched into the local workspace
- Group candidates by a practical list identity rather than per-message rows
- Include strong unsubscribe signals such as `List-Unsubscribe` and recurring bulk/promotional behavior
- Exclude clearly transactional/account/security mail from the candidate list
- Persist local decision state for each candidate such as `selected`, `not_selected`, or `undecided`
- Keep the stored model provider-aware where easy so Proton can plug in later

## Non-goals

- Executing any unsubscribe action
- Clicking HTTP unsubscribe links
- Supporting `mailto:` unsubscribe execution
- Broad provider abstraction work
- Guaranteeing a full inbox-wide inventory from one slice

## Acceptance criteria

- The local workbench shows an unsubscribe inventory section built from stored Gmail data
- The inventory groups messages into one practical row per sender or list identity
- Clearly transactional/account/security messages do not appear as unsubscribe candidates
- The founder can save a local selection state for a candidate without mutating Gmail
- The stored selection artifact includes enough metadata for a later execution slice

## Expected tests or verification

- Test that the workbench inventory includes `List-Unsubscribe` or recurring bulk candidates and excludes transactional mail
- Test that grouped candidates show evidence count, most recent message date, and qualification reason
- Test that saving a candidate selection persists a local provider-aware artifact and re-renders with the saved state
