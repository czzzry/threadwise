import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.label_taxonomy import CANONICAL_LABEL_ORDER
from src.sender_utils import normalized_sender_email
from src.semantic_rule_matching import semantic_rule_matches_message

BLOCKED_TEACHABLE_LABELS = {"promotions", "spam-low-value"}


@dataclass(frozen=True)
class TeachableRule:
    id: str
    instruction: str
    label: str
    terms: tuple[str, ...]
    keep_visible: bool
    created_at: str
    providers: tuple[str, ...] = ()
    enabled: bool = True
    source_examples: tuple[dict, ...] = ()
    scope: str = "instruction"
    match_mode: str = "term-any"
    provenance: dict = field(default_factory=dict)
    updated_at: str = ""
    disabled_at: str = ""
    disabled_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "label": self.label,
            "terms": list(self.terms),
            "keep_visible": self.keep_visible,
            "created_at": self.created_at,
            "providers": list(self.providers),
            "enabled": self.enabled,
            "source_examples": list(self.source_examples),
            "scope": self.scope,
            "match_mode": self.match_mode,
            "provenance": dict(self.provenance),
            "updated_at": self.updated_at,
            "disabled_at": self.disabled_at,
            "disabled_reason": self.disabled_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TeachableRule":
        return cls(
            id=payload["id"],
            instruction=payload["instruction"],
            label=payload["label"],
            terms=tuple(payload.get("terms", [])),
            keep_visible=bool(payload.get("keep_visible", False)),
            created_at=payload["created_at"],
            providers=tuple(payload.get("providers", [])),
            enabled=bool(payload.get("enabled", True)),
            source_examples=tuple(payload.get("source_examples", [])),
            scope=payload.get("scope", "instruction"),
            match_mode=payload.get("match_mode", "term-any"),
            provenance=dict(payload.get("provenance", {})),
            updated_at=payload.get("updated_at", ""),
            disabled_at=payload.get("disabled_at", ""),
            disabled_reason=payload.get("disabled_reason", ""),
        )


class TeachableRuleMemory:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def list_rules(self) -> list[TeachableRule]:
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text())
        return [TeachableRule.from_dict(rule) for rule in payload.get("rules", [])]

    def save_instruction(self, instruction: str, source_examples: list[dict] | None = None) -> TeachableRule:
        rule = parse_teaching_instruction(
            instruction,
            existing_count=len(self.list_rules()),
            source_examples=source_examples or [],
        )
        return self.save_rule(rule)

    def save_rule(self, rule: TeachableRule) -> TeachableRule:
        rules = [saved_rule for saved_rule in self.list_rules() if saved_rule.id != rule.id]
        rules.append(rule)
        self._write_rules(rules)
        return rule

    def disable_rule(self, rule_id: str, reason: str = "") -> TeachableRule:
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rules = self.list_rules()
        updated: TeachableRule | None = None
        rewritten = []
        for rule in rules:
            if rule.id != rule_id:
                rewritten.append(rule)
                continue
            updated = TeachableRule(
                id=rule.id,
                instruction=rule.instruction,
                label=rule.label,
                terms=rule.terms,
                keep_visible=rule.keep_visible,
                created_at=rule.created_at,
                providers=rule.providers,
                enabled=False,
                source_examples=rule.source_examples,
                scope=rule.scope,
                match_mode=rule.match_mode,
                provenance=rule.provenance,
                updated_at=now,
                disabled_at=now,
                disabled_reason=reason,
            )
            rewritten.append(updated)
        if updated is None:
            raise KeyError(f"Unknown teachable rule: {rule_id}")
        self._write_rules(rewritten)
        return updated

    def _write_rules(self, rules: list[TeachableRule]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {
                    "status": "PROTOTYPE - local teachable classification memory",
                    "rules": [saved_rule.to_dict() for saved_rule in rules],
                },
                indent=2,
            )
            + "\n"
        )


