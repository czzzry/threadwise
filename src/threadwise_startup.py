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


def default_launch_agent_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def default_log_dir() -> Path:
    return Path.home() / "Library" / "Logs" / "Threadwise"


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parent.parent


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
    return {
        "label": LAUNCH_AGENT_LABEL,
        "repo_root": str(repo_root.resolve()),
        "plist_path": str(plist_path),
        "plist_exists": plist_path.exists(),
        "log_dir": str(log_dir),
        "log_dir_exists": log_dir.exists(),
        "health": health,
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
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
    result["launchctl_executed"] = True
    return result


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
        uid = subprocess.check_output(["id", "-u"], text=True).strip()
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)], check=False)
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
        output.write(f"LaunchAgent: {report['label']}\n")
        output.write(f"Plist: {'present' if report['plist_exists'] else 'missing'} at {report['plist_path']}\n")
        output.write(f"Logs: {'present' if report['log_dir_exists'] else 'missing'} at {report['log_dir']}\n")
        health = report["health"]
        output.write(f"Health: {health['label']} ({health['kind']})\n")
        output.write(f"Detail: {health['details']}\n")
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
