import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.gmail_companion_state import build_companion_runtime_payload, find_matching_item


class GmailCompanionStateTests(unittest.TestCase):
    def test_legacy_read_only_coverage_batch_never_enters_runtime_or_selected_email(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir()
            (batches_dir / "gmail-coverage-old.json").write_text(
                json.dumps(
                    {
                        "batch_id": "gmail-coverage-old",
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "coverage_read_only": True,
                        "items": [
                            {
                                "message_id": "coverage-only",
                                "review_state": "pending",
                                "final_labels": [],
                                "applied_labels": [],
                                "subject": "Coverage-only discovery",
                                "sender": "sender@example.com",
                            }
                        ],
                        "raw_messages": [],
                    }
                )
            )

            payload = build_companion_runtime_payload(
                storage_dir,
                refresh_pending=False,
            )
            selected = find_matching_item(
                storage_dir,
                {"provider": "gmail", "message_id": "coverage-only"},
            )

            self.assertEqual(payload["items"], [])
            self.assertEqual(payload["needs_attention_items"], [])
            self.assertIsNone(selected)

    def test_runtime_payload_can_skip_pending_item_reclassification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir()
            (batches_dir / "gmail-current.json").write_text(
                json.dumps(
                    {
                        "batch_id": "gmail-current",
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "items": [
                            {
                                "message_id": "gmail-current",
                                "review_state": "pending",
                                "final_labels": [],
                                "applied_labels": [],
                                "subject": "Needs review",
                            }
                        ],
                        "raw_messages": [
                            {
                                "id": "gmail-current",
                                "payload": {"headers": []},
                            }
                        ],
                    }
                )
            )

            with patch(
                "src.gmail_batch_review_store.GmailBatchReviewStore.refresh_pending_item"
            ) as refresh_pending_item:
                payload = build_companion_runtime_payload(
                    storage_dir,
                    refresh_pending=False,
                )

            refresh_pending_item.assert_not_called()
            self.assertEqual(
                [item["message_id"] for item in payload["needs_attention_items"]],
                ["gmail-current"],
            )

    def test_model_failure_is_operational_error_not_unlabeled_review_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir()
            (batches_dir / "gmail-current.json").write_text(json.dumps({
                "batch_id": "gmail-current",
                "provider": "gmail",
                "account_id": "founder-test",
                "items": [{
                    "message_id": "model-failed",
                    "review_state": "pending",
                    "final_labels": [],
                    "applied_labels": [],
                    "decision_provenance": {
                        "decision_source": "model-failure",
                        "llm_failed": True,
                    },
                }],
                "raw_messages": [],
            }))

            payload = build_companion_runtime_payload(
                storage_dir,
                refresh_pending=False,
            )

            self.assertEqual(payload["needs_attention_items"], [])
            self.assertEqual(
                [item["message_id"] for item in payload["classification_error_items"]],
                ["model-failed"],
            )
            self.assertEqual(payload["daily_summary"]["classification_error_count"], 1)

    def test_runtime_queue_is_provider_scoped_and_reconciled_to_live_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir()
            for batch_id, provider, message_id in (
                ("gmail-old", "gmail", "gmail-old"),
                ("gmail-current", "gmail", "gmail-current"),
                ("proton-current", "protonmail", "proton-current"),
            ):
                (batches_dir / f"{batch_id}.json").write_text(
                    json.dumps(
                        {
                            "batch_id": batch_id,
                            "provider": provider,
                            "account_id": provider,
                            "items": [
                                {
                                    "message_id": message_id,
                                    "review_state": "pending",
                                    "final_labels": ["personal"],
                                    "applied_labels": ["personal"],
                                }
                            ],
                            "raw_messages": [],
                        }
                    )
                )

            payload = build_companion_runtime_payload(
                storage_dir,
                provider="gmail",
                allowed_review_message_ids={"gmail-current"},
            )

            self.assertEqual(
                [item["message_id"] for item in payload["needs_attention_items"]],
                ["gmail-current"],
            )
            self.assertEqual(payload["daily_summary"]["needs_attention_count"], 1)
            self.assertEqual(payload["daily_summary"]["live_inbox_count"], 1)


if __name__ == "__main__":
    unittest.main()
