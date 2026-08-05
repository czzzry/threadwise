# Threadwise Menu-Bar Service Control Handoff

Status: Complete
Current as of: 2026-08-05

## Outcome

Threadwise's companion can now be inspected, started, and stopped from a native Mac menu-bar app. The implementation wraps the existing `com.threadwise.companion` LaunchAgent instead of replacing the runtime or moving any project data.

## Behavior

- Status distinguishes Running, Stopped, and Needs attention using both `launchctl` and the companion health endpoint.
- Stop disables the service before unloading it, preventing `KeepAlive` from immediately restarting it while preserving the plist.
- Start re-enables the service and either bootstraps or kickstarts the existing plist.
- Proton Mail Bridge availability is visible without reading the credentials file or changing Bridge state.
- The same control reports and manages the 6:00 a.m. incremental Proton daily schedule.
- The menu controller has its own non-KeepAlive login LaunchAgent and can be quit independently.
- Status polling is serialized so slow checks cannot accumulate.
- Reinstallation stops the exact old menu process before replacing the app bundle, preventing stale control processes.

## Validation

- Focused Python tests cover launch-agent ordering, state reporting, Bridge availability, controller packaging, and exact process matching.
- The Swift menu app compiles with the installed macOS toolchain.
- A live menu click-through stopped the companion, confirmed it was unloaded and disabled while its plist remained present, then started it and confirmed the service returned healthy.
- Proton Mail Bridge retained the same running process across both actions.
- The live menu correctly enabled Start only while stopped and Stop/Open only while running.
- The installed Proton schedule was loaded with `RunAtLoad=false`, zero executions, and a 6:00 calendar trigger; installation did not access the mailbox.

## Deliberate Non-Changes

No email was read or changed. Existing Threadwise projects, local data paths, credentials, Proton Mail Bridge configuration, browser integrations, and the companion's loopback origin remain unchanged. Signing, notarization, updates, and broader distribution remain future work.

## Operating Guide

See `docs/threadwise-menu-bar-control.md`.
