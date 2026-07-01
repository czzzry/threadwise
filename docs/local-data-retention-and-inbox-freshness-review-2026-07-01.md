# Local Data Retention and Inbox Freshness Review

Status: Current HITL review output
Current as of: 2026-07-01
GitHub issue: `#15`
Parent: `docs/prd.md`
Scope: Code and documentation review only. This review did not inspect private local email data, credentials, OAuth files, or live inbox contents.

## Recommendation

Threadwise should keep using local artifacts for audit, retry, teaching, and product transparency, but the local store needs explicit retention classes before more daily use accumulates.

The important distinction is:

- Local state is a product audit log and teaching memory.
- Local state must not become an indefinite local mirror of Gmail.

The next implementation should be read-only first: add a local artifact inventory command that reports artifact counts, sizes, dates, and retention class without printing private email content. Destructive cleanup should remain a separate, founder-approved step.

## What Threadwise Stores Locally

### Raw Message Bodies and Provider Payloads

Examples:

- `data/gmail_fetch/batches/{account_id}-batch-{n}.json`
- `raw_messages` inside stored batches
- normalized batch `items` with `body`, `snippet`, `subject`, `sender`, `message_id`, provider/account fields, Gmail label ids, and unsubscribe headers

Why it exists:

- replay classification and daily runs
- audit what the agent saw
- build attention candidates from actual message content
- support teach/review flows and regression tests against stored corpora

Risk:

- this is the most sensitive local data class
- it can become stale if Gmail changes after the local snapshot
- indefinite retention would make Threadwise look like a mailbox mirror

Retention expectation:

- keep a short operational window by default, such as the latest `N` batches or a 30-90 day window
- keep longer only for explicitly selected teaching/audit examples
- old raw provider payloads and full `body` fields should be prunable or redactable once derived reports, feedback, and rules no longer need replay

### Compact Metadata

Examples:

- batch ids
- account/provider ids
- message ids and thread ids
- sender, subject, date, snippet
- local review state
- `processed_message_ids.json`
- local Gmail label ids captured during fetch

Why it exists:

- dedupe already-processed mail
- connect reports and dashboard items back to source messages
- preserve auditability without requiring full body retention

Risk:

- still private because sender/subject/snippet can reveal content
- Gmail state can become stale

Retention expectation:

- keep longer than raw bodies, likely 6-12 months while the product is learning
- keep `processed_message_ids.json` until a better Gmail freshness/history model replaces it
- prefer compact metadata over full bodies for long-lived audit

### Reports and Derived Analysis

Examples:

- daily reports under `reports/`
- weekly reports
- attention sections inside daily reports
- evaluation reports
- runtime cascade reports
- safety, memory, frontier, and review-pack outputs

Why it exists:

- show what happened in each run
- support product dashboards
- track attention candidates and LLM usage
- make classifier and memory behavior auditable

Risk:

- reports can contain subjects, senders, snippets, evidence, and model explanations
- some review packs may duplicate examples from stored mail

Retention expectation:

- daily/weekly reports can be retained longer than raw bodies, such as 12-24 months, because they are the main audit trail
- attention reports should remain compact and must not duplicate full bodies
- exploratory analysis and superseded review packs should be prunable after their decisions are applied or archived

### Feedback, Rules, and Learning Memory

Examples:

- `teachable_classification_rules.json`
- `attention_feedback.json`
- `attention_rule_proposals.json`
- `attention_rules.json`
- `shadow_suggestion_memory.json`
- `accepted_shadow_teachable_rules.json`
- `memory_proposals.json`
- `safety_dispositions.json`
- founder question/answer packs and applications

Why it exists:

- preserve the founder's preferences
- support the teaching loop
- explain why future classification or attention behavior changed
- preview broader consequences before applying rules

Risk:

- examples can include private subject/sender snippets
- bad retention could preserve too many examples after they stop being useful

Retention expectation:

- keep accepted rules and explicit feedback until reset or superseded
- keep pending proposals until accepted, rejected, or intentionally expired
- examples inside memory artifacts should be minimal and eventually redacted where possible

### Audit State and Action State

Examples:

- `{batch_id}_write_status.json`
- `{batch_id}_write_attempts.json`
- `{batch_id}_inbox_removal_status.json`
- `{batch_id}_inbox_removal_attempts.json`
- `unsubscribe_selections.json`
- `unsubscribe_execution_audit.json`
- `gmail_dashboard_run_status.json`
- `llm_usage_ledger.json`
- `fetch_failures/`

Why it exists:

