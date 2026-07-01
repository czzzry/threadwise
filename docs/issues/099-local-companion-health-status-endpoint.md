# Local companion health/status endpoint

Status: Follow-up candidate
Type: Implementation
GitHub issue: `#24`
Parent: GitHub issue `#16`; `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`

## What to build

Add a compact health/status endpoint to the local companion so setup tools and the extension can verify that the service on `127.0.0.1:8021` is actually Threadwise and understand basic readiness.

## Acceptance criteria

- [ ] Adds a read-only health/status endpoint.
- [ ] Response includes stable service identity, version/schema, status, bound origin, storage path summary, and dashboard path.
- [ ] Response does not include private email content, credentials, OAuth tokens, or full artifact contents.
- [ ] Extension/setup code can distinguish unreachable helper from non-Threadwise service.
- [ ] Tests cover healthy response shape and privacy boundaries.

## Safety boundaries

- Read-only endpoint.
- No live Gmail calls.
- No credential inspection.
- No private email content in response.

## Parallelization

Should land before or alongside `#22` and `#23`.
