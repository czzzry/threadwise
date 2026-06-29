from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import safety_backlog_report_path, safety_dispositions_path, write_json
from src.safety_disposition_store import SafetyDispositionStore


def build_safety_backlog_report(
    *,
    provider_storage_dirs: list[tuple[str, Path]] | None = None,
    storage_dir: Path | None = None,
    report: dict | None = None,
    frontier_plan: dict | None = None,
    cluster_pack: dict | None = None,
    review_pack: dict | None = None,
    digest: dict | None = None,
) -> dict:
    dispositions = _load_dispositions(provider_storage_dirs, storage_dir)
    status_counts = {"pending": 0, "approved": 0, "rejected": 0}
    provider_status_counts: dict[str, dict[str, int]] = {}
    for disposition in dispositions:
        status_counts[disposition.status] = status_counts.get(disposition.status, 0) + 1
        provider_counts = provider_status_counts.setdefault(
            disposition.provider,
            {"pending": 0, "approved": 0, "rejected": 0},
        )
        provider_counts[disposition.status] = provider_counts.get(disposition.status, 0) + 1

    top_targets = list((digest or {}).get("top_targets", []))
    top_target_counts_by_provider: dict[str, int] = {}
    for target in top_targets:
        provider = target.get("provider", "")
        if provider:
            top_target_counts_by_provider[provider] = top_target_counts_by_provider.get(provider, 0) + 1
    provider_summaries = {}
    for provider, provider_report in (report or {}).get("providers", {}).items():
        provider_summaries[provider] = {
            "approved_disposition_count": provider_status_counts.get(provider, {}).get("approved", 0),
            "pending_disposition_count": provider_status_counts.get(provider, {}).get("pending", 0),
            "rejected_disposition_count": provider_status_counts.get(provider, {}).get("rejected", 0),
            "top_target_count": top_target_counts_by_provider.get(provider, 0),
            "eval_false_hide_risk_count": provider_report.get("safety_memory_projection", {})
            .get("projected", {})
            .get("heuristic_false_hide_risk_count", 0),
            "frontier_safety_priority_clusters": (frontier_plan or {}).get("summary", {}).get("safety_priority_clusters", 0),
            "decision_pack_safety_priority_reviews": (cluster_pack or {}).get("summary", {}).get("safety_priority_review_count", 0),
            "review_pack_safety_priority_reviews": (review_pack or {}).get("summary", {}).get("safety_priority_review_count", 0),
        }
    provider_drivers = _provider_drivers(provider_summaries)

    return {
        "generated_at": _now_iso(),
        "artifact_type": "safety-backlog-report",
        "summary": {
            "approved_disposition_count": status_counts.get("approved", 0),
            "pending_disposition_count": status_counts.get("pending", 0),
            "rejected_disposition_count": status_counts.get("rejected", 0),
            "top_target_count": len(top_targets),
            "backlog_pressure": _backlog_pressure(status_counts.get("pending", 0), len(top_targets)),
        },
        "provider_summaries": provider_summaries,
        "provider_drivers": provider_drivers,
        "top_targets": top_targets[:10],
    }


def write_safety_backlog_report(
    output_storage_dir: Path,
    *,
    provider_storage_dirs: list[tuple[str, Path]] | None = None,
    storage_dir: Path | None = None,
    report: dict | None = None,
    frontier_plan: dict | None = None,
    cluster_pack: dict | None = None,
    review_pack: dict | None = None,
    digest: dict | None = None,
) -> dict:
    payload = build_safety_backlog_report(
        provider_storage_dirs=provider_storage_dirs,
        storage_dir=storage_dir,
        report=report,
        frontier_plan=frontier_plan,
        cluster_pack=cluster_pack,
        review_pack=review_pack,
        digest=digest,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = safety_backlog_report_path(output_storage_dir, f"safety-backlog-report-{timestamp}")
    write_json(path, payload)
    payload["report_path"] = str(path)
    return payload


def _backlog_pressure(pending_dispositions: int, top_target_count: int) -> str:
    if pending_dispositions == 0 and top_target_count == 0:
        return "clear"
    if pending_dispositions <= 3 and top_target_count <= 5:
        return "manageable"
    if pending_dispositions <= 10 and top_target_count <= 10:
        return "elevated"
    return "high"


def _load_dispositions(
    provider_storage_dirs: list[tuple[str, Path]] | None,
    storage_dir: Path | None,
) -> list:
    directories = list(provider_storage_dirs or [])
    if storage_dir is not None:
        directories.append(("legacy", storage_dir))

    dispositions = []
    seen_paths: set[Path] = set()
    for _, provider_dir in directories:
        path = safety_dispositions_path(provider_dir)
        if path in seen_paths or not path.exists():
            continue
        seen_paths.add(path)
        dispositions.extend(SafetyDispositionStore(path).list_dispositions())
    return dispositions


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _provider_drivers(provider_summaries: dict[str, dict]) -> list[dict]:
    drivers = []
    for provider, summary in provider_summaries.items():
        score = (
            summary.get("pending_disposition_count", 0) * 4
            + summary.get("top_target_count", 0) * 3
            + summary.get("eval_false_hide_risk_count", 0) * 2
            + summary.get("review_pack_safety_priority_reviews", 0)
        )
        drivers.append(
            {
                "provider": provider,
                "driver_score": score,
                "pending_disposition_count": summary.get("pending_disposition_count", 0),
                "top_target_count": summary.get("top_target_count", 0),
                "eval_false_hide_risk_count": summary.get("eval_false_hide_risk_count", 0),
                "review_pack_safety_priority_reviews": summary.get("review_pack_safety_priority_reviews", 0),
            }
        )
    return sorted(
        drivers,
        key=lambda item: (
            -item["driver_score"],
            -item["top_target_count"],
            item["provider"],
        ),
    )
