# Gmail Whole-Inbox Readiness Policy

Status: Current decision
Current as of: 2026-06-23
Related PRD: `docs/prd.md`
Depends on: `docs/decisions/gmail-bounded-autonomy.md`

## Purpose

Define what "safe enough to run daily on the whole active Gmail inbox" means under the current bounded operating model, so later agents do not treat that phrase as vague or self-evident.

## Current Decision

The current Gmail workflow is considered **supervised-ready** when all of the following are true:

1. it stays inside the existing bounded-autonomy decision,
2. the current stored evidence still supports the classifier and mutation rules,
3. the founder can review the daily report and any leftovers after the run without material burden,
4. no new sign of unsafe low-value handling or mutation drift has appeared.

This is **not** approval for unattended autonomy, background scheduling, or broader inbox mutation.

## Supervised-Ready Meaning

Under this policy, supervised-ready daily whole-inbox Gmail use means:

- the founder may run the current Gmail daily command once per day against the active inbox,
- the run may auto-apply current `EA/` labels and remove `INBOX` only under the existing bounded gate,
- the founder is still expected to review the daily report and inspect the remaining exception list after the run,
- the workflow is trusted as a practical daily operating loop, not as a set-and-forget system.

## Required Evidence Gates

Daily whole-inbox Gmail use should be treated as supervised-ready only when these evidence gates hold.

### 1. Mutation-Safety Gate

The current bounded-autonomy decision must still be true in practice:

- only current `EA/` labels are written,
- `INBOX` removal happens only after successful label writeback,
- `INBOX` removal applies only to `promotions` and `spam-low-value`,
- no delete, trash, broad archive, send, reply, or ProtonMail mutation behavior is introduced.

### 2. Proof Gate

The current end-to-end proof must still exist and pass:

- the daily-run tests proving exact-message Gmail mutation targeting still pass,
- the daily-run tests proving `INBOX` removal is gated on successful label writeback still pass,
- the current classifier tests covering the approved sender-aware cleanup slices still pass.

### 3. Reviewed-Unlabeled Frontier Gate

The current classifier must continue to close the known reviewed-unlabeled frontier on stored founder-test Gmail data:

- re-running the current classifier against historically reviewed unlabeled Gmail items should leave `0` currently remaining unlabeled messages in that measured frontier,
- if new cleanup slices are added later, this frontier should be re-checked rather than assumed.

This gate is evidence about known historical misses. It is not a guarantee that future inbox mail will never surface new exceptions.

### 4. Artifact Gate

Each run must continue to produce inspectable local evidence:

- processed count,
- label counts,
- auto-applied count,
- inbox-removal count,
- unlabeled exception count,
- sender/subject summary for the remaining unlabeled exceptions,
- writeback and inbox-removal status/audit artifacts.

If the workflow stops leaving this evidence, whole-inbox trust should be considered downgraded.

## Acceptable Residual Manual-Review Burden

The current workflow is acceptable for supervised daily use only while the leftover burden remains small.

For a single daily Gmail run:

- the run should leave **no more than 5 unlabeled exceptions**, and
- those exceptions should also remain **no more than 10% of processed messages**.

These limits are intended to keep manual follow-up lightweight enough to remain part of a real daily routine.

If a run exceeds either threshold once, that run should be treated as a warning rather than proof that the workflow is broken. If **two consecutive runs** exceed either threshold, daily whole-inbox use should be paused until the cause is understood.

## Low-Value Trust Rule

Current `spam-low-value` trust is approved for day-to-day use only in a narrow sense.

It is trusted because:

- the Gmail mutation boundary is already constrained,
- `INBOX` removal is already gated on successful label writeback,
- the current low-value slices were closed through focused tests and explicit founder decisions,
- the current measured reviewed-unlabeled frontier has been closed under the classifier.

It is **not** permission to broadly treat every unfamiliar, legal, financial, or transaction-shaped message as low value.

New low-value slices should still follow these rules:

- prefer sender-aware or otherwise narrow pattern rules,
- require founder review before downgrading messages that look financial, account-related, legal, security-related, or subscription-related,
- do not expand low-value coverage by broad topical heuristics alone.

## Pause / Stop Conditions

Daily whole-inbox Gmail use should be paused and re-reviewed if any of the following happens:

- a message the founder would have wanted to retrieve or act on is incorrectly treated as `spam-low-value` or `promotions`,
- a run performs or attempts a Gmail mutation outside the current bounded-autonomy decision,
- label writeback targeting becomes ambiguous or no longer demonstrably exact,
- a run has failed writebacks or failed inbox-removal attempts that are not clearly explained and retried safely,
- two consecutive runs exceed the acceptable residual exception threshold,
- the reviewed-unlabeled frontier check stops closing to `0`,
- a new provider or fetch behavior change makes the current evidence stale.

## Non-Decisions

This policy does not decide:

- unattended scheduling,
- always-on syncing,
- a broader multi-provider autonomy standard,
- a phishing-specific taxonomy bucket,
- a large evaluation framework,
- when ProtonMail should gain any write-side behavior.
