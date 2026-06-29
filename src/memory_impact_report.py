from datetime import UTC, datetime
from pathlib import Path

from src.classifier_corpus_eval import _apply_extra_rules, _classify_messages, _family_key, _load_corpus_messages
from src.local_artifacts import memory_impact_report_path, write_json
from src.teachable_rule_memory import TeachableRule


def build_memory_impact_report(
    provider_storage_dirs: list[tuple[str, Path]],
    *,
    accepted_rules: list[TeachableRule],
    review_pack: dict | None = None,
) -> dict:
    provider_summaries = {}
    projected_items = []

    for provider, storage_dir in provider_storage_dirs:
        messages = _load_corpus_messages(provider, storage_dir)
        base_predictions = _classify_messages(provider, messages)
        provider_items = []
        for message in messages:
            baseline_labels = list(base_predictions.get(message["classifier_message_id"], []))
            projected = _apply_extra_rules(baseline_labels, message, accepted_rules)
            projected_labels = list(projected["labels"])
            provider_items.append(
                {
                    "provider": provider,
                    "account_id": message["account_id"],
                    "batch_id": message["batch_id"],
                    "message_id": message["message_id"],
                    "sender": message["sender"],
                    "subject": message["subject"],
                    "sender_key": _family_key(message)[0],
                    "subject_key": _family_key(message)[1],
                    "baseline_labels": baseline_labels,
                    "projected_labels": projected_labels,
                    "matched_rule_ids": list(projected["matched_rule_ids"]),
                }
            )
        projected_items.extend(provider_items)
        provider_summaries[provider] = _provider_summary(provider_items)

    top_memory_impacts = _top_memory_impacts(projected_items, accepted_rules)
    next_review_payoffs = _next_review_payoffs(review_pack or {})

    unresolved_before = sum(summary["unresolved_before"] for summary in provider_summaries.values())
    unresolved_after = sum(summary["unresolved_after"] for summary in provider_summaries.values())
    return {
        "generated_at": _now_iso(),
        "artifact_type": "memory-impact-report",
        "summary": {
            "provider_count": len(provider_summaries),
            "accepted_rule_count": len(accepted_rules),
            "impacted_rule_count": len([impact for impact in top_memory_impacts if impact["resolved_message_count"] > 0]),
            "unresolved_before": unresolved_before,
            "unresolved_after": unresolved_after,
            "unresolved_delta": unresolved_after - unresolved_before,
            "next_review_payoff_count": len(next_review_payoffs),
        },
        "provider_summaries": provider_summaries,
        "top_memory_impacts": top_memory_impacts[:10],
        "next_review_payoffs": next_review_payoffs[:10],
    }


def write_memory_impact_report(
    output_storage_dir: Path,
    provider_storage_dirs: list[tuple[str, Path]],
    *,
    accepted_rules: list[TeachableRule],
    review_pack: dict | None = None,
) -> dict:
    payload = build_memory_impact_report(
        provider_storage_dirs,
        accepted_rules=accepted_rules,
        review_pack=review_pack,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = memory_impact_report_path(output_storage_dir, f"memory-impact-report-{timestamp}")
    write_json(path, payload)
    payload["report_path"] = str(path)
    return payload


def _provider_summary(items: list[dict]) -> dict:
    unresolved_before = sum(1 for item in items if not item["baseline_labels"])
    unresolved_after = sum(1 for item in items if not item["projected_labels"])
    return {
        "message_count": len(items),
        "unresolved_before": unresolved_before,
        "unresolved_after": unresolved_after,
        "resolved_by_memory": sum(
            1
            for item in items
            if not item["baseline_labels"] and item["projected_labels"]
        ),
        "unresolved_delta": unresolved_after - unresolved_before,
    }


def _top_memory_impacts(items: list[dict], accepted_rules: list[TeachableRule]) -> list[dict]:
    impacts = []
    for rule in accepted_rules:
        matched = [item for item in items if rule.id in item["matched_rule_ids"]]
        resolved = [
            item for item in matched if not item["baseline_labels"] and item["projected_labels"]
        ]
        if not matched:
            continue
        provider_counts = {}
        family_keys = set()
        for item in resolved:
            provider_counts[item["provider"]] = provider_counts.get(item["provider"], 0) + 1
            family_keys.add((item["provider"], item["sender_key"], item["subject_key"]))
        impacts.append(
            {
                "rule_id": rule.id,
                "label": rule.label,
                "providers": list(rule.providers),
                "provenance_source": rule.provenance.get("source", ""),
                "matched_message_count": len(matched),
                "resolved_message_count": len(resolved),
                "affected_family_count": len(family_keys),
                "provider_counts": provider_counts,
                "source_examples": list(rule.source_examples[:3]),
                "top_resolved_families": _top_resolved_families(resolved),
            }
        )
    return sorted(
        impacts,
        key=lambda impact: (
            -impact["resolved_message_count"],
            -impact["matched_message_count"],
            impact["rule_id"],
        ),
    )


def _top_resolved_families(items: list[dict]) -> list[dict]:
    grouped = {}
    for item in items:
        key = (item["provider"], item["sender_key"], item["subject_key"])
        grouped.setdefault(
            key,
            {
                "provider": item["provider"],
                "sender_key": item["sender_key"],
                "subject_key": item["subject_key"],
                "count": 0,
            },
        )
        grouped[key]["count"] += 1
    return sorted(
        grouped.values(),
        key=lambda family: (-family["count"], family["provider"], family["sender_key"], family["subject_key"]),
    )[:3]


def _next_review_payoffs(review_pack: dict) -> list[dict]:
    payoffs = []
    for target in review_pack.get("top_review_targets", []):
        priority = target.get("review_priority", {})
        expected_gain = int(priority.get("estimated_message_gain", target.get("count", 0)))
        bucket = priority.get("bucket", "low")
        if bucket == "urgent":
            gain_band = "high"
        elif bucket == "high":
            gain_band = "medium-high"
        elif bucket == "medium":
            gain_band = "medium"
        else:
            gain_band = "low"
        payoffs.append(
            {
                "provider": target.get("provider", ""),
                "sender_key": target.get("sender_key", ""),
                "subject_key": target.get("subject_key", ""),
                "question_lane": target.get("question_lane", ""),
                "suggested_labels": list(target.get("suggested_labels", [])),
                "priority_score": int(priority.get("score", 0)),
                "priority_bucket": bucket,
                "expected_resolved_messages": expected_gain,
                "expected_gain_band": gain_band,
                "rationale": list(priority.get("reasons", [])),
            }
        )
    return sorted(
        payoffs,
        key=lambda item: (
            -item["priority_score"],
            -item["expected_resolved_messages"],
            item["provider"],
            item["sender_key"],
            item["subject_key"],
        ),
    )


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
