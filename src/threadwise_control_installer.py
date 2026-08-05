from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from src.threadwise_startup import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    PROTON_BRIDGE_APP_PATH,
    current_uid,
    default_launch_agent_plist_path,
    default_log_dir,
)


CONTROL_APP_NAME = "Threadwise Control"
CONTROL_BUNDLE_ID = "com.threadwise.control"
CONTROL_LAUNCH_AGENT_LABEL = "com.threadwise.control"


def default_control_app_path() -> Path:
    return Path.home() / "Applications" / f"{CONTROL_APP_NAME}.app"


def default_control_launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{CONTROL_LAUNCH_AGENT_LABEL}.plist"


def build_control_info_plist() -> dict:
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": CONTROL_APP_NAME,
        "CFBundleIdentifier": CONTROL_BUNDLE_ID,
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": CONTROL_APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSHumanReadableCopyright": "Threadwise personal local control",
    }


def build_control_launch_agent_plist(app_path: Path, *, log_dir: Path | None = None) -> dict:
    log_dir = log_dir or default_log_dir()
    executable = app_path / "Contents" / "MacOS" / CONTROL_APP_NAME
    return {
        "Label": CONTROL_LAUNCH_AGENT_LABEL,
        "ProgramArguments": [str(executable)],
        "RunAtLoad": True,
        "KeepAlive": False,
        "ProcessType": "Interactive",
        "StandardOutPath": str(log_dir / "control.out.log"),
        "StandardErrorPath": str(log_dir / "control.err.log"),
    }


def build_control_config(
    repo_root: Path,
    *,
    python_executable: str | None = None,
) -> dict:
    return {
        "pythonExecutable": python_executable or sys.executable,
        "managerScript": str((repo_root / "scripts" / "manage_threadwise_startup.py").resolve()),
        "repoRoot": str(repo_root.resolve()),
        "companionPlist": str(default_launch_agent_plist_path()),
        "origin": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
        "protonBridgeApp": str(PROTON_BRIDGE_APP_PATH),
    }


def install_control_app(
    repo_root: Path,
    *,
    app_path: Path | None = None,
    launch_agent_path: Path | None = None,
    python_executable: str | None = None,
    dry_run: bool = False,
) -> dict:
    app_path = app_path or default_control_app_path()
    launch_agent_path = launch_agent_path or default_control_launch_agent_path()
    source_path = repo_root / "macos" / "ThreadwiseControl" / "ThreadwiseControl.swift"
    if not source_path.exists():
        raise FileNotFoundError(f"Threadwise Control source not found: {source_path}")

    result = {
        "app_path": str(app_path),
        "launch_agent_path": str(launch_agent_path),
        "dry_run": dry_run,
        "installed": False,
        "launchctl_executed": False,
    }
    if dry_run:
        return result
    if sys.platform != "darwin":
        raise RuntimeError("Threadwise Control can only be installed on macOS.")

    uid = current_uid()
    target = f"gui/{uid}/{CONTROL_LAUNCH_AGENT_LABEL}"
    executable = app_path / "Contents" / "MacOS" / CONTROL_APP_NAME

    with tempfile.TemporaryDirectory(prefix="threadwise-control-") as temp_dir:
        compiled_path = Path(temp_dir) / CONTROL_APP_NAME
        subprocess.run(
            [
                "swiftc",
                "-swift-version",
                "5",
                "-O",
                "-framework",
                "AppKit",
                str(source_path),
                "-o",
                str(compiled_path),
            ],
            check=True,
        )
        _stop_existing_control(target, executable)
        _write_control_bundle(
            repo_root,
            app_path,
            compiled_path=compiled_path,
            python_executable=python_executable,
        )

    log_dir = default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    launch_agent_path.parent.mkdir(parents=True, exist_ok=True)
    launch_agent_path.write_bytes(
        plistlib.dumps(
            build_control_launch_agent_plist(app_path, log_dir=log_dir),
            fmt=plistlib.FMT_XML,
            sort_keys=False,
        )
    )
    subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(launch_agent_path)],
        check=True,
    )
    result["installed"] = True
    result["launchctl_executed"] = True
    return result


def _stop_existing_control(target: str, executable: Path) -> None:
    subprocess.run(
        ["launchctl", "bootout", target],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    exact_process_pattern = exact_process_match(executable)
    for _ in range(20):
        running = subprocess.run(
            ["pgrep", "-f", exact_process_pattern],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if running.returncode != 0:
            return
        subprocess.run(
            ["pkill", "-TERM", "-f", exact_process_pattern],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.1)
    raise RuntimeError("Could not stop the existing Threadwise Control process safely.")


def exact_process_match(executable: Path) -> str:
    return f"^{re.escape(str(executable))}$"


def _write_control_bundle(
    repo_root: Path,
    app_path: Path,
    *,
    compiled_path: Path,
    python_executable: str | None,
) -> None:
    if app_path.exists():
        shutil.rmtree(app_path)
    executable_dir = app_path / "Contents" / "MacOS"
    resources_dir = app_path / "Contents" / "Resources"
    executable_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    target_executable = executable_dir / CONTROL_APP_NAME
    shutil.copy2(compiled_path, target_executable)
    os.chmod(target_executable, 0o755)
    (app_path / "Contents" / "Info.plist").write_bytes(
        plistlib.dumps(build_control_info_plist(), fmt=plistlib.FMT_XML, sort_keys=False)
    )
    (resources_dir / "threadwise-control.json").write_text(
        json.dumps(
            build_control_config(repo_root, python_executable=python_executable),
            indent=2,
        )
        + "\n"
    )
