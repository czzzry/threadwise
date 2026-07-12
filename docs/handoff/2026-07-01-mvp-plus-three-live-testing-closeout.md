# MVP+3 Live Testing Closeout

Status: Current handoff after founder live-testing tranche
Current as of: 2026-07-01

## Summary

MVP+2 Gmail daily usefulness is complete. MVP+3 Slice A and Slice B are complete locally, and the founder live-testing sidetrack produced a set of bounded follow-up fixes around the Gmail companion, teaching loop, startup/status UX, feedback capture, and unsubscribe safety.

The current working tree is intentionally dirty and should be reviewed/packaged before starting the next major product slice.

## Completed Locally

- MVP+3 Slice A: in-Gmail selected-email Agent View and Correct / Teach loop.
- MVP+3 Slice B: compact companion shell, brand fallback, startup/status polish, and friendlier disconnected states.
- Live feedback capture: always-available note capture from the companion, persisted locally without full email bodies.
- Sidebar usability fixes: scrollable panel, cleaner selected-email layout, explicit Gmail open actions, clearer changed-today actions, corrected label-selector copy, and unsubscribe-card styling.
- Teach-preview hardening:
  - blank dropdown can infer labels from clear notes such as spam/phishing/job/interview.
  - Przelewy/phishing notes infer `EA/LowValue`.
  - broader similar candidates are surfaced separately from exact matching-existing emails.
  - broader similar candidates stay review-only and are not silently relabeled by `matching-existing`.
- LinkedIn unsubscribe safety:
  - LinkedIn-hosted raw HTTP unsubscribe previews warn about provider signed-in/error pages.
  - selected-email surfaces no longer present unsupported raw HTTP unsubscribe URLs as the primary action.
  - direct selected-email unsubscribe opens are limited to `mailto:` manual actions; ready/unsupported HTTP paths route through queue/review.

No live unsubscribe execution, Gmail delete/archive/send/reply, or new broad Gmail mutation was introduced in this tranche.

## Current Issue State

- `#41` / `docs/issues/114-live-testing-tranche-sidebar-context-and-teach-fixes.md`: complete.
- `#42` / `docs/issues/115-redesign-correct-teach-ux-from-live-testing.md`: open, needs founder alignment before implementation.
- `#43` / `docs/issues/116-review-unsubscribe-link-behavior-for-provider-error-pages.md`: partial local safety fix complete; broader direct-link policy remains open.
- `docs/issues/117-perfect-core-gmail-inspect-teach-loop-from-live-notes.md`: implemented local tranche plus AFK hardening follow-up.

## Validation

Latest local verification:

- `python3 -m unittest discover -s tests`
- Result: `549 tests OK`
- `node --check extensions/gmail_companion/content.js`
- Result: OK
- Debug instrumentation scan: no `DEBUG-*` markers found.

## Packaging Recommendation

Before starting the next product slice:

1. Review the dirty worktree and make sure all MVP+3/live-testing docs and code changes are intended.
2. Commit this as one closeout commit or split into two commits:
   - MVP+3 companion/teaching/live-feedback implementation
   - live-testing hardening and unsubscribe safety follow-up
3. Push/open/update a PR if continuing with PR flow.

## Recommended Next Slice

Start a fresh alignment cycle for `#42`: Correct / Teach redesign.

The next useful product question is not whether the current loop works; it does. The question is whether the first-visible teaching interaction should become intent-first:

- user types the complaint/correction first,
- Threadwise proposes current relabel vs broader rule,
- affected emails are inspectable,
- current-email, similar-existing, and future-rule application remain separate confirmations.

Do not implement this redesign before founder alignment. It changes the main daily-use interaction model.

