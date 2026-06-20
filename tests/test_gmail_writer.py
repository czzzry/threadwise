import tempfile
import unittest
from pathlib import Path

from src.gmail_writer import MockGmailLabelClient, MockGmailLabelWriter


class MockGmailLabelWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.client = MockGmailLabelClient(
            existing_labels={
                "EA/reply-needed": "Label_1",
                "Personal/Keep": "Label_keep",
            },
            failing_message_ids={"gmail-005"},
        )
        self.writer = MockGmailLabelWriter(
            gmail_client=self.client,
            storage_dir=Path(self.temp_dir.name),
        )
        self.reviewed_items = [
            {
                "message_id": "gmail-001",
                "review_state": "reviewed",
                "review_action": "approve",
                "final_labels": ["reply-needed", "job-related"],
            },
            {
                "message_id": "gmail-002",
                "review_state": "reviewed",
                "review_action": "edit",
                "final_labels": [],
            },
            {
                "message_id": "gmail-003",
                "review_state": "reviewed",
                "review_action": "reject",
                "final_labels": [],
            },
            {
                "message_id": "gmail-004",
                "review_state": "pending",
                "review_action": None,
                "final_labels": None,
            },
            {
                "message_id": "gmail-005",
                "review_state": "reviewed",
                "review_action": "approve",
                "final_labels": ["account-security"],
            },
        ]

    def test_map_reviewed_labels_uses_ea_namespace(self) -> None:
        gmail_names = self.writer.map_reviewed_labels(["reply-needed", "job-related"])

        self.assertEqual(gmail_names, ["EA/reply-needed", "EA/job-related"])

    def test_write_reviewed_labels_creates_missing_namespaced_labels_before_apply(self) -> None:
        self.writer.write_reviewed_labels("founder-test-batch-1", self.reviewed_items[:1])

        self.assertIn("EA/job-related", self.client.labels)
        self.assertEqual(
            self.client.calls[:2],
            [
                ("get_or_create_label", "EA/reply-needed"),
                ("get_or_create_label", "EA/job-related"),
            ],
        )

    def test_write_reviewed_labels_applies_labels_only_for_reviewed_messages_with_labels(self) -> None:
        self.writer.write_reviewed_labels("founder-test-batch-1", self.reviewed_items)

        self.assertIn(
            ("apply_labels", "gmail-001", ["Label_1", self.client.labels["EA/job-related"]]),
            self.client.calls,
        )
        self.assertNotIn(("apply_labels", "gmail-002", []), self.client.calls)
        self.assertNotIn(("apply_labels", "gmail-003", []), self.client.calls)
        self.assertNotIn(("apply_labels", "gmail-004", []), self.client.calls)

    def test_write_reviewed_labels_skips_rejected_and_unlabeled_outcomes(self) -> None:
        self.writer.write_reviewed_labels("founder-test-batch-1", self.reviewed_items[1:3])

        self.assertEqual(
            [call for call in self.client.calls if call[0] == "apply_labels"],
            [],
        )

    def test_write_reviewed_labels_records_per_message_success_and_failure_status(self) -> None:
        self.writer.write_reviewed_labels("founder-test-batch-1", [self.reviewed_items[0], self.reviewed_items[4]])

        self.assertEqual(
            self.writer.get_write_status("founder-test-batch-1", "gmail-001"),
            "applied",
        )
        self.assertEqual(
            self.writer.get_write_status("founder-test-batch-1", "gmail-005"),
            "failed",
        )

    def test_write_reviewed_labels_does_not_alter_non_agent_gmail_labels(self) -> None:
        self.writer.write_reviewed_labels("founder-test-batch-1", [self.reviewed_items[0]])

        self.assertEqual(self.client.labels["Personal/Keep"], "Label_keep")
        self.assertNotIn(("remove_labels", "gmail-001", ["Label_keep"]), self.client.calls)

    def test_write_reviewed_labels_returns_visible_batch_write_summary(self) -> None:
        summary = self.writer.write_reviewed_labels("founder-test-batch-1", self.reviewed_items)

        self.assertEqual(summary["batch_id"], "founder-test-batch-1")
        self.assertEqual(summary["applied_count"], 1)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["skipped_count"], 3)

    def test_remove_inbox_for_low_value_messages_only_touches_eligible_messages_after_applied_writeback(self) -> None:
        self.writer.write_reviewed_labels("founder-test-batch-1", [self.reviewed_items[0]])
        reviewed_items = [
            {
                "message_id": "gmail-001",
                "review_state": "reviewed",
                "review_action": "approve",
                "final_labels": ["promotions"],
            },
            {
                "message_id": "gmail-002",
                "review_state": "reviewed",
                "review_action": "approve",
                "final_labels": ["spam-low-value"],
            },
            {
                "message_id": "gmail-003",
                "review_state": "reviewed",
                "review_action": "approve",
                "final_labels": ["reply-needed"],
            },
        ]

        summary = self.writer.remove_inbox_for_low_value_messages("founder-test-batch-1", reviewed_items)

        self.assertIn(("remove_inbox_label", "gmail-001"), self.client.calls)
        self.assertNotIn(("remove_inbox_label", "gmail-002"), self.client.calls)
        self.assertEqual(self.writer.get_inbox_removal_status("founder-test-batch-1", "gmail-001"), "applied")
        self.assertEqual(self.writer.get_inbox_removal_status("founder-test-batch-1", "gmail-002"), "skipped")
        self.assertEqual(self.writer.get_inbox_removal_status("founder-test-batch-1", "gmail-003"), "ineligible")
        self.assertEqual(summary["applied_count"], 1)
        self.assertEqual(summary["skipped_count"], 1)
        self.assertEqual(summary["ineligible_count"], 1)


if __name__ == "__main__":
    unittest.main()
