from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from email.utils import parseaddr
from pathlib import Path

from src.gmail_companion_rendering import escape_html
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import load_json_or_default, write_json
from src.proton_feedback_memory import migrate_review_feedback, save_feedback_rule
from src.provider_write_queue import ProviderWriteQueue


def _start_background_thread(work) -> None:
    threading.Thread(target=work, daemon=True).start()


def _normalized_sender_identity(value: object) -> str:
    text = str(value or "").strip()
    address = parseaddr(text)[1].strip().casefold()
    return address or " ".join(text.casefold().split())


def _normalized_subject(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def sync_proton_review_ledger(storage_dir: Path, batch_id: str) -> dict:
    """Project one classified Proton batch into the user-facing review queue."""
    batch_path = storage_dir / "batches" / f"{batch_id}.json"
    batch = load_json_or_default(batch_path, {})
    if not isinstance(batch, dict) or not isinstance(batch.get("items"), list):
        raise ValueError(f"Proton batch not found or malformed: {batch_id}")
    if (batch.get("provider") or "") != "protonmail":
        raise ValueError(f"Batch is not a ProtonMail batch: {batch_id}")

    ledger_path = storage_dir / "live_manual_review_ledger.json"
    ledger = load_json_or_default(ledger_path, {"provider": "protonmail", "messages": {}})
    records = ledger.setdefault("messages", {})
    projected = 0
    for item in batch["items"]:
        message_id = str(item.get("message_id") or "")
        if not message_id or records.get(message_id, {}).get("status") == "applied":
            continue
        internal_labels = [str(label) for label in item.get("applied_labels") or [] if str(label)]
        provider_write_state = str(item.get("provider_write_state") or "")
        review_required = item.get("review_state") == "pending"
        records[message_id] = {
            "status": "suggested" if review_required else "provider-confirmed" if provider_write_state == "applied" else "suggested",
            "batch_id": batch_id,
            "account_id": str(batch.get("account_id") or ""),
            "sender": str(item.get("sender") or ""),
            "subject": str(item.get("subject") or ""),
            "date": str(item.get("date") or ""),
            "internal_labels": internal_labels,
            "labels": [gmail_label_name(label) for label in internal_labels],
            "internal_label": internal_labels[0] if internal_labels else "",
            "label": gmail_label_name(internal_labels[0]) if internal_labels else "",
            "reason": str(item.get("interpretation") or "No explanation was stored."),
            "confidence_band": str(item.get("confidence_band") or "low"),
            "review_required": review_required,
            "provider_write_state": provider_write_state,
        }
        projected += 1

    ledger["provider"] = "protonmail"
    ledger["account_id"] = str(batch.get("account_id") or ledger.get("account_id") or "")
    ledger["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    write_json(ledger_path, ledger)
    return {"ledger_path": str(ledger_path), "projected_count": projected}


class ProtonReviewConsole:
    """A bounded, label-only review queue backed by Proton Mail Bridge."""

    def __init__(
        self,
        proton_client: object,
        classification_ledger_path: Path,
        review_state_path: Path,
        *,
        max_results: int = 10_000,
    ) -> None:
        self._proton = proton_client
        self._classification_ledger_path = classification_ledger_path
        self._review_state_path = review_state_path
        self._max_results = max_results
        self._lock = threading.Lock()
        self._provider_writes = ProviderWriteQueue(
            provider="protonmail",
            provider_name="Proton Mail",
            background_runner=_start_background_thread,
            failure_keys=("label_write_failed",),
        )
        migrate_review_feedback(self._classification_ledger_path.parent, self._review_state_path)

    def state(self) -> dict:
        with self._lock:
            return self._state_unlocked()

    def check_coverage(self, limit: int = 100) -> dict:
        """Build a current Proton review snapshot using read-only Bridge calls."""
        if limit < 1:
            raise ValueError("Proton inbox coverage limit must be positive.")
        with self._lock:
            checked_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            listed_ids = list(dict.fromkeys(
                str(message_id)
                for message_id in self._proton.list_messages(limit + 1)
                if str(message_id)
            ))
            bounded = len(listed_ids) > limit
            live_ids = listed_ids[:limit]
            classification = load_json_or_default(
                self._classification_ledger_path,
                {"provider": "protonmail", "messages": {}},
            )
            review_state = load_json_or_default(
                self._review_state_path,
                {"provider": "protonmail", "messages": {}},
            )
            records = classification.setdefault("messages", {})
            reviewed_ids = set((review_state.get("messages") or {}).keys())
            completed_ids = {
                message_id
                for message_id, record in records.items()
                if str(record.get("status") or "").lower()
                in {"applied", "provider-confirmed", "completed"}
            } | reviewed_ids
            review_items: list[dict] = []
            read_failure_count = 0
            requires_sync_count = 0
            for message_id in live_ids:
                if message_id in completed_ids:
                    continue
                record = records.get(message_id)
                coverage_source = "stored-unresolved"
                if not isinstance(record, dict):
                    try:
                        self._proton.get_message(message_id)
                    except Exception:
                        read_failure_count += 1
                        continue
                    requires_sync_count += 1
                    continue
                if not (record.get("internal_labels") or record.get("internal_label")):
                    requires_sync_count += 1
                    continue
                item = self._companion_review_item_unlocked(message_id, record)
                item["coverage_source"] = coverage_source
                review_items.append(item)

            checked_count = max(0, len(live_ids) - read_failure_count)
            unchecked_count = int(bounded) + read_failure_count + requires_sync_count
            status = (
                "partial"
                if unchecked_count
                else "queue-ready"
                if review_items
                else "verified-clear"
            )
            return {
                "status": status,
                "provider": "protonmail",
                "checked_at": checked_at,
                "checked_count": checked_count,
                "candidate_count": len(live_ids) + int(bounded),
                "needs_review_count": len(review_items),
                "read_failure_count": read_failure_count,
                "unchecked_count": unchecked_count,
                "requires_sync_count": requires_sync_count,
                "scope": f"Current Proton Mail Inbox messages (up to {limit})",
                "scope_complete": not bounded,
                "bounded": bounded,
                "review_items": review_items,
                "provider_mutation": "none",
                "provider_routes_called": ["list_messages", "get_message"],
            }

    def companion_harness(self, selected_context: dict | None = None) -> dict:
        """Project the Proton queue into the shared companion sidebar contract."""
        selected_context = {
            **(selected_context or {}),
            "provider": "protonmail",
        }
        with self._lock:
            state = self._state_unlocked()
            selected_email = self._companion_selected_email_unlocked(state, selected_context)

        review_items = list(state.get("items") or [])
        completed_count = int(state.get("completed_count") or 0)
        daily_summary = {
            "provider": "protonmail",
            "account_id": state.get("account_id") or "",
            "processed_count": int(state.get("remaining_count") or 0) + completed_count,
            "needs_attention_count": int(state.get("remaining_count") or 0),
            "unlabeled_count": int(state.get("remaining_count") or 0),
            "auto_handled_count": completed_count,
            "kept_visible_count": completed_count,
            "recent_items": review_items,
            "needs_attention_items": review_items,
            "auto_handled_items": [],
            "kept_visible_items": [],
            "run_count": 1 if review_items or completed_count else 0,
            "source_label": "live Proton Mail inbox",
        }
        provider_write = self._companion_provider_write_activity()
        activity_feed = [provider_write] if provider_write else []
        sidebar_state = {
            "contract_version": "threadwise-sidebar-v2",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "selected_context": selected_context,
            "selected_email": selected_email,
            "daily_summary": daily_summary,
            "run_status": {},
            "ui_state": {
                "default_mode": "minimized",
                "can_minimize": True,
                "panel_title": "Threadwise",
                "provider": "protonmail",
                "provider_name": "Proton Mail",
                "allowed_labels": [
                    {"id": label, "name": gmail_label_name(label)}
                    for label in CANONICAL_LABEL_ORDER
                ],
                "async_follow_up": None,
                "provider_write": provider_write,
                "activity_feed": activity_feed,
            },
        }
        return {
            "selected_context": selected_context,
            "sidebar_state": sidebar_state,
            "recent_items": review_items[:24],
            "needs_attention_items": review_items,
            "auto_handled_items": [],
            "kept_visible_items": [],
            "analytics_status": {"state": "active"},
        }

    def start_companion_write(self, work) -> None:
        self._provider_writes.submit(work)

    def _companion_provider_write_activity(self) -> dict | None:
        return self._provider_writes.activity()

    def companion_write_activity(self) -> dict | None:
        return self._companion_provider_write_activity()

    def retry_companion_write(self) -> dict:
        return self._provider_writes.retry()

    def live_message_ids(self) -> set[str]:
        return set(self._proton.list_messages(self._max_results))

    def acknowledge(self, message_id: str, note: str = "") -> dict:
        with self._lock:
            self._require_pending_unlocked(message_id)
            self._record_decision_unlocked(
                message_id,
                decision="looks-right",
                provider_verified=False,
                note=str(note or "").strip()[:500],
            )
            return self._state_unlocked()

    def apply_suggested(self, message_id: str) -> dict:
        """Apply every locally suggested label, then verify each Proton write."""
        with self._lock:
            current = self._require_pending_unlocked(message_id)
            internal_labels = list(current.get("suggested_internal_labels") or [])
            if not internal_labels:
                raise ValueError("This email has no suggested label. Choose a label or leave it unresolved.")
            return self._apply_labels_unlocked(current, internal_labels, decision="suggested-labels-applied")

    def apply_primary(self, message_id: str) -> dict:
        """Apply only the primary suggestion; additional suggestions require an explicit action."""
        with self._lock:
            current = self._require_pending_unlocked(message_id)
            internal_labels = list(current.get("suggested_internal_labels") or [])
            if not internal_labels:
                raise ValueError("This email has no suggested label. Choose a label or leave it unresolved.")
            return self._apply_labels_unlocked(current, internal_labels[:1], decision="primary-label-applied")

    def _apply_labels_unlocked(self, current: dict, internal_labels: list[str], *, decision: str) -> dict:
        provider_mailboxes: list[str] = []
        for internal_label in internal_labels:
            label_name = gmail_label_name(internal_label)
            write_result = self._proton.apply_label(current["message_id"], label_name)
            if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                raise RuntimeError("Proton label write violated the label-only safety contract.")
            rfc_message_id = str(current.get("rfc_message_id") or "").strip()
            if not rfc_message_id or not self._proton.message_has_label(rfc_message_id, label_name):
                raise RuntimeError("Proton did not confirm the label after the write; the review item was not advanced.")
            provider_mailboxes.append(str(write_result.get("mailbox") or ""))

        self._record_decision_unlocked(
            current["message_id"],
            decision=decision,
            provider_verified=True,
            internal_labels=internal_labels,
            labels=[gmail_label_name(label) for label in internal_labels],
            provider_mailboxes=provider_mailboxes,
        )
        return self._state_unlocked()

    def apply_label(self, message_id: str, internal_label: str, note: str = "") -> dict:
        if internal_label not in CANONICAL_LABEL_ORDER:
            raise ValueError("Choose one of Threadwise's allowed labels.")
        with self._lock:
            current = self._require_pending_unlocked(message_id)
            label_name = gmail_label_name(internal_label)
            write_result = self._proton.apply_label(message_id, label_name)
            if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                raise RuntimeError("Proton label write violated the label-only safety contract.")

            rfc_message_id = str(current.get("rfc_message_id") or "").strip()
            if not rfc_message_id:
                raise RuntimeError("Could not verify the Proton label because the email has no Message-ID header.")
            if not self._proton.message_has_label(rfc_message_id, label_name):
                raise RuntimeError("Proton did not confirm the label after the write; the review item was not advanced.")

            self._record_decision_unlocked(
                message_id,
                decision="label-added",
                provider_verified=True,
                internal_label=internal_label,
                label=label_name,
                provider_mailbox=str(write_result.get("mailbox") or ""),
                note=str(note or "").strip()[:500],
            )
            if note:
                save_feedback_rule(
                    self._classification_ledger_path.parent,
                    message_id=message_id,
                    sender=str(current.get("sender") or ""),
                    subject=str(current.get("subject") or ""),
                    note=note,
                    internal_label=internal_label,
                )
            return self._state_unlocked()

    def apply_companion_label(self, message_id: str, internal_label: str) -> dict:
        """Apply one shared-companion decision without requiring queue position."""
        if internal_label not in CANONICAL_LABEL_ORDER:
            raise ValueError("Choose one of Threadwise's allowed labels.")
        with self._lock:
            classification = load_json_or_default(
                self._classification_ledger_path,
                {"provider": "protonmail", "messages": {}},
            )
            record = (classification.get("messages") or {}).get(message_id)
            if not isinstance(record, dict):
                raise ValueError("That Proton Mail message is not in the current Threadwise sync.")
            if message_id not in set(self._proton.list_messages(self._max_results)):
                raise ValueError("That Proton Mail message is no longer in Inbox.")
            message = self._proton.get_message(message_id)
            label_name = gmail_label_name(internal_label)
            write_result = self._proton.apply_label(message_id, label_name)
            if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                raise RuntimeError("Proton label write violated the label-only safety contract.")
            rfc_message_id = str(message.get("rfc_message_id") or "").strip()
            if not rfc_message_id or not self._proton.message_has_label(rfc_message_id, label_name):
                raise RuntimeError("Proton did not confirm the label after the write.")
            self._record_decision_unlocked(
                message_id,
                decision="companion-label-applied",
                provider_verified=True,
                internal_label=internal_label,
                label=label_name,
                provider_mailbox=str(write_result.get("mailbox") or ""),
            )
            return {
                "message_id": message_id,
                "label": label_name,
                "inbox_preserved": True,
                "destructive_actions": [],
                "provider_verified": True,
            }

    def _state_unlocked(self) -> dict:
        classification = load_json_or_default(
            self._classification_ledger_path,
            {"provider": "protonmail", "messages": {}},
        )
        review_state = load_json_or_default(
            self._review_state_path,
            {"provider": "protonmail", "messages": {}},
        )
        live_ids = set(self._proton.list_messages(self._max_results))
        reviewed = review_state.get("messages") or {}
        provider_completed = {
            message_id
            for message_id, record in (classification.get("messages") or {}).items()
            if str(record.get("status") or "").lower() in {"applied", "provider-confirmed", "completed"}
        }
        completed_ids = provider_completed | set(reviewed)
        candidates: list[tuple[float, str, dict]] = []
        for message_id, record in (classification.get("messages") or {}).items():
            if message_id not in live_ids or message_id in completed_ids:
                continue
            has_label = bool(
                record.get("internal_labels")
                or record.get("internal_label")
                or record.get("labels")
                or record.get("label")
            )
            if not has_label:
                continue
            confidence = float((record.get("double_check") or {}).get("confidence", 1.0))
            candidates.append((confidence, message_id, record))
        candidates.sort(key=lambda item: (item[0], item[1]))

        review_items = [
            self._companion_review_item_unlocked(message_id, record)
            for _, message_id, record in candidates
        ]
        current = None
        if candidates:
            confidence, message_id, record = candidates[0]
            message = self._proton.get_message(message_id)
            current = {
                "message_id": message_id,
                "sender": str(message.get("sender") or ""),
                "subject": str(message.get("subject") or ""),
                "date": str(message.get("date") or ""),
                "body": str(message.get("body") or ""),
                "rfc_message_id": str(message.get("rfc_message_id") or ""),
                "suggested_internal_labels": list(record.get("internal_labels") or ([record.get("internal_label")] if record.get("internal_label") else [])),
                "suggested_labels": list(record.get("labels") or ([record.get("label")] if record.get("label") else [])),
                "suggested_internal_label": str(record.get("internal_label") or ""),
                "suggested_label": str(record.get("label") or ""),
                "reason": str(record.get("reason") or "No label suggestion was stored."),
                "confidence": confidence,
                "source_batch_id": str(record.get("batch_id") or ""),
            }
        return {
            "provider": "protonmail",
            "account_id": str(classification.get("account_id") or ""),
            "queue_name": "Proton inbox review",
            "remaining_count": len(candidates),
            "reviewed_count": len(reviewed),
            "completed_count": len(completed_ids & live_ids),
            "current": current,
            "items": review_items,
            "allowed_labels": [
                {"internal_label": label, "display_label": gmail_label_name(label)}
                for label in CANONICAL_LABEL_ORDER
            ],
            "safety": {
                "label_only": True,
                "inbox_preserved": True,
                "destructive_actions": [],
            },
        }

    def _companion_review_item_unlocked(self, message_id: str, record: dict) -> dict:
        sender = str(record.get("sender") or "")
        subject = str(record.get("subject") or "")
        received_at = str(record.get("date") or "")
        if not sender or not subject:
            message = self._proton.get_message(message_id)
            sender = sender or str(message.get("sender") or "")
            subject = subject or str(message.get("subject") or "")
            received_at = received_at or str(message.get("date") or "")
        internal_labels = list(
            record.get("internal_labels")
            or ([record.get("internal_label")] if record.get("internal_label") else [])
        )
        labels = list(
            record.get("labels")
            or ([record.get("label")] if record.get("label") else [])
        )
        return {
            "provider": "protonmail",
            "account_id": str(record.get("account_id") or ""),
            "batch_id": str(record.get("batch_id") or ""),
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "received_at": received_at,
            "internal_label": internal_labels[0] if internal_labels else None,
            "all_labels": internal_labels,
            "suggested_label": internal_labels[0] if internal_labels else None,
            "classification": labels[0] if labels else "Uncategorized",
            "all_classifications": labels,
            "status": "needs-attention",
            "status_label": "Needs attention",
            "action_reason": "Choose or confirm label",
            "reason": str(record.get("reason") or "No label suggestion was stored."),
            "unsubscribe_available": False,
        }

    def _companion_selected_email_unlocked(self, state: dict, selected_context: dict) -> dict:
        has_context = bool(
            selected_context.get("message_id")
            or selected_context.get("subject")
            or selected_context.get("sender")
        )
        if not has_context:
            return {
                "found": False,
                "provider": "protonmail",
                "status": "idle",
                "status_label": "Waiting for message selection",
                "subject": "",
                "sender": "",
                "understanding_state": "idle",
                "understanding_label": "Idle",
                "understanding_message": "Open an email to inspect or teach Threadwise.",
            }

        selected_id = str(selected_context.get("message_id") or "")
        selected_sender = _normalized_sender_identity(selected_context.get("sender"))
        selected_subject = _normalized_subject(selected_context.get("subject"))
        classification = load_json_or_default(
            self._classification_ledger_path,
            {"provider": "protonmail", "messages": {}},
        )
        records = classification.get("messages") or {}
        live_ids = set(self._proton.list_messages(self._max_results))
        matching_ids: list[str] = []
        if selected_id and selected_id in records and selected_id in live_ids:
            matching_ids = [selected_id]
        elif not selected_id and selected_subject:
            if selected_sender:
                matching_ids = [
                    message_id
                    for message_id, record in records.items()
                    if message_id in live_ids
                    and _normalized_sender_identity(record.get("sender")) == selected_sender
                    and _normalized_subject(record.get("subject")) == selected_subject
                ]
            if not matching_ids:
                matching_ids = [
                    message_id
                    for message_id, record in records.items()
                    if message_id in live_ids
                    and _normalized_subject(record.get("subject")) == selected_subject
                ]
        item = None
        if len(matching_ids) == 1:
            message_id = matching_ids[0]
            item = self._companion_review_item_unlocked(message_id, records[message_id])
            review_state = load_json_or_default(
                self._review_state_path,
                {"provider": "protonmail", "messages": {}},
            )
            provider_status = str(records[message_id].get("status") or "").lower()
            if message_id in (review_state.get("messages") or {}) or provider_status in {
                "applied", "provider-confirmed", "completed",
            }:
                item.update({
                    "status": "auto-handled",
                    "status_label": "Already handled",
                    "action_reason": "Provider label confirmed",
                })
        if item is None:
            ambiguous = len(matching_ids) > 1
            return {
                "found": False,
                "provider": "protonmail",
                "status": "not-in-snapshot",
                "status_label": "Not in Threadwise yet",
                "reason": (
                    "More than one synced Proton Mail message has this sender and subject, so Threadwise will not guess."
                    if ambiguous
                    else "This Proton Mail message is not in the current Threadwise sync yet."
                ),
                "subject": str(selected_context.get("subject") or ""),
                "sender": str(selected_context.get("sender") or ""),
                "understanding_state": "ready",
                "understanding_label": "Ready",
                "understanding_message": "Threadwise is ready with the current email.",
            }
        return {
            **item,
            "found": True,
            "reason": item.get("reason") or "No label suggestion was stored.",
            "details": {"write_status": None, "inbox_status": "preserved"},
            "unsubscribe": None,
            "understanding_state": "ready",
            "understanding_label": "Ready",
            "understanding_message": "Threadwise is ready with the current email.",
        }

    def _require_pending_unlocked(self, message_id: str) -> dict:
        state = self._state_unlocked()
        current = state.get("current")
        if not current or current.get("message_id") != message_id:
            raise ValueError("That Proton review item is no longer current. Refresh the queue and try again.")
        return current

    def _record_decision_unlocked(
        self,
        message_id: str,
        *,
        decision: str,
        provider_verified: bool,
        **details: object,
    ) -> None:
        state = load_json_or_default(
            self._review_state_path,
            {"provider": "protonmail", "messages": {}},
        )
        decided_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        state.setdefault("messages", {})[message_id] = {
            "decision": decision,
            "decided_at": decided_at,
            "provider_verified": provider_verified,
            "inbox_preserved": True,
            "destructive_actions": [],
            **details,
        }
        state["updated_at"] = decided_at
        write_json(self._review_state_path, state)


def render_proton_review_page(state: dict) -> str:
    current = state.get("current")
    remaining = int(state.get("remaining_count") or 0)
    completed = int(state.get("completed_count") or state.get("reviewed_count") or 0)
    options = "".join(
        f'<option value="{escape_html(item["internal_label"])}"'
        f'{" selected" if current and item["internal_label"] == current.get("suggested_internal_label") else ""}>'
        f'{escape_html(item["display_label"])}</option>'
        for item in state.get("allowed_labels") or []
    )
    if current:
        card = f"""
        <article class="message-card" data-proton-current-message="{escape_html(current['message_id'])}">
          <div class="eyebrow">Proton · Needs your review</div>
          <h2>{escape_html(current.get('subject') or '(No subject)')}</h2>
          <div class="sender">{escape_html(current.get('sender') or 'Unknown sender')}</div>
          <div class="date">{escape_html(current.get('date') or '')}</div>
          <section class="suggestion">
            <strong>{escape_html('Threadwise suggests ' + ', '.join(current.get('suggested_labels') or []) if current.get('suggested_labels') else 'Threadwise could not choose a label')}</strong>
            <div>{escape_html(current.get('reason') or 'No reason was stored.')}</div>
          </section>
          <details class="body" open>
            <summary>Full email context</summary>
            <pre>{escape_html(current.get('body') or 'No readable body was available.')}</pre>
          </details>
          <div id="action-status" class="status" role="status" aria-live="polite"></div>
          {f'<button id="apply-primary" class="action primary" type="button">Accept {escape_html((current.get("suggested_labels") or ["label"])[0])} · Next</button>' if current.get('suggested_labels') else '<button id="looks-right" class="action primary" type="button">Leave unlabeled · Next</button>'}
          {f'<button id="apply-suggested" class="action quiet" type="button">Apply all {len(current.get("suggested_labels") or [])} suggested labels · Next</button>' if len(current.get('suggested_labels') or []) > 1 else ''}
          <button id="change-label-toggle" class="action secondary" type="button">Change label</button>
          <div id="correction" class="correction" hidden>
            <label for="target-label">Choose a different label</label>
            <select id="target-label">{options}</select>
            <label for="review-note">Tell Threadwise why <span>(optional)</span></label>
            <textarea id="review-note" rows="2" placeholder="What should Threadwise remember?"></textarea>
            <button id="apply-label" class="action primary" type="button">Apply label · Next</button>
          </div>
        </article>
        """
    else:
        card = """
        <article class="message-card caught-up" data-proton-caught-up>
          <div class="eyebrow">Proton · review complete</div>
          <h2>Your Proton queue is clear</h2>
          <p>Threadwise will not re-offer emails you completed in this review.</p>
        </article>
        """

    safe_state = json.dumps({"message_id": current.get("message_id") if current else None}).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Proton Review</title>
  <style>
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; padding:clamp(12px,4vw,34px); color:#241812; font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:radial-gradient(circle at 18px 18px,rgba(36,24,18,.05) 2px,transparent 2px) 0 0/36px 36px,linear-gradient(135deg,#f7efe0,#fdfaf2 52%,#e7f3ee); }}
    main {{ width:min(880px,100%); margin:0 auto; border:2px solid #241812; border-radius:20px; overflow:hidden; background:#fff7e8; box-shadow:0 16px 40px rgba(36,24,18,.14); }}
    header,.message-card,.safety {{ padding:clamp(16px,3vw,26px); }}
    header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; border-bottom:1px solid rgba(36,24,18,.28); }}
    .brand {{ display:flex; align-items:center; gap:12px; }}
    .brand img {{ width:44px; height:44px; border:1px solid rgba(36,24,18,.34); border-radius:12px; }}
    .eyebrow {{ color:#6b6255; font-size:.72rem; font-weight:850; letter-spacing:.13em; text-transform:uppercase; }}
    h1,h2 {{ margin:5px 0 8px; line-height:1.12; }}
    h1 {{ font-size:1.45rem; }} h2 {{ font-size:1.55rem; }}
    .count {{ white-space:nowrap; border:1px solid rgba(36,24,18,.28); border-radius:999px; padding:7px 11px; background:#f1eadf; font-weight:800; }}
    .message-card {{ background:#fffdf7; }}
    .sender,.date {{ color:#6b6255; overflow-wrap:anywhere; }} .date {{ margin-top:3px; font-size:.86rem; }}
    .suggestion,.body,.correction,.safety {{ margin-top:16px; border:1px solid rgba(36,24,18,.25); border-radius:13px; background:#f5efe2; padding:14px; line-height:1.45; }}
    .suggestion strong {{ display:block; margin-bottom:5px; }}
    .body summary {{ cursor:pointer; font-weight:850; }}
    pre {{ margin:14px 0 0; white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; line-height:1.5; }}
    .correction {{ display:grid; gap:10px; background:#fff7e8; }}
    label {{ font-weight:800; }} select {{ width:100%; padding:10px 12px; border:2px solid #241812; border-radius:10px; background:#fffdf7; color:#241812; font:inherit; }}
    .action {{ width:100%; margin-top:14px; border:2px solid #241812; border-radius:11px; padding:11px 14px; color:#241812; font:inherit; font-weight:850; cursor:pointer; box-shadow:3px 3px 0 #241812; }}
    .primary {{ background:#2eb67d; }} .secondary {{ margin-top:0; background:#ebe4d7; }}
    .action:disabled {{ cursor:wait; opacity:.65; }}
    .status {{ min-height:22px; margin-top:12px; color:#0f6259; font-weight:750; }}
    .status.error {{ color:#9b2c2c; }}
    .safety {{ margin:0; border-width:1px 0 0; border-radius:0; color:#5d5342; background:#eef6f2; }}
    a {{ color:#5d5342; font-weight:800; }}
    :where(button,a,select,summary):focus-visible {{ outline:3px solid #3d6df2; outline-offset:2px; }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand"><img src="/assets/brand/threadwise-app-mark.png" alt=""><div><div class="eyebrow">Threadwise companion</div><h1>Proton review</h1><a href="/daily-dashboard">Back to daily dashboard</a></div></div>
          <div class="count"><span data-remaining-count>{remaining}</span> to review · {completed} completed</div>
    </header>
    {card}
    <aside class="safety"><strong>Label-only trial.</strong> No email will be archived, deleted, moved, or sent. “Looks right” changes only Threadwise's local review record.</aside>
  </main>
  <script>
    const current = {safe_state};
    const statusNode = document.getElementById('action-status');
    const buttons = Array.from(document.querySelectorAll('button'));
    document.getElementById('change-label-toggle')?.addEventListener('click', () => {{
      const correction = document.getElementById('correction');
      if (!correction) return;
      correction.hidden = !correction.hidden;
      document.getElementById('change-label-toggle').textContent = correction.hidden ? 'Change label' : 'Cancel label change';
    }});
    async function submit(path, payload, workingCopy) {{
      buttons.forEach((button) => button.disabled = true);
      if (statusNode) {{ statusNode.className = 'status'; statusNode.textContent = workingCopy; }}
      try {{
        const response = await fetch(path, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)}});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Threadwise could not complete this action.');
        if (statusNode) statusNode.textContent = 'Done. Loading the next Proton email…';
        window.location.reload();
      }} catch (error) {{
        buttons.forEach((button) => button.disabled = false);
        if (statusNode) {{ statusNode.className = 'status error'; statusNode.textContent = error.message; }}
      }}
    }}
    document.getElementById('looks-right')?.addEventListener('click', () => submit('/api/proton-review/acknowledge', {{message_id:current.message_id, note:document.getElementById('review-note')?.value || ''}}, 'Saving this decision…'));
    document.getElementById('apply-primary')?.addEventListener('click', () => submit('/api/proton-review/apply-primary', {{message_id:current.message_id}}, 'Applying and verifying the primary Proton label…'));
    document.getElementById('apply-suggested')?.addEventListener('click', () => submit('/api/proton-review/apply-suggested', {{message_id:current.message_id}}, 'Applying and verifying the suggested Proton label(s)…'));
    document.getElementById('apply-label')?.addEventListener('click', () => submit('/api/proton-review/apply-label', {{message_id:current.message_id, internal_label:document.getElementById('target-label').value, note:document.getElementById('review-note')?.value || ''}}, 'Applying and verifying the Proton label…'));
  </script>
</body>
</html>"""
