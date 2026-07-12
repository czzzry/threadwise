import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import (
    ARTIFACT_REGISTRY,
    CORE_VALIDATED_ARTIFACTS,
    ArtifactValidationError,
    accepted_shadow_rules_path,
    artifact_descriptor,
    artifact_path,
    batch_path,
    candidate_changes_path,
    cluster_decision_pack_path,
    cluster_decision_packs_dir,
    daily_report_path,
    evaluation_preferences_path,
    evaluation_report_path,
    evaluations_dir,
    founder_answer_application_path,
    founder_answer_applications_dir,
    founder_answer_decision_path,
    founder_answer_decisions_dir,
    founder_answer_pack_path,
    founder_answer_packs_dir,
    founder_policy_batch_application_path,
    founder_policy_batch_applications_dir,
    founder_policy_batch_pack_path,
    founder_policy_batch_packs_dir,
    founder_question_pack_path,
    founder_question_packs_dir,
    frontier_plan_path,
    frontier_plans_dir,
    inbox_removal_attempts_path,
    inbox_removal_status_path,
    latest_safety_triage_manifest_path,
    load_json_artifact,
    memory_impact_report_path,
    memory_impact_reports_dir,
    memory_proposals_path,
    reports_dir,
    review_pack_path,
    review_packs_dir,
    runtime_cascade_path,
    runtime_cascades_dir,
    safety_backlog_report_path,
    safety_backlog_reports_dir,
    safety_dispositions_path,
    safety_resolution_pack_path,
    safety_resolution_packs_dir,
    safety_review_digest_path,
    safety_review_digests_dir,
    shadow_suggestion_memory_path,
    teaching_exclusions_path,
    teachable_rules_path,
    unified_review_queue_path,
    unsubscribe_execution_audit_path,
    unsubscribe_selections_path,
    validate_json_artifact,
    weekly_report_path,
    write_attempts_path,
    write_json_artifact,
    write_status_path,
)


