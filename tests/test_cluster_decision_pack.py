import json
import tempfile
import unittest
from pathlib import Path

from src.cluster_decision_pack import build_cluster_decision_pack, load_frontier_plan


class ClusterDecisionPackTests(unittest.TestCase):
    def test_build_cluster_decision_pack_creates_memory_ready_review_units(self) -> None:
        plan = {
            "plan_path": "/tmp/frontier.json",
            "summary": {
                "total_unresolved_sender_clusters": 4,
                "total_unresolved_messages": 52,
                "total_unresolved_families": 16,
            },
            "auto_low_value_clusters": [
                {
                    "provider": "outlookmail",
                    "sender_key": "calgary philharmonic orchestra",
                    "message_count": 20,
                    "family_count": 18,
                    "review_mode": "auto-low-value",
                    "suggested_labels": ["promotions", "spam-low-value"],
                    "heuristic_rationale": "Recurring promo mail.",
                    "confidence": "high",
                    "examples": [
                        {
                            "account_id": "founder-hotmail",
                            "sender": "Calgary Philharmonic Orchestra",
                            "subject": "Fall season update",
                            "subject_key": "fall season update",
                        }
                    ],
                }
            ],
            "safety_review_clusters": [
                {
                    "provider": "outlookmail",
                    "sender_key": "google",
                    "message_count": 10,
                    "family_count": 2,
                    "review_mode": "safety-review",
                    "suggested_labels": ["account-security"],
                    "heuristic_rationale": "Security alert.",
                    "confidence": "medium",
                    "safety_priority": {
                        "priority_score": 7,
                        "reasons": ["approved-safety-memory", "safety-review-lane"],
                        "approved_disposition_ids": ["safety-001"],
                        "approved_dispositions": ["legitimate-security"],
                    },
                    "examples": [
                        {
                            "account_id": "founder-hotmail",
                            "sender": "Google",
                            "subject": "Security alert for your linked Google Account",
                            "subject_key": "security alert for your linked google account",
                        }
                    ],
                }
            ],
            "personal_review_clusters": [
                {
                    "provider": "outlookmail",
                    "sender_key": "justyna bedford",
                    "message_count": 8,
                    "family_count": 2,
                    "review_mode": "personal-review",
                    "suggested_labels": ["personal", "reply-needed"],
                    "heuristic_rationale": "Direct messages.",
                    "confidence": "medium",
                    "examples": [
                        {
                            "account_id": "founder-hotmail",
                            "sender": "Justyna Bedford",
                            "subject": "Justyna Bedford sent you a message.",
                            "subject_key": "justyna bedford sent you a message.",
                        }
                    ],
                }
            ],
            "preference_review_clusters": [
                {
                    "provider": "protonmail",
                    "sender_key": "noreply@tm.openai.com",
                    "message_count": 12,
                    "family_count": 7,
                    "review_mode": "preference-review",
                    "suggested_labels": [],
                    "llm_rationale": "Task update notifications likely map to a user preference.",
                    "llm_confidence": "medium",
                    "examples": [
                        {
                            "account_id": "founder-proton",
                            "sender": "\"OpenAI\" <noreply@tm.openai.com>",
                            "subject": "[Task Update] Reflect on time in writing",
                            "subject_key": "[task update] reflect on time in writing",
                        }
                    ],
                }
            ],
            "unclear_clusters": [],
        }

        pack = build_cluster_decision_pack(plan)

        self.assertEqual(pack["summary"]["decision_unit_count"], 4)
        self.assertEqual(pack["summary"]["message_coverage"], 50)
        self.assertEqual(pack["summary"]["family_coverage"], 29)
        self.assertEqual(pack["provider_summaries"]["outlookmail"]["decision_unit_count"], 3)
        self.assertEqual(pack["auto_low_value_policies"][0]["review_type"], "policy-review")
        self.assertEqual(
            pack["auto_low_value_policies"][0]["memory_seed"]["cluster_policy_key"],
            "outlookmail:calgary philharmonic orchestra",
        )
        self.assertIn(
            "historical recommendation promotions, spam-low-value",
            pack["auto_low_value_policies"][0]["memory_seed"]["llm_prompt_context"],
        )
        self.assertEqual(pack["safety_reviews"][0]["review_type"], "safety-review")
        self.assertEqual(pack["safety_reviews"][0]["safety_priority"]["priority_score"], 7)
        self.assertEqual(pack["safety_reviews"][0]["escalation_hint"]["level"], "review-soon")
        self.assertEqual(pack["personal_policies"][0]["suggested_labels"], ["personal", "reply-needed"])
        self.assertEqual(pack["preference_reviews"][0]["confidence"], "medium")
        self.assertEqual(pack["summary"]["safety_priority_review_count"], 1)

    def test_build_cluster_decision_pack_applies_lane_limits(self) -> None:
        plan = {
            "auto_low_value_clusters": [
                {"provider": "outlookmail", "sender_key": "a", "message_count": 2, "family_count": 1, "examples": []},
                {"provider": "outlookmail", "sender_key": "b", "message_count": 2, "family_count": 1, "examples": []},
            ],
            "safety_review_clusters": [],
            "personal_review_clusters": [],
            "preference_review_clusters": [],
            "unclear_clusters": [],
        }

        pack = build_cluster_decision_pack(plan, lane_limits={"auto_low_value_clusters": 1})

        self.assertEqual(pack["summary"]["decision_unit_count"], 1)
        self.assertEqual(len(pack["auto_low_value_policies"]), 1)
        self.assertEqual(pack["auto_low_value_policies"][0]["sender_key"], "a")

    def test_load_frontier_plan_preserves_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "frontier.json"
            plan_path.write_text(json.dumps({"summary": {}}))

            plan = load_frontier_plan(plan_path)

            self.assertEqual(plan["plan_path"], str(plan_path))


if __name__ == "__main__":
    unittest.main()
