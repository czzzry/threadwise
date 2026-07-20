import unittest
from pathlib import Path

from src.companion_teaching_workflow import TeachingWriteRequest
from src.gmail_teaching_adapter import GmailTeachingAdapter


class GmailTeachingAdapterTests(unittest.TestCase):
    def test_preview_backfill_exposes_semantic_query_without_opening_gmail(self) -> None:
        adapter = GmailTeachingAdapter(
            Path("/tmp/threadwise-test"),
            credentials_dir=Path("/tmp/threadwise-credentials"),
            client_secret_path=None,
            gmail_client_factory=lambda *args: self.fail("Gmail should not be opened"),
        )

        result = adapter.preview_backfill(
            {
                "selected_account_id": "",
                "selected_subject": "Your order shipped",
                "selected_sender": "orders@amazon.example",
                "semantic_rule": {
                    "sender": "orders@amazon.example",
                    "rule_type": "cross-sender-semantic",
                    "include_families": ["orders"],
                    "exclude_families": ["account-security", "privacy-legal", "promotions"],
                },
            }
        )

        self.assertFalse(result["available"])
        self.assertIn('subject:"order confirmation"', result["query"])
        self.assertIn("subject:shipment", result["query"])
        self.assertIn('-subject:"account security"', result["query"])
        self.assertIn('-subject:"privacy policy"', result["query"])
        self.assertIn("-subject:promotion", result["query"])
        self.assertNotIn("from:orders@amazon.example", result["query"])

    def test_apply_future_rule_short_circuits_before_provider_access(self) -> None:
        adapter = GmailTeachingAdapter(
            Path("/tmp/threadwise-test"),
            credentials_dir=Path("/tmp/threadwise-credentials"),
            client_secret_path=None,
            gmail_client_factory=lambda *args: self.fail("Gmail should not be opened"),
        )

        result = adapter.apply(_request(mode="save-future-rule"))

        self.assertEqual(result["mode"], "no-gmail-write-future-rule-only")
        self.assertEqual(result["messages_written"], 0)

    def test_apply_reports_client_initialization_failure_through_one_interface(self) -> None:
        adapter = GmailTeachingAdapter(
            Path("/tmp/threadwise-test"),
            credentials_dir=Path("/tmp/threadwise-credentials"),
            client_secret_path=None,
            gmail_client_factory=lambda *args: (_ for _ in ()).throw(RuntimeError("offline")),
        )

        result = adapter.apply(_request())

        self.assertEqual(result["mode"], "gmail-write-failed")
        self.assertEqual(result["error"], "offline")


def _request(*, mode: str = "current-only") -> TeachingWriteRequest:
    return TeachingWriteRequest(
        account_id="founder-test",
        current_message_id="message-1",
        mode=mode,
        preview_matches=[],
        semantic_rule={"target_label": "reply-needed"},
        current_subject="Need a response",
        current_sender="boss@example.com",
        included_message_ids=frozenset(),
    )


if __name__ == "__main__":
    unittest.main()
