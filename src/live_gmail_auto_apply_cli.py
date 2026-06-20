import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.gmail_writer import MockGmailLabelWriter
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, SetupError
from src.live_gmail_review_cli import (
    StoredBatchReviewStore,
    _default_gmail_client_factory,
    _gmail_label_name,
    _resolve_optional_path,
    _resolve_path,
)


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auto-apply Gmail labels for one stored live batch."
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--client-secret-path", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    gmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_stream = stdin or sys.stdin
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = _resolve_path(args.storage_dir, repo_root)
    credentials_dir = _resolve_path(args.credentials_dir, repo_root)
    client_secret_path = _resolve_optional_path(args.client_secret_path, repo_root)

    try:
        batch_store = StoredBatchReviewStore(storage_dir)
        stored_batch = batch_store.load_batch(args.batch_id)
        pending_count = sum(1 for item in stored_batch["items"] if item.get("review_state") != "reviewed")
        write_status_map = _load_write_status_map(storage_dir, args.batch_id)
        auto_items = _auto_approve_items(stored_batch["items"], write_status_map)
        _print_dry_run(auto_items, pending_count, output)

        confirmation = input_stream.readline().strip()
        if confirmation.upper() != "AUTOAPPLY":
            output.write("No Gmail labels were auto-applied.\n")
            return 0

        batch_store.persist_reviewed_items(args.batch_id, stored_batch["items"])

        gmail_client_factory = gmail_client_factory or _default_gmail_client_factory
        gmail_client = gmail_client_factory(
            stored_batch["account_id"],
            credentials_dir,
            client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=storage_dir,
            label_name_resolver=_gmail_label_name,
        )
        write_summary = writer.write_reviewed_labels(args.batch_id, auto_items)
        inbox_summary = writer.remove_inbox_for_low_value_messages(args.batch_id, auto_items)
        output.write(f"Auto-applied Gmail label updates: {write_summary['applied_count']}\n")
        output.write(f"Failed Gmail label updates: {write_summary['failed_count']}\n")
        output.write(f"Removed from INBOX: {inbox_summary['applied_count']}\n")
        output.write(f"Failed to remove from INBOX: {inbox_summary['failed_count']}\n")
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _auto_approve_items(items: list[dict], write_status_map: dict[str, str]) -> list[dict]:
    auto_items: list[dict] = []
    for item in items:
        labels = list(item.get("applied_labels") or [])
        final_labels = list(item.get("final_labels") or [])
        if item.get("review_state") == "reviewed":
            if item.get("review_action") != "auto-approve":
                continue
            if write_status_map.get(item["message_id"]) == "applied":
                continue
            if not final_labels:
                continue
            auto_items.append(item)
            continue
        if not labels:
            continue
        item["review_state"] = "reviewed"
        item["review_action"] = "auto-approve"
        item["final_labels"] = list(labels)
        auto_items.append(item)
    return auto_items


def _load_write_status_map(storage_dir: Path, batch_id: str) -> dict[str, str]:
    path = storage_dir / f"{batch_id}_write_status.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _print_dry_run(auto_items: list[dict], pending_count: int, output: TextIO) -> None:
    label_counts = Counter(
        _gmail_label_name(label)
        for item in auto_items
        for label in item.get("final_labels") or []
    )
    output.write("Auto-apply dry run:\n")
    output.write(f"Eligible for auto-apply: {len(auto_items)}\n")
    output.write(f"Remaining pending review: {pending_count - len(auto_items)}\n")
    output.write("Labels to auto-apply:\n")
    if label_counts:
        for label_name, count in sorted(label_counts.items()):
            output.write(f"{label_name}: {count}\n")
    else:
        output.write("(none)\n")
    output.write("This writes EA labels and removes INBOX only for EA/LowValue.\n")
    output.write("Type AUTOAPPLY to apply these changes to Gmail.\n")


if __name__ == "__main__":
    raise SystemExit(main())
