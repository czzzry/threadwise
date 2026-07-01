import re
from pathlib import Path

from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_companion_state import find_matching_item
from src.label_taxonomy import gmail_label_name
from src.local_artifacts import load_json, memory_proposals_path, teachable_rules_path
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal, load_storage_items
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRuleMemory


VALID_TEACHING_APPLY_MODES = {"current-only", "matching-existing", "save-future-rule", "future-only"}


def build_sidebar_teach_preview(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
) -> dict:
    current = load_selected_storage_item(storage_dir, selected_context)
    target_label = resolve_target_label(target_label, note)
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
    )
    preview = proposal.preview
    affected_existing = [
        match for match in preview.get("matches", [])
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
    sender = normalized_sender_email(current.get("sender") or "") or current.get("sender") or "this sender"
    plain_rule = f"Treat similar emails from {sender} as {target_label_name}."
    structured_rule = {
        "scope": scope,
        "sender": sender,
        "from_label": current_label_name,
        "to_label": target_label_name,
        "target_label": target_label,
        "matching_basis": ["sender/domain", "stored Threadwise data", "current label/category"],
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
        "selected_label_before": current_labels,
        "selected_label_after": [target_label],
        "current_label_name": current_label_name,
        "target_label_name": target_label_name,
        "plain_english_rule": plain_rule,
        "structured_rule": structured_rule,
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
            {"id": "current-only", "label": "Apply only here"},
            {"id": "matching-existing", "label": "Apply to matching emails too"},
            {"id": "save-future-rule", "label": "Save future rule only"},
            {"id": "refine", "label": "Refine this"},
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
    target_label = resolve_target_label(target_label, note)

    current = load_selected_storage_item(storage_dir, selected_context)
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
    )

    current_changed = False
    if mode in {"current-only", "matching-existing", "future-only"}:
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
    if mode in {"save-future-rule", "future-only"}:
        store = MemoryProposalStore(memory_proposals_path(storage_dir))
        store.save_proposal(proposal)
        memory = TeachableRuleMemory(teachable_rules_path(storage_dir))
        proposal_record = store.review_proposal(proposal.id, "approved", rules_memory=memory)
    if mode == "matching-existing":
        matched_existing_count = apply_label_to_preview_matches(
            storage_dir,
            proposal.preview.get("matches", []),
            selected_message_id=current["message_id"],
            label=target_label,
            note=note,
        )

    return {
        "acknowledgment": build_apply_acknowledgment(
            current=current,
            target_label=target_label,
            mode=mode,
            matched_existing_count=matched_existing_count,
        ),
        "mode": mode,
        "current_changed": current_changed,
        "matched_existing_count": matched_existing_count,
        "proposal": proposal_record.to_dict() if proposal_record else None,
        "current": current,
        "preview_matches": proposal.preview.get("matches", []),
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


def build_companion_memory_proposal(
    storage_dir: Path,
    *,
    current: dict,
    target_label: str,
    note: str,
    scope: str,
):
    provider = current.get("provider", "gmail")
    explanation = note or f"Messages from {normalized_sender_email(current.get('sender') or '') or current.get('sender') or 'this sender'} should be treated as {target_label}."
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


def resolve_target_label(target_label: str, note: str) -> str:
    target_label = (target_label or "").strip()
    if target_label:
        return target_label
    inferred = infer_target_label_from_note(note)
    if inferred:
        return inferred
    raise ValueError("Choose a label or describe the correction more clearly, for example 'this is spam' or 'this needs a reply'.")


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
    for terms, label in checks:
        if any(term in text for term in terms):
            return label
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
            item["review_action"] = "sidebar-matching-existing"
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
            if mode == "matching-existing" and message_id in preview_message_ids:
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
    sender = normalized_sender_email(current.get("sender") or "") or current.get("sender") or "this sender"
    label_name = gmail_label_name(target_label)
    lesson = f"I think messages from {sender} should usually be {label_name}."
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
) -> str:
    label_name = gmail_label_name(target_label)
    if mode == "current-only":
        return f"I relabeled only this email to {label_name}. I did not change other stored emails or save a broader future rule."
    if mode == "matching-existing":
        return f"I relabeled this email to {label_name} and rewrote {matched_existing_count} matching stored emails. I did not save a future rule."
    if mode == "save-future-rule":
        return f"I saved a sender-level lesson for future mail. I did not relabel this email or rewrite other stored emails."
    if mode == "future-only":
        return f"I relabeled this email to {label_name} and saved a sender-level lesson for future mail. No other existing stored emails were rewritten."
    return f"I applied the teaching action for {label_name}."
