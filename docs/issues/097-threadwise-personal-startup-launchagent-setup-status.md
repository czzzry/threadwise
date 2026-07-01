# Threadwise Personal Startup LaunchAgent setup/status

Status: Follow-up candidate
Type: Implementation
GitHub issue: `#22`
Parent: GitHub issue `#16`; `docs/threadwise-startup-and-packaging-model-review-2026-07-01.md`
Depends on: `#24`

## What to build

Add a one-time setup/status/uninstall command for personal macOS startup.

The command should install a user-level LaunchAgent that starts the existing Threadwise Gmail companion at login, using the current repo path and fixed loopback endpoint.

## Acceptance criteria

- [ ] Provides an install command for `~/Library/LaunchAgents/com.threadwise.companion.plist`.
- [ ] Provides status and uninstall commands.
- [ ] LaunchAgent starts `scripts/run_gmail_companion.py` at login.
- [ ] Companion binds only to `127.0.0.1:8021`.
- [ ] Logs go to `~/Library/Logs/Threadwise/`.
- [ ] Setup/status detects whether the helper is reachable and whether the service on `8021` is Threadwise.
- [ ] Does not inspect credentials or live email.
- [ ] Has tests that render/validate plist content and command behavior without installing a real LaunchAgent by default.

## Safety boundaries

- Do not install or unload LaunchAgents in tests.
- Do not run live Gmail.
- Do not move local email artifacts.
- Do not silently restart crashed helpers in this slice.

## Parallelization

Can run in parallel with `#23` after `#24` defines the health/status contract.
