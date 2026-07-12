import json
import tempfile
import unittest
from pathlib import Path

from src.memory_impact_report import build_memory_impact_report
from src.teachable_rule_memory import TeachableRule


class MemoryImpactReportTests(unittest.TestCase):
    def test_build_report_shows_memory_winner_and_next_review_payoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outlook_dir = root / "outlookmail"
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-1",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Yoga Barn Berlin <namaste@yoga-barn-berlin.de>",
                        "subject": "Deine Anmeldung bei Yoga Barn Berlin",
                        "snippet": "Willkommen.",
                        "body": "Willkommen.",
                    },
                    {
                        "message_id": "o2",
                        "sender": "Mystery <mystery@example.com>",
                        "subject": "Unknown",
                        "snippet": "Unknown.",
                        "body": "Unknown.",
                    },
                ],
            )
            rules = [
                TeachableRule(
                    id="shadow-outlookmail-yoga-barn",
                    instruction="Anything from namaste@yoga-barn-berlin.de should be calendar-event.",
                    label="calendar-event",
                    terms=("namaste@yoga-barn-berlin.de",),
                    keep_visible=True,
                    created_at="2026-06-28T00:00:00Z",
                    providers=("outlookmail",),
                    enabled=True,
                    source_examples=(
                        {
                            "sender": "Yoga Barn Berlin <namaste@yoga-barn-berlin.de>",
                            "subject": "Deine Anmeldung bei Yoga Barn Berlin",
                        },
                    ),
                    scope="sender",
                    match_mode="sender",
                    provenance={"source": "accepted-shadow-suggestion"},
                    updated_at="2026-06-28T00:00:00Z",
                )
            ]
            review_pack = {
                "top_review_targets": [
                    {
                        "provider": "outlookmail",
                        "sender_key": "mystery@example.com",
                        "subject_key": "unknown",
                        "question_lane": "taxonomy-question",
                        "suggested_labels": [],
                        "count": 1,
                        "review_priority": {
                            "score": 6,
                            "bucket": "high",
                            "estimated_message_gain": 1,
                            "reasons": ["medium-family"],
                        },
                    }
                ]
            }

            report = build_memory_impact_report(
                [("outlookmail", outlook_dir)],
                accepted_rules=rules,
                review_pack=review_pack,
            )

            self.assertEqual(report["summary"]["accepted_rule_count"], 1)
            self.assertEqual(report["summary"]["impacted_rule_count"], 1)
            self.assertEqual(report["summary"]["unresolved_before"], 2)
            self.assertEqual(report["summary"]["unresolved_after"], 1)
            self.assertEqual(report["top_memory_impacts"][0]["rule_id"], "shadow-outlookmail-yoga-barn")
            self.assertEqual(report["top_memory_impacts"][0]["resolved_message_count"], 1)
            self.assertEqual(report["next_review_payoffs"][0]["provider"], "outlookmail")
            self.assertEqual(report["next_review_payoffs"][0]["expected_gain_band"], "medium-high")

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
