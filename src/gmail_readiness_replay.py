from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.gmail_message_normalizer import normalize_gmail_message
from src.local_artifacts import inbox_removal_status_path, load_json, write_status_path
from src.trusted_sender_store import TrustedSenderStore


UNLABELED_THRESHOLD = 5
EXCEPTION_RATE_THRESHOLD = 0.10


def build_stored_gmail_readiness_replay(storage_dir: Path, account_id: str) -> dict:
    batch_paths = _matching_batch_paths(storage_dir, account_id)
    if not batch_paths:
        return {
            "account_id": account_id,
            "provider": "gmail",
            "batches": [],
        }

    classifier = FixtureBatchClassifier(
        fixtures_dir=storage_dir,
        trusted_personal_senders=TrustedSenderStore(storage_dir).load_or_rebuild(),
    )

    replayed_batches: list[dict] = []
    reviewed_unlabeled_history = 0
    frontier_remaining_unlabeled = 0
    previous_threshold_breach = False

    for batch_path in batch_paths:
        batch = load_json(batch_path)
        reclassified_items = _reclassified_items_for_batch(batch, classifier)
        simulated_items = _simulate_auto_apply(reclassified_items)

        processed_count = len(simulated_items)
        unlabeled_count = sum(1 for item in simulated_items if item.get("review_state") != "reviewed")
        exception_rate = _exception_rate(processed_count, unlabeled_count)
        threshold_breach = (
            unlabeled_count > UNLABELED_THRESHOLD
            or exception_rate > EXCEPTION_RATE_THRESHOLD
        )
        status = "PASS"
        if threshold_breach and previous_threshold_breach:
            status = "PAUSE"
        elif threshold_breach:
            status = "WARN"
        previous_threshold_breach = threshold_breach

        reclassified_by_id = {item["message_id"]: item for item in reclassified_items}
        for item in batch.get("items", []):
            if item.get("review_state") != "reviewed":
                continue
            if item.get("final_labels"):
                continue
            reviewed_unlabeled_history += 1
            current_item = reclassified_by_id.get(item["message_id"])
            if current_item is None or not current_item.get("applied_labels"):
                frontier_remaining_unlabeled += 1

        replayed_batches.append(
            {
                "batch_id": batch["batch_id"],
                "status": status,
                "processed_count": processed_count,
                "unlabeled_count": unlabeled_count,
                "exception_rate": exception_rate,
                "mutation_evidence": _mutation_evidence_status(storage_dir, batch),
            }
        )

    replay_statuses = [batch["status"] for batch in replayed_batches]
    mutation_evidence_statuses = [batch["mutation_evidence"] for batch in replayed_batches]

    overall_status = "PASS"
    if "VIOLATION" in mutation_evidence_statuses or frontier_remaining_unlabeled > 0:
        overall_status = "PAUSE"
    elif "PAUSE" in replay_statuses:
        overall_status = "PAUSE"
    elif "WARN" in replay_statuses:
        overall_status = "WARN"

    return {
        "account_id": account_id,
        "provider": "gmail",
        "overall_status": overall_status,
        "stored_batch_count": len(replayed_batches),
        "stored_message_count": sum(batch["processed_count"] for batch in replayed_batches),
        "replay_pass_count": sum(1 for batch in replayed_batches if batch["status"] == "PASS"),
        "replay_warn_count": sum(1 for batch in replayed_batches if batch["status"] == "WARN"),
        "replay_pause_count": sum(1 for batch in replayed_batches if batch["status"] == "PAUSE"),
        "reviewed_unlabeled_history": reviewed_unlabeled_history,
        "frontier_remaining_unlabeled": frontier_remaining_unlabeled,
        "mutation_evidence_verified_count": sum(
            1 for status in mutation_evidence_statuses if status == "VERIFIED"
        ),
        "mutation_evidence_missing_count": sum(
            1 for status in mutation_evidence_statuses if status == "MISSING"
        ),
        "mutation_evidence_violation_count": sum(
            1 for status in mutation_evidence_statuses if status == "VIOLATION"
        ),
        "batches": replayed_batches,
    }


