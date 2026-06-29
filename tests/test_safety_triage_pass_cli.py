import io
import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import latest_safety_triage_manifest_path
from src.safety_triage_pass_cli import main


class SafetyTriagePassCliTests(unittest.TestCase):
    def test_main_runs_unattended_safety_triage_pass_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            output_dir = root / "classifier_eval"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                sender='"Pest Solutions" <alerts@pestsolutions.test>',
                subject="Service report 123456",
            )
            (gmail_dir / "safety_dispositions.json").write_text(
                json.dumps(
                    {
                        "status": "PROTOTYPE - local safety review dispositions",
                        "generated_at": "2026-06-28T00:00:00Z",
                        "disposition_count": 1,
                        "dispositions": [
                            {
                                "id": "safety-gmail-sender-phishing-alerts-pestsolutions-test",
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "source_batch_id": "seed-batch",
                                "source_message_ids": ["seed-1"],
                                "scope": "sender",
                                "disposition": "phishing",
                                "source_examples": [
                                    {
                                        "provider": "gmail",
                                        "message_id": "seed-1",
                                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                                        "subject": "Service report 555555",
                                        "date": "2026-06-27T00:00:00Z",
                                        "final_labels": [],
                                    }
                                ],
                                "explanation": "Known phishing family.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-28T00:00:00Z",
                                "updated_at": "2026-06-28T00:00:00Z",
                                "review_notes": "Approved by founder.",
                            }
                        ],
                    },
                    indent=2,
                )
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "shadow_suggestion_memory.json").write_text(json.dumps({"candidates": []}, indent=2))
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(gmail_dir),
                    "--protonmail-storage-dir",
                    str(root / "empty-proton"),
                    "--outlookmail-storage-dir",
                    str(root / "empty-outlook"),
                    "--output-storage-dir",
                    str(output_dir),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Safety triage pass:", rendered)
            self.assertIn("Top target:", rendered)
            self.assertIn("Eval report:", rendered)
            self.assertIn("Frontier plan:", rendered)
            self.assertIn("Cluster pack:", rendered)
            self.assertIn("Review pack:", rendered)
            self.assertIn("Safety digest:", rendered)
            self.assertIn("Backlog report:", rendered)
            self.assertIn("Memory impact:", rendered)
            self.assertIn("Founder questions:", rendered)
            self.assertIn("Founder answers:", rendered)
            self.assertIn("Latest manifest:", rendered)

            manifest = json.loads(latest_safety_triage_manifest_path(output_dir).read_text())
            self.assertEqual(manifest["artifact_type"], "latest-safety-triage-pass")
            self.assertIn("backlog_report_path", manifest["artifacts"])
            self.assertIn("memory_impact_report_path", manifest["artifacts"])
            self.assertIn("founder_question_pack_path", manifest["artifacts"])
            self.assertIn("founder_answer_pack_path", manifest["artifacts"])
            self.assertEqual(manifest["summary"]["approved_disposition_count"], 1)

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        sender: str,
        subject: str,
    ) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "items": [
                        {
                            "message_id": "m1",
                            "sender": sender,
                            "subject": subject,
                            "snippet": "Open attached report.",
                            "body": "Open attached report.",
                        }
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
