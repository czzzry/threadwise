import tempfile
import unittest
from pathlib import Path

from src.gmail_safety_action import GmailSafetyAction


class RecordingGmailSafetyClient:
    def __init__(self, *, fail_at: str = "") -> None:
        self.calls = []
        self.fail_at = fail_at

    def get_or_create_label(self, name):
        self.calls.append(("get_or_create_label", name))
        return "Label_suspicious"

    def create_trash_filter(self, sender_query, label_id):
        self.calls.append(("create_trash_filter", sender_query, label_id))
        if self.fail_at == "filter":
            raise RuntimeError("filter failed")
        return "filter-001"

    def replace_threadwise_labels(self, message_id, label_ids, namespace_prefix):
        self.calls.append(("replace_threadwise_labels", message_id, label_ids, namespace_prefix))
        if self.fail_at == "label":
            raise RuntimeError("label failed")

    def trash_message(self, message_id):
        self.calls.append(("trash_message", message_id))
        if self.fail_at == "trash":
            raise RuntimeError("trash failed")

    def delete_filter(self, filter_id):
        self.calls.append(("delete_filter", filter_id))


class GmailSafetyActionTest(unittest.TestCase):
    def test_preview_defaults_to_exact_sender_and_states_every_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            action = GmailSafetyAction(RecordingGmailSafetyClient(), Path(temp_dir))

            preview = action.preview(
                message_id="message-1",
                sender='Alerts <alerts@example.com>',
                scope="sender",
            )

            self.assertEqual(preview["match"], "alerts@example.com")
            self.assertEqual(preview["current_email"], "Label EA/Suspicious and move to Gmail Trash")
            self.assertEqual(preview["future_emails"], "Gmail filter sends exact-sender matches to Trash")
            self.assertTrue(preview["requires_confirmation"])

    def test_apply_creates_future_filter_before_touching_current_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = RecordingGmailSafetyClient()
            action = GmailSafetyAction(client, Path(temp_dir))

            result = action.apply(
                account_id="owner@example.com",
                message_id="message-1",
                sender='Alerts <alerts@example.com>',
                scope="sender",
                confirmed=True,
            )

            self.assertEqual(result["status"], "applied")
            self.assertEqual(
                client.calls,
                [
                    ("get_or_create_label", "EA/Suspicious"),
                    ("create_trash_filter", "alerts@example.com", "Label_suspicious"),
                    ("replace_threadwise_labels", "message-1", ["Label_suspicious"], "EA/"),
                    ("trash_message", "message-1"),
                ],
            )

    def test_domain_scope_is_only_used_when_explicitly_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = RecordingGmailSafetyClient()
            action = GmailSafetyAction(client, Path(temp_dir))

            result = action.apply(
                account_id="owner@example.com",
                message_id="message-1",
                sender="alerts@sub.example.com",
                scope="domain",
                confirmed=True,
            )

            self.assertEqual(result["match"], "@sub.example.com")
            self.assertIn(("create_trash_filter", "@sub.example.com", "Label_suspicious"), client.calls)

    def test_apply_requires_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            action = GmailSafetyAction(RecordingGmailSafetyClient(), Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "confirmation"):
                action.apply(
                    account_id="owner@example.com",
                    message_id="message-1",
                    sender="alerts@example.com",
                    scope="sender",
                    confirmed=False,
                )

    def test_failed_current_write_removes_new_future_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = RecordingGmailSafetyClient(fail_at="label")
            action = GmailSafetyAction(client, Path(temp_dir))

            with self.assertRaisesRegex(RuntimeError, "label failed"):
                action.apply(
                    account_id="owner@example.com",
                    message_id="message-1",
                    sender="alerts@example.com",
                    scope="sender",
                    confirmed=True,
                )

            self.assertEqual(client.calls[-1], ("delete_filter", "filter-001"))


if __name__ == "__main__":
    unittest.main()
