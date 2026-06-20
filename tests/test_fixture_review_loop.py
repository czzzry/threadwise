import unittest
from pathlib import Path

from src.review_loop import FixtureReviewLoop


class FixtureReviewLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent.parent / "examples" / "fixture_batches"
        self.review_loop = FixtureReviewLoop(fixtures_dir=fixtures_dir)

    def test_load_fixture_batch_orders_reply_needed_then_account_security_then_recency(self) -> None:
        review_queue = self.review_loop.load_fixture_batch("one-batch")

        self.assertEqual(
            [item["message_id"] for item in review_queue["items"]],
            ["msg-001", "msg-002", "msg-004", "msg-003"],
        )

    def test_load_fixture_batch_exposes_required_review_fields(self) -> None:
        review_queue = self.review_loop.load_fixture_batch("one-batch")

        self.assertTrue(
            {
                "message_id",
                "sender",
                "subject",
                "date",
                "interpretation",
                "applied_labels",
                "near_misses",
                "confidence_band",
            }.issubset(set(review_queue["items"][0]))
        )

    def test_review_message_approve_marks_item_reviewed_and_keeps_suggested_labels(self) -> None:
        self.review_loop.load_fixture_batch("one-batch")

        reviewed_item = self.review_loop.review_message(
            "one-batch",
            "msg-001",
            {"type": "approve"},
        )

        self.assertEqual(reviewed_item["review_state"], "reviewed")
        self.assertEqual(reviewed_item["review_action"], "approve")
        self.assertEqual(reviewed_item["final_labels"], ["reply-needed", "job-related"])

    def test_review_message_edit_can_change_labels_to_reviewed_unlabeled(self) -> None:
        self.review_loop.load_fixture_batch("one-batch")

        reviewed_item = self.review_loop.review_message(
            "one-batch",
            "msg-003",
            {"type": "edit", "final_labels": []},
        )

        self.assertEqual(reviewed_item["review_state"], "reviewed")
        self.assertEqual(reviewed_item["review_action"], "edit")
        self.assertEqual(reviewed_item["final_labels"], [])

    def test_review_message_reject_records_reviewed_outcome_with_no_applied_labels(self) -> None:
        self.review_loop.load_fixture_batch("one-batch")

        reviewed_item = self.review_loop.review_message(
            "one-batch",
            "msg-004",
            {"type": "reject"},
        )

        self.assertEqual(reviewed_item["review_state"], "reviewed")
        self.assertEqual(reviewed_item["review_action"], "reject")
        self.assertEqual(reviewed_item["final_labels"], [])

    def test_complete_batch_returns_minimal_summary_counts(self) -> None:
        self.review_loop.load_fixture_batch("one-batch")
        self.review_loop.review_message("one-batch", "msg-001", {"type": "approve"})
        self.review_loop.review_message("one-batch", "msg-003", {"type": "edit", "final_labels": []})
        self.review_loop.review_message("one-batch", "msg-004", {"type": "reject"})

        summary = self.review_loop.complete_batch("one-batch")

        self.assertEqual(summary["reviewed_count"], 3)
        self.assertEqual(summary["labeled_count"], 1)
        self.assertEqual(summary["unlabeled_count"], 2)
        self.assertEqual(summary["per_label_counts"], {"reply-needed": 1, "job-related": 1})
        self.assertEqual(summary["reviewer_label_change_count"], 2)

    def test_reload_keeps_reviewed_items_frozen_by_default(self) -> None:
        self.review_loop.load_fixture_batch("one-batch")
        self.review_loop.review_message("one-batch", "msg-001", {"type": "approve"})

        reloaded_queue = self.review_loop.load_fixture_batch("one-batch")
        reviewed_item = next(item for item in reloaded_queue["items"] if item["message_id"] == "msg-001")

        self.assertEqual(reviewed_item["review_state"], "reviewed")
        self.assertEqual(reviewed_item["review_action"], "approve")
        self.assertEqual(reviewed_item["final_labels"], ["reply-needed", "job-related"])

        with self.assertRaisesRegex(ValueError, "already been reviewed"):
            self.review_loop.review_message("one-batch", "msg-001", {"type": "reject"})

    def test_load_fixture_batch_does_not_expose_incompatible_or_over_cap_applied_labels(self) -> None:
        review_queue = self.review_loop.load_fixture_batch("one-batch")
        newsletter_item = next(item for item in review_queue["items"] if item["message_id"] == "msg-004")

        self.assertEqual(newsletter_item["applied_labels"], ["newsletter", "travel", "personal"])
        self.assertEqual(newsletter_item["near_misses"], ["promotions"])


if __name__ == "__main__":
    unittest.main()
