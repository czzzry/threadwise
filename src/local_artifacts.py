import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return load_json(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def batch_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / "batches" / f"{batch_id}.json"


def reports_dir(storage_dir: Path) -> Path:
    return storage_dir / "reports"


def daily_report_path(storage_dir: Path, batch_id: str) -> Path:
    return reports_dir(storage_dir) / f"{batch_id}_daily_report.json"


def weekly_report_path(storage_dir: Path, account_id: str, window_start: str, window_end: str) -> Path:
    return reports_dir(storage_dir) / f"{account_id}_weekly_report_{window_start}_{window_end}.json"


def evaluations_dir(storage_dir: Path) -> Path:
    return storage_dir / "evaluations"


def evaluation_report_path(storage_dir: Path, evaluation_id: str) -> Path:
    return evaluations_dir(storage_dir) / f"{evaluation_id}.json"


def evaluation_preferences_path(storage_dir: Path, evaluation_id: str) -> Path:
    return evaluations_dir(storage_dir) / f"{evaluation_id}-preferences.json"


def write_status_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_write_status.json"


def write_attempts_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_write_attempts.json"


def inbox_removal_status_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_inbox_removal_status.json"


def inbox_removal_attempts_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_inbox_removal_attempts.json"


def unsubscribe_selections_path(storage_dir: Path) -> Path:
    return storage_dir / "unsubscribe_selections.json"


def unsubscribe_execution_audit_path(storage_dir: Path) -> Path:
    return storage_dir / "unsubscribe_execution_audit.json"


def teachable_rules_path(storage_dir: Path) -> Path:
    return storage_dir / "teachable_classification_rules.json"


def shadow_suggestion_memory_path(storage_dir: Path) -> Path:
    return storage_dir / "shadow_suggestion_memory.json"


def accepted_shadow_rules_path(storage_dir: Path) -> Path:
    return storage_dir / "accepted_shadow_teachable_rules.json"


def review_packs_dir(storage_dir: Path) -> Path:
    return storage_dir / "review_packs"


def review_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return review_packs_dir(storage_dir) / f"{pack_id}.json"


def frontier_plans_dir(storage_dir: Path) -> Path:
    return storage_dir / "frontier_plans"


def frontier_plan_path(storage_dir: Path, plan_id: str) -> Path:
    return frontier_plans_dir(storage_dir) / f"{plan_id}.json"


def cluster_decision_packs_dir(storage_dir: Path) -> Path:
    return storage_dir / "cluster_decision_packs"


def cluster_decision_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return cluster_decision_packs_dir(storage_dir) / f"{pack_id}.json"


def runtime_cascades_dir(storage_dir: Path) -> Path:
    return storage_dir / "runtime_cascades"


def runtime_cascade_path(storage_dir: Path, run_id: str) -> Path:
    return runtime_cascades_dir(storage_dir) / f"{run_id}.json"


def memory_proposals_path(storage_dir: Path) -> Path:
    return storage_dir / "memory_proposals.json"


def safety_dispositions_path(storage_dir: Path) -> Path:
    return storage_dir / "safety_dispositions.json"


def safety_review_digests_dir(storage_dir: Path) -> Path:
    return storage_dir / "safety_review_digests"


def safety_review_digest_path(storage_dir: Path, digest_id: str) -> Path:
    return safety_review_digests_dir(storage_dir) / f"{digest_id}.json"


def safety_backlog_reports_dir(storage_dir: Path) -> Path:
    return storage_dir / "safety_backlog_reports"


def safety_backlog_report_path(storage_dir: Path, report_id: str) -> Path:
    return safety_backlog_reports_dir(storage_dir) / f"{report_id}.json"


def safety_resolution_packs_dir(storage_dir: Path) -> Path:
    return storage_dir / "safety_resolution_packs"


def safety_resolution_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return safety_resolution_packs_dir(storage_dir) / f"{pack_id}.json"


def latest_safety_triage_manifest_path(storage_dir: Path) -> Path:
    return storage_dir / "latest_safety_triage_pass.json"


def memory_impact_reports_dir(storage_dir: Path) -> Path:
    return storage_dir / "memory_impact_reports"


def memory_impact_report_path(storage_dir: Path, report_id: str) -> Path:
    return memory_impact_reports_dir(storage_dir) / f"{report_id}.json"


def founder_question_packs_dir(storage_dir: Path) -> Path:
    return storage_dir / "founder_question_packs"


def founder_question_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return founder_question_packs_dir(storage_dir) / f"{pack_id}.json"


def founder_answer_packs_dir(storage_dir: Path) -> Path:
    return storage_dir / "founder_answer_packs"


def founder_answer_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return founder_answer_packs_dir(storage_dir) / f"{pack_id}.json"


def founder_answer_decisions_dir(storage_dir: Path) -> Path:
    return storage_dir / "founder_answer_decisions"


def founder_answer_decision_path(storage_dir: Path, decision_id: str) -> Path:
    return founder_answer_decisions_dir(storage_dir) / f"{decision_id}.json"


def founder_answer_applications_dir(storage_dir: Path) -> Path:
    return storage_dir / "founder_answer_applications"


def founder_answer_application_path(storage_dir: Path, application_id: str) -> Path:
    return founder_answer_applications_dir(storage_dir) / f"{application_id}.json"


def founder_policy_batch_packs_dir(storage_dir: Path) -> Path:
    return storage_dir / "founder_policy_batch_packs"


def founder_policy_batch_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return founder_policy_batch_packs_dir(storage_dir) / f"{pack_id}.json"


def founder_policy_batch_applications_dir(storage_dir: Path) -> Path:
    return storage_dir / "founder_policy_batch_applications"


def founder_policy_batch_application_path(storage_dir: Path, application_id: str) -> Path:
    return founder_policy_batch_applications_dir(storage_dir) / f"{application_id}.json"


def unified_review_queue_path(storage_dir: Path) -> Path:
    return storage_dir / "unified_review_queue.json"
