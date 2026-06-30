from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from src.gmail_batch_review_store import GmailBatchReviewStore
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import (
    inbox_removal_status_path,
    load_json,
    load_json_or_default,
    memory_proposals_path,
    reports_dir,
    teachable_rules_path,
    write_status_path,
)
from src.memory_proposal_store import build_memory_proposal, load_storage_items
from src.sender_utils import normalized_sender_email
from src.unsubscribe_execution import UnsubscribeExecutor
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore


def selected_context_from_query(query: dict[str, list[str]]) -> dict:
    return {
        "provider": first_query_value(query, "provider"),
        "message_id": first_query_value(query, "message_id"),
        "thread_id": first_query_value(query, "thread_id"),
        "subject": first_query_value(query, "subject"),
        "sender": first_query_value(query, "sender"),
        "page_url": first_query_value(query, "page_url"),
        "selected_at": first_query_value(query, "selected_at"),
    }

def first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or [""]
    return values[0]

def build_selected_email_state(storage_dir: Path, unsubscribe_candidates: list[dict], selected_context: dict) -> dict:
    matched = find_matching_item(storage_dir, selected_context)
    if matched is None:
        has_context = bool(selected_context.get("message_id") or selected_context.get("subject") or selected_context.get("sender"))
        return {
            "found": False,
            "internal_label": None,
            "suggested_label": None,
            "classification": None,
            "status": "not-in-snapshot" if has_context else "idle",
            "status_label": "Not in local snapshot" if has_context else "Waiting for message selection",
            "reason": (
                "This Gmail message is not in the current local sync yet. Run a fresh Gmail sync to classify it and apply the latest rules."
                if has_context
                else None
            ),
            "subject": selected_context.get("subject") or "",
            "sender": selected_context.get("sender") or "",
            "unsubscribe_available": False,
            "unsubscribe": None,
        }

    item = matched["item"]
    batch = matched["batch"]
    labels = list(item.get("final_labels") or item.get("applied_labels") or [])
    classification = gmail_label_name(labels[0]) if labels else "Uncategorized"
    write_status = load_json_or_default(write_status_path(storage_dir, batch["batch_id"]), {}).get(item["message_id"])
    inbox_status = load_json_or_default(inbox_removal_status_path(storage_dir, batch["batch_id"]), {}).get(item["message_id"])
    status, status_label = classify_handling_status(item, write_status, inbox_status)
    candidate = find_unsubscribe_candidate(unsubscribe_candidates, item.get("sender") or selected_context.get("sender") or "")
    unsubscribe_available = candidate is not None
    return {
        "found": True,
        "provider": batch.get("provider", "gmail"),
        "account_id": batch.get("account_id"),
        "batch_id": batch.get("batch_id"),
        "message_id": item.get("message_id"),
        "internal_label": labels[0] if labels else None,
        "suggested_label": suggested_label_for_item(item),
        "classification": classification,
        "status": status,
        "status_label": status_label,
        "reason": item.get("interpretation") or item.get("snippet") or "",
        "details": build_selected_email_details(item, write_status, inbox_status, candidate),
        "subject": item.get("subject") or selected_context.get("subject") or "",
        "sender": item.get("sender") or selected_context.get("sender") or "",
        "unsubscribe_available": unsubscribe_available,
        "unsubscribe": build_unsubscribe_detail(candidate, storage_dir) if candidate else None,
    }

def classify_handling_status(item: dict, write_status: str | None, inbox_status: str | None) -> tuple[str, str]:
    labels = item.get("final_labels") or item.get("applied_labels") or []
    if not labels or item.get("review_state") != "reviewed":
        return "needs-attention", "Needs attention"
    if inbox_status == "applied":
        return "auto-handled", "Auto-handled"
    if write_status == "applied":
        return "kept-visible", "Kept visible"
    if item.get("review_action") == "auto-approve":
        return "auto-labeled", "Auto-labeled"
    return "kept-visible", "Kept visible"

