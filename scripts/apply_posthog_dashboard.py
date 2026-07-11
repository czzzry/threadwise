#!/usr/bin/env python3
"""Apply the source-controlled Threadwise dashboard through posthog-cli."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFINITION_PATH = REPO_ROOT / "posthog" / "threadwise-dashboard.json"


def cli_path() -> str:
    configured = os.environ.get("POSTHOG_CLI")
    if configured:
        return configured
    discovered = shutil.which("posthog-cli")
    if discovered:
        return discovered
    user_local = Path.home() / ".local" / "bin" / "posthog-cli"
    if user_local.exists():
        return str(user_local)
    raise SystemExit("posthog-cli is not installed. Run: npx -y @posthog/wizard@latest cli add")


def call_tool(tool: str, payload: dict, *, dry_run: bool = False) -> dict:
    command = [cli_path(), "api", "call", "--json"]
    if dry_run:
        command.append("--dry-run")
    command.extend([tool, json.dumps(payload, separators=(",", ":"))])
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or f"{tool} failed")
    return json.loads(result.stdout or "{}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply the Threadwise PostHog dashboard definition.")
    parser.add_argument("--dry-run", action="store_true", help="Validate official CLI calls without mutating PostHog.")
    args = parser.parse_args(argv)
    definition = json.loads(DEFINITION_PATH.read_text())
    dashboard_definition = definition["dashboard"]

    existing = call_tool(
        "dashboards-get-all",
        {"search": dashboard_definition["name"], "limit": 20, "offset": 0},
    )
    results = existing.get("results", existing if isinstance(existing, list) else [])
    exact = next((item for item in results if item.get("name") == dashboard_definition["name"]), None)
    if exact and not args.dry_run:
        print(f"Dashboard already exists: id={exact['id']} name={exact['name']}")
        return 0

    dashboard = call_tool(
        "dashboard-create",
        {**dashboard_definition, "delete_insights": False},
        dry_run=args.dry_run,
    )
    dashboard_id = dashboard.get("id")
    if args.dry_run:
        for insight in definition["insights"]:
            call_tool("insight-create", {**insight, "dashboards": []}, dry_run=True)
        print(f"Validated dashboard and {len(definition['insights'])} insight definitions.")
        return 0
    if not dashboard_id:
        raise SystemExit("PostHog did not return a dashboard id.")

    for insight in definition["insights"]:
        created = call_tool("insight-create", {**insight, "dashboards": [dashboard_id]})
        print(f"Created insight: {created.get('short_id', created.get('id', insight['name']))}")
    print(f"Applied Threadwise Product Analytics dashboard: id={dashboard_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
