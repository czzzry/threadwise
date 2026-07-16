import tempfile
import unittest
from pathlib import Path

from src.protonmail_manual_review import ProtonManualReviewRunner


class FakeProtonClient:
    def __init__(self) -> None:
        self.messages = {
            "1": {"id": "1", "sender": "person@example.com", "subject": "Can you reply?", "body": "First line\nImportant context at the very end."},
            "2": {"id": "2", "sender": "store@example.com", "subject": "Receipt", "body": "Payment receipt in full."},
        }
        self.calls = []

    def list_messages(self, max_results):
        self.calls.append(("list_messages", max_results))
        return list(self.messages)[:max_results]

    def get_message(self, message_id):
        self.calls.append(("get_message", message_id))
        return dict(self.messages[message_id])

    def apply_label(self, message_id, label_name):
        self.calls.append(("apply_label", message_id, label_name))
        return {"message_id": message_id, "label": label_name, "inbox_preserved": True, "destructive_actions": []}


class RecordingModel:
    def __init__(self) -> None:
        self.messages = []

    def classify(self, messages):
        self.messages.extend(messages)
        return [
            {"message_id": message["id"], "label": "reply-needed" if message["id"] == "1" else "receipt-billing", "reason": "Reviewed full body."}
            for message in messages
        ]


class RecordingUncertaintyModel:
    def assess(self, messages):
        return [
            {
                "message_id": message["id"],
                "confidence": 0.4 if message["id"] == "1" else 0.8,
                "uncertainty_reason": "Could be action or personal." if message["id"] == "1" else "Mostly clear.",
            }
            for message in messages
        ]


class ProtonManualReviewRunnerTest(unittest.TestCase):
    def test_uncertainty_review_adds_overlay_without_replacing_primary_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.json"
            client = FakeProtonClient()
            ProtonManualReviewRunner(client, RecordingModel(), ledger).run(max_results=10, batch_size=2)

            summary = ProtonManualReviewRunner(client, RecordingModel(), ledger).label_least_confident(
                RecordingUncertaintyModel(), limit=1, max_results=10, batch_size=2
            )

            self.assertEqual(summary["double_check_count"], 1)
            self.assertIn(("apply_label", "1", "EA/DoubleCheck"), client.calls)
            self.assertIn(("apply_label", "1", "EA/NeedsAction"), client.calls)

    def test_reads_full_messages_and_only_applies_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FakeProtonClient()
            model = RecordingModel()
            runner = ProtonManualReviewRunner(client, model, Path(temp_dir) / "ledger.json")

            summary = runner.run(max_results=10, batch_size=2)

            self.assertEqual(summary["applied_count"], 2)
            self.assertIn("Important context at the very end.", model.messages[0]["body"])
            self.assertIn(("apply_label", "1", "EA/NeedsAction"), client.calls)
            self.assertIn(("apply_label", "2", "EA/Receipts"), client.calls)
            self.assertFalse(any(call[0] in {"delete", "archive", "trash", "move", "spam"} for call in client.calls))

    def test_resume_skips_messages_already_confirmed_in_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = Path(temp_dir) / "ledger.json"
            client = FakeProtonClient()
            first_model = RecordingModel()
            ProtonManualReviewRunner(client, first_model, ledger).run(max_results=10, batch_size=2)
            second_model = RecordingModel()

            summary = ProtonManualReviewRunner(client, second_model, ledger).run(max_results=10, batch_size=2)

            self.assertEqual(summary["applied_count"], 0)
            self.assertEqual(summary["already_applied_count"], 2)
            self.assertEqual(second_model.messages, [])


if __name__ == "__main__":
    unittest.main()
