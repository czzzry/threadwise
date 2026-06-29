# Handoff: Issue 012 Second-Batch MVP Acceptance Run

## Context

This note records the validation run for [docs/issues/012-second-batch-mvp-acceptance-run.md](docs/issues/012-second-batch-mvp-acceptance-run.md).

This follows the second-batch visibility checkpoint in [docs/handoff/issue-011-read-only-local-batch-index.md](docs/handoff/issue-011-read-only-local-batch-index.md).

## What Changed

- No new product behavior was implemented in this slice
- Reused the existing local workflow on the already-fetched stored batch `founder-test-batch-2`:
  - read-only batch inspection
  - local review
  - explicit confirmed `EA/` Gmail write-back
  - final read-only inspection
- Persisted the normal stored review decisions, per-message write status, and per-message write-attempt history for batch 2 through the existing commands

## Acceptance Status

Acceptance for the bounded slice is met.

Covered behaviors:

- the current MVP was exercised on a second real live batch rather than only the first proof batch
- the existing review flow handled the full batch without new product behavior
- the existing confirmed Gmail write-back path succeeded for the reviewed batch
- no retry was needed in this run
- the final stored batch state is visible through the existing read-only inspection tools

## Validation

Manual live verification only in this slice.

Before-run visibility:

```bash
python3 scripts/list_local_batches.py
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-2
```

Observed pre-review state:

```text
Batch ID: founder-test-batch-2
Account ID: founder-test
Items: 10
Fetch failures: 0
Review states: pending=10
Review actions: (none)
Final labels: labeled=0, unlabeled=0
Label counts: (none)
Write status: missing=10
Write attempts: messages_with_history=0, total_attempts=0, retried_messages=0
```

Review and write-back command:

```bash
python3 scripts/review_live_gmail_batch.py --batch-id founder-test-batch-2
```

Observed review outcome:

- `10` items reviewed
- `6` items approved with suggested labels unchanged
- `4` items edited
- `0` items rejected
- `0` items left unlabeled

Observed dry-run summary:

```text
Approved writes: 10
Rejected: 0
Unlabeled: 0

Labels to create/apply:
EA/Account: 3 messages
EA/LowValue: 7 messages
EA/Promotions: 4 messages
```

Operational note during execution:

- the first write attempt failed before any Gmail mutation because the sandbox blocked the local OAuth callback port bind
- rerunning the same existing command outside the sandbox resolved that environment restriction without changing workflow behavior

Observed write result:

```text
Applied 10 reviewed Gmail label updates.
```

Final stored-state verification:

```bash
python3 scripts/inspect_local_batch_status.py --batch-id founder-test-batch-2
python3 scripts/list_local_batches.py
```

Observed final batch-2 state:

```text
Batch ID: founder-test-batch-2
Account ID: founder-test
Items: 10
Fetch failures: 0
Review states: reviewed=10
Review actions: approve=6, edit=4
Final labels: labeled=10, unlabeled=0
Label counts: EA/Account=3, EA/LowValue=7, EA/Promotions=4
Write status: applied=10
Write attempts: messages_with_history=10, total_attempts=10, retried_messages=0
```

Observed final multi-batch index:

```text
Stored batches: 2
founder-test-batch-1 | account=founder-test | items=10 | review=pending=1,reviewed=9 | labels=labeled=7,unlabeled=2 | writes=applied=7,missing=3 | retries=1 | fetch_failures=0
founder-test-batch-2 | account=founder-test | items=10 | review=reviewed=10 | labels=labeled=10,unlabeled=0 | writes=applied=10 | retries=0 | fetch_failures=0
```

## Suggestion Usefulness And Friction

The MVP still works on a second real batch.

What went well:

- the batch completed end to end using only the existing commands
- most of the batch was handled by direct approval
- write-back succeeded cleanly once the environment-level OAuth restriction was removed
- no retry path was needed

Concrete friction observed:

- `4` of `10` items required edits rather than direct approval
- `3` of those edits were account/security-style messages that arrived with no suggestion and were manually labeled `EA/Account`
- `1` edit trimmed an over-broad `EA/Promotions` plus `EA/LowValue` suggestion down to `EA/LowValue`

Concrete pain exposed by the run:

- account/security/account-document emails are still under-suggested in the current live suggestion flow

This is specific enough to justify the next bounded implementation slice if approved.

## Important Constraints

- This slice added no new behavior, no new Gmail scope, and no new utility surface
- The write path remained limited to the existing explicit `EA/` label creation/application workflow
- The acceptance evidence should be used to drive the next issue only if the founder agrees that the account-suggestion gap is the current highest-value pain

## Risks Or Open Questions

- The second-batch run validates the current MVP, but suggestion quality is still uneven on account/security-style email
- Batch 1 still remains partially reviewed in stored state; that is existing project state rather than a new issue created by this slice

## Recommended Next Step

- If the founder agrees the current concrete pain is under-suggestion for account/security/account-document email, draft the next bounded issue around improving that suggestion quality and nothing broader
- Otherwise, stop here and do not implement new behavior until another concrete pain is chosen through the normal issue-first process
