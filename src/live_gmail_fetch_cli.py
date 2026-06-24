import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.gmail_fetcher import GmailBatchFetcher
from src.gmail_cli_support import default_gmail_client_factory
from src.live_gmail_client import SetupError

DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch live Gmail messages into the review queue.")
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
        gmail_client = gmail_client_factory(args.account_id, credentials_dir, client_secret_path)
        fetcher = GmailBatchFetcher(gmail_client=gmail_client, storage_dir=storage_dir)
        review_queue = fetcher.fetch_gmail_batch(args.account_id, args.batch_size)
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2

    if review_queue is None:
        output.write("No new messages found.\n")
        return 0

    output.write(f"Fetched {len(review_queue['items'])} new messages into {review_queue['batch_id']}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