def parse_teaching_instruction(
    instruction: str,
    existing_count: int = 0,
    source_examples: list[dict] | None = None,
) -> TeachableRule:
    cleaned_instruction = " ".join(instruction.strip().split())
    if not cleaned_instruction:
        raise ValueError("Instruction cannot be empty.")

    label = _label_from_instruction(cleaned_instruction)
    if label in BLOCKED_TEACHABLE_LABELS:
        raise ValueError("Teaching rules cannot create low-value or inbox-removal labels.")
    terms = _terms_from_instruction(cleaned_instruction)
    if not terms:
        raise ValueError("Instruction needs at least one sender, domain, platform, or keyword to match.")

    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return TeachableRule(
        id=f"teach-{existing_count + 1:03d}",
        instruction=cleaned_instruction,
        label=label,
        terms=tuple(terms),
        keep_visible=_keep_visible_from_instruction(cleaned_instruction, label),
        created_at=created_at,
        providers=(),
        source_examples=tuple(source_examples or []),
        scope="instruction",
        match_mode="term-any",
        provenance={},
        updated_at=created_at,
    )


def matching_rules_for_message(message: dict, rules: list[TeachableRule]) -> list[TeachableRule]:
    provider = (message.get("provider") or message.get("source") or "").lower()
    return [
        rule
        for rule in rules
        if rule.enabled
        and (not rule.providers or provider in rule.providers)
        and _rule_matches_message(rule, message)
    ]


def apply_teachable_rules(item: dict, message: dict, rules: list[TeachableRule]) -> dict:
    matched_rules = matching_rules_for_message(message, rules)
    if not matched_rules:
        rendered_item = dict(item)
        rendered_item.setdefault("matched_teachable_rules", [])
        return rendered_item

    rendered_item = dict(item)
    applied_labels = list(rendered_item.get("applied_labels", []))
    near_misses = list(rendered_item.get("near_misses", []))
    for rule in matched_rules:
        if rule.label in applied_labels or rule.label in near_misses:
            continue
        if len(applied_labels) < 3:
            applied_labels.append(rule.label)
        else:
            near_misses.append(rule.label)

    rendered_item["applied_labels"] = applied_labels
    rendered_item["near_misses"] = near_misses
    rendered_item["matched_teachable_rules"] = [rule.to_dict() for rule in matched_rules]
    rendered_item["confidence_band"] = _raised_confidence_band(rendered_item.get("confidence_band"))
    rendered_item["interpretation"] = _interpretation_with_rule_match(
        rendered_item.get("interpretation") or "Informational message with no confident category.",
        matched_rules,
    )
    return rendered_item


def preview_teachable_rule(rule: TeachableRule, items: list[dict]) -> dict:
    matches = []
    for item in items:
        matched_rules = matching_rules_for_message(item, [rule])
        if not matched_rules:
            continue
        labels_before = list(item.get("applied_labels", []))
        labels_after = list(labels_before)
        if rule.label not in labels_after and len(labels_after) < 3:
            labels_after.append(rule.label)
        matches.append(
            {
                "message_id": item["message_id"],
                "sender": item.get("sender"),
                "subject": item.get("subject"),
                "labels_before": labels_before,
                "labels_after": labels_after,
                "matched_terms": [term for term in rule.terms if term in _message_text(item)],
            }
        )
    return {"rule": rule.to_dict(), "matches": matches, "match_count": len(matches)}


def _label_from_instruction(instruction: str) -> str:
    lower = instruction.lower()
    label_aliases = {
        "job-related": ("job-related", "job related", "jobs", "job", "recruiter", "recruiters", "ashby", "greenhouse", "lever"),
        "personal": ("personal",),
        "financial-account": ("financial", "finance", "bank", "account statement"),
        "account-security": ("security", "password", "sign-in", "login", "verification"),
        "shopping-order": ("shopping", "order", "shipping", "delivery"),
        "receipt-billing": ("receipt", "billing", "invoice"),
        "newsletter": ("newsletter",),
        "promotions": ("promotion", "promotions", "promo"),
        "spam-low-value": ("low-value", "low value", "spam"),
        "travel": ("travel", "trip", "flight", "hotel"),
        "calendar-event": ("calendar", "event", "appointment"),
        "reply-needed": ("reply-needed", "reply needed", "needs reply"),
    }
    for label in CANONICAL_LABEL_ORDER:
        if any(alias in lower for alias in label_aliases[label]):
            return label
    raise ValueError("Instruction does not map to a known EmailAgent label.")