def suggested_label_for_item(item: dict) -> str | None:
    labels = item.get("final_labels") or item.get("applied_labels") or []
    if labels:
        return labels[0]
    for candidate in item.get("near_misses") or []:
        if candidate in CANONICAL_LABEL_ORDER:
            return candidate
    return None

def find_unsubscribe_candidate(candidates: list[dict], sender: str) -> dict | None:
    sender_address = normalized_sender_email(sender or "")
    if not sender_address:
        return None
    for candidate in candidates:
        if candidate.get("sender_address") == sender_address:
            return candidate
    return None

def build_unsubscribe_detail(candidate: dict | None, storage_dir: Path) -> dict | None:
    if candidate is None:
        return None
    preview = UnsubscribeExecutor(storage_dir)._build_preview_item(candidate)
    return {
        "list_key": candidate.get("list_key"),
        "display_name": candidate.get("display_name"),
        "sender": candidate.get("sender"),
        "sender_address": candidate.get("sender_address"),
        "decision_state": candidate.get("decision_state", "undecided"),
        "evidence_count": candidate.get("evidence_count", 0),
        "qualification_reasons": list(candidate.get("qualification_reasons") or []),
        "latest_execution": candidate.get("latest_execution"),
        "preview": preview,
        "handoff_path": f"/unsubscribe-review?{urlencode({'list_key': candidate.get('list_key', '')})}",
    }

def build_selected_email_details(
    item: dict,
    write_status: str | None,
    inbox_status: str | None,
    unsubscribe_candidate: dict | None,
) -> dict:
    matched_rules = item.get("matched_teachable_rules") or []
    return {
        "review_action": item.get("review_action") or "",
        "write_status": write_status or "",
        "inbox_status": inbox_status or "",
        "matched_rule_count": len(matched_rules),
        "matched_rule_ids": [rule.get("id") for rule in matched_rules if rule.get("id")],
        "unsubscribe_reasons": list((unsubscribe_candidate or {}).get("qualification_reasons") or []),
    }

def build_daily_summary(storage_dir: Path) -> dict:
    recent_reports = load_recent_reports(storage_dir, limit=5, provider="gmail")
    if recent_reports:
        label_counts = Counter()
        processed_count = 0
        auto_handled_count = 0
        needs_attention_count = 0
        latest_report = recent_reports[-1]
        for report in recent_reports:
            processed_count += report.get("processed_count", 0)
            auto_handled_count += report.get("inbox_removed_count", 0)
            needs_attention_count += report.get("unlabeled_count", 0)
            label_counts.update(report.get("label_counts") or report.get("suggested_label_counts") or {})
        top_labels = [
            {"label": label, "count": count}
            for label, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ]
        unsubscribe_count = len(UnsubscribeInventoryStore(storage_dir).list_candidates())
        changed_today = build_changed_today_summary(storage_dir, latest_report.get("batch_id") or "")
        return {
            "source_label": f"last {len(recent_reports)} Gmail runs",
            "batch_id": latest_report.get("batch_id"),
            "report_date": latest_report.get("report_date"),
            "processed_count": processed_count,
            "auto_handled_count": auto_handled_count,
            "needs_attention_count": needs_attention_count,
            "unlabeled_count": needs_attention_count,
            "top_labels": top_labels,
            "run_count": len(recent_reports),
            "unsubscribe_candidate_count": unsubscribe_count,
            "changed_today": changed_today,
        }

    latest_batch = load_latest_batch(storage_dir)
    if latest_batch is None:
        return {
            "source_label": "no stored Gmail data yet",
            "batch_id": None,
            "report_date": None,
            "processed_count": 0,
            "auto_handled_count": 0,
            "needs_attention_count": 0,
            "unlabeled_count": 0,
            "top_labels": [],
            "run_count": 0,
            "unsubscribe_candidate_count": 0,
        }

    items = latest_batch.get("items", [])
    label_counts = Counter(
        gmail_label_name(label)
        for item in items
        for label in (item.get("final_labels") or item.get("applied_labels") or [])
    )
    auto_handled_count = sum(
        1
        for status in load_json_or_default(inbox_removal_status_path(storage_dir, latest_batch["batch_id"]), {}).values()
        if status == "applied"
    )
    needs_attention = sum(
        1 for item in items if item.get("review_state") != "reviewed" or not (item.get("final_labels") or item.get("applied_labels"))
    )
    return {
        "source_label": "latest stored batch",
        "batch_id": latest_batch.get("batch_id"),
        "report_date": None,
        "processed_count": len(items),
        "auto_handled_count": auto_handled_count,
        "needs_attention_count": needs_attention,
        "unlabeled_count": needs_attention,
        "top_labels": [
            {"label": label, "count": count}
            for label, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        ],
        "run_count": 1,
        "unsubscribe_candidate_count": len(UnsubscribeInventoryStore(storage_dir).list_candidates()),
        "changed_today": build_changed_today_summary(storage_dir, latest_batch.get("batch_id") or ""),
    }

