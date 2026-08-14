# V2 Alignment

Status: Current product-direction alignment
Current as of: 2026-08-12
Builds on: `docs/archive/alignment-v1-gmail-mvp.md` and `docs/archive/prd-v1-gmail-mvp.md` as historical Gmail V1 artifacts
Completed bounded milestone: `docs/archive/prd-memory-runtime-milestone-completed-2026-06-29.md`
Current product-direction PRD: `docs/prd-threadwise-gauntlet-2026-08-09.md`
Implementation checkpoint: `docs/checkpoints/current-operating-model-2026-06-22.md`
Amended by: `docs/issues/139-remove-unsubscribe-and-destructive-suspicious-sender-flows.md`

Threadwise is the public-facing project name for this repo.

## August 9 world-class triage Gauntlet decision

The founder has approved a continuing Gauntlet Loop to make Threadwise a world-class email-triage product. The existing Threadwise logo and the Gmail-overlay architecture are fixed. Threadwise must not become a separate inbox application, and AI auto-response, email writing, reply, forward, compose, and send behavior are excluded.

Mail-0/Zero is the functionality bar, adapted to a Gmail overlay rather than copied as an inbox client. Grammarly is the contextual-intelligence bar, Refined GitHub the host-native extension bar, Raycast the contextual-action and keyboard bar, and Linear only the compact configuration reference.

The detailed product contract and judgeable test seams are in `docs/prd-threadwise-gauntlet-2026-08-09.md`. The smallest-slice decomposition is in `docs/threadwise-gauntlet-slice-map-2026-08-09.md`. Each important slice uses a fresh builder and separate fresh critic; only individually triaged slices are approved for implementation.

`CONTEXT.md` and the Gauntlet slice map own current slice status and completion evidence.

## August 2026 provider-parity decision

The founder has approved a universal Threadwise side panel with one shared in-panel review experience as the provider-parity direction.

Threadwise must present one user experience across Gmail and ProtonMail. It should automatically appear in a minimized state on both providers and expand only when the founder opens it. The existing Gmail interaction model is the initial parity baseline, while shared improvements may change both providers together.

The Gmail companion and Proton review console must not continue as independently designed product surfaces. The existing Gmail in-panel review workflow is the initial behavioral baseline. Gmail and Proton should share one rendering implementation, interaction state machine, teaching flow, activity model, and provider-neutral review workflow. Provider-specific adapters may vary only where mailbox context, message retrieval, matching, writes, verification, or provider navigation genuinely differ.

Gmail and Proton remain separate inboxes with provider-scoped queues, rules, receipts, reconciliation, and reporting. Identical interaction does not imply a merged inbox or automatic cross-provider learning.

The bounded product contract is recorded in `docs/prd-universal-threadwise-experience-2026-08-01.md`.

## Mature product direction

V2 evolves the Gmail-first labeling workflow into a browser-based, teachable inbox agent for one person's provider-scoped inboxes.

The goal is not to jump straight to full automation everywhere. The goal is to pair a daily automation backbone with an inbox-native teaching loop, so the user can correct the agent in context and the agent can safely learn from that feedback.

Unsubscribe management is no longer part of the product. `List-Unsubscribe` remains classification evidence only; historical local artifacts are preserved, but no unsubscribe UI or execution route is available.

## Current product state

The repo already proves more than the original Gmail MVP:

- Gmail daily runs with bounded label write-back and limited `INBOX` removal
- daily per-run operational reports
- weekly per-inbox analytical reports
- provider/account-aware local run artifacts
- ProtonMail import, live fetch, daily run paths, and a first bounded label-only review console through Bridge
- preserved historical unsubscribe artifacts with their former UI and execution paths removed
- local browser review and inspection tools for exceptions and spot checks

This means V2 is no longer "build daily reports, then weekly reports, then ProtonMail." Those slices already exist in the repo. The Gmail release product surface and recruiter-ready portfolio package now exist. `CONTEXT.md` owns the current execution stage and next approved slice.

## Target User

- one user
- managing their own inboxes
- first release target: one Gmail inbox
- second supported provider: that same person's ProtonMail inbox under its narrower label-only write boundary
- not a team product
- not a shared-inbox workflow

