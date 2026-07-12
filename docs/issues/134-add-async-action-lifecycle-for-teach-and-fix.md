# Add Async Action Lifecycle for Teach and Fix

Status: Triaged ready-for-agent
Type: AFK
Parent PRD: `docs/prd-async-threadwise-extension-2026-07-10.md`

## What to build

Turn `Correct / Teach` and current-email fix actions into explicit async lifecycle flows instead of one opaque blocking turn.

This slice should prove one end-to-end path where:

1. the founder submits a correction
2. Threadwise acknowledges immediately
3. the sidebar shows a working state
4. the final result is published as `Done`, `Blocked`, or `Retry available`

without leaving the founder guessing whether the request was accepted or whether the extension froze.

## User stories covered

- 4. As the founder, I want Threadwise to acknowledge my action immediately when I teach or fix an email, so that I know my request was accepted.
- 5. As the founder, I want longer-running work to show progress states, so that I do not confuse normal waiting with a broken companion.
- 6. As the founder, I want Threadwise to distinguish `working`, `done`, `blocked`, and `retry` clearly, so that I know what to do next.
- 10. As the founder, I want failed or stalled operations to explain whether I should retry, reconnect, or just wait, so that the product feels trustworthy under imperfect conditions.

## Acceptance criteria

- [ ] Submitting a teach or fix action produces an immediate acknowledgment before the final result is known.
- [ ] The sidebar shows an explicit in-progress action state while the request is still running.
- [ ] Success, blocked, and retryable outcomes are visibly distinct and do not rely on ambiguous prose alone.
- [ ] Duplicate submissions are prevented while the same action is already in progress.
- [ ] Tests cover the async action lifecycle through the companion API contract and visible sidebar behavior.

## Blocked by

- `docs/issues/133-add-async-selected-email-understanding-states.md`
