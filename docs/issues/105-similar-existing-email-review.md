# Similar Existing Email Review

GitHub issue: `#34`

## Parent

GitHub issue `#27` - PRD: MVP+3 Gmail sidebar interactive teaching loop

## What to build

Use stored Threadwise data to conservatively estimate and review similar existing emails affected by a correction proposal. First version review is apply-all-or-cancel, with no checkbox-level selection.

## Acceptance criteria

- [ ] Similar existing-email estimates use stored Threadwise data only.
- [ ] Matching is conservative, based on signals such as sender/domain, current label/category, and obvious subject patterns.
- [ ] The affected count is clickable/reviewable before any multi-email application.
- [ ] The first version supports apply-all-or-cancel and does not expose per-email checkbox mutation.
- [ ] Tests prove no live Gmail scan/fetch is used for affected-count estimates.

## Blocked by

- GitHub issue `#32` - Correction Proposal Session
