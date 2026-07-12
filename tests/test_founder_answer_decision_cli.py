import io
import json
import tempfile
import unittest
from pathlib import Path

from src.founder_answer_decision_cli import main
from src.local_artifacts import latest_safety_triage_manifest_path


class FounderAnswerDecisionCliTests(unittest.TestCase):
    def test_main_answers_question_and_saves_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            founder_answer_pack_path = output_dir / "founder-answer-pack.json"
            founder_answer_pack_path.write_text(
                json.dumps(
                    {
                        "questions": [
                            {
                                "question_id": "question-marketing-preference",
                                "theme": "marketing-preference",
                                "title": "Title",
                                "prompt": "Prompt",
                                "answer_options": [
                                    {
                                        "answer_key": "low_value_default",
                                        "description": "Default low value.",
                                        "proposal_drafts": [
                                            {
                                                "id": "proposal-outlookmail-sender-cluster-promotions-lieferando",
                                                "provider": "outlookmail",
                                                "account_id": "founder-hotmail",
                                                "source_batch_id": "founder-hotmail-batch-8",
                                                "source_message_ids": ["m1"],
                                                "scope": "sender-cluster",
                                                "label": "promotions",
                                                "instruction": "Anything from lieferando should be promotions.",
                                                "terms": ["lieferando"],
                                                "source_examples": [],
                                                "explanation": "Drafted from founder answer.",
                                                "preview": {"match_count": 3, "matches": []},
                                                "status": "pending",
                                                "created_at": "2026-06-28T00:00:00Z",
                                                "updated_at": "2026-06-28T00:00:00Z",
                                            }
                                        ],
                                        "projection": {"proposal_count": 1, "estimated_resolved_messages": 3},
                                    },
                                    {
                                        "answer_key": "keep_visible",
                                        "description": "Keep visible.",
                                        "proposal_drafts": [],
                                        "projection": {"proposal_count": 0, "estimated_resolved_messages": 0},
                                    },
                                ],
                            }
                        ]
                    },
                    indent=2,
                )
            )
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps(
                    {
                        "artifacts": {
                            "founder_answer_pack_path": str(founder_answer_pack_path),
                        }
                    },
                    indent=2,
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "--output-storage-dir",
                    str(output_dir),
                    "--question-id",
                    "question-marketing-preference",
                    "--response-text",
                    "These are promos and I do not want them in normal attention.",
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Founder answer: marketing-preference | matched=low_value_default | confidence=medium", rendered)
            self.assertIn("Projected impact: proposals=1 | resolved=3", rendered)
            self.assertIn("Saved decision:", rendered)


if __name__ == "__main__":
    unittest.main()
