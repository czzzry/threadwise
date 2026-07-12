import io
import json
import tempfile
import unittest
from pathlib import Path

from src.founder_policy_batch_application_cli import main
from src.local_artifacts import latest_safety_triage_manifest_path


class FounderPolicyBatchApplicationCliTests(unittest.TestCase):
    def test_main_applies_policy_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            outlook_dir = root / "outlookmail"
            batches_dir = outlook_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            (batches_dir / "founder-hotmail-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-hotmail-batch-1",
                        "account_id": "founder-hotmail",
                        "provider": "outlookmail",
                        "items": [{"message_id": "o1", "sender": "Utopia", "subject": "Utopia Age 113", "snippet": "News", "body": "News"}],
                    },
                    indent=2,
                )
            )
            review_pack_path = output_dir / "review-pack.json"
            review_pack_path.parent.mkdir(parents=True, exist_ok=True)
            review_pack_path.write_text(json.dumps({"top_review_targets": []}, indent=2))
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps({"artifacts": {"review_pack_path": str(review_pack_path)}}, indent=2)
            )
            batch_pack_path = output_dir / "batch-pack.json"
            batch_pack_path.write_text(
                json.dumps(
                    {
                        "batches": [
                            {
                                "batch_id": "policy-batch-low-value-opt-in",
                                "policy_key": "low-value-opt-in",
                                "title": "Legitimate but unwanted opt-in mail",
                                "cluster_count": 1,
                                "message_coverage": 28,
                                "family_coverage": 23,
                                "proposal_drafts": [
                                    {
                                        "id": "proposal-outlookmail-sender-cluster-spam-low-value-utopia-utopia-age-113",
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "source_batch_id": "founder-hotmail-batch-1",
                                        "source_message_ids": ["o1"],
                                        "scope": "sender-cluster",
                                        "label": "spam-low-value",
                                        "instruction": "Anything from Utopia with subjects like 'Utopia Age 113' should be spam-low-value.",
                                        "terms": ["utopia", "utopia age 113"],
                                        "source_examples": [{"message_id": "o1", "sender": "Utopia", "subject": "Utopia Age 113"}],
                                        "explanation": "Batch draft.",
                                        "preview": {"match_count": 1, "matches": []},
                                        "status": "pending",
                                        "created_at": "2026-06-28T00:00:00Z",
                                        "updated_at": "2026-06-28T00:00:00Z",
                                    }
                                ],
                            }
                        ]
                    },
                    indent=2,
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "--output-storage-dir",
                    str(output_dir),
                    "--outlookmail-storage-dir",
                    str(outlook_dir),
                    "--gmail-storage-dir",
                    str(root / "gmail"),
                    "--protonmail-storage-dir",
                    str(root / "protonmail"),
                    "--policy-batch-pack-path",
                    str(batch_pack_path),
                    "--batch-id",
                    "policy-batch-low-value-opt-in",
                    "--review-notes",
                    "Batch approved.",
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Applied founder policy batch: low-value-opt-in | approved-proposals=1 | approved-rules=1 | messages=28", rendered)
            self.assertIn("Saved application:", rendered)
            self.assertIn("Saved report:", rendered)


if __name__ == "__main__":
    unittest.main()
