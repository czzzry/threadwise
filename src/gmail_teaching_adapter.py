from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from src.companion_teaching_workflow import TeachingWriteRequest
from src.gmail_message_normalizer import normalize_gmail_message
from src.gmail_writer import MockGmailLabelWriter
from src.label_taxonomy import gmail_label_name
from src.live_gmail_client import GMAIL_MODIFY_SCOPE
from src.local_artifacts import write_json_artifact
from src.semantic_rule_matching import (
    semantic_gmail_search_clauses,
    semantic_rule_matches_message,
    semantic_search_keywords,
)
from src.teaching_loop import load_items_for_gmail_write_through


INBOX_BACKFILL_CONFIRM_THRESHOLD = 200
INBOX_BACKFILL_ESTIMATE_CAP = 25


class GmailTeachingAdapter:
    """Own Gmail-specific preview and mutation mechanics for companion teaching."""

    def __init__(
        self,
        storage_dir: Path,
        *,
        credentials_dir: Path,
        client_secret_path: Path | None,
        gmail_client_factory,
        write_enabled: bool = True,
    ) -> None:
        self._storage_dir = storage_dir
        self._credentials_dir = credentials_dir
        self._client_secret_path = client_secret_path
        self._gmail_client_factory = gmail_client_factory
        self._write_enabled = write_enabled

    def apply(self, request: TeachingWriteRequest) -> dict:
        if request.mode == "save-future-rule":
            return _write_summary("no-gmail-write-future-rule-only")
        if not self._write_enabled:
            return _write_summary("disabled")
        try:
            gmail_client = self._gmail_client(request.account_id)
        except Exception as exc:
            return {
                **_write_summary("gmail-write-failed"),
                "error": str(exc),
            }

        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=self._storage_dir,
            label_name_resolver=gmail_label_name,
        )
        batch_items = load_items_for_gmail_write_through(
            self._storage_dir,
            selected_message_id=request.current_message_id,
            mode=request.mode,
            preview_matches=request.preview_matches,
        )
        totals = {
            "messages_written": 0,
            "label_write_failed": 0,
            "label_write_skipped": 0,
            "inbox_removed": 0,
            "inbox_remove_failed": 0,
            "inbox_remove_skipped": 0,
            "inbox_remove_ineligible": 0,
        }
        for batch_id, items in batch_items.items():
            mutation = writer.apply_reviewed_mutations(batch_id, items)
            _add_mutation_totals(totals, mutation)

        remote = _empty_remote_mutation_summary()
        if request.mode == "apply-included":
            local_ids = {
                item.get("message_id")
                for items in batch_items.values()
                for item in items
                if item.get("message_id")
            }
            remote = self._apply_included_messages(
                gmail_client,
                account_id=request.account_id,
                semantic_rule=request.semantic_rule,
                excluded_message_ids=local_ids,
                included_message_ids=set(request.included_message_ids),
            )
            totals["messages_written"] += remote["applied_count"]
            totals["label_write_failed"] += remote["failed_count"]
            totals["label_write_skipped"] += remote["skipped_count"]
            totals["inbox_removed"] += remote["inbox_removed_count"]
            totals["inbox_remove_failed"] += remote["inbox_failed_count"]
            totals["inbox_remove_skipped"] += remote["inbox_skipped_count"]
            totals["inbox_remove_ineligible"] += remote["inbox_ineligible_count"]

        return {
            **totals,
            "remote_match_count": remote["matched_count"],
            "remote_applied_count": remote["applied_count"],
            "remote_failed_count": remote["failed_count"],
            "remote_skipped_count": remote["skipped_count"],
            "remote_batch_id": remote["batch_id"],
            "remote_inbox_removed_count": remote["inbox_removed_count"],
            "remote_inbox_failed_count": remote["inbox_failed_count"],
            "remote_inbox_skipped_count": remote["inbox_skipped_count"],
            "remote_inbox_ineligible_count": remote["inbox_ineligible_count"],
            "mode": "applied",
        }

    def preview_backfill(self, preview: dict) -> dict:
        if not self._write_enabled:
            return _unavailable_preview()
        account_id = preview.get("selected_account_id") or ""
        query = _build_backfill_query(
            semantic_rule=preview.get("semantic_rule") or {},
            current_subject=preview.get("selected_subject") or "",
            current_sender=preview.get("selected_sender") or "",
        )
        if not account_id or not query:
            return _unavailable_preview(query=query)
        try:
            gmail_client = self._gmail_client(account_id)
            candidate_ids = gmail_client.search_message_ids(
                query,
                INBOX_BACKFILL_ESTIMATE_CAP + 1,
            )
        except Exception:
            return _unavailable_preview(query=query)
        if not hasattr(gmail_client, "get_message"):
            return {
                **_unavailable_preview(query=query),
                "is_capped": len(candidate_ids) > INBOX_BACKFILL_ESTIMATE_CAP,
            }

        semantic_rule = preview.get("semantic_rule") or {}
        selected_id = str(preview.get("selected_message_id") or "")
        seen: set[str] = set()
        inspect_ids: list[str] = []
        for message_id in candidate_ids[:INBOX_BACKFILL_ESTIMATE_CAP]:
            if not message_id or message_id == selected_id or message_id in seen:
                continue
            seen.add(message_id)
            inspect_ids.append(message_id)

        def inspect_message(message_id: str) -> dict | None:
            try:
                normalized = normalize_gmail_message(
                    account_id,
                    gmail_client.get_message(message_id),
                )
            except Exception:
                return None
            if not semantic_rule_matches_message(semantic_rule, normalized):
                return None
            return {
                **normalized,
                "labels_before": [],
                "labels_after": [
                    preview.get("semantic_rule", {}).get("target_label")
                    or (preview.get("selected_label_after") or [""])[0]
                ],
                "source": "gmail-live-preview",
            }

        inspected_matches: list[dict] = []
        if inspect_ids:
            worker_count = min(16, len(inspect_ids))
            with ThreadPoolExecutor(
                max_workers=worker_count,
                thread_name_prefix="threadwise-preview",
            ) as executor:
                inspected_matches = [
                    match
                    for match in executor.map(inspect_message, inspect_ids)
                    if match
                ]
        estimated_count = len(inspected_matches)
        capped = len(candidate_ids) > INBOX_BACKFILL_ESTIMATE_CAP
        return {
            "available": True,
            "estimated_count": estimated_count,
            "is_capped": capped,
            "requires_confirmation": (
                estimated_count > INBOX_BACKFILL_CONFIRM_THRESHOLD or capped
            ),
            "query": query,
            "matches": inspected_matches,
        }

    def _gmail_client(self, account_id: str):
        return self._gmail_client_factory(
            account_id,
            self._credentials_dir,
            self._client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )

    def _apply_included_messages(
        self,
        gmail_client,
        *,
        account_id: str,
        semantic_rule: dict,
        excluded_message_ids: set[str],
        included_message_ids: set[str],
    ) -> dict:
        filtered_ids = sorted(
            message_id
            for message_id in included_message_ids
            if message_id and message_id not in excluded_message_ids
        )
        target_label = (semantic_rule or {}).get("target_label") or ""
        if not gmail_label_name(target_label):
            return {
                **_empty_remote_mutation_summary(),
                "matched_count": len(filtered_ids),
                "skipped_count": len(filtered_ids),
            }
        if not filtered_ids:
            return _empty_remote_mutation_summary()
        batch_id = f"gmail-companion-backfill-{uuid4().hex}"
        reviewed_items = [
            {
                "source": "gmail",
                "account_id": account_id,
                "message_id": message_id,
                "review_state": "reviewed",
                "review_action": "sidebar-remote-backfill",
                "applied_labels": [target_label],
                "final_labels": [target_label],
            }
            for message_id in filtered_ids
        ]
        write_json_artifact(
            "gmail_mutation_batch",
            self._storage_dir,
            {
                "batch_id": batch_id,
                "provider": "gmail",
                "account_id": account_id,
                "items": reviewed_items,
            },
            batch_id,
        )
        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=self._storage_dir,
            label_name_resolver=gmail_label_name,
        )
        mutation = writer.apply_reviewed_mutations(batch_id, reviewed_items)
        write_summary = mutation["write_summary"]
        inbox_summary = mutation["inbox_summary"]
        return {
            "matched_count": len(filtered_ids),
            "applied_count": write_summary["applied_count"],
            "failed_count": write_summary["failed_count"],
            "skipped_count": write_summary["skipped_count"],
            "batch_id": batch_id,
            "inbox_removed_count": inbox_summary["applied_count"],
            "inbox_failed_count": inbox_summary["failed_count"],
            "inbox_skipped_count": inbox_summary["skipped_count"],
            "inbox_ineligible_count": inbox_summary["ineligible_count"],
        }


