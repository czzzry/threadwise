from collections import Counter, defaultdict
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re

from src.fixture_classifier import FixtureBatchClassifier
from src.gmail_message_normalizer import normalize_gmail_message
from src.label_taxonomy import CANONICAL_LABEL_ORDER
from src.local_artifacts import evaluation_report_path, load_json, safety_dispositions_path, write_json
from src.protonmail_message_normalizer import normalize_protonmail_message
from src.safety_disposition_store import SafetyDispositionStore
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRule, apply_teachable_rules


CURRENT_EVAL_CONTRACT = {
    "status": "current",
    "current_as_of": "2026-06-28",
    "current_doc": "docs/current-multi-inbox-eval-contract-2026-06-28.md",
    "global_rules": {
        "reviewed_vs_shadow": (
            "Keep human-reviewed benchmark evidence separate from shadow-only projections. "
            "Do not collapse them into one overall quality claim."
        ),
        "shadow_tuning_boundary": (
            "Tune only from discovery families. Validation and holdout are for post-tuning checks."
        ),
        "family_split_unit": (
            "Shadow corpora are split by normalized sender plus normalized subject family, not by "
            "individual message."
        ),
        "contamination_rule": (
            "If a validation or holdout family is directly inspected for tuning or product review, "
            "treat that family as contaminated and move it into discovery for later reports."
        ),
        "claim_boundary": (
            "ProtonMail and Hotmail results are internal shadow evidence only, not pristine final "
            "exam claims."
        ),
    },
    "corpora": {
        "gmail_reviewed_history": {
            "provider": "gmail",
            "kind": "reviewed-benchmark",
            "trust_level": "medium",
            "contamination_status": "training-adjacent",
            "allowed_uses": [
                "regression checks against reviewed final_labels",
                "label-distribution sanity checks",
                "measuring whether projected changes preserve reviewed Gmail behavior",
            ],
            "disallowed_uses": [
                "claiming a pristine unseen test set",
                "claiming out-of-distribution generalization",
            ],
            "notes": (
                "Many Gmail rules were authored from this history, so it is benchmark-quality "
                "regression evidence but not untouched holdout evidence."
            ),
        },
        "gmail_unreviewed_history": {
            "provider": "gmail",
            "kind": "shadow-tail",
            "trust_level": "low",
            "contamination_status": "mixed-history",
            "allowed_uses": [
                "local shadow projection",
                "spotting recurrent misses that still exist in stored Gmail history",
            ],
            "disallowed_uses": [
                "claiming reviewed benchmark quality",
                "claiming unseen shadow generalization",
            ],
            "notes": (
                "Stored unreviewed Gmail items are useful for local projection only and should not "
                "be conflated with the reviewed benchmark."
            ),
        },
        "protonmail_shadow": {
            "provider": "protonmail",
            "kind": "shadow-corpus",
            "trust_level": "medium",
            "contamination_status": "partially-exposed-pre-split",
            "allowed_uses": [
                "discovery-family review",
                "candidate memory and rule design from discovery families",
                "internal validation and holdout checks after discovery tuning",
            ],
            "disallowed_uses": [
                "claiming ground truth without review",
                "claiming a pristine final generalization exam",
            ],
            "notes": (
                "A full unlabeled exception list was surfaced before the current split existed, so "
                "validation and holdout remain useful internal checks but not untouched final proof."
            ),
        },
        "outlookmail_shadow": {
            "provider": "outlookmail",
            "kind": "shadow-corpus",
            "trust_level": "medium",
            "contamination_status": "debug-inspected",
            "allowed_uses": [
                "large out-of-distribution miss discovery",
                "family-level review and suggestion generation",
                "internal validation and holdout checks with contamination notes",
            ],
            "disallowed_uses": [
                "claiming a pristine untouched holdout",
                "claiming publication-grade benchmark purity",
            ],
            "notes": (
                "The corpus was used to debug browser-backed ingestion and aggregate behavior, so it "
                "is a strong shadow corpus but not a never-seen final exam."
            ),
        },
    },
}


