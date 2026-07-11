import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_cli_support import default_gmail_client_factory
from src.gmail_writer import MockGmailLabelWriter
from src.gmail_automation import failed_write_items, retry_failed_writes
from src.label_taxonomy import gmail_label_name
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, SetupError
from src.local_artifacts import load_json_artifact
from src.product_analytics import AnonymousDistinctIdStore, ProductAnalytics


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retry failed EA label writes and bounded INBOX removals for one stored live Gmail batch."
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
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    client_secret_path = resolve_optional_path(args.client_secret_path, repo_root)

    try:
        stored_batch = _load_retry_batch(storage_dir, args.batch_id)
        gmail_client_factory = gmail_client_factory or default_gmail_client_factory
        gmail_client = gmail_client_factory(
            stored_batch["account_id"],
            credentials_dir,
            client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=storage_dir,
            label_name_resolver=gmail_label_name,
        )

        analytics = ProductAnalytics.from_environment()
        result = retry_failed_writes(
            args.batch_id,
            stored_batch["items"],
            writer,
            analytics=analytics,
            analytics_distinct_id=AnonymousDistinctIdStore(storage_dir).get_or_create(),
        )

        output.write(f"Retryable failed writes: {len(result.retried_items)}\n")
        output.write(f"Retried successfully: {result.retried_successfully_count}\n")
        output.write(f"Still failed after retry: {result.still_failed_count}\n")
        output.write(f"Retryable failed INBOX removals: {len(result.retried_inbox_items)}\n")
        output.write(f"INBOX removals retried successfully: {result.inbox_retried_successfully_count}\n")
        output.write(f"INBOX removals still failed after retry: {result.inbox_still_failed_count}\n")
        output.write(f"Blocked by changed labels: {len(result.blocked_messages)}\n")
        for message in result.blocked_messages:
            output.write(f"{message}\n")
        analytics.shutdown()
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _failed_items(items: list[dict], writer: MockGmailLabelWriter, batch_id: str) -> list[dict]:
    return failed_write_items(items, writer, batch_id)


def _load_retry_batch(storage_dir: Path, batch_id: str) -> dict:
    try:
        return GmailBatchReviewStore(storage_dir).load_batch(batch_id)
    except FileNotFoundError:
        return load_json_artifact("gmail_mutation_batch", storage_dir, batch_id)


if __name__ == "__main__":
    raise SystemExit(main())
