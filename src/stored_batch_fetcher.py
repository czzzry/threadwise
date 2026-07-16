import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from src.fixture_classifier import FixtureBatchClassifier
from src.trusted_sender_store import TrustedSenderStore


class StoredBatchFetcher:
    def __init__(
        self,
        mailbox_client: object,
        storage_dir: Path,
        provider: str,
        normalize_message: Callable[[str, dict], dict],
        classifier: FixtureBatchClassifier | None = None,
    ) -> None:
        self._mailbox_client = mailbox_client
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._provider = provider
        self._normalize_message_fn = normalize_message
        self._classifier = classifier

    def fetch_batch(self, account_id: str, batch_size: int, *, reprocess_matching: bool = False) -> dict | None:
        processed_keys = set() if reprocess_matching else self._load_processed_keys()
        candidate_message_ids = self._mailbox_client.list_messages(batch_size + len(processed_keys))

        selected_messages: list[dict] = []
        fetch_failures: list[dict] = []

        for message_id in candidate_message_ids:
            identity_key = self._identity_key(account_id, message_id)
            if identity_key in processed_keys:
                continue

            try:
                selected_messages.append(self._mailbox_client.get_message(message_id))
            except Exception as exc:
                fetch_failures.append(
                    {
                        "account_id": account_id,
                        "message_id": message_id,
                        "error": str(exc),
                    }
                )
                continue

            if len(selected_messages) == batch_size:
                break

        if not selected_messages:
            if fetch_failures:
                self._persist_fetch_failures(account_id, fetch_failures)
            return None

        batch_id = self._next_batch_id(account_id)
        normalized_messages = [self._normalize_message(account_id, message) for message in selected_messages]
        classifier = self._classifier or FixtureBatchClassifier(
            fixtures_dir=Path("."),
            trusted_personal_senders=TrustedSenderStore(self._storage_dir).load_or_rebuild(),
        )
        review_queue = classifier.classify_messages(batch_id, normalized_messages)
        self._persist_batch(batch_id, account_id, selected_messages, review_queue, fetch_failures)
        self._mark_processed(account_id, [message["id"] for message in selected_messages])
        return review_queue

    def mark_processed(self, batch_id: str, message_ids: list[str]) -> None:
        account_id = batch_id.rsplit("-batch-", 1)[0]
        self._mark_processed(account_id, message_ids)

    def _normalize_message(self, account_id: str, message: dict) -> dict:
        return self._normalize_message_fn(account_id, message)

    def _next_batch_id(self, account_id: str) -> str:
        batches_dir = self._storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)

        existing_numbers: list[int] = []
        prefix = f"{account_id}-batch-"
        for batch_path in batches_dir.glob(f"{account_id}-batch-*.json"):
            suffix = batch_path.stem.removeprefix(prefix)
            if suffix.isdigit():
                existing_numbers.append(int(suffix))

        next_number = max(existing_numbers, default=0) + 1
        return f"{account_id}-batch-{next_number}"

    def _processed_ids_path(self) -> Path:
        return self._storage_dir / "processed_message_ids.json"

    def _load_processed_keys(self) -> set[str]:
        processed_ids_path = self._processed_ids_path()
        if not processed_ids_path.exists():
            return set()
        return set(json.loads(processed_ids_path.read_text()))

    def _mark_processed(self, account_id: str, message_ids: list[str]) -> None:
        processed_keys = self._load_processed_keys()
        processed_keys.update(self._identity_key(account_id, message_id) for message_id in message_ids)
        self._processed_ids_path().write_text(json.dumps(sorted(processed_keys), indent=2))

    def _identity_key(self, account_id: str, message_id: str) -> str:
        return f"{account_id}:{message_id}"

    def _persist_batch(
        self,
        batch_id: str,
        account_id: str,
        raw_messages: list[dict],
        review_queue: dict,
        fetch_failures: list[dict],
    ) -> None:
        batches_dir = self._storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        batch_path = batches_dir / f"{batch_id}.json"
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": self._provider,
                    "raw_messages": raw_messages,
                    "items": review_queue["items"],
                    "fetch_failures": fetch_failures,
                },
                indent=2,
            )
        )

    def _persist_fetch_failures(self, account_id: str, fetch_failures: list[dict]) -> None:
        failures_dir = self._storage_dir / "fetch_failures"
        failures_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        failure_path = failures_dir / f"{account_id}-{timestamp}.json"
        failure_path.write_text(json.dumps(fetch_failures, indent=2))
