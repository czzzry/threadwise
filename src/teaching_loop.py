import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_companion_state import artifact_path_sort_key, find_matching_item
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.candidate_change_store import CandidateChange, CandidateChangeStore
from src.local_artifacts import candidate_changes_path, load_json, memory_proposals_path, teachable_rules_path
from src.memory_proposal_store import (
    MemoryProposalStore,
    build_memory_proposal,
    load_storage_items,
    rule_from_memory_proposal,
)
from src.sender_utils import normalized_sender_email
from src.semantic_rule_matching import build_semantic_boundary, semantic_rule_matches_message
from src.teaching_exclusions import (
    count_teaching_exclusions_for_proposal,
    filter_excluded_preview_matches,
    save_teaching_exclusion,
)
from src.teachable_rule_memory import TeachableRuleMemory, matching_rules_for_message
from src.label_change import (
    LabelChangeError,
    legacy_only_change,
    normalize_label_change,
    require_current_baseline,
)


VALID_TEACHING_APPLY_MODES = {"current-only", "matching-existing", "save-future-rule", "future-only", "apply-included"}
DEFAULT_TEACHING_INTENT_MODEL = "gpt-4.1-mini"
DEFAULT_TEACHING_INTENT_TIMEOUT_SECONDS = 8


def teaching_llm_status() -> dict:
    """Expose configuration state without exposing the credential itself."""
    key_source = "EMAIL_AGENT_OPENAI_API_KEY" if os.getenv("EMAIL_AGENT_OPENAI_API_KEY") else (
        "OPENAI_API_KEY" if os.getenv("OPENAI_API_KEY") else ""
    )
    return {
        "configured": bool(key_source),
        "status": "configured" if key_source else "unavailable",
        "model": os.getenv("THREADWISE_TEACHING_MODEL") or DEFAULT_TEACHING_INTENT_MODEL,
        "key_source": key_source,
        "message": (
            "LLM teaching review is configured for this companion."
            if key_source
            else "LLM teaching review is unavailable because this companion has no OpenAI key configured."
        ),
    }


class OpenAITeachingIntentClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = DEFAULT_TEACHING_INTENT_TIMEOUT_SECONDS) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAITeachingIntentClient | None":
        api_key = os.getenv("EMAIL_AGENT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return cls(api_key=api_key, model=model or os.getenv("THREADWISE_TEACHING_MODEL") or DEFAULT_TEACHING_INTENT_MODEL)

    def interpret(self, payload: dict) -> dict:
        prompt = (
            "You interpret founder correction notes for an email labeling tool.\n"
            "Return strict JSON with keys: target_label, operation, target_labels, source_labels, "
            "resolution_status, clarifying_question, semantic_pattern, cross_sender, confidence, rationale.\n"
            "target_label must be one of: "
            + ", ".join(CANONICAL_LABEL_ORDER)
            + ".\n"
            "Choose the label the founder wants after reading the current email context and complaint.\n"
            "explicit_target_label is the resolved desired label after checking the founder's note. Keep it unless the note clearly rejects it.\n"
            "If selected_target_label_rejected is true, never echo the selected label back as the desired target.\n"
            "Use remembered_instructions as prior founder guidance, but treat the latest correction note as authoritative when it clearly changes or rejects that guidance.\n"
            "semantic_pattern should be a short plain-English description of what should match, honoring every inclusion, negation, and exclusion in the note.\n"
            "cross_sender must be true only if the founder intent clearly spans multiple senders.\n"
            "If uncertain, still pick the best label and set confidence to low."
            " operation must be only, add, remove, or replace. target_labels and source_labels must be canonical label arrays."
            " Use resolution_status=ambiguous or contradictory instead of guessing when the requested final label set is unclear."
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
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:
            return {}
        except urllib.error.URLError:
            return {}
        except TimeoutError:
            return {}
        content = (((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if not content:
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return {**parsed, "_model": self._model} if isinstance(parsed, dict) else {}


def build_sidebar_teach_preview(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    target_label_explicit: bool = True,
    note: str,
    scope: str,
    include_existing_impact: bool = True,
    force_llm_review: bool = False,
) -> dict:
    current = load_selected_storage_item(storage_dir, selected_context)
    current_labels = list(current.get("final_labels") or current.get("applied_labels") or [])
    deterministic_change = infer_label_change_from_note(note, current_labels)
    inferred_change_label = ""
    if deterministic_change:
        inferred_targets = list(deterministic_change.get("target_labels") or [])
        inferred_sources = set(deterministic_change.get("source_labels") or [])
        if deterministic_change.get("operation") == "add":
            inferred_change_label = next(iter(current_labels), next(iter(inferred_targets), ""))
        else:
            inferred_change_label = next(
                iter(inferred_targets),
                next((label for label in current_labels if label not in inferred_sources), ""),
            )
    intent_label = inferred_change_label or (target_label if target_label_explicit or not note.strip() else "")
    remembered_instructions = remembered_teaching_instructions(storage_dir, current)
    intent = interpret_teaching_intent(
        current=current,
        target_label=intent_label,
        note=note,
        scope=scope,
        force_llm_review=force_llm_review,
        remembered_instructions=remembered_instructions,
    )
    target_label = intent["target_label"]
    label_change = build_selected_label_change(
        current_labels=current_labels,
        target_label=target_label,
        note=note,
        intent=intent,
    )
    semantic_rule = build_semantic_future_rule(
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        intent=intent,
    )
    future_rule_allowed = bool(semantic_rule.get("future_rule_allowed", True))
    storage_items = load_storage_items(storage_dir, current.get("provider", "gmail")) if include_existing_impact else []
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        semantic_rule=semantic_rule,
        storage_items=storage_items,
    )
    preview = proposal.preview
    proposal_payload = proposal.to_dict()
    preview_matches = _authoritative_preview_matches(
        storage_dir,
        current=current,
        proposal_preview=preview,
        semantic_rule=semantic_rule,
        storage_items=storage_items,
    )
    preview_matches = filter_excluded_preview_matches(storage_dir, proposal_payload, preview_matches)
    affected_existing = [
        match for match in preview_matches
        if match.get("message_id") != current["message_id"]
    ]
    normalized_existing = [
        {
            **match,
            "labels_after": list(label_change["labels_after"]),
        }
        for match in affected_existing
    ]
    similar_candidates = build_similar_candidate_preview(
        storage_dir,
        current=current,
        target_label=target_label,
        exact_matches=normalized_existing,
        storage_items=storage_items,
    )
    target_label_name = gmail_label_name(target_label)
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
    human_explanation = build_human_teaching_explanation(
        current=current,
        target_label=target_label,
        semantic_rule=semantic_rule,
        intent_source=intent.get("source") or "deterministic-fallback",
        selected_label_conflict=intent.get("selected_label_conflict"),
    )
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
        "selected_label_after": list(label_change["labels_after"]),
        "label_change": label_change,
        "current_label_name": current_label_name,
        "target_label_name": target_label_name,
        "plain_english_rule": semantic_rule["plain_english_rule"],
        "human_explanation": human_explanation,
        "rule_type": semantic_rule["rule_type"],
        "rule_type_label": semantic_rule["rule_type_label"],
        "rule_confidence": semantic_rule["rule_confidence"],
        "rule_confidence_label": semantic_rule["rule_confidence_label"],
        "clarifying_question": semantic_rule["clarifying_question"],
        "structured_rule": structured_rule,
        "semantic_rule": semantic_rule,
        "future_rule_allowed": future_rule_allowed,
        "intent_source": "llm" if intent.get("source") == "llm" else "deterministic-fallback",
        "selected_label_conflict": intent.get("selected_label_conflict"),
        "proposal": proposal.to_dict(),
        "impact": {
            "current_message_will_change": True,
            "matching_existing_count": len(affected_existing),
            "matching_existing_examples": normalized_existing[:5],
            "matching_existing_items": normalized_existing,
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


def finish_sidebar_teach_preview_impact(storage_dir: Path, preview: dict) -> dict:
    completed = dict(preview)
    semantic_rule = dict(completed.get("semantic_rule") or {})
    proposal_payload = dict(completed.get("proposal") or {})
    current = {
        "provider": proposal_payload.get("provider") or "gmail",
        "batch_id": completed.get("selected_batch_id") or proposal_payload.get("source_batch_id") or "",
        "account_id": completed.get("selected_account_id") or proposal_payload.get("account_id") or "",
        "message_id": completed.get("selected_message_id") or "",
        "sender": completed.get("selected_sender") or "",
        "subject": completed.get("selected_subject") or "",
        "final_labels": list(completed.get("selected_label_before") or []),
        "applied_labels": list(completed.get("selected_label_before") or []),
    }
    target_label = semantic_rule.get("target_label") or (completed.get("selected_label_after") or [""])[0]
    storage_items = load_storage_items(storage_dir, current["provider"])
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=str(proposal_payload.get("explanation") or ""),
        scope=str(proposal_payload.get("scope") or semantic_rule.get("scope") or "sender"),
        semantic_rule=semantic_rule,
        storage_items=storage_items,
    )
    proposal_payload = proposal.to_dict()
    preview_matches = _authoritative_preview_matches(
        storage_dir,
        current=current,
        proposal_preview=proposal.preview,
        semantic_rule=semantic_rule,
        storage_items=storage_items,
    )
    preview_matches = filter_excluded_preview_matches(storage_dir, proposal_payload, preview_matches)
    affected_existing = [
        {**match, "labels_after": [target_label]}
        for match in preview_matches
        if match.get("message_id") != current["message_id"]
    ]
    similar_candidates = build_similar_candidate_preview(
        storage_dir,
        current=current,
        target_label=target_label,
        exact_matches=affected_existing,
        storage_items=storage_items,
    )
    impact = dict(completed.get("impact") or {})
    impact.update(
        {
            "matching_existing_count": len(affected_existing),
            "matching_existing_examples": affected_existing[:5],
            "matching_existing_items": affected_existing,
            "similar_candidate_count": similar_candidates["similar_candidate_count"],
            "similar_candidate_examples": similar_candidates["similar_candidate_examples"],
            "similar_candidate_groups": similar_candidates["similar_candidate_groups"],
            "broader_rule_candidates": similar_candidates["broader_rule_candidates"],
        }
    )
    structured_rule = dict(completed.get("structured_rule") or {})
    structured_rule["applies_to_existing_count"] = len(affected_existing)
    completed["proposal"] = proposal_payload
    completed["impact"] = impact
    completed["structured_rule"] = structured_rule
    return completed


def apply_sidebar_teaching(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
    mode: str,
    included_message_ids: list[str] | None = None,
    approved_label_change: dict | None = None,
) -> dict:
    if mode not in VALID_TEACHING_APPLY_MODES:
        raise ValueError("Unsupported apply mode.")
    current = load_selected_storage_item(storage_dir, selected_context)
    if approved_label_change is not None:
        if mode != "current-only":
            raise LabelChangeError("Label-set corrections are limited to this email in this release.")
        label_change = normalize_label_change(approved_label_change)
        require_current_baseline(
            label_change,
            list(current.get("final_labels") or current.get("applied_labels") or []),
        )
        target_label = label_change.primary_label
        intent = {
            "target_label": target_label,
            "source": label_change.interpretation.get("source") or "manual",
        }
    else:
        intent = interpret_teaching_intent(
            current=current,
            target_label=target_label,
            note=note,
            scope=scope,
        )
        target_label = intent["target_label"]
        label_change = None
    semantic_rule = build_semantic_future_rule(current=current, target_label=target_label, note=note, scope=scope, intent=intent)
    if semantic_rule.get("future_rule_allowed") is False and mode != "current-only":
        raise ValueError(
            "This note describes a one-off or uncertain email, so Threadwise will only change this email. "
            "Describe a recurring pattern explicitly before teaching a future or Inbox rule."
        )
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
        semantic_rule=semantic_rule,
    )
    preview_matches = _authoritative_preview_matches(
        storage_dir,
        current=current,
        proposal_preview=proposal.preview,
        semantic_rule=semantic_rule,
    )
    preview_matches = filter_excluded_preview_matches(storage_dir, proposal.to_dict(), preview_matches)
    if mode == "apply-included":
        included_ids = {str(message_id) for message_id in included_message_ids or [] if message_id}
        current_account_id = str(current.get("account_id") or "")
        preview_matches = [
            item
            for item in _deduplicate_messages(
                load_storage_items(storage_dir, current.get("provider", "gmail"))
            )
            if str(item.get("message_id") or "") in included_ids
            and (
                not current_account_id
                or str(item.get("account_id") or "") == current_account_id
            )
        ]

    current_changed = False
    if mode in {"current-only", "matching-existing", "future-only", "apply-included"}:
        current_changed = apply_label_to_message(
            storage_dir,
            batch_id=current["batch_id"],
            message_id=current["message_id"],
            label=target_label,
            labels=list(label_change.labels_after) if label_change else None,
            note=note,
            review_action="sidebar-current-only" if mode == "current-only" else f"sidebar-{mode}",
        )

    matched_existing_count = 0
    proposal_record = None
    candidate_record = None
    future_rule_saved = False
    if mode in {"save-future-rule", "future-only", "apply-included"}:
        store = MemoryProposalStore(memory_proposals_path(storage_dir))
        proposal_record = store.save_proposal(proposal)
        proposal_record = store.review_proposal(
            proposal.id,
            "approved",
            rules_memory=TeachableRuleMemory(teachable_rules_path(storage_dir)),
            review_notes="Explicitly approved in the Gmail companion teaching flow.",
        )
        candidate_store = CandidateChangeStore(candidate_changes_path(storage_dir))
        projection_rule = rule_from_memory_proposal(
            proposal_record,
            existing_count=0,
        )
        candidate_record = candidate_store.save_candidate(
            CandidateChange(
                id=f"candidate-{proposal.id}",
                kind="future-rule",
                source="sidebar-teach",
                title=proposal.instruction,
                description="Reusable future rule saved from inbox teaching.",
                affected_scope_summary=f"{proposal.scope} rule candidate for {proposal.label}",
                provider=proposal.provider,
                account_id=proposal.account_id,
                source_refs=(
                    f"proposal:{proposal.id}",
                    *[f"message:{message_id}" for message_id in proposal.source_message_ids],
                ),
                created_at=proposal.created_at,
                updated_at=proposal.updated_at,
                metadata={
                    "proposal_id": proposal.id,
                    "rules": [projection_rule.to_dict()],
                    "apply_mode": mode,
                },
            )
        )
        candidate_record = candidate_store.apply_decision(
            candidate_record.id,
            decision="promote",
            actor="founder-explicit-teaching-action",
            latest_recommendation="Explicitly approved in the Gmail companion teaching flow.",
        )
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
        "candidate_change": candidate_record.to_dict() if candidate_record else None,
        "current": current,
        "preview_matches": preview_matches,
        "semantic_rule": semantic_rule,
        "label_change": label_change.to_dict() if label_change else None,
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
    entry = save_teaching_exclusion(
        storage_dir,
        proposal=proposal.to_dict(),
        message_id=excluded_message_id,
        reason=reason,
    )
    remaining_matches = _authoritative_preview_matches(
        storage_dir,
        current=current,
        proposal_preview=proposal.preview,
        semantic_rule=semantic_rule,
    )
    remaining_matches = filter_excluded_preview_matches(storage_dir, proposal.to_dict(), remaining_matches)
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
    sender_domain = _email_domain(sender)
    if _note_is_one_off_or_uncertain(note):
        return {
            "scope": scope,
            "application_scope": "current-email",
            "target_label": target_label,
            "sender": sender,
            "semantic_pattern": "",
            "plain_english_rule": "No future rule proposed: your note describes a rare or one-time email.",
            "rule_type": "current-only",
            "rule_type_label": "This email only",
            "rule_confidence": "high",
            "rule_confidence_label": "Current email only",
            "clarifying_question": "If this should apply to recurring Google emails, describe that recurring pattern explicitly.",
            "matching_basis": ["current email", "founder note"],
            "include_families": [],
            "exclude_families": [],
            "excluded_pattern": "",
            "cross_sender": False,
            "future_rule_allowed": False,
        }
    if sender_domain and _note_requests_entire_sender_domain(note):
        return {
            "scope": "sender-domain",
            "target_label": target_label,
            "sender": sender,
            "sender_domain": sender_domain,
            "semantic_pattern": "",
            "plain_english_rule": f"Treat all messages from {sender_domain} as {label_name}.",
            "rule_type": "sender-domain",
            "rule_type_label": "Sender domain rule",
            "rule_confidence": "high",
            "rule_confidence_label": "Future rule",
            "clarifying_question": "",
            "matching_basis": ["sender domain", "founder note", "stored Threadwise data"],
            "include_families": [],
            "exclude_families": [],
            "excluded_pattern": "",
            "cross_sender": False,
        }
    if _note_requests_entire_sender(note):
        return {
            "scope": "sender",
            "target_label": target_label,
            "sender": sender,
            "semantic_pattern": "",
            "plain_english_rule": f"Treat future messages from {sender} as {label_name}.",
            "rule_type": "sender",
            "rule_type_label": "Sender rule",
            "rule_confidence": "high",
            "rule_confidence_label": "Future rule",
            "clarifying_question": "",
            "matching_basis": ["sender", "founder note", "stored Threadwise data"],
            "include_families": [],
            "exclude_families": [],
            "excluded_pattern": "",
            "cross_sender": False,
        }
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
    excluded_pattern = semantic_pattern.get("excluded_pattern") or ""
    if excluded_pattern:
        plain_rule = f"{plain_rule.rstrip('.')} — excluding {excluded_pattern}."
    confidence = "tentative" if not semantic_pattern["has_strong_signal"] else "medium"
    clarifying_question = ""
    if not semantic_pattern["has_strong_signal"] and note:
        clarifying_question = f"Should this apply to all future messages from {sender_name}, or only a narrower kind of message?"
    return {
        "scope": scope,
        "target_label": target_label,
        "sender": sender,
        "semantic_pattern": semantic_pattern["name"],
        "plain_english_rule": plain_rule,
        "rule_type": rule_type,
        "rule_type_label": rule_type_label,
        "rule_confidence": confidence,
        "rule_confidence_label": "Tentative future rule" if confidence == "tentative" else "Future rule",
        "clarifying_question": clarifying_question,
        "matching_basis": matching_basis,
        "include_families": semantic_pattern.get("include_families", []),
        "exclude_families": semantic_pattern.get("exclude_families", []),
        "excluded_pattern": excluded_pattern,
        "cross_sender": cross_sender,
        "future_rule_allowed": True,
    }


def build_human_teaching_explanation(
    *,
    current: dict,
    target_label: str,
    semantic_rule: dict,
    intent_source: str,
    selected_label_conflict: dict | None = None,
) -> str:
    label_name = gmail_label_name(target_label)
    sender = _display_sender(current.get("sender") or "") or normalized_sender_email(current.get("sender") or "") or "this sender"
    if semantic_rule.get("future_rule_allowed") is False:
        explanation = f"I will change only this email to {label_name}. I will not create a broader rule."
    elif semantic_rule.get("rule_type") == "sender":
        explanation = f"I read this as: future emails from {sender} should be {label_name}."
    elif semantic_rule.get("rule_type") == "sender-domain":
        explanation = f"I read this as: emails from this sender domain should be {label_name}."
    else:
        pattern = str(semantic_rule.get("semantic_pattern") or "similar emails")
        explanation = f"I read this as: {pattern} should be {label_name}."
        if sender and semantic_rule.get("rule_type") == "sender-semantic":
            explanation = f"I read this as: {pattern} from {sender} should be {label_name}."
    if selected_label_conflict:
        explanation = f"{selected_label_conflict['message']} {explanation}"
    if intent_source == "llm":
        return f"{explanation} LLM reviewed your note with this email's context."
    return f"{explanation} Threadwise used the note and email context directly because LLM review was unavailable."


def _note_is_one_off_or_uncertain(note: str) -> bool:
    text = " ".join(str(note or "").lower().split())
    if not text:
        return False
    return bool(
        re.search(
            r"\b(?:one[- ]time|one[- ]off|rare|just this email|this email only|only this email)\b|"
            r"\b(?:could|maybe|might)\s+(?:also\s+)?(?:be|have|need)\b|"
            r"\bshould we\s+(?:also\s+)?add\b",
            text,
        )
    )


def _note_requests_entire_sender_domain(note: str) -> bool:
    text = " ".join(str(note or "").lower().split())
    return bool(
        re.search(
            r"\b(?:all|any|every|anything)\s+(?:emails?|messages?|mail)\s+from\s+(?:this|the|that|their)\s+domain\b|"
            r"\b(?:all|any|every|anything)\s+from\s+(?:this|the|that|their)\s+domain\b|"
            r"\b(?:entire|whole)\s+(?:sender\s+)?domain\b",
            text,
        )
    )


def _note_requests_entire_sender(note: str) -> bool:
    text = " ".join(str(note or "").lower().split())
    return bool(
        re.search(
            r"\b(?:all|any|every|anything)\s+(?:future\s+)?(?:emails?|messages?|mail)\s+from\s+(?:this|the|that)\s+(?:exact\s+)?sender\b|"
            r"\b(?:all|any|every|anything)\s+(?:future\s+)?(?:emails?|messages?|mail)\s+from\s+[^.\s]+@[^.\s]+\b",
            text,
        )
    )


def infer_semantic_pattern(current: dict, note: str, target_label: str, intent: dict | None = None) -> dict:
    if target_label == "suspicious":
        return {
            "name": "suspicious or phishing messages from this sender",
            "cross_sender": False,
            "has_strong_signal": True,
            "include_families": [],
            "exclude_families": [],
            "excluded_pattern": "",
        }
    boundary = build_semantic_boundary(
        note=note,
        target_label=target_label,
        llm_pattern=str((intent or {}).get("semantic_pattern") or ""),
        llm_cross_sender=bool((intent or {}).get("cross_sender")),
        llm_confidence=str((intent or {}).get("confidence") or ""),
    )
    if boundary["name"]:
        return boundary
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
            "has_strong_signal": _note_defines_explicit_semantic_boundary(note),
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


def _deduplicate_messages(items: list[dict]) -> list[dict]:
    by_message_id: dict[str, dict] = {}
    without_identity: list[dict] = []
    for item in items:
        message_id = str(item.get("message_id") or "").strip()
        if not message_id:
            without_identity.append(item)
            continue
        by_message_id[message_id] = item
    return [*by_message_id.values(), *without_identity]


def _authoritative_preview_matches(
    storage_dir: Path,
    *,
    current: dict,
    proposal_preview: dict,
    semantic_rule: dict,
    storage_items: list[dict] | None = None,
) -> list[dict]:
    if semantic_rule.get("future_rule_allowed") is False:
        return []
    storage_items = storage_items if storage_items is not None else load_storage_items(storage_dir, current.get("provider", "gmail"))
    if semantic_rule.get("semantic_pattern"):
        return [
            item
            for item in _deduplicate_messages(storage_items)
            if semantic_rule_matches_message(semantic_rule, item)
        ]
    return _deduplicate_messages(list(proposal_preview.get("matches", [])))


def _note_defines_explicit_semantic_boundary(note: str) -> bool:
    text = " ".join(str(note or "").lower().split())
    has_inclusion_boundary = bool(re.search(r"\b(?:only|specifically)\b", text))
    has_exclusion_boundary = bool(re.search(r"\b(?:exclude|excluding|except|unrelated)\b", text))
    semantic_kind_terms = (
        "resource",
        "guide",
        "newsletter",
        "digest",
        "account",
        "transactional",
        "receipt",
        "invoice",
        "statement",
        "security",
        "booking",
        "recruiter",
        "interview",
    )
    return has_inclusion_boundary and has_exclusion_boundary and any(term in text for term in semantic_kind_terms)


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
    storage_items: list[dict] | None = None,
):
    provider = current.get("provider", "gmail")
    semantic_rule = semantic_rule or build_semantic_future_rule(current=current, target_label=target_label, note=note, scope=scope)
    scope = str(semantic_rule.get("scope") or scope)
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
        storage_items=storage_items if storage_items is not None else load_storage_items(storage_dir, provider),
        semantic_rule=semantic_rule,
    )


def build_similar_candidate_preview(
    storage_dir: Path,
    *,
    current: dict,
    target_label: str,
    exact_matches: list[dict],
    storage_items: list[dict] | None = None,
) -> dict:
    provider = current.get("provider", "gmail")
    current_message_id = current.get("message_id", "")
    exact_message_ids = {match.get("message_id") for match in exact_matches if match.get("message_id")}
    storage_items = storage_items if storage_items is not None else load_storage_items(storage_dir, provider)
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


def interpret_teaching_intent(
    *,
    current: dict,
    target_label: str,
    note: str,
    scope: str,
    force_llm_review: bool = False,
    remembered_instructions: list[dict] | None = None,
) -> dict:
    explicit_label = (target_label or "").strip()
    note_label = infer_explicit_target_label_from_note(note)
    deterministic_label = infer_target_label_from_note(note) if not note_label else ""
    explicit_label_rejected = bool(explicit_label and _note_explicitly_rejects_label(note, explicit_label))
    if explicit_label_rejected:
        authoritative_label = note_label or deterministic_label
    else:
        authoritative_label = explicit_label or note_label or deterministic_label
    if not authoritative_label:
        if explicit_label_rejected:
            raise ValueError(
                f"Your note rejects {gmail_label_name(explicit_label)}. Choose the replacement label or describe it more clearly."
            )
        raise ValueError("Choose a label or describe the correction more clearly, for example 'this is spam' or 'this needs a reply'.")
    selected_label_conflict = None
    if explicit_label_rejected and authoritative_label != explicit_label:
        selected_label_conflict = {
            "selected_label": explicit_label,
            "selected_label_name": gmail_label_name(explicit_label),
            "resolved_label": authoritative_label,
            "resolved_label_name": gmail_label_name(authoritative_label),
            "message": (
                f"Your note rejects {gmail_label_name(explicit_label)}, so Threadwise used "
                f"{gmail_label_name(authoritative_label)} instead."
            ),
        }
    llm_client = OpenAITeachingIntentClient.from_env()
    if force_llm_review and llm_client is None:
        raise ValueError(
            "LLM review is not configured for this Threadwise companion. "
            "Configure EMAIL_AGENT_OPENAI_API_KEY in the companion's private environment and restart Threadwise."
        )
    if llm_client is not None and (note or not authoritative_label):
        llm_intent = normalize_llm_teaching_intent(
            llm_client.interpret(
                {
                    "note": note,
                    "scope": scope,
                    "explicit_target_label": authoritative_label,
                    "selected_target_label": explicit_label,
                    "selected_target_label_rejected": explicit_label_rejected,
                    "remembered_instructions": list(remembered_instructions or []),
                    "current_subject": current.get("subject") or "",
                    "current_sender": current.get("sender") or "",
                    "current_snippet": current.get("snippet") or "",
                    "current_body": current.get("body") or "",
                    "current_interpretation": current.get("interpretation") or "",
                    "current_labels": list(current.get("final_labels") or current.get("applied_labels") or []),
                }
            )
        )
        if llm_intent:
            if authoritative_label:
                llm_intent["target_label"] = authoritative_label
            return {
                **llm_intent,
                "source": "llm",
                "selected_label_conflict": selected_label_conflict,
            }
        if force_llm_review:
            raise ValueError("LLM review was unavailable. Nothing was changed; try again in a moment.")

    if authoritative_label:
        return {
            "target_label": authoritative_label,
            "semantic_pattern": "",
            "cross_sender": False,
            "confidence": "high" if note_label else "low",
            "source": "explicit-note-label" if note_label else "explicit-label",
            "selected_label_conflict": selected_label_conflict,
        }

    if deterministic_label:
        return {
            "target_label": deterministic_label,
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
    normalized = {
        "target_label": target_label,
        "semantic_pattern": str(payload.get("semantic_pattern") or "").strip(),
        "cross_sender": bool(payload.get("cross_sender")),
        "confidence": str(payload.get("confidence") or "low").lower(),
        "rationale": str(payload.get("rationale") or "").strip(),
        "model": str(payload.get("_model") or "").strip(),
    }
    operation = str(payload.get("operation") or "").strip().lower()
    if operation:
        normalized["label_change"] = {
            "schema_version": 1,
            "operation": operation,
            "target_labels": list(payload.get("target_labels") or []),
            "source_labels": list(payload.get("source_labels") or []),
            "resolution_status": str(payload.get("resolution_status") or "resolved"),
            "clarifying_question": str(payload.get("clarifying_question") or "").strip(),
        }
    return normalized


def infer_target_label_from_note(note: str) -> str:
    text = f" {str(note or '').lower()} "
    checks = [
        (("phishing", "phish", "suspicious", "credential theft", "impersonation"), "suspicious"),
        (("spam", "junk", "scam", "low value", "low-value", "delete this", "garbage"), "spam-low-value"),
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


def infer_explicit_target_label_from_note(note: str) -> str:
    text = " ".join(str(note or "").lower().replace("_", " ").split())
    label_patterns = (
        ("spam-low-value", r"\b(?:low[- ]?value|spam|junk)\b"),
        ("promotions", r"\bpromotions?\b"),
        ("shopping-order", r"\b(?:orders?|shopping order)\b"),
        ("receipt-billing", r"\b(?:receipts?|billing)\b"),
        ("account-security", r"\b(?:account security|security alert)\b"),
        ("newsletter", r"\bnewsletters?\b"),
        ("job-related", r"\b(?:job[- ]related|work(?: email)?|job)\b"),
        ("reply-needed", r"\b(?:reply[- ]needed|needs? (?:a )?reply)\b"),
        ("travel", r"\btravel\b"),
        ("personal", r"\bpersonal\b"),
    )
    matches: list[str] = []
    for label, pattern in label_patterns:
        for match in re.finditer(pattern, text):
            prefix = text[max(0, match.start() - 18):match.start()]
            if re.search(r"(?:\bnot|isn['’]?t|is not|don['’]?t|do not)\s+$", prefix):
                continue
            matches.append(label)
            break
    unique_matches = list(dict.fromkeys(matches))
    return unique_matches[0] if len(unique_matches) == 1 else ""


def build_selected_label_change(*, current_labels: list[str], target_label: str, note: str, intent: dict) -> dict:
    """Build the exact selected-email set operation; future-rule memory stays singular."""
    llm_change = intent.get("label_change") if isinstance(intent, dict) else None
    intent_source = str(intent.get("source") or "")
    interpretation = {
        "source": "llm" if intent_source == "llm" else "manual" if intent_source == "explicit-label" else "deterministic",
        "status": "reviewed" if intent_source in {"llm", "explicit-label"} else "fallback",
        "model": str(intent.get("model") or ""),
        "rationale": str(intent.get("rationale") or ""),
    }
    if isinstance(llm_change, dict):
        resolution = str(llm_change.get("resolution_status") or "resolved")
        if resolution != "resolved":
            question = str(llm_change.get("clarifying_question") or "Clarify which labels should remain.")
            raise LabelChangeError(question)
        return normalize_label_change({
            **llm_change,
            "labels_before": current_labels,
            "interpretation": interpretation,
        }).to_dict()

    deterministic = infer_label_change_from_note(note, current_labels)
    if deterministic:
        return normalize_label_change({
            **deterministic,
            "labels_before": current_labels,
            "interpretation": interpretation,
        }).to_dict()
    return legacy_only_change(
        labels_before=current_labels,
        target_label=target_label,
        interpretation=interpretation,
    )


def infer_label_change_from_note(note: str, current_labels: list[str]) -> dict | None:
    text = " ".join(str(note or "").lower().replace("_", " ").split())
    aliases = {
        "spam-low-value": ("low value", "low-value", "spam", "junk"),
        "promotions": ("promotion", "promotions", "promo"),
        "shopping-order": ("order", "orders", "shopping order"),
        "receipt-billing": ("receipt", "receipts", "billing"),
        "account-security": ("account", "account security", "security"),
        "newsletter": ("newsletter", "newsletters"),
        "job-related": ("job related", "job-related", "work"),
        "reply-needed": ("reply needed", "reply-needed", "needs action"),
        "travel": ("travel",), "personal": ("personal",),
        "financial-account": ("finance", "financial"),
        "calendar-event": ("calendar",),
    }
    mentioned = [label for label, names in aliases.items() if any(re.search(rf"\b{re.escape(name)}\b", text) for name in names)]
    if not mentioned:
        return None
    requests_add = bool(re.search(r"\b(?:add|keep.+and add)\b", text))
    requests_remove = bool(re.search(r"\b(?:remove|without|drop)\b", text))
    if requests_add and requests_remove and not re.search(r"\b(?:replace|change)\b.+\b(?:with|to)\b", text):
        raise LabelChangeError("This correction asks to add and remove labels at the same time. Clarify the final label set.")
    if re.search(r"\b(?:replace|change)\b.+\b(?:with|to)\b", text):
        sources = [label for label in mentioned if label in current_labels]
        targets = [label for label in mentioned if label not in sources]
        if not sources or not targets:
            raise LabelChangeError("Clarify which existing label to replace and which new label to use.")
        return {"operation": "replace", "source_labels": sources, "target_labels": targets}
    if requests_remove:
        sources = [label for label in mentioned if label in current_labels]
        if not sources:
            raise LabelChangeError("The label you asked to remove is not on this email.")
        return {"operation": "remove", "source_labels": sources, "target_labels": []}
    if requests_add:
        targets = [label for label in mentioned if label not in current_labels]
        if not targets:
            raise LabelChangeError("This request would not change the selected email.")
        return {"operation": "add", "source_labels": [], "target_labels": targets}
    if len(mentioned) > 1 and re.search(r"\b(?:both|two labels?|multiple labels?)\b", text):
        return {"operation": "only", "source_labels": [], "target_labels": mentioned}
    return None


def remembered_teaching_instructions(storage_dir: Path, current: dict, limit: int = 8) -> list[dict]:
    """Return only saved founder rules that match the current message."""
    memory = TeachableRuleMemory(teachable_rules_path(storage_dir))
    try:
        matched_rules = matching_rules_for_message(current, memory.list_rules())
    except (OSError, KeyError, TypeError, ValueError):
        return []
    return [
        {
            "id": rule.id,
            "label": rule.label,
            "instruction": rule.instruction,
            "scope": rule.scope,
        }
        for rule in matched_rules[:limit]
    ]


def _label_note_aliases(label: str) -> tuple[str, ...]:
    normalized = str(label or "").strip().lower().replace("_", " ").replace("-", " ")
    aliases = {normalized}
    if label == "job-related":
        aliases.update({"work", "work email", "job related", "job"})
    return tuple(alias for alias in aliases if alias)


def _note_explicitly_rejects_label(note: str, label: str) -> bool:
    text = " ".join(str(note or "").lower().split())
    if not text or not label:
        return False
    for alias in _label_note_aliases(label):
        escaped = re.escape(alias)
        if re.search(
            rf"\b(?:not|never|isn't|is not|aren't|are not|doesn't|does not|don't|do not)"
            rf"(?:\s+(?:be|an?|the|any))?\s+{escaped}\b",
            text,
        ):
            return True
        if re.search(
            rf"\b(?:exclude|without|never include|do not include|does not include)"
            rf"(?:\s+(?:an?|the|any))?\s+{escaped}\b",
            text,
        ):
            return True
        if re.search(rf"\b{escaped}\b\s+(?:is|are|was|were)?\s*(?:wrong|incorrect|not applicable|not wanted)\b", text):
            return True
    return False


def apply_label_to_message(
    storage_dir: Path,
    *,
    batch_id: str,
    message_id: str,
    label: str,
    labels: list[str] | None = None,
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
        final_labels = list(labels) if labels is not None else [label]
        item["final_labels"] = final_labels
        item["applied_labels"] = final_labels
        if labels is not None:
            item["require_exact_label_set_verification"] = True
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
    if mode == "save-future-rule":
        return {}
    preview_message_ids = {
        match.get("message_id")
        for match in preview_matches
        if match.get("message_id")
    }
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return {}

    target_message_ids = {selected_message_id}
    if mode in {"matching-existing", "apply-included"}:
        target_message_ids.update(preview_message_ids)

    # A message can appear in several stored review snapshots. Gmail must be
    # mutated once, using the newest decision, rather than replaying every
    # historical classification for the same provider message.
    authoritative_items: dict[str, tuple[str, dict]] = {}
    for batch_path in sorted(batches_dir.glob("*.json"), key=artifact_path_sort_key):
        batch = load_json(batch_path)
        batch_id = batch.get("batch_id", "")
        for item in batch.get("items", []):
            message_id = item.get("message_id")
            if message_id in target_message_ids:
                authoritative_items[message_id] = (batch_id, item)

    batches: dict[str, list[dict]] = {}
    for batch_id, item in authoritative_items.values():
        batches.setdefault(batch_id, []).append(item)
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
        future_copy = (
            "saved a future rule"
            if future_rule_saved
            else "did not save a future rule"
        )
        return (
            f"I relabeled this email to {label_name}, rewrote {matched_existing_count} included stored emails, "
            f"kept {exceptions_saved_count} saved exceptions, and {future_copy}."
        )
    if mode == "save-future-rule":
        return f"I saved a future rule. I did not relabel this email or rewrite other existing emails."
    if mode == "future-only":
        return f"I relabeled this email to {label_name} and saved a future rule. No other existing stored emails were rewritten."
    return f"I applied the teaching action for {label_name}."
