import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json
from src.sender_utils import normalized_sender_email


SUPPORTED_SAFETY_SCOPES = {"sender", "sender-cluster", "family-cluster"}
SUPPORTED_SAFETY_DISPOSITIONS = {
    "phishing",
    "legitimate-security",
    "benign-but-watch",
    "not-safety",
}
SAFETY_SIGNAL_PHRASES = (
    "gift card",
    "confirm now",
    "confirm address",
    "click here",
    "tracking",
    "delivery",
    "delivery suspended",
    "pending package",
    "package delivery",
    "storage full",
    "cloud storage",
    "subscription upgraded",
    "plan renewed",
    "authorization received",
    "recurring transaction",
    "reward",
    "survey",
    "verify your address",
    "verify your account",
)
SAFETY_SIGNAL_TOKENS = {
    "gift",
    "card",
    "confirm",
    "delivery",
    "package",
    "tracking",
    "storage",
    "cloud",
    "renewed",
    "subscription",
    "reward",
    "survey",
    "winner",
    "urgent",
    "authorize",
    "authorization",
}


@dataclass(frozen=True)
class SafetyDisposition:
    id: str
    provider: str
    account_id: str
    source_batch_id: str
    source_message_ids: tuple[str, ...]
    scope: str
    disposition: str
    source_examples: tuple[dict, ...]
    explanation: str
    match_signals: dict
    preview: dict
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    review_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "account_id": self.account_id,
            "source_batch_id": self.source_batch_id,
            "source_message_ids": list(self.source_message_ids),
            "scope": self.scope,
            "disposition": self.disposition,
            "source_examples": list(self.source_examples),
            "explanation": self.explanation,
            "match_signals": self.match_signals,
            "preview": self.preview,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "review_notes": self.review_notes,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "SafetyDisposition":
        return cls(
            id=payload["id"],
            provider=payload["provider"],
            account_id=payload.get("account_id", ""),
            source_batch_id=payload.get("source_batch_id", ""),
            source_message_ids=tuple(payload.get("source_message_ids", [])),
            scope=payload["scope"],
            disposition=payload["disposition"],
            source_examples=tuple(payload.get("source_examples", [])),
            explanation=payload.get("explanation", ""),
            match_signals=dict(payload.get("match_signals", {})),
            preview=dict(payload.get("preview", {})),
            status=payload.get("status", "pending"),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            review_notes=payload.get("review_notes", ""),
        )


class SafetyDispositionStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def list_dispositions(self) -> list[SafetyDisposition]:
        payload = load_json_or_default(self._path, {"dispositions": []})
        return [SafetyDisposition.from_dict(item) for item in payload.get("dispositions", [])]

    def save_disposition(self, disposition: SafetyDisposition) -> SafetyDisposition:
        dispositions = [saved for saved in self.list_dispositions() if saved.id != disposition.id]
        dispositions.append(disposition)
        self._write(dispositions)
        return disposition

    def review_disposition(
        self,
        disposition_id: str,
        status: str,
        review_notes: str = "",
    ) -> SafetyDisposition:
        if status not in {"approved", "rejected"}:
            raise ValueError("Disposition status must be approved or rejected.")
        now = _now_iso()
        rewritten = []
        updated = None
        for disposition in self.list_dispositions():
            if disposition.id != disposition_id:
                rewritten.append(disposition)
                continue
            updated = SafetyDisposition(
                id=disposition.id,
                provider=disposition.provider,
                account_id=disposition.account_id,
                source_batch_id=disposition.source_batch_id,
                source_message_ids=disposition.source_message_ids,
                scope=disposition.scope,
                disposition=disposition.disposition,
                source_examples=disposition.source_examples,
                explanation=disposition.explanation,
                match_signals=disposition.match_signals,
                preview=disposition.preview,
                status=status,
                created_at=disposition.created_at,
                updated_at=now,
                review_notes=review_notes,
            )
            rewritten.append(updated)
        if updated is None:
            raise KeyError(f"Unknown safety disposition: {disposition_id}")
        self._write(rewritten)
        return updated

    def _write(self, dispositions: list[SafetyDisposition]) -> None:
        dispositions = sorted(dispositions, key=lambda item: (item.status, item.provider, item.id))
        write_json(
            self._path,
            {
                "status": "PROTOTYPE - local safety review dispositions",
                "generated_at": _now_iso(),
                "disposition_count": len(dispositions),
                "dispositions": [item.to_dict() for item in dispositions],
            },
        )


def build_safety_disposition(
    *,
    provider: str,
    account_id: str,
    source_batch_id: str,
    selected_items: list[dict],
    scope: str,
    disposition: str,
    explanation: str,
    storage_items: list[dict],
) -> SafetyDisposition:
    if scope not in SUPPORTED_SAFETY_SCOPES:
        raise ValueError(f"Unsupported safety scope: {scope}")
    if disposition not in SUPPORTED_SAFETY_DISPOSITIONS:
        raise ValueError(f"Unsupported safety disposition: {disposition}")
    if not selected_items:
        raise ValueError("At least one source email is required.")
    source_examples = tuple(_source_example(item, provider) for item in selected_items)
    match_signals = _match_signals_for(scope, selected_items, source_examples)
    preview = _preview_disposition(scope, source_examples, match_signals, storage_items)
    now = _now_iso()
    return SafetyDisposition(
        id=_disposition_id(provider, scope, disposition, source_examples),
        provider=provider,
        account_id=account_id,
        source_batch_id=source_batch_id,
        source_message_ids=tuple(example["message_id"] for example in source_examples),
        scope=scope,
        disposition=disposition,
        source_examples=source_examples,
        explanation=explanation.strip(),
        match_signals=match_signals,
        preview=preview,
        status="pending",
        created_at=now,
        updated_at=now,
    )


