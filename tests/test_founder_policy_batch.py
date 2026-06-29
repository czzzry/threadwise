import json
import tempfile
import unittest
from pathlib import Path

from src.founder_policy_batch import build_founder_policy_batch_pack
from src.memory_proposal_store import rule_from_memory_proposal, build_memory_proposal
from src.teachable_rule_memory import TeachableRuleMemory


class FounderPolicyBatchPackTests(unittest.TestCase):
    def test_build_pack_groups_clusters_by_accepted_policy_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outlook_dir = root / "outlookmail"
            gmail_dir = root / "gmail"
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {"message_id": "o1", "sender": "Utopia", "subject": "Utopia Age 113", "snippet": "News", "body": "News"},
                    {"message_id": "o2", "sender": "Scott Hennessy", "subject": "Scott Hennessy sent you a message.", "snippet": "Msg", "body": "Msg"},
                ],
            )
            self._write_batch(
                gmail_dir,
                "founder-gmail-batch-1",
                "founder-test",
                "gmail",
                [
                    {"message_id": "g1", "sender": "\"Yoga Barn\" <no-reply@eversports.com>", "subject": "Dein Kauf bei Yoga Barn Berlin", "snippet": "Receipt", "body": "Receipt"},
                ],
            )

            rules_memory = TeachableRuleMemory(root / "accepted.json")
            low_value = build_memory_proposal(
                provider="outlookmail",
                account_id="founder-hotmail",
                source_batch_id="founder-hotmail-batch-1",
                selected_items=[{"message_id": "seed1", "sender": "Lieferando", "subject": "30 % Rabatt"}],
                scope="sender-cluster",
                label="spam-low-value",
                explanation="Founder does not want this opt-in mail.",
                storage_items=[],
            )
            personal = build_memory_proposal(
                provider="outlookmail",
                account_id="founder-hotmail",
                source_batch_id="founder-hotmail-batch-1",
                selected_items=[{"message_id": "seed2", "sender": "Friend", "subject": "Friend sent you a message."}],
                scope="sender-cluster",
                label="personal",
                explanation="Known person keep visible.",
                storage_items=[],
            )
            receipt = build_memory_proposal(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-gmail-batch-1",
                selected_items=[{"message_id": "seed3", "sender": "Shop", "subject": "Your receipt"}],
                scope="sender-cluster",
                label="receipt-billing",
                explanation="Receipt.",
                storage_items=[],
            )
            for idx, proposal in enumerate((low_value, personal, receipt), start=1):
                rules_memory.save_rule(rule_from_memory_proposal(proposal, existing_count=idx))

            cluster_pack = {
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
                ],
                "personal_policies": [
                    {
                        "decision_id": "cluster-outlookmail-scott",
                        "provider": "outlookmail",
                        "sender_key": "scott hennessy",
                        "message_count": 6,
                        "family_count": 1,
                        "review_type": "policy-review",
                        "review_mode": "personal-review",
                        "suggested_labels": ["personal", "reply-needed"],
                        "confidence": "medium",
                        "examples": [
                            {
                                "account_id": "founder-hotmail",
                                "batch_id": "founder-hotmail-batch-1",
                                "message_id": "o2",
                                "sender": "Scott Hennessy",
                                "subject": "Scott Hennessy sent you a message.",
                            }
                        ],
                    }
                ],
                "preference_reviews": [
                    {
                        "decision_id": "cluster-gmail-yoga-kauf",
                        "provider": "gmail",
                        "sender_key": "namaste@yoga-barn-berlin.de",
                        "message_count": 1,
                        "family_count": 1,
                        "review_type": "preference-review",
                        "review_mode": "preference-review",
                        "suggested_labels": ["receipt-billing"],
                        "confidence": "medium",
                        "examples": [
                            {
                                "account_id": "founder-test",
                                "batch_id": "founder-gmail-batch-1",
                                "message_id": "g1",
                                "sender": "\"Yoga Barn\" <no-reply@eversports.com>",
                                "subject": "Dein Kauf bei Yoga Barn Berlin",
                            }
                        ],
                    }
                ],
                "safety_reviews": [],
            }

            pack = build_founder_policy_batch_pack(
                cluster_decision_pack=cluster_pack,
                accepted_rules=rules_memory.list_rules(),
                provider_storage_dirs=[("outlookmail", outlook_dir), ("gmail", gmail_dir)],
            )

            self.assertEqual(pack["summary"]["batch_count"], 3)
            self.assertEqual(pack["summary"]["proposal_count"], 3)
            keys = [batch["policy_key"] for batch in pack["batches"]]
            self.assertIn("low-value-opt-in", keys)
            self.assertIn("personal-keep-visible", keys)
            self.assertIn("receipt-billing", keys)
            low_value_batch = next(batch for batch in pack["batches"] if batch["policy_key"] == "low-value-opt-in")
            self.assertEqual(low_value_batch["message_coverage"], 28)
            self.assertEqual(low_value_batch["proposal_drafts"][0]["label"], "spam-low-value")
            self.assertEqual(low_value_batch["proposal_drafts"][0]["scope"], "sender")

    def test_low_value_batch_falls_back_to_sender_cluster_for_mixed_sender(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outlook_dir = root / "outlookmail"
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Instagram",
                        "subject": "New reel for you",
                        "snippet": "Promo",
                        "body": "Promo",
                        "applied_labels": [],
                    },
                    {
                        "message_id": "o2",
                        "sender": "Instagram",
                        "subject": "Verify your login",
                        "snippet": "Security",
                        "body": "Security",
                        "applied_labels": ["account-security"],
                    },
                ],
            )

            rules_memory = TeachableRuleMemory(root / "accepted.json")
            low_value = build_memory_proposal(
                provider="outlookmail",
                account_id="founder-hotmail",
                source_batch_id="founder-hotmail-batch-1",
                selected_items=[{"message_id": "seed1", "sender": "Lieferando", "subject": "30 % Rabatt"}],
                scope="sender-cluster",
                label="spam-low-value",
                explanation="Founder does not want this opt-in mail.",
                storage_items=[],
            )
            rules_memory.save_rule(rule_from_memory_proposal(low_value, existing_count=1))

            cluster_pack = {
                "auto_low_value_policies": [
                    {
                        "decision_id": "cluster-outlookmail-instagram",
                        "provider": "outlookmail",
                        "sender_key": "instagram",
                        "message_count": 2,
                        "family_count": 2,
                        "review_type": "policy-review",
                        "review_mode": "auto-low-value",
                        "suggested_labels": ["spam-low-value"],
                        "confidence": "high",
                        "examples": [
                            {
                                "account_id": "founder-hotmail",
                                "batch_id": "founder-hotmail-batch-1",
                                "message_id": "o1",
                                "sender": "Instagram",
                                "subject": "New reel for you",
                            }
                        ],
                    }
                ],
                "personal_policies": [],
                "preference_reviews": [],
                "safety_reviews": [],
            }

            pack = build_founder_policy_batch_pack(
                cluster_decision_pack=cluster_pack,
                accepted_rules=rules_memory.list_rules(),
                provider_storage_dirs=[("outlookmail", outlook_dir)],
            )

            low_value_batch = next(batch for batch in pack["batches"] if batch["policy_key"] == "low-value-opt-in")
            self.assertEqual(low_value_batch["proposal_drafts"][0]["scope"], "sender-cluster")

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
