import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.gmail_readiness_replay import build_stored_gmail_readiness_replay


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay current Gmail readiness across stored Gmail batches."
    )
    parser.add_argument("--account-id", required=True)
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

    report = build_stored_gmail_readiness_replay(storage_dir, args.account_id)
    if not report["batches"]:
        output.write("No stored Gmail batches found for that account.\n")
        return 1

    output.write(f"Account: {report['account_id']}\n")
    output.write(f"Provider: {report['provider']}\n")
    output.write(f"Overall status: {report['overall_status']}\n")
    output.write(f"Stored batches: {report['stored_batch_count']}\n")
    output.write(f"Stored messages: {report['stored_message_count']}\n")
    output.write(f"Replay pass batches: {report['replay_pass_count']}\n")
    output.write(f"Replay warn batches: {report['replay_warn_count']}\n")
    output.write(f"Replay pause batches: {report['replay_pause_count']}\n")
    output.write(f"Reviewed unlabeled history: {report['reviewed_unlabeled_history']}\n")
    output.write(f"Frontier remaining unlabeled: {report['frontier_remaining_unlabeled']}\n")
    output.write(f"Mutation evidence verified batches: {report['mutation_evidence_verified_count']}\n")
    output.write(f"Mutation evidence missing batches: {report['mutation_evidence_missing_count']}\n")
    output.write(f"Mutation evidence violation batches: {report['mutation_evidence_violation_count']}\n")

    for batch in report["batches"]:
        output.write(
            f"{batch['status']} | "
            f"{batch['batch_id']} | "
            f"processed={batch['processed_count']} | "
            f"unlabeled={batch['unlabeled_count']} | "
            f"rate={batch['exception_rate'] * 100:.2f}% | "
            f"evidence={batch['mutation_evidence']}\n"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
