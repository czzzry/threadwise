import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.local_batch_summary import format_counter, load_batch, summarize_batch


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List stored local batches without making Gmail API calls."
    )
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
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
    batches_dir = storage_dir / "batches"
    batch_paths = sorted(batches_dir.glob("*.json"))

    output.write(f"Stored batches: {len(batch_paths)}\n")
    for batch_path in batch_paths:
        batch = load_batch(batch_path)
        summary = summarize_batch(storage_dir, batch)

        output.write(
            f"{summary['batch_id']} | "
            f"account={summary['account_id']} | "
            f"items={summary['item_count']} | "
            f"review={format_counter(summary['review_states'])} | "
            f"labels=labeled={summary['labeled_count']},unlabeled={summary['unlabeled_count']} | "
            f"writes={format_counter(summary['write_status_counts'])} | "
            f"inbox_removal={format_counter(summary['inbox_removal_status_counts'])} | "
            f"retries={summary['retried_messages']} | "
            f"fetch_failures={summary['fetch_failure_count']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
