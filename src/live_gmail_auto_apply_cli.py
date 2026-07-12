import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.gmail_cli_support import default_gmail_client_factory
from src.gmail_automation import execute_auto_apply_plan, prepare_auto_apply_batch
from src.label_taxonomy import gmail_label_name
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, SetupError


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auto-apply Gmail labels for one stored live batch."
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--client-secret-path", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    gmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_stream = stdin or sys.stdin
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    client_secret_path = resolve_optional_path(args.client_secret_path, repo_root)

    try:
        plan = prepare_auto_apply_batch(storage_dir, args.batch_id)
        _print_dry_run(plan.auto_items, plan.pending_count, output)

        confirmation = input_stream.readline().strip()
        if confirmation.upper() != "AUTOAPPLY":
            output.write("No Gmail labels were auto-applied.\n")
            return 0

        gmail_client_factory = gmail_client_factory or default_gmail_client_factory
        gmail_client = gmail_client_factory(
            plan.account_id,
            credentials_dir,
            client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        result = execute_auto_apply_plan(storage_dir, plan, gmail_client)
        write_summary = result.write_summary
        inbox_summary = result.inbox_summary
        output.write(f"Auto-applied Gmail label updates: {write_summary['applied_count']}\n")
        output.write(f"Failed Gmail label updates: {write_summary['failed_count']}\n")
        output.write(f"Removed from INBOX: {inbox_summary['applied_count']}\n")
        output.write(f"Failed to remove from INBOX: {inbox_summary['failed_count']}\n")
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _print_dry_run(auto_items: list[dict], pending_count: int, output: TextIO) -> None:
    label_counts = Counter(
        gmail_label_name(label)
        for item in auto_items
        for label in item.get("final_labels") or []
    )
    output.write("Auto-apply dry run:\n")
    output.write(f"Eligible for auto-apply: {len(auto_items)}\n")
    output.write(f"Remaining pending review: {pending_count - len(auto_items)}\n")
    output.write("Labels to auto-apply:\n")
    if label_counts:
        for label_name, count in sorted(label_counts.items()):
            output.write(f"{label_name}: {count}\n")
    else:
        output.write("(none)\n")
    output.write("This writes EA labels and removes INBOX only for EA/LowValue.\n")
    output.write("Type AUTOAPPLY to apply these changes to Gmail.\n")


if __name__ == "__main__":
    raise SystemExit(main())
