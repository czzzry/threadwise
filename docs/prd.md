# PRD

Status: Completed bounded-slice PRD
Current as of: 2026-07-02
Builds on: `docs/v2-alignment.md`, `docs/handoff/2026-07-02-gmail-companion-ux-feedback-triage.md`, and founder alignment from July 2 live testing
Supersedes as current planning focus: `docs/archive/prd-mvp-plus-three-slice-b-gmail-companion-shell-polish-completed-2026-07-02.md`
Release target: MVP+4 Gmail companion Home, modes, and unresolved review
GitHub parent issue: `#51` (closed)

This PRD described the Threadwise Gmail companion slice after live testing showed that the product had working pieces but lacked a coherent daily-use flow. The `#51` through `#57` batch is now implemented and closed; see `docs/handoff/2026-07-02-afk-gmail-companion-ux-progress.md` for completion evidence.

## Problem Statement

Threadwise can label Gmail, show selected-email context, teach rules, route unsubscribe review, and show dashboard reports. The founder's latest testing showed the remaining problem is not more widgets. It is that the sidebar loads into stale or cluttered context, mixes several jobs at once, and does not provide a fast way to clear emails Threadwise could not label.

The core problem is:

> Can Threadwise become a simple mode-based Gmail companion: ambient when everything is fine, focused when correcting the current email, and fast when clearing unresolved mail?

## Target Model

Threadwise has one simple status header and mode-based body content.

### Status Header

The header is omnipresent and color-coded:

- `Ready` / green: connected, recent enough, no blocking issue.
- `Working` / yellow-blue: sync or user action is in progress.
- `Needs check` / yellow: connected, but freshness or unresolved work needs attention.
- `Disconnected` / red: local companion is unreachable.
- `Error` / red: last action failed and needs recovery.

Raw technical details stay hidden by default.

### Modes

Threadwise uses two widths only:

- Compact panel: Home, current email, text-first teaching, status, and small contextual actions.
- Review panel: dense row workflows such as unresolved review and affected-match review.

The body should show only the current job. Dashboard lists, full "What changed today", technical details, and unrelated widgets should not stack in the sidebar.

## User Stories

1. As the founder, I want Threadwise to open to a clean Home state when no Gmail email is open, so that it never shows a stale old email by default.
2. As the founder, I want Threadwise to automatically show the current-email view when Gmail clearly has an opened email, so that the sidebar follows normal Gmail browsing.
3. As the founder, I want Threadwise to use a single simple status area, so that connection, freshness, and recovery state are understandable without technical clutter.
4. As the founder, I want Home to be a launcher, not a dashboard, so that I can choose the job I want without reading unrelated details.
5. As the founder, I want a dedicated `Review unresolved` mode, so that I can clear unlabelled, unsure, and conflicting emails quickly.
6. As the founder, I want unresolved review rows to be dense and inbox-like, so that I can scan many emails without giant cards.
7. As the founder, I want to inspect the full Gmail email while staying in unresolved review, so that I can make the right call without losing queue progress.
8. As the founder, I want teaching one unresolved email to check for matching unresolved emails, so that a few rule decisions can shrink a large queue.
9. As the founder, I want broad unresolved application to require confirmation, so that Threadwise never silently rewrites many emails.
10. As the founder, I want applying a rule to show a compact result and then offer `Next unresolved`, so that the workflow is fast but still trustworthy.
11. As the founder, I want Current email mode to be sparse, so that it shows only sender, subject, label/status, `Correct / Teach`, and small contextual actions.
12. As the founder, I want label reasons hidden behind a small `?` or details affordance, so that explanations are available but not always visible.
13. As the founder, I want Correct / Teach to replace the body with a focused teaching state, so that the sidebar does not become stacked and messy.
14. As the founder, I want the text box to be the primary teaching interface, so that I can talk to Threadwise instead of using a manual label selector.
15. As the founder, I want manual label selection to be optional and secondary, so that it never overrides my note unless I explicitly choose it.
16. As the founder, I want dashboard and unsubscribe review to remain separate worlds, so that the sidebar stays clean.
17. As the founder, I want the selected-email unsubscribe entry to be small and route to safe review, so that raw provider links do not feel like Threadwise failures.
18. As the founder, I want all companion content to remain inside its panel width, so that responses and buttons never overflow the Gmail sidebar.

## Implementation Slices

1. `#54` Build Threadwise Home and two-mode companion shell.
   - Type: AFK.
   - Goal: clean load behavior, compact Home, status header, Current email mode, and removal of full sidebar "What changed today".

2. `#53` Build unresolved review mode with queue compression.
   - Type: AFK after `#54`.
   - Goal: Review-panel queue for unlabelled, unsure, and conflicting emails; inspect in Gmail while pinned; apply confirmed lessons to matching unresolved emails.

3. `#52` Tighten shared text-first Correct / Teach.
   - Type: AFK after `#54`, can overlap with `#53` after shell contracts are stable.
   - Goal: shared teaching component for current-email and unresolved flows, hidden reasons, secondary manual label override, clearer action hierarchy.

4. `#56` Add immediate loading and exact outcome states.
   - Type: AFK.
   - Goal: visible click registration, working state, duplicate-submit protection, exact result copy, and safe recovery.

5. `#55` Enforce sidebar containment.
   - Type: AFK.
   - Goal: regression coverage that no companion response, button row, or panel exceeds compact or review widths.

6. `#57` Keep dashboard launches in active Gmail context.
   - Type: AFK after core mode model.
   - Goal: dashboard email actions preserve continuity with the existing Gmail companion tab where feasible.

## Out of Scope

- Multi-label teaching semantics.
- A separate standalone rule-management product surface.
- Attention/important-but-labeled workflow as a top-level sidebar mode.
- Full dashboard redesign.
- New Gmail mutation types.
- Delete, trash, send, reply, broad archive, or autonomous unsubscribe behavior.
- Raw provider unsubscribe links from selected-email sidebar.
- More than two panel widths.

## Testing Decisions

- Unit tests should protect mode-selection behavior: Home for list/no-email, Current email for confident opened-email context, and no stale default email.
- UI tests should prove Home is a launcher and does not render the full "What changed today" list.
- Review-mode tests should prove dense unresolved rows, pinned review context, and explicit exit actions.
- Teaching tests should prove text-first interpretation, optional manual label override, and separate current-email / matching-unresolved / future-rule actions.
- Browser acceptance should include compact and review width overflow checks.
- Failure-state tests should prove user copy says what changed, what did not change, and what to do next.
