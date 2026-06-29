import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.shadow_review_pack_cli import main


class ShadowReviewPackCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/build_shadow_review_pack.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Build a family-level review pack", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_writes_review_pack_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "report.json"
            output_dir = root / "classifier_eval"
            report_path.write_text(
                json.dumps(
                    {
                        "eval_contract": {"current_doc": "docs/current-multi-inbox-eval-contract-2026-06-28.md"},
                        "providers": {
                            "protonmail": {
                                "shadow_count": 12,
                                "top_unlabeled_families_by_split": {
                                    "discovery": [
                                        {
                                            "sender_key": "confirm@eightfold.ai",
                                            "subject_key": "verify your email",
                                            "count": 3,
                                            "examples": [
                                                {
                                                    "account_id": "personal-proton",
                                                    "sender": "Eightfold <confirm@eightfold.ai>",
                                                    "subject": "Verify your email",
                                                }
                                            ],
                                        }
                                    ]
                                },
                            }
                        },
                        "shadow_suggestion_candidates": {
                            "protonmail": [
                                {
                                    "provider": "protonmail",
                                    "sender_key": "confirm@eightfold.ai",
                                    "subject_key": "verify your email",
                                    "suggested_labels": ["account-security"],
                                    "rationale": "Verification flow.",
                                    "evidence_terms": ["verify your email"],
                                    "generated_by": "openai-shadow-family-suggester",
                                    "confidence": "high",
                                    "status": "pending",
                                }
                            ]
                        },
                    }
                )
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "shadow_suggestion_memory.json").write_text(json.dumps({"candidates": []}))
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--report-path",
                    str(report_path),
                    "--output-storage-dir",
                    str(output_dir),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Built review pack: objective=1", rendered)
            self.assertIn("safety-priority=0", rendered)
            self.assertIn("Saved pack:", rendered)
            pack_path = Path(rendered.split("Saved pack:", 1)[1].splitlines()[0].strip())
            self.assertTrue(pack_path.exists())
            pack = json.loads(pack_path.read_text())
            self.assertEqual(pack["summary"]["objective_review_count"], 1)
            self.assertEqual(pack["objective_reviews"][0]["provider"], "protonmail")

    def test_main_surfaces_top_safety_priority_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "report.json"
            output_dir = root / "classifier_eval"
            report_path.write_text(
                json.dumps(
                    {
                        "eval_contract": {"current_doc": "docs/current-multi-inbox-eval-contract-2026-06-28.md"},
                        "providers": {
                            "protonmail": {
                                "shadow_count": 12,
                                "top_unlabeled_families_by_split": {
                                    "discovery": [
                                        {
                                            "sender_key": "confirm@eightfold.ai",
                                            "subject_key": "verify your email",
                                            "count": 3,
                                            "examples": [
                                                {
                                                    "account_id": "personal-proton",
                                                    "sender": "Eightfold <confirm@eightfold.ai>",
                                                    "subject": "Verify your email",
                                                }
                                            ],
                                        }
                                    ]
                                },
                                "safety_memory_projection": {
                                    "top_projected_false_hide_risk_families": [
                                        {
                                            "sender_key": "confirm@eightfold.ai",
                                            "subject_key": "verify your email",
                                            "count": 3,
                                            "examples": [],
                                        }
                                    ],
                                    "top_projected_caution_families_by_split": {
                                        "discovery": [],
                                        "validation": [],
                                        "holdout": [],
                                    },
                                },
                            }
                        },
                        "shadow_suggestion_candidates": {
                            "protonmail": [
                                {
                                    "provider": "protonmail",
                                    "sender_key": "confirm@eightfold.ai",
                                    "subject_key": "verify your email",
                                    "suggested_labels": ["account-security"],
                                    "rationale": "Verification flow.",
                                    "evidence_terms": ["verify your email"],
                                    "generated_by": "openai-shadow-family-suggester",
                                    "confidence": "high",
                                    "status": "pending",
                                }
                            ]
                        },
                    }
                )
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "shadow_suggestion_memory.json").write_text(json.dumps({"candidates": []}))
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--report-path",
                    str(report_path),
                    "--output-storage-dir",
                    str(output_dir),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Top safety priority: protonmail | confirm@eightfold.ai | verify your email | score=5", rendered)


if __name__ == "__main__":
    unittest.main()
