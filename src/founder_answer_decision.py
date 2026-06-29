from datetime import UTC, datetime
from pathlib import Path
import re

from src.local_artifacts import founder_answer_decision_path, memory_proposals_path, write_json
from src.memory_proposal_store import MemoryProposal, MemoryProposalStore


def build_founder_answer_decision(
    *,
    founder_answer_pack: dict,
    question_id: str,
    response_text: str,
) -> dict:
    question = _find_question(founder_answer_pack, question_id)
    answer_options = list(question.get("answer_options", []))
    matched = _match_answer_option(answer_options, response_text)
    proposals = list(matched.get("proposal_drafts", [])) if matched else []
    projection = dict((matched or {}).get("projection", {}))
    return {
        "decision_id": _decision_id(question_id),
        "generated_at": _now_iso(),
        "artifact_type": "founder-answer-decision",
        "question_id": question_id,
        "theme": question.get("theme", ""),
        "title": question.get("title", ""),
        "prompt": question.get("prompt", ""),
        "response_text": response_text.strip(),
        "matched_answer_key": (matched or {}).get("answer_key", ""),
        "matched_answer_description": (matched or {}).get("description", ""),
        "match_confidence": _match_confidence(matched, response_text),
        "proposal_drafts": proposals,
        "projection": projection,
    }


def save_founder_answer_decision(
    output_storage_dir: Path,
    *,
    founder_answer_pack: dict,
    question_id: str,
    response_text: str,
) -> dict:
    decision = build_founder_answer_decision(
        founder_answer_pack=founder_answer_pack,
        question_id=question_id,
        response_text=response_text,
    )
    store = MemoryProposalStore(memory_proposals_path(output_storage_dir))
    saved_proposal_ids = []
    for payload in decision.get("proposal_drafts", []):
        proposal_payload = _normalize_proposal_payload(payload)
        proposal = MemoryProposal.from_dict(proposal_payload)
        store.save_proposal(proposal)
        saved_proposal_ids.append(proposal.id)
    decision["saved_proposal_ids"] = saved_proposal_ids
    path = founder_answer_decision_path(output_storage_dir, decision["decision_id"])
    write_json(path, decision)
    decision["decision_path"] = str(path)
    return decision


def _find_question(founder_answer_pack: dict, question_id: str) -> dict:
    for question in founder_answer_pack.get("questions", []):
        if question.get("question_id") == question_id:
            return question
    raise KeyError(f"Unknown founder question: {question_id}")


def _match_answer_option(answer_options: list[dict], response_text: str) -> dict | None:
    if not answer_options:
        return None
    scored = [
        (_score_answer_option(option, response_text), option)
        for option in answer_options
    ]
    scored.sort(key=lambda item: (-item[0], item[1].get("answer_key", "")))
    if scored[0][0] <= 0:
        return answer_options[0]
    return scored[0][1]


def _score_answer_option(option: dict, response_text: str) -> int:
    text = response_text.lower()
    answer_key = option.get("answer_key", "")
    score = 0
    if answer_key == "low_value_default" and _contains_any(text, ("promo", "promotion", "low value", "spam", "deprioritize", "don't want", "dont want", "hide")):
        score += 3
    if answer_key == "keep_visible" and _contains_any(text, ("keep visible", "show", "keep these", "don't hide", "dont hide")):
        score += 3
    if answer_key == "always_visible" and _contains_any(text, ("always visible", "keep visible", "important", "security")):
        score += 3
    if answer_key == "known_service_low_priority" and _contains_any(text, ("known service", "lower priority", "not urgent", "if familiar")):
        score += 3
    if answer_key == "calendar_event_default" and _contains_any(text, ("calendar", "event", "appointment")):
        score += 3
    if answer_key == "personal_default" and _contains_any(text, ("personal", "keep these", "message", "person-to-person", "direct message")):
        score += 3
    if answer_key == "shopping_order_default" and _contains_any(text, ("shopping", "order", "purchase", "booking", "confirmation")):
        score += 3
    if answer_key == "receipt_billing_default" and _contains_any(text, ("receipt", "invoice", "billing", "purchase", "bought", "kauf")):
        score += 3
    if answer_key == "sender_allowlist_only" and _contains_any(text, ("allowlist", "specific senders", "only some", "exceptions")):
        score += 3
    if answer_key == "low_value_update_default" and _contains_any(text, ("terms", "policy", "low value", "newsletter", "update")):
        score += 3
    if answer_key == "keep_account_related_visible" and _contains_any(text, ("account", "active use", "keep visible")):
        score += 3
    if answer_key == "map_existing_label" and _contains_any(text, ("map", "label", "existing", "use")):
        score += 2
    if answer_key == "leave_unresolved" and _contains_any(text, ("unclear", "don't know", "dont know", "leave unresolved")):
        score += 2
    description_words = re.findall(r"[a-z]{4,}", option.get("description", "").lower())
    score += sum(1 for word in description_words if word in text)
    return score


def _match_confidence(matched: dict | None, response_text: str) -> str:
    if matched is None:
        return "low"
    score = _score_answer_option(matched, response_text)
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _normalize_proposal_payload(payload: dict) -> dict:
    if "id" in payload:
        return payload
    return {
        "id": payload.get("proposal_id", ""),
        "provider": payload.get("provider", ""),
        "account_id": payload.get("account_id", ""),
        "source_batch_id": payload.get("source_batch_id", ""),
        "source_message_ids": list(payload.get("source_message_ids", [])),
        "scope": payload.get("scope", ""),
        "label": payload.get("label", ""),
        "instruction": payload.get("instruction", ""),
        "terms": list(payload.get("terms", [])),
        "source_examples": list(payload.get("source_examples", [])),
        "explanation": payload.get("explanation", ""),
        "preview": dict(payload.get("preview", {"match_count": payload.get("preview_match_count", 0), "matches": []})),
        "status": payload.get("status", "pending"),
        "created_at": payload.get("created_at", ""),
        "updated_at": payload.get("updated_at", ""),
        "approved_rule_id": payload.get("approved_rule_id", ""),
        "review_notes": payload.get("review_notes", ""),
    }


def _decision_id(question_id: str) -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    fragment = re.sub(r"[^a-z0-9]+", "-", question_id.lower()).strip("-")
    return f"{fragment}-{timestamp}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