def _preview_disposition(
    scope: str,
    source_examples: tuple[dict, ...],
    match_signals: dict,
    storage_items: list[dict],
) -> dict:
    matches = []
    for item in storage_items:
        if matches_safety_context(
            item,
            {
                "scope": scope,
                "sender_terms": match_signals.get("sender_terms", []),
                "subject_terms": match_signals.get("subject_terms", []),
                "content_terms": match_signals.get("content_terms", []),
                "min_content_terms": match_signals.get("min_content_terms", 1),
            },
        ):
            matches.append(
                {
                    "message_id": item.get("message_id", ""),
                    "sender": item.get("sender", ""),
                    "subject": item.get("subject", ""),
                }
            )
    return {
        "match_count": len(matches),
        "matches": matches[:25],
    }


def approved_safety_context(disposition: SafetyDisposition) -> dict:
    match_signals = disposition.match_signals or _match_signals_for(
        disposition.scope,
        list(disposition.source_examples),
        disposition.source_examples,
    )
    return {
        "disposition_id": disposition.id,
        "scope": disposition.scope,
        "disposition": disposition.disposition,
        "explanation": disposition.explanation,
        "review_notes": disposition.review_notes,
        "sender_terms": list(match_signals.get("sender_terms", [])),
        "subject_terms": list(match_signals.get("subject_terms", [])),
        "content_terms": list(match_signals.get("content_terms", [])),
        "min_content_terms": int(match_signals.get("min_content_terms", 1)),
    }


def matches_safety_context(item: dict, context: dict) -> bool:
    scope = context.get("scope", "sender")
    sender_terms = set(context.get("sender_terms", []))
    subject_terms = set(context.get("subject_terms", []))
    content_terms = set(context.get("content_terms", []))
    min_content_terms = max(1, int(context.get("min_content_terms", 1)))
    item_sender = normalized_sender_email(item.get("sender")) or (item.get("sender", "").strip().lower())
    normalized_subject = _normalized_subject(item.get("subject", ""))
    normalized_text = _normalized_text(item)
    content_match_count = sum(1 for term in content_terms if term and term in normalized_text)

    if scope == "sender":
        return item_sender in sender_terms
    if scope == "sender-cluster":
        return item_sender in sender_terms and (not subject_terms or normalized_subject in subject_terms)
    if scope == "family-cluster":
        if item_sender in sender_terms:
            return True
        if normalized_subject in subject_terms and content_match_count >= 1:
            return True
        return content_match_count >= min_content_terms
    return False


def _match_signals_for(scope: str, selected_items: list[dict], source_examples: tuple[dict, ...]) -> dict:
    sender_terms = sorted(
        {
            normalized_sender_email(example.get("sender")) or (example.get("sender", "").strip().lower())
            for example in source_examples
            if example.get("sender")
        }
    )
    subject_terms = sorted(term for term in _subject_terms(source_examples) if term)
    content_terms = sorted(_content_terms(selected_items))
    if scope == "sender":
        subject_terms = []
        content_terms = []
    elif scope == "sender-cluster":
        content_terms = []
    min_content_terms = 2 if scope == "family-cluster" and len(content_terms) >= 2 else 1
    return {
        "sender_terms": sender_terms,
        "subject_terms": subject_terms,
        "content_terms": content_terms,
        "min_content_terms": min_content_terms,
    }


def _source_example(item: dict, provider: str) -> dict:
    return {
        "provider": provider,
        "message_id": item.get("message_id", ""),
        "sender": item.get("sender", ""),
        "subject": item.get("subject", ""),
        "date": item.get("date", ""),
        "snippet": item.get("snippet", ""),
        "final_labels": list(item.get("final_labels") or item.get("applied_labels") or []),
    }


def _subject_terms(source_examples: tuple[dict, ...]) -> set[str]:
    return {_normalized_subject(example.get("subject", "")) for example in source_examples if example.get("subject")}


def _normalized_subject(subject: str) -> str:
    return re.sub(r"\d+", "#", (subject or "").strip().lower())


def _normalized_text(item: dict) -> str:
    combined = " ".join(
        [
            item.get("sender", "") or "",
            item.get("subject", "") or "",
            item.get("snippet", "") or "",
            item.get("body", "") or "",
        ]
    ).lower()
    combined = re.sub(r"\d+", "#", combined)
    combined = re.sub(r"\s+", " ", combined)
    return combined


def _content_terms(selected_items: list[dict]) -> set[str]:
    terms = set()
    normalized_texts = [_normalized_text(item) for item in selected_items]
    for text in normalized_texts:
        for phrase in SAFETY_SIGNAL_PHRASES:
            if phrase in text:
                terms.add(phrase)
        for token in re.findall(r"[a-z#]{4,}", text):
            if token in SAFETY_SIGNAL_TOKENS:
                terms.add(token)
    return terms


def _disposition_id(provider: str, scope: str, disposition: str, source_examples: tuple[dict, ...]) -> str:
    sender = normalized_sender_email(source_examples[0].get("sender")) or source_examples[0].get("sender", "proposal")
    fragment = re.sub(r"[^a-z0-9]+", "-", sender.lower()).strip("-") or "proposal"
    return f"safety-{provider}-{scope}-{disposition}-{fragment}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
