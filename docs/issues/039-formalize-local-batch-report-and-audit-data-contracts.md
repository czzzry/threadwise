# Title

Formalize local batch, report, and audit data contracts

## Type

Refactor

## User-visible goal

Keep the current local inbox workflow behavior unchanged while making the stored JSON artifacts easier to reason about, safer to evolve, and less likely to drift across fetch, review, reporting, evaluation, and unsubscribe flows.

## Scope

- Identify the current local artifact families that now act as important product contracts, especially:
  - stored batch files
  - write-status and inbox-removal status artifacts
  - daily and weekly report artifacts
  - unsubscribe selection and execution audit artifacts
  - shadow-evaluation report artifacts
- Make the code paths that read and write those artifacts more explicit and legible
- Introduce clearer contract boundaries in code for the main artifact shapes without changing their intended workflow meaning
- Reduce duplicated assumptions about required fields, default values, and provider/account metadata
- Preserve backward compatibility with the currently stored local artifacts unless a tiny migration helper is clearly safer
- Strengthen tests around the public behavior that depends on these artifacts

## Non-goals

- Changing product strategy
- Moving from JSON files to a database
- Redesigning the local storage directory layout
- Rewriting the classifier or provider integrations
- Broad schema-framework work for its own sake
- A generic persistence layer unrelated to the current workflow

## Acceptance criteria

- The main local artifact types are easier to identify in code and have clearer ownership
- Shared fields such as provider, account id, batch id, counts, and status values are handled more consistently
- The current workflows still operate against the same local artifact families:
  - fetch and stored review
  - Gmail write-back and retry
  - daily and weekly reporting
  - unsubscribe selection and execution
  - shadow evaluation
- Existing tests remain green, with any added tests focused on workflow-visible behavior rather than internal representation details

## Expected behavior

- Existing scripts and CLIs continue to read and write the same practical local artifacts as before
- Stored batches remain loadable by the current review and inspection tools
- Daily reports still aggregate into weekly reports through the same public flow
- Gmail write/retry and inbox-removal status handling still behave the same
- Unsubscribe selection and execution audit artifacts still support the current workbench flows
- No new provider actions, no new data store, and no migration-heavy storage redesign are introduced

## Expected tests or verification

- Re-run the current report, review-store, browser-UI, retry, unsubscribe, and evaluation-related suites
- Add tests only where needed to pin contract-sensitive public behavior before changing internals
- Verify that one representative stored batch, one daily report, one weekly report, one unsubscribe audit artifact, and one shadow-eval artifact still load through their current public flows
- Keep verification focused on compatibility and clarity, not on inventing a new persistence model

## Dependencies/order

- This refactor is justified once the browser-UI seam is no longer the highest structural pain, or immediately if artifact drift starts blocking new slices
- It pairs well with the existing provider-aware reporting work because those slices already rely on shared local metadata fields
- Follow-on slices should reuse the clarified artifact boundaries instead of adding new ad hoc JSON assumptions

## Stop conditions requiring Founder review

- The refactor starts proposing a database or large persistence redesign instead of contract cleanup
- Artifact compatibility with current local data would be broken without a deliberate migration decision
- The effort expands into a general architecture rewrite instead of clarifying the current workflow contracts
- The work starts changing user-visible reporting, review, or audit semantics instead of preserving them
