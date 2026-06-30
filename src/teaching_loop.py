from pathlib import Path

from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_companion_state import find_matching_item
from src.label_taxonomy import gmail_label_name
from src.local_artifacts import load_json, memory_proposals_path, teachable_rules_path
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal, load_storage_items
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRuleMemory


VALID_TEACHING_APPLY_MODES = {"current-only", "matching-existing", "future-only"}


def build_sidebar_teach_preview(
    storage_dir: Path,
    *,
    selected_context: dict,
    target_label: str,
    note: str,
    scope: str,
) -> dict:
    current = load_selected_storage_item(storage_dir, selected_context)
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
        "selected_label_before": list(current.get("final_labels") or current.get("applied_labels") or []),
        "selected_label_after": [target_label],
        "proposal": proposal.to_dict(),
        "impact": {
            "current_message_will_change": True,
            "matching_existing_count": len(affected_existing),
            "matching_existing_examples": normalized_existing[:5],
            "scope": scope,
        },
        "options": [
            {"id": "current-only", "label": "Apply only here"},
            {"id": "matching-existing", "label": "Apply to matching emails too"},
            {"id": "future-only", "label": "Use for future emails only"},
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

    current = load_selected_storage_item(storage_dir, selected_context)
    proposal = build_companion_memory_proposal(
        storage_dir,
        current=current,
        target_label=target_label,
        note=note,
        scope=scope,
    )

    apply_label_to_message(
        storage_dir,
        batch_id=current["batch_id"],
        message_id=current["message_id"],
        label=target_label,
        note=note,
        review_action="sidebar-current-only" if mode == "current-only" else f"sidebar-{mode}",
    )

    matched_existing_count = 0
    proposal_record = None
    if mode in {"matching-existing", "future-only"}:
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
    if mode == "future-only":
        return f"I relabeled this email to {label_name} and saved a sender-level lesson for future mail. No other existing stored emails were rewritten."
    return f"I relabeled this email to {label_name}, rewrote {matched_existing_count} matching stored emails, and saved the sender-level lesson for future mail."
