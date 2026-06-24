# PRD

Status: Current bounded-slice PRD
Current as of: 2026-06-24
Builds on: `docs/v2-alignment.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, and `docs/decisions/gmail-bounded-autonomy.md`
Related decisions: `docs/decisions/gmail-bounded-autonomy.md`, `docs/decisions/gmail-whole-inbox-readiness-policy.md`
First implementation slice: `docs/issues/041-inspect-repeated-unlabeled-exceptions-across-stored-batches.md`

## Current Progress Under This PRD

The readiness work originally scoped here has now advanced beyond the first inspection slice:

- recurring reviewed-unlabeled inspection is implemented,
- the focused classifier cleanup slices discovered through that inspection are implemented through issue `048`,
- the current reviewed-unlabeled founder-test Gmail frontier reclassifies to `0` remaining unlabeled items under the current classifier,
- the current readiness policy is now explicit in `docs/decisions/gmail-whole-inbox-readiness-policy.md`.
- a local readiness-check command now evaluates individual Gmail daily run artifacts against the run-level readiness policy.
- a local stored-batch replay command now replays the current classifier across stored Gmail batches and reports corpus-level pass/warn/pause evidence without fetching Gmail again.
- the stored founder-test Gmail replay corpus now evaluates to `PASS` under the current classifier and readiness thresholds.
- a real live Gmail pagination bug has been fixed, so historical backfill can now move beyond Gmail's first `500` inbox results.
- the stored founder-test Gmail corpus has now expanded to `29` batches / `1810` messages while still replaying to `PASS`.
- the most recent live historical validation batches (`founder-test-batch-26` through `founder-test-batch-29`) all replay under the current classifier with verified mutation evidence and no replay warnings.
- the historical founder-test Gmail backfill has now reached the current frontier.
- the next bounded slice is `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`, which must measure only genuinely fresh post-frontier Gmail runs rather than whichever historical report is latest on disk.

The main remaining work under this PRD is no longer sender-family cleanup. It is preserving and proving the operating model over time, especially around reliable live backfill and incremental fetch behavior.

## Problem Statement

The repo already proves a bounded Gmail daily run: it can fetch a fresh inbox batch, classify messages, auto-apply current `EA/` labels, remove `INBOX` only for the current low-value classes, and write daily report artifacts. That solves the basic MVP question.

The next product milestone is stronger: the founder wants to be able to let this run daily on the whole active Gmail inbox with confidence. The limiting problem is no longer the mutation boundary alone. The limiting problem is readiness:

- the repo needed a way to inspect and close repeated exception patterns systematically
- the quality threshold for "safe enough to run daily on the whole inbox" needed to be written down as an explicit readiness policy
- the current fetch model is still a local batch workflow, not yet a clearly approved long-lived whole-inbox operating model

## Solution

Define and implement a bounded Gmail whole-inbox readiness path without broadening the current Gmail autonomy boundary.

This slice should:

- treat supervised daily whole-inbox Gmail use as the target milestone
- keep the current bounded mutation rules unchanged while readiness is improved
- make repeated unlabeled exceptions inspectable from stored local artifacts
- reduce manual review burden by turning the current unlabeled tail into concrete, recurring clusters that can later be closed in small classifier slices
- define the later planning path for readiness policy, incremental-fetch reliability, and supervised scheduling

The first implementation slice under this PRD is not scheduling and not broader Gmail write power. It is exception inspection: expose the recurring unlabeled patterns that are currently blocking confident daily whole-inbox use.

## User Stories

1. As the inbox owner, I want to run the assistant every day against new Gmail inbox mail, so that I can rely on it as part of my actual workflow instead of a one-off experiment.
2. As the inbox owner, I want the current Gmail bounded-autonomy rules to stay unchanged while readiness work continues, so that whole-inbox ambitions do not silently broaden provider-side risk.
3. As the inbox owner, I want recurring unlabeled exceptions grouped and counted, so that I can see the main sources of manual review burden quickly.
4. As the inbox owner, I want privacy-safe exception summaries, so that inspection tools do not spill more private content than necessary.
5. As the inbox owner, I want to see which batches and accounts a recurring exception pattern came from, so that I can decide whether it is worth classifier work.
6. As the inbox owner, I want repeated exception clusters ranked by frequency, so that the highest-leverage cleanup opportunities are obvious.
7. As the inbox owner, I want recent representative examples for an exception cluster, so that I can judge whether the grouping is meaningful.
8. As the inbox owner, I want current labeled and mutated flows to remain stable while exception inspection is added, so that readiness work does not destabilize the existing daily run.
9. As the product lead, I want a current PRD that defines "daily whole-inbox readiness" as a bounded milestone, so that future work does not jump straight to scheduling or broader autonomy.
10. As the product lead, I want the first slice to improve observability of the unlabeled tail rather than invent new automation, so that the work stays inside the current trust boundary.
11. As the product lead, I want readiness planning to separate near-term artifact and inspection work from later fetch and scheduling decisions, so that implementation remains reviewable and small.
12. As the product lead, I want a later explicit readiness policy for exception rate, mutation safety, and operator review expectations, so that "safe enough to run daily" becomes a decision with evidence behind it.
13. As an agent working in this repo later, I want the current PRD to name the real blocker to whole-inbox daily use, so that I do not mistake old classifier issues or old MVP gaps for the current problem.

## Implementation Decisions

- Scope this PRD to Gmail daily whole-inbox readiness, not to broader multi-provider autonomy and not to a generic QA framework.
- Preserve the current Gmail bounded-autonomy rules exactly as captured in the current decision note.
- Keep ProtonMail read-only and out of scope for provider-side mutation.
- Treat stored local batch artifacts as the primary evidence source for readiness work before adding new live Gmail actions.
- Start with one thin vertical slice:
  - inspect reviewed unlabeled exceptions across stored batches
  - group repeated patterns into privacy-safe clusters
  - expose counts, sample references, and recent batch/account context
- Prefer a local CLI and optional local artifact output for the first slice, because the repo already has stable seams for storage-backed inspection commands.
- Reuse the existing stored-batch vocabulary:
  - account
  - batch
  - reviewed vs pending
  - labeled vs unlabeled
  - daily report artifact
  - exception
- Use grouping that is stable enough to surface repeated patterns but conservative enough not to imply semantic certainty the classifier does not yet have.
- Treat the first slice as observability for the manual-follow-up path, not as an automatic reclassification engine.
- Reserve later slices for:
  - closing the highest-value recurring exception clusters
  - writing an explicit readiness policy
  - tightening incremental-fetch semantics for long-lived daily use
  - supervised scheduling or operator-triggered recurring runs
- Do not add in this PRD's first slice:
  - broader Gmail mutations
  - delete, trash, or broad archive behavior
  - background jobs
  - always-on syncing
  - a large browser UI redesign
  - cross-provider unification work

## Testing Decisions

- Good tests for this PRD prove externally visible operator behavior from local artifacts, not helper implementation details.
- Prefer the highest seam possible:
  - inspection CLI behavior
  - persisted local batch artifacts
  - any generated local readiness/inspection artifact
- Prior art already exists in:
  - `tests/test_local_batch_index_cli.py` for privacy-safe cross-batch summaries
  - `tests/test_local_batch_status_cli.py` for storage-backed inspection behavior
  - `tests/test_live_gmail_daily_run_cli.py` and `tests/test_weekly_inbox_report_cli.py` for exception counts already exposed in current run/report artifacts
- The first slice should test:
  - grouping of repeated reviewed unlabeled exceptions across multiple stored batches
  - privacy-safe rendering that avoids dumping full private message bodies
  - stable counts and representative references for recurring clusters
  - clean handling of empty storage, mixed accounts, and pending items
- Keep tests scenario-based and operator-facing. Do not build a broad eval harness in this PRD.

## Out of Scope

- changing the current Gmail bounded-autonomy policy
- adding new Gmail actions beyond the current bounded workflow
- changing ProtonMail to support provider-side mutation
- adding delete, trash, or broad archive behavior
- background scheduling in the first slice
- redesigning the taxonomy before the recurring unlabeled tail is visible
- building a large eval framework
- a major UI redesign of the local workbench
- solving every exception pattern in one slice

## Further Notes

- The milestone for this PRD is supervised confidence in daily Gmail whole-inbox use, not fully unattended autonomy.
- The first question is not "can we schedule it?" but "are the remaining exceptions visible and manageable enough to justify daily use?"
- The first implementation slice should leave the repo with a clearer picture of the recurring exception tail and a better basis for choosing the next thin classifier slice.
