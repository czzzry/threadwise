import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import latest_safety_triage_manifest_path, safety_backlog_reports_dir
from src.safety_triage_status import build_safety_triage_status


class SafetyTriageStatusTests(unittest.TestCase):
    def test_build_status_reports_missing_when_manifest_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            status = build_safety_triage_status(Path(temp_dir))
            self.assertEqual(status["status"], "missing")

    def test_build_status_reads_latest_manifest_and_backlog_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-28T10:00:00Z",
                        "summary": {
                            "backlog_pressure": "elevated",
                            "pending_disposition_count": 3,
                            "approved_disposition_count": 2,
                            "rejected_disposition_count": 1,
                            "top_target_count": 4,
                        },
                        "top_target": {
                            "provider": "outlookmail",
                            "sender_key": "alerts@pestsolutions.test",
                            "subject_key": "service report ######",
                        },
                        "provider_drivers": [{"provider": "outlookmail", "driver_score": 8}],
                        "top_review_targets": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "alerts@pestsolutions.test",
                                "subject_key": "service report ######",
                                "review_priority": {"score": 9, "bucket": "urgent"},
                            }
                        ],
                        "memory_impact_summary": {
                            "accepted_rule_count": 3,
                            "impacted_rule_count": 1,
                            "unresolved_before": 9,
                            "unresolved_after": 7,
                            "unresolved_delta": -2,
                        },
                        "top_memory_impacts": [{"rule_id": "shadow-outlookmail-001"}],
                        "next_review_payoffs": [{"provider": "outlookmail", "sender_key": "mystery@example.com"}],
                        "founder_question_summary": {
                            "question_count": 2,
                            "estimated_unblocked_messages": 31,
                        },
                        "founder_questions": [{"theme": "marketing-preference", "providers": ["outlookmail"]}],
                        "founder_answer_summary": {
                            "actionable_answer_count": 3,
                            "answer_option_count": 6,
                        },
                        "founder_answer_previews": [{"theme": "marketing-preference", "answer_key": "low_value_default"}],
                        "latest_founder_answer_application": {
                            "theme": "marketing-preference",
                            "matched_answer_key": "low_value_default",
                            "approved_proposal_count": 2,
                            "resolved_gain": 6,
                        },
                        "artifacts": {"backlog_report_path": "/tmp/backlog.json"},
                    },
                    indent=2,
                )
            )
            reports_dir = safety_backlog_reports_dir(output_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            self._write_backlog_report(reports_dir / "safety-backlog-report-1.json", "2026-06-28T09:00:00Z", 5, 6, "high")
            self._write_backlog_report(reports_dir / "safety-backlog-report-2.json", "2026-06-28T10:00:00Z", 3, 4, "elevated")

            status = build_safety_triage_status(output_dir)

            self.assertEqual(status["status"], "ready")
            self.assertEqual(status["latest"]["backlog_pressure"], "elevated")
            self.assertEqual(status["latest"]["top_target"]["provider"], "outlookmail")
            self.assertEqual(status["latest"]["provider_drivers"][0]["provider"], "outlookmail")
            self.assertEqual(status["latest"]["top_review_targets"][0]["review_priority"]["bucket"], "urgent")
            self.assertEqual(status["latest"]["memory_impact_summary"]["accepted_rule_count"], 3)
            self.assertEqual(status["latest"]["top_memory_impacts"][0]["rule_id"], "shadow-outlookmail-001")
            self.assertEqual(status["latest"]["next_review_payoffs"][0]["provider"], "outlookmail")
            self.assertEqual(status["latest"]["founder_question_summary"]["question_count"], 2)
            self.assertEqual(status["latest"]["founder_questions"][0]["theme"], "marketing-preference")
            self.assertEqual(status["latest"]["founder_answer_summary"]["actionable_answer_count"], 3)
            self.assertEqual(status["latest"]["founder_answer_previews"][0]["theme"], "marketing-preference")
            self.assertEqual(status["latest"]["latest_founder_answer_application"]["resolved_gain"], 6)
            self.assertEqual(status["trend"]["direction"], "improving")
            self.assertEqual(status["trend"]["pending_delta"], -2)
            self.assertEqual(len(status["history"]), 2)

    def _write_backlog_report(
        self,
        path: Path,
        generated_at: str,
        pending_disposition_count: int,
        top_target_count: int,
        backlog_pressure: str,
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "generated_at": generated_at,
                    "summary": {
                        "pending_disposition_count": pending_disposition_count,
                        "approved_disposition_count": 0,
                        "rejected_disposition_count": 0,
                        "top_target_count": top_target_count,
                        "backlog_pressure": backlog_pressure,
                    },
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
