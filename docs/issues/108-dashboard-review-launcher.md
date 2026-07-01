# Dashboard Review Launcher

GitHub issue: `#30`

## Parent

GitHub issue `#27` - PRD: MVP+3 Gmail sidebar interactive teaching loop

## What to build

Make existing dashboard email rows act as review launchers rather than inert lists. Rows should expose minimal `Open in Gmail` actions where link/search data exists, while full teaching and correction remain in the Gmail sidebar.

## Acceptance criteria

- [ ] Existing dashboard email rows expose `Open in Gmail` or equivalent navigation when sufficient message data exists.
- [ ] The dashboard does not duplicate the full correction/teaching workflow.
- [ ] Needs attention and other dashboard lists remain useful as review launchers.
- [ ] Tests cover row action rendering and absence of dashboard-only mutation.

## Blocked by

- GitHub issue `#28` - Selected Email Agent View
