import io
import json
import tempfile
import unittest
from pathlib import Path

from src.founder_policy_batch_cli import main


class FounderPolicyBatchCliTests(unittest.TestCase):
    def test_main_builds_policy_batch_pack(self) -> None:
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
                        "items": [
                            {
                                "message_id": "o1",
                                "sender": "Utopia",
                                "subject": "Utopia Age 113",
                                "snippet": "News",
                                "body": "News",
                            }
                        ],
                    },
                    indent=2,
                )
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "accepted_shadow_teachable_rules.json").write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "id": "teach-001",
                                "instruction": "Anything from lieferando should be spam-low-value.",
                                "label": "spam-low-value",
                                "terms": ["lieferando"],
                                "keep_visible": False,
                                "created_at": "2026-06-28T00:00:00Z",
                                "providers": ["outlookmail"],
                                "enabled": True,
                                "source_examples": [],
                                "scope": "sender-cluster",
                                "match_mode": "sender-cluster",
                                "provenance": {},
                                "updated_at": "2026-06-28T00:00:00Z",
                            }
                        ]
                    },
                    indent=2,
                )
            )
            cluster_pack_path = output_dir / "cluster-pack.json"
            cluster_pack_path.write_text(
                json.dumps(
                    {
                        "auto_low_value_policies": [
                            {
                                "decision_id": "cluster-outlookmail-utopia",
                                "provider": "outlookmail",
                                "sender_key": "utopia",
                                "message_count": 28,
                                "family_count": 23,
                                "review_type": "policy-review",
                                "review_mode": "auto-low-value",
                                "suggested_labels": ["spam-low-value"],
                                "confidence": "high",
                                "examples": [
                                    {
                                        "account_id": "founder-hotmail",
                                        "batch_id": "founder-hotmail-batch-1",
                                        "message_id": "o1",
                                        "sender": "Utopia",
                                        "subject": "Utopia Age 113",
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
                    "--cluster-decision-pack-path",
                    str(cluster_pack_path),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Founder policy batches: batches=1 | proposals=1 | messages=28 | families=23", rendered)
            self.assertIn("Batch: low-value-opt-in | labels=promotions,spam-low-value | clusters=1 | messages=28", rendered)
            self.assertIn("Saved pack:", rendered)


if __name__ == "__main__":
    unittest.main()