- prevent duplicate or confusing write attempts
- make retries explainable
- show what Gmail mutations were performed
- preserve unsubscribe decisions and execution audit
- track LLM usage and estimated cost

Risk:

- action state is safety-critical
- deleting it too early can remove evidence of what Threadwise did

Retention expectation:

- keep action audit state long-term, at least 12-24 months
- keep unsubscribe execution audit indefinitely unless the founder explicitly resets it
- keep LLM usage ledger long enough for weekly/monthly/yearly cost review; it does not need email bodies
- `gmail_dashboard_run_status.json` can stay latest-only unless a future run history is added

### Credentials and Auth Material

Examples:

- `data/gmail_credentials`
- `data/protonmail_credentials`
- `data/outlookmail_credentials`
- OAuth/client-secret/config files
- any browser profile or token material used by live harnesses

Why it exists:

- enable provider access

Risk:

- most sensitive non-email artifact class

Retention expectation:

- never prune automatically as part of general artifact cleanup
- any delete/reset must be a separate explicit founder action
- artifact inventory can report whether a credential directory exists, but should not inspect or print its contents

## What Can Be Pruned Safely

Likely safe prune candidates, after a dry-run report and founder approval:

- old raw Gmail `raw_messages`
- old normalized `body` fields inside batches, once no pending replay/review depends on them
- old transient fetch failures after they are summarized
- superseded evaluation reports and review packs
- rejected or expired proposals after a retention window
- old generated reports that are duplicated by a longer-lived summary

These should be pruned by class and age/count, not by ad hoc filename deletion.

## What Must Remain

Do not prune automatically:

- credentials and OAuth/config material
- accepted teachable rules
- accepted attention rules
- explicit founder feedback
- action audit files for Gmail writes, inbox removals, and unsubscribe execution
- `processed_message_ids.json` until replaced by a better freshness/dedupe model
- latest daily report and latest dashboard state needed by the UI

## Gmail Freshness Model

Current local state is mostly snapshot-based:

- Gmail fetch reads messages from `INBOX`.
- The local batch records message content and Gmail label ids at fetch time.
- `processed_message_ids.json` prevents reprocessing the same message.
- Later dashboard and attention views usually read local artifacts, not the current Gmail state.

That is acceptable for MVP+2, but it creates a product caveat:

> A dashboard item should be treated as "local snapshot as of this run," not guaranteed current Gmail truth.

Threadwise should display or track two different concepts:

- `local_snapshot_at`: when Threadwise last fetched or evaluated the message
- `gmail_verified_at`: when Threadwise last checked the message's current Gmail state

Future freshness refresh should be read-only first. It should query Gmail by known message ids for visible dashboard/attention items and update compact state such as:

- message still exists
- current `labelIds`
- whether `INBOX` is still present
- current thread id
- whether the item appears archived, trashed, spammed, or missing
- last verified timestamp

It should not mutate Gmail.

## Active Gmail Lookback

MVP+2 correctly avoided active Gmail lookback fetch. The stored lookback is cheap and safe, but it misses the founder's intended future case:

- an important email arrived a week ago
- it was archived or left outside the latest local batch
- it becomes urgent today, such as "your flight is tomorrow"

Recommendation:

- active Gmail lookback belongs in a future slice
- it should not be a broad mailbox mirror
- start with targeted, read-only query windows for attention categories
- use bounded queries such as recent travel/bill/security/appointment/job-opportunity terms and date windows
- store only compact attention candidates unless the founder explicitly approves retaining full content

This should come after the current-state refresh slice, because Threadwise first needs to know whether visible local items are stale.

## Follow-Up Issues

Create these as separate bounded slices:

- `#18` / `092`: read-only local artifact inventory and retention report
- `#21` / `093`: raw email body redaction/pruning policy and dry-run cleanup tool
- `#17` / `094`: read-only Gmail current-state refresh for visible dashboard/attention items
- `#20` / `095`: schema-version local artifact registry coverage for MVP+2 artifacts
- `#19` / `096`: bounded active Gmail lookback for time-sensitive attention candidates

Suggested parallelization:

- `092` and `095` can run in parallel.
- `093` should wait for `092`.
- `094` can run in parallel with `092` and `095`, but live Gmail execution remains founder-approved only.
- `096` should wait for `094`.

## HITL Decision Log

The founder approved doing this HITL review after MVP+2 completion and expressed two constraints:

- auditability matters more as Threadwise becomes daily-useful
- local storage should not drift into confusing stale state or over-retention

This review therefore recommends read-only observability first, destructive cleanup second, and active Gmail lookback only after the product can distinguish local snapshot state from current Gmail state.
