# Threadwise startup and packaging model review

Status: Follow-up candidate
Type: HITL
GitHub issue: `#16`
Parent: GitHub issue `#7`; `docs/prd.md`

## What to build

Review Threadwise's startup and delivery model after MVP+2 clarifies daily use.

The current extension plus local companion is acceptable for MVP+2, but the founder does not want the long-term product experience to require remembering Python commands or manually managing a server. This review should compare delivery options and choose the next packaging direction.

## Acceptance criteria

- [ ] The review maps the current extension, local companion server, dashboard, daily run, and local artifacts.
- [ ] The review compares realistic delivery options: improved local companion, packaged desktop helper, native messaging host, menubar/background app, cloud service plus extension, and Gmail-native alternatives where relevant.
- [ ] The review identifies which product logic should remain delivery-model independent.
- [ ] The review identifies which current startup/status improvements remain valuable under future delivery models.
- [ ] The review recommends the next packaging/startup milestone.
- [ ] The review produces follow-up implementation issues if a native helper, installer, packaged app, or background service is approved.

## Blocked by

- MVP+2 Run Gmail check and status UX should land first so the review is based on a real daily-use loop.
