from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from src.attention_feedback import load_attention_feedback
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import (
    inbox_removal_status_path,
    load_json,
    load_json_or_default,
    reports_dir,
    write_status_path,
)
from src.sender_utils import normalized_sender_email
from src.unsubscribe_execution import UnsubscribeExecutor
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore


HIGH_CONSEQUENCE_ATTENTION_CATEGORIES = {
    "travel",
    "bill_due",
    "account_risk",
    "security",
    "reply_deadline",
    "appointment",
    "job_opportunity",
}


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

def build_daily_attention_summary(storage_dir: Path) -> dict:
    recent_reports = load_recent_reports(storage_dir, limit=1, provider="gmail")
    if not recent_reports:
        return empty_daily_attention_summary("No Gmail daily report with attention data yet.")

    report = recent_reports[-1]
    attention = report.get("attention") or {}
    item_index = build_attention_context_index(storage_dir)
    feedback_entries = load_attention_feedback(storage_dir).get("entries", {})
    now_items = []
    possible_items = []
    hidden_insufficient_context_count = 0
    seen_feedback_keys = set()
    for item in attention.get("items") or []:
        feedback = find_attention_feedback(feedback_entries, item.get("message_id", ""), item.get("thread_id", ""))
        if feedback:
            seen_feedback_keys.add(attention_feedback_key(feedback.get("message_id", ""), feedback.get("thread_id", "")))
        if feedback.get("dismissed"):
            continue
        level = item.get("level") or ""
        if level == "needs_attention_now":
            now_items.append(enrich_attention_item(item, report, item_index, feedback))
            continue
        if level == "possible_attention":
            possible_items.append(enrich_attention_item(item, report, item_index, feedback))
            continue
        if level == "insufficient_context":
            if is_high_consequence_attention_item(item):
                possible_items.append(enrich_attention_item(item, report, item_index, feedback))
            else:
                hidden_insufficient_context_count += 1
    for feedback in feedback_entries.values():
        if not feedback.get("manual_attention") or feedback.get("dismissed"):
            continue
        key = attention_feedback_key(feedback.get("message_id", ""), feedback.get("thread_id", ""))
        if key in seen_feedback_keys:
            continue
        now_items.append(enrich_attention_item(manual_attention_item_from_feedback(feedback), report, item_index, feedback))

    return {
        "source_label": "latest Gmail daily report",
        "batch_id": report.get("batch_id", ""),
        "report_date": report.get("report_date", ""),
        "schema_version": attention.get("schema_version"),
        "evaluated_message_count": attention.get("evaluated_message_count", 0),
        "grouped_counts": attention.get("grouped_counts") or {},
        "now_items": now_items,
        "possible_items": possible_items,
        "hidden_insufficient_context_count": hidden_insufficient_context_count,
        "has_attention_contract": "attention" in report,
        "empty_reason": "" if "attention" in report else "The latest Gmail daily report does not include an attention section yet.",
    }

def empty_daily_attention_summary(reason: str) -> dict:
    return {
        "source_label": "no attention report",
        "batch_id": "",
        "report_date": "",
        "schema_version": None,
        "evaluated_message_count": 0,
        "grouped_counts": {},
        "now_items": [],
        "possible_items": [],
        "hidden_insufficient_context_count": 0,
        "has_attention_contract": False,
        "empty_reason": reason,
    }

def build_attention_context_index(storage_dir: Path) -> dict[str, dict[str, dict]]:
    by_message_id: dict[str, dict] = {}
    by_thread_id: dict[str, dict] = {}
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return {"message_id": by_message_id, "thread_id": by_thread_id}

    for batch_path in sorted(batches_dir.glob("*.json"), reverse=True):
        batch = load_json(batch_path)
        batch_id = batch.get("batch_id", "")
        for item in batch.get("items", []):
            context = {
                "batch_id": batch_id,
                "subject": item.get("subject", ""),
                "sender": item.get("sender", ""),
                "message_id": item.get("message_id", ""),
                "thread_id": item.get("thread_id", ""),
            }
            message_id = context["message_id"]
            thread_id = context["thread_id"]
            if message_id and message_id not in by_message_id:
                by_message_id[message_id] = context
            if thread_id and thread_id not in by_thread_id:
                by_thread_id[thread_id] = context
    return {"message_id": by_message_id, "thread_id": by_thread_id}

