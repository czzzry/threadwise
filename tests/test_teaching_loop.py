import json
import tempfile
import unittest
from pathlib import Path

from src.teaching_loop import (
    apply_sidebar_teaching,
    build_sidebar_teach_preview,
    load_items_for_gmail_write_through,
)


class TeachingLoopTests(unittest.TestCase):
    def test_preview_reports_matching_existing_emails_without_app_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "LinkedIn <messages-noreply@linkedin.com>",
                        "subject": "Sophie Riding sent you a message",
                        "snippet": "Let's catch up",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "LinkedIn <messages-noreply@linkedin.com>",
                        "subject": "Sean commented on a post",
                        "snippet": "New activity",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "messages-noreply@linkedin.com",
                    "subject": "Sophie Riding sent you a message",
                },
                target_label="personal",
                note="LinkedIn direct messages from real people should be personal.",
                scope="sender",
            )

            self.assertEqual(preview["selected_message_id"], "gmail-live-001")
            self.assertEqual(preview["impact"]["matching_existing_count"], 1)
            self.assertEqual(preview["impact"]["matching_existing_examples"][0]["message_id"], "gmail-live-002")
            self.assertEqual(preview["impact"]["matching_existing_examples"][0]["labels_after"], ["personal"])

    def test_apply_matching_existing_relabels_current_and_matches_and_saves_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Application portal reminder",
                        "snippet": "Reminder",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = apply_sidebar_teaching(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                mode="matching-existing",
            )

            batch_one = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            batch_two = json.loads((storage_dir / "batches" / "founder-test-batch-2.json").read_text())
            rules = json.loads((storage_dir / "teachable_classification_rules.json").read_text())

            self.assertIn("rewrote 1 matching stored emails", result["acknowledgment"])
            self.assertEqual(result["matched_existing_count"], 1)
            self.assertEqual(batch_one["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(batch_two["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(rules["rules"][0]["label"], "job-related")
            self.assertEqual(result["current"]["message_id"], "gmail-live-001")
            self.assertEqual([match["message_id"] for match in result["preview_matches"]], ["gmail-live-001", "gmail-live-002"])

    def test_write_through_selection_keeps_future_only_to_current_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {"message_id": "gmail-live-001", "final_labels": ["job-related"]},
                    {"message_id": "gmail-live-002", "final_labels": ["job-related"]},
                ],
            )

            selected = load_items_for_gmail_write_through(
                storage_dir,
                selected_message_id="gmail-live-001",
                mode="future-only",
                preview_matches=[{"message_id": "gmail-live-002"}],
            )

            self.assertEqual([item["message_id"] for item in selected["founder-test-batch-1"]], ["gmail-live-001"])

    def _write_batch(self, storage_dir: Path, batch_id: str, items: list[dict]) -> None:
        batch_dir = storage_dir / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "items": items,
                    "raw_messages": [],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
