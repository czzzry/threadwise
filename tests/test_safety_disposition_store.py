import json
import tempfile
import unittest
from pathlib import Path

from src.local_artifacts import safety_dispositions_path
from src.memory_proposal_store import load_storage_items
from src.safety_disposition_store import SafetyDispositionStore, build_safety_disposition


class SafetyDispositionStoreTests(unittest.TestCase):
    def test_build_sender_cluster_safety_disposition_and_approve_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_dir = root / "gmail_fetch"
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Microsoft" <account-security-noreply@accountprotection.microsoft.com>',
                        "subject": "Your verification code 123456",
                        "snippet": "Use this code.",
                        "body": "Use this code.",
                        "applied_labels": ["account-security"],
                    },
                    {
                        "message_id": "g2",
                        "sender": '"Microsoft" <account-security-noreply@accountprotection.microsoft.com>',
                        "subject": "Your verification code 987654",
                        "snippet": "Use this code.",
                        "body": "Use this code.",
                        "applied_labels": ["account-security"],
                    },
                ],
            )
            items = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())["items"]
            storage_items = load_storage_items(storage_dir, "gmail")

            disposition = build_safety_disposition(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-test-batch-1",
                selected_items=[items[0]],
                scope="sender-cluster",
                disposition="legitimate-security",
                explanation="Expected verification flow.",
                storage_items=storage_items,
            )
            store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
            store.save_disposition(disposition)

            approved = store.review_disposition(disposition.id, "approved", review_notes="Looks right.")

            self.assertEqual(approved.status, "approved")
            self.assertGreaterEqual(approved.preview["match_count"], 1)

    def test_build_family_cluster_safety_disposition_matches_adjacent_spoofed_senders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            storage_dir = root / "outlookmail_fetch"
            self._write_batch(
                storage_dir,
                "founder-hotmail-batch-5",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "UPS41538",
                        "subject": "Package",
                        "snippet": "Package Delivery Notification Delivery on Hold Tracking ID# 1Z416074275839315 Confirm Address",
                        "body": "Package Delivery Notification Delivery on Hold Tracking ID# 1Z416074275839315 Confirm Address",
                        "applied_labels": [],
                    },
                    {
                        "message_id": "o2",
                        "sender": "EXPDeIivery",
                        "subject": "Fw: lD#es-09898",
                        "snippet": "Express Delivery Notice Package Delivery Suspended Tracking Number: #zm-2038425426 Confirm Address",
                        "body": "Express Delivery Notice Package Delivery Suspended Tracking Number: #zm-2038425426 Confirm Address",
                        "applied_labels": [],
                    },
                    {
                        "message_id": "o3",
                        "sender": "CA.77",
                        "subject": "Order",
                        "snippet": "UPS You Tracking Order:#eJy-09973260 You have (1) message from us. CONFIRM NOW!",
                        "body": "UPS You Tracking Order:#eJy-09973260 You have (1) message from us. CONFIRM NOW!",
                        "applied_labels": [],
                    },
                ],
            )
            items = json.loads((storage_dir / "batches" / "founder-hotmail-batch-5.json").read_text())["items"]
            storage_items = load_storage_items(storage_dir, "outlookmail")

            disposition = build_safety_disposition(
                provider="outlookmail",
                account_id="founder-hotmail",
                source_batch_id="founder-hotmail-batch-5",
                selected_items=[items[0], items[1]],
                scope="family-cluster",
                disposition="phishing",
                explanation="Spoofed shipping notices asking the founder to confirm delivery details.",
                storage_items=storage_items,
            )

            self.assertEqual(disposition.scope, "family-cluster")
            self.assertIn("delivery", disposition.match_signals["content_terms"])
            self.assertIn("confirm address", disposition.match_signals["content_terms"])
            self.assertGreaterEqual(disposition.preview["match_count"], 3)

    def test_reject_disposition_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir) / "gmail_fetch"
            store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
            disposition = build_safety_disposition(
                provider="gmail",
                account_id="founder-test",
                source_batch_id="founder-test-batch-1",
                selected_items=[
                    {
                        "message_id": "g1",
                        "sender": '"Vendor" <vendor@example.com>',
                        "subject": "Urgent invoice",
                        "date": "2026-06-28T00:00:00Z",
                        "final_labels": [],
                    }
                ],
                scope="sender",
                disposition="phishing",
                explanation="Unexpected sender.",
                storage_items=[],
            )
            store.save_disposition(disposition)

            rejected = store.review_disposition(disposition.id, "rejected", review_notes="Too little evidence.")

            self.assertEqual(rejected.status, "rejected")

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        items: list[dict],
    ) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "items": items,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
