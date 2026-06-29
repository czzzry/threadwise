import io
import json
import tempfile
import unittest
from pathlib import Path

from src.cluster_decision_pack_cli import main


class ClusterDecisionPackCliTests(unittest.TestCase):
    def test_cli_builds_pack_and_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan_path = root / "frontier.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "total_unresolved_sender_clusters": 2,
                            "total_unresolved_messages": 15,
                            "total_unresolved_families": 7,
                        },
                        "auto_low_value_clusters": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "lieferando",
                                "message_count": 9,
                                "family_count": 4,
                                "review_mode": "auto-low-value",
                                "suggested_labels": ["promotions", "spam-low-value"],
                                "examples": [],
                            }
                        ],
                        "safety_review_clusters": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "google",
                                "message_count": 6,
                                "family_count": 3,
                                "review_mode": "safety-review",
                                "suggested_labels": ["account-security"],
                                "safety_priority": {
                                    "priority_score": 7,
                                    "reasons": ["approved-safety-memory", "safety-review-lane"],
                                    "approved_disposition_ids": ["safety-001"],
                                    "approved_dispositions": ["legitimate-security"],
                                },
                                "examples": [],
                            }
                        ],
                        "personal_review_clusters": [],
                        "preference_review_clusters": [],
                        "unclear_clusters": [],
                    },
                    indent=2,
                )
            )
            stdout = io.StringIO()

            exit_code = main(
                ["--plan-path", str(plan_path), "--output-storage-dir", str(root)],
                stdout=stdout,
                cwd=root,
            )

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("Built cluster decision pack: units=2 | messages=15 | families=7", output)
            self.assertIn("Safety-priority=1", output)
            self.assertIn("Top safety review: outlookmail | google | score=7", output)
            self.assertIn("Saved pack:", output)
            saved_files = list((root / "cluster_decision_packs").glob("*.json"))
            self.assertEqual(len(saved_files), 1)


if __name__ == "__main__":
    unittest.main()
