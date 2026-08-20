from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gmail_companion_ui import GmailCompanionApp


SOURCE_DIR = ROOT / "examples" / "gmail_companion_demo"
OUTPUT_PATH = ROOT / "docs" / "demo" / "marketing-fixture.json"


def convert_provider_strings(value, *, key: str | None = None):
    if isinstance(value, dict):
        return {
            child_key: convert_provider_strings(child, key=child_key)
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [convert_provider_strings(child) for child in value]
    if not isinstance(value, str) or key == "contract_version":
        return value
    return value.replace("Gmail", "Proton Mail").replace("gmail", "protonmail")


def provider_fixture(provider: str, *, message_id: str = "demo-001") -> dict:
    with TemporaryDirectory(prefix="threadwise-marketing-") as temporary_directory:
        fixture_dir = Path(temporary_directory) / "fixture"
        shutil.copytree(SOURCE_DIR, fixture_dir)
        app = GmailCompanionApp(
            fixture_dir,
            gmail_write_through_enabled=False,
            gmail_check_enabled=False,
            live_inbox_reconciliation_enabled=False,
        )
        fixture = app.harness_state({"provider": "gmail", "message_id": message_id})
    fixture["sidebar_state"]["generated_at"] = "2026-08-20T00:00:00Z"
    if provider == "gmail":
        return fixture

    return convert_provider_strings(deepcopy(fixture))


def main() -> None:
    payload = {
        "gmail": provider_fixture("gmail"),
        "gmail_next": provider_fixture("gmail", message_id="demo-002"),
        "protonmail": provider_fixture("protonmail"),
        "protonmail_next": provider_fixture("protonmail", message_id="demo-002"),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
