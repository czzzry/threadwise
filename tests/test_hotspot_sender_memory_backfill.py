import json
import tempfile
import unittest
from pathlib import Path

from src.hotspot_sender_memory_backfill import backfill_hotspot_sender_memory
from src.local_artifacts import accepted_shadow_rules_path


class HotspotSenderMemoryBackfillTests(unittest.TestCase):
    def test_backfill_creates_sender_wide_rule_for_marketing_hotspot_application(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            gmail_dir = root / "gmail_fetch"
            (gmail_dir / "batches").mkdir(parents=True, exist_ok=True)
            (output_dir / "founder_answer_applications").mkdir(parents=True, exist_ok=True)
            self._write_batch(
                gmail_dir,
                "gmail-batch-1",
                "founder-gmail",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "eBay <ebay@reply.ebay.de>",
                        "subject": "Promo A",
                        "snippet": "Promo",
                        "body": "Promo",
                    },
                    {
                        "message_id": "g2",
                        "sender": "eBay <ebay@reply.ebay.de>",
                        "subject": "Promo B",
                        "snippet": "Promo",
                        "body": "Promo",
                    },
                ],
            )
            accepted_shadow_rules_path(output_dir).parent.mkdir(parents=True, exist_ok=True)
            accepted_shadow_rules_path(output_dir).write_text(
                json.dumps(
                    {
                        "status": "PROTOTYPE - local teachable classification memory",
                        "rules": [
                            {
                                "id": "teach-1",
                                "instruction": "Anything from ebay@reply.ebay.de with subjects like 'promo a' should be promotions.",
                                "label": "promotions",
                                "terms": ["ebay@reply.ebay.de", "promo a"],
                                "keep_visible": False,
                                "created_at": "2026-06-29T00:00:00Z",
                                "providers": ["gmail"],
                                "enabled": True,
                                "source_examples": [
                                    {"sender": "eBay <ebay@reply.ebay.de>", "subject": "Promo A", "message_id": "g1"}
                                ],
                                "scope": "sender-cluster",
                                "match_mode": "sender-cluster",
                                "provenance": {},
                                "updated_at": "2026-06-29T00:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
            )
            (output_dir / "founder_answer_applications" / "app-1.json").write_text(
                json.dumps(
                    {
                        "question_id": "question-hotspot-gmail-ebay-reply-ebay-de",
                        "theme": "marketing-preference",
                        "approved_proposals": [
                            {
                                "id": "proposal-gmail-sender-cluster-promotions-ebay-reply-ebay-de-promo-a",
                                "provider": "gmail",
                                "account_id": "founder-gmail",
                                "source_batch_id": "gmail-batch-1",
                                "source_message_ids": ["g1", "g2"],
                                "scope": "sender-cluster",
                                "label": "promotions",
                                "instruction": "Anything from ebay@reply.ebay.de with subjects like 'promo a' should be promotions.",
                                "terms": ["ebay@reply.ebay.de", "promo a"],
                                "source_examples": [
                                    {"sender": "eBay <ebay@reply.ebay.de>", "subject": "Promo A", "message_id": "g1"},
                                    {"sender": "eBay <ebay@reply.ebay.de>", "subject": "Promo B", "message_id": "g2"},
                                ],
                                "explanation": "Hotspot answer.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-29T00:00:00Z",
                                "updated_at": "2026-06-29T00:00:00Z",
                                "approved_rule_id": "teach-1",
                                "sender_key": "ebay@reply.ebay.de",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            result = backfill_hotspot_sender_memory(output_dir, [("gmail", gmail_dir)])

            rules = json.loads(accepted_shadow_rules_path(output_dir).read_text())["rules"]
            sender_rules = [rule for rule in rules if rule.get("scope") == "sender"]
            self.assertEqual(result["processed_application_count"], 1)
            self.assertEqual(len(result["created_rule_ids"]), 1)
            self.assertEqual(len(sender_rules), 1)
            self.assertEqual(sender_rules[0]["label"], "promotions")
            self.assertIn("Anything from ebay@reply.ebay.de should be promotions.", sender_rules[0]["instruction"])

    def test_backfill_skips_non_sender_wide_themes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            proton_dir = root / "protonmail_fetch"
            (proton_dir / "batches").mkdir(parents=True, exist_ok=True)
            (output_dir / "founder_answer_applications").mkdir(parents=True, exist_ok=True)
            accepted_shadow_rules_path(output_dir).parent.mkdir(parents=True, exist_ok=True)
            accepted_shadow_rules_path(output_dir).write_text(json.dumps({"status": "PROTOTYPE", "rules": []}, indent=2))
            (output_dir / "founder_answer_applications" / "app-1.json").write_text(
                json.dumps(
                    {
                        "question_id": "question-hotspot-protonmail-noreply-tm-openai-com",
                        "theme": "personal-vs-low-value",
                        "approved_proposals": [
                            {
                                "id": "proposal-protonmail-sender-cluster-personal-noreply-tm-openai-com-task",
                                "provider": "protonmail",
                                "account_id": "founder-proton",
                                "source_batch_id": "batch-1",
                                "source_message_ids": ["p1"],
                                "scope": "sender-cluster",
                                "label": "personal",
                                "instruction": "Anything from noreply@tm.openai.com with subjects like '[task update]' should be personal.",
                                "terms": ["noreply@tm.openai.com", "[task update]"],
                                "source_examples": [
                                    {"sender": '"ChatGPT" <noreply@tm.openai.com>', "subject": "[Task Update] A", "message_id": "p1"}
                                ],
                                "explanation": "Hotspot answer.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-29T00:00:00Z",
                                "updated_at": "2026-06-29T00:00:00Z",
                                "approved_rule_id": "teach-1",
                                "sender_key": "noreply@tm.openai.com",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            result = backfill_hotspot_sender_memory(output_dir, [("protonmail", proton_dir)])
            rules = json.loads(accepted_shadow_rules_path(output_dir).read_text())["rules"]
            self.assertEqual(result["processed_application_count"], 0)
            self.assertEqual(result["created_rule_ids"], [])
            self.assertEqual(rules, [])

    def _write_batch(self, storage_dir: Path, batch_id: str, account_id: str, provider: str, items: list[dict]) -> None:
        (storage_dir / "batches" / f"{batch_id}.json").write_text(
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
