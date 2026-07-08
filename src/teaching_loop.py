import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_companion_state import find_matching_item
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import load_json, memory_proposals_path, teachable_rules_path
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal, load_storage_items
from src.sender_utils import normalized_sender_email
from src.teaching_exclusions import (
    count_teaching_exclusions_for_proposal,
    filter_excluded_preview_matches,
    save_teaching_exclusion,
)
from src.teachable_rule_memory import TeachableRuleMemory


VALID_TEACHING_APPLY_MODES = {"current-only", "matching-existing", "save-future-rule", "future-only", "apply-included"}
DEFAULT_TEACHING_INTENT_MODEL = "gpt-4.1-mini"


class OpenAITeachingIntentClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAITeachingIntentClient | None":
        api_key = os.getenv("EMAIL_AGENT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return cls(api_key=api_key, model=model or os.getenv("THREADWISE_TEACHING_MODEL") or DEFAULT_TEACHING_INTENT_MODEL)

    def interpret(self, payload: dict) -> dict:
        prompt = (
            "You interpret founder correction notes for an email labeling tool.\n"
            "Return strict JSON with keys: target_label, semantic_pattern, cross_sender, confidence, rationale.\n"
            "target_label must be one of: "
            + ", ".join(CANONICAL_LABEL_ORDER)
            + ".\n"
            "Choose the label the founder wants after reading the current email context and complaint.\n"
            "If the founder is rejecting existing wrong labels, do not echo them back as the desired target.\n"
            "semantic_pattern should be a short plain-English message family description.\n"
            "cross_sender must be true only if the founder intent clearly spans multiple senders.\n"
            "If uncertain, still pick the best label and set confidence to low."
        )
        response_payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(response_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:
            return {}
        except urllib.error.URLError:
            return {}
        content = (((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if not content:
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


def build_sidebar_teach_preview(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
) -> dict:
    current = load_selected_storage_item(storage_dir, selected_context)
    intent = interpret_teaching_intent(current=current, target_label=target_label, note=note, scope=scope)
    target_label = intent["target_label"]
    semantic_rule = build_semantic_future_rule(
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        intent=intent,
    )
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        semantic_rule=semantic_rule,
    )
    preview = proposal.preview
    proposal_payload = proposal.to_dict()
    preview_matches = filter_excluded_preview_matches(storage_dir, proposal_payload, preview.get("matches", []))
    affected_existing = [
        match for match in preview_matches
        if match.get("message_id") != current["message_id"]
    ]
    normalized_existing = [
        {
            **match,
            "labels_after": [target_label],
        }
        for match in affected_existing
    ]
    similar_candidates = build_similar_candidate_preview(
        storage_dir,
        current=current,
        target_label=target_label,
        exact_matches=normalized_existing,
    )
    target_label_name = gmail_label_name(target_label)
    current_labels = list(current.get("final_labels") or current.get("applied_labels") or [])
    current_label_name = gmail_label_name(current_labels[0]) if current_labels else "Uncategorized"
    structured_rule = {
        "scope": semantic_rule["scope"],
        "rule_type": semantic_rule["rule_type"],
        "sender": semantic_rule["sender"],
        "semantic_pattern": semantic_rule["semantic_pattern"],
        "from_label": current_label_name,
        "to_label": target_label_name,
        "target_label": target_label,
        "matching_basis": semantic_rule["matching_basis"],
        "applies_to_existing_count": len(affected_existing),
    }
    return {
        "acknowledgment": build_teach_acknowledgment(
            current=current,
            target_label=target_label,
            note=note,
            affected_existing_count=len(affected_existing),
            scope=scope,
        ),
        "selected_message_id": current["message_id"],
        "selected_batch_id": current["batch_id"],
        "selected_account_id": current.get("account_id") or "",
        "selected_subject": current.get("subject") or "",
        "selected_sender": current.get("sender") or "",
        "selected_label_before": current_labels,
        "selected_label_after": [target_label],
        "current_label_name": current_label_name,
        "target_label_name": target_label_name,
        "plain_english_rule": semantic_rule["plain_english_rule"],
        "rule_type": semantic_rule["rule_type"],
        "rule_type_label": semantic_rule["rule_type_label"],
        "rule_confidence": semantic_rule["rule_confidence"],
        "rule_confidence_label": semantic_rule["rule_confidence_label"],
        "clarifying_question": semantic_rule["clarifying_question"],
        "structured_rule": structured_rule,
        "semantic_rule": semantic_rule,
        "proposal": proposal.to_dict(),
        "impact": {
            "current_message_will_change": True,
            "matching_existing_count": len(affected_existing),
            "matching_existing_examples": normalized_existing[:5],
            "similar_candidate_count": similar_candidates["similar_candidate_count"],
            "similar_candidate_examples": similar_candidates["similar_candidate_examples"],
            "similar_candidate_groups": similar_candidates["similar_candidate_groups"],
            "broader_rule_candidates": similar_candidates["broader_rule_candidates"],
            "scope": scope,
        },
        "options": [
            {"id": "current-only", "label": "Fix this email"},
            {"id": "matching-existing", "label": "Also apply broader rule"},
            {"id": "save-future-rule", "label": "Teach future rule"},
            {"id": "refine", "label": "Keep discussing"},
        ],
    }


def apply_sidebar_teaching(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
    mode: str,
) -> dict:
    if mode not in VALID_TEACHING_APPLY_MODES:
        raise ValueError("Unsupported apply mode.")
    intent = interpret_teaching_intent(
        current=load_selected_storage_item(storage_dir, selected_context),
        target_label=target_label,
        note=note,
        scope=scope,
    )
    target_label = intent["target_label"]

    current = load_selected_storage_item(storage_dir, selected_context)
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        semantic_rule=build_semantic_future_rule(current=current, target_label=target_label, note=note, scope=scope, intent=intent),
    )
    preview_matches = filter_excluded_preview_matches(storage_dir, proposal.to_dict(), proposal.preview.get("matches", []))

    current_changed = False
    if mode in {"current-only", "matching-existing", "future-only", "apply-included"}:
        current_changed = apply_label_to_message(
            storage_dir,
            batch_id=current["batch_id"],
            message_id=current["message_id"],
            label=target_label,
            note=note,
            review_action="sidebar-current-only" if mode == "current-only" else f"sidebar-{mode}",
        )

    matched_existing_count = 0
    proposal_record = None
    future_rule_saved = False
    if mode in {"save-future-rule", "future-only", "apply-included"}:
        store = MemoryProposalStore(memory_proposals_path(storage_dir))
        store.save_proposal(proposal)
        memory = TeachableRuleMemory(teachable_rules_path(storage_dir))
        proposal_record = store.review_proposal(proposal.id, "approved", rules_memory=memory)
        future_rule_saved = True
    if mode in {"matching-existing", "apply-included"}:
        matched_existing_count = apply_label_to_preview_matches(
            storage_dir,
            preview_matches,
            selected_message_id=current["message_id"],
            label=target_label,
            note=note,
            review_action="sidebar-matching-existing" if mode == "matching-existing" else "sidebar-apply-included",
        )
    exceptions_saved_count = count_teaching_exclusions_for_proposal(storage_dir, proposal.to_dict())

    return {
        "acknowledgment": build_apply_acknowledgment(
            current=current,
            target_label=target_label,
            mode=mode,
            matched_existing_count=matched_existing_count,
            exceptions_saved_count=exceptions_saved_count,
            future_rule_saved=future_rule_saved,
        ),
        "mode": mode,
        "current_changed": current_changed,
        "matched_existing_count": matched_existing_count,
        "exceptions_saved_count": exceptions_saved_count,
        "future_rule_saved": future_rule_saved,
        "proposal": proposal_record.to_dict() if proposal_record else None,
        "current": current,
        "preview_matches": preview_matches,
    }


def exclude_sidebar_teaching_match(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
    excluded_message_id: str,
    reason: str = "",
) -> dict:
    current = load_selected_storage_item(storage_dir, selected_context)
    intent = interpret_teaching_intent(current=current, target_label=target_label, note=note, scope=scope)
    target_label = intent["target_label"]
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        semantic_rule=build_semantic_future_rule(current=current, target_label=target_label, note=note, scope=scope, intent=intent),
    )
    entry = save_teaching_exclusion(
        storage_dir,
        proposal=proposal.to_dict(),
        message_id=excluded_message_id,
        reason=reason,
    )
    remaining_matches = filter_excluded_preview_matches(storage_dir, proposal.to_dict(), proposal.preview.get("matches", []))
    amendment = build_rule_amendment_proposal(
        current=current,
        proposal=proposal.to_dict(),
        excluded_message_id=excluded_message_id,
        reason=reason,
    )
    return {
        "acknowledgment": "Exception saved. This rule will not apply to this email/pattern later.",
        "excluded_message_id": excluded_message_id,
        "exclusion": entry,
        "proposal": proposal.to_dict(),
        "amendment_proposal": amendment,
        "remaining_matching_count": len(
            [
                match
                for match in remaining_matches
                if match.get("message_id") != current["message_id"]
            ]
        ),
    }


def apply_rule_amendment_decision(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
    amendment: dict,
    decision: str,
) -> dict:
    if decision not in {"accept", "reject"}:
        raise ValueError("Rule amendment decision must be accept or reject.")
    preview = build_sidebar_teach_preview(
        storage_dir,
        selected_context=selected_context,
        target_label=target_label,
        note=note,
        scope=scope,
    )
    if decision == "reject":
        preview["amendment_proposal"] = {
            **dict(amendment or {}),
            "status": "rejected",
        }
        return {
            "amendment_status": "rejected",
            "preview": preview,
            "note": note,
            "changed_matching_count": 0,
        }

    amended_note = (amendment or {}).get("amended_note") or note
    amended_preview = build_sidebar_teach_preview(
        storage_dir,
        selected_context=selected_context,
        target_label=target_label,
        note=amended_note,
        scope=scope,
    )
    amended_preview["plain_english_rule"] = (amendment or {}).get("plain_english_rule") or amended_preview["plain_english_rule"]
    amended_preview["amendment_proposal"] = {
        **dict(amendment or {}),
        "status": "accepted",
    }
    return {
        "amendment_status": "accepted",
        "preview": amended_preview,
        "note": amended_note,
        "changed_matching_count": preview["impact"]["matching_existing_count"] - amended_preview["impact"]["matching_existing_count"],
    }


def build_rule_amendment_proposal(
    *,
    current: dict,
    proposal: dict,
    excluded_message_id: str,
    reason: str,
) -> dict:
    reason_text = " ".join(str(reason or "").strip().split())
    base_rule = proposal.get("preview", {}).get("rule", {}).get("instruction") or proposal.get("instruction", "")
    base_rule = base_rule or "the pending rule"
    if reason_text:
        boundary = _boundary_from_exclusion_reason(reason_text)
        plain_rule = f"{base_rule} except {boundary}."
        return {
            "status": "proposed",
            "reason": reason_text,
            "excluded_message_id": excluded_message_id,
            "plain_english_rule": plain_rule,
            "amended_note": f"{proposal.get('explanation', '').strip()} Boundary: exclude {boundary}.",
            "clarifying_question": "",
            "requires_confirmation": True,
        }
    return {
        "status": "needs-clarification",
        "reason": "",
        "excluded_message_id": excluded_message_id,
        "plain_english_rule": "",
        "amended_note": proposal.get("explanation", ""),
        "clarifying_question": "Should this exclusion stay exact, or should Threadwise narrow the future rule around a broader pattern?",
        "requires_confirmation": True,
    }


def load_selected_storage_item(storage_dir: Path, selected_context: dict) -> dict:
    matched = find_matching_item(storage_dir, selected_context)
    if matched is None:
        raise ValueError("Selected Gmail message is not in the current local snapshot.")
    item = dict(matched["item"])
    item["batch_id"] = matched["batch"]["batch_id"]
    item["provider"] = matched["batch"].get("provider", "gmail")
    item["account_id"] = matched["batch"].get("account_id", "")
    return item


def build_semantic_future_rule(*, current: dict, target_label: str, note: str, scope: str, intent: dict | None = None) -> dict:
    label_name = gmail_label_name(target_label)
    sender = normalized_sender_email(current.get("sender") or "") or current.get("sender") or "this sender"
    sender_name = _display_sender(current.get("sender") or "") or sender
    semantic_pattern = infer_semantic_pattern(current, note, target_label, intent=intent)
    cross_sender = semantic_pattern["cross_sender"]
    if semantic_pattern["name"]:
        subject = semantic_pattern["name"]
        if cross_sender:
            plain_rule = f"Treat {subject} as {label_name}."
            rule_type = "cross-sender-semantic"
            rule_type_label = "Cross-sender semantic rule"
            matching_basis = ["message meaning", "founder note", "stored Threadwise data"]
        else:
            plain_rule = f"Treat {subject} from {sender_name} as {label_name}."
            rule_type = "sender-semantic"
            rule_type_label = "Sender + semantic rule"
            matching_basis = ["sender", "message meaning", "founder note", "stored Threadwise data"]
    else:
        plain_rule = f"Treat future messages from {sender} as {label_name}."
        rule_type = "sender"
        rule_type_label = "Sender rule"
        matching_basis = ["sender", "stored Threadwise data"]
    confidence = "tentative" if not semantic_pattern["has_strong_signal"] else "medium"
    clarifying_question = ""
    if not semantic_pattern["has_strong_signal"] and note:
        clarifying_question = f"Should this apply to all future messages from {sender_name}, or only a narrower kind of message?"
    return {
        "scope": scope,
        "sender": sender,
        "semantic_pattern": semantic_pattern["name"],
        "plain_english_rule": plain_rule,
        "rule_type": rule_type,
        "rule_type_label": rule_type_label,
        "rule_confidence": confidence,
        "rule_confidence_label": "Tentative future rule" if confidence == "tentative" else "Future rule",
        "clarifying_question": clarifying_question,
        "matching_basis": matching_basis,
    }


def infer_semantic_pattern(current: dict, note: str, target_label: str, intent: dict | None = None) -> dict:
    if intent and intent.get("semantic_pattern"):
        return {
            "name": str(intent.get("semantic_pattern") or "").strip(),
            "cross_sender": bool(intent.get("cross_sender")),
            "has_strong_signal": str(intent.get("confidence") or "").lower() in {"medium", "high"},
        }
    text = _semantic_text(current, note)
    if target_label == "spam-low-value" and any(term in text for term in ("phishing", "phish", "scam", "suspicious", "fake")):
        return {
            "name": "payment or account notices that look suspicious",
            "cross_sender": True,
            "has_strong_signal": True,
        }
    label_patterns = {
        "account-security": "account, security, or statement notices",
        "financial-account": "financial account notices",
        "receipt-billing": "billing, receipt, or payment notices",
        "job-related": "job, recruiter, or interview emails",
        "travel": "travel and booking emails",
        "newsletter": "newsletter or digest emails",
        "promotions": "marketing or promotional emails",
        "spam-low-value": "low-value or suspicious emails",
    }
    if target_label in label_patterns:
        return {
            "name": label_patterns[target_label],
            "cross_sender": target_label in {"job-related", "travel", "spam-low-value"},
            "has_strong_signal": False,
        }
    checks = [
        {
            "terms": ("phishing", "phish", "scam", "suspicious", "fake"),
            "name": "payment or account notices that look suspicious",
            "cross_sender": True,
        },
        {
            "terms": ("interview", "recruiter", "hiring", "application", "job"),
            "name": "job, recruiter, or interview emails",
            "cross_sender": True,
        },
        {
            "terms": ("flight", "travel", "hotel", "booking", "reservation"),
            "name": "travel and booking emails",
            "cross_sender": True,
        },
        {
            "terms": ("invoice", "billing", "bill", "payment", "receipt", "charged"),
            "name": "billing, receipt, or payment notices",
            "cross_sender": False,
        },
        {
            "terms": ("account", "login", "security", "closure", "password", "statement", "notice"),
            "name": "account, security, or statement notices",
            "cross_sender": False,
        },
        {
            "terms": ("newsletter", "digest", "marketing", "promo", "promotion", "sale"),
            "name": "newsletter or marketing emails",
            "cross_sender": False,
        },
    ]
    for check in checks:
        if any(term in text for term in check["terms"]):
            return {
                "name": check["name"],
                "cross_sender": check["cross_sender"],
                "has_strong_signal": True,
            }
    return {"name": "", "cross_sender": False, "has_strong_signal": False}


def _semantic_text(current: dict, note: str) -> str:
    return " ".join(
        str(value or "").lower()
        for value in (
            note,
            current.get("subject"),
            current.get("snippet"),
            current.get("interpretation"),
            current.get("body"),
        )
    )


def build_companion_memory_proposal(
    storage_dir: Path,
    *,
    current: dict,
    target_label: str,
    note: str,
    scope: str,
    semantic_rule: dict | None = None,
):
    provider = current.get("provider", "gmail")
    semantic_rule = semantic_rule or build_semantic_future_rule(current=current, target_label=target_label, note=note, scope=scope)
    explanation = note or semantic_rule["plain_english_rule"]
    if note and semantic_rule.get("semantic_pattern"):
        explanation = f"{semantic_rule['plain_english_rule']} Founder note: {note}"
    return build_memory_proposal(
        provider=provider,
        account_id=current.get("account_id", ""),
        source_batch_id=current["batch_id"],
        selected_items=[current],
        scope=scope,
        label=target_label,
        explanation=explanation,
        storage_items=load_storage_items(storage_dir, provider),
    )


def build_similar_candidate_preview(
    storage_dir: Path,
    *,
    current: dict,
    target_label: str,
    exact_matches: list[dict],
) -> dict:
    provider = current.get("provider", "gmail")
    current_message_id = current.get("message_id", "")
    exact_message_ids = {match.get("message_id") for match in exact_matches if match.get("message_id")}
    storage_items = load_storage_items(storage_dir, provider)
    groups = [
        _similar_group_same_domain(current, storage_items, target_label, exact_message_ids),
        _similar_group_display_sender(current, storage_items, target_label, exact_message_ids),
        _similar_group_subject_pattern(current, storage_items, target_label, exact_message_ids),
    ]
    groups = [group for group in groups if group["count"] > 0]
    seen = set()
    examples = []
    for group in groups:
        for example in group["examples"]:
            message_id = example.get("message_id")
            if not message_id or message_id == current_message_id or message_id in seen:
                continue
            seen.add(message_id)
            examples.append(example)
    broader_rules = _broader_rule_candidates(current, target_label, groups)
    return {
        "similar_candidate_count": len(seen),
        "similar_candidate_examples": examples[:5],
        "similar_candidate_groups": groups,
        "broader_rule_candidates": broader_rules,
    }


def _similar_group_same_domain(current: dict, items: list[dict], target_label: str, exact_message_ids: set[str]) -> dict:
    current_sender = normalized_sender_email(current.get("sender") or "")
    current_domain = _email_domain(current_sender)
    matches = []
    if current_domain:
        for item in items:
            sender = normalized_sender_email(item.get("sender") or "")
            if _email_domain(sender) != current_domain:
                continue
            if sender == current_sender:
                continue
            matches.append(item)
    return _similar_group(
        "same-domain",
        f"Same sender domain: {current_domain}" if current_domain else "Same sender domain",
        "Same email domain, but not the exact same sender address.",
        matches,
        target_label,
        exact_message_ids,
    )


def _similar_group_display_sender(current: dict, items: list[dict], target_label: str, exact_message_ids: set[str]) -> dict:
    current_display = _display_sender(current.get("sender") or "")
    matches = []
    if current_display:
        for item in items:
            if _display_sender(item.get("sender") or "") != current_display:
                continue
            if normalized_sender_email(item.get("sender") or "") == normalized_sender_email(current.get("sender") or ""):
                continue
            matches.append(item)
    return _similar_group(
        "display-sender",
        f"Same display sender: {current_display}" if current_display else "Same display sender",
        "Same visible sender name with a different address.",
        matches,
        target_label,
        exact_message_ids,
    )


def _similar_group_subject_pattern(current: dict, items: list[dict], target_label: str, exact_message_ids: set[str]) -> dict:
    current_pattern = _subject_pattern(current.get("subject") or "")
    matches = []
    if current_pattern:
        for item in items:
            if _subject_pattern(item.get("subject") or "") != current_pattern:
                continue
            if item.get("message_id") == current.get("message_id"):
                continue
            matches.append(item)
    return _similar_group(
        "subject-pattern",
        f"Same subject pattern: {current_pattern}" if current_pattern else "Same subject pattern",
        "Subject matches after removing changing IDs, numbers, and codes.",
        matches,
        target_label,
        exact_message_ids,
    )


def _similar_group(
    group_id: str,
    label: str,
    reason: str,
    matches: list[dict],
    target_label: str,
    exact_message_ids: set[str],
) -> dict:
    examples = []
    seen = set()
    for item in matches:
        message_id = item.get("message_id", "")
        if not message_id or message_id in exact_message_ids or message_id in seen:
            continue
        seen.add(message_id)
        examples.append(_similar_example(item, target_label))
    return {
        "id": group_id,
        "label": label,
        "reason": reason,
        "count": len(examples),
        "examples": examples[:5],
    }


def _similar_example(item: dict, target_label: str) -> dict:
    return {
        "message_id": item.get("message_id", ""),
        "sender": item.get("sender", ""),
        "subject": item.get("subject", ""),
        "labels_before": list(item.get("applied_labels") or []),
        "labels_after": [target_label],
    }


def _broader_rule_candidates(current: dict, target_label: str, groups: list[dict]) -> list[dict]:
    candidates = []
    current_domain = _email_domain(normalized_sender_email(current.get("sender") or ""))
    subject_pattern = _subject_pattern(current.get("subject") or "")
    if any(group["id"] == "same-domain" for group in groups) and current_domain:
        candidates.append(
            {
                "id": "domain-rule",
                "scope": "sender-domain",
                "plain_english_rule": f"Treat emails from {current_domain} like this as {gmail_label_name(target_label)}.",
                "signals": ["sender domain", "selected email context"],
            }
        )
    if any(group["id"] == "subject-pattern" for group in groups) and subject_pattern:
        candidates.append(
            {
                "id": "subject-pattern-rule",
                "scope": "subject-pattern",
                "plain_english_rule": f"Treat emails with subject pattern '{subject_pattern}' as {gmail_label_name(target_label)}.",
                "signals": ["subject pattern", "selected email context"],
            }
        )
    return candidates


def _email_domain(sender_email: str) -> str:
    if "@" not in sender_email:
        return ""
    return sender_email.rsplit("@", 1)[1].strip().lower()


def _display_sender(sender: str) -> str:
    value = str(sender or "").strip()
    if "<" in value:
        value = value.split("<", 1)[0].strip()
    value = value.strip('"').strip("'").strip().lower()
    return re.sub(r"\s+", " ", value)


def _subject_pattern(subject: str) -> str:
    value = str(subject or "").strip().lower()
    if not value:
        return ""
    value = re.sub(r"\([^)]*[a-z]*\d[\w-]*[^)]*\)", "(...)", value)
    value = re.sub(r"\b[a-z]*\d[\w-]*\b", "#", value)
    value = re.sub(r"\d+", "#", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _boundary_from_exclusion_reason(reason: str) -> str:
    cleaned = " ".join(str(reason or "").strip().split())
    if not cleaned:
        return "emails matching the excluded pattern"
    lowered = cleaned.lower()
    for prefix in ("this one is ", "this is ", "it is ", "it's "):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    cleaned = cleaned.rstrip(".")
    return cleaned


def resolve_target_label(target_label: str, note: str) -> str:
    target_label = (target_label or "").strip()
    if target_label:
        return target_label
    inferred = infer_target_label_from_note(note)
    if inferred:
        return inferred
    raise ValueError("Choose a label or describe the correction more clearly, for example 'this is spam' or 'this needs a reply'.")


def interpret_teaching_intent(*, current: dict, target_label: str, note: str, scope: str) -> dict:
    explicit_label = (target_label or "").strip()
    if explicit_label:
        return {
            "target_label": explicit_label,
            "semantic_pattern": "",
            "cross_sender": False,
            "confidence": "high",
            "source": "explicit-label",
        }

    llm_client = OpenAITeachingIntentClient.from_env()
    if llm_client is not None:
        llm_intent = normalize_llm_teaching_intent(
            llm_client.interpret(
                {
                    "note": note,
                    "scope": scope,
                    "current_subject": current.get("subject") or "",
                    "current_sender": current.get("sender") or "",
                    "current_snippet": current.get("snippet") or "",
                    "current_interpretation": current.get("interpretation") or "",
                    "current_labels": list(current.get("final_labels") or current.get("applied_labels") or []),
                }
            )
        )
        if llm_intent:
            return {**llm_intent, "source": "llm"}

    inferred = infer_target_label_from_note(note)
    if inferred:
        return {
            "target_label": inferred,
            "semantic_pattern": "",
            "cross_sender": False,
            "confidence": "medium",
            "source": "deterministic",
        }
    raise ValueError("Choose a label or describe the correction more clearly, for example 'this is spam' or 'this needs a reply'.")


def normalize_llm_teaching_intent(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    target_label = str(payload.get("target_label") or "").strip()
    if target_label not in CANONICAL_LABEL_ORDER:
        return {}
    return {
        "target_label": target_label,
        "semantic_pattern": str(payload.get("semantic_pattern") or "").strip(),
        "cross_sender": bool(payload.get("cross_sender")),
        "confidence": str(payload.get("confidence") or "low").lower(),
        "rationale": str(payload.get("rationale") or "").strip(),
    }


def infer_target_label_from_note(note: str) -> str:
    text = f" {str(note or '').lower()} "
    checks = [
        (("spam", "junk", "scam", "phishing", "phish", "suspicious", "low value", "low-value", "delete this", "garbage"), "spam-low-value"),
        (("newsletter", "digest", "mailing list"), "newsletter"),
        (("promotion", "promo", "sale", "discount", "marketing"), "promotions"),
        (("receipt", "invoice", "billing", "bill", "payment", "charged"), "receipt-billing"),
        (("order", "shipping", "delivery", "dispatched", "tracking"), "shopping-order"),
        (("account", "login", "security", "closure", "password", "suspension"), "account-security"),
        (("reply", "respond", "needs response", "answer this"), "reply-needed"),
        (("job", "recruiter", "interview", "application", "hiring"), "job-related"),
        (("travel", "flight", "hotel", "booking", "reservation"), "travel"),
        (("calendar", "appointment", "meeting", "event"), "calendar-event"),
        (("personal", "friend", "family"), "personal"),
        (("finance", "bank", "financial", "account statement"), "financial-account"),
    ]
    negative_markers = (" not ", " isn't ", " isnt ", " wrong ", " should not ", " shouldn't ", " not be ", " not even ")
    replacement_markers = (" should be ", " regarding ", " about ", " this is ", " it is ", " it's ", " should clearly be ")
    scored: list[tuple[int, str]] = []
    for terms, label in checks:
        positive = 0
        negative = 0
        emphasis = 0
        for term in terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b")
            for match in pattern.finditer(text):
                idx = match.start()
                window = text[max(0, idx - 36): min(len(text), match.end() + 36)]
                if any(marker in window for marker in negative_markers):
                    negative += 1
                else:
                    positive += 1
                if any(marker in window for marker in replacement_markers):
                    emphasis += 1
        score = positive * 3 + emphasis * 2 - negative * 4
        if score > 0:
            scored.append((score, label))
    if scored:
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored[0][1]
    return ""


def apply_label_to_message(
    storage_dir: Path,
    *,
    batch_id: str,
    message_id: str,
    label: str,
    note: str,
    review_action: str,
) -> bool:
    store = GmailBatchReviewStore(storage_dir)
    stored_batch = store.load_batch(batch_id)
    changed = False
    for item in stored_batch.get("items", []):
        if item.get("message_id") != message_id:
            continue
        item["review_state"] = "reviewed"
        item["review_action"] = review_action
        item["final_labels"] = [label]
        item["applied_labels"] = [label]
        if note:
            item["interpretation"] = note
        changed = True
        break
    if changed:
        store.persist_reviewed_items(batch_id, stored_batch["items"])
    return changed


def apply_label_to_preview_matches(
    storage_dir: Path,
    matches: list[dict],
    *,
    selected_message_id: str,
    label: str,
    note: str,
    review_action: str = "sidebar-matching-existing",
) -> int:
    count = 0
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return 0
    for batch_path in sorted(batches_dir.glob("*.json")):
        batch = load_json(batch_path)
        batch_changed = False
        for item in batch.get("items", []):
            if item.get("message_id") == selected_message_id:
                continue
            if not any(match.get("message_id") == item.get("message_id") for match in matches):
                continue
            item["review_state"] = "reviewed"
            item["review_action"] = review_action
            item["final_labels"] = [label]
            item["applied_labels"] = [label]
            if note:
                item["interpretation"] = note
            batch_changed = True
            count += 1
        if batch_changed:
            GmailBatchReviewStore(storage_dir).persist_reviewed_items(batch.get("batch_id", ""), batch.get("items", []))
    return count


def load_items_for_gmail_write_through(
    storage_dir: Path,
    *,
    selected_message_id: str,
    mode: str,
    preview_matches: list[dict],
) -> dict[str, list[dict]]:
    preview_message_ids = {
        match.get("message_id")
        for match in preview_matches
        if match.get("message_id")
    }
    batches: dict[str, list[dict]] = {}
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return batches
    for batch_path in sorted(batches_dir.glob("*.json")):
        batch = load_json(batch_path)
        batch_id = batch.get("batch_id", "")
        matched_items = []
        if mode == "save-future-rule":
            continue
        for item in batch.get("items", []):
            message_id = item.get("message_id")
            if message_id == selected_message_id:
                matched_items.append(item)
                continue
            if mode in {"matching-existing", "apply-included"} and message_id in preview_message_ids:
                matched_items.append(item)
        if matched_items:
            batches[batch_id] = matched_items
    return batches


def build_teach_acknowledgment(
    *,
    current: dict,
    target_label: str,
    note: str,
    affected_existing_count: int,
    scope: str,
) -> str:
    label_name = gmail_label_name(target_label)
    semantic_rule = build_semantic_future_rule(current=current, target_label=target_label, note=note, scope=scope)
    lesson = f"I interpreted the future rule as: {semantic_rule['plain_english_rule']}"
    if note:
        lesson = f"{lesson} I used your note to interpret the lesson."
    if affected_existing_count:
        return f"I can relabel this email to {label_name}. {lesson} That would also change {affected_existing_count} existing stored emails if you confirm."
    future_phrase = "future emails" if scope == "sender" else "future matching emails"
    return f"I can relabel this email to {label_name}. {lesson} I do not see any other existing stored emails to change right now, so this would mainly teach {future_phrase}."


def build_apply_acknowledgment(
    *,
    current: dict,
    target_label: str,
    mode: str,
    matched_existing_count: int,
    exceptions_saved_count: int = 0,
    future_rule_saved: bool = False,
) -> str:
    label_name = gmail_label_name(target_label)
    if mode == "current-only":
        return f"I relabeled only this email to {label_name}. I did not change other stored emails or save a broader future rule."
    if mode == "matching-existing":
        return f"I relabeled this email to {label_name} and rewrote {matched_existing_count} matching stored emails. I did not save a future rule."
    if mode == "apply-included":
        future_copy = "saved a future rule" if future_rule_saved else "did not save a future rule"
        return (
            f"I relabeled this email to {label_name}, rewrote {matched_existing_count} included stored emails, "
            f"kept {exceptions_saved_count} saved exceptions, and {future_copy}."
        )
    if mode == "save-future-rule":
        return f"I saved a future rule. I did not relabel this email or rewrite other existing emails."
    if mode == "future-only":
        return f"I relabeled this email to {label_name} and saved a future rule. No other existing stored emails were rewritten."
    return f"I applied the teaching action for {label_name}."
