# V2 Alignment

Status: Current product-direction alignment
Current as of: 2026-07-16
Builds on: `docs/archive/alignment-v1-gmail-mvp.md` and `docs/archive/prd-v1-gmail-mvp.md` as historical Gmail V1 artifacts
Completed bounded milestone: `docs/archive/prd-memory-runtime-milestone-completed-2026-06-29.md`
Current bounded PRD: `docs/prd.md` for MVP+2 Gmail daily usefulness
Implementation checkpoint: `docs/checkpoints/current-operating-model-2026-06-22.md`

Threadwise is the public-facing project name for this repo.

## Mature product direction

V2 should turn the current Gmail-only autonomous labeling workflow into a browser-based, teachable inbox agent for one person's inboxes.

The goal is not to jump straight to full automation everywhere. The goal is to pair a daily automation backbone with an inbox-native teaching loop, so the user can correct the agent in context and the agent can safely learn from that feedback.

Unsubscribe management is part of the mature product. It is not a side utility.

## Current product state

The repo already proves more than the original Gmail MVP:

- Gmail daily runs with bounded label write-back and limited `INBOX` removal
- daily per-run operational reports
- weekly per-inbox analytical reports
- provider/account-aware local run artifacts
- ProtonMail import, live fetch, daily run paths, and a first bounded label-only review console through Bridge
- unsubscribe inventory, supported execution, and manual follow-up paths
- local browser review and inspection tools for exceptions and spot checks

This means V2 is no longer "build daily reports, then weekly reports, then ProtonMail." Those slices already exist in the repo. The Gmail release product surface and recruiter-ready portfolio package now exist. The current MVP+2 job is to make the Gmail daily loop more useful before ProtonMail expansion resumes.

## Target User

- one user
- managing their own inboxes
- first release target: one Gmail inbox
- later product expansion target after the Gmail daily-use loop is stronger: add that same person's ProtonMail inbox
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
- exposing `Correct / Teach` and unsubscribe actions when relevant
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

The first launch target should still be Gmail-first. ProtonMail belongs after the recruiter-ready portfolio demo, not as a blocker to the first serious Gmail release or its public packaging.

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
- what unsubscribe opportunities it found

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
- build unsubscribe inventory locally and execute only supported unsubscribe actions that the user explicitly selected
- leave unlabeled or unsupported exceptions for manual handling

Still out of scope for default autonomy:

- deleting mail
- trashing mail
- archiving mail broadly
- unsubscribing from lists without explicit user selection or confirmation
- ProtonMail label replacement, moving, archiving, Trash, Spam, sending, or provider-side filter/rule management; the approved Proton trial may only add and read back one `EA/` label while preserving Inbox

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

## Remaining roadmap

Near-term product work now looks more like:

1. ship the Gmail inbox companion sidebar as the primary product surface
2. make in-inbox `Correct / Teach` conversational and immediate
3. keep the daily dashboard and unsubscribe flows aligned with that inbox-native surface
4. use the current workbench/review infrastructure as supporting product plumbing, not the destination UX
5. package the Gmail release as a recruiter-ready portfolio demo
6. make the Gmail daily loop genuinely useful with a teachable Needs attention lane and product-triggered Gmail check flow
7. add the founder's ProtonMail inbox after the Gmail daily-use loop and public demo story are solid

## Non-goals for now

Do not assume immediate priority for:

- background scheduling
- multi-user support
- merged cross-provider inbox UX
- generic provider framework work beyond what the workflow actually needs
- deleting or archiving mail automatically

Do not let the product drift into:

- a dashboard-first experience
- a team/shared-inbox workflow
- a generic all-provider platform before the Gmail release is solid
