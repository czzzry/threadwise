# Title

Second-batch MVP acceptance run through the existing live workflow

## Type

HITL

## User-visible goal

Let the user run `founder-test-batch-2` through the already-proven local Gmail workflow end to end, capture whether the current MVP is useful on a second real batch, and surface any concrete operational or quality pain before approving further implementation work.

## Scope

- Reuse the existing stored live batch `founder-test-batch-2`
- Reuse only the already-proven workflow from issues `006` through `011`:
  - inspect
  - review
  - confirmed `EA/` write-back
  - retry if needed
  - final local inspection
- Treat this slice as validation and acceptance of the current MVP rather than as new product behavior
- Record structured evidence from the second-batch run about:
  - suggestion usefulness
  - manual review friction
  - write-back friction or failures
  - retry necessity
  - final batch outcome
- Produce a durable written handoff or checkpoint summarizing what happened in the run
- If the run exposes a concrete pain, name it precisely enough to draft the next bounded issue
- Define expected behavior and verification before execution begins

## Non-goals

- new review behavior
- new Gmail behavior or broader Gmail permissions
- changing the fixed taxonomy
- building another utility, dashboard, or reporting surface before the run proves a need
- broad quality analytics beyond what is needed to judge this one acceptance run
- autonomous inbox actions, background sync, or multi-account support
- exposing private email content by default in any new artifact

## Acceptance criteria

- `founder-test-batch-2` is run through the existing local workflow from review through final stored inspection
- The run records whether current suggestions were usable enough to complete the batch without inventing new behavior mid-run
- The run records concrete review friction, including where manual edits or uncertainty occurred
- Any Gmail write failures and retry behavior are captured if they occur
- The final stored batch state can be inspected locally using the existing read-only tools
- The outcome is written down as a durable acceptance note that states either:
  - the current MVP still holds on a second real batch, or
  - the run exposed one concrete pain that should become the next bounded slice
- No new product behavior is implemented as part of this issue

## Expected behavior

- The user starts from the already-fetched stored batch `founder-test-batch-2`
- Existing local inspection commands may be used first to confirm the batch starts in a pre-review state
- The existing review flow is used to review the batch locally
- During review, the run captures lightweight evidence about suggestion usefulness, such as:
  - how often suggested labels were accepted unchanged
  - how often labels were edited, cleared, or left unlabeled
  - whether any repeated misclassification pattern is obvious
- The existing confirmed write-back flow is used after review if the batch contains approved labels
- If write failures occur and existing retry rules allow it, the existing retry path may be used
- Existing read-only inspection commands are used after the run to confirm the final stored state
- The run ends with a short durable summary of:
  - what happened
  - whether the MVP still feels useful on batch 2
  - what concrete pain, if any, now deserves the next issue
- If no concrete pain emerges, the slice ends without proposing speculative implementation work

## Expected tests or verification

- Manual verification on `founder-test-batch-2` using only the existing live commands and existing local inspection tools
- Capture the before/after batch state using the existing inspection or batch-index commands
- Record whether Gmail write-back succeeded directly, required retry, or surfaced no writable items
- Record whether review friction was low enough that no new slice is justified yet
- If a concrete pain appears, confirm it is specific, repeatable enough to describe, and narrow enough to become one bounded issue
- No implementation changes or new automated tests are required unless the run uncovers a separately approved follow-up slice

## Dependencies/order

- Depends on issues `006` through `011`
- Should happen before drafting another implementation slice, because batch 1 has proven the loop once and batch 2 is the next acceptance checkpoint
- Should be completed as a validation run plus handoff before any new behavior work is approved

## Stop conditions requiring Founder review

- The run appears to require new product behavior to finish rather than exercising the existing workflow
- The run pressures the project toward broader Gmail actions, broader scopes, or default exposure of private email content
- The observed pain is vague, speculative, or better framed as a broader product decision instead of one bounded slice
- Any proposed follow-up starts drifting into generic tooling or plumbing without a clear user-visible pain from the batch-2 run
