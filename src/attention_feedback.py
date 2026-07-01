from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json


ATTENTION_FEEDBACK_SCHEMA_VERSION = 1
ATTENTION_FEEDBACK_ACTIONS = {
    "good_catch",
    "not_attention",
    "wrong_reason",
    "mark_needs_attention",
}


def attention_feedback_path(storage_dir: Path) -> Path:
    return storage_dir / "attention_feedback.json"


def load_attention_feedback(storage_dir: Path) -> dict:
    payload = load_json_or_default(attention_feedback_path(storage_dir), {})
    if not isinstance(payload, dict):
        return empty_attention_feedback()
    return {
        "schema_version": payload.get("schema_version", ATTENTION_FEEDBACK_SCHEMA_VERSION),
        "updated_at": payload.get("updated_at", ""),
        "entries": payload.get("entries") if isinstance(payload.get("entries"), dict) else {},
    }


def record_attention_feedback(storage_dir: Path, payload: dict, *, now: datetime | None = None) -> dict:
    action = (payload.get("action") or "").strip()
    if action not in ATTENTION_FEEDBACK_ACTIONS:
        raise ValueError(f"Unsupported attention feedback action: {action}")
    message_id = (payload.get("message_id") or "").strip()
    thread_id = (payload.get("thread_id") or "").strip()
    if not message_id and not thread_id:
        raise ValueError("Attention feedback requires a message_id or thread_id.")

    timestamp = (now or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    feedback = load_attention_feedback(storage_dir)
    entries = feedback["entries"]
    key = message_id or f"thread:{thread_id}"
    existing = entries.get(key, {})
    event = {
        "action": action,
        "created_at": timestamp,
        "note": (payload.get("note") or "").strip(),
        "corrected_reason": (payload.get("corrected_reason") or "").strip(),
        "corrected_category": (payload.get("corrected_category") or "").strip(),
        "source": payload.get("source") or "daily_dashboard",
        "gmail_mutation": "none",
        "creates_broader_rule": False,
    }
    events = list(existing.get("events") or [])
    events.append(event)
    entry = {
        "message_id": message_id,
        "thread_id": thread_id,
        "batch_id": (payload.get("batch_id") or existing.get("batch_id") or "").strip(),
        "subject": (payload.get("subject") or existing.get("subject") or "").strip(),
        "sender": (payload.get("sender") or existing.get("sender") or "").strip(),
        "latest_action": action,
        "feedback_state": action,
        "note": event["note"],
        "corrected_reason": event["corrected_reason"],
        "corrected_category": event["corrected_category"],
        "dismissed": action == "not_attention",
        "manual_attention": action == "mark_needs_attention",
        "positive_signal": action == "good_catch",
        "creates_broader_rule": False,
        "gmail_mutation": "none",
        "created_at": existing.get("created_at") or timestamp,
        "updated_at": timestamp,
        "events": events,
    }
    entries[key] = entry
    feedback["schema_version"] = ATTENTION_FEEDBACK_SCHEMA_VERSION
    feedback["updated_at"] = timestamp
    feedback["entries"] = entries
    write_json(attention_feedback_path(storage_dir), feedback)
    return entry


def empty_attention_feedback() -> dict:
    return {
        "schema_version": ATTENTION_FEEDBACK_SCHEMA_VERSION,
        "updated_at": "",
        "entries": {},
    }
