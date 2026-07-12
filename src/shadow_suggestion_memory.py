import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import urllib.error
import urllib.request
from hashlib import sha1

from src.label_taxonomy import CANONICAL_LABEL_ORDER
from src.local_artifacts import load_json_or_default, write_json
from src.teachable_rule_memory import TeachableRule


@dataclass(frozen=True)
class ShadowSuggestionCandidate:
    provider: str
    sender_key: str
    subject_key: str
    split: str
    count: int
    suggested_labels: tuple[str, ...]
    rationale: str
    evidence_terms: tuple[str, ...]
    source_examples: tuple[dict, ...]
    generated_by: str
    confidence: str
    status: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    review_notes: str = ""
    accepted_labels: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str, str]:
        return self.provider, self.sender_key, self.subject_key

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "sender_key": self.sender_key,
            "subject_key": self.subject_key,
            "split": self.split,
            "count": self.count,
            "suggested_labels": list(self.suggested_labels),
            "rationale": self.rationale,
            "evidence_terms": list(self.evidence_terms),
            "source_examples": list(self.source_examples),
            "generated_by": self.generated_by,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "review_notes": self.review_notes,
            "accepted_labels": list(self.accepted_labels),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ShadowSuggestionCandidate":
        return cls(
            provider=payload["provider"],
            sender_key=payload["sender_key"],
            subject_key=payload["subject_key"],
            split=payload["split"],
            count=int(payload["count"]),
            suggested_labels=tuple(payload.get("suggested_labels", [])),
            rationale=payload.get("rationale", ""),
            evidence_terms=tuple(payload.get("evidence_terms", [])),
            source_examples=tuple(payload.get("source_examples", [])),
            generated_by=payload.get("generated_by", "heuristic-shadow-family-suggester"),
            confidence=payload.get("confidence", "low"),
            status=payload.get("status", "pending"),
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
            review_notes=payload.get("review_notes", ""),
            accepted_labels=tuple(payload.get("accepted_labels", [])),
        )


