import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.protonmail_fetcher import ProtonMailBatchFetcher, ProtonMailExportClient

DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch ProtonMail export messages into the review queue.")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--source-path", type=Path, required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--batch-size", type=int, default=50)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    cwd: Path | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output = stdout or sys.stdout
    repo_root = cwd or Path.cwd()
    storage_dir = resolve_path(args.storage_dir, repo_root)
    source_path = resolve_path(args.source_path, repo_root)

    storage_dir.mkdir(parents=True, exist_ok=True)

    fetcher = ProtonMailBatchFetcher(
        protonmail_client=ProtonMailExportClient(source_path),
        storage_dir=storage_dir,
    )
    review_queue = fetcher.fetch_protonmail_batch(args.account_id, args.batch_size)

    if review_queue is None:
        output.write("No new messages found.\n")
        return 0

    output.write(f"Fetched {len(review_queue['items'])} new messages into {review_queue['batch_id']}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