def build_changed_today_summary(storage_dir: Path, batch_id: str) -> dict:
    if not batch_id:
        return {
            "label_writes_count": 0,
            "inbox_removed_count": 0,
            "taught_count": 0,
            "selected_unsubscribe_count": 0,
            "items": [],
            "selected_unsubscribe_examples": [],
        }
    batch = load_json_or_default(storage_dir / "batches" / f"{batch_id}.json", {})
    items = batch.get("items", [])
    write_status_map = load_json_or_default(write_status_path(storage_dir, batch_id), {})
    inbox_status_map = load_json_or_default(inbox_removal_status_path(storage_dir, batch_id), {})
    changed_items = []
    label_writes_count = 0
    inbox_removed_count = 0
    taught_count = 0
    for item in items:
        message_id = item.get("message_id", "")
        write_status = write_status_map.get(message_id)
        inbox_status = inbox_status_map.get(message_id)
        review_action = item.get("review_action") or ""
        change_summary = ""
        if inbox_status == "applied":
            inbox_removed_count += 1
            change_summary = "Removed from inbox as low-value mail."
        elif write_status == "applied":
            label_writes_count += 1
            change_summary = f"Applied {gmail_label_name((item.get('final_labels') or item.get('applied_labels') or [''])[0])} in Gmail."
        elif review_action.startswith("sidebar-"):
            taught_count += 1
            change_summary = "Changed from inbox teaching feedback."
        if not change_summary:
            continue
        changed_items.append(
            {
                "message_id": message_id,
                "subject": item.get("subject", ""),
                "sender": item.get("sender", ""),
                "change_summary": change_summary,
            }
        )
    selected_candidates = [
        candidate
        for candidate in UnsubscribeInventoryStore(storage_dir).list_candidates()
        if candidate.get("decision_state") == "selected"
    ]
    selected_unsubscribe_count = len(selected_candidates)
    selected_unsubscribe_examples = [
        {
            "display_name": candidate.get("display_name") or "(unknown list)",
            "sender": candidate.get("sender") or "",
            "handoff_path": f"/unsubscribe-review?{urlencode({'list_key': candidate.get('list_key', '')})}",
        }
        for candidate in selected_candidates
    ][:3]
    return {
        "label_writes_count": label_writes_count,
        "inbox_removed_count": inbox_removed_count,
        "taught_count": taught_count,
        "selected_unsubscribe_count": selected_unsubscribe_count,
        "items": changed_items[:6],
        "selected_unsubscribe_examples": selected_unsubscribe_examples,
    }

