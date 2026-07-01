import json
import tempfile
import unittest
from pathlib import Path

from src.daily_report import (
    ATTENTION_SCHEMA_VERSION,
    build_attention_section,
    build_empty_attention_section,
    build_gmail_daily_report,
    write_daily_report,
)
from src.local_artifacts import validate_json_artifact


class DailyReportTests(unittest.TestCase):
    def test_build_attention_section_groups_items_and_never_records_gmail_mutation(self) -> None:
        attention = build_attention_section(
            evaluated_message_count=3,
            lookback_window={
                "latest_batch_id": "founder-test-batch-2",
                "stored_lookback_batch_ids": ["founder-test-batch-1"],
                "max_evaluated_messages": 50,
            },
            model={"provider": "openai", "name": "fake-attention-model"},
            usage={"input_tokens": 1200, "output_tokens": 180, "estimated_cost_usd": 0.0042},
            items=[
                {
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "level": "needs_attention_now",
                    "category": "travel",
                    "reason": "Flight departs tomorrow morning.",
                    "evidence": "Message includes a departure date in the next day.",
                    "source": "llm",
                    "handled_state": "appears_unhandled",
                    "feedback_state": "unset",
                    "gmail_mutation": "applied",
                    "body": "This must never be copied into the attention artifact.",
                },
                {
                    "message_id": "gmail-live-002",
                    "level": "possible_attention",
                    "category": "job_opportunity",
                    "reason": "Recruiter scheduling link may need action.",
                    "evidence": "Message asks the founder to book an interview slot.",
                    "source": "llm",
                },
            ],
        )

        self.assertEqual(attention["schema_version"], ATTENTION_SCHEMA_VERSION)
        self.assertEqual(attention["evaluated_message_count"], 3)
        self.assertEqual(
            attention["grouped_counts"],
            {
                "needs_attention_now": 1,
                "possible_attention": 1,
                "not_attention": 0,
                "insufficient_context": 0,
            },
        )
        self.assertEqual(attention["usage"]["input_tokens"], 1200)
        self.assertEqual(attention["items"][0]["gmail_mutation"], "none")
        self.assertEqual(attention["items"][1]["handled_state"], "unknown")
        self.assertNotIn("body", attention["items"][0])

    def test_gmail_daily_report_includes_empty_attention_contract_without_changing_unlabeled_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_id = "founder-test-batch-1"
            (storage_dir / "batches").mkdir(parents=True)
            (storage_dir / "batches" / f"{batch_id}.json").write_text(
                json.dumps(
                    {
                        "batch_id": batch_id,
                        "account_id": "founder-test",
                        "items": [
                            {
                                "message_id": "gmail-live-001",
                                "review_state": "reviewed",
                                "final_labels": ["shopping-order"],
                            },
                            {
                                "message_id": "gmail-live-002",
                                "review_state": "pending",
                                "final_labels": [],
                            },
                        ],
                    },
                    indent=2,
                )
            )

            report = build_gmail_daily_report(
                storage_dir=storage_dir,
                batch_id=batch_id,
                account_id="founder-test",
                fetched_count=2,
                applied_count=1,
                inbox_removals=0,
                unlabeled_exceptions=[
                    {
                        "sender": "Mystery <mystery@example.com>",
                        "subject": "Needs a human label",
                    }
                ],
            )

            self.assertEqual(report["unlabeled_count"], 1)
            self.assertEqual(report["attention"], build_empty_attention_section(batch_id=batch_id))
            self.assertEqual(report["attention"]["grouped_counts"]["needs_attention_now"], 0)

    def test_daily_report_validation_accepts_absent_or_present_attention_section(self) -> None:
        minimal_legacy_report = {
            "account_id": "founder-test",
            "provider": "gmail",
            "batch_id": "founder-test-batch-1",
            "report_date": "2026-07-01",
            "processed_count": 1,
            "unlabeled_count": 0,
        }
        modern_report = dict(minimal_legacy_report)
        modern_report["attention"] = build_empty_attention_section(batch_id="founder-test-batch-1")

        self.assertIsNone(validate_json_artifact("daily_report", minimal_legacy_report))
        self.assertIsNone(validate_json_artifact("daily_report", modern_report))

    def test_write_daily_report_persists_attention_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            report = {
                "account_id": "founder-test",
                "provider": "gmail",
                "batch_id": "founder-test-batch-1",
                "report_date": "2026-07-01",
                "processed_count": 1,
                "unlabeled_count": 0,
                "attention": build_empty_attention_section(batch_id="founder-test-batch-1"),
            }

            write_daily_report(storage_dir, "founder-test-batch-1", report)

            saved = json.loads((storage_dir / "reports" / "founder-test-batch-1_daily_report.json").read_text())
            self.assertEqual(saved["attention"]["schema_version"], ATTENTION_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
