from pathlib import Path

from src.local_artifacts import batch_path, load_json, write_json
from src.trusted_sender_store import TrustedSenderStore


class StoredBatchReviewStore:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def load_batch(self, batch_id: str) -> dict:
        return load_json(self._batch_path(batch_id))

    def persist_reviewed_items(self, batch_id: str, items: list[dict]) -> None:
        batch_path = self._batch_path(batch_id)
        stored_batch = load_json(batch_path)
        stored_batch["items"] = items
        write_json(batch_path, stored_batch)
        TrustedSenderStore(self._storage_dir).rebuild_from_batches()

    def _batch_path(self, batch_id: str) -> Path:
        return batch_path(self._storage_dir, batch_id)
