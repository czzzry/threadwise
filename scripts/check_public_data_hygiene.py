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

SECRET_CHECKS = {
    "OpenAI API key": re.compile(
        r"(?<![A-Za-z0-9_-])sk-(?:(?:proj|svcacct|admin)-[A-Za-z0-9_-]{20,}|"
        r"[A-Za-z0-9]{20,})(?![A-Za-z0-9_-])"
    ),
    "Google API key": re.compile(
        r"(?<![A-Za-z0-9_-])AIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"
    ),
    "Google OAuth client ID": re.compile(
        r"(?<![A-Za-z0-9_-])\d{12,}-[A-Za-z0-9_-]{20,}"
        r"\.apps\.googleusercontent\.com\b"
    ),
    "Google OAuth client secret": re.compile(
        r"(?<![A-Za-z0-9_-])GOCSPX-[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
    ),
    "Google OAuth access token": re.compile(
        r"(?<![A-Za-z0-9_-])ya29\.[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
    ),
    "Google OAuth refresh token": re.compile(
        r"(?<![A-Za-z0-9_/])1//[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_-])"
    ),
}

PLACEHOLDER_MARKER = re.compile(
    r"(?:\.{3}|x{8,}|abcdefghijklmnopqrstuvwxyz|0123456789|"
    r"(?:^|[-_.])(?:your|placeholder|redacted|dummy|replace[-_ ]?me)(?:$|[-_.]))",
    re.IGNORECASE,
)

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
MACHINE_HOME_CHECK_EXEMPT_PATHS = {
    Path("tests/test_threadwise_control_installer.py"),
    Path("tests/test_threadwise_startup.py"),
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


def is_documentation_placeholder(candidate: str) -> bool:
    return bool(PLACEHOLDER_MARKER.search(candidate))


def scan_text(path: Path, text: str) -> list[str]:
    violations: list[str] = []
    relative = path.relative_to(ROOT)
    if relative not in CHECK_EXEMPT_PATHS:
        for label, pattern in CHECKS.items():
            for match in pattern.finditer(text):
                if (
                    label == "machine-specific home path"
                    and relative in MACHINE_HOME_CHECK_EXEMPT_PATHS
                ):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{label}: {relative}:{line}")
        for label, pattern in SECRET_CHECKS.items():
            for match in pattern.finditer(text):
                if is_documentation_placeholder(match.group(0)):
                    continue
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
        if path.name != ".env.example" and path.suffix.lower() not in TEXT_EXTENSIONS:
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
