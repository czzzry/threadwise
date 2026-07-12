from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.candidate_change_store import CandidateChange
from src.classifier_corpus_eval import (
    build_classifier_corpus_report,
    _apply_extra_rules,
    _classify_messages,
    _load_corpus_messages,
)
from src.label_taxonomy import CANONICAL_LABEL_ORDER
from src.local_artifacts import evaluation_report_path, load_json, write_json
from src.teachable_rule_memory import TeachableRule


ATTENTION_LABELS = {
    "account-security",
    "financial-account",
    "job-related",
    "personal",
    "reply-needed",
}
LOW_PRIORITY_LABELS = {"newsletter", "promotions", "spam-low-value"}


@dataclass(frozen=True)
class CandidateEvalSummary:
    candidate_id: str
    recommendation: str
    metrics: dict
    deltas: dict


def evaluate_candidate_batch(
    *,
    candidates: list[CandidateChange],
    provider_storage_dirs: list[tuple[str, Path]],
    output_storage_dir: Path,
    top_limit: int = 10,
    split_salt: str = "2026-06-27-v2-unseen-holdout",
) -> dict:
    baseline_report = build_classifier_corpus_report(
        provider_storage_dirs,
        top_limit=top_limit,
        split_salt=split_salt,
        extra_rules=[],
    )
    baseline_metrics = summarize_candidate_eval_report(baseline_report, provider_storage_dirs, extra_rules=[])

    candidate_summaries = []
    for candidate in candidates:
        candidate_report, candidate_metrics = _candidate_projection(
            candidate,
            provider_storage_dirs=provider_storage_dirs,
            top_limit=top_limit,
            split_salt=split_salt,
            baseline_report=baseline_report,
            baseline_metrics=baseline_metrics,
        )
        deltas = _metrics_delta(baseline_metrics, candidate_metrics)
        recommendation = _recommend_candidate(baseline_metrics, candidate_metrics, deltas)
        candidate_summaries.append(
            {
                "candidate_id": candidate.id,
                "kind": candidate.kind,
                "title": candidate.title,
                "status": candidate.status,
                "metrics": candidate_metrics,
                "deltas": deltas,
                "recommendation": recommendation,
                "baseline_ref": candidate.baseline_ref,
                "report_snapshot": {
                    "providers": candidate_report["providers"],
                },
            }
        )

    batch_recommendation = _recommend_batch(candidate_summaries)
    report = {
        "generated_at": _now_iso(),
        "kind": "candidate-eval-batch",
        "candidate_count": len(candidates),
        "baseline_metrics": baseline_metrics,
        "candidate_summaries": candidate_summaries,
        "batch_recommendation": batch_recommendation,
    }
    report_path = evaluation_report_path(
        output_storage_dir,
        f"candidate-eval-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}",
    )
    write_json(report_path, report)
    report["report_path"] = str(report_path)
    return report


def summarize_candidate_eval_report(
    report: dict,
    provider_storage_dirs: list[tuple[str, Path]],
    *,
    extra_rules: list[TeachableRule],
) -> dict:
    providers = report["providers"]
    gmail_report = providers.get("gmail", {})
    attention_metrics = _attention_metrics(provider_storage_dirs, extra_rules)

    shadow_rates = {}
    shadow_split_rates = {}
    total_shadow_messages = 0
    total_shadow_unlabeled = 0
    for provider, provider_report in providers.items():
        shadow_count = int(provider_report.get("shadow_count", 0))
        if shadow_count <= 0:
            continue
        split_counts = provider_report.get("split_counts", {})
        shadow_unlabeled_count = sum(
            int(split_counts.get(split, {}).get("unlabeled_count", 0))
            for split in ("discovery", "validation", "holdout")
        )
        total_shadow_messages += shadow_count
        total_shadow_unlabeled += shadow_unlabeled_count
        shadow_rates[provider] = _percent(shadow_unlabeled_count, shadow_count)
        shadow_split_rates[provider] = {
            split: float(split_counts.get(split, {}).get("unlabeled_rate", 0.0))
            for split in ("discovery", "validation", "holdout")
        }

    return {
        "reviewed_gmail_exact_match_rate": float(
            gmail_report.get("reviewed_metrics", {}).get("exact_match_rate", 0.0)
        ),
        "reviewed_gmail_overlap_rate": float(
            gmail_report.get("reviewed_metrics", {}).get("overlap_rate", 0.0)
        ),
        "shadow_unlabeled_rate_overall": _percent(total_shadow_unlabeled, total_shadow_messages),
        "shadow_unlabeled_rate_by_provider": shadow_rates,
        "shadow_unlabeled_rate_by_provider_and_split": shadow_split_rates,
        "attention_miss_count": attention_metrics["attention_miss_count"],
        "attention_recall": attention_metrics["attention_recall"],
        "unsafe_action_count": attention_metrics["unsafe_action_count"],
    }


