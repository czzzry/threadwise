import io
import json
import tempfile
import unittest
from pathlib import Path

from src.memory_impact_report_cli import main


class MemoryImpactReportCliTests(unittest.TestCase):
    def test_main_writes_report_and_prints_top_memory_impact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
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
                    }
                ],
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "accepted_shadow_teachable_rules.json").write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "id": "shadow-outlookmail-yoga-barn",
                                "instruction": "Anything from namaste@yoga-barn-berlin.de should be calendar-event.",
                                "label": "calendar-event",
                                "terms": ["namaste@yoga-barn-berlin.de"],
                                "keep_visible": True,
                                "created_at": "2026-06-28T00:00:00Z",
                                "providers": ["outlookmail"],
                                "enabled": True,
                                "source_examples": [
                                    {
                                        "sender": "Yoga Barn Berlin <namaste@yoga-barn-berlin.de>",
                                        "subject": "Deine Anmeldung bei Yoga Barn Berlin",
                                    }
                                ],
                                "scope": "sender",
                                "match_mode": "sender",
                                "provenance": {"source": "accepted-shadow-suggestion"},
                                "updated_at": "2026-06-28T00:00:00Z",
                            }
                        ]
                    },
                    indent=2,
                )
            )
            review_pack_path = output_dir / "review-pack.json"
            review_pack_path.write_text(
                json.dumps(
                    {
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
                                    "reasons": [],
                                },
                            }
                        ]
                    },
                    indent=2,
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "--output-storage-dir",
                    str(output_dir),
                    "--gmail-storage-dir",
                    str(root / "gmail"),
                    "--protonmail-storage-dir",
                    str(root / "protonmail"),
                    "--outlookmail-storage-dir",
                    str(outlook_dir),
                    "--review-pack-path",
                    str(review_pack_path),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Memory impact: rules=1 | impacted=1 | unresolved before=1 | after=0", rendered)
            self.assertIn("Top memory impact: shadow-outlookmail-yoga-barn | resolved=1 | matched=1", rendered)
            self.assertIn("Top review payoff: outlookmail | mystery@example.com | expected gain=1 | bucket=medium-high", rendered)
            self.assertIn("Saved report:", rendered)

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
