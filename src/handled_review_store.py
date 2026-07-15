from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json


class HandledReviewStore:
    def __init__(self, storage_dir: Path) -> None:
        self._path = storage_dir / "handled_review_decisions.json"

    def acknowledge(
        self,
        *,
        provider: str,
        account_id: str,
        message_id: str,
        batch_id: str = "",
    ) -> dict:
        provider = str(provider or "").strip().lower()
        account_id = str(account_id or "").strip()
        message_id = str(message_id or "").strip()
        if not provider or not message_id:
            raise ValueError("Handled review requires provider and message_id.")
        payload = load_json_or_default(self._path, {"decisions": []})
        decisions = list(payload.get("decisions") or [])
        key = self._key(provider, account_id, message_id)
        for decision in decisions:
            if self._decision_key(decision) == key:
                return decision
        decision = {
            "provider": provider,
            "account_id": account_id,
            "message_id": message_id,
            "batch_id": str(batch_id or "").strip(),
            "decision": "looks-right",
            "acknowledged_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        decisions.append(decision)
        write_json(self._path, {"decisions": decisions})
        return decision

    def is_acknowledged(self, item: dict) -> bool:
        provider = str(item.get("provider") or item.get("source") or "gmail").strip().lower()
        account_id = str(item.get("account_id") or "").strip()
        message_id = str(item.get("message_id") or "").strip()
        if not message_id:
            return False
        decisions = load_json_or_default(self._path, {"decisions": []}).get("decisions") or []
        exact_key = self._key(provider, account_id, message_id)
        if any(self._decision_key(decision) == exact_key for decision in decisions):
            return True
        if account_id:
            return False
        return any(
            str(decision.get("provider") or "").lower() == provider
            and str(decision.get("message_id") or "") == message_id
            for decision in decisions
        )

    @staticmethod
    def _key(provider: str, account_id: str, message_id: str) -> tuple[str, str, str]:
        return provider, account_id, message_id

    def _decision_key(self, decision: dict) -> tuple[str, str, str]:
        return self._key(
            str(decision.get("provider") or "").lower(),
            str(decision.get("account_id") or ""),
            str(decision.get("message_id") or ""),
        )
