import json
import tempfile
import unittest
from pathlib import Path

from src.gmail_fetcher import GmailSearchBatchFetcher, MockGmailBatchFetcher, MockGmailClient
from src.review_loop import FixtureReviewLoop


class MockGmailBatchFetcherTests(unittest.TestCase):
    def setUp(self) -> None:
        fixture_path = (
            Path(__file__).resolve().parent.parent / "examples" / "gmail_api" / "mock_inbox_payloads.json"
        )
        fixture = json.loads(fixture_path.read_text())

        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.client = MockGmailClient(gmail_payloads=fixture["messages"])
        self.fetcher = MockGmailBatchFetcher(
            gmail_client=self.client,
            storage_dir=Path(self.temp_dir.name),
        )
        self.review_loop = FixtureReviewLoop(fixtures_dir=Path(self.temp_dir.name))

    def test_fetch_gmail_batch_normalizes_representative_payloads_into_review_ready_items(self) -> None:
        review_queue = self.fetcher.fetch_gmail_batch("founder-test", batch_size=4)

        self.assertEqual(review_queue["batch_id"], "founder-test-batch-1")
        self.assertTrue(review_queue["items"])
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

    def test_fetch_gmail_batch_returns_only_bounded_inbox_messages(self) -> None:
        review_queue = self.fetcher.fetch_gmail_batch("founder-test", batch_size=3)

        self.assertEqual(len(review_queue["items"]), 3)
        self.assertEqual(
            [item["message_id"] for item in review_queue["items"]],
            ["gmail-001", "gmail-002", "gmail-003"],
        )

    def test_fetch_gmail_batch_orders_messages_for_review(self) -> None:
        review_queue = self.fetcher.fetch_gmail_batch("founder-test", batch_size=4)

        self.assertEqual(
            [item["message_id"] for item in review_queue["items"]],
            ["gmail-001", "gmail-002", "gmail-004", "gmail-003"],
        )

    def test_fetch_gmail_batch_skips_processed_message_ids_by_default(self) -> None:
        first_batch = self.fetcher.fetch_gmail_batch("founder-test", batch_size=2)
        self.fetcher.mark_processed(first_batch["batch_id"], ["gmail-001"])

        second_batch = self.fetcher.fetch_gmail_batch("founder-test", batch_size=4)

        self.assertNotIn("gmail-001", [item["message_id"] for item in second_batch["items"]])

    def test_fetch_gmail_batch_stores_message_content_and_review_metadata_in_local_storage(self) -> None:
        review_queue = self.fetcher.fetch_gmail_batch("founder-test", batch_size=2)

        stored_batch_path = Path(self.temp_dir.name) / "batches" / f"{review_queue['batch_id']}.json"
        stored_batch = json.loads(stored_batch_path.read_text())

        self.assertEqual(stored_batch["batch_id"], review_queue["batch_id"])
        self.assertEqual(stored_batch["items"][0]["message_id"], review_queue["items"][0]["message_id"])
        self.assertIn("snippet", stored_batch["raw_messages"][0])

    def test_fetch_gmail_batch_persists_richer_normalized_context_from_payload_parts(self) -> None:
        client = MockGmailClient(
            gmail_payloads=[
                {
                    "id": "gmail-live-010",
                    "threadId": "thread-010",
                    "internalDate": "1718784000000",
                    "labelIds": ["INBOX"],
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
            ]
        )
        fetcher = MockGmailBatchFetcher(
            gmail_client=client,
            storage_dir=Path(self.temp_dir.name),
        )

        review_queue = fetcher.fetch_gmail_batch("founder-test", batch_size=1)

        item = review_queue["items"][0]
        self.assertEqual(item["snippet"], "Your single-use code is 123456.")
        self.assertIn("Only enter this code on an official website.", item["body"])

    def test_fetch_gmail_batch_flows_through_existing_review_loop(self) -> None:
        review_queue = self.fetcher.fetch_gmail_batch("founder-test", batch_size=4)
        self.review_loop.load_review_queue(review_queue)

        reviewed_item = self.review_loop.review_message(review_queue["batch_id"], "gmail-001", {"type": "approve"})

        self.assertEqual(reviewed_item["review_state"], "reviewed")
        self.assertEqual(reviewed_item["review_action"], "approve")
        self.assertEqual(reviewed_item["final_labels"], ["reply-needed", "job-related"])

    def test_fetch_gmail_batch_uses_live_style_gmail_metadata_to_suggest_useful_labels(self) -> None:
        client = MockGmailClient(
            gmail_payloads=[
                {
                    "id": "gmail-live-001",
                    "internalDate": "1718784000000",
                    "snippet": "Free shipping this weekend. Hurry, while supplies last.",
                    "labelIds": ["INBOX", "CATEGORY_PROMOTIONS", "UNREAD"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                            {"name": "Subject", "value": "Father's Day Sale is live"},
                            {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                            {
                                "name": "List-Unsubscribe",
                                "value": "<mailto:unsubscribe@example.com>, <https://example.com/unsub>",
                            },
                        ]
                    },
                }
            ]
        )
        fetcher = MockGmailBatchFetcher(
            gmail_client=client,
            storage_dir=Path(self.temp_dir.name),
        )

        review_queue = fetcher.fetch_gmail_batch("founder-test", batch_size=1)

        self.assertEqual(review_queue["items"][0]["applied_labels"], ["spam-low-value"])
        self.assertEqual(
            review_queue["items"][0]["interpretation"],
            "Promotional marketing email that looks low priority to review.",
        )

    def test_fetch_gmail_batch_performs_no_gmail_writeback_actions(self) -> None:
        self.fetcher.fetch_gmail_batch("founder-test", batch_size=2)

        self.assertEqual(
            self.client.calls,
            [
                ("list_messages", ("INBOX",), 2),
                ("get_message", "gmail-001"),
                ("get_message", "gmail-002"),
            ],
        )

    def test_search_batch_uses_the_explicit_query_and_reprocesses_matching_mail(self) -> None:
        class SearchClient(MockGmailClient):
            def search_message_ids(self, query: str, max_results: int) -> list[str]:
                self.calls.append(("search_message_ids", query, max_results))
                return ["gmail-001", "gmail-002"][:max_results]

        storage_dir = Path(self.temp_dir.name)
        (storage_dir / "processed_message_ids.json").write_text(
            json.dumps(["founder-test:gmail-001"])
        )
        client = SearchClient(list(self.client._gmail_payloads.values()))
        fetcher = GmailSearchBatchFetcher(
            gmail_client=client,
            storage_dir=storage_dir,
            query="-in:inbox -label:EA/LowValue",
        )

        review_queue = fetcher.fetch_gmail_batch("founder-test", batch_size=2)

        self.assertEqual(
            client.calls[:3],
            [
                ("search_message_ids", "-in:inbox -label:EA/LowValue", 2),
                ("get_message", "gmail-001"),
                ("get_message", "gmail-002"),
            ],
        )
        self.assertEqual({item["message_id"] for item in review_queue["items"]}, {"gmail-001", "gmail-002"})


if __name__ == "__main__":
    unittest.main()
