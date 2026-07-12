import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.operational_readiness_cli import main


class OperationalReadinessCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/check_operational_readiness.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("operationally", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_prints_operational_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            runtime_dir = output_dir / "runtime_cascades"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            for index in range(1, 4):
                (runtime_dir / f"runtime-cascade-{index}.json").write_text(
                    json.dumps(
                        {
                            "generated_at": "2026-06-29T00:00:00Z",
                            "summary": {
                                "message_count": 100,
                                "resolved_count": 90,
                                "unresolved_count": 10,
                                "accepted_memory_count": 30,
                                "deterministic_count": 58,
                                "llm_escalation_count": 2,
                                "safety_review_count": 4,
                            },
                        },
                        indent=2,
                    )
                )
            (output_dir / "unified_review_queue.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "pending_count": 18,
                            "pending_by_type": {"founder-question": 2},
                        }
                    },
                    indent=2,
                )
            )
            founder_dir = output_dir / "founder_answer_applications"
            founder_dir.mkdir(parents=True, exist_ok=True)
            (founder_dir / "application-1.json").write_text(
                json.dumps({"question_id": "question-1", "impact_delta": {"resolved_gain": 5}}, indent=2)
            )
            stdout = io.StringIO()

            exit_code = main(
                ["--output-storage-dir", temp_dir, "--window", "3"],
                stdout=stdout,
                cwd=output_dir.parent,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Overall status: PASS", rendered)
            self.assertIn("Latest queue pending count: 18", rendered)
            self.assertIn("Founder applications recorded: 1", rendered)
            self.assertIn("Saved report:", rendered)


if __name__ == "__main__":
    unittest.main()
