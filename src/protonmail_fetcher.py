import json
from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.protonmail_message_normalizer import normalize_protonmail_message
from src.proton_feedback_memory import load_rules
from src.stored_batch_fetcher import StoredBatchFetcher
from src.teachable_rule_memory import apply_teachable_rules


class ProtonMailExportClient:
    def __init__(self, source_path: Path) -> None:
        self._messages = {
            message["id"]: message
            for message in json.loads(source_path.read_text())
        }

    def list_messages(self, max_results: int) -> list[str]:
        message_ids: list[str] = []
        for message in self._messages.values():
            if message.get("mailbox", "inbox").lower() != "inbox":
                continue
            message_ids.append(message["id"])
            if len(message_ids) == max_results:
                break
        return message_ids

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]


class ProtonMailBatchFetcher(StoredBatchFetcher):
    def __init__(
        self,
        protonmail_client: object,
        storage_dir: Path,
        classifier: FixtureBatchClassifier | None = None,
    ) -> None:
        super().__init__(
            mailbox_client=protonmail_client,
            storage_dir=storage_dir,
            provider="protonmail",
            normalize_message=normalize_protonmail_message,
            classifier=classifier,
        )

    def fetch_protonmail_batch(self, account_id: str, batch_size: int) -> dict | None:
        return self.fetch_batch(account_id, batch_size)

    def _postprocess_review_queue(self, review_queue: dict, normalized_messages: list[dict]) -> dict:
        rules = load_rules(self._storage_dir)
        if not rules:
            return review_queue
        messages_by_id = {message.get("message_id"): message for message in normalized_messages}
        review_queue["items"] = [
            apply_teachable_rules(item, messages_by_id.get(item.get("message_id"), {}), rules)
            for item in review_queue.get("items", [])
        ]
        return review_queue


class MockProtonMailBatchFetcher(ProtonMailBatchFetcher):
    pass