def _candidate_projection(
    candidate: CandidateChange,
    *,
    provider_storage_dirs: list[tuple[str, Path]],
    top_limit: int,
    split_salt: str,
    baseline_report: dict,
    baseline_metrics: dict,
) -> tuple[dict, dict]:
    if candidate.kind == "classifier-code-change" and candidate.baseline_ref:
        baseline_from_ref = load_json(Path(candidate.baseline_ref))
        current_report = build_classifier_corpus_report(
            provider_storage_dirs,
            top_limit=top_limit,
            split_salt=split_salt,
            extra_rules=[],
        )
        return current_report, summarize_candidate_eval_report(
            current_report,
            provider_storage_dirs,
            extra_rules=[],
        )

    extra_rules = _rules_from_candidate(candidate)
    candidate_report = build_classifier_corpus_report(
        provider_storage_dirs,
        top_limit=top_limit,
        split_salt=split_salt,
        extra_rules=extra_rules,
    )
    candidate_metrics = summarize_candidate_eval_report(
        candidate_report,
        provider_storage_dirs,
        extra_rules=extra_rules,
    )
    return candidate_report, candidate_metrics


def _rules_from_candidate(candidate: CandidateChange) -> list[TeachableRule]:
    rules_payload = candidate.metadata.get("rules", [])
    rules = [TeachableRule.from_dict(rule) for rule in rules_payload]
    return rules


def _attention_metrics(
    provider_storage_dirs: list[tuple[str, Path]],
    extra_rules: list[TeachableRule],
) -> dict:
    reviewed_items = []
    for provider, storage_dir in provider_storage_dirs:
        messages = _load_corpus_messages(provider, storage_dir)
        predictions = _classify_messages(provider, messages)
        for message in messages:
            if message.get("review_state") != "reviewed":
                continue
            base_labels = predictions.get(message["classifier_message_id"], [])
            projected = _apply_extra_rules(base_labels, message, extra_rules)
            reviewed_items.append(
                {
                    "truth": set(message.get("final_labels") or []),
                    "predicted": set(projected["labels"]),
                }
            )

    attention_rows = [item for item in reviewed_items if item["truth"].intersection(ATTENTION_LABELS)]
    attention_misses = [
        item for item in attention_rows if not item["predicted"].intersection(ATTENTION_LABELS)
    ]
    unsafe_actions = [
        item
        for item in attention_rows
        if not item["predicted"].intersection(ATTENTION_LABELS)
        and (not item["predicted"] or item["predicted"].intersection(LOW_PRIORITY_LABELS))
    ]
    recall = _percent(len(attention_rows) - len(attention_misses), len(attention_rows))
    return {
        "attention_miss_count": len(attention_misses),
        "attention_recall": recall,
        "unsafe_action_count": len(unsafe_actions),
    }


def _metrics_delta(baseline: dict, current: dict) -> dict:
    provider_delta = {
        provider: round(current["shadow_unlabeled_rate_by_provider"].get(provider, 0.0) - rate, 1)
        for provider, rate in baseline["shadow_unlabeled_rate_by_provider"].items()
    }
    split_delta = {}
    all_providers = set(baseline["shadow_unlabeled_rate_by_provider_and_split"]) | set(
        current["shadow_unlabeled_rate_by_provider_and_split"]
    )
    for provider in all_providers:
        split_delta[provider] = {}
        for split in ("discovery", "validation", "holdout"):
            split_delta[provider][split] = round(
                current["shadow_unlabeled_rate_by_provider_and_split"].get(provider, {}).get(split, 0.0)
                - baseline["shadow_unlabeled_rate_by_provider_and_split"].get(provider, {}).get(split, 0.0),
                1,
            )
    return {
        "reviewed_gmail_exact_match_rate_delta": round(
            current["reviewed_gmail_exact_match_rate"] - baseline["reviewed_gmail_exact_match_rate"],
            1,
        ),
        "reviewed_gmail_overlap_rate_delta": round(
            current["reviewed_gmail_overlap_rate"] - baseline["reviewed_gmail_overlap_rate"],
            1,
        ),
        "shadow_unlabeled_rate_overall_delta": round(
            current["shadow_unlabeled_rate_overall"] - baseline["shadow_unlabeled_rate_overall"],
            1,
        ),
        "shadow_unlabeled_rate_by_provider_delta": provider_delta,
        "shadow_unlabeled_rate_by_provider_and_split_delta": split_delta,
        "attention_miss_count_delta": current["attention_miss_count"] - baseline["attention_miss_count"],
        "attention_recall_delta": round(current["attention_recall"] - baseline["attention_recall"], 1),
        "unsafe_action_count_delta": current["unsafe_action_count"] - baseline["unsafe_action_count"],
    }


def _recommend_candidate(baseline: dict, current: dict, deltas: dict) -> str:
    if deltas["reviewed_gmail_exact_match_rate_delta"] < 0:
        return "Reject"
    if deltas["attention_miss_count_delta"] > 0:
        return "Reject"
    if deltas["unsafe_action_count_delta"] > 0:
        return "Reject"
    validation_or_holdout_worse = any(
        delta > 0
        for provider, split_deltas in deltas["shadow_unlabeled_rate_by_provider_and_split_delta"].items()
        for split, delta in split_deltas.items()
        if split in {"validation", "holdout"}
    )
    if deltas["shadow_unlabeled_rate_overall_delta"] < 0 and not validation_or_holdout_worse:
        return "Promote"
    if deltas["shadow_unlabeled_rate_overall_delta"] < 0 and validation_or_holdout_worse:
        return "Review"
    return "Review"


def _recommend_batch(candidate_summaries: list[dict]) -> str:
    recommendations = {item["recommendation"] for item in candidate_summaries}
    if recommendations == {"Promote"}:
        return "Promote"
    if recommendations == {"Reject"}:
        return "Reject"
    return "Review"


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
