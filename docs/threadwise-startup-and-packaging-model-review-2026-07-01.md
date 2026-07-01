# Threadwise Startup and Packaging Model Review

Status: Current HITL review output
Current as of: 2026-07-01
GitHub issue: `#16`
Parent: `docs/prd.md`
Scope: Product and architecture review only. This review did not install startup services, alter browser settings, inspect credentials, or run live Gmail.

## Recommendation

Threadwise should stay browser-first and local-first for the next startup milestone.

The next implementation should be **Threadwise Personal Startup**:

- one-time setup command installs a macOS user LaunchAgent
- LaunchAgent starts the existing local companion at login
- companion binds only to `127.0.0.1:8021`
- Brave Gmail extension keeps using the local companion
- Gmail shows Threadwise minimized by default
- disconnected state appears as an ultra-minimal badge, not a large persistent panel
- status and uninstall commands exist for recovery

The milestone should not build a full installer, menubar app, dynamic port discovery, cloud service, standalone email client, or ProtonMail browser companion yet.

## Target User Experience

The founder's target daily workflow is:

1. Open Brave.
2. Go to Gmail.
3. Threadwise is already present, minimized, and connected.
4. No Python command, server command, settings ritual, or agent assistance is required.

If Threadwise is disconnected:

1. Gmail still shows a very small Threadwise presence.
2. It does not cover a meaningful part of the inbox.
3. Expanding it shows the failure reason and remediation steps.
4. Restart remains user-approved rather than silently performed.

## Current Model

Current implementation shape:

- `extensions/gmail_companion/` is a thin Brave/Chrome extension.
- The extension is hard-coded to talk to `http://127.0.0.1:8021`.
- `scripts/run_gmail_companion.py` starts the Python local companion.
- `src/gmail_companion_ui.py` owns the local HTTP UI, dashboard, sidebar API, Gmail check endpoint, teaching endpoints, unsubscribe handoff, and status.
- The dashboard can trigger a confirmed Gmail check using existing safe mutation boundaries.
- Local artifacts remain in the existing repo-local data paths.

The current friction is not that product logic is in the wrong place. The friction is that the user has to remember and manage the local companion process.

## Options Compared

### Improved Local Companion

This means keeping the existing extension plus Python companion, but adding startup, health, status, and recovery tooling.

Recommendation: choose this now.

Why:

- directly solves the founder's daily-use friction
- preserves local-first privacy
- avoids cloud/auth/distribution decisions
- keeps the browser inbox as the primary product surface
- can later graduate into a packaged helper or menubar app

### Packaged Desktop Helper or Menubar App

This means creating a Mac app that manages startup, status, restart, logs, and possibly native messaging.

Recommendation: keep as a later slice.

Why not now:

- valuable polish, but more packaging work
- introduces app signing, updates, UI, process management, and data-location decisions
- does not need to precede proving the simpler startup loop

### Native Messaging Host

This means registering a browser-native local host so the extension can communicate with a local process more formally than local HTTP.

Recommendation: later, if prompted restart or dynamic discovery becomes necessary.

Why not now:

- useful for a more robust extension/helper relationship
- not needed to prove "open Gmail and Threadwise is there"
- adds browser-specific host registration and packaging surface

### Cloud Service Plus Extension

This means moving the companion service off the local machine.

Recommendation: do not choose now.

Why:

- changes the privacy, auth, hosting, data-retention, and Gmail integration model
- unnecessary for a one-person local daily workflow
- conflicts with the current local-first trust model before the product loop is stable

### Gmail-Native Alternative

This means trying to move Threadwise into Gmail-native extension points or a different Gmail integration model.

Recommendation: do not choose now.

Why:

- likely too constrained for the current sidebar, teaching, dashboard, and local audit model
- would not naturally generalize to ProtonMail

### Standalone Email Client

This means reading email inside Threadwise instead of using Gmail/ProtonMail in the browser.

Recommendation: do not choose now.

Why:

- the founder's actual behavior is browser email
- Threadwise should live beside the real inbox, not replace it

## Technical Defaults

Use these defaults for the implementation issues:

- fixed loopback endpoint: `127.0.0.1:8021`
- macOS user LaunchAgent: `~/Library/LaunchAgents/com.threadwise.companion.plist`
- process logs: `~/Library/Logs/Threadwise/`
- app support location reserved for later: `~/Library/Application Support/Threadwise/`
- existing email artifacts remain where they are for now
- no silent crash restart in the first slice
- disconnected state stays ultra-minimal until expanded
- urgent/attention state uses badge or indicator only, not auto-expand
- setup command owns local helper install/status/uninstall
- Brave extension install remains guided/manual, with validation where practical

## Delivery-Model-Independent Product Logic

These areas should remain independent from startup/packaging:

- Gmail classification and bounded mutation policy
- attention detection and attention feedback
- teachable rules and broader-impact preview
- daily/weekly reports
- local audit artifacts
- unsubscribe inventory and explicit execution audit
- future provider adapters

Startup packaging should make these capabilities easier to reach, not entangle them with macOS-specific code.

## ProtonMail Future

The browser-first local-helper architecture still fits ProtonMail:

- same local helper can host shared product logic
- Gmail and ProtonMail can have provider-specific browser companions later
- provider adapters can remain separate
- no standalone email client is required

This review does not approve ProtonMail browser companion implementation. It only preserves that direction.

## AI OS Future

Future AI OS tools should be treated as a secondary control plane.

The long-term shape can be:

- browser inbox companion remains the daily surface
- local Threadwise helper exposes carefully scoped local capabilities
- an AI OS can call Threadwise later for tasks like "what needs attention?" or "summarize today's inbox"

This review does not approve AI OS integration implementation. It only captures the architectural reminder not to hide all product behavior inside the Brave extension.

## Follow-Up Issues

Create these as bounded slices:

- `#22` / `097`: Threadwise Personal Startup LaunchAgent setup/status
- `#23` / `098`: Ultra-minimal connected/disconnected Gmail extension state
- `#24` / `099`: Local companion health/status endpoint
- `#25` / `100`: Future full installer and menubar app packaging review
- `#26` / `101`: Future AI OS local-control API review

Suggested sequencing:

- `#24` / `099` should land before or alongside `#22` / `097` and `#23` / `098`.
- `#22` / `097` and `#23` / `098` can run in parallel after the health contract is clear.
- `#25` / `100` waits until the personal startup loop has been used.
- `#26` / `101` waits until the local API shape is stable enough to expose deliberately.

## HITL Decision Log

Decisions made during review:

- Optimize #16 for personal daily use, not external installability.
- Keep Threadwise browser-first, not a standalone email client.
- Keep local helper architecture; do not move to cloud.
- Preserve future ProtonMail browser companion possibility.
- Treat AI OS integration as a future secondary control plane.
- Build auto-start background service before menubar app.
- Use ultra-minimal disconnected state with expandable diagnostics.
- Use badge/indicator for attention now; defer auto-expand.
- Use one-time setup command now; defer full installer.
- Use macOS user-level logs and LaunchAgent locations.
- Keep existing email artifacts where they are for now.