def build_companion_runtime_payload(storage_dir: Path) -> dict:
    items = []
    batches_dir = storage_dir / "batches"
    unsubscribe_candidates = UnsubscribeInventoryStore(storage_dir).list_candidates()
    unsubscribe_addresses = {
        candidate.get("sender_address")
        for candidate in unsubscribe_candidates
        if candidate.get("sender_address")
    }
    if batches_dir.exists():
        recent_batch_paths = sorted(batches_dir.glob("*.json"), reverse=True)[:4]
        for batch_path in recent_batch_paths:
            batch = load_json(batch_path)
            batch_id = batch.get("batch_id", "")
            write_status_map = load_json_or_default(write_status_path(storage_dir, batch_id), {})
            inbox_status_map = load_json_or_default(inbox_removal_status_path(storage_dir, batch_id), {})
            for item in batch.get("items", [])[:25]:
                labels = list(item.get("final_labels") or item.get("applied_labels") or [])
                classification = gmail_label_name(labels[0]) if labels else "Uncategorized"
                sender_address = normalized_sender_email(item.get("sender") or "")
                status, status_label = classify_handling_status(
                    item,
                    write_status_map.get(item.get("message_id", "")),
                    inbox_status_map.get(item.get("message_id", "")),
                )
                items.append(
                    {
                        "provider": batch.get("provider", "gmail"),
                        "account_id": batch.get("account_id", ""),
                        "batch_id": batch_id,
                        "message_id": item.get("message_id", ""),
                        "subject": item.get("subject", ""),
                        "subject_key": (item.get("subject") or "").strip().lower(),
                        "sender": item.get("sender", ""),
                        "sender_address": sender_address,
                        "internal_label": labels[0] if labels else None,
                        "suggested_label": suggested_label_for_item(item),
                        "classification": classification,
                        "status": status,
                        "status_label": status_label,
                        "reason": item.get("interpretation") or item.get("snippet") or "",
                        "unsubscribe_available": sender_address in unsubscribe_addresses,
                    }
                )
            if len(items) >= 80:
                break
    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "daily_summary": build_daily_summary(storage_dir),
        "items": items[:80],
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

def load_latest_report(storage_dir: Path) -> dict | None:
    matches = sorted(reports_dir(storage_dir).glob("*_daily_report.json")) if reports_dir(storage_dir).exists() else []
    if not matches:
        return None
    return load_json(matches[-1])

def load_recent_reports(storage_dir: Path, limit: int = 5, provider: str | None = None) -> list[dict]:
    matches = sorted(reports_dir(storage_dir).glob("*_daily_report.json")) if reports_dir(storage_dir).exists() else []
    reports = []
    for path in matches:
        report = load_json(path)
        if provider and report.get("provider") != provider:
            continue
        reports.append(report)
    return reports[-limit:]

def load_latest_batch(storage_dir: Path) -> dict | None:
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return None
    matches = sorted(batches_dir.glob("*.json"))
    if not matches:
        return None
    return load_json(matches[-1])

def find_matching_item(storage_dir: Path, selected_context: dict) -> dict | None:
    message_id = selected_context.get("message_id") or ""
    normalized_selected_sender = normalized_sender_email(selected_context.get("sender") or "")
    normalized_subject = (selected_context.get("subject") or "").strip().lower()
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return None
    for batch_path in sorted(batches_dir.glob("*.json"), reverse=True):
        batch = load_json(batch_path)
        for item in batch.get("items", []):
            if message_id and item.get("message_id") == message_id:
                return {"batch": batch, "item": item}
            if normalized_subject and normalized_selected_sender:
                sender = normalized_sender_email(item.get("sender") or "")
                subject = (item.get("subject") or "").strip().lower()
                if sender == normalized_selected_sender and subject == normalized_subject:
                    return {"batch": batch, "item": item}
    return None

def selected_email_contract() -> dict:
    return {
        "contract_version": "gmail-companion-selected-email-v1",
        "selected_context_fields": [
            "provider",
            "message_id",
            "thread_id",
            "subject",
            "sender",
            "page_url",
            "selected_at",
        ],
        "sidebar_state_fields": [
            "contract_version",
            "generated_at",
            "selected_context",
            "selected_email",
            "daily_summary",
            "ui_state",
        ],
        "matching_rules": {
            "primary": "message_id exact match",
            "fallback": "sender plus subject match against stored batch items",
        },
    }
