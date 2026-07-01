from datetime import UTC, datetime
from pathlib import Path

from src.attention_feedback import load_attention_feedback
from src.local_artifacts import load_json, load_json_or_default, write_json
from src.sender_utils import normalized_sender_email


ATTENTION_RULE_PROPOSAL_SCHEMA_VERSION = 1
ATTENTION_RULE_SCHEMA_VERSION = 1
ATTENTION_RULE_APPLICATION_MODES = {
    "current_email_only",
    "future_only",
    "matching_existing",
}


def attention_rule_proposals_path(storage_dir: Path) -> Path:
    return storage_dir / "attention_rule_proposals.json"


def attention_rules_path(storage_dir: Path) -> Path:
    return storage_dir / "attention_rules.json"


def load_attention_rule_proposals(storage_dir: Path) -> dict:
    payload = load_json_or_default(attention_rule_proposals_path(storage_dir), {})
    if not isinstance(payload, dict) or not payload:
        return {
            "schema_version": ATTENTION_RULE_PROPOSAL_SCHEMA_VERSION,
            "updated_at": "",
            "proposals": {},
        }
    payload.setdefault("schema_version", ATTENTION_RULE_PROPOSAL_SCHEMA_VERSION)
    payload.setdefault("updated_at", "")
    payload.setdefault("proposals", {})
    return payload


def load_attention_rules(storage_dir: Path) -> dict:
    payload = load_json_or_default(attention_rules_path(storage_dir), {})
    if not isinstance(payload, dict) or not payload:
        return {
            "schema_version": ATTENTION_RULE_SCHEMA_VERSION,
            "updated_at": "",
            "rules": [],
        }
    payload.setdefault("schema_version", ATTENTION_RULE_SCHEMA_VERSION)
    payload.setdefault("updated_at", "")
    payload.setdefault("rules", [])
    return payload


