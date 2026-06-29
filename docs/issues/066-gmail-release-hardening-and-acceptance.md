# Status

Current
Current as of: 2026-06-29
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/064-inbox-correct-teach-conversation.md`, `docs/issues/065-sidebar-daily-summary-and-unsubscribe-flow.md`

# Title

Harden the Gmail companion release and prove supervised acceptance

## Type

Feature

## Blocked by

- `docs/issues/064-inbox-correct-teach-conversation.md`
- `docs/issues/065-sidebar-daily-summary-and-unsubscribe-flow.md`

## User stories covered

`19`, `20`, `21`, `22`, `31`, `33`, `36`, `37`, `38`

## What to build

Finish the Gmail release as a trustworthy supervised product rather than a promising prototype.

This slice should harden the integrated experience:

- selected-email context stays stable while browsing Gmail
- the sidebar, correction flow, and unsubscribe signals work together coherently
- prompting stays within the agreed product budget
- ignored clarification prompts degrade gracefully instead of creating churn
- changes made by the agent are easy to see in compact form
- live Gmail browsing validates that the release flow works end to end under real usage conditions

This is the slice that should turn "the pieces exist" into "the Gmail release is actually ready to be used."

## Acceptance criteria

- [ ] The integrated Gmail companion flow works during supervised real Gmail browsing.
- [ ] Prompting behavior stays within the bounded product budget or batches appropriately.
- [ ] Ignored clarification prompts leave the system in a safe and understandable state.
- [ ] Agent-made changes are visible in lightweight operational summaries.
- [ ] The release has a clear supervised acceptance pass and any remaining sharp edges are documented.

## Output

- hardened Gmail companion release flow
- supervised acceptance notes
- documented remaining sharp edges, if any
