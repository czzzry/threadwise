import json
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path


class FixtureReviewLoop:
    def __init__(self, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self._loaded_batches: dict[str, dict] = {}

    def load_fixture_batch(self, batch_id: str) -> dict:
        if batch_id not in self._loaded_batches:
            batch_path = self._fixtures_dir / f"{batch_id}.json"
            batch = json.loads(batch_path.read_text())
            self._loaded_batches[batch_id] = self._prepare_batch(
                batch["batch_id"],
                batch["messages"],
            )

        return self._loaded_batches[batch_id]

    def load_review_queue(self, review_queue: dict) -> dict:
        batch_id = review_queue["batch_id"]
        if batch_id not in self._loaded_batches:
            self._loaded_batches[batch_id] = self._prepare_batch(
                batch_id,
                review_queue["items"],
            )
        return self._loaded_batches[batch_id]

    def review_message(self, batch_id: str, message_id: str, action: dict) -> dict:
        batch = self.load_fixture_batch(batch_id)

        for item in batch["items"]:
            if item["message_id"] == message_id:
                if item["review_state"] == "reviewed":
                    raise ValueError(f"Message {message_id} has already been reviewed")

                if action["type"] == "approve":
                    item["review_state"] = "reviewed"
                    item["review_action"] = "approve"
                    item["final_labels"] = list(item["applied_labels"])
                elif action["type"] == "edit":
                    item["review_state"] = "reviewed"
                    item["review_action"] = "edit"
                    item["final_labels"] = list(action["final_labels"])
                elif action["type"] == "reject":
                    item["review_state"] = "reviewed"
                    item["review_action"] = "reject"
                    item["final_labels"] = []
                if action.get("actionability") is not None:
                    item["actionability"] = action["actionability"]
                return item

        raise KeyError(f"Unknown message_id: {message_id}")

    def complete_batch(self, batch_id: str) -> dict:
        batch = self.load_fixture_batch(batch_id)
        reviewed_items = [item for item in batch["items"] if item["review_state"] == "reviewed"]
        per_label_counts = Counter(
            label
            for item in reviewed_items
            for label in item["final_labels"]
        )

        return {
            "batch_id": batch_id,
            "reviewed_count": len(reviewed_items),
            "labeled_count": sum(1 for item in reviewed_items if item["final_labels"]),
            "unlabeled_count": sum(1 for item in reviewed_items if not item["final_labels"]),
            "per_label_counts": dict(per_label_counts),
            "reviewer_label_change_count": sum(
                1 for item in reviewed_items if item["final_labels"] != item["applied_labels"]
            ),
        }

    def _sort_key(self, item: dict) -> tuple[int, float]:
        labels = set(item["applied_labels"])

        if "reply-needed" in labels:
            priority = 0
        elif "account-security" in labels:
            priority = 1
        else:
            priority = 2

        timestamp = datetime.fromisoformat(item["date"].replace("Z", "+00:00")).astimezone(UTC)
        return (priority, -timestamp.timestamp())

    def _with_default_review_state(self, item: dict) -> dict:
        normalized_item = self._normalize_labels(item)
        review_item = dict(normalized_item)
        review_item["review_state"] = item.get("review_state", "pending")
        review_item["review_action"] = item.get("review_action")
        review_item["final_labels"] = (
            list(item["final_labels"])
            if item.get("final_labels") is not None
            else None
        )
        review_item["actionability"] = item.get("actionability")
        return review_item

    def _prepare_batch(self, batch_id: str, items: list[dict]) -> dict:
        prepared_items = [self._with_default_review_state(item) for item in items]
        return {
            "batch_id": batch_id,
            "items": sorted(prepared_items, key=self._sort_key),
        }

    def _normalize_labels(self, item: dict) -> dict:
        review_item = dict(item)
        applied_labels = list(review_item["applied_labels"])
        near_misses = list(review_item["near_misses"])

        if "newsletter" in applied_labels and "promotions" in applied_labels:
            applied_labels.remove("promotions")
            near_misses.append("promotions")

        if len(applied_labels) > 3:
            overflow = applied_labels[3:]
            applied_labels = applied_labels[:3]
            near_misses.extend(overflow)

        review_item["applied_labels"] = applied_labels
        review_item["near_misses"] = near_misses
        return review_item
