# Review Unsubscribe Link Behavior for Provider Error Pages

GitHub issue: `#43`

Status: Complete

## What to explore

Live testing showed that opening a LinkedIn unsubscribe URL can lead to a raw provider error page. The unsubscribe review flow should avoid making broken provider endpoints feel like Threadwise failures.

## Acceptance criteria

- [x] Add clearer copy for unsupported or provider-error-prone unsubscribe paths.
- [x] Preserve explicit confirmation before any unsubscribe execution.
- [x] Stop selected-email sidebar cards from presenting unsupported raw HTTP unsubscribe URLs as the primary action.
- [x] Revisit when Threadwise should show direct unsubscribe links versus only queue/review actions.
- [x] Decide whether one-click unsubscribe URLs should be executed through the supported audited flow instead of opened directly.

## Product decision

- Selected-email sidebar cards should only offer direct unsubscribe opens for `mailto:` manual follow-up.
- Supported one-click HTTPS unsubscribe candidates should be queued/reviewed from the sidebar and executed only through the audited unsubscribe flow after explicit confirmation.
- Unsupported HTTP/provider unsubscribe URLs may still be exposed as manual provider pages in the dedicated unsubscribe review surface, but the copy must say that the link may require a signed-in provider session or may show a provider error page.
- Opening a manual provider page is not a Threadwise unsubscribe action.

## Local diagnosis

The immediate LinkedIn symptom is that Threadwise can correctly classify a candidate as unsupported while still rendering a raw `https://www.linkedin.com/...` unsubscribe URL as `Open unsubscribe` in the selected-email surface. Clicking that can land on a provider-owned signed-in/error page, which feels like a Threadwise failure.

Local fix:

- LinkedIn-hosted HTTP unsubscribe previews now explain that the provider link may open a signed-in error page.
- The live Gmail companion selected-email card and simulator selected-email card only expose direct unsubscribe opens for `mailto:` manual actions.
- Ready one-click and unsupported HTTP unsubscribe paths are routed through queue/review actions from the selected-email card.
- The dedicated unsubscribe review page no longer labels HTTP URLs as generic `Open unsubscribe link`.
- Ready one-click HTTPS candidates show an audited-action-only note instead of a raw browser link.
- Unsupported HTTP candidates are labeled as manual provider pages and explicitly say that opening them does not execute a Threadwise unsubscribe.

No real unsubscribe execution, Gmail mutation, delete, archive, send, or provider request was introduced.
