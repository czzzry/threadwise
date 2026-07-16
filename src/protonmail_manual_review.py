import json
import os
from datetime import UTC, datetime
from pathlib import Path
import urllib.error
import urllib.request

from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.local_artifacts import load_json_or_default, write_json


class OpenAIProtonReviewClient:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAIProtonReviewClient":
        key = os.environ.get("EMAIL_AGENT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("An OpenAI API key is required for the Proton full-body review.")
        return cls(key, model or os.environ.get("EMAIL_AGENT_OPENAI_MODEL") or "gpt-4.1-mini")

    def classify(self, messages: list[dict]) -> list[dict]:
        allowed = ", ".join(CANONICAL_LABEL_ORDER)
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are performing a careful, full-body manual inbox review for Threadwise. "
                        "Read the complete body of every email, not just sender or subject. Assign exactly one "
                        f"label from: {allowed}. Return JSON {{\"decisions\":[{{\"message_id\":str,"
                        "\"label\":str,\"reason\":str}]}} with exactly one decision per input. "
                        "Use reply-needed (displayed as NeedsAction) only when the owner must act or reply. "
                        "Use suspicious for likely phishing, impersonation, credential theft, or dangerous mail. "
                        "On Proton, suspicious is a label only: do not propose deletion, Spam, moving, or archiving. "
                        "Use spam-low-value for unwanted low-value mail, promotions for wanted commercial offers, "
                        "newsletter for opted-in editorial digests, shopping-order for order/delivery lifecycle, "
                        "receipt-billing for completed charges/invoices, and account-security for legitimate account notices."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"emails": messages}, ensure_ascii=False),
                },
            ],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Proton review model request failed: {exc.code} {body}") from exc
        parsed = json.loads(raw["choices"][0]["message"]["content"])
        return list(parsed.get("decisions") or [])

    def assess(self, messages: list[dict]) -> list[dict]:
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Audit prior Threadwise Proton classifications. Read every complete email body and compare it "
                        "with current_label and current_reason. Return JSON {\"assessments\":[{\"message_id\":str,"
                        "\"confidence\":number,\"uncertainty_reason\":str}]}. Confidence is 0 to 1 that the current "
                        "single primary label is the best taxonomy choice. Lower confidence for overlapping action-vs-topic "
                        "cases, ambiguous promotional/newsletter intent, suspicious-vs-legitimate security, unreadable body, "
                        "or insufficient context. Return exactly one assessment per input."
                    ),
                },
                {"role": "user", "content": json.dumps({"emails": messages}, ensure_ascii=False)},
            ],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Proton uncertainty audit failed: {exc.code} {body}") from exc
        parsed = json.loads(raw["choices"][0]["message"]["content"])
        return list(parsed.get("assessments") or [])


