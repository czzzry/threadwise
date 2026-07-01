# Save Future Rule Separately

GitHub issue: `#35`

## Parent

GitHub issue `#27` - PRD: MVP+3 Gmail sidebar interactive teaching loop

## What to build

Persist a future Threadwise rule from a correction proposal only after separate confirmation. Saving the rule affects future runs by default and must not silently relabel existing emails.

## Acceptance criteria

- [ ] A correction proposal exposes a distinct action for saving a future rule.
- [ ] Future-rule save requires explicit confirmation separate from current-email relabel and existing-email application.
- [ ] Saved rules are represented in plain English with an expandable structured form.
- [ ] Tests prove saving a future rule does not mutate existing Gmail/local labels.

## Blocked by

- GitHub issue `#32` - Correction Proposal Session
