import json
import tempfile
import unittest
from pathlib import Path

from src.unresolved_gap_report import build_unresolved_gap_report


class UnresolvedGapReportTests(unittest.TestCase):
    def test_build_report_summarizes_gap_and_recommended_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            runtime_dir = output_dir / "runtime_cascades"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-cascade-1.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-29T00:00:00Z",
                        "summary": {
                            "message_count": 100,
                            "unresolved_count": 20,
                        },
                        "providers": {
                            "gmail": {
                                "unresolved_count": 12,
                                "outcomes": [
                                    {"stage": "unresolved", "sender_key": "vendor", "subject": "Deal"},
                                    {"stage": "unresolved", "sender_key": "vendor", "subject": "Deal"},
                                    {"stage": "resolved", "sender_key": "other", "subject": "Ignore"},
                                ],
                            }
                        },
                    },
                    indent=2,
                )
            )
            (output_dir / "latest_safety_triage_pass.json").write_text(
                json.dumps(
                    {
                        "founder_questions": [
                            {
                                "question_id": "question-1",
                                "title": "How should deals be handled?",
                                "providers": ["gmail"],
                                "estimated_unblocked_messages": 8,
                            }
                        ],
                        "top_review_targets": [
                            {
                                "provider": "gmail",
                                "sender_key": "vendor",
                                "subject_key": "deal",
                                "count": 2,
                            }
                        ],
                    },
                    indent=2,
                )
            )

            report = build_unresolved_gap_report(output_dir)

            self.assertEqual(report["summary"]["current_unresolved_count"], 20)
            self.assertEqual(report["summary"]["target_unresolved_count"], 10)
            self.assertEqual(report["summary"]["remaining_gap_count"], 10)
            self.assertEqual(report["recommended_actions"][0]["action_type"], "founder-question")
            self.assertEqual(report["provider_hotspots"][0]["provider"], "gmail")
            self.assertEqual(report["provider_hotspots"][0]["top_families"][0]["count"], 2)
            self.assertEqual(report["provider_hotspots"][0]["top_families"][0]["top_subject"], "Deal")


if __name__ == "__main__":
    unittest.main()
