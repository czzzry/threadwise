import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRule, TeachableRuleMemory, preview_teachable_rule


SUPPORTED_MEMORY_SCOPES = {"sender", "sender-cluster", "global"}


@dataclass(frozen=True)
class MemoryProposal:
    id: str
    provider: str
    account_id: str
    source_batch_id: str
    source_message_ids: tuple[str, ...]
    scope: str
    label: str
    instruction: str
    terms: tuple[str, ...]
    source_examples: tuple[dict, ...]
    explanation: str
    preview: dict
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    approved_rule_id: str = ""
    review_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "account_id": self.account_id,
            "source_batch_id": self.source_batch_id,
            "source_message_ids": list(self.source_message_ids),
            "scope": self.scope,
            "label": self.label,
            "instruction": self.instruction,
            "terms": list(self.terms),
            "source_examples": list(self.source_examples),
            "explanation": self.explanation,
            "preview": self.preview,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_rule_id": self.approved_rule_id,
            "review_notes": self.review_notes,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "MemoryProposal":
        return cls(
            id=payload["id"],
            provider=payload["provider"],
            account_id=payload.get("account_id", ""),
            source_batch_id=payload.get("source_batch_id", ""),
            source_message_ids=tuple(payload.get("source_message_ids", [])),
            scope=payload["scope"],
            label=payload["label"],
            instruction=payload["instruction"],
            terms=tuple(payload.get("terms", [])),
            source_examples=tuple(payload.get("source_examples", [])),
            explanation=payload.get("explanation", ""),
            preview=dict(payload.get("preview", {})),
            status=payload.get("status", "pending"),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            approved_rule_id=payload.get("approved_rule_id", ""),
            review_notes=payload.get("review_notes", ""),
        )


class MemoryProposalStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def list_proposals(self) -> list[MemoryProposal]:
        payload = load_json_or_default(self._path, {"proposals": []})
        return [MemoryProposal.from_dict(item) for item in payload.get("proposals", [])]

    def save_proposal(self, proposal: MemoryProposal) -> MemoryProposal:
        proposals = [saved for saved in self.list_proposals() if saved.id != proposal.id]
        proposals.append(proposal)
        self._write(proposals)
        return proposal

    def review_proposal(
        self,
        proposal_id: str,
        status: str,
        rules_memory: TeachableRuleMemory | None = None,
        review_notes: str = "",
    ) -> MemoryProposal:
        if status not in {"approved", "rejected"}:
            raise ValueError("Proposal status must be approved or rejected.")
        now = _now_iso()
        rewritten = []
        updated: MemoryProposal | None = None
        for proposal in self.list_proposals():
            if proposal.id != proposal_id:
                rewritten.append(proposal)
                continue
            approved_rule_id = proposal.approved_rule_id
            if status == "approved":
                if rules_memory is None:
                    raise ValueError("rules_memory is required to approve a proposal.")
                if proposal.status != "approved" or not approved_rule_id:
                    rule = rules_memory.save_rule(
                        rule_from_memory_proposal(proposal, existing_count=len(rules_memory.list_rules()))
                    )
                    approved_rule_id = rule.id
            updated = MemoryProposal(
                id=proposal.id,
                provider=proposal.provider,
                account_id=proposal.account_id,
                source_batch_id=proposal.source_batch_id,
                source_message_ids=proposal.source_message_ids,
                scope=proposal.scope,
                label=proposal.label,
                instruction=proposal.instruction,
                terms=proposal.terms,
                source_examples=proposal.source_examples,
                explanation=proposal.explanation,
                preview=proposal.preview,
                status=status,
                created_at=proposal.created_at,
                updated_at=now,
                approved_rule_id=approved_rule_id,
                review_notes=review_notes,
            )
            rewritten.append(updated)
        if updated is None:
            raise KeyError(f"Unknown memory proposal: {proposal_id}")
        self._write(rewritten)
        return updated

    def _write(self, proposals: list[MemoryProposal]) -> None:
        proposals = sorted(proposals, key=lambda proposal: (proposal.status, proposal.provider, proposal.id))
        write_json(
            self._path,
            {
                "status": "PROTOTYPE - local teachable memory proposals",
                "generated_at": _now_iso(),
                "proposal_count": len(proposals),
                "proposals": [proposal.to_dict() for proposal in proposals],
            },
        )


def build_memory_proposal(
    *,
    provider: str,
    account_id: str,
    source_batch_id: str,
    selected_items: list[dict],
    scope: str,
    label: str,
    explanation: str,
    storage_items: list[dict],
) -> MemoryProposal:
    if scope not in SUPPORTED_MEMORY_SCOPES:
        raise ValueError(f"Unsupported memory scope: {scope}")
    if not selected_items:
        raise ValueError("At least one source email is required.")
    if scope == "global" and not explanation.strip():
        raise ValueError("Global memory proposals require an explanation.")
    source_examples = tuple(_source_example(item, provider) for item in selected_items)
    terms = tuple(_terms_for_scope(scope, source_examples, explanation))
    if not terms and scope == "global":
        raise ValueError("Global proposal explanation did not produce reusable terms.")
    instruction = _instruction_for(scope, source_examples, label, explanation)
    proposal_id = _proposal_id(provider, scope, label, source_examples)
    preview_rule = rule_from_memory_proposal(
        MemoryProposal(
            id=proposal_id,
            provider=provider,
            account_id=account_id,
            source_batch_id=source_batch_id,
            source_message_ids=tuple(example["message_id"] for example in source_examples),
            scope=scope,
            label=label,
            instruction=instruction,
            terms=terms,
            source_examples=source_examples,
            explanation=explanation,
            preview={},
            created_at=_now_iso(),
            updated_at=_now_iso(),
        ),
        existing_count=0,
    )
    preview = preview_teachable_rule(preview_rule, storage_items)
    return MemoryProposal(
        id=proposal_id,
        provider=provider,
        account_id=account_id,
        source_batch_id=source_batch_id,
        source_message_ids=tuple(example["message_id"] for example in source_examples),
        scope=scope,
        label=label,
        instruction=instruction,
        terms=terms,
        source_examples=source_examples,
        explanation=explanation,
        preview=preview,
        status="pending",
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )


