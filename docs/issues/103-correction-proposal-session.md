# Correction Proposal Session

GitHub issue: `#32`

## Parent

GitHub issue `#27` - PRD: MVP+3 Gmail sidebar interactive teaching loop

## What to build

Turn natural-language text from the Agent View input into a pinned correction proposal session. The proposal should distinguish explanation requests from correction instructions and, for corrections, show proposed current-email relabel, future rule, expandable structured rule, affected-count estimate, and separate follow-up actions.

## Acceptance criteria

- [ ] Natural-language correction input creates a pending correction session tied to the originating selected email.
- [ ] The pending session shows current label/status, proposed label/status, plain-English rule, expandable structured rule, and affected-count estimate.
- [ ] The pending session remains pinned when selected email context changes until the founder applies, cancels, or refines it.
- [ ] Tests use fake model/rule clients and prove no live LLM API is called.

## Blocked by

- GitHub issue `#28` - Selected Email Agent View
