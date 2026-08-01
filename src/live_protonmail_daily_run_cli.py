import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.daily_report import build_protonmail_daily_report, suggested_label_counts, write_daily_report
from src.label_taxonomy import gmail_label_name
from src.live_protonmail_client import LiveProtonMailClient, SetupError
from src.live_protonmail_fetch_cli import DEFAULT_CREDENTIALS_DIR, DEFAULT_STORAGE_DIR
from src.protonmail_fetcher import ProtonMailBatchFetcher
from src.proton_review_console import sync_proton_review_ledger
from src.stored_batch_review_store import StoredBatchReviewStore


PROTON_REVIEW_URL = "https://mail.proton.me/"


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
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    bridge_config_path = resolve_optional_path(args.bridge_config_path, repo_root)

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
        auto_applied_count, write_failure_count = _auto_apply_confident_labels(
            protonmail_client,
            stored_batch,
        )
        batch_store.persist_reviewed_items(review_queue["batch_id"], stored_batch["items"])
        sync_proton_review_ledger(storage_dir, review_queue["batch_id"])
        unlabeled_exceptions = [item for item in stored_batch["items"] if not item.get("applied_labels")]
        classified_count = len(stored_batch["items"]) - len(unlabeled_exceptions)
        _print_summary(
            review_queue["batch_id"],
            stored_batch["account_id"],
            len(review_queue["items"]),
            classified_count,
            unlabeled_exceptions,
            auto_applied_count,
            write_failure_count,
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
    auto_applied_count: int,
    write_failure_count: int,
    storage_dir: Path,
    output: TextIO,
) -> None:
    report = build_protonmail_daily_report(
        storage_dir,
        batch_id,
        account_id,
        fetched_count,
        classified_count,
        unlabeled_exceptions,
        auto_applied_count,
    )
    write_daily_report(storage_dir, batch_id, report)
    output.write(f"Batch: {batch_id}\n")
    output.write(f"Fetched: {fetched_count}\n")
    output.write(f"Provider label writes: {auto_applied_count} (Inbox preserved and verified)\n")
    output.write("INBOX removals: 0\n")
    output.write(f"Suggested labels ready for review: {classified_count}\n")
    output.write(f"Needs a label decision: {len(unlabeled_exceptions)}\n")
    output.write(f"Provider write verification failures for review: {write_failure_count}\n")
    output.write(f"Open Threadwise in Proton Mail: {PROTON_REVIEW_URL}\n")
    for item in unlabeled_exceptions:
        output.write(f"{item['sender']} || {item['subject']}\n")


def _auto_apply_confident_labels(protonmail_client: object, stored_batch: dict) -> tuple[int, int]:
    """Apply only non-edge Proton suggestions and keep every exception reviewable."""
    raw_messages_by_id = {
        str(message.get("id") or ""): message
        for message in stored_batch.get("raw_messages") or []
    }
    applied_count = 0
    failure_count = 0
    for item in stored_batch.get("items") or []:
        labels = [str(label) for label in item.get("applied_labels") or [] if str(label)]
        if item.get("confidence_band") not in {"medium", "high"} or not labels:
            item["provider_write_state"] = "not-attempted"
            continue

        message_id = str(item.get("message_id") or "")
        rfc_message_id = str(raw_messages_by_id.get(message_id, {}).get("rfc_message_id") or "").strip()
        try:
            if not message_id or not rfc_message_id:
                raise ValueError("Missing Proton message identity for label verification.")
            for internal_label in labels:
                label_name = gmail_label_name(internal_label)
                write_result = protonmail_client.apply_label(message_id, label_name)
                if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                    raise RuntimeError("Proton label write violated the label-only safety contract.")
                if not protonmail_client.message_has_label(rfc_message_id, label_name):
                    raise RuntimeError("Proton did not confirm the label after the write.")
            item["provider_write_state"] = "applied"
            applied_count += 1
        except Exception as exc:
            item["provider_write_state"] = "failed"
            item["provider_write_error"] = str(exc)
            failure_count += 1
    return applied_count, failure_count


def _suggested_label_counts_for_report(storage_dir: Path, batch_id: str) -> dict[str, int]:
    return suggested_label_counts(storage_dir, batch_id)


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


if __name__ == "__main__":
    raise SystemExit(main())
