# V2 Alignment

## Purpose

V2 should turn the current Gmail-only autonomous labeling workflow into the beginning of a real multi-inbox assistant for one person.

The goal is not to jump straight to full automation everywhere. The goal is to extend the operating model that now works for one Gmail inbox into a product that can support two inboxes cleanly and produce useful summaries about what happened.

## Target User

- one user
- managing two inboxes
- one Gmail inbox
- one ProtonMail inbox

## Core Product Job

Help one person stay in control of two noisy inboxes by:

- labeling email consistently for retrieval
- auto-handling the mail that is already well understood
- surfacing what happened in clear reports
- leaving only the uncertain or user-choice cases for manual follow-up

Unsubscribe management is part of the mature product. It is not a side utility.

## Operating Model

The intended steady-state operating model is:

1. run the assistant once per day for each inbox
2. fetch the latest messages for that inbox
3. classify the messages
4. auto-apply current suggested labels
5. remove `INBOX` only for low-value or promotional mail
6. produce a daily per-run report for that inbox
7. leave only unlabeled or otherwise unresolved exceptions for manual follow-up

Manual review remains available as a fallback path, not the default path.

## Inbox Model

V2 should support:

- separate per-inbox processing
- shared labeling logic where practical
- shared operating model across providers
- shared reporting structure across providers

V2 should not force a merged unified inbox model first.

The product should be able to tell the user what happened in Gmail and what happened in ProtonMail separately, even if both runs happen on the same day.

## Reporting Model

### Daily Report

The daily report should be a broad operational digest for one inbox run.

Primary contents:

- total emails processed
- counts by label
- how many were auto-labeled
- how many had `INBOX` removed
- how many were left unlabeled
- a short list of the unlabeled leftovers

The daily report is not primarily an alert feed. It is an operational summary of what the assistant did.

### Weekly Report

The weekly report should be a per-inbox analytical rollup covering the previous full week.

It should go beyond simple sums and include:

- trends over the week
- biggest categories
- exception rate
- notable changes in mix or volume

Cross-inbox combined reporting may come later, but per-inbox weekly reporting is enough for the current direction.

## Autonomy Boundary

Current accepted autonomy:

- auto-apply all current suggested `EA/` labels
- remove `INBOX` only for `spam-low-value` and `promotions`
- leave unlabeled exceptions for manual handling

Still out of scope for default autonomy:

- deleting mail
- trashing mail
- archiving mail broadly
- unsubscribing from lists without explicit user selection

## Unsubscribe Management

Unsubscribe management is part of the mature product and should be treated as a core future job of the assistant.

It should be staged:

1. identify which mailing lists or newsletters the user is on
2. let the user review that list
3. let the user choose which lists to leave
4. execute unsubscribes only after explicit confirmation

This should not be the first v2 implementation slice, but it should remain in the intended product direction.

## Near-Term Sequencing

Recommended early v2 sequence:

1. daily per-run operational report for one inbox
2. weekly per-inbox analytical report
3. make the workflow explicitly provider/account-aware while still running Gmail live
4. add list/subscription inventory
5. add user-selected unsubscribe execution
6. add ProtonMail live integration into the already-defined workflow

This sequence is intended to reduce integration risk while still moving toward the mature product.

## Non-Goals For Immediate V2 Start

Do not assume immediate priority for:

- background scheduling
- multi-user support
- merged cross-provider inbox UX
- generic provider framework work beyond what the workflow actually needs
- deleting or archiving mail automatically

## Current Product Position

The current product is no longer just a review experiment.

It is now a usable autonomous Gmail workflow with:

- manual fetch
- autonomous label write-back
- bounded inbox clearing for low-value/promotional mail
- local audit state
- small unlabeled exception tails

V2 should build on that operating model instead of restarting from first principles.