class ShadowSuggestionMemory:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def list_candidates(self) -> list[ShadowSuggestionCandidate]:
        return list(self._load_existing_candidates().values())

    def merge_candidates(self, candidates: list[ShadowSuggestionCandidate]) -> list[ShadowSuggestionCandidate]:
        def mutate(existing: dict[tuple[str, str, str], ShadowSuggestionCandidate]) -> list[ShadowSuggestionCandidate]:
            now = _now_iso()
            merged: list[ShadowSuggestionCandidate] = []
            seen_keys: set[tuple[str, str, str]] = set()
            for candidate in candidates:
                saved = existing.get(candidate.key)
                seen_keys.add(candidate.key)
                if saved is None:
                    merged.append(
                        ShadowSuggestionCandidate(
                            **{
                                **candidate.to_dict(),
                                "created_at": now,
                                "updated_at": now,
                            }
                        )
                    )
                    continue
                merged.append(
                    ShadowSuggestionCandidate(
                        provider=candidate.provider,
                        sender_key=candidate.sender_key,
                        subject_key=candidate.subject_key,
                        split=candidate.split,
                        count=candidate.count,
                        suggested_labels=candidate.suggested_labels,
                        rationale=candidate.rationale,
                        evidence_terms=candidate.evidence_terms,
                        source_examples=candidate.source_examples,
                        generated_by=candidate.generated_by,
                        confidence=candidate.confidence,
                        status=saved.status,
                        created_at=saved.created_at or now,
                        updated_at=now,
                        review_notes=saved.review_notes,
                        accepted_labels=saved.accepted_labels,
                    )
                )
            for key, saved in existing.items():
                if key not in seen_keys:
                    merged.append(saved)
            return merged

        return self._mutate_candidates(mutate)

    def review_candidate(
        self,
        provider: str,
        sender_key: str,
        subject_key: str,
        status: str,
        accepted_labels: list[str] | None = None,
        review_notes: str = "",
    ) -> ShadowSuggestionCandidate:
        if status not in {"pending", "accepted", "rejected"}:
            raise ValueError("Status must be pending, accepted, or rejected.")
        normalized_labels = self._normalize_review_labels(status, accepted_labels or [])
        match: ShadowSuggestionCandidate | None = None

        def mutate(existing: dict[tuple[str, str, str], ShadowSuggestionCandidate]) -> list[ShadowSuggestionCandidate]:
            nonlocal match
            key = (provider, sender_key, subject_key)
            candidate = existing.get(key)
            if candidate is None:
                raise KeyError(f"Unknown shadow suggestion candidate: {provider} {sender_key} {subject_key}")
            now = _now_iso()
            if status == "accepted":
                final_labels = normalized_labels or candidate.accepted_labels or candidate.suggested_labels
                if not final_labels:
                    raise ValueError("Accepted shadow suggestions need at least one canonical label.")
            else:
                final_labels = ()
            match = ShadowSuggestionCandidate(
                provider=candidate.provider,
                sender_key=candidate.sender_key,
                subject_key=candidate.subject_key,
                split=candidate.split,
                count=candidate.count,
                suggested_labels=candidate.suggested_labels,
                rationale=candidate.rationale,
                evidence_terms=candidate.evidence_terms,
                source_examples=candidate.source_examples,
                generated_by=candidate.generated_by,
                confidence=candidate.confidence,
                status=status,
                created_at=candidate.created_at or now,
                updated_at=now,
                review_notes=review_notes,
                accepted_labels=tuple(final_labels),
            )
            updated = list(existing.values())
            for index, existing_candidate in enumerate(updated):
                if existing_candidate.key == key:
                    updated[index] = match
                    break
            return updated

        self._mutate_candidates(mutate)
        assert match is not None
        return match

    def export_accepted_rules(self, rules_path: Path) -> list[TeachableRule]:
        existing = load_json_or_default(rules_path, {"rules": []})
        preserved_rules = [
            TeachableRule.from_dict(rule)
            for rule in existing.get("rules", [])
            if not _is_shadow_export_rule_payload(rule)
        ]
        exported_rules: list[TeachableRule] = []
        exported_keys: list[dict[str, str]] = []
        for candidate in self.list_candidates():
            if candidate.status != "accepted":
                continue
            labels = list(candidate.accepted_labels or candidate.suggested_labels)
            if not labels:
                continue
            terms = _candidate_terms(candidate)
            exported_keys.append(
                {
                    "provider": candidate.provider,
                    "sender_key": candidate.sender_key,
                    "subject_key": candidate.subject_key,
                }
            )
            for label in labels:
                exported_rules.append(
                    TeachableRule(
                        id=_rule_id_for_candidate(candidate, label),
                        instruction=_candidate_instruction(candidate, label),
                        label=label,
                        terms=tuple(terms),
                        keep_visible=label in {"job-related", "personal", "account-security", "financial-account", "reply-needed"},
                        created_at=_now_iso(),
                        providers=(candidate.provider,),
                        enabled=True,
                        source_examples=tuple(candidate.source_examples),
                        scope="sender-cluster",
                        match_mode="sender-cluster",
                        provenance={
                            "source": "accepted-shadow-suggestion",
                            "approval_status": "accepted",
                            "provider": candidate.provider,
                            "sender_key": candidate.sender_key,
                            "subject_key": candidate.subject_key,
                            "review_notes": candidate.review_notes,
                        },
                        updated_at=_now_iso(),
                    )
                )

        write_json(
            rules_path,
            {
                "status": "PROTOTYPE - compiled accepted shadow suggestion rules",
                "source_memory_path": str(self._path),
                "existing_rule_count": len(existing.get("rules", [])),
                "provider_scope": "per-rule",
                "exported_candidate_keys": exported_keys,
                "exported_rule_count": len(exported_rules),
                "rules": [rule.to_dict() for rule in [*preserved_rules, *exported_rules]],
            },
        )
        return exported_rules

    def _load_existing_candidates(self) -> dict[tuple[str, str, str], ShadowSuggestionCandidate]:
        payload = load_json_or_default(self._path, {"candidates": []})
        candidates: dict[tuple[str, str, str], ShadowSuggestionCandidate] = {}
        for item in payload.get("candidates", []):
            candidate = ShadowSuggestionCandidate.from_dict(item)
            candidates[candidate.key] = candidate
        return candidates

    def _mutate_candidates(
        self,
        mutator,
    ) -> list[ShadowSuggestionCandidate]:
        with _FileLock(self._path.with_suffix(f"{self._path.suffix}.lock")):
            existing = self._load_existing_candidates()
            mutated = list(mutator(existing))
            mutated.sort(key=lambda item: (item.provider, item.split, -item.count, item.sender_key, item.subject_key))
            payload = {
                "status": "PROTOTYPE - local shadow suggestion memory",
                "generated_at": _now_iso(),
                "candidate_count": len(mutated),
                "candidates": [candidate.to_dict() for candidate in mutated],
            }
            _write_json_atomic(self._path, payload)
            return mutated

    def _normalize_review_labels(self, status: str, accepted_labels: list[str]) -> tuple[str, ...]:
        if status != "accepted":
            return ()
        invalid = [label for label in accepted_labels if label not in CANONICAL_LABEL_ORDER]
        if invalid:
            raise ValueError(f"Unknown accepted labels: {', '.join(invalid)}")
        normalized: list[str] = []
        for label in accepted_labels:
            if label not in normalized:
                normalized.append(label)
        return tuple(normalized)


class OpenAIShadowFamilySuggestionClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls, model: str) -> "OpenAIShadowFamilySuggestionClient":
        api_key = os.environ.get("EMAIL_AGENT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "EMAIL_AGENT_OPENAI_API_KEY or OPENAI_API_KEY is required for shadow family suggestions."
            )
        return cls(api_key=api_key, model=model)

    def suggest_for_family(self, provider: str, family: dict) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate review-only family-level inbox classification suggestions. "
                        "Return strict JSON with keys labels, rationale, evidence_terms, and confidence. "
                        "labels must be zero to three values from the allowed taxonomy only."
                    ),
                },
                {
                    "role": "user",
                    "content": _shadow_family_prompt(provider, family),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API request failed: {exc.code} {body}") from exc

        parsed = json.loads(raw["choices"][0]["message"]["content"])
        return {
            "labels": [label for label in parsed.get("labels", []) if label in CANONICAL_LABEL_ORDER][:3],
            "rationale": parsed.get("rationale", ""),
            "evidence_terms": [term for term in parsed.get("evidence_terms", []) if isinstance(term, str)][:5],
            "confidence": parsed.get("confidence", "low"),
        }


def build_shadow_suggestion_candidates(
    report: dict,
    limit_per_provider: int = 12,
    model_client: OpenAIShadowFamilySuggestionClient | None = None,
) -> dict[str, list[dict]]:
    rendered: dict[str, list[dict]] = {}
    for provider, provider_report in report.get("providers", {}).items():
        families = provider_report.get("top_shadow_unlabeled_families_by_split", {}).get(
            "discovery",
            provider_report.get("top_unlabeled_families_by_split", {}).get("discovery", []),
        )
        candidates: list[ShadowSuggestionCandidate] = []
        for family in families:
            candidate = _candidate_for_family(provider, family, model_client=model_client)
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) >= limit_per_provider:
                break
        rendered[provider] = [candidate.to_dict() for candidate in candidates]
    return rendered


def _candidate_for_family(
    provider: str,
    family: dict,
    model_client: OpenAIShadowFamilySuggestionClient | None = None,
) -> ShadowSuggestionCandidate | None:
    sender_key = family["sender_key"]
    subject_key = family["subject_key"]
    examples = family.get("examples", [])
    text = " ".join(
        [
            sender_key,
            subject_key,
            *[example.get("sender", "") for example in examples],
            *[example.get("subject", "") for example in examples],
        ]
    ).lower()
    suggestion = _heuristic_suggestion_for_text(text)
    generated_by = "heuristic-shadow-family-suggester"
    if model_client is not None:
        try:
            model_suggestion = model_client.suggest_for_family(provider, family)
        except RuntimeError:
            model_suggestion = None
        if model_suggestion and model_suggestion.get("labels"):
            suggestion = (
                model_suggestion["labels"],
                model_suggestion.get("rationale") or "Model-backed family suggestion.",
                model_suggestion.get("evidence_terms") or [],
                model_suggestion.get("confidence") or "medium",
            )
            generated_by = "openai-shadow-family-suggester"
    if suggestion is None:
        return None

    labels, rationale, evidence_terms, confidence = suggestion
    return ShadowSuggestionCandidate(
        provider=provider,
        sender_key=sender_key,
        subject_key=subject_key,
        split="discovery",
        count=int(family.get("count", 0)),
        suggested_labels=tuple(label for label in labels if label in CANONICAL_LABEL_ORDER)[:3],
        rationale=rationale,
        evidence_terms=tuple(evidence_terms),
        source_examples=tuple(examples[:3]),
        generated_by=generated_by,
        confidence=confidence,
    )


