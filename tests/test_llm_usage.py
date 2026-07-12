import json
import tempfile
import unittest
from pathlib import Path

from src.llm_usage import (
    COST_BASIS,
    build_llm_usage_event,
    append_llm_usage_event,
    llm_usage_ledger_path,
    load_llm_usage_events,
    summarize_llm_usage,
    usage_metadata_for_run,
)


class LLMUsageTests(unittest.TestCase):
    def test_append_and_load_usage_event_records_estimated_cost_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            event = build_llm_usage_event(
                timestamp="2026-07-01T09:30:00+00:00",
                feature="gmail_attention",
                model="gpt-4.1-mini",
                input_tokens=1200,
                output_tokens=180,
                estimated_cost_usd=0.0042,
                run_id="founder-test-batch-1",
            )

            saved = append_llm_usage_event(storage_dir, event)
            loaded_events = load_llm_usage_events(storage_dir)

            self.assertEqual(saved["timestamp"], "2026-07-01T09:30:00+00:00")
            self.assertEqual(saved["feature"], "gmail_attention")
            self.assertEqual(saved["model"], "gpt-4.1-mini")
            self.assertEqual(saved["input_tokens"], 1200)
            self.assertEqual(saved["output_tokens"], 180)
            self.assertEqual(saved["estimated_cost_usd"], 0.0042)
            self.assertEqual(saved["run_id"], "founder-test-batch-1")
            self.assertIs(saved["cost_is_estimate"], True)
            self.assertEqual(loaded_events, [saved])

            ledger = json.loads(llm_usage_ledger_path(storage_dir).read_text())
            self.assertEqual(ledger["schema_version"], 1)
            self.assertEqual(ledger["cost_basis"], COST_BASIS)
            self.assertEqual(ledger["events"], [saved])

    def test_summarizes_usage_by_day_week_month_and_feature(self) -> None:
        events = [
            build_llm_usage_event(
                timestamp="2026-07-01T09:30:00+00:00",
                feature="gmail_attention",
                model="gpt-4.1-mini",
                input_tokens=100,
                output_tokens=20,
                estimated_cost_usd=0.001,
                run_id="run-1",
            ),
            build_llm_usage_event(
                timestamp="2026-07-02T11:00:00+00:00",
                feature="gmail_attention",
                model="gpt-4.1-mini",
                input_tokens=200,
                output_tokens=30,
                estimated_cost_usd=0.002,
                run_id="run-2",
            ),
            build_llm_usage_event(
                timestamp="2026-08-03T12:00:00+00:00",
                feature="rule_proposal",
                model="gpt-4.1",
                input_tokens=500,
                output_tokens=60,
                estimated_cost_usd=0.02,
                run_id="run-3",
            ),
        ]

        summary = summarize_llm_usage(events)

        self.assertEqual(summary["cost_basis"], COST_BASIS)
        self.assertEqual(
            summary["total"],
            {
                "event_count": 3,
                "input_tokens": 800,
                "output_tokens": 110,
                "total_tokens": 910,
                "estimated_cost_usd": 0.023,
            },
        )
        self.assertEqual(summary["by_day"]["2026-07-01"]["estimated_cost_usd"], 0.001)
        self.assertEqual(summary["by_day"]["2026-07-02"]["input_tokens"], 200)
        self.assertEqual(summary["by_week"]["2026-W27"]["event_count"], 2)
        self.assertEqual(summary["by_month"]["2026-07"]["output_tokens"], 50)
        self.assertEqual(summary["by_feature"]["gmail_attention"]["estimated_cost_usd"], 0.003)
        self.assertEqual(summary["by_feature"]["rule_proposal"]["total_tokens"], 560)

    def test_run_usage_metadata_matches_attention_report_usage_shape(self) -> None:
        events = [
            build_llm_usage_event(
                timestamp="2026-07-01T09:30:00+00:00",
                feature="gmail_attention",
                model="gpt-4.1-mini",
                input_tokens=100,
                output_tokens=20,
                estimated_cost_usd=0.001,
                run_id="founder-test-batch-1",
            ),
            build_llm_usage_event(
                timestamp="2026-07-01T09:31:00+00:00",
                feature="gmail_attention",
                model="gpt-4.1-mini",
                input_tokens=300,
                output_tokens=40,
                estimated_cost_usd=0.003,
                run_id="founder-test-batch-1",
            ),
            build_llm_usage_event(
                timestamp="2026-07-01T09:32:00+00:00",
                feature="rule_proposal",
                model="gpt-4.1",
                input_tokens=999,
                output_tokens=99,
                estimated_cost_usd=0.99,
                run_id="founder-test-batch-1",
            ),
        ]

        metadata = usage_metadata_for_run(events, run_id="founder-test-batch-1", feature="gmail_attention")

        self.assertEqual(
            metadata,
            {
                "input_tokens": 400,
                "output_tokens": 60,
                "estimated_cost_usd": 0.004,
                "event_count": 2,
                "cost_is_estimate": True,
                "cost_basis": COST_BASIS,
            },
        )


if __name__ == "__main__":
    unittest.main()
