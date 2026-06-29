from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json, safety_review_digest_path, write_json


def build_safety_review_digest(
    *,
    report: dict | None = None,
    frontier_plan: dict | None = None,
    cluster_pack: dict | None = None,
    review_pack: dict | None = None,
) -> dict:
    provider_summaries = {}
    top_targets = []

    for provider, provider_report in (report or {}).get("providers", {}).items():
        projection = provider_report.get("safety_memory_projection", {})
        provider_summaries.setdefault(provider, {})
        provider_summaries[provider]["eval"] = {
            "approved_disposition_count": projection.get("approved_disposition_count", 0),
            "safety_memory_hit_count": projection.get("projected", {}).get("safety_memory_hit_count", 0),
            "heuristic_false_hide_risk_count": projection.get("projected", {}).get("heuristic_false_hide_risk_count", 0),
        }
        for family in projection.get("top_projected_false_hide_risk_families", [])[:3]:
            top_targets.append(
                {
                    "source": "eval-false-hide-risk",
                    "provider": provider,
                    "sender_key": family["sender_key"],
                    "subject_key": family["subject_key"],
                    "priority_score": 9,
                }
            )

    for cluster in (frontier_plan or {}).get("top_safety_priority_clusters", [])[:5]:
        provider = cluster["provider"]
        provider_summaries.setdefault(provider, {})
        provider_summaries[provider]["frontier"] = {
            "safety_priority_clusters": (frontier_plan or {}).get("summary", {}).get("safety_priority_clusters", 0)
        }
        top_targets.append(
            {
                "source": "frontier-priority",
                "provider": provider,
                "sender_key": cluster["sender_key"],
                "subject_key": cluster["examples"][0]["subject_key"] if cluster.get("examples") else "",
                "priority_score": cluster.get("safety_priority", {}).get("priority_score", 0),
            }
        )

    for unit in (cluster_pack or {}).get("safety_reviews", [])[:5]:
        provider = unit["provider"]
        provider_summaries.setdefault(provider, {})
        provider_summaries[provider]["decision_pack"] = {
            "safety_priority_review_count": (cluster_pack or {}).get("summary", {}).get("safety_priority_review_count", 0)
        }
        top_targets.append(
            {
                "source": "decision-pack",
                "provider": provider,
                "sender_key": unit["sender_key"],
                "subject_key": unit.get("examples", [{}])[0].get("subject_key", "") if unit.get("examples") else "",
                "priority_score": unit.get("safety_priority", {}).get("priority_score", 0),
            }
        )

    for unit in (review_pack or {}).get("safety_priority_reviews", [])[:5]:
        provider = unit["provider"]
        provider_summaries.setdefault(provider, {})
        provider_summaries[provider]["review_pack"] = {
            "safety_priority_review_count": (review_pack or {}).get("summary", {}).get("safety_priority_review_count", 0)
        }
        top_targets.append(
            {
                "source": "review-pack",
                "provider": provider,
                "sender_key": unit["sender_key"],
                "subject_key": unit["subject_key"],
                "priority_score": unit.get("safety_priority", {}).get("priority_score", 0),
            }
        )

    deduped = {}
    for target in top_targets:
        key = (target["provider"], target["sender_key"], target["subject_key"])
        existing = deduped.get(key)
        if existing is None or target["priority_score"] > existing["priority_score"]:
            deduped[key] = target
    top_targets = sorted(
        deduped.values(),
        key=lambda item: (-item["priority_score"], item["provider"], item["sender_key"], item["subject_key"]),
    )

    return {
        "generated_at": _now_iso(),
        "artifact_type": "safety-review-digest",
        "provider_summaries": provider_summaries,
        "summary": {
            "provider_count": len(provider_summaries),
            "top_target_count": len(top_targets),
        },
        "top_targets": top_targets[:10],
    }


def write_safety_review_digest(
    output_storage_dir: Path,
    *,
    report: dict | None = None,
    frontier_plan: dict | None = None,
    cluster_pack: dict | None = None,
    review_pack: dict | None = None,
) -> dict:
    digest = build_safety_review_digest(
        report=report,
        frontier_plan=frontier_plan,
        cluster_pack=cluster_pack,
        review_pack=review_pack,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = safety_review_digest_path(output_storage_dir, f"safety-review-digest-{timestamp}")
    write_json(path, digest)
    digest["digest_path"] = str(path)
    return digest


def load_artifact(path: Path) -> dict:
    payload = load_json(path)
    payload["artifact_path"] = str(path)
    return payload


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
