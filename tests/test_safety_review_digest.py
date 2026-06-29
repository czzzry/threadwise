import io
import json
import tempfile
import unittest
from pathlib import Path

from src.safety_review_digest import build_safety_review_digest
from src.safety_review_digest_cli import main


class SafetyReviewDigestTests(unittest.TestCase):
    def test_build_digest_combines_top_targets_from_multiple_artifacts(self) -> None:
        digest = build_safety_review_digest(
            report={
                "providers": {
                    "gmail": {
                        "safety_memory_projection": {
                            "approved_disposition_count": 1,
                            "projected": {
                                "safety_memory_hit_count": 2,
                                "heuristic_false_hide_risk_count": 1,
                            },
                            "top_projected_false_hide_risk_families": [
                                {
                                    "sender_key": "alerts@pestsolutions.test",
                                    "subject_key": "service report ######",
                                    "count": 2,
                                }
                            ],
                        }
                    }
                }
            },
            frontier_plan={
                "summary": {"safety_priority_clusters": 1},
                "top_safety_priority_clusters": [
                    {
                        "provider": "gmail",
                        "sender_key": "alerts@pestsolutions.test",
                        "message_count": 2,
                        "family_count": 1,
                        "examples": [{"subject_key": "service report ######"}],
                        "safety_priority": {"priority_score": 10},
                    }
                ],
            },
        )

        self.assertEqual(digest["summary"]["provider_count"], 1)
        self.assertGreaterEqual(digest["summary"]["top_target_count"], 1)
        self.assertEqual(digest["top_targets"][0]["sender_key"], "alerts@pestsolutions.test")

    def test_cli_writes_digest_and_prints_top_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            report_path = root / "report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "gmail": {
                                "safety_memory_projection": {
                                    "approved_disposition_count": 1,
                                    "projected": {
                                        "safety_memory_hit_count": 1,
                                        "heuristic_false_hide_risk_count": 1,
                                    },
                                    "top_projected_false_hide_risk_families": [
                                        {
                                            "sender_key": "alerts@pestsolutions.test",
                                            "subject_key": "service report ######",
                                            "count": 1,
                                        }
                                    ],
                                }
                            }
                        }
                    },
                    indent=2,
                )
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--output-storage-dir",
                    str(output_dir),
                    "--report-path",
                    str(report_path),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Built safety digest:", rendered)
            self.assertIn("Top target: gmail | alerts@pestsolutions.test", rendered)
            self.assertIn("Saved digest:", rendered)


if __name__ == "__main__":
    unittest.main()
