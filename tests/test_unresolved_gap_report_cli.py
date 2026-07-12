import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.unresolved_gap_report_cli import main


class UnresolvedGapReportCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/check_unresolved_gap.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("remaining unresolved gap", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_prints_gap_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            runtime_dir = output_dir / "runtime_cascades"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / "runtime-cascade-1.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-29T00:00:00Z",
                        "summary": {
                            "message_count": 100,
                            "unresolved_count": 20,
                        },
                        "providers": {"gmail": {"unresolved_count": 20, "outcomes": []}},
                    },
                    indent=2,
                )
            )
            stdout = io.StringIO()

            exit_code = main(["--output-storage-dir", temp_dir], stdout=stdout, cwd=output_dir.parent)

            self.assertEqual(exit_code, 0)
            rendered = stdout.getvalue()
            self.assertIn("Unresolved gap: 20/10 target unresolved", rendered)
            self.assertIn("Provider hotspots:", rendered)
            self.assertIn("Saved report:", rendered)


if __name__ == "__main__":
    unittest.main()
