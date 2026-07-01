import json
import tempfile
import unittest
from pathlib import Path

from src.gmail_attention import evaluate_gmail_attention


class FakeAttentionModelClient:
    def __init__(self, compact_items: list[dict], full_body_items: dict[str, dict] | None = None) -> None:
        self.compact_items = compact_items
        self.full_body_items = full_body_items or {}
        self.compact_payloads: list[list[dict]] = []
        self.full_body_payloads: list[dict] = []
        self.model_metadata = {"provider": "fake", "name": "fake-attention-model"}

    def evaluate_gmail_attention_batch(self, payloads: list[dict]) -> dict:
        self.compact_payloads.append(payloads)
        return {
            "items": self.compact_items,
            "model": self.model_metadata,
            "usage": {"input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0},
        }

    def evaluate_gmail_attention_full_body(self, payload: dict) -> dict:
        self.full_body_payloads.append(payload)
        return self.full_body_items[payload["message_id"]]


class FailingAttentionModelClient:
    model_metadata = {"provider": "fake", "name": "failing-attention-model"}

    def evaluate_gmail_attention_batch(self, payloads: list[dict]) -> dict:
        raise RuntimeError("model unavailable")


class GmailAttentionTests(unittest.TestCase):
    def test_evaluator_uses_latest_batch_then_bounded_stored_lookback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    self._item("lookback-1", "Older bill", body="Please pay this bill."),
                    self._item("lookback-2", "Older appointment", body="Appointment reminder."),
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                [
                    self._item("latest-1", "Flight tomorrow", body="Your flight departs tomorrow at 8 AM."),
                    self._item("latest-2", "Package shipped", body="Package shipped."),
                ],
            )
            model = FakeAttentionModelClient(
                compact_items=[
                    {
                        "message_id": "latest-1",
                        "level": "needs_attention_now",
                        "category": "travel",
                        "reason": "Flight departs tomorrow.",
                        "evidence": "Departure time appears in the message.",
                    },
                    {
                        "message_id": "latest-2",
                        "level": "not_attention",
                        "category": "",
                        "reason": "Routine shipping update.",
                        "evidence": "No action requested.",
                    },
                    {
                        "message_id": "lookback-1",
                        "level": "possible_attention",
                        "category": "bill_due",
                        "reason": "Bill may require payment.",
                        "evidence": "Payment language appears in the message.",
                    },
                ]
            )

            attention = evaluate_gmail_attention(
                storage_dir=storage_dir,
                latest_batch_id="founder-test-batch-2",
                model_client=model,
                max_evaluated_messages=3,
            )

            self.assertEqual(
                [payload["message_id"] for payload in model.compact_payloads[0]],
                ["latest-1", "latest-2", "lookback-1"],
            )
            self.assertEqual(attention["evaluated_message_count"], 3)
            self.assertEqual(attention["lookback_window"]["stored_lookback_batch_ids"], ["founder-test-batch-1"])
            self.assertEqual(attention["grouped_counts"]["needs_attention_now"], 1)
            self.assertEqual(attention["grouped_counts"]["possible_attention"], 1)
            self.assertEqual(attention["grouped_counts"]["not_attention"], 1)
            self.assertEqual(attention["items"][0]["gmail_mutation"], "none")

    def test_compact_payloads_exclude_full_body_and_full_body_second_pass_is_limited_to_high_consequence_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            long_body = "Security alert. " + ("Sensitive account details. " * 80)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    self._item("security-1", "Confirm account activity", body=long_body),
                    self._item("job-1", "Book your interview", body="Use this link to schedule your interview this week."),
                    self._item("newsletter-1", "Weekly update", body="A newsletter with unclear value."),
                ],
            )
            model = FakeAttentionModelClient(
                compact_items=[
                    {
                        "message_id": "security-1",
                        "level": "insufficient_context",
                        "category": "security",
                        "reason": "Could be account risk, but compact context is not enough.",
                        "evidence": "Security alert language appears.",
                    },
                    {
                        "message_id": "job-1",
                        "level": "insufficient_context",
                        "category": "job_opportunity",
                        "reason": "Could be an interview scheduling action.",
                        "evidence": "Mentions booking an interview.",
                    },
                    {
                        "message_id": "newsletter-1",
                        "level": "insufficient_context",
                        "category": "",
                        "reason": "Unclear newsletter.",
                        "evidence": "No concrete deadline or consequence.",
                    },
                ],
                full_body_items={
                    "security-1": {
                        "message_id": "security-1",
                        "level": "needs_attention_now",
                        "category": "security",
                        "reason": "Account sign-in needs review.",
                        "evidence": "Full body says to verify activity today.",
                    },
                    "job-1": {
                        "message_id": "job-1",
                        "level": "needs_attention_now",
                        "category": "job_opportunity",
                        "reason": "Interview scheduling link needs action.",
                        "evidence": "Full body asks the founder to book an interview slot this week.",
                    },
                },
            )

            attention = evaluate_gmail_attention(
                storage_dir=storage_dir,
                latest_batch_id="founder-test-batch-1",
                model_client=model,
            )

            compact_payload = model.compact_payloads[0][0]
            self.assertNotIn("body", compact_payload)
            self.assertLessEqual(len(compact_payload["body_excerpt"]), 500)
            self.assertEqual([payload["message_id"] for payload in model.full_body_payloads], ["security-1", "job-1"])
            self.assertIn("body", model.full_body_payloads[0])
            self.assertEqual(attention["items"][0]["level"], "needs_attention_now")
            self.assertEqual(attention["items"][0]["source"], "llm_full_body")
            self.assertTrue(attention["items"][0]["full_body_used"])
            self.assertNotIn("body", attention["items"][0])
            self.assertEqual(attention["items"][1]["level"], "needs_attention_now")
            self.assertEqual(attention["items"][1]["category"], "job_opportunity")
            self.assertTrue(attention["items"][1]["full_body_used"])
            self.assertFalse(attention["items"][2]["full_body_used"])

    def test_evaluator_fails_soft_to_empty_attention_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [self._item("message-1", "Flight tomorrow", body="Your flight departs tomorrow.")],
            )

            attention = evaluate_gmail_attention(
                storage_dir=storage_dir,
                latest_batch_id="founder-test-batch-1",
                model_client=FailingAttentionModelClient(),
            )

            self.assertEqual(attention["evaluated_message_count"], 0)
            self.assertEqual(attention["items"], [])
            self.assertEqual(attention["grouped_counts"]["needs_attention_now"], 0)
            self.assertEqual(attention["gmail_mutation"], "none")

    def _write_batch(self, storage_dir: Path, batch_id: str, items: list[dict]) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "items": items,
                },
                indent=2,
            )
        )

    def _item(self, message_id: str, subject: str, body: str) -> dict:
        return {
            "source": "gmail",
            "account_id": "founder-test",
            "message_id": message_id,
            "thread_id": f"thread-{message_id}",
            "sender": "Sender <sender@example.com>",
            "subject": subject,
            "date": "2026-07-01T08:00:00Z",
            "snippet": body[:120],
            "body": body,
            "gmail_label_ids": ["INBOX"],
            "applied_labels": ["reply-needed"],
            "review_state": "reviewed",
            "review_action": "auto-approve",
            "final_labels": ["reply-needed"],
        }


if __name__ == "__main__":
    unittest.main()
