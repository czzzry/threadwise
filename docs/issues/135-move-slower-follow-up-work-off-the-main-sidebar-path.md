# Move Slower Follow-Up Work Off the Main Sidebar Path

Status: Completed
Current as of: 2026-07-11
Triage state: `completed`
Type: AFK
Parent PRD: `docs/prd-async-threadwise-extension-2026-07-10.md`

## What to build

Separate the fast current-email interaction path from slower follow-up work that does not need to block the founder's immediate experience.

This slice should prove that Threadwise can finish the user-visible current-email response first while deferring slower follow-up such as:

- reusable candidate preparation
- broader sidebar refresh
- heavier summary recomputation
- slower supporting bookkeeping

The founder should feel that Threadwise acted quickly even when secondary work is still completing.

## User stories covered

- 7. As the founder, I want current-email understanding to stay fast even when broader reusable-change preparation is slower, so that the inbox loop stays responsive.
- 8. As the founder, I want reusable future-rule or candidate preparation to happen without stalling the main current-email response, so that teaching remains practical during normal inbox use.
- 9. As the founder, I want sidebar refreshes and broader summary recomputation to stop blocking the main interaction turn, so that the extension does not feel heavier than the job requires.

## Acceptance criteria

- [x] At least one currently slow follow-up path is moved behind the fast current-email response path.
- [x] The founder can receive a useful current-email result before every secondary refresh or reusable-change follow-up completes.
- [x] Follow-up work updates the UI when it completes instead of requiring the founder to guess or manually retry without context.
- [x] Existing safety boundaries and result correctness are preserved.
- [x] Tests prove that the fast-path response and slower follow-up path can complete in separate visible stages.

## Blocked by

- `docs/issues/134-add-async-action-lifecycle-for-teach-and-fix.md`
