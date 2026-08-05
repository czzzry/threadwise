# Threadwise Menu-Bar Control

Status: Current personal Mac operating guide
Current as of: 2026-08-05

## What It Does

`Threadwise Control` lives in the Mac menu bar and controls the existing `com.threadwise.companion` LaunchAgent without requiring Terminal.

The first menu row always reports one of:

- **Running**: the LaunchAgent is loaded and Threadwise responds to its health check.
- **Stopped**: the LaunchAgent is unloaded and disabled, so KeepAlive cannot restart it.
- **Needs attention**: the process state and health response disagree or Threadwise cannot be inspected normally.

The Proton Mail Bridge row reports **Available**, **Required but unavailable**, or **Not configured**. When Bridge is required, installed, and not running, the menu offers **Open Proton Mail Bridge**. The control checks only whether the existing Threadwise Bridge configuration file is present; it does not read credentials.

The **Proton daily sync** row reports whether the incremental 6:00 a.m. run is scheduled. The run skips messages already recorded as processed before classification, so a 25-message batch limit means “up to 25 new messages,” not “reprocess the latest 25 messages.”

## Start And Stop

1. Click **Threadwise** in the Mac menu bar.
2. Click **Stop Threadwise** to disable and unload the background service and Proton daily schedule. Their plists, project files, local data, and Proton Mail Bridge are left untouched.
3. Click **Start Threadwise** to re-enable the service and daily schedule. The status changes to **Running** after the local health check succeeds.
4. Click **Open Threadwise** to open the existing local workspace while the service is running.

The separate **Quit Menu Bar Control** command closes only the menu-bar UI. It does not stop the Threadwise companion.

## Installation

The service and daily schedule installer is:

```bash
python3 scripts/manage_threadwise_startup.py install
```

The personal menu-bar installer is:

```bash
python3 scripts/install_threadwise_control.py
```

It builds `~/Applications/Threadwise Control.app` and registers `~/Library/LaunchAgents/com.threadwise.control.plist` so the menu appears at login. The UI controller is not kept alive if explicitly quit; the Threadwise companion retains its existing KeepAlive behavior until **Stop Threadwise** is chosen.

This is a personal local build. Signing, notarization, automatic updates, and moving Threadwise data into Application Support are intentionally outside this slice.
