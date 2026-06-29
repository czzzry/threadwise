import json
import tempfile
import unittest
from pathlib import Path

from src.founder_answer_pack import build_founder_answer_pack


class FounderAnswerPackTests(unittest.TestCase):
    def test_build_answer_pack_creates_memory_proposals_for_actionable_answers(self) -> None:
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
                        "sender": "Lieferando",
                        "subject": "30 % Rabatt auf Gemüse",
                        "snippet": "Rabatt.",
                        "body": "Rabatt.",
                    },
                    {
                        "message_id": "o2",
                        "sender": "Lieferando",
                        "subject": "Coupon inside",
                        "snippet": "Coupon.",
                        "body": "Coupon.",
                    },
                ],
            )
            founder_question_pack = {
                "questions": [
                    {
                        "question_id": "question-marketing-preference",
                        "theme": "marketing-preference",
                        "title": "How should recurring marketing mail be handled?",
                        "prompt": "Prompt.",
                        "providers": ["outlookmail"],
                        "family_count": 1,
                        "estimated_unblocked_messages": 2,
                        "answer_options": [],
                        "draft_answers": [
                            {"answer_key": "low_value_default", "description": "Default low value."},
                            {"answer_key": "keep_visible", "description": "Keep visible."},
                        ],
                        "example_targets": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "lieferando",
                                "subject_key": "30 % rabatt auf gemüse",
                                "count": 2,
                            }
                        ],
                    }
                ]
            }
            review_pack = {
                "top_review_targets": [
                    {
                        "provider": "outlookmail",
                        "sender_key": "lieferando",
                        "subject_key": "30 % rabatt auf gemüse",
                        "count": 2,
                        "examples": [
                            {
                                "account_id": "founder-hotmail",
                                "batch_id": "founder-hotmail-batch-1",
                                "message_id": "o1",
                                "sender": "Lieferando",
                                "subject": "30 % Rabatt auf Gemüse",
                            },
                            {
                                "account_id": "founder-hotmail",
                                "batch_id": "founder-hotmail-batch-1",
                                "message_id": "o2",
                                "sender": "Lieferando",
                                "subject": "Coupon inside",
                            },
                        ],
                    }
                ]
            }

            pack = build_founder_answer_pack(
                founder_question_pack=founder_question_pack,
                review_pack=review_pack,
                provider_storage_dirs=[("outlookmail", outlook_dir)],
            )

            self.assertEqual(pack["summary"]["question_count"], 1)
            self.assertEqual(pack["summary"]["actionable_answer_count"], 1)
            actionable = pack["questions"][0]["answer_options"][0]
            self.assertEqual(actionable["answer_key"], "low_value_default")
            self.assertEqual(actionable["projection"]["estimated_resolved_messages"], 2)
            self.assertEqual(actionable["proposal_drafts"][0]["label"], "promotions")
            self.assertEqual(pack["questions"][0]["answer_options"][1]["projection"]["estimated_resolved_messages"], 0)

    def test_build_answer_pack_supports_receipt_billing_for_purchase_confirmations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-24",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "\"Yoga Barn Berlin\" <no-reply@eversports.com>",
                        "subject": "Dein Kauf bei Yoga Barn Berlin",
                        "snippet": "Danke fuer den Einkauf.",
                        "body": "Danke fuer den Einkauf. Die Rechnung findest du im Anhang.",
                    }
                ],
            )
            founder_question_pack = {
                "questions": [
                    {
                        "question_id": "question-shopping",
                        "theme": "shopping-and-order-confirmations",
                        "title": "Title",
                        "prompt": "Prompt",
                        "providers": ["gmail"],
                        "family_count": 1,
                        "estimated_unblocked_messages": 1,
                        "draft_answers": [
                            {"answer_key": "shopping_order_default", "description": "Shopping order."},
                            {"answer_key": "receipt_billing_default", "description": "Receipt billing."},
                            {"answer_key": "calendar_or_personal_default", "description": "Calendar or personal."},
                        ],
                        "example_targets": [
                            {
                                "provider": "gmail",
                                "sender_key": "namaste@yoga-barn-berlin.de",
                                "subject_key": "dein kauf bei yoga barn berlin",
                                "count": 1,
                            }
                        ],
                    }
                ]
            }
            review_pack = {
                "top_review_targets": [
                    {
                        "provider": "gmail",
                        "sender_key": "namaste@yoga-barn-berlin.de",
                        "subject_key": "dein kauf bei yoga barn berlin",
                        "count": 1,
                        "examples": [
                            {
                                "account_id": "founder-test",
                                "batch_id": "founder-test-batch-24",
                                "message_id": "g1",
                                "sender": "\"Yoga Barn Berlin\" <no-reply@eversports.com>",
                                "subject": "Dein Kauf bei Yoga Barn Berlin",
                            }
                        ],
                    }
                ]
            }

            pack = build_founder_answer_pack(
                founder_question_pack=founder_question_pack,
                review_pack=review_pack,
                provider_storage_dirs=[("gmail", gmail_dir)],
            )

            options = {option["answer_key"]: option for option in pack["questions"][0]["answer_options"]}
            self.assertEqual(options["receipt_billing_default"]["proposal_drafts"][0]["label"], "receipt-billing")
            self.assertEqual(options["receipt_billing_default"]["projection"]["estimated_resolved_messages"], 1)

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
