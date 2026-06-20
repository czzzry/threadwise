# Title

Show inbox-removal status in local inspection and batch index

## Type

AFK

## User-visible goal

Let the user inspect stored live Gmail batches locally and see the persisted `remove INBOX` outcomes from issue `014` through the existing read-only inspection and batch-index commands, without making Gmail API calls, without performing Gmail writes, and without exposing private email content by default.

## Scope

- Extend the existing one-batch local inspection command to summarize persisted inbox-removal status and attempt history
- Extend the existing multi-batch local index command to include a compact inbox-removal summary per batch
- Reuse the inbox-removal status and attempt files already persisted by issue `014`
- Keep the work read-only and local-only
- Preserve the existing privacy-safe default output shape
- Handle missing optional inbox-removal artifacts cleanly per batch
- Define expected behavior and tests before implementation begins

## Non-goals

- Gmail API calls or Gmail writes of any kind
- new inbox-removal behavior
- review, relabel, retry, or write commands
- dashboard UI, server process, or background monitoring
- message-level private content output by default
- taxonomy expansion or changes to inbox-removal eligibility

## Acceptance criteria

- `inspect_local_batch_status` shows inbox-removal counts for one stored batch
- `list_local_batches` includes a compact inbox-removal summary per stored batch
- Missing inbox-removal status or attempt files are handled cleanly rather than failing
- Default output remains privacy-safe and does not print subjects, senders, snippets, bodies, or raw headers
- The slice performs no Gmail API calls, no Gmail writes, and no state mutation anywhere in its public flow

## Expected behavior

- The one-batch inspection command shows inbox-removal status counts such as:
  - applied or removed_from_inbox
  - failed
  - skipped
  - ineligible
  - missing when no persisted status exists for some or all messages
- The one-batch inspection command shows inbox-removal attempt history counts when present
- The multi-batch index includes one compact inbox-removal summary field per batch
- If a batch has no inbox-removal files yet, the read-only commands report that cleanly rather than failing
- The commands remain deterministic enough to test from fixture-like stored batch files only
- No network activity or local state mutation occurs

## Expected tests or verification

- Test one stored batch with inbox-removal status and attempt history
- Test one stored batch with missing inbox-removal artifacts
- Test multi-batch index output including compact inbox-removal state
- Test that default output remains privacy-safe and omits private email content
- Test that no Gmail client/API/write path is involved in the public flow

## Dependencies/order

- Depends on issue `014`
- Should start only after the issue draft is approved for bounded read-only visibility work

## Stop conditions requiring Founder review

- The slice starts drifting toward message-level detail by default rather than summary-only visibility
- The work pressures the project toward dashboard/reporting expansion instead of bounded local inspection
- The change appears to require new persistence contracts rather than reusing the existing `014` artifacts