class ProtonManualReviewRunner:
    def __init__(self, proton_client: object, model_client: object, ledger_path: Path) -> None:
        self._proton = proton_client
        self._model = model_client
        self._ledger_path = ledger_path

    def run(self, *, max_results: int = 10_000, batch_size: int = 8, progress=None) -> dict:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        inbox_ids = self._proton.list_messages(max_results)
        ledger = load_json_or_default(self._ledger_path, {"provider": "protonmail", "messages": {}})
        records = ledger.setdefault("messages", {})
        pending_ids = [message_id for message_id in inbox_ids if records.get(message_id, {}).get("status") != "applied"]
        applied_count = 0

        for offset in range(0, len(pending_ids), batch_size):
            ids = pending_ids[offset:offset + batch_size]
            messages = [self._proton.get_message(message_id) for message_id in ids]
            decisions = self._validated_decisions(ids, self._model.classify(messages))
            for message_id in ids:
                decision = decisions[message_id]
                label_name = gmail_label_name(decision["label"])
                write_result = self._proton.apply_label(message_id, label_name)
                if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                    raise RuntimeError("Proton label write violated the label-only safety contract.")
                records[message_id] = {
                    "status": "applied",
                    "internal_label": decision["label"],
                    "label": label_name,
                    "reason": decision.get("reason", ""),
                    "provider_mailbox": write_result.get("mailbox", ""),
                    "applied_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "inbox_preserved": True,
                    "destructive_actions": [],
                }
                ledger["inbox_snapshot_count"] = len(inbox_ids)
                ledger["updated_at"] = records[message_id]["applied_at"]
                write_json(self._ledger_path, ledger)
                applied_count += 1
            if progress is not None:
                progress(
                    {
                        "inbox_count": len(inbox_ids),
                        "applied_this_run": applied_count,
                        "already_applied": len(inbox_ids) - len(pending_ids),
                        "remaining": len(pending_ids) - applied_count,
                    }
                )

        return {
            "inbox_count": len(inbox_ids),
            "applied_count": applied_count,
            "already_applied_count": len(inbox_ids) - len(pending_ids),
            "remaining_count": len(pending_ids) - applied_count,
            "ledger_path": str(self._ledger_path),
        }

    def _validated_decisions(self, expected_ids: list[str], decisions: list[dict]) -> dict[str, dict]:
        by_id = {}
        for decision in decisions:
            message_id = str(decision.get("message_id") or "")
            label = decision.get("label")
            if message_id in by_id:
                raise ValueError(f"Duplicate Proton review decision for {message_id}")
            if label not in CANONICAL_LABEL_ORDER:
                raise ValueError(f"Invalid Proton review label for {message_id}: {label}")
            by_id[message_id] = decision
        if set(by_id) != set(expected_ids):
            raise ValueError("Proton review model did not return exactly one decision per message.")
        return by_id

    def label_least_confident(
        self,
        assessment_client: object,
        *,
        limit: int = 12,
        max_results: int = 10_000,
        batch_size: int = 8,
        progress=None,
    ) -> dict:
        inbox_ids = self._proton.list_messages(max_results)
        ledger = load_json_or_default(self._ledger_path, {"provider": "protonmail", "messages": {}})
        records = ledger.setdefault("messages", {})
        assessments = []
        for offset in range(0, len(inbox_ids), batch_size):
            ids = inbox_ids[offset:offset + batch_size]
            messages = []
            for message_id in ids:
                if records.get(message_id, {}).get("status") != "applied":
                    raise ValueError("Unlabeled Proton message found during uncertainty audit.")
                message = self._proton.get_message(message_id)
                message["current_label"] = records[message_id]["internal_label"]
                message["current_reason"] = records[message_id].get("reason", "")
                messages.append(message)
            assessed = assessment_client.assess(messages)
            by_id = {str(item.get("message_id") or ""): item for item in assessed}
            if set(by_id) != set(ids):
                raise ValueError("Proton uncertainty audit did not return exactly one result per message.")
            for message in messages:
                assessment = by_id[message["id"]]
                confidence = float(assessment.get("confidence"))
                if not 0 <= confidence <= 1:
                    raise ValueError("Proton uncertainty confidence must be between 0 and 1.")
                assessments.append(
                    {
                        "message_id": message["id"],
                        "sender": message.get("sender", ""),
                        "subject": message.get("subject", ""),
                        "current_label": records[message["id"]]["label"],
                        "confidence": confidence,
                        "uncertainty_reason": str(assessment.get("uncertainty_reason") or ""),
                    }
                )
            if progress:
                progress({"assessed": min(offset + len(ids), len(inbox_ids)), "total": len(inbox_ids)})

        selected = sorted(assessments, key=lambda item: (item["confidence"], item["message_id"]))[:limit]
        for item in selected:
            record = records[item["message_id"]]
            if not record.get("double_check"):
                write_result = self._proton.apply_label(item["message_id"], "EA/DoubleCheck")
                if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                    raise RuntimeError("Proton DoubleCheck write violated the label-only safety contract.")
            record["double_check"] = {
                "label": "EA/DoubleCheck",
                "confidence": item["confidence"],
                "uncertainty_reason": item["uncertainty_reason"],
                "sender": item["sender"],
                "subject": item["subject"],
            }
            write_json(self._ledger_path, ledger)
        return {"double_check_count": len(selected), "items": selected}
