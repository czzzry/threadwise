import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.gmail_automation import DailyGmailRunResult, run_daily_gmail_automation
from src.gmail_cli_support import default_gmail_client_factory
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
        result = run_daily_gmail_automation(
            account_id=args.account_id,
            batch_size=args.batch_size,
            storage_dir=storage_dir,
            gmail_client=gmail_client,
        )
        if result is None:
            output.write("No new messages found.\n")
            return 0
        _print_summary(result, output)
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _print_summary(result: DailyGmailRunResult, output: TextIO) -> None:
    output.write(f"Batch: {result.batch_id}\n")
    output.write(f"Fetched: {result.fetched_count}\n")
    output.write(f"Auto-applied label writes: {result.label_write_count}\n")
    output.write(f"INBOX removals: {result.inbox_removal_count}\n")
    output.write(f"Classified messages: {result.label_write_count}\n")
    output.write(f"Unlabeled exceptions: {len(result.unlabeled_exceptions)}\n")
    for item in result.unlabeled_exceptions:
        output.write(f"{item['sender']} || {item['subject']}\n")


if __name__ == "__main__":
    raise SystemExit(main())
