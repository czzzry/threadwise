import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ArtifactValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactDescriptor:
    name: str
    path_builder: Callable[..., Path]
    kind: str = "json"
    required_fields: tuple[str, ...] = ()

    def path(self, storage_dir: Path, *args: str) -> Path:
        return self.path_builder(storage_dir, *args)


def _build_registry() -> dict[str, ArtifactDescriptor]:
    return {
        "batch": ArtifactDescriptor(
            "batch",
            lambda storage_dir, batch_id: storage_dir / "batches" / f"{batch_id}.json",
            required_fields=("batch_id", "account_id", "items"),
        ),
        "reports_dir": ArtifactDescriptor("reports_dir", lambda storage_dir: storage_dir / "reports", kind="directory"),
        "daily_report": ArtifactDescriptor(
            "daily_report",
            lambda storage_dir, batch_id: storage_dir / "reports" / f"{batch_id}_daily_report.json",
            required_fields=(
                "account_id",
                "provider",
                "batch_id",
                "report_date",
                "processed_count",
                "unlabeled_count",
            ),
        ),
        "weekly_report": ArtifactDescriptor(
            "weekly_report",
            lambda storage_dir, account_id, window_start, window_end: storage_dir
            / "reports"
            / f"{account_id}_weekly_report_{window_start}_{window_end}.json",
            required_fields=("account_id", "provider", "window_start", "window_end", "processed_count"),
        ),
        "evaluations_dir": ArtifactDescriptor("evaluations_dir", lambda storage_dir: storage_dir / "evaluations", kind="directory"),
        "evaluation_report": ArtifactDescriptor("evaluation_report", lambda storage_dir, evaluation_id: storage_dir / "evaluations" / f"{evaluation_id}.json"),
        "evaluation_preferences": ArtifactDescriptor("evaluation_preferences", lambda storage_dir, evaluation_id: storage_dir / "evaluations" / f"{evaluation_id}-preferences.json"),
        "write_status": ArtifactDescriptor("write_status", lambda storage_dir, batch_id: storage_dir / f"{batch_id}_write_status.json"),
        "write_attempts": ArtifactDescriptor("write_attempts", lambda storage_dir, batch_id: storage_dir / f"{batch_id}_write_attempts.json"),
        "inbox_removal_status": ArtifactDescriptor("inbox_removal_status", lambda storage_dir, batch_id: storage_dir / f"{batch_id}_inbox_removal_status.json"),
        "inbox_removal_attempts": ArtifactDescriptor("inbox_removal_attempts", lambda storage_dir, batch_id: storage_dir / f"{batch_id}_inbox_removal_attempts.json"),
        "unsubscribe_selections": ArtifactDescriptor("unsubscribe_selections", lambda storage_dir: storage_dir / "unsubscribe_selections.json", required_fields=("candidates",)),
        "unsubscribe_execution_audit": ArtifactDescriptor("unsubscribe_execution_audit", lambda storage_dir: storage_dir / "unsubscribe_execution_audit.json", required_fields=("candidates",)),
        "teachable_rules": ArtifactDescriptor("teachable_rules", lambda storage_dir: storage_dir / "teachable_classification_rules.json", required_fields=("rules",)),
        "shadow_suggestion_memory": ArtifactDescriptor("shadow_suggestion_memory", lambda storage_dir: storage_dir / "shadow_suggestion_memory.json"),
        "accepted_shadow_rules": ArtifactDescriptor("accepted_shadow_rules", lambda storage_dir: storage_dir / "accepted_shadow_teachable_rules.json"),
        "review_packs_dir": ArtifactDescriptor("review_packs_dir", lambda storage_dir: storage_dir / "review_packs", kind="directory"),
        "review_pack": ArtifactDescriptor("review_pack", lambda storage_dir, pack_id: storage_dir / "review_packs" / f"{pack_id}.json"),
        "frontier_plans_dir": ArtifactDescriptor("frontier_plans_dir", lambda storage_dir: storage_dir / "frontier_plans", kind="directory"),
        "frontier_plan": ArtifactDescriptor("frontier_plan", lambda storage_dir, plan_id: storage_dir / "frontier_plans" / f"{plan_id}.json"),
        "cluster_decision_packs_dir": ArtifactDescriptor("cluster_decision_packs_dir", lambda storage_dir: storage_dir / "cluster_decision_packs", kind="directory"),
        "cluster_decision_pack": ArtifactDescriptor("cluster_decision_pack", lambda storage_dir, pack_id: storage_dir / "cluster_decision_packs" / f"{pack_id}.json"),
        "runtime_cascades_dir": ArtifactDescriptor("runtime_cascades_dir", lambda storage_dir: storage_dir / "runtime_cascades", kind="directory"),
        "runtime_cascade": ArtifactDescriptor("runtime_cascade", lambda storage_dir, run_id: storage_dir / "runtime_cascades" / f"{run_id}.json"),
        "memory_proposals": ArtifactDescriptor("memory_proposals", lambda storage_dir: storage_dir / "memory_proposals.json", required_fields=("proposals",)),
        "safety_dispositions": ArtifactDescriptor("safety_dispositions", lambda storage_dir: storage_dir / "safety_dispositions.json"),
        "safety_review_digests_dir": ArtifactDescriptor("safety_review_digests_dir", lambda storage_dir: storage_dir / "safety_review_digests", kind="directory"),
        "safety_review_digest": ArtifactDescriptor("safety_review_digest", lambda storage_dir, digest_id: storage_dir / "safety_review_digests" / f"{digest_id}.json"),
        "safety_backlog_reports_dir": ArtifactDescriptor("safety_backlog_reports_dir", lambda storage_dir: storage_dir / "safety_backlog_reports", kind="directory"),
        "safety_backlog_report": ArtifactDescriptor("safety_backlog_report", lambda storage_dir, report_id: storage_dir / "safety_backlog_reports" / f"{report_id}.json"),
        "safety_resolution_packs_dir": ArtifactDescriptor("safety_resolution_packs_dir", lambda storage_dir: storage_dir / "safety_resolution_packs", kind="directory"),
        "safety_resolution_pack": ArtifactDescriptor("safety_resolution_pack", lambda storage_dir, pack_id: storage_dir / "safety_resolution_packs" / f"{pack_id}.json"),
        "latest_safety_triage_manifest": ArtifactDescriptor("latest_safety_triage_manifest", lambda storage_dir: storage_dir / "latest_safety_triage_pass.json"),
        "memory_impact_reports_dir": ArtifactDescriptor("memory_impact_reports_dir", lambda storage_dir: storage_dir / "memory_impact_reports", kind="directory"),
        "memory_impact_report": ArtifactDescriptor("memory_impact_report", lambda storage_dir, report_id: storage_dir / "memory_impact_reports" / f"{report_id}.json"),
        "founder_question_packs_dir": ArtifactDescriptor("founder_question_packs_dir", lambda storage_dir: storage_dir / "founder_question_packs", kind="directory"),
        "founder_question_pack": ArtifactDescriptor("founder_question_pack", lambda storage_dir, pack_id: storage_dir / "founder_question_packs" / f"{pack_id}.json"),
        "founder_answer_packs_dir": ArtifactDescriptor("founder_answer_packs_dir", lambda storage_dir: storage_dir / "founder_answer_packs", kind="directory"),
        "founder_answer_pack": ArtifactDescriptor("founder_answer_pack", lambda storage_dir, pack_id: storage_dir / "founder_answer_packs" / f"{pack_id}.json"),
        "founder_answer_decisions_dir": ArtifactDescriptor("founder_answer_decisions_dir", lambda storage_dir: storage_dir / "founder_answer_decisions", kind="directory"),
        "founder_answer_decision": ArtifactDescriptor("founder_answer_decision", lambda storage_dir, decision_id: storage_dir / "founder_answer_decisions" / f"{decision_id}.json"),
        "founder_answer_applications_dir": ArtifactDescriptor("founder_answer_applications_dir", lambda storage_dir: storage_dir / "founder_answer_applications", kind="directory"),
        "founder_answer_application": ArtifactDescriptor("founder_answer_application", lambda storage_dir, application_id: storage_dir / "founder_answer_applications" / f"{application_id}.json"),
        "founder_policy_batch_packs_dir": ArtifactDescriptor("founder_policy_batch_packs_dir", lambda storage_dir: storage_dir / "founder_policy_batch_packs", kind="directory"),
        "founder_policy_batch_pack": ArtifactDescriptor("founder_policy_batch_pack", lambda storage_dir, pack_id: storage_dir / "founder_policy_batch_packs" / f"{pack_id}.json"),
        "founder_policy_batch_applications_dir": ArtifactDescriptor("founder_policy_batch_applications_dir", lambda storage_dir: storage_dir / "founder_policy_batch_applications", kind="directory"),
        "founder_policy_batch_application": ArtifactDescriptor("founder_policy_batch_application", lambda storage_dir, application_id: storage_dir / "founder_policy_batch_applications" / f"{application_id}.json"),
        "unified_review_queue": ArtifactDescriptor("unified_review_queue", lambda storage_dir: storage_dir / "unified_review_queue.json", required_fields=("summary", "items")),
    }


