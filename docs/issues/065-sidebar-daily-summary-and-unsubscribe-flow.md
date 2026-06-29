# Status

Current
Current as of: 2026-06-29
Triage state: `ready-for-agent`
Builds on: `docs/prd.md`, `docs/issues/063-gmail-companion-sidebar-spine.md`

# Title

Build the sidebar daily summary and unsubscribe handoff flow

## Type

Feature

## Blocked by

- `docs/issues/063-gmail-companion-sidebar-spine.md`

## User stories covered

`24`, `25`, `26`, `27`, `28`, `29`, `30`, `31`, `32`, `33`

## What to build

Deliver the operational companion behavior that makes the sidebar useful even when the user is not actively correcting a mislabel.

This slice should:

- make the compact daily summary operational-first
- show what came in, how it was categorized, what was auto-handled, and what still needs attention
- keep the "what the agent changed" signal easy to find
- surface current-email unsubscribe availability when relevant
- support simple obvious current-email unsubscribe actions from the sidebar when already safe and supported
- hand off to a fuller unsubscribe view for family-level selection, preview, and confirmation
- keep safety-sensitive mail visibly separate in the summary and attention states

This slice should not invent a brand-new dashboard system. It should reuse the existing reporting and unsubscribe infrastructure, exposed through the inbox-native product surface.

## Acceptance criteria

- [ ] The sidebar default state includes a compact daily summary that is operationally useful.
- [ ] The summary clearly distinguishes categorized mail, auto-handled mail, and attention-needed mail.
- [ ] The user can see what the agent changed today without reading a long audit log.
- [ ] Unsubscribe availability appears in current-email context when relevant.
- [ ] Simple safe unsubscribe actions can be initiated from the sidebar.
- [ ] Broader unsubscribe cases hand off to a fuller explicit review flow.

## Output

- operational sidebar summary
- contextual unsubscribe signal and quick flow
- handoff into fuller unsubscribe view

