import json
import tempfile
import unittest
from pathlib import Path

from src.founder_answer_decision import build_founder_answer_decision, save_founder_answer_decision
from src.local_artifacts import memory_proposals_path


class FounderAnswerDecisionTests(unittest.TestCase):
    def test_build_decision_matches_natural_language_to_answer_option(self) -> None:
        founder_answer_pack = {
            "questions": [
                {
                    "question_id": "question-marketing-preference",
                    "theme": "marketing-preference",
                    "title": "Title",
                    "prompt": "Prompt",
                    "answer_options": [
                        {
                            "answer_key": "low_value_default",
                            "description": "Default these families to promo/low-value handling.",
                            "proposal_drafts": [{"id": "proposal-1"}],
                            "projection": {"proposal_count": 1, "estimated_resolved_messages": 6},
                        },
                        {
                            "answer_key": "keep_visible",
                            "description": "Keep these visible unless narrower.",
                            "proposal_drafts": [],
                            "projection": {"proposal_count": 0, "estimated_resolved_messages": 0},
                        },
                    ],
                }
            ]
        }

        decision = build_founder_answer_decision(
            founder_answer_pack=founder_answer_pack,
            question_id="question-marketing-preference",
            response_text="These are promos and I do not want them in normal attention.",
        )

        self.assertEqual(decision["matched_answer_key"], "low_value_default")
        self.assertEqual(decision["projection"]["estimated_resolved_messages"], 6)
        self.assertEqual(decision["match_confidence"], "high")

    def test_save_decision_writes_pending_memory_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            founder_answer_pack = {
                "questions": [
                    {
                        "question_id": "question-direct-message",
                        "theme": "direct-message-handling",
                        "title": "Title",
                        "prompt": "Prompt",
                        "answer_options": [
                            {
                                "answer_key": "personal_default",
                                "description": "Keep visible as personal.",
                                "proposal_drafts": [
                                    {
                                        "id": "proposal-outlookmail-sender-cluster-personal-krysia-druzkowska",
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "source_batch_id": "founder-hotmail-batch-8",
                                        "source_message_ids": ["m1"],
                                        "scope": "sender-cluster",
                                        "label": "personal",
                                        "instruction": "Anything from krysia should be personal.",
                                        "terms": ["krysia druzkowska", "krysia druzkowska sent you a message."],
                                        "source_examples": [{"sender": "Krysia Druzkowska", "subject": "Krysia Druzkowska sent you a message."}],
                                        "explanation": "Drafted from founder answer.",
                                        "preview": {"match_count": 3, "matches": []},
                                        "status": "pending",
                                        "created_at": "2026-06-28T00:00:00Z",
                                        "updated_at": "2026-06-28T00:00:00Z",
                                    }
                                ],
                                "projection": {"proposal_count": 1, "estimated_resolved_messages": 3},
                            }
                        ],
                    }
                ]
            }

            decision = save_founder_answer_decision(
                output_storage_dir=output_dir,
                founder_answer_pack=founder_answer_pack,
                question_id="question-direct-message",
                response_text="These look personal, keep them visible.",
            )

            self.assertEqual(decision["matched_answer_key"], "personal_default")
            proposals = json.loads(memory_proposals_path(output_dir).read_text())["proposals"]
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["label"], "personal")

    def test_sender_cluster_proposals_keep_distinct_ids_for_distinct_subject_families(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            founder_answer_pack = {
                "questions": [
                    {
                        "question_id": "question-marketing-preference",
                        "theme": "marketing-preference",
                        "title": "Title",
                        "prompt": "Prompt",
                        "answer_options": [
                            {
                                "answer_key": "low_value_default",
                                "description": "Default low value.",
                                "proposal_drafts": [
                                    {
                                        "id": "proposal-outlookmail-sender-cluster-promotions-lieferando-30-rabatt",
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "source_batch_id": "founder-hotmail-batch-8",
                                        "source_message_ids": ["m1"],
                                        "scope": "sender-cluster",
                                        "label": "promotions",
                                        "instruction": "Anything from lieferando with subjects like '30 % rabatt' should be promotions.",
                                        "terms": ["lieferando", "30 % rabatt"],
                                        "source_examples": [{"sender": "Lieferando", "subject": "30 % Rabatt"}],
                                        "explanation": "Draft one.",
                                        "preview": {"match_count": 3, "matches": []},
                                        "status": "pending",
                                        "created_at": "2026-06-28T00:00:00Z",
                                        "updated_at": "2026-06-28T00:00:00Z",
                                    },
                                    {
                                        "id": "proposal-outlookmail-sender-cluster-promotions-lieferando-coupon-inside",
                                        "provider": "outlookmail",
                                        "account_id": "founder-hotmail",
                                        "source_batch_id": "founder-hotmail-batch-8",
                                        "source_message_ids": ["m2"],
                                        "scope": "sender-cluster",
                                        "label": "promotions",
                                        "instruction": "Anything from lieferando with subjects like 'coupon inside' should be promotions.",
                                        "terms": ["lieferando", "coupon inside"],
                                        "source_examples": [{"sender": "Lieferando", "subject": "Coupon inside"}],
                                        "explanation": "Draft two.",
                                        "preview": {"match_count": 3, "matches": []},
                                        "status": "pending",
                                        "created_at": "2026-06-28T00:00:00Z",
                                        "updated_at": "2026-06-28T00:00:00Z",
                                    },
                                ],
                                "projection": {"proposal_count": 2, "estimated_resolved_messages": 6},
                            }
                        ],
                    }
                ]
            }

            decision = save_founder_answer_decision(
                output_storage_dir=output_dir,
                founder_answer_pack=founder_answer_pack,
                question_id="question-marketing-preference",
                response_text="These are promos and low value.",
            )

            self.assertEqual(len(decision["saved_proposal_ids"]), 2)
            self.assertNotEqual(decision["saved_proposal_ids"][0], decision["saved_proposal_ids"][1])


if __name__ == "__main__":
    unittest.main()
