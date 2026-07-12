# Gmail Bounded Autonomy

Status: Current decision
Current as of: 2026-06-23
Related PRD: `docs/prd.md`

## Purpose

Define the current Gmail autonomy boundary clearly enough that later agents do not broaden it implicitly and later tests know exactly what behavior they are proving.

## Current Decision

The current Gmail daily run is allowed to do only these bounded automatic actions:

1. fetch a Gmail inbox batch
2. classify messages into the current taxonomy
3. auto-apply current suggested `EA/` labels for messages that fall inside the current trusted daily-run path
4. remove `INBOX` only for Gmail messages that are in the currently allowed low-value classes
5. write daily report artifacts and status/audit artifacts

Everything else remains manual, explicit, unsupported, or out of scope by default.

## Allowed Automatic Gmail Actions

- create or reuse the current `EA/` Gmail labels needed for the run
- apply current suggested `EA/` labels to Gmail messages that the current daily run chose to auto-approve
- remove `INBOX` only after the message has already passed the current writeback gate and only for the currently allowed low-value classes

## `INBOX` Removal Gate

`INBOX` removal is currently allowed only when all of the following are true:

- the message is in the Gmail path
- the message is inside the reviewed or auto-approved current run outcome
- the current label writeback for that message succeeded
- the final labels place the message in the currently allowed low-value classes:
  - `promotions`
  - `spam-low-value`

If those conditions are not met, the message must not have `INBOX` removed automatically.

## Manual / Exception-Only Cases

These stay outside the automatic boundary:

- unlabeled exceptions
- unsupported or uncertain cases
- failed Gmail writes or failed inbox-removal attempts
- unsupported unsubscribe flows
- any ProtonMail provider-side action
- delete, trash, or broad archive behavior

## Required Recorded Evidence

The current workflow must leave enough evidence to inspect what happened. At minimum, the current artifacts should preserve or expose:

- provider
- account id
- batch id
- message id
- final or suggested labels relevant to the action
- writeback status
- inbox-removal status
- daily report counts for auto-applied labels, inbox removals, classified messages, and unlabeled exceptions

## Non-Decisions

This note does not decide:

- a broader multi-provider autonomy model
- new auto-action categories
- whether some labels should later move in or out of auto-apply
- a large eval framework

Those require separate alignment if they become current product scope.