def build_classifier_corpus_report(
    provider_storage_dirs: list[tuple[str, Path]],
    top_limit: int = 10,
    split_salt: str = "2026-06-27-v2-unseen-holdout",
    exposed_families: dict[str, set[tuple[str, str]]] | None = None,
    extra_rules: list[TeachableRule] | None = None,
) -> dict:
    provider_reports = {}
    for provider, storage_dir in provider_storage_dirs:
        messages = _load_corpus_messages(provider, storage_dir)
        provider_reports[provider] = _build_provider_report(
            provider,
            storage_dir,
            messages,
            top_limit,
            split_salt,
            (exposed_families or {}).get(provider, set()),
            extra_rules or [],
        )

    return {
        "generated_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "taxonomy": list(CANONICAL_LABEL_ORDER),
        "eval_contract": _build_eval_contract(split_salt),
        "method": {
            "reviewed_items": "Compared against human-reviewed final_labels when present.",
            "shadow_items": "Reported current classifier predictions only; not treated as ground truth.",
            "split_method": "Deterministic sender/normalized-subject family split: 50% discovery, 25% validation, 25% holdout.",
            "split_salt": split_salt,
            "exposed_families": "Previously surfaced families are forced into discovery before validation/holdout assignment.",
            "llm_usage": "None. This report is local-only and deterministic.",
            "safety_projection": (
                "Approved safety dispositions are replayed as provider-scoped safety memory and compared "
                "against a baseline without safety memory. False-hide metrics are internal guardrails, not "
                "ground-truth phishing scores."
            ),
        },
        "providers": provider_reports,
    }


