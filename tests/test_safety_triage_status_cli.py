import io
import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import latest_safety_triage_manifest_path, safety_backlog_reports_dir
from src.safety_triage_status_cli import main


class SafetyTriageStatusCliTests(unittest.TestCase):
    def test_main_reports_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            exit_code = main(["--output-storage-dir", temp_dir], stdout=stdout)
            self.assertEqual(exit_code, 1)
            self.assertIn("No safety triage manifest found.", stdout.getvalue())

    def test_main_prints_latest_status_and_trend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-28T10:00:00Z",
                        "summary": {
                            "backlog_pressure": "manageable",
                            "pending_disposition_count": 1,
                            "approved_disposition_count": 4,
                            "rejected_disposition_count": 0,
                            "top_target_count": 2,
                        },
                        "top_target": {
                            "provider": "gmail",
                            "sender_key": "alerts@pestsolutions.test",
                            "subject_key": "service report ######",
                        },
                        "provider_drivers": [
                            {
                                "provider": "gmail",
                                "driver_score": 7,
                                "top_target_count": 2,
                                "eval_false_hide_risk_count": 1,
                            }
                        ],
                        "top_review_targets": [
                            {
                                "provider": "gmail",
                                "sender_key": "alerts@pestsolutions.test",
                                "subject_key": "service report ######",
                                "review_priority": {"score": 9, "bucket": "urgent"},
                            }
                        ],
                        "memory_impact_summary": {
                            "accepted_rule_count": 4,
                            "impacted_rule_count": 2,
                            "unresolved_before": 12,
                            "unresolved_after": 8,
                            "unresolved_delta": -4,
                        },
                        "top_memory_impacts": [
                            {
                                "rule_id": "shadow-gmail-001",
                                "label": "promotions",
                                "resolved_message_count": 3,
                                "matched_message_count": 5,
                                "top_resolved_families": [{"provider": "gmail", "sender_key": "deals@example.com"}],
                            }
                        ],
                        "next_review_payoffs": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "mystery@example.com",
                                "expected_resolved_messages": 4,
                                "expected_gain_band": "medium-high",
                            }
                        ],
                        "founder_question_summary": {
                            "question_count": 3,
                            "estimated_unblocked_messages": 42,
                        },
                        "founder_questions": [
                            {
                                "theme": "marketing-preference",
                                "providers": ["outlookmail", "gmail"],
                                "family_count": 4,
                                "estimated_unblocked_messages": 25,
                            }
                        ],
                        "founder_answer_summary": {
                            "actionable_answer_count": 4,
                            "answer_option_count": 9,
                        },
                        "founder_answer_previews": [
                            {
                                "theme": "marketing-preference",
                                "answer_key": "low_value_default",
                                "estimated_resolved_messages": 25,
                                "proposal_count": 4,
                            }
                        ],
                        "latest_founder_answer_application": {
                            "theme": "marketing-preference",
                            "matched_answer_key": "low_value_default",
                            "approved_proposal_count": 2,
                            "resolved_gain": 6,
                        },
                        "artifacts": {},
                    },
                    indent=2,
                )
            )
            reports_dir = safety_backlog_reports_dir(output_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "report-1.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-28T09:00:00Z",
                        "summary": {
                            "pending_disposition_count": 2,
                            "approved_disposition_count": 3,
                            "rejected_disposition_count": 0,
                            "top_target_count": 3,
                            "backlog_pressure": "elevated",
                        },
                    },
                    indent=2,
                )
            )
            (reports_dir / "report-2.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-28T10:00:00Z",
                        "summary": {
                            "pending_disposition_count": 1,
                            "approved_disposition_count": 4,
                            "rejected_disposition_count": 0,
                            "top_target_count": 2,
                            "backlog_pressure": "manageable",
                        },
                    },
                    indent=2,
                )
            )

            stdout = io.StringIO()
            exit_code = main(["--output-storage-dir", temp_dir], stdout=stdout)
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Latest safety triage: 2026-06-28T10:00:00Z", rendered)
            self.assertIn("Backlog pressure: manageable", rendered)
            self.assertIn("Pending dispositions: 1", rendered)
            self.assertIn("Top targets: 2", rendered)
            self.assertIn("Trend: improving: pending delta=-1, top-target delta=-1", rendered)
            self.assertIn("Top target: gmail | alerts@pestsolutions.test | service report ######", rendered)
            self.assertIn("Provider driver: gmail | score=7 | targets=2 | false-hide=1", rendered)
            self.assertIn(
                "Review target: gmail | alerts@pestsolutions.test | service report ###### | priority=9 | bucket=urgent",
                rendered,
            )
            self.assertIn("Memory impact: rules=4 | impacted=2 | unresolved before=12 | after=8", rendered)
            self.assertIn("Memory winner: gmail | deals@example.com | promotions | resolved=3 | matched=5", rendered)
            self.assertIn("Next payoff: outlookmail | mystery@example.com | expected gain=4 | bucket=medium-high", rendered)
            self.assertIn("Founder questions: count=3 | estimated unlocked=42", rendered)
            self.assertIn("Founder question: marketing-preference | providers=outlookmail,gmail | families=4 | unlocked=25", rendered)
            self.assertIn("Founder answers: options=9 | actionable=4", rendered)
            self.assertIn("Founder answer preview: marketing-preference | low_value_default | resolved=25 | proposals=4", rendered)
            self.assertIn("Latest founder application: marketing-preference | low_value_default | approved=2 | resolved gain=6", rendered)


if __name__ == "__main__":
    unittest.main()
