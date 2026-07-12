import json
import tempfile
import unittest
from pathlib import Path

from src.founder_policy_batch_application import apply_founder_policy_batch
from src.local_artifacts import accepted_shadow_rules_path, latest_safety_triage_manifest_path


class FounderPolicyBatchApplicationTests(unittest.TestCase):
    def test_apply_batch_approves_all_proposals_and_refreshes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [{"message_id": "o1", "sender": "Utopia", "subject": "Utopia Age 113", "snippet": "News", "body": "News"}],
            )
            review_pack_path = output_dir / "review-pack.json"
            review_pack_path.parent.mkdir(parents=True, exist_ok=True)
            review_pack_path.write_text(json.dumps({"top_review_targets": []}, indent=2))
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps({"artifacts": {"review_pack_path": str(review_pack_path)}}, indent=2)
            )

            policy_batch_pack = {
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
            }

            application = apply_founder_policy_batch(
                output_dir,
                policy_batch_pack=policy_batch_pack,
                batch_id="policy-batch-low-value-opt-in",
                provider_storage_dirs=[("outlookmail", outlook_dir)],
                review_notes="Batch approved.",
                review_pack={},
            )

            rules_payload = json.loads(accepted_shadow_rules_path(output_dir).read_text())
            self.assertEqual(len(rules_payload["rules"]), 1)
            self.assertEqual(application["approved_proposal_count"], 1)
            self.assertEqual(application["impact_after"]["accepted_rule_count"], 1)

            manifest = json.loads(latest_safety_triage_manifest_path(output_dir).read_text())
            self.assertEqual(manifest["latest_founder_policy_batch_application"]["policy_key"], "low-value-opt-in")
            self.assertEqual(manifest["latest_founder_policy_batch_application"]["message_coverage"], 28)

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        items: list[dict],
    ) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "items": items,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
