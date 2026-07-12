# Status

Current
Current as of: 2026-06-24
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/decisions/gmail-bounded-autonomy.md`, and the local teachable-rules prototype branch

# Title

Teach classification rules from selected stored emails

## Type

Implementation slice

## User-visible goal

Let the founder select stored local email examples, type a teaching instruction, preview the resulting classification rule, save it as local memory, and see future stored-batch classifications explain when that saved rule matched.

## Scope

- extend the existing local browser review UI, not live Gmail commands
- allow pending stored-batch emails to be selected as teaching examples
- save a local JSON rule memory artifact with:
  - instruction text
  - target label
  - match terms
  - source examples
  - enabled state
  - created timestamp
- preview a proposed rule against the currently loaded stored batch before saving
- apply enabled teaching rules additively when the local stored-batch review UI reclassifies raw Gmail messages
- show matched rule evidence on affected classification cards and batch API responses
- keep saved teaching rules from creating low-value inbox-removal behavior

## Non-goals

- live Gmail fetches or writes
- Gmail delete, trash, send, broad archive, or new inbox-removal behavior
- ProtonMail mutation
- unattended scheduling
- LLM-based rule compilation
- broad taxonomy redesign

## Acceptance criteria

- The local browser review UI can save a teaching rule from selected pending examples.
- The saved rule persists under local storage.
- The UI preview shows which currently loaded emails would match before saving.
- Reopening/reloading the stored batch shows labels added by matching saved rules.
- Affected cards show which saved rule matched.
- Rules can add retrieval/visibility labels but cannot add `promotions` or `spam-low-value`.
- Existing local browser review tests and the full unit suite continue to pass.
