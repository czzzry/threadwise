import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_cli_support import default_gmail_client_factory
from src.gmail_writer import MockGmailLabelWriter
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, SetupError


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove INBOX for one stored live Gmail batch after approved EA label write-back."
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
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    client_secret_path = resolve_optional_path(args.client_secret_path, repo_root)

    try:
        batch_store = GmailBatchReviewStore(storage_dir)
        stored_batch = batch_store.load_batch(args.batch_id)
        gmail_client_factory = gmail_client_factory or default_gmail_client_factory
        gmail_client = gmail_client_factory(
            stored_batch["account_id"],
            credentials_dir,
            client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        writer = MockGmailLabelWriter(gmail_client=gmail_client, storage_dir=storage_dir)

        eligible_count, skipped_count, ineligible_count = _summarize_candidates(args.batch_id, stored_batch["items"], writer)
        output.write("INBOX removal dry run:\n")
        output.write(f"Eligible for INBOX removal: {eligible_count}\n")
        output.write(f"Skipped until label write-back is applied: {skipped_count}\n")
        output.write(f"Ineligible: {ineligible_count}\n")
        output.write("This removes INBOX only. It does not delete or trash messages.\n")
        output.write("Type REMOVE to remove INBOX from eligible messages.\n")

        confirmation = input_stream.readline().strip()
        if confirmation.upper() != "REMOVE":
            output.write("No inbox labels were removed.\n")
            return 0

        summary = writer.remove_inbox_for_low_value_messages(args.batch_id, stored_batch["items"])
        output.write(f"Removed from INBOX: {summary['applied_count']}\n")
        output.write(f"Failed to remove from INBOX: {summary['failed_count']}\n")
        output.write(f"Skipped until label write-back is applied: {summary['skipped_count']}\n")
        output.write(f"Ineligible: {summary['ineligible_count']}\n")
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _summarize_candidates(batch_id: str, items: list[dict], writer: MockGmailLabelWriter) -> tuple[int, int, int]:
    eligible_count = 0
    skipped_count = 0
    ineligible_count = 0
    for item in items:
        final_labels = list(item.get("final_labels") or [])
        if item.get("review_state") != "reviewed" or not _is_inbox_removal_label_eligible(final_labels):
            ineligible_count += 1
            continue
        if writer.get_write_status(batch_id, item["message_id"]) != "applied":
            skipped_count += 1
            continue
        eligible_count += 1
    return eligible_count, skipped_count, ineligible_count


def _is_inbox_removal_label_eligible(final_labels: list[str]) -> bool:
    return "promotions" in final_labels or "spam-low-value" in final_labels


if __name__ == "__main__":
    raise SystemExit(main())
