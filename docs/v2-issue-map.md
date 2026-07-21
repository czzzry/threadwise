# V2 Issue Map

Status: Historical candidate next-slice map
Historical context as of: 2026-06-29
Current stage: [CONTEXT.md](../CONTEXT.md)
Builds on: `docs/checkpoints/current-operating-model-2026-06-22.md`
Bounded PRD at the time: `docs/prd.md`

This file is a candidate map, not an approved implementation sequence.

Do not treat it as authorization to code the next major slice without a focused grill, a current scope note or PRD, and triage.

## Current Position

The repo already proves the operating model through later slices beyond the original Gmail MVP, including:

- daily Gmail runs
- daily and weekly reports
- provider-aware artifacts
- ProtonMail read-only flows
- unsubscribe inventory and supported execution
- maintenance refactors for UI responsibilities and artifact contracts

The current bounded planning focus is the Gmail inbox companion release through `docs/prd.md`.

## Candidate Decision Lanes

### Gmail Companion Surface

Possible focus:

- build the Gmail companion sidebar shell
- stabilize selected-email context and current-status rendering
- make the inbox the primary product surface rather than the workbench

### In-Inbox Teaching Loop

Possible focus:

- add `Correct / Teach` directly in Gmail
- acknowledge user feedback in short conversational replies
- preview broader impact before changing other existing emails
- support refine-and-compare when the agent misunderstood feedback

### Daily Summary / Unsubscribe

Possible focus:

- keep the sidebar useful on quiet days with a compact daily summary
- surface unsubscribe opportunities in context
- hand off cleanly to fuller dashboard and unsubscribe views when needed

### Release Hardening

Possible focus:

- harden real-time selected-email continuity
- enforce bounded prompting
- verify graceful behavior when clarification prompts are ignored
- prove the release flow against live Gmail browsing

## Selection Rule

Prefer the next slice that:

1. solves the most concrete current pain
2. moves the inbox-native Gmail release directly
3. does not broaden provider risk or inbox-action scope without explicit approval
4. is large enough to deliver a visible product step while still fitting in one current PRD and one triaged issue

## Next-Step Rule

Before implementing from this map:

1. use `docs/prd.md` as the current Gmail release brief
2. start with the sidebar-spine slice that freezes shared UI and selected-email contracts
3. then parallelize the teaching-loop slice and the summary/unsubscribe slice
4. finish with Gmail release hardening and supervised acceptance
