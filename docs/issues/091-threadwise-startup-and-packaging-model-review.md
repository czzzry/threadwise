# Threadwise startup and packaging model review

Status: Completed
Type: HITL
GitHub issue: `#16`
Parent: GitHub issue `#7`; `docs/prd.md`
Completed by: `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`

## What to build

Review Threadwise's startup and delivery model after MVP+2 clarifies daily use.

The current extension plus local companion is acceptable for MVP+2, but the founder does not want the long-term product experience to require remembering Python commands or manually managing a server. This review should compare delivery options and choose the next packaging direction.

## Acceptance criteria

- [x] The review maps the current extension, local companion server, dashboard, daily run, and local artifacts.
- [x] The review compares realistic delivery options: improved local companion, packaged desktop helper, native messaging host, menubar/background app, cloud service plus extension, and Gmail-native alternatives where relevant.
- [x] The review identifies which product logic should remain delivery-model independent.
- [x] The review identifies which current startup/status improvements remain valuable under future delivery models.
- [x] The review recommends the next packaging/startup milestone.
- [x] The review produces follow-up implementation issues if a native helper, installer, packaged app, or background service is approved.

## Blocked by

- MVP+2 Run Gmail check and status UX should land first so the review is based on a real daily-use loop.

## Follow-up issues

- `#22` / `097`: Threadwise Personal Startup LaunchAgent setup/status
- `#23` / `098`: Ultra-minimal connected/disconnected Gmail extension state
- `#24` / `099`: Local companion health/status endpoint
- `#25` / `100`: Future full installer and menubar app packaging review
- `#26` / `101`: Future AI OS local-control API review
