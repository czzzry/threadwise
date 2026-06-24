import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.unlabeled_exception_report import collect_recurring_unlabeled_exceptions


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect recurring reviewed unlabeled exceptions across stored local batches."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--provider", default="gmail")
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
    report = collect_recurring_unlabeled_exceptions(
        storage_dir=storage_dir,
        account_id=args.account_id,
        provider=args.provider,
    )

    output.write(f"Account: {report['account_id']}\n")
    output.write(f"Provider: {report['provider']}\n")
    output.write(f"Reviewed unlabeled items: {report['reviewed_unlabeled_count']}\n")
    output.write(f"Recurring clusters: {len(report['recurring_clusters'])}\n")

    if not report["recurring_clusters"]:
        output.write("No recurring reviewed unlabeled exceptions found.\n")
        return 0

    for cluster in report["recurring_clusters"]:
        output.write(
            f"{cluster['count']} items | "
            f"sender={cluster['sender']} | "
            f"subject_pattern={cluster['subject_pattern']}\n"
        )
        output.write(f"Recent batches: {', '.join(cluster['recent_batch_ids'])}\n")
        for example in cluster["recent_examples"]:
            output.write(f"{example['batch_id']} || {example['subject']}\n")

    return 0


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
