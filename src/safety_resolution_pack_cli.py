import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.safety_resolution_pack import load_artifact, write_safety_resolution_pack


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a reviewed safety-resolution pack from suspicious runtime backlog without approved safety memory."
    )
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
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
    report = load_artifact(resolve_path(args.report_path, repo_root))
    pack = write_safety_resolution_pack(
        resolve_path(args.output_storage_dir, repo_root),
        report=report,
        provider_storage_dirs=[
            ("gmail", resolve_path(args.gmail_storage_dir, repo_root)),
            ("protonmail", resolve_path(args.protonmail_storage_dir, repo_root)),
            ("outlookmail", resolve_path(args.outlookmail_storage_dir, repo_root)),
        ],
    )
    output.write(
        f"Built safety resolution pack: candidates={pack['summary']['candidate_count']} | "
        f"phishing={pack['summary']['phishing_candidate_count']} | "
        f"not-safety={pack['summary']['not_safety_candidate_count']}\n"
    )
    if pack["candidates"]:
        top = pack["candidates"][0]
        output.write(
            f"Top candidate: {top['provider']} | {top['suggested_disposition']} | "
            f"{top['suggested_scope']} | {top['group_key']} | messages={top['message_count']}\n"
        )
    output.write(f"Saved pack: {pack['pack_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
