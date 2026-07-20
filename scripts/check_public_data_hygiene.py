#!/usr/bin/env python3
"""Fail when tracked public files contain common private-data residue."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


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
    "unsanitized live-account evidence": re.compile(
        r"\b(?:live founder(?:'s)? (?:gmail|protonmail|inbox)|"
        r"founder(?:'s)? real (?:gmail|inbox)|founder(?:'s)? signed-in|"
        r"current stored founder gmail|rejected token was retained)\b",
        re.IGNORECASE,
    ),
}

EMAIL_ADDRESS = re.compile(
    r"(?P<local>[A-Z0-9._%+-]+)@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)
PUBLIC_DEMO_ROOTS = (
    Path("docs/assets/demo-stage"),
    Path("examples/gmail_companion_demo"),
)
RESERVED_DOMAINS = {"example.com", "example.net", "example.org"}
RESERVED_SUFFIXES = (".example", ".invalid", ".test")
CHECK_EXEMPT_PATHS = {
    Path("scripts/check_public_data_hygiene.py"),
    Path("tests/test_public_data_hygiene.py"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / raw.decode() for raw in result.stdout.split(b"\0") if raw]


def is_public_demo(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return any(relative == root or root in relative.parents for root in PUBLIC_DEMO_ROOTS)


def is_reserved_domain(domain: str) -> bool:
    normalized = urlsplit(f"//{domain}").hostname or ""
    return normalized in RESERVED_DOMAINS or normalized.endswith(RESERVED_SUFFIXES)


def scan_text(path: Path, text: str) -> list[str]:
    violations: list[str] = []
    relative = path.relative_to(ROOT)
    if relative not in CHECK_EXEMPT_PATHS:
        for label, pattern in CHECKS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{label}: {relative}:{line}")

    if is_public_demo(path):
        for match in EMAIL_ADDRESS.finditer(text):
            if is_reserved_domain(match.group("domain")):
                continue
            line = text.count("\n", 0, match.start()) + 1
            violations.append(f"non-reserved demo email domain: {relative}:{line}")

    if relative.parts[:2] == ("docs", "qa") and "Data classification:" not in text:
        violations.append(f"missing QA data classification: {relative}:1")

    return violations


def main() -> int:
    violations: list[str] = []
    for path in tracked_files():
        if path.name == ".DS_Store":
            violations.append(f"tracked OS metadata: {path.relative_to(ROOT)}")
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        violations.extend(scan_text(path, text))

    if violations:
        print("Public-data hygiene check failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Public-data hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
