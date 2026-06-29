Status: Current handoff
Current as of: 2026-06-29
Builds on: `docs/prd.md`, `docs/issues/064-inbox-correct-teach-conversation.md`, `docs/issues/065-sidebar-daily-summary-and-unsubscribe-flow.md`, `docs/issues/066-gmail-release-hardening-and-acceptance.md`

# Gmail companion simulator acceptance pass

This handoff records the current safe-browser acceptance pass for the Gmail companion before more founder QA.

## What was exercised end to end

The simulator pass now covers real browser interaction against `http://127.0.0.1:8031/simulator`:

1. load simulator and verify initial selected-email state
2. minimize and reopen the companion panel
3. switch summary and inbox filters
4. select a needs-attention email from the inbox list
5. type a teach note and preview broader impact
6. choose `Refine this`
7. verify the previous interpretation stays visible
8. revise the teach note and preview again
9. verify old vs revised interpretation remain visible together
10. type a temporary draft and use `Clear`
11. verify draft text and preview state reset cleanly
12. preview again and apply `future-only`
13. preview again and apply `matching-existing`
14. verify acknowledgment text, visible refresh, and queue update
15. trigger the unsynced-message state
16. verify the panel stays useful and still shows synced queue context
17. click a queue item from the unsynced-message fallback and verify recovery into a selected synced email
18. switch the `Today` filter and click a queue card from the summary itself
19. verify the selected-email panel follows that summary-driven navigation

## What changed in code

- Added visible `Previous interpretation` state to the simulator, local harness, and live Gmail sidebar.
- `Refine this` now preserves the last preview instead of silently discarding it.
- `Clear` and successful apply now clear both the active preview and the preserved prior preview.
- Expanded the CDP validation script to exercise refine, compare, and clear flows instead of only preview/apply.
- Made `Today` queue cards clickable instead of static summary text in the simulator and live Gmail sidebar.
- Added a queue-preview mode in the live Gmail sidebar with a `Back to inbox email` escape hatch.
- Made the unsynced-message state actionable by exposing clickable current-queue recovery cards.
- Added clearer product hierarchy in the simulator, harness, and live sidebar:
  - `Agent view` summary cards
  - `What to do now` guidance
  - `Viewing` context for the active queue slice

## Validation run

- `python3 -m unittest tests.test_gmail_companion_ui`
- `python3 -m py_compile src/gmail_companion_ui.py scripts/run_gmail_companion_simulator.py`
- `node --check scripts/validate_gmail_companion_simulator_cdp.mjs`
- `node --check extensions/gmail_companion/content.js`
- `node scripts/validate_gmail_companion_simulator_cdp.mjs http://127.0.0.1:8032/simulator http://127.0.0.1:9222 future-only`

## Remaining sharp edges

- This pass hardens the teach loop and summary interaction, but it still does not add the fuller unsubscribe family-management flow from the sidebar itself.
- The safe simulator is the current acceptance environment. Live Gmail acceptance is still needed after more product hardening.
- Parallel acceptance runs should not share one mutable simulator instance. Reset between runs.
