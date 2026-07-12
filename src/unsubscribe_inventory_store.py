from datetime import UTC, datetime
from email.utils import parseaddr
from pathlib import Path

from src.local_artifacts import load_json, unsubscribe_selections_path, write_json
from src.local_batch_summary import load_batch
from src.sender_utils import normalized_sender_email
from src.unsubscribe_execution import UnsubscribeExecutor


class UnsubscribeInventoryStore:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def list_candidates(self) -> list[dict]:
        selection_map = self._load_selection_map()
        latest_attempt_map = UnsubscribeExecutor(self._storage_dir).latest_attempt_map()
        grouped: dict[str, dict] = {}

        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            provider = batch.get("provider") or "gmail"
            account_id = batch.get("account_id") or ""
            raw_messages = {message.get("id"): message for message in batch.get("raw_messages", [])}
            for item in batch.get("items", []):
                message_id = item.get("message_id")
                if not message_id:
                    continue
                raw_message = raw_messages.get(message_id, {})
                candidate = self._candidate_from_message(provider, account_id, item, raw_message)
                if candidate is None:
                    continue
                existing = grouped.get(candidate["list_key"])
                if existing is None:
                    grouped[candidate["list_key"]] = candidate
                    continue
                existing["evidence_count"] += 1
                existing["message_ids"].append(message_id)
                existing["qualification_reasons"] = sorted(
                    set(existing["qualification_reasons"]).union(candidate["qualification_reasons"])
                )
                if candidate["latest_message_date"] > existing["latest_message_date"]:
                    existing["latest_message_date"] = candidate["latest_message_date"]
                    existing["display_name"] = candidate["display_name"]
                    existing["sender"] = candidate["sender"]
                    existing["sender_address"] = candidate["sender_address"]
                    existing["list_unsubscribe"] = candidate["list_unsubscribe"]

        candidates = []
        for candidate in grouped.values():
            saved = selection_map.get(candidate["list_key"], {})
            candidate["decision_state"] = saved.get("decision_state", "undecided")
            candidate["list_unsubscribe_post"] = saved.get(
                "list_unsubscribe_post",
                candidate.get("list_unsubscribe_post", ""),
            )
            candidate["latest_execution"] = latest_attempt_map.get(candidate["list_key"])
            candidates.append(candidate)

        for list_key, saved in selection_map.items():
            if list_key in grouped:
                continue
            restored = dict(saved)
            restored["list_key"] = list_key
            restored["decision_state"] = saved.get("decision_state", "undecided")
            restored["latest_execution"] = latest_attempt_map.get(list_key)
            candidates.append(restored)

        candidates.sort(key=lambda item: item["display_name"].lower())
        candidates.sort(key=lambda item: item["latest_message_date"], reverse=True)
        candidates.sort(key=lambda item: _decision_rank(item["decision_state"]), reverse=True)
        return candidates

    def selected_candidate_map(self) -> dict[str, dict]:
        candidates = {}
        for list_key, saved in self._load_selection_map().items():
            if saved.get("decision_state") != "selected":
                continue
            restored = dict(saved)
            restored["list_key"] = list_key
            candidates[list_key] = restored
        return candidates

    def save_selection_states(self, candidate_keys: list[str], selected_candidate_keys: list[str]) -> list[dict]:
        selected_set = set(selected_candidate_keys)
        candidate_map = {candidate["list_key"]: candidate for candidate in self.list_candidates()}
        selections = self._load_selections()
        stored_candidates = selections.setdefault("candidates", {})
        saved_candidates: list[dict] = []

        for candidate_key in candidate_keys:
            candidate = candidate_map.get(candidate_key)
            if candidate is None:
                continue
            decision_state = "selected" if candidate_key in selected_set else "not_selected"
            saved_record = {
                "provider": candidate["provider"],
                "account_id": candidate["account_id"],
                "list_key": candidate["list_key"],
                "display_name": candidate["display_name"],
                "sender": candidate["sender"],
                "sender_address": candidate["sender_address"],
                "decision_state": decision_state,
                "evidence_count": candidate["evidence_count"],
                "latest_message_date": candidate["latest_message_date"],
                "qualification_reasons": candidate["qualification_reasons"],
                "list_unsubscribe": candidate.get("list_unsubscribe"),
                "list_unsubscribe_post": candidate.get("list_unsubscribe_post", ""),
                "updated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            }
            stored_candidates[candidate_key] = saved_record
            saved_candidates.append(saved_record)

        write_json(self._selection_path(), selections)
        return saved_candidates

    def _candidate_from_message(self, provider: str, account_id: str, item: dict, raw_message: dict) -> dict | None:
        return candidate_from_message(provider, account_id, item, raw_message)

    def _load_selections(self) -> dict:
        selection_path = self._selection_path()
        if not selection_path.exists():
            return {"candidates": {}}
        return load_json(selection_path)

    def _load_selection_map(self) -> dict[str, dict]:
        return self._load_selections().get("candidates", {})

    def _selection_path(self) -> Path:
        return unsubscribe_selections_path(self._storage_dir)


def candidate_from_message(provider: str, account_id: str, item: dict, raw_message: dict) -> dict | None:
        labels = set(item.get("final_labels") or item.get("applied_labels") or [])
        if labels.intersection({"account-security", "receipt-billing", "shopping-order", "calendar-event", "personal", "job-related"}):
            return None

        headers = {
            header["name"].lower(): header["value"]
            for header in raw_message.get("payload", {}).get("headers", [])
            if isinstance(header, dict) and header.get("name")
        }
        list_unsubscribe = headers.get("list-unsubscribe") or item.get("list_unsubscribe")
        list_unsubscribe_post = headers.get("list-unsubscribe-post", "")
        precedence = (headers.get("precedence") or item.get("precedence") or "").lower()
        gmail_label_ids = {label.lower() for label in raw_message.get("labelIds", []) if isinstance(label, str)}
        qualification_reasons = []
        if list_unsubscribe:
            qualification_reasons.append("List-Unsubscribe header")
        if precedence == "bulk":
            qualification_reasons.append("Bulk precedence header")
        if labels.intersection({"newsletter", "promotions", "spam-low-value"}):
            qualification_reasons.append("Promotional/newsletter classification")
        if "category_promotions" in gmail_label_ids:
            qualification_reasons.append("Gmail promotions category")
        if not qualification_reasons:
            return None

        sender = item.get("sender") or headers.get("from") or ""
        sender_address = normalized_sender_email(sender)
        display_name = _display_name(sender)
        identity = sender_address or sender.strip().lower()
        if not identity:
            return None

        return {
            "provider": provider,
            "account_id": account_id,
            "list_key": f"{provider}:{account_id}:{identity}",
            "display_name": display_name,
            "sender": sender,
            "sender_address": sender_address,
            "decision_state": "undecided",
            "evidence_count": 1,
            "latest_message_date": item.get("date") or "",
            "qualification_reasons": sorted(set(qualification_reasons)),
            "list_unsubscribe": list_unsubscribe,
            "list_unsubscribe_post": list_unsubscribe_post,
            "message_ids": [item.get("message_id")],
        }


def _display_name(sender: str) -> str:
    name, address = parseaddr(sender)
    return name or address or sender or "(unknown sender)"


def _decision_rank(decision_state: str) -> int:
    return {
        "selected": 2,
        "undecided": 1,
        "not_selected": 0,
    }.get(decision_state, 0)
