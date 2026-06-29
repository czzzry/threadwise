from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json, write_json


DEFAULT_WINDOW = 5
PASS = "PASS"
WARN = "WARN"
PAUSE = "PAUSE"
TARGET_UNRESOLVED_RATE = 0.10
WARN_UNRESOLVED_RATE = 0.15
PAUSE_UNRESOLVED_RATE = 0.25
WARN_FOUNDER_QUESTION_COUNT = 20
PAUSE_QUEUE_PENDING_COUNT = 200
WARN_QUEUE_PENDING_COUNT = 75


def build_operational_readiness_report(output_storage_dir: Path, *, window: int = DEFAULT_WINDOW) -> dict:
    runtime_reports = _latest_runtime_reports(output_storage_dir, window)
    if not runtime_reports:
        return {
            "generated_at": _now_iso(),
            "artifact_type": "operational-readiness-report",
            "overall_status": WARN,
            "summary": {
                "run_count": 0,
                "reason_count": 1,
            },
            "reasons": ["No runtime cascade reports were found."],
            "runs": [],
        }

    queue_summary = _load_queue_summary(output_storage_dir)
    founder_signal = _founder_application_signal(output_storage_dir)
    runs = [_runtime_run_summary(path, payload) for path, payload in runtime_reports]
    status, reasons = _judge_status(runs, queue_summary=queue_summary, founder_signal=founder_signal)
    latest = runs[-1]
    unresolved_rates = [run["unresolved_rate"] for run in runs]
    caution_rates = [run["caution_rate"] for run in runs]
    progress = _progress_summary(output_storage_dir, runs, queue_summary=queue_summary)

    return {
        "generated_at": _now_iso(),
        "artifact_type": "operational-readiness-report",
        "overall_status": status,
        "summary": {
            "run_count": len(runs),
            "latest_run_id": latest["run_id"],
            "latest_message_count": latest["message_count"],
            "latest_unresolved_count": latest["unresolved_count"],
            "latest_unresolved_rate": latest["unresolved_rate"],
            "latest_queue_pending_count": queue_summary.get("pending_count", 0),
            "latest_queue_founder_question_count": queue_summary.get("pending_by_type", {}).get("founder-question", 0),
            "recent_avg_unresolved_rate": _round(sum(unresolved_rates) / len(unresolved_rates)),
            "recent_max_unresolved_rate": max(unresolved_rates),
            "recent_avg_caution_rate": _round(sum(caution_rates) / len(caution_rates)),
            "founder_application_count": founder_signal["application_count"],
            "founder_resolved_gain_total": founder_signal["resolved_gain_total"],
            "target_unresolved_rate": TARGET_UNRESOLVED_RATE,
            "target_founder_question_limit": WARN_FOUNDER_QUESTION_COUNT,
            "reason_count": len(reasons),
        },
        "queue_summary": queue_summary,
        "founder_signal": founder_signal,
        "progress": progress,
        "reasons": reasons,
        "runs": runs,
    }


def write_operational_readiness_report(output_storage_dir: Path, *, window: int = DEFAULT_WINDOW) -> dict:
    payload = build_operational_readiness_report(output_storage_dir, window=window)
    reports_dir = output_storage_dir / "operational_readiness_reports"
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = reports_dir / f"operational-readiness-{timestamp}.json"
    write_json(path, payload)
    payload["report_path"] = str(path)
    return payload


