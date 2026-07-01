from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


MAX_NOTE_LENGTH = 20000
FOUNDER_FEEDBACK_FILENAME = "founder_feedback.jsonl"


def founder_feedback_path(storage_dir: Path) -> Path:
    return storage_dir / FOUNDER_FEEDBACK_FILENAME


def record_founder_feedback(storage_dir: Path, payload: dict) -> dict:
    note = str(payload.get("note") or "").strip()
    if not note:
        raise ValueError("Feedback note is required.")
    if len(note) > MAX_NOTE_LENGTH:
        raise ValueError(f"Feedback note must be {MAX_NOTE_LENGTH} characters or fewer.")

    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    selected_context = context.get("selected_context") if isinstance(context.get("selected_context"), dict) else {}
    selected_email = context.get("selected_email") if isinstance(context.get("selected_email"), dict) else {}

    entry = {
        "id": f"feedback-{uuid4().hex[:12]}",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "note": note,
        "source": str(payload.get("source") or "threadwise"),
        "surface": str(context.get("surface") or ""),
        "page_url": str(context.get("page_url") or ""),
        "connection_kind": str(context.get("connection_kind") or ""),
        "active_summary_filter": str(context.get("active_summary_filter") or ""),
        "selected_context": {
            "provider": str(selected_context.get("provider") or ""),
            "message_id": str(selected_context.get("message_id") or ""),
            "thread_id": str(selected_context.get("thread_id") or ""),
            "subject": str(selected_context.get("subject") or ""),
            "sender": str(selected_context.get("sender") or ""),
        },
        "selected_email": {
            "found": bool(selected_email.get("found")),
            "status": str(selected_email.get("status") or ""),
            "status_label": str(selected_email.get("status_label") or ""),
            "classification": str(selected_email.get("classification") or ""),
            "unsubscribe_available": bool(selected_email.get("unsubscribe_available")),
        },
    }

    path = founder_feedback_path(storage_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def load_founder_feedback(storage_dir: Path) -> list[dict]:
    path = founder_feedback_path(storage_dir)
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entries.append(json.loads(line))
    return entries
