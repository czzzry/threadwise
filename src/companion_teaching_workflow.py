from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.teaching_loop import apply_sidebar_teaching


@dataclass(frozen=True)
class TeachingWriteRequest:
    account_id: str
    current_message_id: str
    mode: str
    preview_matches: list[dict]
    semantic_rule: dict
    current_subject: str
    current_sender: str
    included_message_ids: frozenset[str]


@dataclass(frozen=True)
class TeachingWorkflowResult:
    response: dict
    selected_context: dict
    write_summary: dict


class CompanionTeachingWorkflow:
    """Apply one companion lesson through local state and an injected provider seam."""

    def __init__(
        self,
        storage_dir: Path,
        *,
        write_through: Callable[[TeachingWriteRequest], dict],
    ) -> None:
        self._storage_dir = storage_dir
        self._write_through = write_through

    def apply(self, payload: dict) -> TeachingWorkflowResult:
        selected_context = dict(payload.get("selected_context") or {})
        target_label = payload["target_label"]
        if target_label == "suspicious":
            raise ValueError(
                "Suspicious email requires the explicit Gmail safety preview and confirmation flow."
            )
        included_message_ids = _included_message_ids(payload)
        teaching_result = apply_sidebar_teaching(
            self._storage_dir,
            selected_context=selected_context,
            target_label=target_label,
            note=(payload.get("note") or "").strip(),
            scope=payload.get("scope") or "sender",
            mode=payload["mode"],
            included_message_ids=included_message_ids,
        )
        current = teaching_result["current"]
        write_summary = self._write_through(
            TeachingWriteRequest(
                account_id=current["account_id"],
                current_message_id=current["message_id"],
                mode=teaching_result["mode"],
                preview_matches=list(teaching_result["preview_matches"]),
                semantic_rule={
                    **(teaching_result.get("semantic_rule") or {}),
                    "target_label": target_label,
                },
                current_subject=current.get("subject") or "",
                current_sender=current.get("sender") or "",
                included_message_ids=frozenset(included_message_ids),
            )
        )
        response = {
            "acknowledgment": _apply_acknowledgment(teaching_result, write_summary),
            "mode": teaching_result["mode"],
            "matched_existing_count": teaching_result["matched_existing_count"],
            "proposal": teaching_result["proposal"],
            "gmail_write_through": write_summary,
            "outcome": _apply_outcome(teaching_result, write_summary),
        }
        return TeachingWorkflowResult(
            response=response,
            selected_context=selected_context,
            write_summary=write_summary,
        )


def _included_message_ids(payload: dict) -> list[str]:
    included_message_ids = payload.get("included_message_ids") or []
    if not isinstance(included_message_ids, list) or any(
        not isinstance(message_id, str) or not message_id.strip()
        for message_id in included_message_ids
    ):
        raise ValueError("included_message_ids must be a list of message ids.")
    return included_message_ids


def _apply_acknowledgment(teaching_result: dict, write_summary: dict) -> str:
    base = teaching_result["acknowledgment"]
    gmail_mode = write_summary.get("mode")
    local_changed = int(bool(teaching_result.get("current_changed"))) + int(
        teaching_result.get("matched_existing_count") or 0
    )
    local_email_label = f"email{'' if local_changed == 1 else 's'}"
    if gmail_mode == "no-gmail-write-future-rule-only":
        return f"{base} Gmail was not changed because this action only saved future behavior."
    if gmail_mode == "disabled":
        return (
            f"{base} Stored locally for {local_changed} {local_email_label}. "
            "Gmail write-through is disabled here."
        )
    if gmail_mode == "gmail-write-failed":
        error = write_summary.get("error") or "unknown Gmail write error"
        return (
            f"{base} Stored locally for {local_changed} {local_email_label}, "
            f"but Gmail was not updated: {error}. "
            "Retry Gmail write-through after the connection is healthy."
        )
    messages_written = int(write_summary.get("messages_written") or 0)
    label_failed = int(write_summary.get("label_write_failed") or 0)
    label_skipped = int(write_summary.get("label_write_skipped") or 0)
    inbox_removed = int(write_summary.get("inbox_removed") or 0)
    inbox_failed = int(write_summary.get("inbox_remove_failed") or 0)
    skipped_copy = f", {label_skipped} skipped" if label_skipped else ""
    if label_failed or inbox_failed:
        return (
            f"{base} Stored locally for {local_changed} {local_email_label}. "
            f"Gmail label writes: {messages_written} applied, {label_failed} failed"
            f"{skipped_copy}. Inbox removal: {inbox_removed} applied, {inbox_failed} failed. "
            "Retry failed Gmail writes when ready."
        )
    return (
        f"{base} Gmail label writes: {messages_written} applied{skipped_copy}. "
        f"Inbox removal: {inbox_removed} applied."
    )


def _apply_outcome(teaching_result: dict, write_summary: dict) -> dict:
    mode = teaching_result.get("mode") or ""
    gmail_mode = write_summary.get("mode") or ""
    label_failed = int(write_summary.get("label_write_failed") or 0)
    messages_written = int(write_summary.get("messages_written") or 0)
    current_changed = bool(teaching_result.get("current_changed"))
    future_rule_saved = bool(teaching_result.get("future_rule_saved"))
    current_written = (
        current_changed
        and gmail_mode == "applied"
        and messages_written > 0
        and label_failed == 0
    )
    scope = {
        "current-only": "current-email",
        "matching-existing": "matching-existing",
        "save-future-rule": "future-rule",
        "future-only": "current-email-and-future-rule",
        "apply-included": "included-existing",
    }.get(mode, mode or "unknown")
    changed_count = int(current_changed) + int(teaching_result.get("matched_existing_count") or 0)
    if future_rule_saved and not changed_count:
        state = "future-rule-saved"
    elif changed_count and label_failed:
        state = "partially-changed"
    elif changed_count:
        state = "changed"
    else:
        state = "unchanged"
    return {
        "state": state,
        "scope": scope,
        "current_email_changed_locally": current_changed,
        "current_email_written_to_gmail": current_written,
        "matching_existing_changed_locally": int(
            teaching_result.get("matched_existing_count") or 0
        ),
        "future_rule_saved": future_rule_saved,
        "gmail_write_mode": gmail_mode,
        "gmail_label_write_failed": label_failed,
    }
