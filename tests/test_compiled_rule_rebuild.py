import json
import tempfile
import unittest
from pathlib import Path

from src.compiled_rule_rebuild import rebuild_compiled_rules


class CompiledRuleRebuildTests(unittest.TestCase):
    def test_rebuild_compiled_rules_restores_approved_proposals_and_shadow_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "memory_proposals.json").write_text(
                json.dumps(
                    {
                        "proposals": [
                            {
                                "id": "proposal-gmail-sender-promotions-ebay",
                                "provider": "gmail",
                                "account_id": "founder-gmail",
                                "source_batch_id": "batch-1",
                                "source_message_ids": ["m1"],
                                "scope": "sender",
                                "label": "promotions",
                                "instruction": "Anything from ebay@reply.ebay.de should be promotions.",
                                "terms": ["ebay@reply.ebay.de"],
                                "source_examples": [{"sender": "eBay <ebay@reply.ebay.de>", "subject": "Promo", "message_id": "m1"}],
                                "explanation": "Approved hotspot.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-29T00:00:00Z",
                                "updated_at": "2026-06-29T00:00:00Z",
                                "approved_rule_id": "teach-200",
                                "review_notes": "",
                            }
                        ]
                    },
                    indent=2,
                )
            )
            (output_dir / "shadow_suggestion_memory.json").write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "sony",
                                "subject_key": "change your password",
                                "split": "discovery",
                                "count": 2,
                                "suggested_labels": ["account-security"],
                                "rationale": "Password flow.",
                                "evidence_terms": ["password"],
                                "source_examples": [{"sender": "Sony <alerts@sony.com>", "subject": "Change your password"}],
                                "generated_by": "openai-shadow-family-suggester",
                                "confidence": "high",
                                "status": "accepted",
                                "created_at": "2026-06-29T00:00:00Z",
                                "updated_at": "2026-06-29T00:00:00Z",
                                "review_notes": "",
                                "accepted_labels": ["account-security"],
                            }
                        ]
                    },
                    indent=2,
                )
            )

            result = rebuild_compiled_rules(output_dir)
            payload = json.loads((output_dir / "accepted_shadow_teachable_rules.json").read_text())

            self.assertEqual(result["proposal_rule_count"], 1)
            self.assertEqual(result["shadow_rule_count"], 1)
            self.assertEqual(result["total_rule_count"], 2)
            self.assertTrue(any(rule["id"] == "teach-200" for rule in payload["rules"]))
            self.assertTrue(any(rule["id"].startswith("shadow-outlookmail-") for rule in payload["rules"]))


if __name__ == "__main__":
    unittest.main()