ARTIFACT_REGISTRY = _build_registry()

CORE_VALIDATED_ARTIFACTS = {
    "batch",
    "daily_report",
    "weekly_report",
    "write_status",
    "inbox_removal_status",
    "teachable_rules",
    "memory_proposals",
    "unsubscribe_selections",
    "unsubscribe_execution_audit",
    "unified_review_queue",
}


def artifact_descriptor(name: str) -> ArtifactDescriptor:
    try:
        return ARTIFACT_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown local artifact: {name}") from exc


def artifact_path(name: str, storage_dir: Path, *args: str) -> Path:
    return artifact_descriptor(name).path(storage_dir, *args)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return load_json(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def load_json_artifact(name: str, storage_dir: Path, *args: str) -> Any:
    payload = load_json(artifact_path(name, storage_dir, *args))
    validate_json_artifact(name, payload)
    return payload


def write_json_artifact(name: str, storage_dir: Path, value: Any, *args: str) -> Path:
    validate_json_artifact(name, value)
    path = artifact_path(name, storage_dir, *args)
    write_json(path, value)
    return path


def validate_json_artifact(name: str, payload: Any) -> None:
    descriptor = artifact_descriptor(name)
    if descriptor.kind != "json" or name not in CORE_VALIDATED_ARTIFACTS:
        return
    if not isinstance(payload, dict):
        raise ArtifactValidationError(f"{name} must be a JSON object")
    for field in descriptor.required_fields:
        if field not in payload:
            raise ArtifactValidationError(f"{name} missing required field: {field}")


def batch_path(storage_dir: Path, batch_id: str) -> Path:
    return artifact_path("batch", storage_dir, batch_id)


def reports_dir(storage_dir: Path) -> Path:
    return artifact_path("reports_dir", storage_dir)


def daily_report_path(storage_dir: Path, batch_id: str) -> Path:
    return artifact_path("daily_report", storage_dir, batch_id)


def weekly_report_path(storage_dir: Path, account_id: str, window_start: str, window_end: str) -> Path:
    return artifact_path("weekly_report", storage_dir, account_id, window_start, window_end)


def evaluations_dir(storage_dir: Path) -> Path:
    return artifact_path("evaluations_dir", storage_dir)


def evaluation_report_path(storage_dir: Path, evaluation_id: str) -> Path:
    return artifact_path("evaluation_report", storage_dir, evaluation_id)


def evaluation_preferences_path(storage_dir: Path, evaluation_id: str) -> Path:
    return artifact_path("evaluation_preferences", storage_dir, evaluation_id)


def write_status_path(storage_dir: Path, batch_id: str) -> Path:
    return artifact_path("write_status", storage_dir, batch_id)


def write_attempts_path(storage_dir: Path, batch_id: str) -> Path:
    return artifact_path("write_attempts", storage_dir, batch_id)


def inbox_removal_status_path(storage_dir: Path, batch_id: str) -> Path:
    return artifact_path("inbox_removal_status", storage_dir, batch_id)


def inbox_removal_attempts_path(storage_dir: Path, batch_id: str) -> Path:
    return artifact_path("inbox_removal_attempts", storage_dir, batch_id)


def unsubscribe_selections_path(storage_dir: Path) -> Path:
    return artifact_path("unsubscribe_selections", storage_dir)


def unsubscribe_execution_audit_path(storage_dir: Path) -> Path:
    return artifact_path("unsubscribe_execution_audit", storage_dir)


def teachable_rules_path(storage_dir: Path) -> Path:
    return artifact_path("teachable_rules", storage_dir)


def shadow_suggestion_memory_path(storage_dir: Path) -> Path:
    return artifact_path("shadow_suggestion_memory", storage_dir)


def accepted_shadow_rules_path(storage_dir: Path) -> Path:
    return artifact_path("accepted_shadow_rules", storage_dir)


def review_packs_dir(storage_dir: Path) -> Path:
    return artifact_path("review_packs_dir", storage_dir)


def review_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return artifact_path("review_pack", storage_dir, pack_id)


def frontier_plans_dir(storage_dir: Path) -> Path:
    return artifact_path("frontier_plans_dir", storage_dir)


def frontier_plan_path(storage_dir: Path, plan_id: str) -> Path:
    return artifact_path("frontier_plan", storage_dir, plan_id)


def cluster_decision_packs_dir(storage_dir: Path) -> Path:
    return artifact_path("cluster_decision_packs_dir", storage_dir)


def cluster_decision_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return artifact_path("cluster_decision_pack", storage_dir, pack_id)


def runtime_cascades_dir(storage_dir: Path) -> Path:
    return artifact_path("runtime_cascades_dir", storage_dir)


def runtime_cascade_path(storage_dir: Path, run_id: str) -> Path:
    return artifact_path("runtime_cascade", storage_dir, run_id)


def memory_proposals_path(storage_dir: Path) -> Path:
    return artifact_path("memory_proposals", storage_dir)


def safety_dispositions_path(storage_dir: Path) -> Path:
    return artifact_path("safety_dispositions", storage_dir)


def safety_review_digests_dir(storage_dir: Path) -> Path:
    return artifact_path("safety_review_digests_dir", storage_dir)


def safety_review_digest_path(storage_dir: Path, digest_id: str) -> Path:
    return artifact_path("safety_review_digest", storage_dir, digest_id)


def safety_backlog_reports_dir(storage_dir: Path) -> Path:
    return artifact_path("safety_backlog_reports_dir", storage_dir)


def safety_backlog_report_path(storage_dir: Path, report_id: str) -> Path:
    return artifact_path("safety_backlog_report", storage_dir, report_id)


def safety_resolution_packs_dir(storage_dir: Path) -> Path:
    return artifact_path("safety_resolution_packs_dir", storage_dir)


def safety_resolution_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return artifact_path("safety_resolution_pack", storage_dir, pack_id)


def latest_safety_triage_manifest_path(storage_dir: Path) -> Path:
    return artifact_path("latest_safety_triage_manifest", storage_dir)


def memory_impact_reports_dir(storage_dir: Path) -> Path:
    return artifact_path("memory_impact_reports_dir", storage_dir)


def memory_impact_report_path(storage_dir: Path, report_id: str) -> Path:
    return artifact_path("memory_impact_report", storage_dir, report_id)


def founder_question_packs_dir(storage_dir: Path) -> Path:
    return artifact_path("founder_question_packs_dir", storage_dir)


def founder_question_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return artifact_path("founder_question_pack", storage_dir, pack_id)


def founder_answer_packs_dir(storage_dir: Path) -> Path:
    return artifact_path("founder_answer_packs_dir", storage_dir)


def founder_answer_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return artifact_path("founder_answer_pack", storage_dir, pack_id)


def founder_answer_decisions_dir(storage_dir: Path) -> Path:
    return artifact_path("founder_answer_decisions_dir", storage_dir)


def founder_answer_decision_path(storage_dir: Path, decision_id: str) -> Path:
    return artifact_path("founder_answer_decision", storage_dir, decision_id)


def founder_answer_applications_dir(storage_dir: Path) -> Path:
    return artifact_path("founder_answer_applications_dir", storage_dir)


def founder_answer_application_path(storage_dir: Path, application_id: str) -> Path:
    return artifact_path("founder_answer_application", storage_dir, application_id)


def founder_policy_batch_packs_dir(storage_dir: Path) -> Path:
    return artifact_path("founder_policy_batch_packs_dir", storage_dir)


def founder_policy_batch_pack_path(storage_dir: Path, pack_id: str) -> Path:
    return artifact_path("founder_policy_batch_pack", storage_dir, pack_id)


def founder_policy_batch_applications_dir(storage_dir: Path) -> Path:
    return artifact_path("founder_policy_batch_applications_dir", storage_dir)


def founder_policy_batch_application_path(storage_dir: Path, application_id: str) -> Path:
    return artifact_path("founder_policy_batch_application", storage_dir, application_id)


def unified_review_queue_path(storage_dir: Path) -> Path:
    return artifact_path("unified_review_queue", storage_dir)
