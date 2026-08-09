# Threadwise Gauntlet handoff: queue-local filtering and navigation

Status: Slice complete; fresh critic WIN
Current as of: 2026-08-09
Issue: `#106`
Parent: `#104`
Branch: `codex/threadwise-gauntlet`

## Outcome

Threadwise Home now discloses a compact finder for the already-loaded active-provider review queue. Search stays local to that bounded array, preserves provider order, and matches sender, subject, displayed classification/label, and status. Entering a result reuses the existing selected-email review surface; pointer Previous/Next and panel-scoped J/K traverse that filtered set without wrapping or turning Threadwise into a separate inbox.

The provider-selected email remains primary. The finder is absent until the user explicitly enters Home/queue context. Enter and Escape remain root-scoped, native/editable controls are protected, and Gmail/outside-root events remain untouched.

## Files

- `extensions/gmail_companion/queue_navigation.js`
- `extensions/gmail_companion/manifest.json`
- `extensions/gmail_companion/content.js`
- `tests/gmail_companion_queue_navigation_test.js`
- `scripts/validate_threadwise_queue_navigation_cdp.mjs`

No provider adapter, backend route, SDK, service, dependency, or analytics schema changed. The typed query is never sent to analytics or logs.

## Gauntlet rounds

1. Fresh critic: `82/100`; not a WIN because the browser proof manually focused the queue-navigation wrapper before J/K.
2. Fresh critic after guarded async focus handoff: not a WIN because the recorded scroll positions were zero and therefore did not prove `preventScroll`.
3. Fresh critic after nonzero-scroll proof: not a WIN because explicit Home/reopen boundaries could retain stale queue UI state.
4. Fresh critic after exit-state correction: **WIN at `85/100`**, baseline `~70/100`, five of six fixed tasks won, no hard gate triggered.

The final guarded focus handoff restores focus only when the queue preview is still active and the user has not focused another element during the async rerender. `Back to queue` preserves the active filter; explicit Home/reopen exits clear the query, disclosures, preview identity, and pending focus.

## Validation

- `node tests/gmail_companion_queue_navigation_test.js`: pass
- existing onboarding and analytics Node suites: pass
- controlled CDP acceptance: pass
- compact `1280x800`, short `756x469`, and narrow `360x800`: contained with no host displacement
- real pointer entry followed by CDP J/K to `activeElement`: pass
- nonzero page scroll `180` and companion scroll `72` preserved through pointer entry, pointer Next, J, and K rerenders
- dirty queue state → explicit Home exit → minimize → selected-email reopen → one Escape: pass
- forbidden requests: `0`
- `python3 -m unittest discover -s tests`: `795` passed
- `git diff --check` and JavaScript syntax checks: pass

Screenshots and machine-readable evidence are reproducible at:

- `/tmp/threadwise-queue-navigation-compact.png`
- `/tmp/threadwise-queue-navigation-short.png`
- `/tmp/threadwise-queue-navigation-narrow.png`
- `/tmp/threadwise-queue-navigation-result.json`
- `/tmp/threadwise-queue-navigation-forbidden-requests.json`

## Safety and remaining boundary

- no live inbox, credential, OAuth, or private-email access
- no provider search, sync trigger, handled acknowledgement, teaching apply, safety apply, unsubscribe execution, mailbox write, reply, send, or AI writing
- real Gmail/Proton acceptance and provider writes remain approval-gated

## Next bounded step

Triage slice 3, the contextual action panel. It should expose only actions valid for the current selected email, queue item, teaching preview, receipt, or blocked state, and must reuse the queue keyboard vocabulary rather than introducing a global command palette.
