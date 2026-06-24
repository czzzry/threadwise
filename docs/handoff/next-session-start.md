# Next Session Start

Use this after `/clear` to re-situate quickly before starting the next task.

## Read First

- [AGENTS.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/AGENTS.md)
- [docs/archive/mvp-checkpoint-v1-issues-001-027.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/archive/mvp-checkpoint-v1-issues-001-027.md)
- [docs/handoff/mvp-v0.1-acceptance.md](/Users/cezarybaraniecki/Documents/AI project/email-agent/docs/handoff/mvp-v0.1-acceptance.md)

## Current State

- Issues `001` through `017` are implemented and checkpointed
- A second real live batch now exists: `founder-test-batch-2`
- The local batch index is available via:

```bash
python3 scripts/list_local_batches.py
```
- The preferred local review surface is now:

```bash
python3 scripts/review_local_batch_in_browser.py --batch-id founder-test-batch-N --port 8001
```

## Startup Instruction

Do not start coding immediately.

1. Re-summarize the then-current MVP from `docs/archive/mvp-checkpoint-v1-issues-001-027.md`.
2. Reconfirm the MVP v0.1 acceptance checkpoint and browser-review/apply sequence.
3. Ask what the current concrete pain is now.
4. Choose the next bounded slice only through the issue-first process:
   - align on the pain
   - draft the issue
   - define expected behavior and tests
   - then implement with `/tdd`

## Guardrails

- Do not invent broad new product scope
- Do not broaden Gmail permissions or Gmail write behavior without explicit approval
- Do not expose private email content by default in new local tools
- Prefer the next slice to stay vertical and user-visible rather than adding generic plumbing
