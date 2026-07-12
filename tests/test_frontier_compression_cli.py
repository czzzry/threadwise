import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.frontier_compression_cli import main


class FrontierCompressionCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/build_frontier_compression.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Build a sender-cluster frontier compression plan", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_writes_frontier_plan_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            output_dir = root / "classifier_eval"
            rules_path = output_dir / "accepted_shadow_teachable_rules.json"
            batches_dir = gmail_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            (batches_dir / "founder-test-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "provider": "gmail",
                        "items": [
                            {
                                "message_id": "g1",
                                "sender": "noreply@1se.co",
                                "subject": "[1SE] We haven't seen you in a while.",
                                "snippet": "Inactive account notice.",
                                "body": "Inactive account notice.",
                            }
                        ],
                    }
                )
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            rules_path.write_text(json.dumps({"rules": []}))
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(gmail_dir),
                    "--protonmail-storage-dir",
                    str(root / "empty-proton"),
                    "--outlookmail-storage-dir",
                    str(root / "empty-outlook"),
                    "--output-storage-dir",
                    str(output_dir),
                    "--accepted-shadow-rules-path",
                    str(rules_path),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Frontier clusters:", rendered)
            self.assertIn("Auto-low-value:", rendered)
            self.assertIn("Safety-priority:", rendered)
            self.assertIn("Saved plan:", rendered)
            plan_path = Path(rendered.split("Saved plan:", 1)[1].splitlines()[0].strip())
            self.assertTrue(plan_path.exists())
            plan = json.loads(plan_path.read_text())
            self.assertEqual(plan["summary"]["total_unresolved_sender_clusters"], 1)


if __name__ == "__main__":
    unittest.main()
