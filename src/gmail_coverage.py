import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from src.gmail_companion_state import artifact_path_sort_key, load_json
from src.live_gmail_client import GMAIL_READONLY_SCOPE


DEFAULT_COVERAGE_LIMIT = 100
DEFAULT_METADATA_WORKERS = 8
COVERAGE_SNAPSHOT_NAME = "gmail_coverage_snapshot.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _header(message: dict, name: str) -> str:
    for header in ((message.get("payload") or {}).get("headers") or []):
        if str(header.get("name") or "").lower() == name.lower():
            return str(header.get("value") or "")
    return ""


class GmailCoverageService:
    """Build a truthful, read-only view of current Gmail Inbox coverage.

    The service only lists and reads messages with gmail.readonly. It does not
    create unlabeled review work: mail absent from Threadwise's stored batches
    is reported as needing a normal classification run.
    """

    def __init__(
        self,
        storage_dir: Path,
        *,
        gmail_client_factory,
        credentials_dir: Path,
        client_secret_path: Path | None = None,
        limit: int = DEFAULT_COVERAGE_LIMIT,
    ) -> None:
        self._storage_dir = storage_dir
        self._gmail_client_factory = gmail_client_factory
        self._credentials_dir = credentials_dir
        self._client_secret_path = client_secret_path
        self._limit = limit
        self._condition = threading.Condition()
        self._inflight = False
        self._last_result: dict | None = None
        self._last_error: Exception | None = None

    @property
    def snapshot_path(self) -> Path:
        return self._storage_dir / COVERAGE_SNAPSHOT_NAME

    def check(self, account_id: str) -> dict:
        if not account_id:
            raise ValueError("Gmail coverage needs an account id from a stored Threadwise run.")
        with self._condition:
            if self._inflight:
                while self._inflight:
                    self._condition.wait()
                if self._last_error is not None:
                    raise self._last_error
                return {**(self._last_result or {}), "deduplicated": True}
            self._inflight = True
        try:
            result = self._run_check(account_id)
            with self._condition:
                self._last_result = result
                self._last_error = None
            return result
        except Exception as exc:
            with self._condition:
                self._last_error = exc
            raise
        finally:
            with self._condition:
                self._inflight = False
                self._condition.notify_all()

    def _run_check(self, account_id: str) -> dict:
        client = self._gmail_client_factory(
            account_id,
            self._credentials_dir,
            self._client_secret_path,
            GMAIL_READONLY_SCOPE,
        )
        candidate_ids = [
            str(message_id)
            for message_id in client.search_message_ids("in:inbox", self._limit + 1)
            if message_id
        ]
        bounded = len(candidate_ids) > self._limit
        message_ids = list(dict.fromkeys(candidate_ids[: self._limit]))
        known = self._known_message_states()
        previous = self._load_snapshot()
        cached_metadata = dict(previous.get("metadata") or {})
        metadata_getter = getattr(client, "get_message_metadata", client.get_message)
        metadata_ids = [
            message_id
            for message_id in message_ids
            if message_id not in known and message_id not in cached_metadata
        ]
        fetched_metadata: dict[str, dict | None] = {}

        def fetch_metadata(message_id: str) -> dict | None:
            try:
                message = metadata_getter(message_id)
                return {
                    "message_id": message_id,
                    "thread_id": str(message.get("threadId") or ""),
                    "subject": _header(message, "Subject") or "(no subject)",
                    "sender": _header(message, "From") or "(unknown sender)",
                }
            except Exception:
                return None

        if metadata_ids:
            worker_count = min(DEFAULT_METADATA_WORKERS, len(metadata_ids))
            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="gmail-coverage") as executor:
                fetched_metadata = dict(zip(metadata_ids, executor.map(fetch_metadata, metadata_ids), strict=True))
        metadata: dict[str, dict] = {}
        review_items: list[dict] = []
        requires_sync_count = 0
        read_failures = 0
        reused_count = 0
        provider_get_count = 0

        for message_id in message_ids:
            known_item = known.get(message_id)
            if known_item is not None:
                metadata[message_id] = {
                    "message_id": message_id,
                    "subject": str(known_item.get("subject") or "(no subject)"),
                    "sender": str(known_item.get("sender") or "(unknown sender)"),
                }
                if self._needs_judgment(known_item):
                    if known_item.get("final_labels") or known_item.get("applied_labels"):
                        review_items.append(self._review_item(
                            metadata[message_id],
                            source="stored-unresolved",
                            classified_item=known_item,
                        ))
                    else:
                        requires_sync_count += 1
                continue
            if message_id in cached_metadata:
                item_metadata = dict(cached_metadata[message_id])
                reused_count += 1
            else:
                provider_get_count += 1
                item_metadata = fetched_metadata.get(message_id)
                if item_metadata is None:
                    read_failures += 1
                    continue
            metadata[message_id] = item_metadata
            requires_sync_count += 1

        is_partial = bounded or read_failures > 0 or requires_sync_count > 0
        unchecked_count = read_failures + requires_sync_count + (1 if bounded else 0)
        status = "partial" if is_partial else ("queue-ready" if review_items else "verified-clear")
        checked_at = _utc_now()
        scope = (
            f"First {self._limit} current Gmail Inbox messages"
            if bounded
            else "Current Gmail Inbox messages"
        )
        result = {
            "status": status,
            "checked_at": checked_at,
            "checked_count": len(message_ids) - read_failures,
            "candidate_count": len(message_ids) + (1 if bounded else 0),
            "needs_review_count": len(review_items),
            "review_items": review_items,
            "scope": scope,
            "scope_complete": not is_partial,
            "bounded": bounded,
            "read_failure_count": read_failures,
            "unchecked_count": unchecked_count,
            "requires_sync_count": requires_sync_count,
            "reused_metadata_count": reused_count,
            "gmail_mutation": "none",
            "provider_routes_called": ["gmail.messages.list", *(["gmail.messages.get"] if provider_get_count else [])],
            "truth_note": (
                "Unread mail stays in your inbox. Only classified messages needing your judgment enter this queue."
            ),
        }
        self._persist_snapshot({**result, "metadata": metadata, "message_ids": message_ids})
        return result

    def _known_message_states(self) -> dict[str, dict]:
        known: dict[str, dict] = {}
        batches_dir = self._storage_dir / "batches"
        if not batches_dir.exists():
            return known
        for path in sorted(batches_dir.glob("*.json"), key=artifact_path_sort_key, reverse=True):
            batch = load_json(path)
            if (batch.get("provider") or "gmail") != "gmail":
                continue
            if batch.get("coverage_read_only") is True:
                continue
            for item in batch.get("items") or []:
                message_id = str(item.get("message_id") or "")
                if message_id and message_id not in known:
                    known[message_id] = item
        return known

    @staticmethod
    def _needs_judgment(item: dict) -> bool:
        return item.get("review_state") != "reviewed" or not (
            item.get("final_labels") or item.get("applied_labels")
        )

    @staticmethod
    def _review_item(metadata: dict, *, source: str, classified_item: dict | None = None) -> dict:
        classified_item = classified_item or {}
        labels = list(classified_item.get("final_labels") or classified_item.get("applied_labels") or [])
        return {
            "provider": "gmail",
            "message_id": str(metadata.get("message_id") or ""),
            "thread_id": str(metadata.get("thread_id") or ""),
            "subject": str(metadata.get("subject") or "(no subject)"),
            "sender": str(metadata.get("sender") or "(unknown sender)"),
            "internal_label": labels[0] if labels else None,
            "suggested_label": labels[0] if labels else None,
            "classification": labels[0] if labels else "Classification unavailable",
            "status": "needs-attention",
            "status_label": "Needs review",
            "reason": str(classified_item.get("interpretation") or "Threadwise labeled this message and wants your confirmation."),
            "coverage_source": source,
        }

    def _load_snapshot(self) -> dict:
        if not self.snapshot_path.exists():
            return {}
        try:
            return json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _persist_snapshot(self, payload: dict) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.snapshot_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.snapshot_path)
