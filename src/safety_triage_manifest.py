from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import latest_safety_triage_manifest_path, write_json


def build_safety_triage_manifest(
    *,
    report: dict,
    frontier_plan: dict,
    cluster_pack: dict,
    review_pack: dict,
    digest: dict,
    backlog: dict,
    memory_impact: dict | None = None,
    founder_question_pack: dict | None = None,
    founder_answer_pack: dict | None = None,
) -> dict:
    top_target = (digest.get("top_targets") or [None])[0]
    return {
        "generated_at": _now_iso(),
        "artifact_type": "latest-safety-triage-pass",
        "summary": {
            "provider_count": digest.get("summary", {}).get("provider_count", 0),
            "top_target_count": digest.get("summary", {}).get("top_target_count", 0),
            "backlog_pressure": backlog.get("summary", {}).get("backlog_pressure", "clear"),
            "pending_disposition_count": backlog.get("summary", {}).get("pending_disposition_count", 0),
            "approved_disposition_count": backlog.get("summary", {}).get("approved_disposition_count", 0),
            "rejected_disposition_count": backlog.get("summary", {}).get("rejected_disposition_count", 0),
        },
        "top_target": top_target,
        "provider_drivers": list(backlog.get("provider_drivers", []))[:5],
        "top_review_targets": list(review_pack.get("top_review_targets", []))[:5],
        "memory_impact_summary": {
            "accepted_rule_count": (memory_impact or {}).get("summary", {}).get("accepted_rule_count", 0),
            "impacted_rule_count": (memory_impact or {}).get("summary", {}).get("impacted_rule_count", 0),
            "unresolved_before": (memory_impact or {}).get("summary", {}).get("unresolved_before", 0),
            "unresolved_after": (memory_impact or {}).get("summary", {}).get("unresolved_after", 0),
            "unresolved_delta": (memory_impact or {}).get("summary", {}).get("unresolved_delta", 0),
        },
        "top_memory_impacts": list((memory_impact or {}).get("top_memory_impacts", []))[:5],
        "next_review_payoffs": list((memory_impact or {}).get("next_review_payoffs", []))[:5],
        "founder_question_summary": {
            "question_count": (founder_question_pack or {}).get("summary", {}).get("question_count", 0),
            "estimated_unblocked_messages": (founder_question_pack or {}).get("summary", {}).get("estimated_unblocked_messages", 0),
        },
        "founder_questions": list((founder_question_pack or {}).get("questions", []))[:5],
        "founder_answer_summary": {
            "actionable_answer_count": (founder_answer_pack or {}).get("summary", {}).get("actionable_answer_count", 0),
            "answer_option_count": (founder_answer_pack or {}).get("summary", {}).get("answer_option_count", 0),
        },
        "founder_answer_previews": _top_founder_answer_previews(founder_answer_pack),
        "artifacts": {
            "eval_report_path": report.get("report_path"),
            "frontier_plan_path": frontier_plan.get("plan_path"),
            "cluster_pack_path": cluster_pack.get("pack_path"),
            "review_pack_path": review_pack.get("pack_path"),
            "safety_digest_path": digest.get("digest_path"),
            "backlog_report_path": backlog.get("report_path"),
            "memory_impact_report_path": (memory_impact or {}).get("report_path"),
            "founder_question_pack_path": (founder_question_pack or {}).get("pack_path"),
            "founder_answer_pack_path": (founder_answer_pack or {}).get("pack_path"),
        },
    }


def write_safety_triage_manifest(
    output_storage_dir: Path,
    *,
    report: dict,
    frontier_plan: dict,
    cluster_pack: dict,
    review_pack: dict,
    digest: dict,
    backlog: dict,
    memory_impact: dict | None = None,
    founder_question_pack: dict | None = None,
    founder_answer_pack: dict | None = None,
) -> dict:
    payload = build_safety_triage_manifest(
        report=report,
        frontier_plan=frontier_plan,
        cluster_pack=cluster_pack,
        review_pack=review_pack,
        digest=digest,
        backlog=backlog,
        memory_impact=memory_impact,
        founder_question_pack=founder_question_pack,
        founder_answer_pack=founder_answer_pack,
    )
    path = latest_safety_triage_manifest_path(output_storage_dir)
    write_json(path, payload)
    payload["manifest_path"] = str(path)
    return payload


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _top_founder_answer_previews(founder_answer_pack: dict | None) -> list[dict]:
    previews = []
    for question in (founder_answer_pack or {}).get("questions", []):
        for answer in question.get("answer_options", []):
            projection = answer.get("projection", {})
            if projection.get("estimated_resolved_messages", 0) <= 0:
                continue
            previews.append(
                {
                    "question_id": question.get("question_id", ""),
                    "theme": question.get("theme", ""),
                    "answer_key": answer.get("answer_key", ""),
                    "estimated_resolved_messages": projection.get("estimated_resolved_messages", 0),
                    "proposal_count": projection.get("proposal_count", 0),
                }
            )
    previews.sort(
        key=lambda item: (
            -item["estimated_resolved_messages"],
            -item["proposal_count"],
            item["theme"],
            item["answer_key"],
        )
    )
    return previews[:5]
