from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json
from src.sender_utils import normalized_sender_email


SUPPORTED_SCOPES = {"sender", "domain"}


class GmailSafetyAction:
    """Apply the explicitly confirmed Gmail phishing disposition.

    This is intentionally separate from ordinary classification and teaching:
    it creates a provider-side rule and moves the current message to Trash.
    """

    def __init__(self, gmail_client: object, storage_dir: Path) -> None:
        self._gmail_client = gmail_client
        self._audit_path = storage_dir / "gmail_safety_action_audit.json"

    def preview(self, *, message_id: str, sender: str, scope: str = "sender") -> dict:
        match = self._match(sender, scope)
        return {
            "message_id": message_id,
            "scope": scope,
            "match": match,
            "current_email": "Label EA/Suspicious and move to Gmail Trash",
            "future_emails": (
                "Gmail filter sends exact-sender matches to Trash"
                if scope == "sender"
                else "Gmail filter sends every message from this domain to Trash"
            ),
            "warning": (
                "Domain scope can hide legitimate messages from other addresses at this domain."
                if scope == "domain"
                else "Only this exact sender address will be filtered."
            ),
            "requires_confirmation": True,
        }

    def apply(
        self,
        *,
        account_id: str,
        message_id: str,
        sender: str,
        scope: str = "sender",
        confirmed: bool,
    ) -> dict:
        if not confirmed:
            raise ValueError("Explicit confirmation is required for a suspicious-email action.")
        preview = self.preview(message_id=message_id, sender=sender, scope=scope)
        suspicious_label_id = self._gmail_client.get_or_create_label("EA/Suspicious")
        filter_id = self._gmail_client.create_trash_filter(preview["match"], suspicious_label_id)
        try:
            self._gmail_client.replace_threadwise_labels(message_id, [suspicious_label_id], "EA/")
            self._gmail_client.trash_message(message_id)
        except Exception:
            # Do not leave a new future destructive rule active after a partial
            # current-message failure. Trash remains reversible if it succeeded.
            self._gmail_client.delete_filter(filter_id)
            raise

        result = {
            **preview,
            "account_id": account_id,
            "filter_id": filter_id,
            "status": "applied",
            "applied_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self._append_audit(result)
        return result

    def _match(self, sender: str, scope: str) -> str:
        if scope not in SUPPORTED_SCOPES:
            raise ValueError(f"Unsupported suspicious-email scope: {scope}")
        email = normalized_sender_email(sender)
        if not email:
            raise ValueError("A valid sender email is required for a suspicious-email rule.")
        if scope == "sender":
            return email
        return f"@{email.rsplit('@', 1)[1]}"

    def _append_audit(self, result: dict) -> None:
        audit = load_json_or_default(self._audit_path, {"actions": []})
        audit.setdefault("actions", []).append(result)
        write_json(self._audit_path, audit)