def _matching_batch_paths(storage_dir: Path, account_id: str) -> list[Path]:
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return []

    matching_paths = []
    for batch_path in batches_dir.glob("*.json"):
        batch = load_json(batch_path)
        if batch.get("provider", "gmail") != "gmail":
            continue
        if batch.get("account_id") != account_id:
            continue
        matching_paths.append(batch_path)

    return sorted(matching_paths, key=lambda path: _batch_sort_key(path.stem))


def _batch_sort_key(batch_id: str) -> tuple[str, int]:
    prefix, separator, suffix = batch_id.rpartition("-batch-")
    if separator and suffix.isdigit():
        return prefix, int(suffix)
    return batch_id, -1


def _reclassified_items_for_batch(batch: dict, classifier: FixtureBatchClassifier) -> list[dict]:
    existing_items = {
        item["message_id"]: item
        for item in batch.get("items", [])
        if item.get("message_id")
    }
    raw_messages = batch.get("raw_messages") or []
    if raw_messages:
        normalized_messages = [
            normalize_gmail_message(
                batch["account_id"],
                raw_message,
                existing_items.get(raw_message.get("id", "")),
            )
            for raw_message in raw_messages
        ]
    else:
        normalized_messages = [
            _normalized_message_from_item(batch["account_id"], item)
            for item in batch.get("items", [])
        ]
    return classifier.classify_messages(batch["batch_id"], normalized_messages)["items"]


def _normalized_message_from_item(account_id: str, item: dict) -> dict:
    return {
        "source": item.get("source", "gmail"),
        "account_id": account_id,
        "message_id": item["message_id"],
        "sender": item.get("sender", ""),
        "subject": item.get("subject", ""),
        "date": item.get("date", "1970-01-01T00:00:00Z"),
        "snippet": item.get("snippet", ""),
        "body": item.get("body", ""),
        "gmail_label_ids": list(item.get("gmail_label_ids", [])),
        "list_unsubscribe": item.get("list_unsubscribe"),
        "precedence": item.get("precedence", ""),
    }


def _simulate_auto_apply(items: list[dict]) -> list[dict]:
    simulated_items = [dict(item) for item in items]
    for item in simulated_items:
        labels = list(item.get("applied_labels") or [])
        if not labels:
            continue
        item["review_state"] = "reviewed"
        item["review_action"] = "auto-approve"
        item["final_labels"] = list(labels)
    return simulated_items


def _exception_rate(processed_count: int, unlabeled_count: int) -> float:
    if not processed_count:
        return 0.0
    return unlabeled_count / processed_count


def _mutation_evidence_status(storage_dir: Path, batch: dict) -> str:
    batch_id = batch["batch_id"]
    write_status_file = write_status_path(storage_dir, batch_id)
    inbox_status_file = inbox_removal_status_path(storage_dir, batch_id)
    if not write_status_file.exists() or not inbox_status_file.exists():
        return "MISSING"

    if _has_inbox_removal_policy_violation(
        batch,
        load_json(write_status_file),
        load_json(inbox_status_file),
    ):
        return "VIOLATION"

    return "VERIFIED"


def _has_inbox_removal_policy_violation(batch: dict, write_status: dict, inbox_status: dict) -> bool:
    items_by_id = {item["message_id"]: item for item in batch.get("items", [])}
    allowed_labels = {"spam-low-value", "promotions"}

    for message_id, status in inbox_status.items():
        if status != "applied":
            continue
        item = items_by_id.get(message_id)
        if item is None:
            return True
        final_labels = set(item.get("final_labels") or [])
        if not final_labels.intersection(allowed_labels):
            return True
        if write_status.get(message_id) != "applied":
            return True

    return False
