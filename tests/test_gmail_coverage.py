import tempfile
import threading
import time
import unittest
from pathlib import Path

from src.gmail_coverage import GmailCoverageService
from src.live_gmail_client import GMAIL_READONLY_SCOPE


class FakeReadonlyGmailClient:
    def __init__(self, message_ids, messages=None, *, block=None):
        self.message_ids = list(message_ids)
        self.messages = messages or {}
        self.block = block
        self.calls = []

    def search_message_ids(self, query, max_results):
        self.calls.append(("search_message_ids", query, max_results))
        if self.block:
            self.block.wait(1)
        return self.message_ids[:max_results]

    def get_message(self, message_id):
        self.calls.append(("get_message", message_id))
        value = self.messages.get(message_id)
        if isinstance(value, Exception):
            raise value
        return value or {
            "id": message_id,
            "threadId": f"thread-{message_id}",
            "payload": {"headers": [
                {"name": "Subject", "value": f"Subject {message_id}"},
                {"name": "From", "value": "sender@example.com"},
            ]},
        }


class GmailCoverageTests(unittest.TestCase):
    def service(self, storage_dir, client, *, limit=100):
        scopes = []

        def factory(_account_id, _credentials_dir, _secret, scope):
            scopes.append(scope)
            return client

        service = GmailCoverageService(
            storage_dir,
            gmail_client_factory=factory,
            credentials_dir=storage_dir / "credentials",
            limit=limit,
        )
        return service, scopes

    def test_unseen_checked_mail_requests_sync_without_creating_unlabeled_review_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FakeReadonlyGmailClient(["new-1"])
            service, scopes = self.service(Path(temp_dir), client)

            result = service.check("founder-test")

            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["needs_review_count"], 0)
            self.assertEqual(result["requires_sync_count"], 1)
            self.assertEqual(result["review_items"], [])
            self.assertEqual(scopes, [GMAIL_READONLY_SCOPE])
            self.assertEqual(result["gmail_mutation"], "none")
            self.assertNotIn("modify", " ".join(map(str, client.calls)))

    def test_legacy_coverage_only_batch_is_treated_as_needing_real_sync(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches = storage_dir / "batches"
            batches.mkdir(parents=True)
            (batches / "gmail-coverage-old.json").write_text(
                '{"provider":"gmail","coverage_read_only":true,"items":[{"message_id":"new-1","review_state":"pending","final_labels":[],"applied_labels":[]}]}',
                encoding="utf-8",
            )
            client = FakeReadonlyGmailClient(["new-1"])
            service, _ = self.service(storage_dir, client)

            result = service.check("founder-test")

            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["requires_sync_count"], 1)
            self.assertEqual(result["needs_review_count"], 0)


    def test_known_reviewed_messages_can_produce_truthful_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches = storage_dir / "batches"
            batches.mkdir(parents=True)
            (batches / "batch.json").write_text(
                '{"provider":"gmail","items":[{"message_id":"known-1","review_state":"reviewed","final_labels":["receipts"],"subject":"Receipt","sender":"store@example.com"}]}',
                encoding="utf-8",
            )
            client = FakeReadonlyGmailClient(["known-1"])
            service, _ = self.service(storage_dir, client)

            result = service.check("founder-test")

            self.assertEqual(result["status"], "verified-clear")
            self.assertEqual(result["checked_count"], 1)
            self.assertEqual(result["needs_review_count"], 0)
            self.assertIn("Unread mail stays", result["truth_note"])

    def test_bounded_or_failed_read_is_partial_and_never_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FakeReadonlyGmailClient(["one", "two", "overflow"], {"two": RuntimeError("gone")})
            service, _ = self.service(Path(temp_dir), client, limit=2)

            result = service.check("founder-test")

            self.assertEqual(result["status"], "partial")
            self.assertFalse(result["scope_complete"])
            self.assertTrue(result["bounded"])
            self.assertEqual(result["read_failure_count"], 1)
            self.assertEqual(result["unchecked_count"], 3)

    def test_cached_unknown_metadata_avoids_repeated_message_fetch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            client = FakeReadonlyGmailClient(["new-1"])
            first, _ = self.service(storage_dir, client)
            first.check("founder-test")
            second_client = FakeReadonlyGmailClient(["new-1"])
            second, _ = self.service(storage_dir, second_client)

            result = second.check("founder-test")

            self.assertEqual(result["requires_sync_count"], 1)
            self.assertEqual(result["needs_review_count"], 0)
            self.assertEqual(second_client.calls, [("search_message_ids", "in:inbox", 101)])

    def test_unseen_metadata_reads_are_bounded_and_parallel(self):
        class ParallelClient(FakeReadonlyGmailClient):
            def __init__(self, message_ids):
                super().__init__(message_ids)
                self.lock = threading.Lock()
                self.active = 0
                self.max_active = 0

            def get_message_metadata(self, message_id):
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                time.sleep(0.02)
                try:
                    return super().get_message(message_id)
                finally:
                    with self.lock:
                        self.active -= 1

        with tempfile.TemporaryDirectory() as temp_dir:
            message_ids = [f"new-{index}" for index in range(12)]
            client = ParallelClient(message_ids)
            service, _ = self.service(Path(temp_dir), client)

            result = service.check("founder-test")

            self.assertEqual(result["requires_sync_count"], len(message_ids))
            self.assertEqual(result["needs_review_count"], 0)
            self.assertGreater(client.max_active, 1)
            self.assertLessEqual(client.max_active, 8)

    def test_concurrent_checks_share_one_provider_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gate = threading.Event()
            client = FakeReadonlyGmailClient([], block=gate)
            service, _ = self.service(Path(temp_dir), client)
            results = []
            threads = [threading.Thread(target=lambda: results.append(service.check("founder-test"))) for _ in range(2)]
            for thread in threads:
                thread.start()
            time.sleep(0.05)
            gate.set()
            for thread in threads:
                thread.join()

            self.assertEqual([call[0] for call in client.calls], ["search_message_ids"])
            self.assertEqual(len(results), 2)
            self.assertEqual(sum(bool(result.get("deduplicated")) for result in results), 1)


if __name__ == "__main__":
    unittest.main()
