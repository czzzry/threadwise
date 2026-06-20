from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.gmail_message_normalizer import normalize_gmail_message
from src.stored_batch_fetcher import StoredBatchFetcher


class MockGmailClient:
    def __init__(self, gmail_payloads: list[dict], failing_message_ids: set[str] | None = None) -> None:
        self._gmail_payloads = {payload["id"]: payload for payload in gmail_payloads}
        self._failing_message_ids = set(failing_message_ids or set())
        self.calls: list[tuple] = []

    def list_messages(self, label_ids: tuple[str, ...], max_results: int) -> list[str]:
        self.calls.append(("list_messages", label_ids, max_results))
        message_ids: list[str] = []
        for message in self._gmail_payloads.values():
            if all(label_id in message.get("labelIds", []) for label_id in label_ids):
                message_ids.append(message["id"])
            if len(message_ids) == max_results:
                break
        return message_ids

    def get_message(self, message_id: str) -> dict:
        self.calls.append(("get_message", message_id))
        if message_id in self._failing_message_ids:
            raise RuntimeError(f"Failed to fetch message {message_id}")
        return self._gmail_payloads[message_id]


class _GmailInboxClientAdapter:
    def __init__(self, gmail_client: object) -> None:
        self._gmail_client = gmail_client

    def list_messages(self, max_results: int) -> list[str]:
        return self._gmail_client.list_messages(("INBOX",), max_results)

    def get_message(self, message_id: str) -> dict:
        return self._gmail_client.get_message(message_id)


class GmailBatchFetcher(StoredBatchFetcher):
    def __init__(
        self,
        gmail_client: object,
        storage_dir: Path,
        classifier: FixtureBatchClassifier | None = None,
    ) -> None:
        super().__init__(
            mailbox_client=_GmailInboxClientAdapter(gmail_client),
            storage_dir=storage_dir,
            provider="gmail",
            normalize_message=normalize_gmail_message,
            classifier=classifier,
        )

    def fetch_gmail_batch(self, account_id: str, batch_size: int) -> dict | None:
        return self.fetch_batch(account_id, batch_size)


class MockGmailBatchFetcher(GmailBatchFetcher):
    pass
