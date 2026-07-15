import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.gmail_companion_ui import GmailCompanionApp
from src.handled_review_store import HandledReviewStore


class HandledReviewStoreTests(unittest.TestCase):
    def test_acknowledgment_is_durable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            store = HandledReviewStore(storage_dir)

            first = store.acknowledge(
                provider="gmail",
                account_id="founder-test",
                message_id="message-1",
                batch_id="batch-1",
            )
            second = store.acknowledge(
                provider="gmail",
                account_id="founder-test",
                message_id="message-1",
                batch_id="batch-1",
            )

            self.assertEqual(first, second)
            self.assertTrue(store.is_acknowledged({
                "provider": "gmail",
                "account_id": "founder-test",
                "message_id": "message-1",
            }))
            payload = json.loads((storage_dir / "handled_review_decisions.json").read_text())
            self.assertEqual(len(payload["decisions"]), 1)

    def test_acknowledgment_does_not_hide_a_different_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = HandledReviewStore(Path(temp_dir))
            store.acknowledge(provider="gmail", account_id="founder-test", message_id="message-1")

            self.assertFalse(store.is_acknowledged({
                "provider": "gmail",
                "account_id": "founder-test",
                "message_id": "message-2",
            }))

    def test_harness_state_filters_acknowledged_handled_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            item = {
                "provider": "gmail",
                "account_id": "founder-test",
                "message_id": "message-1",
                "status": "auto-handled",
            }
            app = GmailCompanionApp(storage_dir)
            app._handled_review_store.acknowledge(
                provider="gmail",
                account_id="founder-test",
                message_id="message-1",
            )

            with patch.object(app, "_cached_runtime_payload", return_value={"items": [item], "daily_summary": {}}), patch.object(
                app,
                "sidebar_state",
                return_value={"selected_email": {"found": True, **item}, "daily_summary": {}},
            ):
                payload = app._build_harness_state({"provider": "gmail", "message_id": "message-1"})

            self.assertEqual(payload["recent_items"], [])
            self.assertEqual(payload["auto_handled_items"], [])
            self.assertTrue(payload["sidebar_state"]["selected_email"]["handled_review_acknowledged"])


if __name__ == "__main__":
    unittest.main()
