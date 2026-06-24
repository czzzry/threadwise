from datetime import UTC, datetime
from pathlib import Path

from src.label_taxonomy import gmail_label_name
from src.local_artifacts import daily_report_path, write_json
from src.stored_batch_review_store import StoredBatchReviewStore


def build_gmail_daily_report(
    storage_dir: Path,
    batch_id: str,
    account_id: str,
    fetched_count: int,
    applied_count: int,
    inbox_removals: int,
    unlabeled_exceptions: list[dict],
) -> dict:
    label_counts = reviewed_label_counts(storage_dir, batch_id)
    return {
        "account_id": account_id,
        "provider": "gmail",
        "batch_id": batch_id,
        "report_date": datetime.now(UTC).date().isoformat(),
        "processed_count": fetched_count,
        "auto_applied_count": applied_count,
        "inbox_removed_count": inbox_removals,
        "classified_count": applied_count,
        "unlabeled_count": len(unlabeled_exceptions),
        "label_counts": label_counts,
        "suggested_label_counts": label_counts,
        "unlabeled_exceptions": exception_summaries(unlabeled_exceptions),
    }


def build_protonmail_daily_report(
    storage_dir: Path,
    batch_id: str,
    account_id: str,
    fetched_count: int,
    classified_count: int,
    unlabeled_exceptions: list[dict],
) -> dict:
    return {
        "account_id": account_id,
        "provider": "protonmail",
        "batch_id": batch_id,
        "report_date": datetime.now(UTC).date().isoformat(),
        "processed_count": fetched_count,
        "auto_applied_count": 0,
        "inbox_removed_count": 0,
        "classified_count": classified_count,
        "label_counts": {},
        "suggested_label_counts": suggested_label_counts(storage_dir, batch_id),
        "unlabeled_count": len(unlabeled_exceptions),
        "unlabeled_exceptions": exception_summaries(unlabeled_exceptions),
    }


def write_daily_report(storage_dir: Path, batch_id: str, report: dict) -> None:
    write_json(daily_report_path(storage_dir, batch_id), report)


def reviewed_label_counts(storage_dir: Path, batch_id: str) -> dict[str, int]:
    batch_store = StoredBatchReviewStore(storage_dir)
    stored_batch = batch_store.load_batch(batch_id)
    counts: dict[str, int] = {}
    for item in stored_batch["items"]:
        if item.get("review_state") != "reviewed":
            continue
        for label in item.get("final_labels") or []:
            label_name = gmail_label_name(label)
            counts[label_name] = counts.get(label_name, 0) + 1
    return dict(sorted(counts.items()))


def suggested_label_counts(storage_dir: Path, batch_id: str) -> dict[str, int]:
    batch_store = StoredBatchReviewStore(storage_dir)
    stored_batch = batch_store.load_batch(batch_id)
    counts: dict[str, int] = {}
    for item in stored_batch["items"]:
        for label in item.get("applied_labels") or []:
            label_name = gmail_label_name(label)
            counts[label_name] = counts.get(label_name, 0) + 1
    return dict(sorted(counts.items()))


def exception_summaries(unlabeled_exceptions: list[dict]) -> list[dict]:
    return [
        {
            "sender": item["sender"],
            "subject": item["subject"],
        }
        for item in unlabeled_exceptions
    ]
