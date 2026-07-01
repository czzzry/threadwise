# Show Needs attention in daily dashboard

Status: Completed
Type: AFK
GitHub issue: `#10`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed in: `c820b8d`

## What to build

Make the daily dashboard the first product surface for the MVP+2 Needs attention lane.

After a Gmail daily run with attention data, the dashboard should open with a clear Needs attention section that separates high-confidence "now" items from lower-confidence possible attention. Each item should explain why it was surfaced and make the safety boundary clear.

## Acceptance criteria

- [x] The daily dashboard reads attention data from the daily report.
- [x] Needs attention now and Possible attention render as separate sections.
- [x] Each item shows subject, sender, category, reason, evidence or evidence summary, and source message context.
- [x] Each item clearly indicates that attention detection itself made no Gmail mutation.
- [x] `insufficient_context` items appear only when high-consequence cues justify surfacing them.
- [x] Empty states are useful when there are no attention candidates.
- [x] Existing dashboard sections for handled mail, kept-visible/unlabeled mail, audit changes, and unsubscribe candidates continue to work.
- [x] Tests cover dashboard rendering with attention items, possible attention items, high-consequence insufficient-context items, and no attention items.

## Blocked by

- GitHub issue `#8`; `docs/issues/083-add-gmail-attention-contract-to-daily-report.md`
