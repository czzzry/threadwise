# Selected Email Agent View

GitHub issue: `#28`

## Parent

GitHub issue `#27` - PRD: MVP+3 Gmail sidebar interactive teaching loop

## What to build

Make Agent View center on the currently selected Gmail email. It should show the selected email identity, concrete `EA/...` label, human-readable status, an honest likely-reason explanation, and an always-visible text input that can later support explain/correct interactions. When no email is selected, Agent View should prompt the founder to open an email and keep Today summary available below.

## Acceptance criteria

- [ ] Agent View renders the selected email identity, concrete `EA/...` label, human-readable status, and likely reason when a selected email is available.
- [ ] The explain/correct input is visible without hunting or scrolling in the selected-email Agent View.
- [ ] Empty Agent View prompts the founder to open an email and keeps Today summary visible below.
- [ ] Tests cover selected-email and no-selected-email states without calling live Gmail or live LLM APIs.

## Blocked by

None - can start immediately.
