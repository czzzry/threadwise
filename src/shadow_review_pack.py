from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json, load_json_or_default, review_pack_path, write_json


PREFERENCE_SENSITIVE_LABELS = {
    "newsletter",
    "promotions",
    "spam-low-value",
    "personal",
    "job-related",
}


def build_shadow_review_pack(
    report: dict,
    suggestion_memory_path: Path | None = None,
    max_families_per_provider: int = 6,
) -> dict:
    memory_status_by_key = _memory_status_by_key(suggestion_memory_path)
    safety_priority_by_key = _safety_priority_by_key(report)
    objective_reviews = []
    preference_questions = []
    taxonomy_questions = []
    safety_priority_reviews = []
    provider_summaries = {}

    for provider, provider_report in report.get("providers", {}).items():
        families = provider_report.get("top_shadow_unlabeled_families_by_split", {}).get(
            "discovery",
            provider_report.get("top_unlabeled_families_by_split", {}).get("discovery", []),
        )
        candidate_by_key = {
            (candidate["provider"], candidate["sender_key"], candidate["subject_key"]): candidate
            for candidate in report.get("shadow_suggestion_candidates", {}).get(provider, [])
        }
        review_units = []
        for family in families[:max_families_per_provider]:
            key = (provider, family["sender_key"], family["subject_key"])
            candidate = candidate_by_key.get(key)
            status = memory_status_by_key.get(key, {}).get("status", candidate.get("status", "pending") if candidate else "pending")
            if status != "pending":
                continue
            review_unit = _build_review_unit(
                provider,
                family,
                candidate,
                status,
                safety_priority=safety_priority_by_key.get(key, {}),
            )
            review_units.append(review_unit)
            if review_unit["safety_priority"]["priority_score"] > 0:
                safety_priority_reviews.append(review_unit)
            lane = review_unit["question_lane"]
            if lane == "objective-review":
                objective_reviews.append(review_unit)
            elif lane == "preference-question":
                preference_questions.append(review_unit)
            else:
                taxonomy_questions.append(review_unit)

        provider_summaries[provider] = {
            "shadow_count": provider_report.get("shadow_count", 0),
            "discovery_family_count": len(families),
            "review_unit_count": len(review_units),
            "message_coverage": sum(unit["count"] for unit in review_units),
            "safety_priority_review_count": sum(1 for unit in review_units if unit["safety_priority"]["priority_score"] > 0),
            "priority_message_coverage": sum(
                unit["count"] for unit in review_units if unit["review_priority"]["bucket"] in {"urgent", "high"}
            ),
            "top_review_priority_score": max((unit["review_priority"]["score"] for unit in review_units), default=0),
        }

    objective_reviews.sort(key=_review_unit_sort_key)
    preference_questions.sort(key=_review_unit_sort_key)
    taxonomy_questions.sort(key=_review_unit_sort_key)
    safety_priority_reviews.sort(key=_review_unit_sort_key)
    top_review_targets = sorted(
        [*objective_reviews, *preference_questions, *taxonomy_questions],
        key=_review_unit_sort_key,
    )[:10]
    return {
        "generated_at": _now_iso(),
        "source_report_path": report.get("report_path", ""),
        "source_eval_contract": report.get("eval_contract", {}).get("current_doc", ""),
        "artifact_type": "shadow-family-review-pack",
        "provider_summaries": provider_summaries,
        "top_review_targets": top_review_targets,
        "safety_priority_reviews": safety_priority_reviews,
        "objective_reviews": objective_reviews,
        "preference_questions": preference_questions,
        "taxonomy_questions": taxonomy_questions,
        "summary": {
            "safety_priority_review_count": len(safety_priority_reviews),
            "objective_review_count": len(objective_reviews),
            "preference_question_count": len(preference_questions),
            "taxonomy_question_count": len(taxonomy_questions),
            "top_review_target_count": len(top_review_targets),
            "message_coverage": sum(
                unit["count"] for unit in [*objective_reviews, *preference_questions, *taxonomy_questions]
            ),
        },
    }


