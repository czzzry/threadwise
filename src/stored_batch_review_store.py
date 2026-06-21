import json
from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.gmail_message_normalizer import normalize_gmail_message
from src.local_artifacts import batch_path, load_json, write_json
from src.trusted_sender_store import TrustedSenderStore


class StoredBatchReviewStore:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def load_batch(self, batch_id: str) -> dict:
        return load_json(self._batch_path(batch_id))

    def to_review_queue(self, stored_batch: dict) -> dict:
        items = stored_batch["items"]
        if stored_batch.get("raw_messages"):
            classifier = FixtureBatchClassifier(
                fixtures_dir=self._storage_dir,
                trusted_personal_senders=TrustedSenderStore(self._storage_dir).load_or_rebuild(),
            )
            existing_items = {item["message_id"]: item for item in stored_batch["items"]}
            normalized_messages = [
                normalize_gmail_message(
                    stored_batch["account_id"],
                    raw_message,
                    existing_items.get(raw_message.get("id", "")),
                )
                for raw_message in stored_batch["raw_messages"]
            ]
            reclassified_queue = classifier.classify_messages(stored_batch["batch_id"], normalized_messages)
            items = []
            for item in reclassified_queue["items"]:
                existing_item = existing_items.get(item["message_id"])
                if existing_item and existing_item.get("review_state") == "reviewed":
                    items.append(self._merge_existing_item(item, existing_item))
                    continue
                if existing_item and "review_state" in existing_item:
                    items.append(self._merge_pending_item(item, existing_item))
                    continue
                items.append(item)

        return {
            "batch_id": stored_batch["batch_id"],
            "account_id": stored_batch["account_id"],
            "items": items,
        }

    def persist_reviewed_items(self, batch_id: str, items: list[dict]) -> None:
        batch_path = self._batch_path(batch_id)
        stored_batch = load_json(batch_path)
        stored_batch["items"] = items
        write_json(batch_path, stored_batch)
        TrustedSenderStore(self._storage_dir).rebuild_from_batches()

    def _merge_existing_item(self, refreshed_item: dict, existing_item: dict) -> dict:
        merged_item = dict(existing_item)
        for field in (
            "source",
            "account_id",
            "sender",
            "subject",
            "date",
            "snippet",
            "body",
            "interpretation",
            "confidence_band",
        ):
            merged_item[field] = refreshed_item.get(field, existing_item.get(field))
        return merged_item

    def _merge_pending_item(self, refreshed_item: dict, existing_item: dict) -> dict:
        merged_item = dict(refreshed_item)
        for field in ("review_state", "review_action", "final_labels", "actionability"):
            if field in existing_item:
                merged_item[field] = existing_item[field]
        return merged_item

    def _batch_path(self, batch_id: str) -> Path:
        return batch_path(self._storage_dir, batch_id)
