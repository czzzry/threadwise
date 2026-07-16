import json
from pathlib import Path

from src.sender_utils import normalized_sender_email


class TrustedSenderStore:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def load_or_rebuild(self) -> set[str]:
        return {entry["address"] for entry in self.load_entries_or_rebuild()}

    def load_entries_or_rebuild(self) -> list[dict]:
        store_path = self._store_path()
        if store_path.exists():
            payload = json.loads(store_path.read_text())
            entries = payload.get("trusted_personal_senders", [])
            if entries and isinstance(entries[0], str):
                return [
                    {
                        "address": address,
                        "source": "review_history",
                        "kind": "direct",
                        "notes": "Imported from legacy trust store format.",
                    }
                    for address in entries
                ]
            return entries
        return self.rebuild_from_batches()

    def rebuild_from_batches(self) -> list[dict]:
        counts: dict[str, int] = {}
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = json.loads(batch_path.read_text())
            for item in batch.get("items", []):
                if item.get("review_state") != "reviewed":
                    continue
                if "personal" not in (item.get("final_labels") or []):
                    continue

                sender_email = normalized_sender_email(item.get("sender"))
                if sender_email is None or not _looks_like_trustworthy_personal_address(sender_email, item):
                    continue
                counts[sender_email] = counts.get(sender_email, 0) + 1

        trusted_entries = [
            {
                "address": sender_email,
                "source": "review_history",
                "kind": "direct",
                "notes": f"Auto-seeded from {count} reviewed personal messages.",
            }
            for sender_email, count in sorted(counts.items())
            if count >= 2
        ]
        store_path = self._store_path()
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(
            json.dumps(
                {
                    "trusted_personal_senders": trusted_entries,
                },
                indent=2,
            )
        )
        return trusted_entries

    def _store_path(self) -> Path:
        return self._storage_dir / "trusted_personal_senders.json"


def _looks_like_trustworthy_personal_address(sender_email: str, item: dict) -> bool:
    local_part = sender_email.split("@", 1)[0]
    if any(
        token in local_part
        for token in (
            "no-reply",
            "noreply",
            "do-not-reply",
            "mailer-daemon",
            "notification",
            "notifications",
            "digest",
            "updates",
            "news",
            "auto",
        )
    ):
        return False

    if item.get("list_unsubscribe"):
        return False

    if (item.get("precedence") or "").lower() == "bulk":
        return False

    return True
