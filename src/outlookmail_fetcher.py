from pathlib import Path

from src.fixture_classifier import FixtureBatchClassifier
from src.outlookmail_message_normalizer import normalize_outlookmail_message
from src.stored_batch_fetcher import StoredBatchFetcher


class OutlookMailBatchFetcher(StoredBatchFetcher):
    def __init__(
        self,
        outlookmail_client: object,
        storage_dir: Path,
        classifier: FixtureBatchClassifier | None = None,
    ) -> None:
        super().__init__(
            mailbox_client=outlookmail_client,
            storage_dir=storage_dir,
            provider="outlookmail",
            normalize_message=normalize_outlookmail_message,
            classifier=classifier,
        )

    def fetch_outlookmail_batch(self, account_id: str, batch_size: int) -> dict | None:
        return self.fetch_batch(account_id, batch_size)