def _write_summary(mode: str) -> dict:
    return {
        "messages_written": 0,
        "inbox_removed": 0,
        "label_write_failed": 0,
        "label_write_skipped": 0,
        "inbox_remove_failed": 0,
        "inbox_remove_skipped": 0,
        "inbox_remove_ineligible": 0,
        "mode": mode,
    }


def _add_mutation_totals(totals: dict, mutation: dict) -> None:
    write_summary = mutation["write_summary"]
    inbox_summary = mutation["inbox_summary"]
    totals["messages_written"] += write_summary["applied_count"]
    totals["label_write_failed"] += write_summary["failed_count"]
    totals["label_write_skipped"] += write_summary["skipped_count"]
    totals["inbox_removed"] += inbox_summary["applied_count"]
    totals["inbox_remove_failed"] += inbox_summary["failed_count"]
    totals["inbox_remove_skipped"] += inbox_summary["skipped_count"]
    totals["inbox_remove_ineligible"] += inbox_summary["ineligible_count"]


def _unavailable_preview(*, query: str = "") -> dict:
    return {
        "available": False,
        "estimated_count": 0,
        "requires_confirmation": False,
        "query": query,
        "matches": [],
    }


def _empty_remote_mutation_summary() -> dict:
    return {
        "matched_count": 0,
        "applied_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "batch_id": "",
        "inbox_removed_count": 0,
        "inbox_failed_count": 0,
        "inbox_skipped_count": 0,
        "inbox_ineligible_count": 0,
    }


