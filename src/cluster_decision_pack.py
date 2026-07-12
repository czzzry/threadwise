from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
import re

from src.local_artifacts import cluster_decision_pack_path, load_json, write_json


LANE_KEYS = (
    "auto_low_value_clusters",
    "safety_review_clusters",
    "personal_review_clusters",
    "preference_review_clusters",
    "unclear_clusters",
)

LANE_REVIEW_TYPES = {
    "auto_low_value_clusters": "policy-review",
    "safety_review_clusters": "safety-review",
    "personal_review_clusters": "policy-review",
    "preference_review_clusters": "preference-review",
    "unclear_clusters": "taxonomy-review",
}

DEFAULT_LANE_LIMITS = {
    "auto_low_value_clusters": 8,
    "safety_review_clusters": 8,
    "personal_review_clusters": 8,
    "preference_review_clusters": 8,
    "unclear_clusters": 8,
}


def build_cluster_decision_pack(
    plan: dict,
    lane_limits: dict[str, int] | None = None,
) -> dict:
    limits = {**DEFAULT_LANE_LIMITS, **(lane_limits or {})}
    provider_summaries: dict[str, dict] = defaultdict(_empty_provider_summary)
    sections: dict[str, list[dict]] = {}
    total_units = 0
    total_messages = 0
    total_families = 0

    for lane_key in LANE_KEYS:
        clusters = list(plan.get(lane_key, []))[: limits.get(lane_key, 0)]
        units = [_build_decision_unit(lane_key, cluster) for cluster in clusters]
        sections[lane_key] = units
        for unit in units:
            provider_summary = provider_summaries[unit["provider"]]
            provider_summary["decision_unit_count"] += 1
            provider_summary["message_coverage"] += unit["message_count"]
            provider_summary["family_coverage"] += unit["family_count"]
            provider_summary["lanes"][unit["review_type"]] += 1
            if unit["safety_priority"]["priority_score"] > 0:
                provider_summary["safety_priority_review_count"] += 1
            total_units += 1
            total_messages += unit["message_count"]
            total_families += unit["family_count"]

    return {
        "generated_at": _now_iso(),
        "artifact_type": "cluster-decision-pack",
        "source_plan_path": plan.get("plan_path", ""),
        "source_plan_summary": plan.get("summary", {}),
        "lane_limits": {key: limits[key] for key in LANE_KEYS},
        "provider_summaries": {
            provider: {
                **summary,
                "lanes": dict(summary["lanes"]),
            }
            for provider, summary in sorted(provider_summaries.items())
        },
        "summary": {
            "decision_unit_count": total_units,
            "message_coverage": total_messages,
            "family_coverage": total_families,
            "auto_low_value_count": len(sections["auto_low_value_clusters"]),
            "safety_review_count": len(sections["safety_review_clusters"]),
            "personal_review_count": len(sections["personal_review_clusters"]),
            "preference_review_count": len(sections["preference_review_clusters"]),
            "unclear_review_count": len(sections["unclear_clusters"]),
            "safety_priority_review_count": sum(
                1
                for unit in [
                    *sections["auto_low_value_clusters"],
                    *sections["safety_review_clusters"],
                    *sections["personal_review_clusters"],
                    *sections["preference_review_clusters"],
                    *sections["unclear_clusters"],
                ]
                if unit["safety_priority"]["priority_score"] > 0
            ),
        },
        "auto_low_value_policies": sections["auto_low_value_clusters"],
        "safety_reviews": sections["safety_review_clusters"],
        "personal_policies": sections["personal_review_clusters"],
        "preference_reviews": sections["preference_review_clusters"],
        "unclear_reviews": sections["unclear_clusters"],
    }


def write_cluster_decision_pack(
    output_storage_dir: Path,
    plan: dict,
    lane_limits: dict[str, int] | None = None,
) -> dict:
    pack = build_cluster_decision_pack(plan, lane_limits=lane_limits)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = cluster_decision_pack_path(output_storage_dir, f"cluster-decision-pack-{timestamp}")
    write_json(path, pack)
    pack["pack_path"] = str(path)
    return pack


def load_frontier_plan(path: Path) -> dict:
    plan = load_json(path)
    plan["plan_path"] = str(path)
    return plan


def _build_decision_unit(lane_key: str, cluster: dict) -> dict:
    review_type = LANE_REVIEW_TYPES[lane_key]
    examples = list(cluster.get("examples", []))[:3]
    suggested_labels = list(cluster.get("suggested_labels", []))
    review_mode = cluster.get("review_mode", "")
    rationale = cluster.get("llm_rationale") or cluster.get("heuristic_rationale", "")
    confidence = cluster.get("llm_confidence") or cluster.get("confidence", "low")
    memory_seed = _memory_seed(cluster, review_mode, suggested_labels, review_type, rationale, confidence)
    return {
        "decision_id": _decision_id(cluster),
        "provider": cluster["provider"],
        "sender_key": cluster["sender_key"],
        "message_count": int(cluster.get("message_count", 0)),
        "family_count": int(cluster.get("family_count", 0)),
        "review_type": review_type,
        "review_mode": review_mode,
        "suggested_labels": suggested_labels,
        "confidence": confidence,
        "rationale": rationale,
        "safety_priority": {
            "priority_score": int(cluster.get("safety_priority", {}).get("priority_score", 0)),
            "reasons": list(cluster.get("safety_priority", {}).get("reasons", [])),
            "approved_disposition_ids": list(cluster.get("safety_priority", {}).get("approved_disposition_ids", [])),
            "approved_dispositions": list(cluster.get("safety_priority", {}).get("approved_dispositions", [])),
        },
        "escalation_hint": _escalation_hint(cluster, review_type),
        "examples": examples,
        "account_ids": _account_ids(examples),
        "question_prompt": _question_prompt(cluster, review_type, suggested_labels),
        "memory_seed": memory_seed,
    }


