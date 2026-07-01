# Confirm Current-Email Relabel

GitHub issue: `#33`

## Parent

GitHub issue `#27` - PRD: MVP+3 Gmail sidebar interactive teaching loop

## What to build

Add explicit confirmation for relabeling only the currently selected/originating email from a correction proposal. After confirmation, apply the current-email relabel through the existing safe Gmail/local label pathway and show a clear acknowledgement.

## Acceptance criteria

- [ ] A correction proposal exposes a distinct action for relabeling only the current/originating email.
- [ ] Current-email relabel does not happen until the founder confirms.
- [ ] Confirmed relabel updates the visible selected-email state or reports the queued/applied result clearly.
- [ ] Tests prove this path does not apply changes to similar emails or save a future rule.

## Blocked by

- GitHub issue `#32` - Correction Proposal Session
