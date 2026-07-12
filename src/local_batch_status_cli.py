import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.local_batch_summary import format_counter, load_batch, summarize_batch


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect one stored local batch without making Gmail API calls."
    )
    parser.add_argument("--batch-id", required=True)
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
    storage_dir = _resolve_path(args.storage_dir, repo_root)

    batch = load_batch(storage_dir / "batches" / f"{args.batch_id}.json")
    summary = summarize_batch(storage_dir, batch)

    output.write(f"Batch ID: {batch['batch_id']}\n")
    output.write(f"Account ID: {batch['account_id']}\n")
    output.write(f"Items: {summary['item_count']}\n")
    output.write(f"Fetch failures: {summary['fetch_failure_count']}\n")
    output.write(f"Review states: {format_counter(summary['review_states'], separator=', ')}\n")
    output.write(f"Review actions: {format_counter(summary['review_actions'], separator=', ')}\n")
    output.write(f"Final labels: labeled={summary['labeled_count']}, unlabeled={summary['unlabeled_count']}\n")
    output.write(f"Label counts: {format_counter(summary['label_counts'], separator=', ')}\n")
    output.write(f"Write status: {format_counter(summary['write_status_counts'], separator=', ')}\n")
    output.write(
        "Write attempts: "
        f"messages_with_history={summary['messages_with_history']}, "
        f"total_attempts={summary['total_attempts']}, "
        f"retried_messages={summary['retried_messages']}\n"
    )
    output.write(f"Inbox removal: {format_counter(summary['inbox_removal_status_counts'], separator=', ')}\n")
    output.write(
        "Inbox removal attempts: "
        f"messages_with_history={summary['inbox_removal_messages_with_history']}, "
        f"total_attempts={summary['inbox_removal_total_attempts']}, "
        f"retried_messages={summary['inbox_removal_retried_messages']}\n"
    )
    return 0


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
