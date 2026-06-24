# Status

Current
Current as of: 2026-06-24
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/decisions/gmail-bounded-autonomy.md`, `docs/decisions/gmail-whole-inbox-readiness-policy.md`
Blocked by: arrival of fresh Gmail mail to measure

# Title

Prove supervised Gmail daily use on new mail

## Type

AFK

## User-visible goal

Give the founder a bounded, artifact-backed answer about whether the current Gmail daily run stays trustworthy on genuinely new incoming mail, not just on replayed historical backfill.

## Scope

- start only after the historical Gmail frontier is exhausted
- define the proving window as the first `10` fresh Gmail daily runs that fetch at least one new message after frontier exhaustion
- treat a run that prints `No new messages found.` as a no-op day that does not count toward the proving window
- run the existing daily Gmail command on fresh mail only and record the resulting batch IDs
- evaluate each counted fresh batch immediately with `scripts/check_gmail_readiness.py --batch-id <fresh-batch-id>` so the evidence points at the exact new-mail run rather than the latest historical report
- use `scripts/replay_gmail_readiness.py --account-id founder-test` only as a baseline guardrail before or during the proving window, not as the success metric for fresh-mail proof
- record for each counted run:
  - batch ID
  - report date
  - processed count
  - unlabeled count
  - exception rate
  - readiness status (`PASS`, `WARN`, or `PAUSE`)
  - any unlabeled leftovers that recur across fresh runs
- allow follow-on classifier work only for recurring fresh-mail misses that appear in at least `2` counted fresh batches
- keep the Gmail mutation boundary exactly as it is today

## Non-goals

- returning to broad historical backfill
- treating the latest historical daily report as proof for fresh-mail readiness
- broad taxonomy redesign
- unattended scheduling
- background jobs
- broader Gmail actions such as delete, trash, or archive expansion
- ProtonMail write-side behavior
- building a new evaluation framework before the proving window is run once

## Acceptance criteria

- The slice starts from a documented frontier-exhausted baseline:
  - live Gmail check returns `No new messages found.`
  - stored replay still reports `PASS`
- The proving window is explicit and bounded to the first `10` fresh Gmail daily runs after frontier exhaustion.
- Each counted fresh run is evaluated against its own batch with the existing readiness-check command rather than inferred from whichever historical report happens to be latest on disk.
- The proving log distinguishes:
  - counted fresh runs
  - no-op days with no new mail
  - recurring fresh-mail misses that may justify follow-on classifier work
- The slice ends with a short durable summary that states:
  - how many fresh runs were counted
  - pass/warn/pause totals
  - whether any consecutive readiness breaches occurred
  - which leftover misses recurred across fresh runs, if any
  - whether supervised daily Gmail use on new mail currently looks operationally trustworthy

## Expected behavior

- New mail continues to be fetched, classified, labeled, and subject to bounded low-value `INBOX` removal under the current Gmail decision.
- A fresh batch is judged from its own artifacts, so historical backfill reports do not distort the fresh-mail proof.
- Single isolated misses remain evidence to watch, not automatic justification for a new cleanup campaign.
- Repeated fresh-mail misses become concrete candidates for small follow-on classifier slices.

## Expected tests or verification

- Before the proving window begins:
  - `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 100`
  - `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- For each counted fresh run:
  - `python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 100`
  - `python3 scripts/check_gmail_readiness.py --account-id founder-test --batch-id <fresh-batch-id>`
- Periodically during the window:
  - `python3 scripts/replay_gmail_readiness.py --account-id founder-test`
- Only if recurring fresh misses appear:
  - targeted classifier tests for the specific recurring family

## Dependencies/order

- Start only after the historical frontier has been exhausted.
- Use `docs/prd.md` as the current product source of truth.
- Treat this issue as the current bounded operational slice under the current PRD.
- Do not open a follow-on classifier issue unless the same fresh-mail miss recurs in at least `2` counted runs.
- A staged historical rollout may begin under `docs/issues/053-stage-supervised-gmail-historical-rollout.md` once the first `3` counted fresh runs satisfy the start gate, even though this issue's stronger `10`-run proof window remains open.

## Stop conditions requiring Founder review

- New mail reveals a qualitatively new category that challenges the current taxonomy.
- A counted fresh run reaches `PAUSE`, or two consecutive counted fresh runs breach the readiness threshold.
- The work starts drifting toward unattended scheduling or broader inbox autonomy.
- The proving loop begins to depend on manual interpretation of historical backfill artifacts instead of fresh-run evidence.
