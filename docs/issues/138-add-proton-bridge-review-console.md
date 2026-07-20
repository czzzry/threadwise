# Add Proton Bridge Review Console

Status: Complete locally as of 2026-07-16
Type: AFK
Founder approval: 2026-07-16, in the current task

## What to build

Add a first reversible Proton interaction surface to the local Threadwise app. The console must use the existing Proton Mail Bridge adapter, show the complete readable message for a bounded review queue, and let the founder either confirm the existing classification or apply one canonical `EA/` label before advancing to the next message.

This is a provider-specific vertical slice, not approval for a generic provider framework or a full mail client.

## Safety boundary

- Proton writes are label-only.
- Do not archive, delete, trash, move, send, unsubscribe, or create spam/filter rules.
- A successful label action must preserve Inbox and report no destructive actions.
- Queue acknowledgments are local and reversible; they do not mutate Proton.
- Only messages still present in the live Proton Inbox may appear in the queue.

## Acceptance criteria

- [x] The daily Threadwise server exposes a discoverable Proton review console.
- [x] The console shows sender, subject, date, complete readable body, suggested label, and stored reason.
- [x] `Looks right · Next` marks only the review decision locally and advances without re-offering the same message.
- [x] `Add label · Next` applies one allowed additional label through Bridge, verifies the non-destructive contract, records the decision, and advances.
- [x] Queue count decreases immediately after either completed action.
- [x] Double submission is prevented while an action is in progress.
- [x] Deleted or no-longer-Inbox messages are excluded by intersecting the review ledger with the current live Inbox.
- [x] Automated tests cover the multi-message next flow, an added-label decision, stale-message exclusion, and the no-destructive-action guard.
- [x] A live acceptance check uses the real Bridge path without deleting, moving, or archiving any message.

## Explicitly out of scope

- Future semantic rules and matching-inbox backfill
- Proton Sieve, Spam, Trash, or block-list changes
- A Proton web-page content script
- Packaging the local app as a native desktop binary
- Background synchronization

## Triage

The founder selected the provider-neutral local review direction and explicitly asked to attempt it with rollback available. The existing Bridge read path and label-only write primitive make this independently testable. No additional product decision is required inside the safety boundary above.

## Completion evidence

- `python3 -m unittest discover -s tests`: 709 tests passed.
- Live at `http://127.0.0.1:8021/proton-review`: dashboard entry, real 12-item Bridge queue, full HTML body rendering, and label-only safety copy verified in the in-app browser.
- No live review acknowledgment or label write was performed during acceptance because the first real `EA/NeedsAction` decision was genuinely uncertain.
- Live testing found and fixed embedded CSS/script leakage plus malformed unclosed-`head` handling in HTML email bodies.
