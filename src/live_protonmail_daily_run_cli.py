import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from src.live_protonmail_client import LiveProtonMailClient, SetupError
from src.live_protonmail_fetch_cli import DEFAULT_CREDENTIALS_DIR, DEFAULT_STORAGE_DIR
from src.protonmail_fetcher import ProtonMailBatchFetcher
from src.stored_batch_review_store import StoredBatchReviewStore
from src.label_taxonomy import gmail_label_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch and classify ProtonMail messages for one inbox batch."
    )
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
        if review_queue is None:
            output.write("No new messages found.\n")
            return 0

        batch_store = StoredBatchReviewStore(storage_dir)
        stored_batch = batch_store.load_batch(review_queue["batch_id"])
        unlabeled_exceptions = [item for item in stored_batch["items"] if not item.get("applied_labels")]
        classified_count = len(stored_batch["items"]) - len(unlabeled_exceptions)
        _print_summary(
            review_queue["batch_id"],
            stored_batch["account_id"],
            len(review_queue["items"]),
            classified_count,
            unlabeled_exceptions,
            storage_dir,
            output,
        )
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _print_summary(
    batch_id: str,
    account_id: str,
    fetched_count: int,
    classified_count: int,
    unlabeled_exceptions: list[dict],
    storage_dir: Path,
    output: TextIO,
) -> None:
    report = {
        "account_id": account_id,
        "provider": "protonmail",
        "batch_id": batch_id,
        "report_date": datetime.now(UTC).date().isoformat(),
        "processed_count": fetched_count,
        "auto_applied_count": 0,
        "inbox_removed_count": 0,
        "classified_count": classified_count,
        "label_counts": {},
        "suggested_label_counts": _suggested_label_counts_for_report(storage_dir, batch_id),
        "unlabeled_count": len(unlabeled_exceptions),
        "unlabeled_exceptions": [
            {
                "sender": item["sender"],
                "subject": item["subject"],
            }
            for item in unlabeled_exceptions
        ],
    }
    _write_daily_report(storage_dir, batch_id, report)
    output.write(f"Batch: {batch_id}\n")
    output.write(f"Fetched: {fetched_count}\n")
    output.write("Auto-applied label writes: 0\n")
    output.write("INBOX removals: 0\n")
    output.write(f"Classified messages: {classified_count}\n")
    output.write(f"Unlabeled exceptions: {len(unlabeled_exceptions)}\n")
    for item in unlabeled_exceptions:
        output.write(f"{item['sender']} || {item['subject']}\n")


def _suggested_label_counts_for_report(storage_dir: Path, batch_id: str) -> dict[str, int]:
    batch_store = StoredBatchReviewStore(storage_dir)
    stored_batch = batch_store.load_batch(batch_id)
    counts: dict[str, int] = {}
    for item in stored_batch["items"]:
        for label in item.get("applied_labels") or []:
            label_name = gmail_label_name(label)
            counts[label_name] = counts.get(label_name, 0) + 1
    return dict(sorted(counts.items()))


def _write_daily_report(storage_dir: Path, batch_id: str, report: dict) -> None:
    reports_dir = storage_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{batch_id}_daily_report.json").write_text(json.dumps(report, indent=2))


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