## Core Product Job

Help one person stay in control of two noisy inboxes by:

- labeling email consistently for retrieval
- auto-handling the mail that is already well understood
- surfacing what happened in clear reports
- letting the user teach the agent in context when it gets something wrong
- leaving only the uncertain or user-choice cases for bounded follow-up

## Current operating model

The intended steady-state operating model is:

1. run the assistant once per day for each inbox
2. fetch the latest messages for that inbox
3. classify the messages
4. auto-apply current suggested labels where the provider flow supports it
5. remove `INBOX` only for low-value or promotional Gmail mail
6. produce a daily per-run report for that inbox
7. show the user what happened in a minimizable inbox companion panel and daily dashboard
8. let the user correct misclassifications from the inbox itself
9. learn from that correction carefully, with confirmation before broader existing-message rewrites
10. leave only unresolved or preference-sensitive cases for bounded follow-up

Manual review remains available as a fallback path, not the default path. The dashboard/workbench remains secondary support infrastructure, not the main product surface.

## Primary Product Surface

The first serious release surface should be:

- a browser-based inbox companion sidebar attached to Gmail
- minimizable when not needed
- showing the currently selected email's classification, status, and a short plain-English reason
- exposing `Correct / Teach` with explicit current-email and broader-impact scope
- supporting short conversational acknowledgments and clarifying follow-up only when needed

The sidebar should be robust and inbox-adjacent now, while preserving an architecture that could evolve toward a more magical thread-native feel later.

## Inbox Model

V2 should support:

- separate per-inbox processing
- shared labeling logic where practical
- shared operating model across providers
- shared reporting structure across providers

V2 should not force a merged unified inbox model first.

The product should be able to tell the user what happened in Gmail and what happened in ProtonMail separately, even if both runs happen on the same day.

Gmail remains the first acceptance surface. ProtonMail follows the same shared interaction contract while retaining its narrower label-only write boundary.

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

In the mature product, the daily dashboard should emphasize:

- what came in
- how the agent categorized it
- what it auto-handled
- what still needs attention
- what provider-scoped coverage was verified and how fresh it is

Learning progress can appear as a small secondary section, but should not dominate the daily view.

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
- leave unlabeled or unsupported exceptions for manual handling

Still out of scope for default autonomy:

- deleting mail
- trashing mail
- archiving mail broadly
- any unsubscribe execution or user-facing unsubscribe management
- ProtonMail label replacement, moving, archiving, Trash, Spam, sending, or provider-side filter/rule management. Daily Proton runs may add and read back suggested `EA/` labels only for medium/high-confidence classifications while preserving Inbox; low-confidence, unlabeled, and failed-verification items require review.

## Teaching Loop Rules

When the user corrects the agent from the inbox:

- the current email should be fixed immediately
- the agent should respond briefly so the user knows it understood
- the agent should say what it thinks it learned
- if the inferred learning would change any other existing emails, it must surface that impact and ask for confirmation first
- the user should be able to choose:
  - apply only to this email
  - apply to matching emails too
  - use for future emails only
  - refine the interpretation further
- if the user refines the interpretation, the product should preserve the prior interpretation so the user can compare old vs revised understanding
- if the user ignores a prompt, the system should keep working and leave the unresolved decision in a safe, batched follow-up state

Prompting should stay bounded:

- ideal day: `0`
- normal acceptable day: `1-3`
- heavy day: up to `5`

Above that, the agent should batch and summarize instead of continuing to interrupt.

## Directional roadmap

Keep hardening the Gmail daily-use loop, provider-scoped review, and public story, then close the remaining live Proton acceptance and parity work. `CONTEXT.md` and the Gauntlet slice map own implementation sequence and current completion status.

## Non-goals for now

Do not assume immediate priority for:

- background scheduling
- multi-user support
- merged cross-provider inbox UX
- generic provider framework work beyond what the workflow actually needs
- deleting or archiving mail automatically
- unsubscribe execution or user-facing unsubscribe management

Do not let the product drift into:

- a dashboard-first experience
- a team/shared-inbox workflow
- a generic all-provider platform before the Gmail release is solid
