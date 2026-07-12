# Gmail Readiness And Historical Rollout Run Log

Status: Current operational log
Current as of: 2026-06-27
Related issues: `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`, `docs/issues/053-stage-supervised-gmail-historical-rollout.md`

Use this file to record the fresh-mail proof runs from issue `052` and the staged historical rollout chunks from issue `053`.

## Fresh-Mail Start Gate

Count only runs that fetch at least one new message. If a run prints `No new messages found.`, record it under no-op days and do not count it toward the start gate.

| Counted run | Date | Batch ID | Processed | Unlabeled | Exception rate | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-06-25 | founder-test-batch-47 | 4 | 0 | 0.00% | PASS | Day 1 of 3 fresh-mail start gate. Auto-applied 4 label writes; removed INBOX for 2 bounded low-value messages; exact-batch readiness PASS; stored replay PASS across 47 batches / 3358 messages. |
| 2 | 2026-06-26 | founder-test-batch-48 | 8 | 0 | 0.00% | PASS | Day 2 of 3 fresh-mail start gate. Auto-applied 8 label writes; removed INBOX for 6 bounded low-value messages; exact-batch readiness PASS; stored replay PASS across 48 batches / 3366 messages. |
| 3 | 2026-06-27 | founder-test-batch-49 | 6 | 1 | 16.67% | WARN | Day 3 of 3 fresh-mail start gate. Auto-applied 5 label writes; removed INBOX for 4 bounded low-value messages; exact-batch readiness WARN due to 1 unlabeled exception: Amazon passkey added to account; stored replay WARN across 49 batches / 3372 messages with no mutation evidence violations. Remediated same day with narrow Amazon passkey classifier coverage; stored replay then reported PASS across 49 batches / 3372 messages with batch 49 replaying at 0 unlabeled and no mutation evidence violations. |
| 4 |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |
| 6 |  |  |  |  |  |  |  |
| 7 |  |  |  |  |  |  |  |
| 8 |  |  |  |  |  |  |  |
| 9 |  |  |  |  |  |  |  |
| 10 |  |  |  |  |  |  |  |

## No-Op Days

| Date | Command result | Notes |
| --- | --- | --- |
| 2026-06-27 | `No new messages found.` | Historical rollout rung `200` found no further eligible live Gmail messages after chunk 1. |

## Historical Rollout Chunks

Start only after the first `3` counted fresh runs satisfy the issue `053` start gate.

Gate decision as of 2026-06-27: proceed after remediation. Runs `1` and `2` were clean
`PASS` runs. Run `3` originally warned due to one unlabeled account-security-shaped Amazon
passkey notice, but that miss was a narrow gap in an existing Amazon passkey/account-security
rule. After targeted classifier coverage, stored replay returned `PASS` across `49` batches /
`3372` messages, including batch `49` replaying with `0` unlabeled items and no mutation
evidence violations. Founder approved proceeding with the staged rollout instead of waiting
for a fourth fresh run.

| Chunk | Target size | Date | Batch ID | Processed | Auto-applied | INBOX removals | Unlabeled | Exception rate | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 100 | 2026-06-27 | founder-test-batch-50 | 1 | 1 | 1 | 0 | 0.00% | PASS | First historical rollout rung fetched only 1 eligible live Gmail message. Exact-batch readiness PASS; stored replay PASS across 50 batches / 3373 messages with no mutation evidence violations. |
| 2 | 200 | 2026-06-27 | n/a | 0 | 0 | 0 | 0 | 0.00% | n/a | Command returned `No new messages found.`, so no stored batch was created and no Gmail mutation occurred. |
| 3 | 300 |  |  |  |  |  |  |  |  |  |
| 4 | 300-400 |  |  |  |  |  |  |  |  |  |
| 5 | 300-400 |  |  |  |  |  |  |  |  |  |
| 6 | 300-400 |  |  |  |  |  |  |  |  |  |

## Commands

Fresh-mail proof:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 100
python3 scripts/check_gmail_readiness.py --account-id founder-test --batch-id <fresh-batch-id>
```

Historical rollout chunk:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size <chunk-size>
python3 scripts/check_gmail_readiness.py --account-id founder-test --batch-id <chunk-batch-id>
```

Periodic guardrail:

```bash
python3 scripts/replay_gmail_readiness.py --account-id founder-test
```
