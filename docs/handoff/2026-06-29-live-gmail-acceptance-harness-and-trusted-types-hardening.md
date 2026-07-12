# Live Gmail Acceptance Harness And Trusted Types Hardening

Status: Current handoff
Current as of: 2026-06-29
Builds on: `docs/prd.md`, `docs/issues/066-gmail-release-hardening-and-acceptance.md`, `docs/handoff/2026-06-29-gmail-companion-simulator-acceptance-pass.md`

## What changed

This pass turned the live Gmail acceptance effort from manual trial-and-error into a deterministic host-driven harness.

Implemented changes:

- added a direct CDP bootstrap for the real signed-in Gmail page:
  - `scripts/bootstrap_live_gmail_companion_cdp.mjs`
- added a direct CDP live acceptance runner:
  - `scripts/live_gmail_companion_acceptance_cdp.mjs`
- hardened the Gmail companion content script against Gmail Trusted Types restrictions:
  - `extensions/gmail_companion/content.js`
- made the content script singleton-safe so repeated injection does not leave stale refresh loops behind
- added explicit content-script test hooks for queue-preview and teach-preview actions
- added CORS plus private-network headers in the local companion server to support controlled browser-host bridging paths:
  - `src/gmail_companion_ui.py`
- extended unit coverage for the new server headers:
  - `tests/test_gmail_companion_ui.py`

## Main diagnosis

The repeated live-testing confusion was not a user sign-in problem.

The actual issues were:

1. the earlier browser-control path was often reading the wrong Chrome target
2. the live Gmail page can enforce stricter Trusted Types behavior than the simulator path
3. direct Gmail-page fetches to localhost are not reliable enough as the primary live harness bridge
4. reinjecting the sidebar without teardown caused multiple active refresh loops to fight each other

## What is now proven

Using the direct CDP path, the agent can now:

- attach to the real signed-in Gmail inbox page target
- inject the companion sidebar into that live page
- show the compact daily summary on a real Gmail thread page
- move from unsynced live-email state into stored queue-preview state
- run a real `Correct / Teach` preview on a queue-preview email
- surface a real multi-email impact preview from the stored artifacts

Confirmed live example from the acceptance run:

- queue-preview selected a LinkedIn job-alert email
- teach-preview proposed relabeling it to `EA/Work`
- the preview surfaced that this would affect `445` existing stored emails and presented the apply/refine options

## Remaining caveat

The deterministic live harness currently relies on host-driven injection and host-driven message fulfillment rather than the unpacked extension loading itself perfectly inside the isolated Chrome automation profile.

That is acceptable for acceptance and debugging, but it is still different from the founder's normal installed-browser path.

## Recommended next step

Use the new live harness for one more UX-focused pass under issue `066`, then either:

- close `066` as complete if no further blocking issues are found, or
- open a narrowly scoped follow-up issue specifically for isolated-browser extension loading parity.
