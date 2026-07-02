# Add Read-Only Expanded Affected-Email Review Mode

GitHub issue: `#46`

Parent: GitHub issue `#42`

## What to build

Add an expanded Threadwise review mode for exact affected-email inspection.

From the sidebar, `Review N` should expand Threadwise into a wider right-side panel while leaving a small Gmail inbox strip visible for continuity. The expanded view should show exact affected emails in dense inbox-like rows and keep the pending rule session pinned.

## Acceptance criteria

- [ ] Sidebar impact count exposes `Review N` when affected emails exist.
- [ ] `Review N` opens an expanded Threadwise-owned review mode, not a new tab, Gmail search result, modal, or tiny sidebar list.
- [ ] Expanded mode leaves some Gmail surface visible on the left for continuity.
- [ ] Affected emails render as dense rows with sender, subject, current label, proposed label, and status.
- [ ] Each row has `Open in Gmail` for deep inspection.
- [ ] Expanded mode has clear `Collapse` / `Back to sidebar` behavior.
- [ ] The pending rule session remains pinned across collapse/expand and Gmail email opening.
- [ ] This slice is read-only: no broader apply or exclusion persistence yet.

## Blocked by

- GitHub issue `#45`
