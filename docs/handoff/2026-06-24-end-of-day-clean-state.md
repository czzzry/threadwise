# Handoff

Current as of: 2026-06-24

## Current source of truth

Read in this order before continuing:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`

## Repository state

- Working tree is clean as of this handoff.
- Full local validation passed:
  - `python3 -m compileall -q src tests`
  - `python3 -m unittest discover -s tests`
  - result: `296` tests passed
- No live Gmail, ProtonMail, unsubscribe, or other inbox action was run after the final commit cleanup.

## Commits added today

- `45dd91c` Refactor batch workflow command boundaries
- `b1553b8` Update current-state docs and agent workflow
- `d02fd89` Document and test Gmail bounded autonomy
- `207f441` Harden live Gmail client fetching
- `5721008` Add recurring unlabeled exception inspection
- `b709452` Close reviewed unlabeled classifier gaps
- `9baad02` Add Gmail whole-inbox readiness checks
- `7a701e8` Add Gmail readiness handoffs and next slices
- `b07ce3e` Ignore local Lavish scratch artifacts

## What changed

- Current repo docs now distinguish current operating docs from historical V1 artifacts.
- Local agent workflow and triage guidance are documented.
- Gmail bounded-autonomy rules are explicit and covered by tests.
- Gmail live fetch now paginates beyond the first `500` messages and retries transient failures.
- Reviewed-unlabeled exception inspection exists as a local read-only command.
- Classifier cleanup closed the known reviewed-unlabeled frontier under stored Gmail replay.
- Gmail whole-inbox readiness policy, run-level readiness check, and stored-batch readiness replay are implemented.
- The next active operational slice is issue `052`, which waits for genuinely fresh Gmail mail.

## Next bounded action

Wait for genuinely fresh Gmail mail, then follow `docs/issues/052-prove-supervised-gmail-daily-use-on-new-mail.md`.

When fresh mail is expected, run:

```bash
python3 scripts/daily_live_gmail_run.py --account-id founder-test --batch-size 100
```

If it fetches a fresh batch, immediately evaluate that exact batch:

```bash
python3 scripts/check_gmail_readiness.py --account-id founder-test --batch-id <fresh-batch-id>
```

If the command prints `No new messages found.`, record it as a no-op day and do not count it toward the proving window.

## Do not do next

- Do not start another broad refactor pass.
- Do not treat latest-on-disk historical reports as fresh-mail proof.
- Do not broaden Gmail actions beyond the bounded-autonomy decision.
- Do not add ProtonMail write behavior without explicit product alignment.
- Do not continue live inbox work without confirming the action is intended for the current session.