def _build_backfill_query(
    *,
    semantic_rule: dict,
    current_subject: str,
    current_sender: str,
) -> str:
    sender = (semantic_rule or {}).get("sender") or current_sender or ""
    sender_domain = str((semantic_rule or {}).get("sender_domain") or "").strip().lower().lstrip("@")
    semantic_pattern = (semantic_rule or {}).get("semantic_pattern") or ""
    rule_type = (semantic_rule or {}).get("rule_type") or ""
    if rule_type == "sender-domain" and sender_domain:
        return f"from:{sender_domain}"
    include_clauses, exclude_clauses = semantic_gmail_search_clauses(semantic_rule)
    subject_keywords = semantic_search_keywords(semantic_rule) or _query_keywords(
        semantic_pattern,
        current_subject,
    )
    parts: list[str] = []
    if sender and "@" in sender and rule_type != "cross-sender-semantic":
        parts.append(f"from:{sender}")
    if include_clauses:
        if len(include_clauses) == 1:
            parts.append(include_clauses[0])
        else:
            parts.append("{" + " ".join(include_clauses) + "}")
        parts.extend(exclude_clauses)
    elif subject_keywords:
        if len(subject_keywords) == 1:
            parts.append(subject_keywords[0])
        else:
            parts.append("{" + " ".join(subject_keywords) + "}")
    elif rule_type == "sender":
        return " ".join(parts)
    return " ".join(part for part in parts if part).strip()


def _query_keywords(semantic_pattern: str, current_subject: str) -> list[str]:
    pattern = str(semantic_pattern or "").lower()
    mappings = {
        "job, recruiter, or interview emails": ["job", "jobs", "recruiter", "interview", "application"],
        "billing, receipt, or payment notices": ["receipt", "invoice", "payment", "billing"],
        "travel and booking emails": ["travel", "flight", "hotel", "booking"],
        "newsletter or marketing emails": ["newsletter", "promo", "sale", "digest"],
        "account, security, or statement notices": ["security", "account", "statement", "login"],
        "financial account notices": ["account", "statement", "payment"],
        "low-value or suspicious emails": ["alert", "promo", "notice"],
    }
    if pattern in mappings:
        return mappings[pattern]
    words = []
    for raw in (current_subject or "").lower().split():
        clean = "".join(ch for ch in raw if ch.isalnum())
        if len(clean) < 4 or clean in {"this", "that", "from", "with", "more", "your", "have"}:
            continue
        words.append(clean)
        if len(words) == 3:
            break
    return words
