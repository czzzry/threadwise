import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.daily_report import build_gmail_daily_report, reviewed_label_counts, write_daily_report
from src.gmail_fetcher import GmailBatchFetcher
from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_cli_support import default_gmail_client_factory
from src.gmail_writer import MockGmailLabelWriter
from src.label_taxonomy import gmail_label_name
from src.live_gmail_auto_apply_cli import _auto_approve_items, _load_write_status_map
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, SetupError


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch and auto-apply Gmail labels for one inbox batch."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--client-secret-path", type=Path)
    parser.add_argument("--batch-size", type=int, default=50)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    gmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    client_secret_path = resolve_optional_path(args.client_secret_path, repo_root)

    storage_dir.mkdir(parents=True, exist_ok=True)
    credentials_dir.mkdir(parents=True, exist_ok=True)

    gmail_client_factory = gmail_client_factory or default_gmail_client_factory

    try:
        gmail_client = gmail_client_factory(
            args.account_id,
            credentials_dir,
            client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        fetcher = GmailBatchFetcher(gmail_client=gmail_client, storage_dir=storage_dir)
        review_queue = fetcher.fetch_gmail_batch(args.account_id, args.batch_size)
        if review_queue is None:
            output.write("No new messages found.\n")
            return 0

        batch_store = GmailBatchReviewStore(storage_dir)
        stored_batch = batch_store.load_batch(review_queue["batch_id"])
        write_status_map = _load_write_status_map(storage_dir, review_queue["batch_id"])
        auto_items = _auto_approve_items(stored_batch["items"], write_status_map)
        batch_store.persist_reviewed_items(review_queue["batch_id"], stored_batch["items"])

        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=storage_dir,
            label_name_resolver=gmail_label_name,
        )
        write_summary = writer.write_reviewed_labels(review_queue["batch_id"], auto_items)
        inbox_summary = writer.remove_inbox_for_low_value_messages(review_queue["batch_id"], auto_items)
        unlabeled_exceptions = [
            item for item in stored_batch["items"] if item.get("review_state") != "reviewed"
        ]
        _print_summary(
            review_queue["batch_id"],
            stored_batch["account_id"],
            len(review_queue["items"]),
            write_summary["applied_count"],
            inbox_summary["applied_count"],
            unlabeled_exceptions,
            storage_dir,
            output,
        )
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _print_summary(
    batch_id: str,
    account_id: str,
    fetched_count: int,
    applied_count: int,
    inbox_removals: int,
    unlabeled_exceptions: list[dict],
    storage_dir: Path,
    output: TextIO,
) -> None:
    report = build_gmail_daily_report(
        storage_dir,
        batch_id,
        account_id,
        fetched_count,
        applied_count,
        inbox_removals,
        unlabeled_exceptions,
    )
    write_daily_report(storage_dir, batch_id, report)
    output.write(f"Batch: {batch_id}\n")
    output.write(f"Fetched: {fetched_count}\n")
    output.write(f"Auto-applied label writes: {applied_count}\n")
    output.write(f"INBOX removals: {inbox_removals}\n")
    output.write(f"Classified messages: {applied_count}\n")
    output.write(f"Unlabeled exceptions: {len(unlabeled_exceptions)}\n")
    for item in unlabeled_exceptions:
        output.write(f"{item['sender']} || {item['subject']}\n")


def _label_counts_for_report(storage_dir: Path, batch_id: str) -> dict[str, int]:
    return reviewed_label_counts(storage_dir, batch_id)


if __name__ == "__main__":
    raise SystemExit(main())