def _terms_from_instruction(instruction: str) -> list[str]:
    lower = instruction.lower()
    terms: list[str] = []

    for email in re.findall(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", lower):
        terms.append(email)

    quoted_phrases = re.findall(r"[\"']([^\"']+)[\"']", instruction)
    candidates = [*quoted_phrases]

    if "anything from" in lower:
        tail = re.split(r"anything from", lower, maxsplit=1)[1]
        tail = re.split(r"\bshould\b|\bis\b|\bare\b|\bgets\b|\bgoes\b", tail, maxsplit=1)[0]
        candidates.extend(re.split(r",|\bor\b|\band\b", tail))

    for candidate in candidates:
        term = _normalize_term(candidate)
        if term and term not in terms and not _is_instruction_filler(term):
            terms.append(term)
            if term.endswith("s") and len(term) > 3:
                singular = term[:-1]
                if singular not in terms:
                    terms.append(singular)

    return terms


def _keep_visible_from_instruction(instruction: str, label: str) -> bool:
    lower = instruction.lower()
    return label in {"job-related", "personal", "account-security", "financial-account", "reply-needed"} or "visible" in lower


def _message_text(message: dict) -> str:
    return " ".join(
        str(message.get(field) or "").lower()
        for field in ("sender", "subject", "snippet", "body")
    )


def _rule_matches_message(rule: TeachableRule, message: dict) -> bool:
    semantic_rule = (rule.provenance or {}).get("semantic_rule") or {}
    if semantic_rule.get("semantic_pattern") or semantic_rule.get("scope") == "sender-domain":
        return semantic_rule_matches_message(semantic_rule, message)
    if rule.match_mode == "sender":
        return _sender_rule_matches(rule, message)
    if rule.match_mode == "sender-domain":
        return _sender_domain_rule_matches(rule, message)
    if rule.match_mode == "sender-cluster":
        return _shadow_rule_matches_family(rule, message)
    if rule.id.startswith("shadow-") and rule.source_examples:
        return _shadow_rule_matches_family(rule, message)
    text = _message_text(message)
    return any(term in text for term in rule.terms)


def _sender_rule_matches(rule: TeachableRule, message: dict) -> bool:
    message_sender = _normalized_sender_key(message.get("sender", ""))
    return any(_normalized_sender_key(example.get("sender", "")) == message_sender for example in rule.source_examples)


def _sender_domain_rule_matches(rule: TeachableRule, message: dict) -> bool:
    message_sender = _normalized_sender_key(message.get("sender", ""))
    message_domain = message_sender.rsplit("@", 1)[1] if "@" in message_sender else ""
    return any(
        "@" in _normalized_sender_key(example.get("sender", ""))
        and _normalized_sender_key(example.get("sender", "")).rsplit("@", 1)[1] == message_domain
        for example in rule.source_examples
    )


def _shadow_rule_matches_family(rule: TeachableRule, message: dict) -> bool:
    message_sender = _normalized_sender_key(message.get("sender", ""))
    message_subject = _normalized_subject(message.get("subject", ""))
    return any(
        _normalized_sender_key(example.get("sender", "")) == message_sender
        and _normalized_subject(example.get("subject", "")) == message_subject
        for example in rule.source_examples
    )


def _raised_confidence_band(existing: str | None) -> str:
    if existing == "high":
        return "high"
    return "medium"


def _interpretation_with_rule_match(existing: str, matched_rules: list[TeachableRule]) -> str:
    rule_summary = "; ".join(f"{rule.id} -> {rule.label}" for rule in matched_rules)
    return f"{existing} Matched saved teaching rule: {rule_summary}."


def _normalize_term(candidate: str) -> str:
    return re.sub(r"\s+", " ", candidate.strip().lower()).strip(" .;:")


def _is_instruction_filler(term: str) -> bool:
    return term in {"anything", "from", "should", "kept visible", "keep visible", "visible", "be job-related"}


def _normalized_sender_key(sender: str) -> str:
    return normalized_sender_email(sender) or sender.strip().lower()


def _normalized_subject(subject: str) -> str:
    normalized = subject.lower()
    normalized = re.sub(r"\b\d+\b", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:100]