def build_attention_rule_proposal(storage_dir: Path, message_id: str, *, scope: str = "sender") -> dict:
    feedback = load_attention_feedback(storage_dir).get("entries", {}).get(message_id)
    if not feedback:
        raise ValueError(f"No attention feedback found for message: {message_id}")
    if scope != "sender":
        raise ValueError("MVP+2 attention rule proposals support sender scope only.")

    sender_address = normalized_sender_email(feedback.get("sender") or "")
    if not sender_address:
        raise ValueError("Attention rule proposal requires a sender address.")

    priority, priority_reason = infer_attention_priority(feedback)
    proposal_id = f"attention-proposal-{message_id}"
    preview = preview_attention_rule(storage_dir, sender_address=sender_address, attention_priority=priority)
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    proposal = {
        "id": proposal_id,
        "status": "pending",
        "rule_type": "attention_promotion",
        "scope": "sender",
        "condition": {
            "sender_address": sender_address,
            "category_hint": feedback.get("corrected_category", ""),
        },
        "attention_priority": priority,
        "priority_reason": priority_reason,
        "auto_promote": True,
        "gmail_mutation": "none",
        "source_feedback": {
            "message_id": feedback.get("message_id", ""),
            "thread_id": feedback.get("thread_id", ""),
            "latest_action": feedback.get("latest_action", ""),
            "note": feedback.get("note", ""),
            "corrected_reason": feedback.get("corrected_reason", ""),
            "corrected_category": feedback.get("corrected_category", ""),
        },
        "application_options": sorted(ATTENTION_RULE_APPLICATION_MODES),
        "preview": preview,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    proposals = load_attention_rule_proposals(storage_dir)
    proposals["proposals"][proposal_id] = proposal
    proposals["updated_at"] = timestamp
    write_json(attention_rule_proposals_path(storage_dir), proposals)
    return proposal


def approve_attention_rule_proposal(storage_dir: Path, proposal_id: str, *, application_mode: str) -> dict:
    if application_mode not in ATTENTION_RULE_APPLICATION_MODES:
        raise ValueError(f"Unsupported attention rule application mode: {application_mode}")
    proposals = load_attention_rule_proposals(storage_dir)
    proposal = dict(proposals.get("proposals", {}).get(proposal_id) or {})
    if not proposal:
        raise ValueError(f"Attention rule proposal not found: {proposal_id}")

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    proposal["status"] = "approved"
    proposal["reviewed_at"] = timestamp
    proposal["application_mode"] = application_mode
    proposal["approved_rule_id"] = ""
    proposal["applied_to_message_ids"] = []
    if application_mode in {"future_only", "matching_existing"}:
        rule = rule_from_proposal(proposal, timestamp)
        rules = load_attention_rules(storage_dir)
        rules["rules"] = [existing for existing in rules["rules"] if existing.get("id") != rule["id"]]
        rules["rules"].append(rule)
        rules["updated_at"] = timestamp
        write_json(attention_rules_path(storage_dir), rules)
        proposal["approved_rule_id"] = rule["id"]
    if application_mode == "matching_existing":
        proposal["applied_to_message_ids"] = [
            item.get("message_id", "")
            for item in proposal.get("preview", {}).get("matches", [])
            if item.get("message_id")
        ]
    proposal["gmail_mutation"] = "none"
    proposals["proposals"][proposal_id] = proposal
    proposals["updated_at"] = timestamp
    write_json(attention_rule_proposals_path(storage_dir), proposals)
    return proposal


def reject_attention_rule_proposal(storage_dir: Path, proposal_id: str, *, notes: str = "") -> dict:
    proposals = load_attention_rule_proposals(storage_dir)
    proposal = dict(proposals.get("proposals", {}).get(proposal_id) or {})
    if not proposal:
        raise ValueError(f"Attention rule proposal not found: {proposal_id}")
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    proposal["status"] = "rejected"
    proposal["reviewed_at"] = timestamp
    proposal["review_notes"] = notes
    proposals["proposals"][proposal_id] = proposal
    proposals["updated_at"] = timestamp
    write_json(attention_rule_proposals_path(storage_dir), proposals)
    return proposal


def preview_attention_rule(storage_dir: Path, *, sender_address: str, attention_priority: str) -> dict:
    matches = []
    for item in stored_gmail_items(storage_dir):
        if normalized_sender_email(item.get("sender") or "") != sender_address:
            continue
        matches.append(
            {
                "message_id": item.get("message_id", ""),
                "thread_id": item.get("thread_id", ""),
                "batch_id": item.get("batch_id", ""),
                "subject": item.get("subject", ""),
                "sender": item.get("sender", ""),
                "attention_priority_after": attention_priority,
                "gmail_mutation": "none",
            }
        )
    return {
        "match_count": len(matches),
        "matches": matches,
    }


def infer_attention_priority(feedback: dict) -> tuple[str, str]:
    text = " ".join(
        str(feedback.get(key) or "").lower()
        for key in ("subject", "note", "corrected_reason", "corrected_category")
    )
    concrete_terms = (
        "today",
        "tomorrow",
        "tonight",
        "due",
        "deadline",
        "closes",
        "flight",
        "account closure",
        "suspension",
        "service interruption",
    )
    if any(term in text for term in concrete_terms):
        return "needs_attention_now", "concrete_time_or_consequence_evidence"
    return "possible_attention", "preference_signal_without_concrete_time_or_consequence"


def rule_from_proposal(proposal: dict, timestamp: str) -> dict:
    return {
        "id": f"attention-rule-{proposal['id']}",
        "rule_type": "attention_promotion",
        "scope": proposal.get("scope", "sender"),
        "condition": dict(proposal.get("condition") or {}),
        "attention_priority": proposal.get("attention_priority", "possible_attention"),
        "priority_reason": proposal.get("priority_reason", ""),
        "auto_promote": True,
        "gmail_mutation": "none",
        "source_proposal_id": proposal.get("id", ""),
        "created_at": timestamp,
    }


def stored_gmail_items(storage_dir: Path) -> list[dict]:
    items = []
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return items
    for batch_path in sorted(batches_dir.glob("*.json")):
        batch = load_json(batch_path)
        for item in batch.get("items", []):
            enriched = dict(item)
            enriched.setdefault("batch_id", batch.get("batch_id", ""))
            items.append(enriched)
    return items
