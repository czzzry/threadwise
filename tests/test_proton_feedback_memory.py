import json
import tempfile
import unittest
from pathlib import Path

from src.proton_feedback_memory import load_rules, migrate_review_feedback, save_feedback_rule
from src.protonmail_fetcher import ProtonMailBatchFetcher


class FakeProtonClient:
    def list_messages(self, max_results: int) -> list[str]:
        return ["message-2"]

    def get_message(self, message_id: str) -> dict:
        return {
            "id": message_id,
            "sender": "Example <person@example.test>",
            "subject": "A new message",
            "body": "A new message from this sender.",
            "mailbox": "inbox",
        }


class ProtonFeedbackMemoryTests(unittest.TestCase):
    def test_feedback_becomes_a_sender_scoped_proton_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = save_feedback_rule(
                root,
                message_id="message-1",
                sender="Example <person@example.test>",
                subject="A new message",
                note="This sender is always work.",
                internal_label="job-related",
            )

            self.assertEqual(result["status"], "accepted-as-sender-rule")
            rules = load_rules(root)
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].providers, ("protonmail",))
            self.assertEqual(rules[0].match_mode, "sender")

    def test_safety_sensitive_feedback_is_recorded_without_automatic_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = save_feedback_rule(
                root,
                message_id="message-1",
                sender="Example <person@example.test>",
                subject="A promotion",
                note="This sender is always promo.",
                internal_label="promotions",
            )

            self.assertEqual(result["status"], "recorded-needs-review")
            self.assertEqual(load_rules(root), [])

    def test_existing_review_notes_are_migrated_without_provider_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "batches").mkdir()
            (root / "batches" / "founder-proton-batch-1.json").write_text(json.dumps({
                "provider": "protonmail",
                "raw_messages": [{"id": "message-1", "sender": "Example <person@example.test>", "subject": "A new message"}],
                "items": [{"message_id": "message-1"}],
            }))
            review_path = root / "review.json"
            review_path.write_text(json.dumps({
                "messages": {
                    "message-1": {
                        "decision": "label-added",
                        "internal_label": "job-related",
                        "note": "Always work from this sender.",
                    }
                }
            }))

            result = migrate_review_feedback(root, review_path)

            self.assertEqual(result["migrated_count"], 1)
            self.assertEqual(len(load_rules(root)), 1)

    def test_future_proton_fetch_applies_saved_feedback_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            save_feedback_rule(
                root,
                message_id="message-1",
                sender="Example <person@example.test>",
                subject="An earlier message",
                note="This sender is always work.",
                internal_label="job-related",
            )

            queue = ProtonMailBatchFetcher(FakeProtonClient(), root).fetch_protonmail_batch("founder-proton", 10)

            self.assertEqual(queue["items"][0]["applied_labels"], ["job-related"])


if __name__ == "__main__":
    unittest.main()
