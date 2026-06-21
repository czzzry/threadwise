import json
from collections import Counter
from pathlib import Path

from src.label_taxonomy import gmail_label_name
from src.local_artifacts import (
    inbox_removal_attempts_path,
    inbox_removal_status_path,
    load_json,
    load_json_or_default,
    write_attempts_path,
    write_status_path,
)


def summarize_batch(storage_dir: Path, batch: dict) -> dict:
    batch_id = batch["batch_id"]
    status_map = load_json_or_default(write_status_path(storage_dir, batch_id), {})
    attempts = load_json_or_default(write_attempts_path(storage_dir, batch_id), {})
    inbox_removal_status_map = load_json_or_default(inbox_removal_status_path(storage_dir, batch_id), {})
    inbox_removal_attempts = load_json_or_default(inbox_removal_attempts_path(storage_dir, batch_id), {})

    review_states = Counter(item.get("review_state", "pending") for item in batch["items"])
    review_actions = Counter(item.get("review_action") for item in batch["items"] if item.get("review_action"))
    reviewed_items = [item for item in batch["items"] if item.get("review_state") == "reviewed"]
    labeled_items = [item for item in reviewed_items if item.get("final_labels")]
    unlabeled_count = sum(1 for item in reviewed_items if not item.get("final_labels"))
    label_counts = Counter(
        gmail_label_name(label)
        for item in labeled_items
        for label in item.get("final_labels") or []
    )
    write_status_counts = Counter(status_map.values())
    missing_count = sum(1 for item in batch["items"] if item["message_id"] not in status_map)
    if missing_count:
        write_status_counts["missing"] += missing_count

    messages_with_history = len(attempts)
    total_attempts = sum(len(history) for history in attempts.values())
    retried_messages = sum(1 for history in attempts.values() if len(history) > 1)
    inbox_removal_status_counts = Counter(inbox_removal_status_map.values())
    inbox_removal_missing_count = sum(1 for item in batch["items"] if item["message_id"] not in inbox_removal_status_map)
    if inbox_removal_missing_count:
        inbox_removal_status_counts["missing"] += inbox_removal_missing_count
    inbox_removal_messages_with_history = len(inbox_removal_attempts)
    inbox_removal_total_attempts = sum(len(history) for history in inbox_removal_attempts.values())
    inbox_removal_retried_messages = sum(1 for history in inbox_removal_attempts.values() if len(history) > 1)

    return {
        "batch_id": batch_id,
        "account_id": batch["account_id"],
        "provider": batch.get("provider", "gmail"),
        "item_count": len(batch["items"]),
        "fetch_failure_count": len(batch.get("fetch_failures", [])),
        "review_states": review_states,
        "review_actions": review_actions,
        "labeled_count": len(labeled_items),
        "unlabeled_count": unlabeled_count,
        "label_counts": label_counts,
        "write_status_counts": write_status_counts,
        "messages_with_history": messages_with_history,
        "total_attempts": total_attempts,
        "retried_messages": retried_messages,
        "inbox_removal_status_counts": inbox_removal_status_counts,
        "inbox_removal_messages_with_history": inbox_removal_messages_with_history,
        "inbox_removal_total_attempts": inbox_removal_total_attempts,
        "inbox_removal_retried_messages": inbox_removal_retried_messages,
    }


def load_batch(path: Path) -> dict:
    return load_json(path)


def load_optional_json(path: Path, default):
    return load_json_or_default(path, default)


def format_counter(counter: Counter, separator: str = ",") -> str:
    if not counter:
        return "(none)"
    return separator.join(f"{key}={counter[key]}" for key in sorted(counter))