def write_classifier_corpus_report(
    output_storage_dir: Path,
    provider_storage_dirs: list[tuple[str, Path]],
    top_limit: int = 10,
    split_salt: str = "2026-06-27-v2-unseen-holdout",
    exposed_families: dict[str, set[tuple[str, str]]] | None = None,
    extra_rules: list[TeachableRule] | None = None,
) -> dict:
    report = build_classifier_corpus_report(
        provider_storage_dirs,
        top_limit=top_limit,
        split_salt=split_salt,
        exposed_families=exposed_families,
        extra_rules=extra_rules,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = evaluation_report_path(output_storage_dir, f"classifier-corpus-eval-{timestamp}")
    write_json(report_path, report)
    report["report_path"] = str(report_path)
    return report


def _load_corpus_messages(provider: str, storage_dir: Path) -> list[dict]:
    messages = []
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return messages

    for batch_path in sorted(batches_dir.glob("*.json")):
        batch = load_json(batch_path)
        batch_provider = batch.get("provider", provider)
        if batch.get("provider") and batch_provider != provider:
            continue
        raw_by_id = {
            raw_message.get("id"): raw_message
            for raw_message in batch.get("raw_messages", [])
            if raw_message.get("id")
        }
        for item in batch.get("items", []):
            message_id = item.get("message_id", "")
            normalized = _normalize_stored_message(
                batch_provider,
                batch.get("account_id", ""),
                item,
                raw_by_id.get(message_id),
            )
            messages.append(
                {
                    "batch_id": batch.get("batch_id", batch_path.stem),
                    "account_id": batch.get("account_id", ""),
                    "provider": batch_provider,
                    "message_id": message_id,
                    "classifier_message_id": f"{batch_provider}:{batch.get('batch_id', batch_path.stem)}:{message_id}",
                    "sender": normalized.get("sender", ""),
                    "subject": normalized.get("subject", ""),
                    "date": normalized.get("date") or "1970-01-01T00:00:00Z",
                    "snippet": normalized.get("snippet") or "",
                    "body": normalized.get("body") or "",
                    "gmail_label_ids": list(normalized.get("gmail_label_ids") or []),
                    "list_unsubscribe": normalized.get("list_unsubscribe"),
                    "precedence": normalized.get("precedence", ""),
                    "review_state": item.get("review_state"),
                    "final_labels": list(item.get("final_labels") or []),
                }
            )
    return messages


def _normalize_stored_message(
    provider: str,
    account_id: str,
    item: dict,
    raw_message: dict | None,
) -> dict:
    if provider == "gmail" and _has_stored_normalized_gmail_fields(item):
        return {
            "sender": item.get("sender", ""),
            "subject": item.get("subject", ""),
            "date": item.get("date") or "1970-01-01T00:00:00Z",
            "snippet": item.get("snippet") or "",
            "body": item.get("body") or item.get("snippet") or item.get("subject") or "",
            "gmail_label_ids": list(item.get("gmail_label_ids") or []),
            "list_unsubscribe": item.get("list_unsubscribe"),
            "precedence": item.get("precedence", ""),
        }
    if provider == "gmail" and raw_message is not None:
        return normalize_gmail_message(account_id, raw_message, fallback_message=item)
    if provider == "protonmail":
        proton_raw = dict(item)
        proton_raw["id"] = item.get("message_id", proton_raw.get("id", ""))
        if raw_message is not None:
            proton_raw.update(raw_message)
        return normalize_protonmail_message(account_id, proton_raw)
    return {
        "sender": item.get("sender", ""),
        "subject": item.get("subject", ""),
        "date": item.get("date") or "1970-01-01T00:00:00Z",
        "snippet": item.get("snippet") or "",
        "body": item.get("body") or "",
        "gmail_label_ids": list(item.get("gmail_label_ids") or []),
        "list_unsubscribe": item.get("list_unsubscribe"),
        "precedence": item.get("precedence", ""),
    }


def _has_stored_normalized_gmail_fields(item: dict) -> bool:
    return bool(item.get("sender")) and bool(item.get("subject")) and bool(item.get("date")) and (
        bool(item.get("body")) or bool(item.get("snippet"))
    )


def _build_provider_report(
    provider: str,
    storage_dir: Path,
    messages: list[dict],
    top_limit: int,
    split_salt: str,
    exposed_families: set[tuple[str, str]],
    extra_rules: list[TeachableRule],
) -> dict:
    predictions = _classify_messages(provider, messages)
    evaluated = []
    for message in messages:
        labels = predictions.get(message["classifier_message_id"], [])
        applied = _apply_extra_rules(labels, message, extra_rules)
        evaluated_item = {
            **message,
            "current_labels": applied["labels"],
            "matched_rule_ids": applied["matched_rule_ids"],
        }
        evaluated_item["split"] = _split_for_family(*_family_key(evaluated_item), split_salt, exposed_families)
        evaluated.append(evaluated_item)

    total_count = len(evaluated)
    reviewed_items = [item for item in evaluated if item.get("review_state") == "reviewed"]
    shadow_items = [item for item in evaluated if item.get("review_state") != "reviewed"]
    unlabeled_items = [item for item in evaluated if not item["current_labels"]]
    shadow_unlabeled_items = [item for item in shadow_items if not item["current_labels"]]
    label_counts = Counter(label for item in evaluated for label in item["current_labels"])
    shadow_split_counts = {
        split: sum(
            1 for item in shadow_items if item["split"] == split
        )
        for split in ("discovery", "validation", "holdout")
    }

    report = {
        "total_count": total_count,
        "reviewed_count": len(reviewed_items),
        "shadow_count": len(shadow_items),
        "unlabeled_count": len(unlabeled_items),
        "unlabeled_rate": _percent(len(unlabeled_items), total_count),
        "label_counts": {label: label_counts.get(label, 0) for label in CANONICAL_LABEL_ORDER},
        "evidence_bucket_counts": {
            "reviewed_benchmark": len(reviewed_items),
            "shadow_total": len(shadow_items),
            "shadow_discovery": shadow_split_counts["discovery"],
            "shadow_validation": shadow_split_counts["validation"],
            "shadow_holdout": shadow_split_counts["holdout"],
        },
        "split_counts": _split_counts(evaluated),
        "family_splits": _family_splits(evaluated, split_salt, exposed_families),
        "top_unlabeled_families": _top_families(unlabeled_items, top_limit),
        "top_unlabeled_families_by_split": {
            split: _top_families(
                [item for item in unlabeled_items if item["split"] == split],
                top_limit,
            )
            for split in ("discovery", "validation", "holdout")
        },
        "top_shadow_unlabeled_families_by_split": {
            split: _top_families(
                [item for item in shadow_unlabeled_items if item["split"] == split],
                top_limit,
            )
            for split in ("discovery", "validation", "holdout")
        },
        "matched_shadow_rule_count": sum(1 for item in evaluated if item["matched_rule_ids"]),
    }
    if reviewed_items:
        report["reviewed_metrics"] = _reviewed_metrics(reviewed_items)
        report["top_reviewed_disagreement_families"] = _top_families(
            [
                item
                for item in reviewed_items
                if sorted(item["current_labels"]) != sorted(item["final_labels"])
            ],
            top_limit,
        )
    report["safety_memory_projection"] = _safety_memory_projection(
        evaluated,
        storage_dir,
        top_limit,
    )
    return report


def _build_eval_contract(split_salt: str) -> dict:
    contract = {
        **CURRENT_EVAL_CONTRACT,
        "global_rules": dict(CURRENT_EVAL_CONTRACT["global_rules"]),
        "corpora": {
            corpus_id: {
                **policy,
                "allowed_uses": list(policy["allowed_uses"]),
                "disallowed_uses": list(policy["disallowed_uses"]),
            }
            for corpus_id, policy in CURRENT_EVAL_CONTRACT["corpora"].items()
        },
    }
    contract["shadow_split"] = {
        "unit": "normalized sender + normalized subject family",
        "shares": {
            "discovery": 50,
            "validation": 25,
            "holdout": 25,
        },
        "split_salt": split_salt,
        "exposed_family_rule": (
            "Families already surfaced to the founder or to tuning workflows are forced into discovery."
        ),
    }
    return contract


def _apply_extra_rules(base_labels: list[str], message: dict, rules: list[TeachableRule]) -> dict:
    if not rules:
        return {"labels": list(base_labels), "matched_rule_ids": []}
    item = {
        "message_id": message["classifier_message_id"],
        "applied_labels": list(base_labels),
        "near_misses": [],
        "interpretation": "",
        "confidence_band": "low",
    }
    projected = apply_teachable_rules(item, message, rules)
    return {
        "labels": list(projected.get("applied_labels", [])),
        "matched_rule_ids": [rule["id"] for rule in projected.get("matched_teachable_rules", [])],
    }


def _classify_messages(provider: str, messages: list[dict]) -> dict[str, list[str]]:
    if not messages:
        return {}

    classifier_messages = [
        {
            "message_id": message["classifier_message_id"],
            "sender": message["sender"],
            "subject": message["subject"],
            "date": message["date"],
            "snippet": message["snippet"],
            "body": message["body"],
            "gmail_label_ids": list(message.get("gmail_label_ids") or []),
            "list_unsubscribe": message.get("list_unsubscribe"),
            "precedence": message.get("precedence", ""),
            "provider": provider,
        }
        for message in messages
    ]
    review_queue = FixtureBatchClassifier(fixtures_dir=Path(".")).classify_messages(
        f"{provider}-corpus-eval",
        classifier_messages,
    )
    return {
        item["message_id"]: list(item.get("applied_labels") or [])
        for item in review_queue["items"]
    }


def _reviewed_metrics(items: list[dict]) -> dict:
    exact = 0
    overlap = 0
    for item in items:
        truth = set(item["final_labels"])
        predicted = set(item["current_labels"])
        if predicted == truth:
            exact += 1
        if predicted.intersection(truth):
            overlap += 1
    return {
        "exact_match_count": exact,
        "exact_match_rate": _percent(exact, len(items)),
        "overlap_count": overlap,
        "overlap_rate": _percent(overlap, len(items)),
    }


def _top_families(items: list[dict], limit: int) -> list[dict]:
    grouped = defaultdict(list)
    for item in items:
        grouped[_family_key(item)].append(item)

    families = []
    for (sender_key, subject_key), family_items in grouped.items():
        examples = [
            {
                "provider": item["provider"],
                "account_id": item["account_id"],
                "batch_id": item["batch_id"],
                "message_id": item["message_id"],
                "sender": item["sender"],
                "subject": item["subject"],
                "current_labels": item["current_labels"],
                "final_labels": item["final_labels"],
                "split": item["split"],
            }
            for item in family_items[:3]
        ]
        families.append(
            {
                "sender_key": sender_key,
                "subject_key": subject_key,
                "count": len(family_items),
                "examples": examples,
            }
        )

    return sorted(families, key=lambda family: (-family["count"], family["sender_key"], family["subject_key"]))[
        :limit
    ]


def _split_counts(items: list[dict]) -> dict[str, dict]:
    counts = {
        split: {
            "total_count": 0,
            "reviewed_count": 0,
            "shadow_count": 0,
            "unlabeled_count": 0,
        }
        for split in ("discovery", "validation", "holdout")
    }
    for item in items:
        split_counts = counts[item["split"]]
        split_counts["total_count"] += 1
        if item.get("review_state") == "reviewed":
            split_counts["reviewed_count"] += 1
        else:
            split_counts["shadow_count"] += 1
        if not item["current_labels"]:
            split_counts["unlabeled_count"] += 1

    for split_counts in counts.values():
        split_counts["unlabeled_rate"] = _percent(split_counts["unlabeled_count"], split_counts["total_count"])
    return counts


def _family_splits(
    items: list[dict],
    split_salt: str,
    exposed_families: set[tuple[str, str]],
) -> list[dict]:
    grouped = defaultdict(list)
    for item in items:
        grouped[_family_key(item)].append(item)

    families = []
    for (sender_key, subject_key), family_items in grouped.items():
        split = _split_for_family(sender_key, subject_key, split_salt, exposed_families)
        unlabeled_count = sum(1 for item in family_items if not item["current_labels"])
        families.append(
            {
                "sender_key": sender_key,
                "subject_key": subject_key,
                "split": split,
                "exposed": (sender_key, subject_key) in exposed_families,
                "count": len(family_items),
                "unlabeled_count": unlabeled_count,
                "example_refs": [
                    {
                        "provider": item["provider"],
                        "batch_id": item["batch_id"],
                        "message_id": item["message_id"],
                    }
                    for item in family_items[:3]
                ],
            }
        )

    return sorted(families, key=lambda family: (family["split"], -family["count"], family["sender_key"], family["subject_key"]))


def _family_key(item: dict) -> tuple[str, str]:
    sender_key = normalized_sender_email(item.get("sender")) or item.get("sender", "").strip().lower() or "(unknown)"
    subject_key = _normalize_subject(item.get("subject", ""))
    return sender_key, subject_key


def _split_for_family(
    sender_key: str,
    subject_key: str,
    split_salt: str,
    exposed_families: set[tuple[str, str]],
) -> str:
    if (sender_key, subject_key) in exposed_families:
        return "discovery"
    digest = hashlib.sha256(f"{split_salt}\n{sender_key}\n{subject_key}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    if bucket < 50:
        return "discovery"
    if bucket < 75:
        return "validation"
    return "holdout"


def _normalize_subject(subject: str) -> str:
    normalized = subject.lower()
    normalized = re.sub(r"\b\d+\b", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:100]


def _percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _safety_memory_projection(
    evaluated: list[dict],
    storage_dir: Path,
    top_limit: int,
) -> dict:
    approved_contexts = _approved_safety_contexts(storage_dir)
    baseline_items = [_with_safety_projection(item, {}, False) for item in evaluated]
    projected_items = [
        _with_safety_projection(
            item,
            _matching_safety_context(approved_contexts, item),
            True,
        )
        for item in evaluated
    ]
    return {
        "approved_disposition_count": len(approved_contexts),
        "baseline": _safety_projection_counts(baseline_items),
        "projected": _safety_projection_counts(projected_items),
        "delta": _projection_delta(
            _safety_projection_counts(baseline_items),
            _safety_projection_counts(projected_items),
        ),
        "by_split": {
            split: _projection_by_split(split, baseline_items, projected_items)
            for split in ("discovery", "validation", "holdout")
        },
        "top_projected_false_hide_risk_families": _top_families(
            [item for item in projected_items if item["heuristic_false_hide_risk"] or item["reviewed_false_hide_risk"]],
            top_limit,
        ),
        "top_projected_caution_families_by_split": {
            split: _top_families(
                [item for item in projected_items if item["split"] == split and item["projected_requires_caution"]],
                top_limit,
            )
            for split in ("discovery", "validation", "holdout")
        },
    }


def _projection_by_split(split: str, baseline_items: list[dict], projected_items: list[dict]) -> dict:
    baseline = _safety_projection_counts([item for item in baseline_items if item["split"] == split])
    projected = _safety_projection_counts([item for item in projected_items if item["split"] == split])
    return {
        "baseline": baseline,
        "projected": projected,
        "delta": _projection_delta(baseline, projected),
    }


def _with_safety_projection(item: dict, safety_context: dict, safety_memory_used: bool) -> dict:
    projected = dict(item)
    projected["safety_context"] = dict(safety_context)
    projected["safety_memory_used"] = safety_memory_used
    projected["projected_safety_lane"] = _projected_safety_lane(item, safety_context)
    projected["projected_requires_caution"] = projected["projected_safety_lane"] != "ordinary"
    projected["heuristic_false_hide_risk"] = _heuristic_false_hide_risk(item, projected["projected_safety_lane"])
    projected["reviewed_false_hide_risk"] = _reviewed_false_hide_risk(item, projected["projected_safety_lane"])
    return projected


def _safety_projection_counts(items: list[dict]) -> dict:
    caution_count = sum(1 for item in items if item["projected_requires_caution"])
    suspicious_count = sum(1 for item in items if item["projected_safety_lane"] == "suspicious")
    security_sensitive_count = sum(1 for item in items if item["projected_safety_lane"] == "security-sensitive")
    return {
        "message_count": len(items),
        "caution_count": caution_count,
        "caution_rate": _percent(caution_count, len(items)),
        "suspicious_count": suspicious_count,
        "security_sensitive_count": security_sensitive_count,
        "safety_memory_hit_count": sum(1 for item in items if item["safety_memory_used"]),
        "heuristic_false_hide_risk_count": sum(1 for item in items if item["heuristic_false_hide_risk"]),
        "reviewed_false_hide_risk_count": sum(1 for item in items if item["reviewed_false_hide_risk"]),
    }


def _projection_delta(baseline: dict, projected: dict) -> dict:
    return {
        "caution_count_delta": projected["caution_count"] - baseline["caution_count"],
        "caution_rate_delta": round(projected["caution_rate"] - baseline["caution_rate"], 1),
        "suspicious_count_delta": projected["suspicious_count"] - baseline["suspicious_count"],
        "security_sensitive_count_delta": projected["security_sensitive_count"] - baseline["security_sensitive_count"],
        "safety_memory_hit_count_delta": projected["safety_memory_hit_count"] - baseline["safety_memory_hit_count"],
        "heuristic_false_hide_risk_count_delta": (
            projected["heuristic_false_hide_risk_count"] - baseline["heuristic_false_hide_risk_count"]
        ),
        "reviewed_false_hide_risk_count_delta": (
            projected["reviewed_false_hide_risk_count"] - baseline["reviewed_false_hide_risk_count"]
        ),
    }


def _projected_safety_lane(item: dict, safety_context: dict) -> str:
    labels = set(item.get("current_labels") or [])
    if "account-security" in labels:
        return "security-sensitive"
    disposition = safety_context.get("disposition")
    if disposition == "phishing":
        return "suspicious"
    if disposition == "legitimate-security":
        return "security-sensitive"
    if disposition == "benign-but-watch":
        return "suspicious"
    if disposition == "not-safety":
        return "ordinary"
    if _looks_suspicious(item):
        return "suspicious"
    return "ordinary"


def _looks_suspicious(item: dict) -> bool:
    text = f"{item.get('sender', '')} {item.get('subject', '')}".lower()
    suspicious_terms = ("verify your account", "verification code", "invoice", "payment", "package", "urgent")
    return any(term in text for term in suspicious_terms)


def _heuristic_false_hide_risk(item: dict, projected_safety_lane: str) -> bool:
    return item.get("review_state") != "reviewed" and _looks_suspicious(item) and projected_safety_lane == "ordinary"


def _reviewed_false_hide_risk(item: dict, projected_safety_lane: str) -> bool:
    final_labels = set(item.get("final_labels") or [])
    return item.get("review_state") == "reviewed" and "account-security" in final_labels and projected_safety_lane == "ordinary"


def _approved_safety_contexts(storage_dir: Path) -> list[dict]:
    store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
    contexts = []
    for disposition in store.list_dispositions():
        if disposition.status != "approved":
            continue
        sender_terms = []
        subject_terms = []
        for example in disposition.source_examples:
            sender = normalized_sender_email(example.get("sender")) or (example.get("sender", "").strip().lower())
            if sender and sender not in sender_terms:
                sender_terms.append(sender)
            subject = _normalize_subject(example.get("subject", ""))
            if subject and subject not in subject_terms:
                subject_terms.append(subject)
        contexts.append(
            {
                "disposition_id": disposition.id,
                "scope": disposition.scope,
                "disposition": disposition.disposition,
                "sender_terms": sender_terms,
                "subject_terms": subject_terms,
            }
        )
    return contexts


def _matching_safety_context(safety_contexts: list[dict], item: dict) -> dict:
    sender = normalized_sender_email(item.get("sender")) or item.get("sender", "").strip().lower()
    subject = _normalize_subject(item.get("subject", ""))
    for context in safety_contexts:
        if sender not in context["sender_terms"]:
            continue
        if context["scope"] == "sender":
            return context
        if subject in context["subject_terms"]:
            return context
    return {}
