import argparse
import sys
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
        description="Retry failed EA label writes for one stored live Gmail batch."
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--client-secret-path", type=Path)
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
    storage_dir = _resolve_path(args.storage_dir, repo_root)
    credentials_dir = _resolve_path(args.credentials_dir, repo_root)
    client_secret_path = _resolve_optional_path(args.client_secret_path, repo_root)

    try:
        batch_store = StoredBatchReviewStore(storage_dir)
        stored_batch = batch_store.load_batch(args.batch_id)
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

        retried_items: list[dict] = []
        blocked_messages: list[str] = []
        for item in _failed_items(stored_batch["items"], writer, args.batch_id):
            try:
                writer.retry_failed_write(args.batch_id, item)
                retried_items.append(item)
            except ValueError as exc:
                blocked_messages.append(str(exc))

        output.write(f"Retryable failed writes: {len(retried_items)}\n")
        output.write(
            f"Retried successfully: {sum(1 for item in retried_items if writer.get_write_status(args.batch_id, item['message_id']) == 'applied')}\n"
        )
        output.write(
            f"Still failed after retry: {sum(1 for item in retried_items if writer.get_write_status(args.batch_id, item['message_id']) == 'failed')}\n"
        )
        output.write(f"Blocked by changed labels: {len(blocked_messages)}\n")
        for message in blocked_messages:
            output.write(f"{message}\n")
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _failed_items(items: list[dict], writer: MockGmailLabelWriter, batch_id: str) -> list[dict]:
    failed_items: list[dict] = []
    for item in items:
        if writer.get_write_status(batch_id, item["message_id"]) != "failed":
            continue
        failed_items.append(item)
    return failed_items


if __name__ == "__main__":
    raise SystemExit(main())
