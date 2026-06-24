# V2 Alignment

Status: Current product-direction alignment
Current as of: 2026-06-22
Builds on: `docs/archive/alignment-v1-gmail-mvp.md` and `docs/archive/prd-v1-gmail-mvp.md` as historical Gmail V1 artifacts
Current bounded PRD: `docs/prd.md`
Implementation checkpoint: `docs/checkpoints/current-operating-model-2026-06-22.md`

## Mature product direction

V2 should turn the current Gmail-only autonomous labeling workflow into the beginning of a real multi-inbox assistant for one person.

The goal is not to jump straight to full automation everywhere. The goal is to extend the operating model that now works for one Gmail inbox into a product that can support two inboxes cleanly and produce useful summaries about what happened.

Unsubscribe management is part of the mature product. It is not a side utility.

## Current product state

The repo already proves more than the original Gmail MVP:

- Gmail daily runs with bounded label write-back and limited `INBOX` removal
- daily per-run operational reports
- weekly per-inbox analytical reports
- provider/account-aware local run artifacts
- ProtonMail read-only import, live fetch, and daily run paths
- unsubscribe inventory, supported execution, and manual follow-up paths
- local browser review and inspection tools for exceptions and spot checks

This means V2 is no longer "build daily reports, then weekly reports, then ProtonMail." Those slices already exist in the repo. The current job is to keep the operating model stable, keep the docs synchronized, and choose the next bounded product move.

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

## Current operating model

The intended steady-state operating model is:

1. run the assistant once per day for each inbox
2. fetch the latest messages for that inbox
3. classify the messages
4. auto-apply current suggested labels where the provider flow supports it
5. remove `INBOX` only for low-value or promotional Gmail mail
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

## Reporting model

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

## Current safety rules

Current accepted autonomy:

- auto-apply all current suggested `EA/` labels
- remove `INBOX` only for `spam-low-value` and `promotions` in Gmail
- build unsubscribe inventory locally and execute only supported unsubscribe actions that the user explicitly selected
- leave unlabeled or unsupported exceptions for manual handling

Still out of scope for default autonomy:

- deleting mail
- trashing mail
- archiving mail broadly
- unsubscribing from lists without explicit user selection or confirmation
- provider-side ProtonMail mutation

## Remaining roadmap

Near-term product work now looks more like:

1. tighten the current provider/account-aware operating model and artifact contracts
2. improve the manual follow-up path for unlabeled and unsupported cases
3. write clearer product and safety rules for subscription management
4. decide whether ProtonMail should remain read-only or later gain bounded write actions
5. consider combined cross-inbox reporting, scheduling, and multi-user support only if the one-user local workflow keeps proving useful

## Non-goals for now

Do not assume immediate priority for:

- background scheduling
- multi-user support
- merged cross-provider inbox UX
- generic provider framework work beyond what the workflow actually needs
- deleting or archiving mail automatically
