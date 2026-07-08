import json
import tempfile
import unittest
from pathlib import Path

from src.gmail_automation import (
    auto_approve_items,
    build_gmail_label_writer,
    retry_failed_writes,
    run_daily_gmail_automation,
    summarize_inbox_removal_candidates,
)
from src.gmail_writer import MockGmailLabelClient


class FakeDailyRunGmailClient(MockGmailLabelClient):
    def __init__(self, messages: list[dict]) -> None:
        super().__init__()
        self._messages = {message["id"]: message for message in messages}

    def list_messages(self, label_ids: tuple[str, ...], max_results: int) -> list[str]:
        self.calls.append(("list_messages", label_ids, max_results))
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        self.calls.append(("get_message", message_id))
        return self._messages[message_id]


class FakeAttentionModelClient:
    def __init__(self) -> None:
        self.compact_payloads: list[list[dict]] = []
        self.model_metadata = {"provider": "fake", "name": "fake-attention-model"}

    def evaluate_gmail_attention_batch(self, payloads: list[dict]) -> dict:
        self.compact_payloads.append(payloads)
        return {
            "model": self.model_metadata,
            "usage": {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0},
            "items": [
                {
                    "message_id": payloads[0]["message_id"],
                    "level": "needs_attention_now",
                    "category": "travel",
                    "reason": "Flight departs tomorrow.",
                    "evidence": "The message includes a concrete departure time.",
                },
                {
                    "message_id": payloads[1]["message_id"],
                    "level": "possible_attention",
                    "category": "bill_due",
                    "reason": "Stored bill may still need payment.",
                    "evidence": "The lookback message contains payment language.",
                },
            ],
        }


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

    def test_daily_run_writes_attention_from_latest_batch_and_stored_lookback_without_extra_gmail_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_json(
                storage_dir / "batches" / "founder-test-batch-1.json",
                {
                    "batch_id": "founder-test-batch-1",
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "items": [
                        {
                            "source": "gmail",
                            "account_id": "founder-test",
                            "message_id": "lookback-bill",
                            "thread_id": "thread-lookback-bill",
                            "sender": "Utility <billing@example.com>",
                            "subject": "Payment due",
                            "date": "2026-06-30T09:00:00Z",
                            "snippet": "Your payment is due soon.",
                            "body": "Your payment is due soon.",
                            "applied_labels": ["finance"],
                            "final_labels": ["finance"],
                            "review_state": "reviewed",
                        }
                    ],
                },
            )
            gmail_client = FakeDailyRunGmailClient(
                [
                    {
                        "id": "latest-order",
                        "threadId": "thread-latest-order",
                        "internalDate": "1782883200000",
                        "snippet": "Your package has shipped.",
                        "labelIds": ["INBOX", "CATEGORY_UPDATES"],
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "\"Amazon.de\" <versandbestaetigung@amazon.de>"},
                                {"name": "Subject", "value": "Dispatched: 'GEWAGE CO2 Bicycle Pump -...'"},
                                {"name": "Date", "value": "Wed, 01 Jul 2026 08:00:00 +0000"},
                            ]
                        },
                    }
                ]
            )
            attention_model = FakeAttentionModelClient()

            result = run_daily_gmail_automation(
                account_id="founder-test",
                batch_size=1,
                storage_dir=storage_dir,
                gmail_client=gmail_client,
                attention_model_client=attention_model,
                attention_max_evaluated_messages=2,
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.report["batch_id"], "founder-test-batch-2")
            self.assertEqual(
                [payload["message_id"] for payload in attention_model.compact_payloads[0]],
                ["latest-order", "lookback-bill"],
            )
            self.assertEqual(result.report["attention"]["evaluated_message_count"], 2)
            self.assertEqual(result.report["attention"]["grouped_counts"]["needs_attention_now"], 1)
            self.assertEqual(result.report["attention"]["grouped_counts"]["possible_attention"], 1)
            self.assertEqual(
                result.report["attention"]["lookback_window"]["stored_lookback_batch_ids"],
                ["founder-test-batch-1"],
            )
            self.assertEqual(
                [call[0] for call in gmail_client.calls],
                ["list_messages", "get_message", "get_or_create_label", "replace_threadwise_labels"],
            )
            saved_report = json.loads(
                (storage_dir / "reports" / "founder-test-batch-2_daily_report.json").read_text()
            )
            self.assertEqual(saved_report["attention"], result.report["attention"])

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    unittest.main()
