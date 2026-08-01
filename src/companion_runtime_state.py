import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from src.gmail_companion_state import (
    build_companion_runtime_payload,
    build_daily_summary,
    build_selected_email_state,
    selected_email_understanding_state,
)
from src.gmail_run_control import load_gmail_dashboard_run_status
from src.handled_review_store import HandledReviewStore
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore


HARNESS_STATE_CACHE_SECONDS = 120.0
COMPANION_DATA_CACHE_SECONDS = 120.0


class CompanionRuntimeState:
    """Own cached companion snapshots, activity state, and invalidation semantics."""

    def __init__(
        self,
        storage_dir: Path,
        *,
        unsubscribe_store: UnsubscribeInventoryStore,
        handled_review_store: HandledReviewStore,
        analytics_status: Callable[[], dict],
        live_inbox_ids_loader: Callable[[], set[str] | None],
        background_runner: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self._storage_dir = storage_dir
        self._unsubscribe_store = unsubscribe_store
        self._handled_review_store = handled_review_store
        self._analytics_status = analytics_status
        self._live_inbox_ids_loader = live_inbox_ids_loader
        self._background_runner = background_runner or _start_background_thread
        self._harness_cache: dict[str, tuple[float, dict]] = {}
        self._harness_lock = threading.Lock()
        self._runtime_payload_cache: tuple[float, dict] | None = None
        self._live_inbox_ids_cache: tuple[float, set[str] | None] | None = None
        self._daily_summary_cache: tuple[float, dict] | None = None
        self._unsubscribe_candidates_cache: tuple[float, list[dict]] | None = None
        self._data_lock = threading.Lock()
        self._async_follow_up_state: dict | None = None
        self._provider_write_state: dict | None = None
        self._pending_provider_writes: list[Callable[[], dict]] = []
        self._failed_provider_writes: list[Callable[[], dict]] = []
        self._provider_write_worker_running = False
        self._async_lock = threading.Lock()

    def sidebar(self, selected_context: dict | None) -> dict:
        selected_context = selected_context or {}
        return {
            "contract_version": "gmail-companion-sidebar-v1",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "selected_context": selected_context,
            "selected_email": build_selected_email_state(
                self._storage_dir,
                self.unsubscribe_candidates(),
                selected_context,
            ),
            "daily_summary": self._daily_summary(),
            "run_status": load_gmail_dashboard_run_status(self._storage_dir),
            "ui_state": self._ui_state(),
        }

    def harness(self, selected_context: dict | None) -> dict:
        selected_context = selected_context or {}
        cache_key = json.dumps(selected_context, sort_keys=True)
        now = time.monotonic()
        with self._harness_lock:
            cached = self._harness_cache.get(cache_key)
            if cached is not None:
                created_at, payload = cached
                if now - created_at <= HARNESS_STATE_CACHE_SECONDS:
                    return self._with_live_understanding(payload, selected_context)
            payload = self._build_harness(selected_context)
            self._harness_cache[cache_key] = (time.monotonic(), payload)
            return self._with_live_understanding(payload, selected_context)

    def runtime_payload(self) -> dict:
        now = time.monotonic()
        with self._data_lock:
            if self._runtime_payload_cache is not None:
                created_at, payload = self._runtime_payload_cache
                if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                    return payload
            payload = build_companion_runtime_payload(
                self._storage_dir,
                provider="gmail",
                allowed_review_message_ids=self._live_inbox_ids(),
            )
            self._runtime_payload_cache = (time.monotonic(), payload)
            return payload

    def unsubscribe_candidates(self) -> list[dict]:
        now = time.monotonic()
        with self._data_lock:
            if self._unsubscribe_candidates_cache is not None:
                created_at, payload = self._unsubscribe_candidates_cache
                if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                    return payload
            payload = self._unsubscribe_store.list_candidates()
            self._unsubscribe_candidates_cache = (time.monotonic(), payload)
            return payload

    def invalidate(self) -> None:
        with self._data_lock:
            self._runtime_payload_cache = None
            self._live_inbox_ids_cache = None
            self._daily_summary_cache = None
            self._unsubscribe_candidates_cache = None
        with self._harness_lock:
            self._harness_cache.clear()

    def start_teaching_refresh(self, selected_context: dict) -> None:
        selected_context = dict(selected_context or {})
        self._set_async_follow_up(
            {
                "kind": "teach-apply-refresh",
                "state": "working",
                "label": "Background refresh running",
                "message": "Refreshing the queue summary and follow-up context in the background.",
            }
        )
        self._background_runner(lambda: self._run_teaching_refresh(selected_context))

    def start_teaching_write(self, work: Callable[[], dict]) -> None:
        with self._async_lock:
            self._pending_provider_writes.append(work)
            pending_count = len(self._pending_provider_writes)
            self._provider_write_state = {
                "id": "gmail-teaching-write",
                "kind": "provider-write",
                "state": "working",
                "label": "Gmail writes running",
                "message": f"Threadwise is applying {pending_count} accepted Gmail change{'s' if pending_count != 1 else ''} in order.",
                "provider": "gmail",
            }
            if self._provider_write_worker_running:
                return
            self._provider_write_worker_running = True
        self._background_runner(self._run_teaching_write_queue)

    def retry_teaching_writes(self) -> dict:
        with self._async_lock:
            if self._provider_write_worker_running:
                raise ValueError("Gmail writes are still running.")
            if not self._failed_provider_writes:
                raise ValueError("There are no failed Gmail writes to retry.")
            self._pending_provider_writes.extend(self._failed_provider_writes)
            self._failed_provider_writes.clear()
            self._provider_write_worker_running = True
            self._provider_write_state = {
                "id": "gmail-teaching-write",
                "kind": "provider-write",
                "state": "working",
                "label": "Retrying Gmail writes",
                "message": "Threadwise is retrying the failed Gmail changes in order.",
                "provider": "gmail",
            }
        self._background_runner(self._run_teaching_write_queue)
        return self._provider_write_status() or {}

    def acknowledge_handled_review(self, payload: dict) -> dict:
        selected_context = dict(payload.get("selected_context") or {})
        selected_email = self.sidebar(selected_context).get("selected_email") or {}
        if not selected_email.get("found"):
            raise ValueError("Selected email is not available for handled review.")
        if selected_email.get("status") not in {
            "auto-handled",
            "kept-visible",
            "auto-labeled",
            "provider-confirmed",
        }:
            raise ValueError("Selected email is not a completed handled item.")
        decision = self._handled_review_store.acknowledge(
            provider=selected_email.get("provider")
            or selected_context.get("provider")
            or "gmail",
            account_id=selected_email.get("account_id")
            or selected_context.get("account_id")
            or "",
            message_id=selected_email.get("message_id")
            or selected_context.get("message_id")
            or "",
            batch_id=selected_email.get("batch_id") or "",
        )
        self.invalidate()
        return {
            "acknowledged": True,
            "decision": decision,
            "harness_state": self.harness(selected_context),
        }

    def _daily_summary(self) -> dict:
        now = time.monotonic()
        with self._data_lock:
            if self._daily_summary_cache is not None:
                created_at, payload = self._daily_summary_cache
                if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                    return payload
            payload = build_daily_summary(self._storage_dir)
            self._daily_summary_cache = (time.monotonic(), payload)
            return payload

    def _live_inbox_ids(self) -> set[str] | None:
        now = time.monotonic()
        if self._live_inbox_ids_cache is not None:
            created_at, message_ids = self._live_inbox_ids_cache
            if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                return message_ids
        message_ids = self._live_inbox_ids_loader()
        self._live_inbox_ids_cache = (time.monotonic(), message_ids)
        return message_ids

    def _async_follow_up(self) -> dict | None:
        with self._async_lock:
            return dict(self._async_follow_up_state) if self._async_follow_up_state else None

    def _set_async_follow_up(self, payload: dict | None) -> None:
        with self._async_lock:
            self._async_follow_up_state = dict(payload) if payload else None

    def _activity_feed(self) -> list[dict]:
        follow_up = self._async_follow_up()
        provider_write = self._provider_write_status()
        items = []
        if provider_write:
            items.append(provider_write)
        if follow_up:
            items.append({
                "id": follow_up.get("kind") or "async-follow-up",
                "kind": follow_up.get("kind") or "async-follow-up",
                "state": follow_up.get("state") or "working",
                "label": follow_up.get("label") or "Background refresh",
                "message": follow_up.get("message") or "",
            })
        return items

    def _ui_state(self) -> dict:
        return {
            "default_mode": "expanded",
            "can_minimize": True,
            "panel_title": "Threadwise",
            "allowed_labels": [
                {"id": label, "name": gmail_label_name(label)}
                for label in CANONICAL_LABEL_ORDER
            ],
            "async_follow_up": self._async_follow_up(),
            "provider_write": self._provider_write_status(),
            "activity_feed": self._activity_feed(),
        }

    def _provider_write_status(self) -> dict | None:
        with self._async_lock:
            return dict(self._provider_write_state) if self._provider_write_state else None

    def _set_provider_write_state(self, payload: dict | None) -> None:
        with self._async_lock:
            self._provider_write_state = dict(payload) if payload else None

    def _run_teaching_write_queue(self) -> None:
        completed = 0
        while True:
            with self._async_lock:
                if not self._pending_provider_writes:
                    self._provider_write_worker_running = False
                    failed_count = len(self._failed_provider_writes)
                    self._provider_write_state = {
                        "id": "gmail-teaching-write",
                        "kind": "provider-write",
                        "state": "error" if failed_count else "done",
                        "label": "Gmail writes need attention" if failed_count else "Gmail labels applied",
                        "message": (
                            f"{failed_count} accepted Gmail change{'s' if failed_count != 1 else ''} could not be confirmed."
                            if failed_count
                            else f"{completed} accepted Gmail change{'s' if completed != 1 else ''} confirmed."
                        ),
                        "provider": "gmail",
                        **({"action": "retry-provider-write", "action_label": "Try again"} if failed_count else {}),
                    }
                    return
                work = self._pending_provider_writes.pop(0)
            failed = False
            try:
                summary = work() or {}
                failed = bool(
                    int(summary.get("label_write_failed") or 0)
                    + int(summary.get("inbox_remove_failed") or 0)
                )
            except Exception:
                failed = True
            with self._async_lock:
                if failed:
                    self._failed_provider_writes.append(work)
                else:
                    completed += 1

    def _run_teaching_refresh(self, selected_context: dict) -> None:
        try:
            self.invalidate()
            self.sidebar(selected_context)
            self._set_async_follow_up(
                {
                    "kind": "teach-apply-refresh",
                    "state": "done",
                    "label": "Background refresh done",
                    "message": "Queue summary and follow-up context are ready.",
                }
            )
            cache_key = json.dumps(selected_context, sort_keys=True)
            payload = self._build_harness(selected_context)
            with self._harness_lock:
                self._harness_cache[cache_key] = (time.monotonic(), payload)
        except Exception as exc:
            self._set_async_follow_up(
                {
                    "kind": "teach-apply-refresh",
                    "state": "retry",
                    "label": "Background refresh stalled",
                    "message": f"Queue summary refresh stalled: {exc}",
                }
            )

    def _build_harness(self, selected_context: dict) -> dict:
        runtime = self.runtime_payload()
        items = runtime.get("items", [])
        unacknowledged_items = [
            item
            for item in items
            if not self._handled_review_store.is_acknowledged(item)
        ]
        sidebar_state = self.sidebar(selected_context)
        sidebar_state["daily_summary"] = (
            runtime.get("daily_summary")
            or sidebar_state.get("daily_summary")
            or {}
        )
        selected_email = dict(sidebar_state.get("selected_email") or {})
        selected_message_id = str(selected_context.get("message_id") or "")
        runtime_selected = next(
            (
                item
                for item in [
                    *(runtime.get("needs_attention_items") or []),
                    *(runtime.get("items") or []),
                ]
                if str(item.get("message_id") or "") == selected_message_id
            ),
            None,
        )
        if runtime_selected is not None:
            for field in (
                "internal_label",
                "suggested_label",
                "classification",
                "status",
                "status_label",
                "action_reason",
                "reason",
            ):
                if runtime_selected.get(field) is not None:
                    selected_email[field] = runtime_selected[field]
        selected_email["handled_review_acknowledged"] = (
            self._handled_review_store.is_acknowledged(selected_email)
        )
        sidebar_state["selected_email"] = selected_email
        return {
            "selected_context": selected_context,
            "sidebar_state": sidebar_state,
            "recent_items": unacknowledged_items[:24],
            "needs_attention_items": list(runtime.get("needs_attention_items") or [])[:12],
            "auto_handled_items": [
                item
                for item in unacknowledged_items
                if item.get("status") == "auto-handled"
            ][:12],
            "kept_visible_items": [
                item
                for item in unacknowledged_items
                if item.get("status") in {"kept-visible", "auto-labeled", "provider-confirmed"}
            ][:12],
            "analytics_status": self._analytics_status(),
        }

    def _with_live_understanding(self, payload: dict, selected_context: dict) -> dict:
        sidebar_state = dict(payload.get("sidebar_state") or {})
        selected_email = dict(sidebar_state.get("selected_email") or {})
        live_context = selected_context or payload.get("selected_context") or {}
        selected_email.update(selected_email_understanding_state(live_context))
        sidebar_state["selected_email"] = selected_email
        return {
            **payload,
            "sidebar_state": sidebar_state,
        }


def _start_background_thread(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()
