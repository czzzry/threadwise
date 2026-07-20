import argparse
import getpass
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.live_outlookmail_client import LiveOutlookMailClient, SetupError
from src.outlookmail_fetcher import OutlookMailBatchFetcher

DEFAULT_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/outlookmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch live Outlook.com IMAP messages into the review queue.")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--imap-config-path", type=Path)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument(
        "--prompt-password",
        action="store_true",
        help="Prompt securely for the Outlook IMAP password or app password instead of relying on the config file value.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    outlookmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    imap_config_path = resolve_optional_path(args.imap_config_path, repo_root)

    storage_dir.mkdir(parents=True, exist_ok=True)
    credentials_dir.mkdir(parents=True, exist_ok=True)

    outlookmail_client_factory = outlookmail_client_factory or _default_outlookmail_client_factory

    try:
        password_override = _resolve_password_override(
            credentials_dir=credentials_dir,
            account_id=args.account_id,
            imap_config_path=imap_config_path,
            prompt_password=args.prompt_password,
        )
        outlookmail_client = outlookmail_client_factory(args.account_id, credentials_dir, imap_config_path, password_override)
        fetcher = OutlookMailBatchFetcher(outlookmail_client=outlookmail_client, storage_dir=storage_dir)
        review_queue = fetcher.fetch_outlookmail_batch(args.account_id, args.batch_size)
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2

    if review_queue is None:
        output.write("No new messages found.\n")
        return 0

    output.write(f"Fetched {len(review_queue['items'])} new messages into {review_queue['batch_id']}.\n")
    return 0


def _default_outlookmail_client_factory(
    account_id: str,
    credentials_dir: Path,
    imap_config_path: Path | None,
    password_override: str | None,
) -> object:
    return LiveOutlookMailClient.from_imap_config(
        account_id,
        credentials_dir,
        config_path=imap_config_path,
        password_override=password_override,
    )


def _resolve_password_override(
    credentials_dir: Path,
    account_id: str,
    imap_config_path: Path | None,
    prompt_password: bool,
) -> str | None:
    env_password = os.getenv("OUTLOOKMAIL_PASSWORD")
    if env_password:
        return env_password

    if prompt_password:
        return getpass.getpass("Outlook IMAP password/app password: ")

    try:
        config = _load_imap_config(credentials_dir, account_id, imap_config_path)
    except FileNotFoundError:
        return None
    if config.get("password"):
        return None

    return getpass.getpass("Outlook IMAP password/app password: ")


def _load_imap_config(credentials_dir: Path, account_id: str, imap_config_path: Path | None) -> dict:
    resolved_path = (
        imap_config_path
        if imap_config_path is not None
        else credentials_dir / "imap" / f"{account_id}.json"
    )
    return json.loads(resolved_path.read_text())


if __name__ == "__main__":
    raise SystemExit(main())
