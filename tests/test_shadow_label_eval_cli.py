import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.shadow_label_eval_cli import main


class FakeModelClient:
    def classify(self, message) -> dict:
        return {"labels": list(message.final_labels), "reason": "Matches ground truth."}


class ShadowLabelEvalCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_shadow_model_labels.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Compare local heuristic label suggestions", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_can_run_without_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(Path(temp_dir))
            stdout = io.StringIO()

            exit_code = main(
                ["--storage-dir", temp_dir, "--no-model"],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Heuristic exact-match rate", stdout.getvalue())
            self.assertIn("Saved report:", stdout.getvalue())

    def test_main_uses_model_client_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(Path(temp_dir))
            stdout = io.StringIO()

            exit_code = main(
                ["--storage-dir", temp_dir, "--model", "fake-model"],
                stdout=stdout,
                model_client_factory=lambda model: FakeModelClient(),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Model exact-match rate: 100.0%", stdout.getvalue())

    def test_main_surfaces_missing_api_key_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(Path(temp_dir))
            stderr = io.StringIO()

            exit_code = main(
                ["--storage-dir", temp_dir, "--model", "fake-model"],
                stderr=stderr,
                model_client_factory=lambda model: (_ for _ in ()).throw(
                    RuntimeError("EMAIL_AGENT_OPENAI_API_KEY or OPENAI_API_KEY is required")
                ),
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("EMAIL_AGENT_OPENAI_API_KEY or OPENAI_API_KEY is required", stderr.getvalue())

    def _write_batch(self, storage_dir: Path) -> None:
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


if __name__ == "__main__":
    unittest.main()
