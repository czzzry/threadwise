# Title

Execute selected Gmail unsubscribes with audit

## Type

HITL

## User-visible goal

Allow the founder to execute previously selected Gmail unsubscribe candidates using explicit confirmation, while recording a durable audit trail for each attempt and leaving unsupported methods clearly marked for manual follow-up.

## Scope

- Read locally selected unsubscribe candidates from the existing workbench state
- Preview which selected candidates are executable now versus unsupported
- Execute only explicit `http` or `https` `List-Unsubscribe` links
- Require an explicit confirmation step before execution
- Persist a durable per-candidate audit record with method, status, timestamp, and notes

## Non-goals

- `mailto:` unsubscribe execution
- Browser-assisted/manual automation fallbacks
- Gmail inbox mutation during unsubscribe execution
- Cross-provider execution workflows

## Acceptance criteria

- The founder can preview selected unsubscribe candidates before any outbound request is sent
- Only candidates with supported one-click HTTP methods are executed
- Unsupported or missing methods are recorded clearly without pretending success
- Each execution attempt produces a durable local audit artifact
- The workbench can show the latest unsubscribe status after execution

## Expected tests or verification

- Test parsing and executing one-click HTTP unsubscribe links from selected candidates
- Test that `mailto:`-only candidates are marked unsupported in the audit
- Test that the workbench/API requires explicit confirmation before execution
- Test that the audit artifact records status, method, timestamp, and notes per candidate
