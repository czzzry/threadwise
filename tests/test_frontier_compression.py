import json
import tempfile
import unittest
from pathlib import Path

from src.frontier_compression import build_frontier_compression_plan
from src.teachable_rule_memory import TeachableRule


class FrontierCompressionTests(unittest.TestCase):
    def test_groups_unresolved_messages_into_sender_clusters_and_auto_low_value_lane(self) -> None:
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
                        "subject": "Nicht vergessen: dein 20 € Rabatt 😍",
                        "snippet": "Discount mail.",
                        "body": "Discount mail.",
                    },
                    {
                        "message_id": "o2",
                        "sender": "Lieferando",
                        "subject": "Schnapp dir mindestens 25 % Rabatt 🏃",
                        "snippet": "Discount mail.",
                        "body": "Discount mail.",
                    },
                ],
            )

            plan = build_frontier_compression_plan([("outlookmail", outlook_dir)], extra_rules=[])

            self.assertEqual(plan["summary"]["total_unresolved_sender_clusters"], 1)
            self.assertEqual(plan["summary"]["auto_low_value_clusters"], 1)
            cluster = plan["auto_low_value_clusters"][0]
            self.assertEqual(cluster["sender_key"], "lieferando")
            self.assertEqual(cluster["message_count"], 2)
            self.assertEqual(cluster["family_count"], 2)
            self.assertEqual(cluster["suggested_labels"], ["promotions", "spam-low-value"])

    def test_routes_security_and_personal_message_clusters(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proton_dir = root / "protonmail"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                proton_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Mercor Trust & Safety <expert-trust@mercor.com>",
                        "subject": "Update from Mercor Security Team",
                        "snippet": "Security team update.",
                        "body": "Security team update.",
                    }
                ],
            )
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Krysia Druzkowska",
                        "subject": "Krysia Druzkowska sent you a message.",
                        "snippet": "Message notification.",
                        "body": "Message notification.",
                    }
                ],
            )

            plan = build_frontier_compression_plan(
                [("protonmail", proton_dir), ("outlookmail", outlook_dir)],
                extra_rules=[],
            )

            self.assertEqual(plan["summary"]["safety_review_clusters"], 1)
            self.assertEqual(plan["summary"]["personal_review_clusters"], 1)
            self.assertEqual(plan["safety_review_clusters"][0]["suggested_labels"], ["account-security"])
            self.assertEqual(plan["personal_review_clusters"][0]["suggested_labels"], ["personal", "reply-needed"])

    def test_excludes_messages_already_resolved_by_accepted_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Amazon.de" <no-reply@amazon.de>',
                        "subject": "Your return for Amazon order 305-0960012-3218757",
                        "snippet": "Order return.",
                        "body": "Order return.",
                    }
                ],
            )
            rules = [
                TeachableRule(
                    id="shadow-gmail-001",
                    instruction="Anything from no-reply@amazon.de with subject like 'your return for amazon order #-#-#' should be receipt-billing.",
                    label="receipt-billing",
                    terms=("no-reply@amazon.de", "your return for amazon order #-#-#"),
                    keep_visible=False,
                    created_at="2026-06-28T00:00:00Z",
                    providers=("gmail",),
                    enabled=True,
                    source_examples=(
                        {
                            "sender": '"Amazon.de" <no-reply@amazon.de>',
                            "subject": "Your return for Amazon order 305-0960012-3218757",
                        },
                    ),
                )
            ]

            plan = build_frontier_compression_plan([("gmail", gmail_dir)], extra_rules=rules)

            self.assertEqual(plan["summary"]["total_unresolved_sender_clusters"], 0)

    def test_prioritizes_clusters_with_approved_safety_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                        "subject": "Service report 123456",
                        "snippet": "Open attached report.",
                        "body": "Open attached report.",
                    }
                ],
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

            plan = build_frontier_compression_plan([("gmail", gmail_dir)], extra_rules=[])

            self.assertEqual(plan["summary"]["safety_priority_clusters"], 1)
            self.assertEqual(plan["top_safety_priority_clusters"][0]["sender_key"], "alerts@pestsolutions.test")
            self.assertEqual(plan["top_safety_priority_clusters"][0]["safety_priority"]["priority_score"], 10)

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
