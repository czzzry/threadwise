import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.live_outlookmail_browser_client import LiveOutlookMailBrowserClient, SetupError
from src.outlookmail_fetcher import OutlookMailBatchFetcher

DEFAULT_STORAGE_DIR = Path("data/outlookmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Outlook.com inbox rows from a signed-in local browser debug session into the review queue."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--debug-base-url", default="http://127.0.0.1:9222")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--repeat-until-empty", action="store_true")
    parser.add_argument("--max-batches", type=int, default=None)
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
    storage_dir.mkdir(parents=True, exist_ok=True)

    outlookmail_client_factory = outlookmail_client_factory or _default_outlookmail_client_factory

    try:
        client = outlookmail_client_factory(args.debug_base_url)
        fetcher = OutlookMailBatchFetcher(outlookmail_client=client, storage_dir=storage_dir)
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2

    fetched_batches = 0
    fetched_messages = 0

    while True:
        review_queue = fetcher.fetch_outlookmail_batch(args.account_id, args.batch_size)
        if review_queue is None:
            if fetched_batches == 0:
                output.write("No new messages found.\n")
            else:
                output.write(
                    f"Completed {fetched_batches} batches totaling {fetched_messages} new messages.\n"
                )
            return 0

        fetched_batches += 1
        fetched_messages += len(review_queue["items"])
        output.write(f"Fetched {len(review_queue['items'])} new messages into {review_queue['batch_id']}.\n")

        if not args.repeat_until_empty:
            return 0
        if args.max_batches is not None and fetched_batches >= args.max_batches:
            output.write(
                f"Stopped after {fetched_batches} batches totaling {fetched_messages} new messages.\n"
            )
            return 0

    return 0


def _default_outlookmail_client_factory(debug_base_url: str) -> object:
    return LiveOutlookMailBrowserClient(debug_base_url=debug_base_url)


if __name__ == "__main__":
    raise SystemExit(main())
