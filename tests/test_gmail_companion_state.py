import json
import tempfile
import unittest
from pathlib import Path

from src.gmail_companion_state import build_companion_runtime_payload


class GmailCompanionStateTests(unittest.TestCase):
    def test_runtime_queue_is_provider_scoped_and_reconciled_to_live_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir()
            for batch_id, provider, message_id in (
                ("gmail-old", "gmail", "gmail-old"),
                ("gmail-current", "gmail", "gmail-current"),
                ("proton-current", "protonmail", "proton-current"),
            ):
                (batches_dir / f"{batch_id}.json").write_text(
                    json.dumps(
                        {
                            "batch_id": batch_id,
                            "provider": provider,
                            "account_id": provider,
                            "items": [
                                {
                                    "message_id": message_id,
                                    "review_state": "pending",
                                    "final_labels": [],
                                    "applied_labels": [],
                                }
                            ],
                            "raw_messages": [],
                        }
                    )
                )

            payload = build_companion_runtime_payload(
                storage_dir,
                provider="gmail",
                allowed_review_message_ids={"gmail-current"},
            )

            self.assertEqual(
                [item["message_id"] for item in payload["needs_attention_items"]],
                ["gmail-current"],
            )
            self.assertEqual(payload["daily_summary"]["needs_attention_count"], 1)
            self.assertEqual(payload["daily_summary"]["live_inbox_count"], 1)


if __name__ == "__main__":
    unittest.main()
