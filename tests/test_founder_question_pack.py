import unittest

from src.founder_question_pack import build_founder_question_pack


class FounderQuestionPackTests(unittest.TestCase):
    def test_build_question_pack_collapses_multiple_targets_into_fewer_questions(self) -> None:
        review_pack = {
            "top_review_targets": [
                {
                    "provider": "outlookmail",
                    "sender_key": "lieferando",
                    "subject_key": "30 % rabatt",
                    "count": 27,
                    "question_lane": "preference-question",
                    "suggested_labels": ["promotions", "spam-low-value"],
                    "review_priority": {"score": 5, "estimated_message_gain": 27},
                },
                {
                    "provider": "outlookmail",
                    "sender_key": "groupon",
                    "subject_key": "coupon inside",
                    "count": 15,
                    "question_lane": "preference-question",
                    "suggested_labels": ["promotions"],
                    "review_priority": {"score": 4, "estimated_message_gain": 15},
                },
                {
                    "provider": "gmail",
                    "sender_key": "security@example.com",
                    "subject_key": "verify your login",
                    "count": 8,
                    "question_lane": "objective-review",
                    "suggested_labels": ["account-security"],
                    "review_priority": {"score": 9, "estimated_message_gain": 8},
                },
            ]
        }
        memory_impact = {
            "next_review_payoffs": [
                {
                    "provider": "outlookmail",
                    "sender_key": "lieferando",
                    "subject_key": "30 % rabatt",
                    "expected_resolved_messages": 27,
                },
                {
                    "provider": "outlookmail",
                    "sender_key": "groupon",
                    "subject_key": "coupon inside",
                    "expected_resolved_messages": 15,
                },
                {
                    "provider": "gmail",
                    "sender_key": "security@example.com",
                    "subject_key": "verify your login",
                    "expected_resolved_messages": 8,
                },
            ]
        }
        provider_drivers = [
            {"provider": "outlookmail", "driver_score": 15},
            {"provider": "gmail", "driver_score": 9},
        ]

        pack = build_founder_question_pack(
            review_pack=review_pack,
            memory_impact=memory_impact,
            provider_drivers=provider_drivers,
            max_questions=5,
        )

        self.assertEqual(pack["summary"]["question_count"], 2)
        self.assertGreaterEqual(pack["summary"]["estimated_unblocked_messages"], 50)
        self.assertEqual(pack["questions"][0]["theme"], "marketing-preference")
        self.assertEqual(pack["questions"][0]["family_count"], 2)
        self.assertIn("lieferando", pack["questions"][0]["example_senders"])
        self.assertEqual(pack["questions"][1]["theme"], "account-security-handling")

    def test_build_question_pack_uses_text_heuristics_for_better_question_themes(self) -> None:
        review_pack = {
            "top_review_targets": [
                {
                    "provider": "gmail",
                    "sender_key": "namaste@yoga-barn-berlin.de",
                    "subject_key": "deine anmeldung bei yoga barn berlin",
                    "question_lane": "taxonomy-question",
                    "suggested_labels": [],
                    "count": 5,
                    "review_priority": {"score": 2, "estimated_message_gain": 5},
                    "examples": [
                        {
                            "sender": "\"Yoga Barn Berlin via Eversports\" <no-reply@eversports.com>",
                            "subject": "Deine Anmeldung bei Yoga Barn Berlin",
                        }
                    ],
                },
                {
                    "provider": "outlookmail",
                    "sender_key": "krysia druzkowska",
                    "subject_key": "krysia druzkowska sent you a message.",
                    "question_lane": "taxonomy-question",
                    "suggested_labels": [],
                    "count": 3,
                    "review_priority": {"score": 1, "estimated_message_gain": 3},
                    "examples": [{"sender": "Krysia Druzkowska", "subject": "Krysia Druzkowska sent you a message."}],
                },
                {
                    "provider": "protonmail",
                    "sender_key": "expedia@eg.expedia.com",
                    "subject_key": "updates to our rewards program terms and conditions",
                    "question_lane": "taxonomy-question",
                    "suggested_labels": [],
                    "count": 1,
                    "review_priority": {"score": 0, "estimated_message_gain": 1},
                    "examples": [{"sender": "\"Expedia.com\" <expedia@eg.expedia.com>", "subject": "Updates to our rewards program terms and conditions"}],
                },
            ]
        }

        pack = build_founder_question_pack(review_pack=review_pack, memory_impact={}, provider_drivers=[], max_questions=5)
        themes = [question["theme"] for question in pack["questions"]]

        self.assertIn("events-and-confirmations", themes)
        self.assertIn("direct-message-handling", themes)
        self.assertIn("terms-and-policy-updates", themes)

    def test_build_question_pack_splits_booking_and_purchase_families_for_same_sender(self) -> None:
        review_pack = {
            "top_review_targets": [
                {
                    "provider": "gmail",
                    "sender_key": "namaste@yoga-barn-berlin.de",
                    "subject_key": "deine anmeldung bei yoga barn berlin",
                    "question_lane": "taxonomy-question",
                    "suggested_labels": [],
                    "count": 5,
                    "review_priority": {"score": 2, "estimated_message_gain": 5},
                    "examples": [
                        {
                            "sender": "\"Yoga Barn Berlin via Eversports\" <no-reply@eversports.com>",
                            "subject": "Deine Anmeldung bei Yoga Barn Berlin",
                        }
                    ],
                },
                {
                    "provider": "gmail",
                    "sender_key": "namaste@yoga-barn-berlin.de",
                    "subject_key": "dein kauf bei yoga barn berlin",
                    "question_lane": "taxonomy-question",
                    "suggested_labels": [],
                    "count": 2,
                    "review_priority": {"score": 2, "estimated_message_gain": 2},
                    "examples": [
                        {
                            "sender": "\"Yoga Barn Berlin via Eversports\" <no-reply@eversports.com>",
                            "subject": "Dein Kauf bei Yoga Barn Berlin",
                        }
                    ],
                },
            ]
        }

        pack = build_founder_question_pack(review_pack=review_pack, memory_impact={}, provider_drivers=[], max_questions=5)
        by_sender = {
            tuple(question["example_senders"]): question["theme"]
            for question in pack["questions"]
        }

        self.assertEqual(len(pack["questions"]), 2)
        self.assertIn("events-and-confirmations", [question["theme"] for question in pack["questions"]])
        self.assertIn("shopping-and-order-confirmations", [question["theme"] for question in pack["questions"]])


if __name__ == "__main__":
    unittest.main()