def _heuristic_suggestion_for_text(text: str) -> tuple[list[str], str, list[str], str] | None:
    rules = [
        (
            ["account-security"],
            ["security alert", "verify your email", "verify your", "sign-in", "signin", "passkey", "password", "verification code", "unusual sign-in", "linked google account", "account team"],
            "Looks like an account access, verification, or security notice.",
            "high",
        ),
        (
            ["financial-account"],
            ["statement", "bank", "e-statement", "account statement", "transaction alert", "balance", "schwab"],
            "Looks like a financial account or statement notice.",
            "high",
        ),
        (
            ["receipt-billing"],
            ["invoice", "billing", "receipt", "payment", "subscription", "renewal", "bill", "charged"],
            "Looks like a payment, invoice, or recurring billing notice.",
            "medium",
        ),
        (
            ["shopping-order", "receipt-billing"],
            ["order", "shipment", "shipping", "delivery", "tracking", "package", "purchase confirmation"],
            "Looks like an order, shipment, or purchase flow.",
            "medium",
        ),
        (
            ["travel"],
            ["boarding", "flight", "hotel", "reservation", "booking confirmed", "train", "trip", "travel"],
            "Looks like travel or reservation mail.",
            "medium",
        ),
        (
            ["calendar-event"],
            ["appointment", "meeting", "reservation confirmed", "event", "calendar"],
            "Looks like a scheduled event or appointment.",
            "medium",
        ),
        (
            ["job-related"],
            ["application", "recruiter", "talent", "interview", "job", "work at a startup", "ashby", "greenhouse", "lever", "angellist"],
            "Looks like recruiting, application, or job platform mail.",
            "medium",
        ),
        (
            ["newsletter"],
            ["newsletter", "weekly", "digest", "top suggestions", "updates to our terms of use"],
            "Looks like a digest, update, or newsletter-style message.",
            "medium",
        ),
        (
            ["promotions"],
            ["sale", "deal", "offer", "discount", "welcome package", "casino", "promo"],
            "Looks like promotional or marketing mail.",
            "medium",
        ),
        (
            ["spam-low-value"],
            ["ad choices", "ad-free outlook", "upgrade your account"],
            "Looks like low-value product marketing or ad noise.",
            "low",
        ),
    ]

    for labels, terms, rationale, confidence in rules:
        matched = [term for term in terms if term in text]
        if matched:
            return labels, rationale, matched[:5], confidence
    return None


def _shadow_family_prompt(provider: str, family: dict) -> str:
    allowed = ", ".join(CANONICAL_LABEL_ORDER)
    examples = family.get("examples", [])[:3]
    rendered_examples = "\n".join(
        [
            (
                f"- sender: {example.get('sender', '')}\n"
                f"  subject: {example.get('subject', '')}\n"
                f"  current_labels: {example.get('current_labels', [])}\n"
            )
            for example in examples
        ]
    )
    return (
        "Suggest review-only labels for this recurring unlabeled email family.\n"
        f"Allowed labels: {allowed}\n"
        "Rules:\n"
        "- This is a family-level suggestion, not a final truth label.\n"
        "- Prefer 0 to 2 labels unless a third is clearly justified.\n"
        "- Use spam-low-value only when the family is clearly low-value noise.\n"
        "- Use account-security for verification, login, password, or security-flow messages.\n"
        "- Use reply-needed only when the user likely needs to respond or act.\n"
        "- Return strict JSON: "
        "{\"labels\": [...], \"rationale\": \"...\", \"evidence_terms\": [\"...\"], \"confidence\": \"low|medium|high\"}\n\n"
        f"Provider: {provider}\n"
        f"Family sender key: {family.get('sender_key', '')}\n"
        f"Family subject key: {family.get('subject_key', '')}\n"
        f"Family count: {family.get('count', 0)}\n"
        f"Examples:\n{rendered_examples}\n"
    )


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _candidate_terms(candidate: ShadowSuggestionCandidate) -> list[str]:
    terms: list[str] = []
    for value in [candidate.sender_key, candidate.subject_key, *candidate.evidence_terms]:
        normalized = re.sub(r"\s+", " ", value.strip().lower()).strip(" .;:")
        if normalized and normalized not in terms and normalized != "(unknown)":
            terms.append(normalized)
    return terms[:8]


def _candidate_instruction(candidate: ShadowSuggestionCandidate, label: str) -> str:
    sender = candidate.sender_key
    subject = candidate.subject_key
    return (
        f"Anything from {sender} with subject like '{subject}' should be {label}."
    )


def _rule_id_for_candidate(candidate: ShadowSuggestionCandidate, label: str) -> str:
    digest = sha1(
        "|".join([candidate.provider, candidate.sender_key, candidate.subject_key, label]).encode("utf-8")
    ).hexdigest()[:12]
    return f"shadow-{candidate.provider}-{digest}"


def _is_shadow_export_rule_payload(rule: dict) -> bool:
    provenance = rule.get("provenance", {})
    return provenance.get("source") == "accepted-shadow-suggestion" or str(rule.get("id", "")).startswith("shadow-")


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temp_path, path)


class _FileLock:
    def __init__(self, path: Path, timeout_seconds: float = 5.0, poll_interval_seconds: float = 0.05) -> None:
        self._path = path
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._fd: int | None = None

    def __enter__(self) -> "_FileLock":
        deadline = time.monotonic() + self._timeout_seconds
        while True:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for shadow suggestion memory lock: {self._path}")
                time.sleep(self._poll_interval_seconds)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