def _memory_seed(
    cluster: dict,
    review_mode: str,
    suggested_labels: list[str],
    review_type: str,
    rationale: str,
    confidence: str,
) -> dict:
    provider = cluster["provider"]
    sender_key = cluster["sender_key"]
    subject_keys = _subject_keys(cluster.get("examples", []))
    message_count = int(cluster.get("message_count", 0))
    family_count = int(cluster.get("family_count", 0))
    policy_key = f"{provider}:{sender_key}"
    fact_labels = ", ".join(suggested_labels) if suggested_labels else "no accepted labels yet"
    facts = [
        f"Provider-scoped sender cluster: {policy_key}.",
        f"Observed {message_count} unresolved messages across {family_count} subject families.",
        f"Current review type: {review_type}; current mode: {review_mode or 'unclear'}.",
        f"Current recommended labels: {fact_labels}.",
    ]
    if cluster.get("safety_priority", {}).get("priority_score", 0) > 0:
        facts.append(
            "Safety priority: "
            + ", ".join(cluster.get("safety_priority", {}).get("reasons", []))
            + "."
        )
    if subject_keys:
        facts.append(f"Representative subjects: {', '.join(subject_keys[:3])}.")
    if rationale:
        facts.append(f"Why this cluster is grouped this way: {rationale}")
    return {
        "memory_kind": "cluster-policy",
        "cluster_policy_key": policy_key,
        "provider_scope": provider,
        "sender_key": sender_key,
        "review_type": review_type,
        "review_mode": review_mode,
        "recommended_labels": suggested_labels,
        "confidence": confidence,
        "memory_facts": facts,
        "llm_prompt_context": (
            "Use this prior cluster memory when classifying future mail from the same normalized sender. "
            f"Sender cluster {policy_key} has historical recommendation {fact_labels}. "
            "Treat this as soft memory that can be overridden only by strong conflicting message evidence."
        ),
    }


def _question_prompt(cluster: dict, review_type: str, suggested_labels: list[str]) -> str:
    sender_key = cluster["sender_key"]
    if review_type == "policy-review":
        if suggested_labels:
            return f"Approve or edit the standing policy for {sender_key}: {', '.join(suggested_labels)}."
        return f"Set a standing policy for recurring mail from {sender_key}, or keep it visible."
    if review_type == "safety-review":
        return (
            f"Should recurring mail from {sender_key} enter the safety lane as "
            f"{', '.join(suggested_labels) if suggested_labels else 'suspicious/account-related'}, "
            "or be treated differently?"
        )
    if review_type == "preference-review":
        return (
            f"For recurring mail from {sender_key}, what should the default behavior be: "
            f"{', '.join(suggested_labels) if suggested_labels else 'set a preference or keep visible'}?"
        )
    return (
        f"What should the assistant learn for recurring mail from {sender_key}? "
        "If no stable policy fits yet, leave it unresolved."
    )


def _subject_keys(examples: list[dict]) -> list[str]:
    subject_keys = []
    for example in examples:
        subject_key = (example.get("subject_key") or "").strip()
        if subject_key and subject_key not in subject_keys:
            subject_keys.append(subject_key)
    return subject_keys


def _account_ids(examples: list[dict]) -> list[str]:
    account_ids = []
    for example in examples:
        account_id = example.get("account_id", "")
        if account_id and account_id not in account_ids:
            account_ids.append(account_id)
    return account_ids


def _decision_id(cluster: dict) -> str:
    sender_key = re.sub(r"[^a-z0-9]+", "-", cluster["sender_key"].lower()).strip("-")
    return f"cluster-{cluster['provider']}-{sender_key or 'unknown'}"


def _empty_provider_summary() -> dict:
    return {
        "decision_unit_count": 0,
        "message_coverage": 0,
        "family_coverage": 0,
        "lanes": defaultdict(int),
        "safety_priority_review_count": 0,
    }


def _escalation_hint(cluster: dict, review_type: str) -> dict:
    safety_priority = cluster.get("safety_priority", {})
    score = int(safety_priority.get("priority_score", 0))
    approved_dispositions = set(safety_priority.get("approved_dispositions", []))
    if "phishing" in approved_dispositions or score >= 8:
        return {"level": "review-immediately", "reason": "high safety priority"}
    if review_type == "safety-review" or score >= 4:
        return {"level": "review-soon", "reason": "safety-sensitive cluster"}
    if review_type == "preference-review":
        return {"level": "blocked-on-founder-preference", "reason": "needs preference decision"}
    return {"level": "safe-to-batch", "reason": "ordinary batch review"}


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
