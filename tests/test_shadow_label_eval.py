import json
import tempfile
import unittest
from pathlib import Path

from src.shadow_label_eval import ReviewedMessage, ShadowLabelEvaluator, _shadow_label_prompt, build_shadow_eval_report


class FakeModelClient:
    def __init__(self, predictions: dict[str, dict]) -> None:
        self._predictions = predictions

    def classify(self, message) -> dict:
        return self._predictions[message.message_id]


class ShadowLabelEvalTests(unittest.TestCase):
    def test_shadow_prompt_encodes_executive_triage_policy(self) -> None:
        prompt = _shadow_label_prompt(
            ReviewedMessage(
                batch_id="founder-test-batch-1",
                message_id="m1",
                sender="Resort <offers@example.com>",
                subject="Exclusive resort sale",
                snippet="Save 30% this weekend.",
                body="Book now for a luxury escape.",
                final_labels=[],
                heuristic_labels=[],
            )
        )

        self.assertIn("Classify this email for executive inbox triage and retrieval.", prompt)
        self.assertIn("spam-low-value usually overrides topical labels", prompt)
        self.assertIn("Actual application or hiring-process mail must never be spam-low-value", prompt)
        self.assertIn("prefer a single label", prompt)

    def test_build_shadow_eval_report_compares_heuristic_and_model(self) -> None:
        report = build_shadow_eval_report(
            [
                {
                    "batch_id": "founder-test-batch-1",
                    "message_id": "m1",
                    "sender": "A <a@example.com>",
                    "subject": "Trip",
                    "ground_truth": ["travel"],
                    "heuristic_labels": [],
                    "model_labels": ["travel"],
                    "model_reason": "Travel booking.",
                },
                {
                    "batch_id": "founder-test-batch-1",
                    "message_id": "m2",
                    "sender": "B <b@example.com>",
                    "subject": "Sale",
                    "ground_truth": ["promotions", "spam-low-value"],
                    "heuristic_labels": ["promotions", "spam-low-value"],
                    "model_labels": ["promotions"],
                    "model_reason": "Promotion.",
                },
            ],
            model_available=True,
            disagreement_limit=10,
        )

        self.assertEqual(report["overall"]["reviewed_count"], 2)
        self.assertEqual(report["overall"]["heuristic"]["exact_match_rate"], 50.0)
        self.assertEqual(report["overall"]["model"]["exact_match_rate"], 50.0)
        self.assertEqual(len(report["disagreements"]["model_better_than_heuristic"]), 1)
        self.assertEqual(len(report["disagreements"]["heuristic_better_than_model"]), 1)
        self.assertEqual(len(report["comparison_candidates"]), 1)
        self.assertEqual(report["comparison_candidates"][0]["message_id"], "m2")
        self.assertEqual(report["comparison_candidates"][0]["model_labels"], ["promotions"])

    def test_evaluator_persists_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            (batches_dir / "founder-test-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "items": [
                            {
                                "message_id": "m1",
                                "sender": "A <a@example.com>",
                                "subject": "Trip",
                                "snippet": "Boarding pass",
                                "body": "Your travel itinerary is attached.",
                                "review_state": "reviewed",
                                "final_labels": ["travel"],
                                "applied_labels": [],
                            }
                        ],
                    },
                    indent=2,
                )
            )

            evaluator = ShadowLabelEvaluator(
                storage_dir=storage_dir,
                model_client=FakeModelClient({"m1": {"labels": ["travel"], "reason": "Travel."}}),
            )
            report = evaluator.run()

            self.assertIn("report_path", report)
            self.assertTrue(Path(report["report_path"]).exists())
            saved = json.loads(Path(report["report_path"]).read_text())
            self.assertEqual(saved["overall"]["reviewed_count"], 1)


if __name__ == "__main__":
    unittest.main()
