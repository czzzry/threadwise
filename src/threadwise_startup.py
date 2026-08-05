from __future__ import annotations

import argparse
import json
import plistlib
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


LAUNCH_AGENT_LABEL = "com.threadwise.companion"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8021
HEALTH_PATH = "/api/health"
HEALTH_SERVICE_ID = "threadwise-gmail-companion"
HEALTH_SERVICE_NAME = "Threadwise Gmail Companion"
PROTON_BRIDGE_APP_PATH = Path("/Applications/Proton Mail Bridge.app")
PROTON_BRIDGE_ACCOUNT_ID = "founder-proton"


def default_launch_agent_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def default_log_dir() -> Path:
    return Path.home() / "Library" / "Logs" / "Threadwise"


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parent.parent


def launch_agent_target(uid: str) -> str:
    return f"gui/{uid}/{LAUNCH_AGENT_LABEL}"


def current_uid() -> str:
    return subprocess.check_output(["id", "-u"], text=True).strip()


def launch_agent_is_loaded(*, uid: str | None = None) -> bool:
    uid = uid or current_uid()
    result = subprocess.run(
        ["launchctl", "print", launch_agent_target(uid)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def inspect_launch_agent(*, uid: str | None = None) -> dict:
    if platform.system() != "Darwin":
        return {"loaded": False, "disabled": False, "supported": False}
    uid = uid or current_uid()
    loaded = launch_agent_is_loaded(uid=uid)
    disabled_result = subprocess.run(
        ["launchctl", "print-disabled", f"gui/{uid}"],
        check=False,
        capture_output=True,
        text=True,
    )
    disabled = _launch_agent_disabled_from_output(disabled_result.stdout or "")
    return {
        "loaded": loaded,
        "disabled": disabled,
        "supported": True,
        "target": launch_agent_target(uid),
    }


def _launch_agent_disabled_from_output(output: str) -> bool:
    for line in output.splitlines():
        if LAUNCH_AGENT_LABEL in line:
            return line.rsplit("=>", 1)[-1].strip().rstrip(";") == "true"
    return False


def proton_bridge_config_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "data"
        / "protonmail_credentials"
        / "protonmail_bridge"
        / f"{PROTON_BRIDGE_ACCOUNT_ID}.json"
    )


def proton_bridge_is_running(*, app_path: Path = PROTON_BRIDGE_APP_PATH) -> bool:
    executable = app_path / "Contents" / "MacOS" / "Proton Mail Bridge"
    result = subprocess.run(
        ["pgrep", "-f", str(executable)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def build_proton_bridge_status(
    repo_root: Path,
    *,
    app_path: Path = PROTON_BRIDGE_APP_PATH,
) -> dict:
    config_path = proton_bridge_config_path(repo_root)
    configured = config_path.exists()
    installed = app_path.exists()
    if not configured:
        return {
            "required": False,
            "configured": False,
            "installed": installed,
            "running": proton_bridge_is_running(app_path=app_path) if installed else False,
            "state": "not-configured",
            "label": "Not configured",
            "details": "Proton Mail Bridge is only required when Proton Mail is configured in Threadwise.",
        }
    if not installed:
        return {
            "required": True,
            "configured": True,
            "installed": False,
            "running": False,
            "state": "unavailable",
            "label": "Required but unavailable",
            "details": "Install Proton Mail Bridge to use Threadwise with Proton Mail.",
        }
    running = proton_bridge_is_running(app_path=app_path)
    return {
        "required": True,
        "configured": True,
        "installed": True,
        "running": running,
        "state": "available" if running else "unavailable",
        "label": "Available" if running else "Required but unavailable",
        "details": (
            "Proton Mail Bridge is running."
            if running
            else "Open Proton Mail Bridge before using Threadwise with Proton Mail."
        ),
    }


def build_launch_agent_plist(
    repo_root: Path,
    *,
    python_executable: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    log_dir: Path | None = None,
) -> dict:
    log_dir = log_dir or default_log_dir()
    companion_script = (repo_root / "scripts" / "run_gmail_companion.py").resolve()
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": [
            python_executable or sys.executable,
            str(companion_script),
            "--host",
            host,
            "--port",
            str(port),
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(repo_root.resolve()),
        "StandardOutPath": str(log_dir / "companion.out.log"),
        "StandardErrorPath": str(log_dir / "companion.err.log"),
    }


def render_launch_agent_plist(
    repo_root: Path,
    *,
    python_executable: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    log_dir: Path | None = None,
) -> bytes:
    payload = build_launch_agent_plist(
        repo_root,
        python_executable=python_executable,
        host=host,
        port=port,
        log_dir=log_dir,
    )
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False)


def write_launch_agent_plist(
    repo_root: Path,
    plist_path: Path | None = None,
    *,
    python_executable: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    log_dir: Path | None = None,
    create_log_dir: bool = True,
) -> Path:
    plist_path = plist_path or default_launch_agent_plist_path()
    log_dir = log_dir or default_log_dir()
    if create_log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(
        render_launch_agent_plist(
            repo_root,
            python_executable=python_executable,
            host=host,
            port=port,
            log_dir=log_dir,
        )
    )
    return plist_path


def remove_launch_agent_plist(plist_path: Path | None = None) -> bool:
    plist_path = plist_path or default_launch_agent_plist_path()
    if not plist_path.exists():
        return False
    plist_path.unlink()
    return True


def probe_health(
    *,
    origin: str | None = None,
    timeout_seconds: float = 1.5,
) -> dict:
    origin = origin or f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    request = urllib.request.Request(f"{origin}{HEALTH_PATH}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body) if body else {}
            service_id = payload.get("service_id", "")
            service_name = payload.get("service_name", "")
            status = payload.get("status", "")
            if service_id and service_id != HEALTH_SERVICE_ID:
                return {
                    "reachable": True,
                    "kind": "wrong-service",
                    "label": "Wrong service on port",
                    "status_code": response.status,
                    "service_id": service_id,
                    "service_name": service_name,
                    "health_path": payload.get("health_path", HEALTH_PATH),
                    "details": f"Something else is listening at {origin}.",
                }
            if status and status != "ready":
                return {
                    "reachable": True,
                    "kind": "health-failed",
                    "label": "Health check failed",
                    "status_code": response.status,
                    "service_id": service_id or HEALTH_SERVICE_ID,
                    "service_name": service_name or HEALTH_SERVICE_NAME,
                    "health_path": payload.get("health_path", HEALTH_PATH),
                    "details": f"Threadwise reported status={status!r}.",
                }
            return {
                "reachable": True,
                "kind": "ready",
                "label": "Ready",
                "status_code": response.status,
                "service_id": service_id or HEALTH_SERVICE_ID,
                "service_name": service_name or HEALTH_SERVICE_NAME,
                "health_path": payload.get("health_path", HEALTH_PATH),
                "details": f"{service_name or HEALTH_SERVICE_NAME} is responding at {origin}.",
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        return {
            "reachable": False,
            "kind": "helper-unreachable",
            "label": "Helper unreachable",
            "health_path": HEALTH_PATH,
            "details": f"Could not reach {origin}{HEALTH_PATH}: {error}.",
        }


def build_status_report(
    repo_root: Path,
    *,
    plist_path: Path | None = None,
    origin: str | None = None,
    timeout_seconds: float = 1.5,
) -> dict:
    plist_path = plist_path or default_launch_agent_plist_path()
    log_dir = default_log_dir()
    health = probe_health(origin=origin, timeout_seconds=timeout_seconds)
    launch_agent = inspect_launch_agent()
    if launch_agent["loaded"] and health.get("kind") == "ready":
        state = "running"
        state_label = "Running"
    elif not launch_agent["loaded"] and not health.get("reachable"):
        state = "stopped"
        state_label = "Stopped"
    else:
        state = "needs-attention"
        state_label = "Needs attention"
    return {
        "label": LAUNCH_AGENT_LABEL,
        "repo_root": str(repo_root.resolve()),
        "plist_path": str(plist_path),
        "plist_exists": plist_path.exists(),
        "log_dir": str(log_dir),
        "log_dir_exists": log_dir.exists(),
        "health": health,
        "launch_agent": launch_agent,
        "state": state,
        "state_label": state_label,
        "proton_bridge": build_proton_bridge_status(repo_root),
        "service_id": HEALTH_SERVICE_ID,
        "service_name": HEALTH_SERVICE_NAME,
        "origin": origin or f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
    }


def install_launch_agent(
    repo_root: Path,
    *,
    plist_path: Path | None = None,
    python_executable: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    dry_run: bool = False,
) -> dict:
    plist_path = write_launch_agent_plist(
        repo_root,
        plist_path=plist_path,
        python_executable=python_executable,
        host=host,
        port=port,
        create_log_dir=not dry_run,
    )
    result = {
        "plist_path": str(plist_path),
        "dry_run": dry_run,
        "launchctl_executed": False,
    }
    if dry_run:
        return result
    if platform.system() != "Darwin":
        raise RuntimeError("LaunchAgent installation is only supported on macOS.")
    uid = current_uid()
    service_target = launch_agent_target(uid)
    subprocess.run(["launchctl", "enable", service_target], check=True)
    subprocess.run(
        ["launchctl", "bootout", service_target],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
    result["launchctl_executed"] = True
    return result


def start_launch_agent(
    repo_root: Path,
    *,
    plist_path: Path | None = None,
    python_executable: str | None = None,
) -> dict:
    if platform.system() != "Darwin":
        raise RuntimeError("Threadwise service control is only supported on macOS.")
    plist_path = plist_path or default_launch_agent_plist_path()
    if not plist_path.exists():
        write_launch_agent_plist(
            repo_root,
            plist_path=plist_path,
            python_executable=python_executable,
        )
    uid = current_uid()
    target = launch_agent_target(uid)
    subprocess.run(["launchctl", "enable", target], check=True)
    if launch_agent_is_loaded(uid=uid):
        subprocess.run(["launchctl", "kickstart", "-k", target], check=True)
    else:
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
            check=True,
        )
    return {
        "state": "starting",
        "plist_path": str(plist_path),
        "target": target,
    }


def stop_launch_agent(*, plist_path: Path | None = None) -> dict:
    if platform.system() != "Darwin":
        raise RuntimeError("Threadwise service control is only supported on macOS.")
    plist_path = plist_path or default_launch_agent_plist_path()
    uid = current_uid()
    target = launch_agent_target(uid)
    # Disable first so KeepAlive cannot race the subsequent unload.
    subprocess.run(["launchctl", "disable", target], check=True)
    subprocess.run(
        ["launchctl", "bootout", target],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "state": "stopped",
        "plist_path": str(plist_path),
        "target": target,
    }


def uninstall_launch_agent(
    *,
    plist_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    plist_path = plist_path or default_launch_agent_plist_path()
    result = {
        "plist_path": str(plist_path),
        "dry_run": dry_run,
        "launchctl_executed": False,
        "removed": False,
    }
    if dry_run:
        result["removed"] = plist_path.exists()
        return result
    if platform.system() == "Darwin" and plist_path.exists():
        uid = current_uid()
        subprocess.run(["launchctl", "bootout", launch_agent_target(uid)], check=False)
        result["launchctl_executed"] = True
    result["removed"] = remove_launch_agent_plist(plist_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Threadwise personal startup LaunchAgent.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--plist-path", type=Path, default=default_launch_agent_plist_path())
    parser.add_argument("--origin", default=f"http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Write and bootstrap the LaunchAgent.")
    install_parser.add_argument("--dry-run", action="store_true", help="Write the plist but skip launchctl.")
    install_parser.add_argument("--python", dest="python_executable", default=None)

    status_parser = subparsers.add_parser("status", help="Report plist and helper status.")
    status_parser.add_argument("--timeout", type=float, default=1.5)
    status_parser.add_argument("--json", action="store_true", help="Print machine-readable status.")

    subparsers.add_parser("start", help="Enable and start the Threadwise companion.")
    subparsers.add_parser("stop", help="Disable and stop the Threadwise companion.")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove the LaunchAgent.")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Skip launchctl and only remove the plist.")

    return parser


def main(argv: list[str] | None = None, stdout=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout

    if args.command == "install":
        result = install_launch_agent(
            args.repo_root,
            plist_path=args.plist_path,
            python_executable=args.python_executable,
            dry_run=args.dry_run,
        )
        output.write(f"Wrote LaunchAgent plist to {result['plist_path']}\n")
        if result["dry_run"]:
            output.write("Dry run only; launchctl was not invoked.\n")
        elif result["launchctl_executed"]:
            output.write("Bootstrapped the LaunchAgent.\n")
        return 0

    if args.command == "status":
        report = build_status_report(
            args.repo_root,
            plist_path=args.plist_path,
            origin=args.origin,
            timeout_seconds=args.timeout,
        )
        if args.json:
            output.write(json.dumps(report) + "\n")
            return 0
        output.write(f"Threadwise: {report['state_label']}\n")
        output.write(f"LaunchAgent: {report['label']}\n")
        output.write(f"Plist: {'present' if report['plist_exists'] else 'missing'} at {report['plist_path']}\n")
        output.write(f"Logs: {'present' if report['log_dir_exists'] else 'missing'} at {report['log_dir']}\n")
        health = report["health"]
        output.write(f"Health: {health['label']} ({health['kind']})\n")
        output.write(f"Detail: {health['details']}\n")
        bridge = report["proton_bridge"]
        output.write(f"Proton Mail Bridge: {bridge['label']}\n")
        output.write(f"Bridge detail: {bridge['details']}\n")
        return 0

    if args.command == "start":
        result = start_launch_agent(
            args.repo_root,
            plist_path=args.plist_path,
        )
        output.write(f"Threadwise is starting from {result['plist_path']}\n")
        return 0

    if args.command == "stop":
        result = stop_launch_agent(plist_path=args.plist_path)
        output.write(f"Threadwise is stopped. Startup settings remain at {result['plist_path']}\n")
        return 0

    if args.command == "uninstall":
        result = uninstall_launch_agent(plist_path=args.plist_path, dry_run=args.dry_run)
        if result["removed"]:
            output.write(f"Removed LaunchAgent plist at {result['plist_path']}\n")
        else:
            output.write(f"No LaunchAgent plist to remove at {result['plist_path']}\n")
        if result["dry_run"]:
            output.write("Dry run only; launchctl was not invoked.\n")
        elif result["launchctl_executed"]:
            output.write("Requested launchctl bootout.\n")
        return 0

    parser.error("Unknown command.")
    return 2