def write_shadow_review_pack(
    output_storage_dir: Path,
    report: dict,
    suggestion_memory_path: Path | None = None,
    max_families_per_provider: int = 6,
) -> dict:
    pack = build_shadow_review_pack(
        report,
        suggestion_memory_path=suggestion_memory_path,
        max_families_per_provider=max_families_per_provider,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    pack_path = review_pack_path(output_storage_dir, f"shadow-review-pack-{timestamp}")
    write_json(pack_path, pack)
    pack["pack_path"] = str(pack_path)
    return pack


def _build_review_unit(
    provider: str,
    family: dict,
    candidate: dict | None,
    status: str,
    safety_priority: dict,
) -> dict:
    suggested_labels = list(candidate.get("suggested_labels", [])) if candidate else []
    confidence = candidate.get("confidence", "low") if candidate else "low"
    examples = list(family.get("examples", []))[:3]
    question_lane = _question_lane(suggested_labels, confidence)
    review_priority = _review_priority(
        question_lane=question_lane,
        count=int(family.get("count", 0)),
        confidence=confidence,
        suggested_labels=suggested_labels,
        safety_priority=safety_priority,
    )
    return {
        "provider": provider,
        "account_ids": _account_ids(examples),
        "sender_key": family["sender_key"],
        "subject_key": family["subject_key"],
        "count": int(family.get("count", 0)),
        "question_lane": question_lane,
        "status": status,
        "suggested_labels": suggested_labels,
        "confidence": confidence,
        "generated_by": candidate.get("generated_by", "") if candidate else "",
        "rationale": candidate.get("rationale", "") if candidate else "",
        "evidence_terms": list(candidate.get("evidence_terms", [])) if candidate else [],
        "review_priority": review_priority,
        "safety_priority": {
            "priority_score": int(safety_priority.get("priority_score", 0)),
            "has_false_hide_risk": bool(safety_priority.get("has_false_hide_risk", False)),
            "caution_splits": list(safety_priority.get("caution_splits", [])),
            "reasons": list(safety_priority.get("reasons", [])),
        },
        "examples": examples,
        "question_prompt": _question_prompt(question_lane, family, suggested_labels),
    }


def _question_lane(suggested_labels: list[str], confidence: str) -> str:
    if not suggested_labels:
        return "taxonomy-question"
    if len(suggested_labels) > 1:
        return "preference-question"
    if suggested_labels[0] in PREFERENCE_SENSITIVE_LABELS:
        return "preference-question"
    if confidence == "low":
        return "preference-question"
    return "objective-review"


def _question_prompt(question_lane: str, family: dict, suggested_labels: list[str]) -> str:
    family_ref = f"{family['sender_key']} / {family['subject_key']}"
    if question_lane == "objective-review":
        return f"Approve or edit the proposed labels for {family_ref}: {', '.join(suggested_labels)}."
    if question_lane == "preference-question":
        labels = ", ".join(suggested_labels) if suggested_labels else "no current suggestion"
        return (
            f"For {family_ref}, is this a preference-sensitive family you want treated as {labels}, "
            "or should it stay visible/unlabeled?"
        )
    return (
        f"What label should this recurring family map to, if any: {family_ref}? "
        "If no current taxonomy fits, leave it unlabeled and note the missing concept."
    )


def _account_ids(examples: list[dict]) -> list[str]:
    account_ids = []
    for example in examples:
        account_id = example.get("account_id", "")
        if account_id and account_id not in account_ids:
            account_ids.append(account_id)
    return account_ids


def _memory_status_by_key(suggestion_memory_path: Path | None) -> dict[tuple[str, str, str], dict]:
    if suggestion_memory_path is None:
        return {}
    payload = load_json_or_default(suggestion_memory_path, {"candidates": []})
    statuses = {}
    for candidate in payload.get("candidates", []):
        key = (candidate["provider"], candidate["sender_key"], candidate["subject_key"])
        statuses[key] = {
            "status": candidate.get("status", "pending"),
            "accepted_labels": list(candidate.get("accepted_labels", [])),
        }
    return statuses


def load_report(path: Path) -> dict:
    report = load_json(path)
    report["report_path"] = str(path)
    return report


def _review_unit_sort_key(unit: dict) -> tuple[int, str, str, str]:
    return (
        -unit["review_priority"]["score"],
        -unit["count"],
        unit["provider"],
        unit["sender_key"],
        unit["subject_key"],
    )


def _review_priority(
    *,
    question_lane: str,
    count: int,
    confidence: str,
    suggested_labels: list[str],
    safety_priority: dict,
) -> dict:
    score = int(safety_priority.get("priority_score", 0))
    reasons = list(safety_priority.get("reasons", []))

    if question_lane == "objective-review":
        score += 3
        reasons.append("objective-review")
    elif question_lane == "preference-question":
        score += 1
        reasons.append("preference-question")
    else:
        reasons.append("taxonomy-question")

    if count >= 10:
        score += 3
        reasons.append("large-family")
    elif count >= 5:
        score += 2
        reasons.append("medium-family")
    elif count >= 2:
        score += 1
        reasons.append("small-family")

    if confidence == "high":
        score += 2
        reasons.append("high-confidence")
    elif confidence == "medium":
        score += 1
        reasons.append("medium-confidence")

    if suggested_labels and "account-security" in suggested_labels:
        score += 2
        reasons.append("account-security-suggestion")

    if score >= 9:
        bucket = "urgent"
    elif score >= 6:
        bucket = "high"
    elif score >= 3:
        bucket = "medium"
    else:
        bucket = "low"

    return {
        "score": score,
        "bucket": bucket,
        "reasons": reasons,
        "estimated_message_gain": count,
    }


def _safety_priority_by_key(report: dict) -> dict[tuple[str, str, str], dict]:
    priorities = {}
    for provider, provider_report in report.get("providers", {}).items():
        projection = provider_report.get("safety_memory_projection", {})
        for family in projection.get("top_projected_false_hide_risk_families", []):
            key = (provider, family["sender_key"], family["subject_key"])
            current = priorities.setdefault(key, {"priority_score": 0, "has_false_hide_risk": False, "caution_splits": [], "reasons": []})
            current["priority_score"] += 5
            current["has_false_hide_risk"] = True
            current["reasons"].append("false-hide-risk")
        for split in ("validation", "holdout"):
            for family in projection.get("top_projected_caution_families_by_split", {}).get(split, []):
                key = (provider, family["sender_key"], family["subject_key"])
                current = priorities.setdefault(key, {"priority_score": 0, "has_false_hide_risk": False, "caution_splits": [], "reasons": []})
                current["priority_score"] += 2 if split == "validation" else 3
                if split not in current["caution_splits"]:
                    current["caution_splits"].append(split)
                current["reasons"].append(f"{split}-caution")
    return priorities


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
