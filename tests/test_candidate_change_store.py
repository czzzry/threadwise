import tempfile
import unittest
from pathlib import Path

from src.candidate_change_store import (
    CandidateChange,
    CandidateChangeStore,
    candidate_kind_for_teaching_apply_mode,
)
from src.local_artifacts import candidate_changes_path


class CandidateChangeStoreTests(unittest.TestCase):
    def test_product_originated_future_rule_candidate_persists_and_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / "gmail_fetch"
            store = CandidateChangeStore(candidate_changes_path(storage_dir))
            candidate = CandidateChange(
                id="candidate-future-rule-001",
                kind="future-rule",
                source="sidebar-teach",
                title="Teach future rule for weekly vendor digest",
                description="Save a reusable newsletter rule from inbox teaching.",
                affected_scope_summary="future mail matching vendor digest family",
                provider="gmail",
                account_id="founder-test",
                source_refs=("proposal:teach-001", "message:gmail:founder-test-batch-1:g1"),
                metadata={"apply_mode": "future-only"},
                created_at="2026-07-10T10:00:00Z",
                updated_at="2026-07-10T10:00:00Z",
            )

            store.save_candidate(candidate)
            saved = store.list_candidates()

            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].kind, "future-rule")
            self.assertEqual(saved[0].status, "pending")
            self.assertEqual(saved[0].source_refs[0], "proposal:teach-001")

    def test_code_originated_candidate_persists_and_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / "classifier_eval"
            store = CandidateChangeStore(candidate_changes_path(storage_dir))
            candidate = CandidateChange(
                id="candidate-code-change-001",
                kind="classifier-code-change",
                source="dev-workflow",
                title="Tighten billing/security classification",
                description="Change deterministic classifier behavior for billing and account-security families.",
                affected_scope_summary="deterministic classifier behavior",
                source_refs=("file:src/fixture_classifier.py", "commit:local-working-tree"),
                metadata={"changed_files": ["src/fixture_classifier.py", "tests/test_fixture_classifier.py"]},
                created_at="2026-07-10T10:05:00Z",
                updated_at="2026-07-10T10:05:00Z",
            )

            store.save_candidate(candidate)
            reloaded = store.get_candidate("candidate-code-change-001")

            self.assertEqual(reloaded.kind, "classifier-code-change")
            self.assertEqual(reloaded.source, "dev-workflow")
            self.assertEqual(reloaded.metadata["changed_files"][0], "src/fixture_classifier.py")

    def test_current_only_teach_does_not_become_candidate_by_default(self) -> None:
        self.assertIsNone(candidate_kind_for_teaching_apply_mode("current-only"))
        self.assertIsNone(candidate_kind_for_teaching_apply_mode("matching-existing"))

    def test_future_teaching_modes_map_to_reusable_candidate_kinds(self) -> None:
        self.assertEqual(candidate_kind_for_teaching_apply_mode("save-future-rule"), "future-rule")
        self.assertEqual(candidate_kind_for_teaching_apply_mode("future-only"), "future-rule")
        self.assertEqual(candidate_kind_for_teaching_apply_mode("apply-included"), "future-rule")

    def test_candidate_status_and_evaluation_reference_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / "gmail_fetch"
            store = CandidateChangeStore(candidate_changes_path(storage_dir))
            candidate = CandidateChange(
                id="candidate-amendment-001",
                kind="rule-amendment",
                source="sidebar-teach-amendment",
                title="Narrow future rule boundary",
                description="Adjust future rule after exclusion review.",
                affected_scope_summary="sender cluster narrowed by exclusion",
                source_refs=("proposal:teach-002",),
                created_at="2026-07-10T10:10:00Z",
                updated_at="2026-07-10T10:10:00Z",
            )
            store.save_candidate(candidate)

            updated = store.update_candidate(
                "candidate-amendment-001",
                status="evaluated",
                baseline_ref="evaluation:baseline-20260710",
                latest_evaluation_ref="evaluation:candidate-batch-20260710",
                latest_recommendation="Review",
                metadata={"recommendation": "Review"},
            )

            self.assertEqual(updated.status, "evaluated")
            self.assertEqual(updated.baseline_ref, "evaluation:baseline-20260710")
            self.assertEqual(updated.latest_evaluation_ref, "evaluation:candidate-batch-20260710")
            self.assertEqual(updated.latest_recommendation, "Review")
            self.assertEqual(updated.metadata["recommendation"], "Review")

    def test_per_candidate_decisions_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / "gmail_fetch"
            store = CandidateChangeStore(candidate_changes_path(storage_dir))
            candidate = CandidateChange(
                id="candidate-future-rule-003",
                kind="future-rule",
                source="sidebar-teach",
                title="Teach payroll notices as finance",
                description="Future rule from founder correction.",
                affected_scope_summary="payroll sender family",
                created_at="2026-07-10T10:20:00Z",
                updated_at="2026-07-10T10:20:00Z",
            )
            store.save_candidate(candidate)

            promoted = store.apply_decision(
                "candidate-future-rule-003",
                decision="promote",
                actor="founder",
                latest_recommendation="Promote",
            )

            self.assertEqual(promoted.status, "promoted")
            self.assertEqual(promoted.latest_recommendation, "Promote")
            self.assertEqual(promoted.decision_actor, "founder")
            self.assertEqual(promoted.metadata["last_decision"], "promote")

    def test_override_promote_requires_reason_and_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / "gmail_fetch"
            store = CandidateChangeStore(candidate_changes_path(storage_dir))
            candidate = CandidateChange(
                id="candidate-future-rule-004",
                kind="future-rule",
                source="sidebar-teach",
                title="Teach founder-specific promo exception",
                description="Risky but intentionally accepted founder rule.",
                affected_scope_summary="founder exception",
                created_at="2026-07-10T10:25:00Z",
                updated_at="2026-07-10T10:25:00Z",
            )
            store.save_candidate(candidate)

            with self.assertRaises(ValueError):
                store.apply_decision(
                    "candidate-future-rule-004",
                    decision="override-promote",
                    actor="founder",
                    latest_recommendation="Reject",
                )

            overridden = store.apply_decision(
                "candidate-future-rule-004",
                decision="override-promote",
                actor="founder",
                latest_recommendation="Reject",
                override_reason="Useful founder-specific workflow despite benchmark regression.",
            )

            self.assertEqual(overridden.status, "override-promoted")
            self.assertEqual(overridden.latest_recommendation, "Reject")
            self.assertIn("founder-specific workflow", overridden.override_reason)
            self.assertEqual(overridden.metadata["last_decision"], "override-promote")


if __name__ == "__main__":
    unittest.main()
