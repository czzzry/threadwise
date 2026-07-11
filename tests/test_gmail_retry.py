import tempfile
import unittest
from pathlib import Path

from src.gmail_writer import MockGmailLabelClient, MockGmailLabelWriter
from src.gmail_automation import retry_failed_writes
from src.product_analytics import ProductAnalytics


class FakePostHogClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def capture(self, event: str, **kwargs) -> None:
        self.calls.append({"event": event, **kwargs})

    def shutdown(self) -> None:
        return


class MockGmailRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.client = MockGmailLabelClient(
            existing_labels={"EA/account-security": "Label_sec"},
            failing_message_ids={"gmail-005"},
        )
        self.writer = MockGmailLabelWriter(
            gmail_client=self.client,
            storage_dir=Path(self.temp_dir.name),
        )
        self.failed_item = {
            "message_id": "gmail-005",
            "review_state": "reviewed",
            "review_action": "approve",
            "final_labels": ["account-security"],
        }
        self.writer.write_reviewed_labels("founder-test-batch-1", [self.failed_item])

    def test_failed_write_status_is_distinguishable_from_success(self) -> None:
        self.assertEqual(self.writer.get_write_status("founder-test-batch-1", "gmail-005"), "failed")

    def test_retry_failed_write_succeeds_without_rereview_when_labels_are_unchanged(self) -> None:
        self.client.clear_failure("gmail-005")

        summary = self.writer.retry_failed_write("founder-test-batch-1", self.failed_item)

        self.assertEqual(summary["retried_count"], 1)
        self.assertEqual(self.writer.get_write_status("founder-test-batch-1", "gmail-005"), "applied")

    def test_retry_failed_write_is_blocked_when_approved_labels_changed(self) -> None:
        changed_item = dict(self.failed_item)
        changed_item["final_labels"] = ["reply-needed"]

        with self.assertRaisesRegex(ValueError, "requires re-review"):
            self.writer.retry_failed_write("founder-test-batch-1", changed_item)

    def test_retry_failed_write_preserves_attempt_history(self) -> None:
        self.client.clear_failure("gmail-005")
        self.writer.retry_failed_write("founder-test-batch-1", self.failed_item)

        history = self.writer.get_write_attempt_history("founder-test-batch-1", "gmail-005")

        self.assertEqual([entry["status"] for entry in history], ["failed", "applied"])

    def test_retry_failed_write_is_rejected_when_message_is_not_currently_failed(self) -> None:
        self.client.clear_failure("gmail-005")
        self.writer.retry_failed_write("founder-test-batch-1", self.failed_item)

        with self.assertRaisesRegex(ValueError, "not currently retryable"):
            self.writer.retry_failed_write("founder-test-batch-1", self.failed_item)

    def test_retry_outcome_is_captured_without_gmail_identifiers(self) -> None:
        self.client.clear_failure("gmail-005")
        posthog_client = FakePostHogClient()
        analytics = ProductAnalytics(client=posthog_client, environment="production", enabled=True)

        result = retry_failed_writes(
            "founder-test-batch-1",
            [self.failed_item],
            self.writer,
            analytics=analytics,
            analytics_distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
        )

        self.assertEqual(result.retried_successfully_count, 1)
        self.assertEqual(posthog_client.calls[0]["event"], "label write retried")
        properties = posthog_client.calls[0]["properties"]
        self.assertEqual(properties["retry_outcome"], "completed")
        self.assertEqual(properties["retry_count"], 1)
        self.assertNotIn("message_id", properties)
        self.assertNotIn("batch_id", properties)


if __name__ == "__main__":
    unittest.main()
