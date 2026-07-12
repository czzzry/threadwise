import io
import json
import tempfile
import unittest
from pathlib import Path

from src.unified_review_queue_cli import main


class UnifiedReviewQueueCliTests(unittest.TestCase):
    def test_build_and_list_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            runtime_dir = output_dir / "runtime_cascades"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (root / "gmail_fetch" / "batches").mkdir(parents=True, exist_ok=True)
            (root / "protonmail_fetch" / "batches").mkdir(parents=True, exist_ok=True)
            (root / "outlookmail_fetch" / "batches").mkdir(parents=True, exist_ok=True)
            report_path = runtime_dir / "runtime-cascade-1.json"
            report_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-29T00:00:00Z",
                        "providers": {
                            "outlookmail": {
                                "outcomes": [
                                    {
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "batch_id": "batch-1",
                                        "message_id": "m-1",
                                        "sender": "Vendor <vendor@example.com>",
                                        "subject": "30 % Rabatt",
                                        "sender_key": "vendor@example.com",
                                        "subject_key": "30 % rabatt",
                                        "stage": "llm-escalation",
                                        "labels": ["promotions"],
                                        "llm_rationale": "Promo family.",
                                        "llm_confidence": "high",
                                        "decision_provenance": {"llm_model": "gpt-test"},
                                        "decision": {"confidence": "high", "safety_lane": "ordinary"},
                                    }
                                ]
                            }
                        },
                    },
                    indent=2,
                )
            )
            stdout = io.StringIO()

            build_exit = main(
                [
                    "build",
                    "--output-storage-dir",
                    str(output_dir),
                    "--runtime-report-path",
                    str(report_path),
                    "--gmail-storage-dir",
                    str(root / "gmail_fetch"),
                    "--protonmail-storage-dir",
                    str(root / "protonmail_fetch"),
                    "--outlookmail-storage-dir",
                    str(root / "outlookmail_fetch"),
                ],
                stdout=stdout,
                cwd=root,
            )
            list_exit = main(
                [
                    "list",
                    "--output-storage-dir",
                    str(output_dir),
                    "--gmail-storage-dir",
                    str(root / "gmail_fetch"),
                    "--protonmail-storage-dir",
                    str(root / "protonmail_fetch"),
                    "--outlookmail-storage-dir",
                    str(root / "outlookmail_fetch"),
                ],
                stdout=stdout,
                cwd=root,
            )

            rendered = stdout.getvalue()
            self.assertEqual(build_exit, 0)
            self.assertEqual(list_exit, 0)
            self.assertIn("Unified review queue: items=1 | pending=1", rendered)
            self.assertIn("runtime-llm-candidate", rendered)


if __name__ == "__main__":
    unittest.main()
