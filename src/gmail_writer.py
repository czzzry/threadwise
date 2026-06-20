import json
from pathlib import Path


class MockGmailLabelClient:
    def __init__(
        self,
        existing_labels: dict[str, str] | None = None,
        failing_message_ids: set[str] | None = None,
    ) -> None:
        self.labels = dict(existing_labels or {})
        self._failing_message_ids = set(failing_message_ids or set())
        self.calls: list[tuple] = []

    def get_or_create_label(self, label_name: str) -> str:
        self.calls.append(("get_or_create_label", label_name))
        if label_name not in self.labels:
            self.labels[label_name] = f"Label_{len(self.labels) + 1}"
        return self.labels[label_name]

    def apply_labels(self, message_id: str, label_ids: list[str]) -> None:
        self.calls.append(("apply_labels", message_id, label_ids))
        if message_id in self._failing_message_ids:
            raise RuntimeError(f"Failed to apply labels to {message_id}")

    def remove_inbox_label(self, message_id: str) -> None:
        self.calls.append(("remove_inbox_label", message_id))
        if message_id in self._failing_message_ids:
            raise RuntimeError(f"Failed to remove INBOX from {message_id}")

    def clear_failure(self, message_id: str) -> None:
        self._failing_message_ids.discard(message_id)


class MockGmailLabelWriter:
    def __init__(
        self,
        gmail_client: MockGmailLabelClient,
        storage_dir: Path,
        namespace: str = "EA",
        label_name_resolver=None,
    ) -> None:
        self._gmail_client = gmail_client
        self._storage_dir = storage_dir
        self._namespace = namespace
        self._label_name_resolver = label_name_resolver or (lambda label: f"{self._namespace}/{label}")
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def map_reviewed_labels(self, final_labels: list[str], namespace: str | None = None) -> list[str]:
        if namespace is not None and namespace != self._namespace:
            return [f"{namespace}/{label}" for label in final_labels]
        return [self._label_name_resolver(label) for label in final_labels]

    def write_reviewed_labels(self, batch_id: str, reviewed_items: list[dict]) -> dict:
        status_map = self._load_status_map(batch_id)
        attempts = self._load_attempts(batch_id)
        applied_count = 0
        failed_count = 0
        skipped_count = 0
        for item in reviewed_items:
            if item.get("review_state") != "reviewed":
                skipped_count += 1
                continue

            final_labels = item.get("final_labels") or []
            if not final_labels:
                skipped_count += 1
                continue

            label_ids = []
            for label_name in self.map_reviewed_labels(final_labels):
                label_ids.append(self._gmail_client.get_or_create_label(label_name))
            try:
                self._gmail_client.apply_labels(item["message_id"], label_ids)
                status_map[item["message_id"]] = "applied"
                attempts.setdefault(item["message_id"], []).append(
                    {"status": "applied", "final_labels": list(final_labels)}
                )
                applied_count += 1
            except RuntimeError:
                status_map[item["message_id"]] = "failed"
                attempts.setdefault(item["message_id"], []).append(
                    {"status": "failed", "final_labels": list(final_labels)}
                )
                failed_count += 1
        self._write_status_map(batch_id, status_map)
        self._write_attempts(batch_id, attempts)
        return {
            "batch_id": batch_id,
            "applied_count": applied_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
        }

    def get_write_status(self, batch_id: str, message_id: str) -> str | None:
        return self._load_status_map(batch_id).get(message_id)

    def retry_failed_write(self, batch_id: str, reviewed_item: dict) -> dict:
        attempts = self._load_attempts(batch_id)
        message_id = reviewed_item["message_id"]
        history = attempts.get(message_id, [])
        if not history or history[-1]["status"] != "failed":
            raise ValueError(f"Message {message_id} is not currently retryable")

        previous_labels = history[-1]["final_labels"]
        current_labels = list(reviewed_item.get("final_labels") or [])
        if current_labels != previous_labels:
            raise ValueError(f"Message {message_id} requires re-review before retry")

        result = self.write_reviewed_labels(batch_id, [reviewed_item])
        return {"batch_id": batch_id, "retried_count": result["applied_count"] + result["failed_count"]}

    def get_write_attempt_history(self, batch_id: str, message_id: str) -> list[dict]:
        return self._load_attempts(batch_id).get(message_id, [])

    def remove_inbox_for_low_value_messages(self, batch_id: str, reviewed_items: list[dict]) -> dict:
        status_map = self._load_inbox_removal_status_map(batch_id)
        attempts = self._load_inbox_removal_attempts(batch_id)
        applied_count = 0
        failed_count = 0
        skipped_count = 0
        ineligible_count = 0

        for item in reviewed_items:
            message_id = item["message_id"]
            final_labels = list(item.get("final_labels") or [])
            if item.get("review_state") != "reviewed" or not self._is_inbox_removal_label_eligible(final_labels):
                status_map[message_id] = "ineligible"
                attempts.setdefault(message_id, []).append({"status": "ineligible", "final_labels": final_labels})
                ineligible_count += 1
                continue

            if self.get_write_status(batch_id, message_id) != "applied":
                status_map[message_id] = "skipped"
                attempts.setdefault(message_id, []).append({"status": "skipped", "final_labels": final_labels})
                skipped_count += 1
                continue

            try:
                self._gmail_client.remove_inbox_label(message_id)
                status_map[message_id] = "applied"
                attempts.setdefault(message_id, []).append({"status": "applied", "final_labels": final_labels})
                applied_count += 1
            except RuntimeError:
                status_map[message_id] = "failed"
                attempts.setdefault(message_id, []).append({"status": "failed", "final_labels": final_labels})
                failed_count += 1

        self._write_inbox_removal_status_map(batch_id, status_map)
        self._write_inbox_removal_attempts(batch_id, attempts)
        return {
            "batch_id": batch_id,
            "applied_count": applied_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "ineligible_count": ineligible_count,
        }

    def get_inbox_removal_status(self, batch_id: str, message_id: str) -> str | None:
        return self._load_inbox_removal_status_map(batch_id).get(message_id)

    def get_inbox_removal_attempt_history(self, batch_id: str, message_id: str) -> list[dict]:
        return self._load_inbox_removal_attempts(batch_id).get(message_id, [])

    def _status_path(self, batch_id: str) -> Path:
        return self._storage_dir / f"{batch_id}_write_status.json"

    def _load_status_map(self, batch_id: str) -> dict[str, str]:
        path = self._status_path(batch_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _write_status_map(self, batch_id: str, status_map: dict[str, str]) -> None:
        self._status_path(batch_id).write_text(json.dumps(status_map, indent=2))

    def _attempts_path(self, batch_id: str) -> Path:
        return self._storage_dir / f"{batch_id}_write_attempts.json"

    def _load_attempts(self, batch_id: str) -> dict[str, list[dict]]:
        path = self._attempts_path(batch_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _write_attempts(self, batch_id: str, attempts: dict[str, list[dict]]) -> None:
        self._attempts_path(batch_id).write_text(json.dumps(attempts, indent=2))

    def _inbox_removal_status_path(self, batch_id: str) -> Path:
        return self._storage_dir / f"{batch_id}_inbox_removal_status.json"

    def _load_inbox_removal_status_map(self, batch_id: str) -> dict[str, str]:
        path = self._inbox_removal_status_path(batch_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _write_inbox_removal_status_map(self, batch_id: str, status_map: dict[str, str]) -> None:
        self._inbox_removal_status_path(batch_id).write_text(json.dumps(status_map, indent=2))

    def _inbox_removal_attempts_path(self, batch_id: str) -> Path:
        return self._storage_dir / f"{batch_id}_inbox_removal_attempts.json"

    def _load_inbox_removal_attempts(self, batch_id: str) -> dict[str, list[dict]]:
        path = self._inbox_removal_attempts_path(batch_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _write_inbox_removal_attempts(self, batch_id: str, attempts: dict[str, list[dict]]) -> None:
        self._inbox_removal_attempts_path(batch_id).write_text(json.dumps(attempts, indent=2))

    def _is_inbox_removal_label_eligible(self, final_labels: list[str]) -> bool:
        return "promotions" in final_labels or "spam-low-value" in final_labels
