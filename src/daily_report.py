from datetime import UTC, datetime
from pathlib import Path

from src.label_taxonomy import gmail_label_name
from src.local_artifacts import daily_report_path, write_json
from src.stored_batch_review_store import StoredBatchReviewStore


ATTENTION_SCHEMA_VERSION = 1
ATTENTION_LEVELS = (
    "needs_attention_now",
    "possible_attention",
    "not_attention",
    "insufficient_context",
)


def build_gmail_daily_report(
    storage_dir: Path,
    batch_id: str,
    account_id: str,
    fetched_count: int,
    applied_count: int,
    inbox_removals: int,
    unlabeled_exceptions: list[dict],
    attention: dict | None = None,
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
        "attention": attention if attention is not None else build_empty_attention_section(batch_id=batch_id),
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


def build_empty_attention_section(batch_id: str = "") -> dict:
    return build_attention_section(
        evaluated_message_count=0,
        lookback_window={
            "latest_batch_id": batch_id,
            "stored_lookback_batch_ids": [],
            "max_evaluated_messages": 0,
        },
        items=[],
    )


def build_attention_section(
    *,
    evaluated_message_count: int,
    lookback_window: dict | None = None,
    model: dict | None = None,
    usage: dict | None = None,
    items: list[dict] | None = None,
) -> dict:
    normalized_items = [attention_item_summary(item) for item in items or []]
    return {
        "schema_version": ATTENTION_SCHEMA_VERSION,
        "evaluated_message_count": evaluated_message_count,
        "lookback_window": dict(lookback_window or {}),
        "model": dict(model or {}),
        "usage": {
            "input_tokens": int((usage or {}).get("input_tokens", 0)),
            "output_tokens": int((usage or {}).get("output_tokens", 0)),
            "estimated_cost_usd": float((usage or {}).get("estimated_cost_usd", 0.0)),
        },
        "grouped_counts": attention_grouped_counts(normalized_items),
        "items": normalized_items,
    }


def attention_grouped_counts(items: list[dict]) -> dict[str, int]:
    counts = {level: 0 for level in ATTENTION_LEVELS}
    for item in items:
        level = item.get("level")
        if level in counts:
            counts[level] += 1
    return counts


def attention_item_summary(item: dict) -> dict:
    return {
        "message_id": item.get("message_id", ""),
        "thread_id": item.get("thread_id", ""),
        "level": item.get("level", "not_attention"),
        "category": item.get("category", ""),
        "reason": item.get("reason", ""),
        "evidence": item.get("evidence", ""),
        "source": item.get("source", ""),
        "handled_state": item.get("handled_state", "unknown"),
        "feedback_state": item.get("feedback_state", "unset"),
        "gmail_mutation": "none",
    }


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
