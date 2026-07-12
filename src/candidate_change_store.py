from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json


CANDIDATE_CHANGE_KINDS = {
    "future-rule",
    "rule-amendment",
    "compiled-teaching-batch",
    "classifier-code-change",
}

CANDIDATE_CHANGE_STATUSES = {
    "pending",
    "evaluated",
    "recommended-promote",
    "recommended-review",
    "recommended-reject",
    "promoted",
    "rejected",
    "override-promoted",
}


@dataclass(frozen=True)
class CandidateChange:
    id: str
    kind: str
    source: str
    title: str
    description: str
    affected_scope_summary: str
    provider: str = ""
    account_id: str = ""
    status: str = "pending"
    source_refs: tuple[str, ...] = ()
    baseline_ref: str = ""
    latest_evaluation_ref: str = ""
    latest_recommendation: str = ""
    override_reason: str = ""
    decision_actor: str = ""
    decision_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "title": self.title,
            "description": self.description,
            "affected_scope_summary": self.affected_scope_summary,
            "provider": self.provider,
            "account_id": self.account_id,
            "status": self.status,
            "source_refs": list(self.source_refs),
            "baseline_ref": self.baseline_ref,
            "latest_evaluation_ref": self.latest_evaluation_ref,
            "latest_recommendation": self.latest_recommendation,
            "override_reason": self.override_reason,
            "decision_actor": self.decision_actor,
            "decision_at": self.decision_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "CandidateChange":
        return cls(
            id=payload["id"],
            kind=payload["kind"],
            source=payload["source"],
            title=payload.get("title", ""),
            description=payload.get("description", ""),
            affected_scope_summary=payload.get("affected_scope_summary", ""),
            provider=payload.get("provider", ""),
            account_id=payload.get("account_id", ""),
            status=payload.get("status", "pending"),
            source_refs=tuple(payload.get("source_refs", [])),
            baseline_ref=payload.get("baseline_ref", ""),
            latest_evaluation_ref=payload.get("latest_evaluation_ref", ""),
            latest_recommendation=payload.get("latest_recommendation", ""),
            override_reason=payload.get("override_reason", ""),
            decision_actor=payload.get("decision_actor", ""),
            decision_at=payload.get("decision_at", ""),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            metadata=dict(payload.get("metadata", {})),
        )


class CandidateChangeStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def list_candidates(self) -> list[CandidateChange]:
        payload = load_json_or_default(self._path, {"candidates": []})
        return [CandidateChange.from_dict(item) for item in payload.get("candidates", [])]

    def get_candidate(self, candidate_id: str) -> CandidateChange:
        for candidate in self.list_candidates():
            if candidate.id == candidate_id:
                return candidate
        raise KeyError(f"Unknown candidate change: {candidate_id}")

    def save_candidate(self, candidate: CandidateChange) -> CandidateChange:
        _validate_candidate(candidate)
        candidates = [saved for saved in self.list_candidates() if saved.id != candidate.id]
        candidates.append(_with_timestamps(candidate, preserve_created=bool(candidate.created_at)))
        self._write(candidates)
        return self.get_candidate(candidate.id)

    def update_candidate(
        self,
        candidate_id: str,
        *,
        status: str | None = None,
        baseline_ref: str | None = None,
        latest_evaluation_ref: str | None = None,
        latest_recommendation: str | None = None,
        override_reason: str | None = None,
        decision_actor: str | None = None,
        decision_at: str | None = None,
        metadata: dict | None = None,
    ) -> CandidateChange:
        updated: CandidateChange | None = None
        rewritten: list[CandidateChange] = []
        for candidate in self.list_candidates():
            if candidate.id != candidate_id:
                rewritten.append(candidate)
                continue
            next_candidate = CandidateChange(
                id=candidate.id,
                kind=candidate.kind,
                source=candidate.source,
                title=candidate.title,
                description=candidate.description,
                affected_scope_summary=candidate.affected_scope_summary,
                provider=candidate.provider,
                account_id=candidate.account_id,
                status=status or candidate.status,
                source_refs=candidate.source_refs,
                baseline_ref=candidate.baseline_ref if baseline_ref is None else baseline_ref,
                latest_evaluation_ref=(
                    candidate.latest_evaluation_ref
                    if latest_evaluation_ref is None
                    else latest_evaluation_ref
                ),
                latest_recommendation=(
                    candidate.latest_recommendation
                    if latest_recommendation is None
                    else latest_recommendation
                ),
                override_reason=candidate.override_reason if override_reason is None else override_reason,
                decision_actor=candidate.decision_actor if decision_actor is None else decision_actor,
                decision_at=candidate.decision_at if decision_at is None else decision_at,
                created_at=candidate.created_at,
                updated_at=_now_iso(),
                metadata={**candidate.metadata, **(metadata or {})},
            )
            _validate_candidate(next_candidate)
            updated = next_candidate
            rewritten.append(next_candidate)
        if updated is None:
            raise KeyError(f"Unknown candidate change: {candidate_id}")
        self._write(rewritten)
        return updated

    def apply_decision(
        self,
        candidate_id: str,
        *,
        decision: str,
        actor: str,
        latest_recommendation: str,
        override_reason: str = "",
    ) -> CandidateChange:
        decision_to_status = {
            "promote": "promoted",
            "keep-pending": "pending",
            "reject": "rejected",
            "override-promote": "override-promoted",
        }
        try:
            status = decision_to_status[decision]
        except KeyError as exc:
            raise ValueError(f"Unsupported candidate decision: {decision}") from exc
        if decision == "override-promote" and not override_reason.strip():
            raise ValueError("Override promotion requires a non-empty override reason.")
        return self.update_candidate(
            candidate_id,
            status=status,
            latest_recommendation=latest_recommendation,
            override_reason=override_reason,
            decision_actor=actor,
            decision_at=_now_iso(),
            metadata={"last_decision": decision},
        )

    def _write(self, candidates: list[CandidateChange]) -> None:
        candidates = sorted(candidates, key=lambda candidate: (candidate.status, candidate.kind, candidate.id))
        write_json(
            self._path,
            {
                "status": "PROTOTYPE - candidate changes for evaluation and promotion",
                "generated_at": _now_iso(),
                "candidate_count": len(candidates),
                "candidates": [candidate.to_dict() for candidate in candidates],
            },
        )


def candidate_kind_for_teaching_apply_mode(mode: str) -> str | None:
    if mode in {"save-future-rule", "future-only", "apply-included"}:
        return "future-rule"
    return None


def _validate_candidate(candidate: CandidateChange) -> None:
    if candidate.kind not in CANDIDATE_CHANGE_KINDS:
        raise ValueError(f"Unsupported candidate change kind: {candidate.kind}")
    if candidate.status not in CANDIDATE_CHANGE_STATUSES:
        raise ValueError(f"Unsupported candidate change status: {candidate.status}")
    if not candidate.id:
        raise ValueError("Candidate change id is required.")
    if not candidate.source:
        raise ValueError("Candidate change source is required.")
    if not candidate.title:
        raise ValueError("Candidate change title is required.")


def _with_timestamps(candidate: CandidateChange, *, preserve_created: bool) -> CandidateChange:
    now = _now_iso()
    return CandidateChange(
        id=candidate.id,
        kind=candidate.kind,
        source=candidate.source,
        title=candidate.title,
        description=candidate.description,
        affected_scope_summary=candidate.affected_scope_summary,
        provider=candidate.provider,
        account_id=candidate.account_id,
        status=candidate.status,
        source_refs=candidate.source_refs,
        baseline_ref=candidate.baseline_ref,
        latest_evaluation_ref=candidate.latest_evaluation_ref,
        latest_recommendation=candidate.latest_recommendation,
        override_reason=candidate.override_reason,
        decision_actor=candidate.decision_actor,
        decision_at=candidate.decision_at,
        created_at=candidate.created_at if preserve_created else now,
        updated_at=now,
        metadata=dict(candidate.metadata),
    )


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
