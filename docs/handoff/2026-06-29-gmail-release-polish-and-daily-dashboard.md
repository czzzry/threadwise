# Threadwise Handoff

Date: 2026-06-29
Repo: `.`
Focus completed: release-polish tranche for the Gmail companion surface, including live acceptance hardening and the first fuller daily dashboard handoff from the inbox sidebar.

## Read first
1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md`
5. `docs/checkpoints/current-operating-model-2026-06-22.md`

## What changed

### 1. Inbox companion got calmer and more usable in live Gmail

Behavior:
- unsynced Gmail messages now offer actionable fallback into synced queue items instead of a dead-end warning
- daily summary metrics and changed-today items stay clickable and previewable
- teaching drafts now survive sidebar refreshes
- deeper provenance moved behind a `Show details` toggle so the default view stays concise

Updated:
- `extensions/gmail_companion/content.js`
- `src/gmail_companion_ui.py`
- `tests/test_gmail_companion_ui.py`

### 2. Live Gmail acceptance harness now proves more realistic user flows

Behavior:
- the CDP acceptance harness now verifies:
  - sidebar load
  - queue preview
  - unsubscribe action visibility
  - summary filter navigation
  - draft persistence across refresh
  - teach-preview impact confirmation copy
- the script now forces the sidebar into a non-empty queue bucket before attempting queue-preview assertions, which removed a flaky assumption from the harness itself

Updated:
- `scripts/live_gmail_companion_acceptance_cdp.mjs`

### 3. Daily dashboard handoff now exists as a real product surface

Added behavior:
- new route: `/daily-dashboard`
- fed by the same stored companion runtime payload as the sidebar
- shows:
  - top-line daily metrics
  - what changed today
  - queued unsubscribe review
  - current queue sections for:
    - needs attention
    - kept visible
    - auto-handled
    - recent queue
- the sidebar now links directly to the dashboard for a fuller operational view

Updated:
- `src/gmail_companion_ui.py`
- `extensions/gmail_companion/content.js`
- `tests/test_gmail_companion_ui.py`

## Validation completed

Passed:
- `python3 -m unittest tests.test_gmail_companion_ui`
- `node --check extensions/gmail_companion/content.js`

Passed live:
- `node scripts/bootstrap_live_gmail_companion_cdp.mjs http://127.0.0.1:9222 http://127.0.0.1:8021`
- `node scripts/live_gmail_companion_acceptance_cdp.mjs http://127.0.0.1:9222 http://127.0.0.1:8021`

Latest live acceptance checks:
- `sidebarLoaded`
- `queuePreviewReached`
- `unsubscribeActionVisible`
- `summaryFilterNavigation`
- `draftPersistsAcrossRefresh`
- `teachPreviewReached`
- `impactWarningVisible`
- `explicitChoiceCopyVisible`
- `keepDiscussingVisible`
- `dailySummaryVisible`

All passed in the latest run.

## Current product state after this tranche

Gmail release surface now includes:
- live minimizable inbox sidebar in Gmail
- selected-email classification and handling view
- in-context `Correct / Teach` preview and confirmation loop
- queued unsubscribe review handoff
- compact daily summary in-sidebar
- fuller daily dashboard handoff for what changed today and queue buckets

This is no longer just a sidebar shell. It is a coherent Gmail-first supervised product slice.

## Remaining gap to full Gmail MVP

Still not fully closed:
- release-readiness/docs can still drift unless refreshed immediately after behavior changes
- live acceptance still depends on host-driven injection instead of pure unpacked-extension parity
- ProtonMail remains explicitly out of this Gmail release scope

## Recommended next step

Treat the Gmail inbox companion build as entering final release-closeout:
- review/push current code
- refresh any remaining current-state docs that still describe the dashboard as future tense
- decide whether to call Gmail MVP done or take one last visual/UI polish pass before release signoff
