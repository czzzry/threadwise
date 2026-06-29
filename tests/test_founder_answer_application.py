import json
import tempfile
import unittest
from pathlib import Path

from src.founder_answer_application import apply_founder_answer_decision
from src.local_artifacts import accepted_shadow_rules_path, latest_safety_triage_manifest_path


class FounderAnswerApplicationTests(unittest.TestCase):
    def test_apply_decision_approves_rules_and_refreshes_manifest_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Lieferando <deals@lieferando.de>",
                        "subject": "30 % Rabatt",
                        "snippet": "Deal.",
                        "body": "Deal.",
                    }
                ],
            )
            review_pack_path = output_dir / "review-pack.json"
            review_pack_path.parent.mkdir(parents=True, exist_ok=True)
            review_pack_path.write_text(
                json.dumps(
                    {
                        "top_review_targets": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "lieferando",
                                "subject_key": "30 % rabatt",
                                "count": 1,
                                "question_lane": "preference-question",
                                "suggested_labels": ["promotions"],
                                "review_priority": {"score": 1, "estimated_message_gain": 1},
                                "examples": [
                                    {
                                        "account_id": "founder-hotmail",
                                        "batch_id": "founder-hotmail-batch-1",
                                        "message_id": "o1",
                                        "sender": "Lieferando <deals@lieferando.de>",
                                        "subject": "30 % Rabatt",
                                    }
                                ],
                            }
                        ]
                    },
                    indent=2,
                )
            )
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps(
                    {
                        "provider_drivers": [{"provider": "outlookmail", "driver_score": 3}],
                        "artifacts": {"review_pack_path": str(review_pack_path)},
                    },
                    indent=2,
                )
            )

            decision = {
                "decision_id": "decision-1",
                "question_id": "question-marketing-preference",
                "theme": "marketing-preference",
                "matched_answer_key": "low_value_default",
                "proposal_drafts": [
                    {
                        "id": "proposal-outlookmail-sender-cluster-promotions-lieferando-30-rabatt",
                        "provider": "outlookmail",
                        "account_id": "founder-hotmail",
                        "source_batch_id": "founder-hotmail-batch-1",
                        "source_message_ids": ["o1"],
                        "scope": "sender-cluster",
                        "label": "promotions",
                        "instruction": "Anything from lieferando with this subject family should be promotions.",
                        "terms": ["lieferando", "30 rabatt"],
                        "source_examples": [{"message_id": "o1", "sender": "Lieferando <deals@lieferando.de>", "subject": "30 % Rabatt"}],
                        "explanation": "Drafted from founder answer.",
                        "preview": {"match_count": 1, "matches": []},
                        "status": "pending",
                        "created_at": "2026-06-28T00:00:00Z",
                        "updated_at": "2026-06-28T00:00:00Z",
                    }
                ],
            }

            application = apply_founder_answer_decision(
                output_dir,
                decision=decision,
                provider_storage_dirs=[("outlookmail", outlook_dir)],
                review_notes="Approved by founder.",
                review_pack={},
            )

            rules_payload = json.loads(accepted_shadow_rules_path(output_dir).read_text())
            self.assertEqual(len(rules_payload["rules"]), 1)
            self.assertEqual(application["approved_proposal_count"], 1)
            self.assertEqual(application["impact_after"]["accepted_rule_count"], 1)
            self.assertEqual(application["impact_delta"]["resolved_gain"], 1)

            manifest = json.loads(latest_safety_triage_manifest_path(output_dir).read_text())
            self.assertEqual(manifest["memory_impact_summary"]["accepted_rule_count"], 1)
            self.assertEqual(manifest["latest_founder_answer_application"]["resolved_gain"], 1)
            self.assertEqual(manifest["founder_question_summary"]["question_count"], 0)
            self.assertEqual(manifest["founder_answer_summary"]["answer_option_count"], 0)

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
