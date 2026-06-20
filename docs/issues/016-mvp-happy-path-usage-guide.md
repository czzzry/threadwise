# Title

MVP happy-path usage guide

## Type

AFK

## User-visible goal

Give the founder or a future cleared session one concise copy-paste guide for using the current local Gmail assistant MVP end to end with the existing commands only, including setup notes, safety limits, inspection commands, and known troubleshooting points.

## Scope

- Produce a concise written usage guide for the current MVP only
- Use the already-existing command set and proven behavior only
- Cover:
  - one-time setup notes at a high level
  - fetch
  - review and apply labels
  - retry failed writes
  - remove `INBOX` for approved low-value/promotions messages
  - inspect one batch
  - list all batches
  - safety rules
  - troubleshooting notes
  - current MVP definition
- Include exact copy-paste commands
- Optionally add lightweight doc links or tiny help-text improvements if obviously useful and low-risk

## Non-goals

- new product behavior
- live Gmail verification work
- OAuth/browser flow changes
- workflow automation or orchestration
- dashboard or UI work
- taxonomy changes

## Acceptance criteria

- A reader can understand the current MVP and its safety boundaries from one concise guide
- The guide includes the existing command set needed for the happy path
- The guide distinguishes what the tool will do from what it will not do
- The guide includes practical troubleshooting notes for known local issues
- No new live behavior is introduced

## Expected behavior

- The guide is concise, copy-paste friendly, and grounded in the current proven commands
- The guide explains the sequence a human should actually follow
- The guide stays aligned with the current bounded Gmail mutation rules and safety model

## Expected tests or verification

- Manual doc review for accuracy against the current command set
- Run any relevant lightweight tests only if a small CLI help or code-adjacent change is added

## Dependencies/order

- Follows issues `006` through `015` as documentation over the already-proven workflow
- Should stay doc-first and not reopen implementation unless a tiny obvious doc-link/help gap is found

## Stop conditions requiring Founder review

- The guide starts implying unsupported automation or broader product scope
- Accurate guidance would require changing live behavior rather than documenting what already exists