class LocalArtifactsRegistryTests(unittest.TestCase):
    def test_registry_covers_current_helper_surface(self) -> None:
        expected_names = {
            "batch",
            "reports_dir",
            "daily_report",
            "weekly_report",
            "evaluations_dir",
            "evaluation_report",
            "evaluation_preferences",
            "write_status",
            "write_attempts",
            "inbox_removal_status",
            "inbox_removal_attempts",
            "unsubscribe_selections",
            "unsubscribe_execution_audit",
            "teachable_rules",
            "teaching_exclusions",
            "shadow_suggestion_memory",
            "accepted_shadow_rules",
            "review_packs_dir",
            "review_pack",
            "frontier_plans_dir",
            "frontier_plan",
            "cluster_decision_packs_dir",
            "cluster_decision_pack",
            "runtime_cascades_dir",
            "runtime_cascade",
            "memory_proposals",
            "candidate_changes",
            "safety_dispositions",
            "safety_review_digests_dir",
            "safety_review_digest",
            "safety_backlog_reports_dir",
            "safety_backlog_report",
            "safety_resolution_packs_dir",
            "safety_resolution_pack",
            "latest_safety_triage_manifest",
            "memory_impact_reports_dir",
            "memory_impact_report",
            "founder_question_packs_dir",
            "founder_question_pack",
            "founder_answer_packs_dir",
            "founder_answer_pack",
            "founder_answer_decisions_dir",
            "founder_answer_decision",
            "founder_answer_applications_dir",
            "founder_answer_application",
            "founder_policy_batch_packs_dir",
            "founder_policy_batch_pack",
            "founder_policy_batch_applications_dir",
            "founder_policy_batch_application",
            "unified_review_queue",
        }

        self.assertEqual(set(ARTIFACT_REGISTRY), expected_names)

    def test_registry_preserves_existing_helper_paths(self) -> None:
        storage_dir = Path("/tmp/threadwise-artifacts")

        expectations = {
            "batch": (batch_path(storage_dir, "batch-1"), ("batch-1",)),
            "reports_dir": (reports_dir(storage_dir), ()),
            "daily_report": (daily_report_path(storage_dir, "batch-1"), ("batch-1",)),
            "weekly_report": (weekly_report_path(storage_dir, "acct", "2026-06-24", "2026-06-30"), ("acct", "2026-06-24", "2026-06-30")),
            "evaluations_dir": (evaluations_dir(storage_dir), ()),
            "evaluation_report": (evaluation_report_path(storage_dir, "eval-1"), ("eval-1",)),
            "evaluation_preferences": (evaluation_preferences_path(storage_dir, "eval-1"), ("eval-1",)),
            "write_status": (write_status_path(storage_dir, "batch-1"), ("batch-1",)),
            "write_attempts": (write_attempts_path(storage_dir, "batch-1"), ("batch-1",)),
            "inbox_removal_status": (inbox_removal_status_path(storage_dir, "batch-1"), ("batch-1",)),
            "inbox_removal_attempts": (inbox_removal_attempts_path(storage_dir, "batch-1"), ("batch-1",)),
            "unsubscribe_selections": (unsubscribe_selections_path(storage_dir), ()),
            "unsubscribe_execution_audit": (unsubscribe_execution_audit_path(storage_dir), ()),
            "teachable_rules": (teachable_rules_path(storage_dir), ()),
            "teaching_exclusions": (teaching_exclusions_path(storage_dir), ()),
            "shadow_suggestion_memory": (shadow_suggestion_memory_path(storage_dir), ()),
            "accepted_shadow_rules": (accepted_shadow_rules_path(storage_dir), ()),
            "review_packs_dir": (review_packs_dir(storage_dir), ()),
            "review_pack": (review_pack_path(storage_dir, "pack-1"), ("pack-1",)),
            "frontier_plans_dir": (frontier_plans_dir(storage_dir), ()),
            "frontier_plan": (frontier_plan_path(storage_dir, "plan-1"), ("plan-1",)),
            "cluster_decision_packs_dir": (cluster_decision_packs_dir(storage_dir), ()),
            "cluster_decision_pack": (cluster_decision_pack_path(storage_dir, "pack-1"), ("pack-1",)),
            "runtime_cascades_dir": (runtime_cascades_dir(storage_dir), ()),
            "runtime_cascade": (runtime_cascade_path(storage_dir, "run-1"), ("run-1",)),
            "memory_proposals": (memory_proposals_path(storage_dir), ()),
            "candidate_changes": (candidate_changes_path(storage_dir), ()),
            "safety_dispositions": (safety_dispositions_path(storage_dir), ()),
            "safety_review_digests_dir": (safety_review_digests_dir(storage_dir), ()),
            "safety_review_digest": (safety_review_digest_path(storage_dir, "digest-1"), ("digest-1",)),
            "safety_backlog_reports_dir": (safety_backlog_reports_dir(storage_dir), ()),
            "safety_backlog_report": (safety_backlog_report_path(storage_dir, "report-1"), ("report-1",)),
            "safety_resolution_packs_dir": (safety_resolution_packs_dir(storage_dir), ()),
            "safety_resolution_pack": (safety_resolution_pack_path(storage_dir, "pack-1"), ("pack-1",)),
            "latest_safety_triage_manifest": (latest_safety_triage_manifest_path(storage_dir), ()),
            "memory_impact_reports_dir": (memory_impact_reports_dir(storage_dir), ()),
            "memory_impact_report": (memory_impact_report_path(storage_dir, "report-1"), ("report-1",)),
            "founder_question_packs_dir": (founder_question_packs_dir(storage_dir), ()),
            "founder_question_pack": (founder_question_pack_path(storage_dir, "pack-1"), ("pack-1",)),
            "founder_answer_packs_dir": (founder_answer_packs_dir(storage_dir), ()),
            "founder_answer_pack": (founder_answer_pack_path(storage_dir, "pack-1"), ("pack-1",)),
            "founder_answer_decisions_dir": (founder_answer_decisions_dir(storage_dir), ()),
            "founder_answer_decision": (founder_answer_decision_path(storage_dir, "decision-1"), ("decision-1",)),
            "founder_answer_applications_dir": (founder_answer_applications_dir(storage_dir), ()),
            "founder_answer_application": (founder_answer_application_path(storage_dir, "application-1"), ("application-1",)),
            "founder_policy_batch_packs_dir": (founder_policy_batch_packs_dir(storage_dir), ()),
            "founder_policy_batch_pack": (founder_policy_batch_pack_path(storage_dir, "pack-1"), ("pack-1",)),
            "founder_policy_batch_applications_dir": (founder_policy_batch_applications_dir(storage_dir), ()),
            "founder_policy_batch_application": (founder_policy_batch_application_path(storage_dir, "application-1"), ("application-1",)),
            "unified_review_queue": (unified_review_queue_path(storage_dir), ()),
        }

        for artifact_name, (expected_path, path_args) in expectations.items():
            with self.subTest(artifact_name=artifact_name):
                self.assertEqual(artifact_path(artifact_name, storage_dir, *path_args), expected_path)

    def test_json_artifact_helpers_preserve_json_read_write_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            payload = {
                "batch_id": "batch-1",
                "account_id": "acct",
                "items": [],
            }

            path = write_json_artifact("batch", storage_dir, payload, "batch-1")

            self.assertEqual(path, batch_path(storage_dir, "batch-1"))
            self.assertEqual(json.loads(path.read_text()), payload)
            self.assertEqual(load_json_artifact("batch", storage_dir, "batch-1"), payload)

    def test_core_artifact_validation_is_minimal_and_opt_in(self) -> None:
        self.assertEqual(
            CORE_VALIDATED_ARTIFACTS,
            {
                "batch",
                "daily_report",
                "weekly_report",
                "write_status",
                "inbox_removal_status",
                "teachable_rules",
                "memory_proposals",
                "candidate_changes",
                "unsubscribe_selections",
                "unsubscribe_execution_audit",
                "unified_review_queue",
            },
        )
        self.assertIsNone(validate_json_artifact("write_status", {"message-1": "applied"}))
        self.assertIsNone(validate_json_artifact("teachable_rules", {"rules": []}))
        self.assertIsNone(validate_json_artifact("unified_review_queue", {"summary": {}, "items": []}))

        with self.assertRaisesRegex(ArtifactValidationError, "batch missing required field: items"):
            validate_json_artifact("batch", {"batch_id": "batch-1", "account_id": "acct"})

        with self.assertRaisesRegex(ArtifactValidationError, "write_status must be a JSON object"):
            validate_json_artifact("write_status", [])

    def test_unknown_artifact_name_fails_clearly(self) -> None:
        with self.assertRaisesRegex(KeyError, "Unknown local artifact"):
            artifact_descriptor("not-real")


if __name__ == "__main__":
    unittest.main()
