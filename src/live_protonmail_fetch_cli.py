import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.live_protonmail_client import LiveProtonMailClient, SetupError
from src.protonmail_fetcher import ProtonMailBatchFetcher

DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/protonmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch live ProtonMail Bridge messages into the review queue.")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--bridge-config-path", type=Path)
    parser.add_argument("--batch-size", type=int, default=50)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    protonmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = _resolve_path(args.storage_dir, repo_root)
    credentials_dir = _resolve_path(args.credentials_dir, repo_root)
    bridge_config_path = _resolve_optional_path(args.bridge_config_path, repo_root)

    storage_dir.mkdir(parents=True, exist_ok=True)
    credentials_dir.mkdir(parents=True, exist_ok=True)

    protonmail_client_factory = protonmail_client_factory or _default_protonmail_client_factory

    try:
        protonmail_client = protonmail_client_factory(args.account_id, credentials_dir, bridge_config_path)
        fetcher = ProtonMailBatchFetcher(protonmail_client=protonmail_client, storage_dir=storage_dir)
        review_queue = fetcher.fetch_protonmail_batch(args.account_id, args.batch_size)
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2

    if review_queue is None:
        output.write("No new messages found.\n")
        return 0

    output.write(f"Fetched {len(review_queue['items'])} new messages into {review_queue['batch_id']}.\n")
    return 0


def _default_protonmail_client_factory(
    account_id: str,
    credentials_dir: Path,
    bridge_config_path: Path | None,
) -> object:
    return LiveProtonMailClient.from_bridge_config(
        account_id,
        credentials_dir,
        bridge_config_path=bridge_config_path,
    )


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _resolve_optional_path(path: Path | None, repo_root: Path) -> Path | None:
    if path is None:
        return None
    return _resolve_path(path, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
