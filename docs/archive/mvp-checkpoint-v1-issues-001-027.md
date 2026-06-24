# MVP Checkpoint (Issues 001-027)

Status: Historical checkpoint after issues `001` through `027`
Applies to: Gmail MVP before daily runs, weekly reports, provider-aware artifacts, ProtonMail read-only slices, and unsubscribe workbench slices
Current implementation checkpoint: `docs/checkpoints/current-operating-model-2026-06-22.md`

This document records what the repo had proven at the original Gmail MVP boundary.

## Current State

Issues `001` through `027` now establish a working local Gmail labeling workflow with bounded autonomous action on one Gmail inbox.

What is now proven:

- one local Gmail account can be connected with bounded OAuth
- inbox messages can be fetched manually into local stored batches
- stored batches can be classified into the approved fixed taxonomy
- a human can review suggestions locally before any Gmail mutation
- one stored batch can be reviewed in a local browser UI with the same persisted review decisions as the CLI flow
- approved `EA/` labels can be written back to Gmail with explicit confirmation
- failed label writes can be retried without re-review when approved labels are unchanged
- stored batch state can be inspected locally through a privacy-safe summary command
- account/security/account-document messages are now better suggested into the approved fixed taxonomy on stored live batches
- approved low-value/promotions messages can be explicitly removed from the main Gmail inbox view by removing `INBOX` without deleting them
- inbox-removal outcomes can be inspected locally through the same privacy-safe batch status and batch index tools
- current suggested labels can be auto-applied to Gmail for pending items in a stored live batch
- autonomous runs can resume safely if a prior write was interrupted before Gmail write-back completed
- fresh live batches can now be handled primarily by autonomous label application, with only unlabeled leftovers requiring manual review

What this means in practical terms:

- the current operating loop now exists end to end:
- fetch
- classify
- auto-apply suggested labels
- remove `INBOX` for low-value/promotions
- inspect unlabeled leftovers
- retry failed writes
- inspect stored batch state

## Boundaries

The current MVP remains intentionally narrow.

Still out of scope:

- background polling or syncing
- multi-account handling
- multi-provider support
- broad dashboard/reporting UX
- default exposure of private email content in local tools
- taxonomy expansion beyond the approved labels
- deleting, trashing, or archiving mail

## Issue Map

Implemented and checkpointed:

- `001`: fixture-backed review loop
- `002`: generated suggestions for fixture batches
- `003`: mocked Gmail fetch into review queue
- `004`: mocked Gmail write-back
- `005`: mocked retry seam
- `006`: live Gmail read-only manual fetch
- `007`: live review plus confirmed `EA/` write-back
- `008`: improved local suggestions for stored live batches
- `009`: live retry of failed writes without re-review
- `010`: read-only local stored-batch status inspection
- `011`: read-only local batch index
- `012`: second-batch MVP acceptance run
- `013`: improved `EA/Account` suggestions for stored live batches
- `014`: remove `INBOX` for approved low-value live messages
- `015`: show inbox-removal status in local inspection
- `016`: MVP happy-path usage guide
- `017`: local browser review UI for stored batch decisions
- `018` through `025`: suggestion-quality improvements over real stored batches
- `026`: auto-apply low-risk live Gmail labels
- `027`: auto-apply all suggested live Gmail labels

## MVP Read

The smallest useful version is no longer hypothetical.

It is now reasonable to describe the MVP as:

- a local Gmail labeling assistant for one non-primary inbox
- with autonomous label application as the default path
- with `INBOX` removal limited to low-value/promotional mail
- with manual review reserved for unlabeled leftovers and spot checks
- local audit history
- bounded retry handling
- privacy-safe local batch inspection

## Remaining Gaps

Known limitations that are visible from the current slices:

- fresh batches still require a manual fetch step
- unlabeled exceptions still need a small manual workflow
- inspection is still CLI-first and intentionally minimal
- there is no explicit quality/metrics slice beyond local counts and exception volume
- there is no single daily-run command that fetches, auto-applies, and reports exceptions in one routine action

## Candidate Slice Map

These are candidate next-slice directions only. None is approved yet.

### A. Daily Autonomous Run

Possible pain addressed:

- the current workflow is usable but still spread across fetch, apply, and inspection steps

Likely shape:

- one command that fetches, auto-applies, and summarizes unlabeled leftovers
- still bounded to one inbox and current Gmail actions

### B. Unlabeled Exception Workflow

Possible pain addressed:

- the remaining manual work is now concentrated in a small unlabeled tail

Likely shape:

- tighter inspection or review flow for unlabeled items only
- privacy-sensitive by design

### C. Product-Level Quality Checkpoint

Possible pain addressed:

- hard to quantify whether the autonomous workflow is consistently useful enough

Likely shape:

- local measurement/reporting slice over auto-applied vs unlabeled outcomes
- focus on exception rate, write success, and trust signals

## Next-Step Rule

Do not pick the next slice from this map automatically.

Use the normal process:

1. identify the concrete current pain
2. align on the smallest useful response
3. draft the next bounded issue
4. define expected behavior and tests
5. then implement