def find_attention_feedback(entries: dict, message_id: str, thread_id: str) -> dict:
    if message_id and message_id in entries:
        return entries[message_id]
    thread_key = f"thread:{thread_id}" if thread_id else ""
    if thread_key and thread_key in entries:
        return entries[thread_key]
    for entry in entries.values():
        if thread_id and entry.get("thread_id") == thread_id:
            return entry
    return {}

def attention_feedback_key(message_id: str, thread_id: str) -> str:
    return message_id or (f"thread:{thread_id}" if thread_id else "")

def manual_attention_item_from_feedback(feedback: dict) -> dict:
    return {
        "message_id": feedback.get("message_id", ""),
        "thread_id": feedback.get("thread_id", ""),
        "level": "needs_attention_now",
        "category": feedback.get("corrected_category") or "founder_marked",
        "reason": feedback.get("note") or feedback.get("corrected_reason") or "Founder marked this email as needing attention.",
        "evidence": "Founder feedback marked this stored email as needs attention.",
        "source": "founder_marked",
        "handled_state": "founder_marked",
        "feedback_state": "mark_needs_attention",
        "gmail_mutation": "none",
    }

def enrich_attention_item(item: dict, report: dict, item_index: dict[str, dict[str, dict]], feedback: dict | None = None) -> dict:
    message_id = item.get("message_id", "")
    thread_id = item.get("thread_id", "")
    context = item_index["message_id"].get(message_id) or item_index["thread_id"].get(thread_id) or {}
    batch_id = context.get("batch_id") or report.get("batch_id", "")
    feedback = feedback or {}
    source_context = attention_source_context(
        source=item.get("source", ""),
        message_id=message_id,
        thread_id=thread_id,
        batch_id=batch_id,
    )
    return {
        "message_id": message_id,
        "thread_id": thread_id,
        "batch_id": batch_id,
        "level": item.get("level", ""),
        "category": item.get("category", ""),
        "reason": item.get("reason", ""),
        "evidence": item.get("evidence", ""),
        "source": item.get("source", ""),
        "source_context": source_context,
        "handled_state": item.get("handled_state", "unknown"),
        "feedback_state": feedback.get("feedback_state") or item.get("feedback_state", "unset"),
        "feedback_note": feedback.get("note", ""),
        "corrected_reason": feedback.get("corrected_reason", ""),
        "corrected_category": feedback.get("corrected_category", ""),
        "creates_broader_rule": bool(feedback.get("creates_broader_rule", False)),
        "gmail_mutation": item.get("gmail_mutation") or "none",
        "subject": context.get("subject") or feedback.get("subject") or "(subject unavailable)",
        "sender": context.get("sender") or feedback.get("sender") or "(sender unavailable)",
        "surface_note": attention_surface_note(item),
    }

def attention_source_context(*, source: str, message_id: str, thread_id: str, batch_id: str) -> str:
    parts = []
    if source:
        parts.append(source)
    if message_id:
        parts.append(f"Gmail message {message_id}")
    if thread_id:
        parts.append(f"thread {thread_id}")
    if batch_id:
        parts.append(f"batch {batch_id}")
    return " | ".join(parts) if parts else "Source message context unavailable"

def attention_surface_note(item: dict) -> str:
    if item.get("level") == "insufficient_context":
        return "Insufficient context, high-consequence cue"
    return item.get("handled_state") or "unknown"

def is_high_consequence_attention_item(item: dict) -> bool:
    category = (item.get("category") or "").strip()
    if category in HIGH_CONSEQUENCE_ATTENTION_CATEGORIES:
        return True
    text = " ".join(
        str(item.get(key) or "").lower()
        for key in ("reason", "evidence")
    )
    high_consequence_terms = (
        "account closure",
        "suspension",
        "service interruption",
        "security",
        "payment deadline",
        "bill",
        "flight",
        "interview",
        "reply deadline",
    )
    return any(term in text for term in high_consequence_terms)

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
        "recent_items": items[:24],
        "needs_attention_items": [item for item in items if item.get("status") == "needs-attention"][:12],
        "auto_handled_items": [item for item in items if item.get("status") == "auto-handled"][:12],
        "kept_visible_items": [item for item in items if item.get("status") in {"kept-visible", "auto-labeled"}][:12],
    }

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
