import json
import tempfile
import unittest
from pathlib import Path

from src.gmail_automation import (
    auto_approve_items,
    build_gmail_label_writer,
    retry_failed_writes,
    summarize_inbox_removal_candidates,
)
from src.gmail_writer import MockGmailLabelClient


class GmailAutomationTests(unittest.TestCase):
    def test_auto_approve_items_skips_already_written_auto_approved_messages(self) -> None:
        items = [
            {
                "message_id": "gmail-live-001",
                "review_state": "reviewed",
                "review_action": "auto-approve",
                "final_labels": ["shopping-order"],
                "applied_labels": ["shopping-order"],
            },
            {
                "message_id": "gmail-live-002",
                "review_state": "pending",
                "applied_labels": ["reply-needed"],
            },
            {
                "message_id": "gmail-live-003",
                "review_state": "pending",
                "applied_labels": [],
            },
        ]

        approved = auto_approve_items(items, {"gmail-live-001": "applied"})

        self.assertEqual([item["message_id"] for item in approved], ["gmail-live-002"])
        self.assertEqual(items[1]["review_state"], "reviewed")
        self.assertEqual(items[1]["review_action"], "auto-approve")
        self.assertEqual(items[1]["final_labels"], ["reply-needed"])
        self.assertEqual(items[2]["review_state"], "pending")

    def test_inbox_removal_summary_keeps_successful_writeback_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            writer = build_gmail_label_writer(MockGmailLabelClient(), storage_dir)
            self._write_json(
                storage_dir / "founder-test-batch-1_write_status.json",
                {
                    "gmail-live-001": "applied",
                    "gmail-live-002": "failed",
                    "gmail-live-003": "applied",
                },
            )
            items = [
                {"message_id": "gmail-live-001", "review_state": "reviewed", "final_labels": ["promotions"]},
                {"message_id": "gmail-live-002", "review_state": "reviewed", "final_labels": ["spam-low-value"]},
                {"message_id": "gmail-live-003", "review_state": "reviewed", "final_labels": ["reply-needed"]},
            ]

            summary = summarize_inbox_removal_candidates("founder-test-batch-1", items, writer)

            self.assertEqual(summary, (1, 1, 1))

    def test_retry_failed_writes_blocks_changed_labels_and_retries_current_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            writer = build_gmail_label_writer(MockGmailLabelClient(), storage_dir)
            self._write_json(
                storage_dir / "founder-test-batch-1_write_status.json",
                {
                    "gmail-live-001": "failed",
                    "gmail-live-002": "failed",
                    "gmail-live-003": "applied",
                },
            )
            self._write_json(
                storage_dir / "founder-test-batch-1_write_attempts.json",
                {
                    "gmail-live-001": [{"status": "failed", "final_labels": ["reply-needed"]}],
                    "gmail-live-002": [{"status": "failed", "final_labels": ["shopping-order"]}],
                    "gmail-live-003": [{"status": "applied", "final_labels": ["personal"]}],
                },
            )
            items = [
                {"message_id": "gmail-live-001", "review_state": "reviewed", "final_labels": ["reply-needed"]},
                {"message_id": "gmail-live-002", "review_state": "reviewed", "final_labels": ["account-security"]},
                {"message_id": "gmail-live-003", "review_state": "reviewed", "final_labels": ["personal"]},
            ]

            result = retry_failed_writes("founder-test-batch-1", items, writer)

            self.assertEqual([item["message_id"] for item in result.retried_items], ["gmail-live-001"])
            self.assertEqual(result.retried_successfully_count, 1)
            self.assertEqual(result.still_failed_count, 0)
            self.assertEqual(result.blocked_messages, ["Message gmail-live-002 requires re-review before retry"])

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    unittest.main()
