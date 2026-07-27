from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import load_json_or_default, write_json
from src.teachable_rule_memory import TeachableRule


BLOCKED_AUTOMATIC_RULE_LABELS = {"promotions", "spam-low-value", "suspicious"}


def memory_path(storage_dir: Path) -> Path:
    return storage_dir / "proton_feedback_memory.json"


def load_memory(storage_dir: Path) -> dict:
    payload = load_json_or_default(memory_path(storage_dir), {})
    payload.setdefault("provider", "protonmail")
    payload.setdefault("rules", [])
    payload.setdefault("feedback", [])
    return payload


def load_rules(storage_dir: Path) -> list[TeachableRule]:
    return [TeachableRule.from_dict(rule) for rule in load_memory(storage_dir)["rules"]]


def save_feedback_rule(
    storage_dir: Path,
    *,
    message_id: str,
    sender: str,
    subject: str,
    note: str,
    internal_label: str,
) -> dict:
    note = " ".join(str(note or "").split())[:500]
    if not note:
        return {"status": "ignored", "reason": "empty-note"}
    if internal_label not in CANONICAL_LABEL_ORDER:
        return {"status": "ignored", "reason": "invalid-label"}
    if any(phrase in note.lower() for phrase in ("don't care", "dont care", "do not care", "no feedback")):
        payload = load_memory(storage_dir)
        rule_id = f"proton-feedback-{message_id}"
        payload["rules"] = [saved for saved in payload["rules"] if saved.get("id") != rule_id]
        payload["feedback"] = [entry for entry in payload["feedback"] if entry.get("message_id") != message_id]
        payload["feedback"].append({"message_id": message_id, "note": note, "status": "recorded-user-declined"})
        payload["updated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        write_json(memory_path(storage_dir), payload)
        return {"status": "recorded", "reason": "user-declined-feedback"}
    if internal_label in BLOCKED_AUTOMATIC_RULE_LABELS:
        payload = load_memory(storage_dir)
        rule_id = f"proton-feedback-{message_id}"
        payload["rules"] = [saved for saved in payload["rules"] if saved.get("id") != rule_id]
        payload["feedback"] = [entry for entry in payload["feedback"] if entry.get("message_id") != message_id]
        payload["feedback"].append(
            {
                "message_id": message_id,
                "sender": sender,
                "subject": subject,
                "note": note,
                "internal_label": internal_label,
                "label": gmail_label_name(internal_label),
                "status": "recorded-needs-review",
            }
        )
        payload["updated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        write_json(memory_path(storage_dir), payload)
        return {"status": "recorded-needs-review", "reason": "safety-sensitive-label"}

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = load_memory(storage_dir)
    rule_id = f"proton-feedback-{message_id}"
    rule = TeachableRule(
        id=rule_id,
        instruction=note,
        label=internal_label,
        terms=(),
        keep_visible=internal_label in {"job-related", "personal", "account-security", "financial-account", "reply-needed"},
        created_at=now,
        providers=("protonmail",),
        enabled=True,
        source_examples=({"sender": sender, "subject": subject},),
        scope="sender",
        match_mode="sender",
        provenance={
            "source": "proton-review-feedback",
            "message_id": message_id,
            "display_label": gmail_label_name(internal_label),
        },
        updated_at=now,
    )
    payload["rules"] = [saved for saved in payload["rules"] if saved.get("id") != rule_id]
    payload["rules"].append(rule.to_dict())
    payload["feedback"] = [entry for entry in payload["feedback"] if entry.get("message_id") != message_id]
    payload["feedback"].append(
        {
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "note": note,
            "internal_label": internal_label,
            "label": gmail_label_name(internal_label),
            "status": "accepted-as-sender-rule",
            "created_at": now,
        }
    )
    payload["updated_at"] = now
    write_json(memory_path(storage_dir), payload)
    return {"status": "accepted-as-sender-rule", "rule_id": rule_id, "label": gmail_label_name(internal_label)}


def migrate_review_feedback(storage_dir: Path, review_state_path: Path) -> dict:
    """Backfill rules from completed Proton notes without touching the provider."""
    review_state = load_json_or_default(review_state_path, {})
    items_by_id: dict[str, dict] = {}
    batches_dir = storage_dir / "batches"
    if batches_dir.exists():
        for batch_path in batches_dir.glob("*.json"):
            batch = load_json_or_default(batch_path, {})
            if batch.get("provider") != "protonmail":
                continue
            raw_by_id = {str(message.get("id")): message for message in batch.get("raw_messages", [])}
            for item in batch.get("items", []):
                message_id = str(item.get("message_id") or "")
                raw = raw_by_id.get(message_id, {})
                items_by_id[message_id] = {
                    "sender": str(raw.get("sender") or item.get("sender") or ""),
                    "subject": str(raw.get("subject") or item.get("subject") or ""),
                }
    migrated = 0
    for message_id, decision in (review_state.get("messages") or {}).items():
        note = str(decision.get("note") or "").strip()
        internal_label = str(decision.get("internal_label") or "")
        context = items_by_id.get(message_id, {})
        if not note or not internal_label or not context.get("sender"):
            continue
        result = save_feedback_rule(
            storage_dir,
            message_id=message_id,
            sender=context["sender"],
            subject=context.get("subject", ""),
            note=note,
            internal_label=internal_label,
        )
        if result.get("status") == "accepted-as-sender-rule":
            migrated += 1
    return {"migrated_count": migrated, "memory_path": str(memory_path(storage_dir))}