def rule_from_memory_proposal(proposal: MemoryProposal, existing_count: int) -> TeachableRule:
    created_at = _now_iso()
    return TeachableRule(
        id=proposal.approved_rule_id or (f"teach-{existing_count + 1:03d}" if not proposal.id.startswith("shadow-") else proposal.id),
        instruction=proposal.instruction,
        label=proposal.label,
        terms=proposal.terms,
        keep_visible=proposal.label in {"job-related", "personal", "account-security", "financial-account", "reply-needed"},
        created_at=created_at,
        providers=(proposal.provider,),
        enabled=True,
        source_examples=proposal.source_examples,
        scope=proposal.scope,
        match_mode="sender" if proposal.scope == "sender" else "sender-cluster" if proposal.scope == "sender-cluster" else "term-any",
        provenance={
            "proposal_id": proposal.id,
            "approval_status": "approved",
            "source": "human-correction-proposal",
            "source_batch_id": proposal.source_batch_id,
            "source_message_ids": list(proposal.source_message_ids),
            "scope": proposal.scope,
            "explanation": proposal.explanation,
        },
        updated_at=created_at,
    )


def load_storage_items(storage_dir: Path, provider: str) -> list[dict]:
    items = []
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return items
    for batch_path in sorted(batches_dir.glob("*.json")):
        batch = json.loads(batch_path.read_text())
        if batch.get("provider", provider) != provider:
            continue
        for item in batch.get("items", []):
            items.append(
                {
                    "provider": provider,
                    "batch_id": batch.get("batch_id", ""),
                    "account_id": item.get("account_id", batch.get("account_id", "")),
                    "message_id": item.get("message_id", ""),
                    "sender": item.get("sender", ""),
                    "subject": item.get("subject", ""),
                    "date": item.get("date", ""),
                    "snippet": item.get("snippet", ""),
                    "body": item.get("body", ""),
                    "applied_labels": list(item.get("applied_labels", [])),
                }
            )
    return items


def _source_example(item: dict, provider: str) -> dict:
    return {
        "provider": provider,
        "message_id": item.get("message_id", ""),
        "sender": item.get("sender", ""),
        "subject": item.get("subject", ""),
        "date": item.get("date", ""),
        "final_labels": list(item.get("final_labels") or item.get("applied_labels") or []),
    }


def _terms_for_scope(scope: str, source_examples: tuple[dict, ...], explanation: str) -> list[str]:
    if scope == "sender":
        return _sender_terms(source_examples)
    if scope == "sender-cluster":
        return _sender_terms(source_examples) + _subject_terms(source_examples)
    return _explanation_terms(explanation)


def _sender_terms(source_examples: tuple[dict, ...]) -> list[str]:
    terms = []
    for example in source_examples:
        sender = example.get("sender", "")
        normalized_email = normalized_sender_email(sender)
        candidate = normalized_email or sender.strip().lower()
        if candidate and candidate not in terms:
            terms.append(candidate)
    return terms


def _subject_terms(source_examples: tuple[dict, ...]) -> list[str]:
    terms = []
    for example in source_examples:
        subject = (example.get("subject") or "").strip().lower()
        subject = re.sub(r"\d+", "#", subject)
        if subject and subject not in terms:
            terms.append(subject)
    return terms


def _explanation_terms(explanation: str) -> list[str]:
    words = [word.lower() for word in re.findall(r"[a-zA-Z]{4,}", explanation)]
    terms = []
    for word in words:
        if word in {"this", "that", "with", "from", "have", "your", "should", "keep", "mail", "email"}:
            continue
        if word not in terms:
            terms.append(word)
        if len(terms) >= 6:
            break
    return terms


def _instruction_for(scope: str, source_examples: tuple[dict, ...], label: str, explanation: str) -> str:
    sender_text = ", ".join(_sender_terms(source_examples)) or "selected sender"
    if scope == "sender":
        return f"Anything from {sender_text} should be {label}."
    if scope == "sender-cluster":
        subject_text = ", ".join(_subject_terms(source_examples)[:3]) or "matching this sender cluster"
        return f"Anything from {sender_text} with subjects like '{subject_text}' should be {label}."
    return f"Messages matching this global preference should be {label}: {explanation.strip()}"


def _proposal_id(provider: str, scope: str, label: str, source_examples: tuple[dict, ...]) -> str:
    sender_fragment = re.sub(r"[^a-z0-9]+", "-", (_sender_terms(source_examples)[0] if _sender_terms(source_examples) else "proposal"))
    sender_fragment = sender_fragment.strip("-") or "proposal"
    if scope == "sender-cluster":
        subject_fragment = re.sub(r"[^a-z0-9]+", "-", (_subject_terms(source_examples)[0] if _subject_terms(source_examples) else "cluster"))
        subject_fragment = subject_fragment.strip("-") or "cluster"
        return f"proposal-{provider}-{scope}-{label}-{sender_fragment}-{subject_fragment}"
    return f"proposal-{provider}-{scope}-{label}-{sender_fragment}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
