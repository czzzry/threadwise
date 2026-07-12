# Ultra-minimal connected/disconnected Gmail extension state

Status: Completed
Type: Implementation
GitHub issue: `#23`
Parent: GitHub issue `#16`; `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`
Depends on: `#24`
Completed by: `extensions/gmail_companion/background.js`, `extensions/gmail_companion/content.js`

## What to build

Update the Gmail companion extension/sidebar so disconnected Threadwise is visible but extremely small by default.

The founder should not see a large persistent error panel when the helper is down. The collapsed state should be tiny, with diagnostics and remediation steps shown only after expansion.

## Acceptance criteria

- [x] Connected Gmail panel defaults to minimized.
- [x] Disconnected state defaults to an ultra-minimal badge/presence.
- [x] Expanded disconnected state shows failure reason and remediation steps.
- [x] Needs-attention state uses a badge/count/indicator, not auto-expand.
- [x] Copy distinguishes helper unreachable, health check failed, and wrong service on port when the health contract allows it.
- [x] Tests cover connected, disconnected, and needs-attention visual state contracts.

## Safety boundaries

- Do not add auto-expand for attention in this slice.
- Do not add silent restart behavior.
- Do not change Gmail mutation scope.

## Parallelization

Can run in parallel with `#22` after `#24` defines the health/status contract.
