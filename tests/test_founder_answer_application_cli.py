import io
import json
import tempfile
import unittest
from pathlib import Path

from src.founder_answer_application_cli import main
from src.local_artifacts import founder_answer_decision_path, latest_safety_triage_manifest_path


class FounderAnswerApplicationCliTests(unittest.TestCase):
    def test_main_applies_latest_decision_for_question(self) -> None:
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
                        "sender": "Lieferando <deals@lieferando.de>",
                        "subject": "30 % Rabatt",
                        "snippet": "Deal.",
                        "body": "Deal.",
                    }
                ],
            )
            review_pack_path = output_dir / "review-pack.json"
            review_pack_path.parent.mkdir(parents=True, exist_ok=True)
            review_pack_path.write_text(json.dumps({"top_review_targets": []}, indent=2))
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps({"artifacts": {"review_pack_path": str(review_pack_path)}}, indent=2)
            )
            decision_path = founder_answer_decision_path(output_dir, "question-marketing-preference-1")
            decision_path.parent.mkdir(parents=True, exist_ok=True)
            decision_path.write_text(
                json.dumps(
                    {
                        "decision_id": "question-marketing-preference-1",
                        "question_id": "question-marketing-preference",
                        "theme": "marketing-preference",
                        "matched_answer_key": "low_value_default",
                        "proposal_drafts": [
                            {
                                "id": "proposal-outlookmail-sender-cluster-promotions-lieferando-30-rabatt",
                                "provider": "outlookmail",
                                "account_id": "founder-hotmail",
                                "source_batch_id": "founder-hotmail-batch-1",
                                "source_message_ids": ["o1"],
                                "scope": "sender-cluster",
                                "label": "promotions",
                                "instruction": "Anything from lieferando with this subject family should be promotions.",
                                "terms": ["lieferando", "30 rabatt"],
                                "source_examples": [
                                    {
                                        "message_id": "o1",
                                        "sender": "Lieferando <deals@lieferando.de>",
                                        "subject": "30 % Rabatt",
                                    }
                                ],
                                "explanation": "Drafted from founder answer.",
                                "preview": {"match_count": 1, "matches": []},
                                "status": "pending",
                                "created_at": "2026-06-28T00:00:00Z",
                                "updated_at": "2026-06-28T00:00:00Z",
                            }
                        ],
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
                    "--question-id",
                    "question-marketing-preference",
                    "--review-notes",
                    "Approved by founder.",
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Applied founder answer: marketing-preference | matched=low_value_default | approved-proposals=1 | approved-rules=1", rendered)
            self.assertIn("resolved gain=1", rendered)
            self.assertIn("Saved application:", rendered)
            self.assertIn("Saved report:", rendered)

    def test_main_allows_resolving_question_without_actionable_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "classifier_eval"
            review_pack_path = output_dir / "review-pack.json"
            review_pack_path.parent.mkdir(parents=True, exist_ok=True)
            review_pack_path.write_text(json.dumps({"top_review_targets": []}, indent=2))
            latest_safety_triage_manifest_path(output_dir).write_text(
                json.dumps({"artifacts": {"review_pack_path": str(review_pack_path)}}, indent=2)
            )
            decision_path = founder_answer_decision_path(output_dir, "question-taxonomy-gap-1")
            decision_path.parent.mkdir(parents=True, exist_ok=True)
            decision_path.write_text(
                json.dumps(
                    {
                        "decision_id": "question-taxonomy-gap-1",
                        "question_id": "question-taxonomy-gap",
                        "theme": "taxonomy-gap",
                        "matched_answer_key": "map_existing_label",
                        "proposal_drafts": [],
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
                    str(root / "outlookmail"),
                    "--question-id",
                    "question-taxonomy-gap",
                    "--review-notes",
                    "Resolved without new proposals.",
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Applied founder answer: taxonomy-gap | matched=map_existing_label | approved-proposals=0 | approved-rules=0", rendered)

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
