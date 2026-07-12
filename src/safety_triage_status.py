from pathlib import Path

from src.local_artifacts import latest_safety_triage_manifest_path, load_json, safety_backlog_reports_dir


def build_safety_triage_status(output_storage_dir: Path, history_limit: int = 5) -> dict:
    manifest_path = latest_safety_triage_manifest_path(output_storage_dir)
    if not manifest_path.exists():
        return {
            "status": "missing",
            "message": "No safety triage manifest found.",
            "history": [],
        }

    manifest = load_json(manifest_path)
    history = _load_backlog_history(output_storage_dir, history_limit)
    trend = _build_trend(history)

    return {
        "status": "ready",
        "manifest_path": str(manifest_path),
        "latest": {
            "generated_at": manifest.get("generated_at", ""),
            "backlog_pressure": manifest.get("summary", {}).get("backlog_pressure", "clear"),
            "pending_disposition_count": manifest.get("summary", {}).get("pending_disposition_count", 0),
            "approved_disposition_count": manifest.get("summary", {}).get("approved_disposition_count", 0),
            "rejected_disposition_count": manifest.get("summary", {}).get("rejected_disposition_count", 0),
            "top_target_count": manifest.get("summary", {}).get("top_target_count", 0),
            "top_target": manifest.get("top_target"),
            "provider_drivers": list(manifest.get("provider_drivers", [])),
            "top_review_targets": list(manifest.get("top_review_targets", [])),
            "memory_impact_summary": dict(manifest.get("memory_impact_summary", {})),
            "top_memory_impacts": list(manifest.get("top_memory_impacts", [])),
            "next_review_payoffs": list(manifest.get("next_review_payoffs", [])),
            "founder_question_summary": dict(manifest.get("founder_question_summary", {})),
            "founder_questions": list(manifest.get("founder_questions", [])),
            "founder_answer_summary": dict(manifest.get("founder_answer_summary", {})),
            "founder_answer_previews": list(manifest.get("founder_answer_previews", [])),
            "latest_founder_answer_application": dict(manifest.get("latest_founder_answer_application", {})),
        },
        "history": history,
        "trend": trend,
        "artifacts": manifest.get("artifacts", {}),
    }


def _load_backlog_history(output_storage_dir: Path, history_limit: int) -> list[dict]:
    reports_dir = safety_backlog_reports_dir(output_storage_dir)
    if not reports_dir.exists():
        return []

    history = []
    for path in sorted(reports_dir.glob("*.json"))[-history_limit:]:
        payload = load_json(path)
        summary = payload.get("summary", {})
        history.append(
            {
                "report_path": str(path),
                "generated_at": payload.get("generated_at", ""),
                "backlog_pressure": summary.get("backlog_pressure", "clear"),
                "pending_disposition_count": summary.get("pending_disposition_count", 0),
                "approved_disposition_count": summary.get("approved_disposition_count", 0),
                "rejected_disposition_count": summary.get("rejected_disposition_count", 0),
                "top_target_count": summary.get("top_target_count", 0),
            }
        )
    return history


def _build_trend(history: list[dict]) -> dict:
    if len(history) < 2:
        return {
            "direction": "unknown",
            "pending_delta": 0,
            "top_target_delta": 0,
            "summary": "Not enough history yet.",
        }

    first = history[0]
    last = history[-1]
    pending_delta = last["pending_disposition_count"] - first["pending_disposition_count"]
    top_target_delta = last["top_target_count"] - first["top_target_count"]

    if pending_delta < 0 or top_target_delta < 0:
        direction = "improving"
    elif pending_delta > 0 or top_target_delta > 0:
        direction = "worsening"
    else:
        direction = "stable"

    return {
        "direction": direction,
        "pending_delta": pending_delta,
        "top_target_delta": top_target_delta,
        "summary": (
            f"{direction}: pending delta={pending_delta}, top-target delta={top_target_delta}"
        ),
    }
