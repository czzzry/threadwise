# Title

Manual follow-up path for unsupported unsubscribes

## Type

HITL

## User-visible goal

Show explicit manual follow-up actions in the local workbench for selected unsubscribe candidates that cannot be safely auto-executed, so the founder can still work through `mailto:` and non-one-click HTTP unsubscribe cases without pretending they were handled automatically.

## Scope

- Detect unsupported selected candidates that still expose a manual path
- Show a clear manual action in the workbench for `mailto:` unsubscribes
- Show a clear manual action in the workbench for non-one-click HTTP unsubscribe links
- Preserve the latest execution status and notes alongside the manual action
- Keep all manual actions user-triggered from the local review surface

## Non-goals

- Sending `mailto:` unsubscribe messages automatically
- Browser automation beyond exposing an explicit manual link
- Bulk execution of unsupported methods
- Inventing custom per-provider unsubscribe heuristics

## Acceptance criteria

- Selected `mailto:` candidates render a usable manual follow-up action in the workbench
- Selected non-one-click HTTP candidates render a manual open-link action in the workbench
- Manual-path candidates remain clearly distinct from auto-executable one-click candidates
- Latest unsubscribe audit status remains visible next to the manual action

## Expected tests or verification

- Test that a selected `mailto:` candidate renders a manual mail action in the workbench
- Test that a selected non-one-click HTTP candidate renders a manual open-link action
- Test that one-click executable candidates do not render the manual-only action copy