def _judge_status(runs: list[dict], *, queue_summary: dict, founder_signal: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    status = PASS
    latest = runs[-1]
    pending_count = int(queue_summary.get("pending_count", 0))
    founder_questions = int(queue_summary.get("pending_by_type", {}).get("founder-question", 0))
    recent_unresolved = [run["unresolved_rate"] for run in runs]
    recent_growth = latest["unresolved_rate"] - min(recent_unresolved)

    if len(runs) < 3:
        status = _worsen(status, WARN)
        reasons.append("Fewer than 3 recent runs are available, so stability is not yet proven.")
    if latest["unresolved_rate"] > PAUSE_UNRESOLVED_RATE:
        status = _worsen(status, PAUSE)
        reasons.append(f"Latest unresolved rate is {latest['unresolved_rate'] * 100:.2f}%, which is too high.")
    elif latest["unresolved_rate"] > WARN_UNRESOLVED_RATE:
        status = _worsen(status, WARN)
        reasons.append(f"Latest unresolved rate is {latest['unresolved_rate'] * 100:.2f}%, which is still heavy.")

    if recent_growth > 0.05:
        status = _worsen(status, WARN)
        reasons.append("Recent runs show unresolved pressure growing instead of shrinking.")

    if pending_count > PAUSE_QUEUE_PENDING_COUNT:
        status = _worsen(status, PAUSE)
        reasons.append(f"The unified review queue has {pending_count} pending items, which is too much operator debt.")
    elif pending_count > WARN_QUEUE_PENDING_COUNT:
        status = _worsen(status, WARN)
        reasons.append(f"The unified review queue still has {pending_count} pending items.")

    if founder_questions > WARN_FOUNDER_QUESTION_COUNT:
        status = _worsen(status, WARN)
        reasons.append(f"There are {founder_questions} founder questions pending, which is more than the loop should ask at once.")

    if latest["caution_rate"] > 0.12:
        status = _worsen(status, WARN)
        reasons.append("A large share of the latest run is still landing in the caution lane.")

    if founder_signal["application_count"] == 0:
        status = _worsen(status, WARN)
        reasons.append("No founder-answer applications have been recorded yet, so the feedback loop is not fully proven.")

    if not reasons:
        reasons.append("Recent runs are stable enough by current thresholds.")
    return status, reasons


def _load_queue_summary(output_storage_dir: Path) -> dict:
    path = output_storage_dir / "unified_review_queue.json"
    if not path.exists():
        return {"pending_count": 0, "pending_by_type": {}, "provider_counts": {}}
    payload = load_json(path)
    return dict(payload.get("summary", {}))


def _founder_application_signal(output_storage_dir: Path) -> dict:
    applications_dir = output_storage_dir / "founder_answer_applications"
    if not applications_dir.exists():
        return {"application_count": 0, "resolved_gain_total": 0}
    application_paths = sorted(applications_dir.glob("*.json"))
    resolved_gain_total = 0
    for path in application_paths:
        payload = load_json(path)
        resolved_gain_total += int(payload.get("impact_delta", {}).get("resolved_gain", 0))
    return {
        "application_count": len(application_paths),
        "resolved_gain_total": resolved_gain_total,
    }


def _latest_runtime_reports(output_storage_dir: Path, window: int) -> list[tuple[Path, dict]]:
    runtime_dir = output_storage_dir / "runtime_cascades"
    if not runtime_dir.exists():
        return []
    paths = sorted(runtime_dir.glob("*.json"))[-window:]
    return [(path, load_json(path)) for path in paths]


def _runtime_run_summary(path: Path, payload: dict) -> dict:
    summary = payload.get("summary", {})
    message_count = int(summary.get("message_count", 0))
    unresolved_count = int(summary.get("unresolved_count", 0))
    caution_count = int(summary.get("safety_review_count", 0))
    llm_count = int(summary.get("llm_escalation_count", 0))
    memory_count = int(summary.get("accepted_memory_count", 0))
    deterministic_count = int(summary.get("deterministic_count", 0))
    return {
        "run_id": path.stem,
        "generated_at": payload.get("generated_at", ""),
        "message_count": message_count,
        "resolved_count": int(summary.get("resolved_count", 0)),
        "unresolved_count": unresolved_count,
        "unresolved_rate": _fraction(unresolved_count, message_count),
        "caution_count": caution_count,
        "caution_rate": _fraction(caution_count, message_count),
        "llm_escalation_count": llm_count,
        "memory_count": memory_count,
        "deterministic_count": deterministic_count,
    }


def _progress_summary(output_storage_dir: Path, runs: list[dict], *, queue_summary: dict) -> dict:
    latest = runs[-1]
    baseline = _historical_worst_unresolved_rate(output_storage_dir)
    current = latest["unresolved_rate"]
    if baseline <= TARGET_UNRESOLVED_RATE:
        unresolved_progress_fraction = 1.0
    else:
        unresolved_progress_fraction = _round(
            max(0.0, min(1.0, (baseline - current) / (baseline - TARGET_UNRESOLVED_RATE)))
        )
    target_unresolved_count = int(latest["message_count"] * TARGET_UNRESOLVED_RATE)
    remaining_unresolved_gap = max(0, latest["unresolved_count"] - target_unresolved_count)
    founder_questions = int(queue_summary.get("pending_by_type", {}).get("founder-question", 0))
    return {
        "unresolved_baseline_rate": baseline,
        "unresolved_current_rate": current,
        "unresolved_target_rate": TARGET_UNRESOLVED_RATE,
        "unresolved_progress_fraction": unresolved_progress_fraction,
        "unresolved_current_count": latest["unresolved_count"],
        "unresolved_target_count": target_unresolved_count,
        "unresolved_remaining_gap_count": remaining_unresolved_gap,
        "founder_question_count": founder_questions,
        "founder_question_limit": WARN_FOUNDER_QUESTION_COUNT,
    }


def _historical_worst_unresolved_rate(output_storage_dir: Path) -> float:
    runtime_dir = output_storage_dir / "runtime_cascades"
    if not runtime_dir.exists():
        return TARGET_UNRESOLVED_RATE
    worst = TARGET_UNRESOLVED_RATE
    for path in sorted(runtime_dir.glob("*.json")):
        payload = load_json(path)
        summary = payload.get("summary", {})
        message_count = int(summary.get("message_count", 0))
        unresolved_count = int(summary.get("unresolved_count", 0))
        if message_count <= 0:
            continue
        worst = max(worst, _fraction(unresolved_count, message_count))
    return worst


def _fraction(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round(numerator / denominator)


def _round(value: float) -> float:
    return round(value, 4)


def _worsen(current: str, candidate: str) -> str:
    order = {PASS: 0, WARN: 1, PAUSE: 2}
    return candidate if order[candidate] > order[current] else current


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
