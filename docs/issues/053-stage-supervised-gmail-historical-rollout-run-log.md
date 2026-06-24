# Gmail Readiness And Historical Rollout Run Log

Status: Current operational log
Current as of: 2026-06-24
Related issues: `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`, `docs/issues/053-stage-supervised-gmail-historical-rollout.md`

Use this file to record the fresh-mail proof runs from issue `052` and the staged historical rollout chunks from issue `053`.

## Fresh-Mail Start Gate

Count only runs that fetch at least one new message. If a run prints `No new messages found.`, record it under no-op days and do not count it toward the start gate.

| Counted run | Date | Batch ID | Processed | Unlabeled | Exception rate | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
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
|  | `No new messages found.` |  |

## Historical Rollout Chunks

Start only after the first `3` counted fresh runs satisfy the issue `053` start gate.

| Chunk | Target size | Date | Batch ID | Processed | Auto-applied | INBOX removals | Unlabeled | Exception rate | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 100 |  |  |  |  |  |  |  |  |  |
| 2 | 200 |  |  |  |  |  |  |  |  |  |
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
