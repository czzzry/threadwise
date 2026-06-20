import json
import tempfile
import unittest
from pathlib import Path

from src.stored_batch_review_store import StoredBatchReviewStore


class StoredBatchReviewStoreTests(unittest.TestCase):
    def test_to_review_queue_refreshes_context_from_raw_messages_and_pending_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            batch_path = batches_dir / "founder-test-batch-1.json"
            batch_path.write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "raw_messages": [
                            {
                                "id": "gmail-live-001",
                                "internalDate": "1718784000000",
                                "snippet": "Your single-use code is 123456.",
                                "payload": {
                                    "mimeType": "multipart/alternative",
                                    "headers": [
                                        {"name": "From", "value": "Microsoft <account@example.com>"},
                                        {"name": "Subject", "value": "Your single-use code"},
                                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                                    ],
                                    "parts": [
                                        {
                                            "mimeType": "text/plain",
                                            "body": {
                                                "data": "SGkgQ2V6YXJ5LAoKWW91ciBzaW5nbGUtdXNlIGNvZGUgaXMgMTIzNDU2LgpPbmx5IGVudGVyIHRoaXMgY29kZSBvbiBhbiBvZmZpY2lhbCB3ZWJzaXRlLg=="
                                            },
                                        }
                                    ],
                                },
                            }
                        ],
                        "items": [
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-001",
                                "sender": "Microsoft <account@example.com>",
                                "subject": "Your single-use code",
                                "date": "2024-06-19T08:00:00Z",
                                "interpretation": "Informational message with no confident category.",
                                "applied_labels": [],
                                "near_misses": [],
                                "confidence_band": "low",
                                "review_state": "pending",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            store = StoredBatchReviewStore(storage_dir)
            review_queue = store.to_review_queue(store.load_batch("founder-test-batch-1"))

            item = review_queue["items"][0]
            self.assertEqual(item["applied_labels"], ["account-security"])
            self.assertEqual(item["snippet"], "Your single-use code is 123456.")
            self.assertIn("Only enter this code on an official website.", item["body"])
            self.assertEqual(item["review_state"], "pending")

    def test_to_review_queue_preserves_reviewed_items_while_refreshing_other_pending_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            batch_path = batches_dir / "founder-test-batch-1.json"
            batch_path.write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "raw_messages": [
                            {
                                "id": "gmail-live-001",
                                "internalDate": "1718784000000",
                                "snippet": "Please reply today.",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Manager <boss@example.com>"},
                                        {"name": "Subject", "value": "Need your approval today"},
                                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                                    ]
                                },
                                "labelIds": ["INBOX"],
                            },
                            {
                                "id": "gmail-live-002",
                                "internalDate": "1718787600000",
                                "snippet": "Free shipping this weekend.",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                                        {"name": "Subject", "value": "Father's Day Sale is live"},
                                        {"name": "Date", "value": "Wed, 19 Jun 2024 09:00:00 +0000"},
                                        {
                                            "name": "List-Unsubscribe",
                                            "value": "<mailto:unsubscribe@example.com>, <https://example.com/unsub>",
                                        },
                                    ]
                                },
                                "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
                            },
                        ],
                        "items": [
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-001",
                                "sender": "Manager <boss@example.com>",
                                "subject": "Need your approval today",
                                "date": "2024-06-19T08:00:00Z",
                                "interpretation": "A manager asks for a same-day approval.",
                                "applied_labels": ["reply-needed", "job-related"],
                                "near_misses": [],
                                "confidence_band": "high",
                                "review_state": "reviewed",
                                "review_action": "approve",
                                "final_labels": ["reply-needed", "job-related"],
                            },
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-002",
                                "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                                "subject": "Father's Day Sale is live",
                                "date": "2024-06-19T09:00:00Z",
                                "interpretation": "Informational message with no confident category.",
                                "applied_labels": ["promotions", "spam-low-value"],
                                "near_misses": [],
                                "confidence_band": "low",
                                "review_state": "pending",
                            },
                        ],
                    },
                    indent=2,
                )
            )

            store = StoredBatchReviewStore(storage_dir)
            review_queue = store.to_review_queue(store.load_batch("founder-test-batch-1"))

            reviewed_item = next(item for item in review_queue["items"] if item["message_id"] == "gmail-live-001")
            pending_item = next(item for item in review_queue["items"] if item["message_id"] == "gmail-live-002")

            self.assertEqual(reviewed_item["applied_labels"], ["reply-needed", "job-related"])
            self.assertEqual(reviewed_item["review_state"], "reviewed")
            self.assertEqual(pending_item["applied_labels"], ["spam-low-value"])
            self.assertEqual(pending_item["review_state"], "pending")

    def test_to_review_queue_seeds_trusted_personal_senders_from_repeated_reviewed_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)

            (batches_dir / "founder-test-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "raw_messages": [],
                        "items": [
                            {
                                "message_id": "gmail-old-001",
                                "sender": "Sophie Riding <sophielyneriding@gmail.com>",
                                "subject": "Old note",
                                "date": "2024-06-19T08:00:00Z",
                                "applied_labels": [],
                                "near_misses": [],
                                "confidence_band": "low",
                                "interpretation": "Informational message with no confident category.",
                                "review_state": "reviewed",
                                "review_action": "edit",
                                "final_labels": ["personal"],
                            },
                            {
                                "message_id": "gmail-old-002",
                                "sender": "Sophie Riding <sophielyneriding@gmail.com>",
                                "subject": "Another old note",
                                "date": "2024-06-20T08:00:00Z",
                                "applied_labels": [],
                                "near_misses": [],
                                "confidence_band": "low",
                                "interpretation": "Informational message with no confident category.",
                                "review_state": "reviewed",
                                "review_action": "edit",
                                "final_labels": ["personal"],
                            },
                        ],
                    },
                    indent=2,
                )
            )
            (batches_dir / "founder-test-batch-2.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-2",
                        "account_id": "founder-test",
                        "raw_messages": [
                            {
                                "id": "gmail-live-003",
                                "internalDate": "1718956800000",
                                "snippet": "A few pictures from the weekend.",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Sophie Riding <sophielyneriding@gmail.com>"},
                                        {"name": "Subject", "value": "Trip photos"},
                                        {"name": "Date", "value": "Fri, 21 Jun 2024 08:00:00 +0000"},
                                    ]
                                },
                                "labelIds": ["INBOX"],
                            }
                        ],
                        "items": [
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-003",
                                "sender": "Sophie Riding <sophielyneriding@gmail.com>",
                                "subject": "Trip photos",
                                "date": "2024-06-21T08:00:00Z",
                                "interpretation": "Informational message with no confident category.",
                                "applied_labels": [],
                                "near_misses": [],
                                "confidence_band": "low",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            store = StoredBatchReviewStore(storage_dir)
            review_queue = store.to_review_queue(store.load_batch("founder-test-batch-2"))

            self.assertEqual(review_queue["items"][0]["applied_labels"], ["personal"])
            trusted_store = json.loads((storage_dir / "trusted_personal_senders.json").read_text())
            self.assertEqual(
                trusted_store["trusted_personal_senders"][0]["address"],
                "sophielyneriding@gmail.com",
            )


if __name__ == "__main__":
    unittest.main()
