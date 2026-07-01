# Future AI OS local-control API review

Status: Follow-up candidate
Type: HITL
GitHub issue: `#26`
Parent: GitHub issue `#16`; `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`

## What to build

Review how Threadwise could expose local capabilities to a future AI OS or personal assistant without replacing the browser inbox companion as the primary daily surface.

## Acceptance criteria

- [ ] Defines which Threadwise capabilities could be safely exposed to local tools.
- [ ] Separates read-only summary/query tools from mutation-capable actions.
- [ ] Preserves browser inbox companion as the primary daily UX.
- [ ] Identifies auth/consent boundaries for local control.
- [ ] Produces implementation issues only if a scoped local API/control-plane path is approved.

## Safety boundaries

- No AI OS integration implementation in this review.
- No new external integrations.
- No Gmail mutations or credential exposure.
- Any future mutation-capable tool must require explicit confirmation.

## Parallelization

Wait until the local helper API shape is stable enough to expose deliberately.
