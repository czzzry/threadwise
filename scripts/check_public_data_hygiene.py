#!/usr/bin/env python3
"""Fail when tracked public files contain common private-data residue."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

CHECKS = {
    "consumer mailbox address": re.compile(
        r"[A-Z0-9._%+-]+@(?:gmail|outlook|hotmail|protonmail|yahoo|icloud|"
        r"zoho|rogers|freemail)\.[A-Z]{2,}",
        re.IGNORECASE,
    ),
    "machine-specific home path": re.compile(r"/(?:Users|home)/[^/\s]+/"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / raw.decode() for raw in result.stdout.split(b"\0") if raw]


def main() -> int:
    violations: list[str] = []
    for path in tracked_files():
        if path.name == ".DS_Store":
            violations.append(f"tracked OS metadata: {path.relative_to(ROOT)}")
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in CHECKS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{label}: {path.relative_to(ROOT)}:{line}")

    if violations:
        print("Public-data hygiene check failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Public-data hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
