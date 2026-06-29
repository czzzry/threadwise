import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.shadow_suggestion_memory import ShadowSuggestionCandidate, ShadowSuggestionMemory
from src.shadow_suggestion_memory_cli import main


class ShadowSuggestionMemoryCliTests(unittest.TestCase):
    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/manage_shadow_suggestion_memory.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Manage local shadow suggestion memory candidates", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_approve_and_export_rules_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            memory = ShadowSuggestionMemory(storage_dir / "shadow_suggestion_memory.json")
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="protonmail",
                        sender_key="confirm@eightfold.ai",
                        subject_key="verify your email",
                        split="discovery",
                        count=1,
                        suggested_labels=("account-security",),
                        rationale="Verification flow.",
                        evidence_terms=("verify your email",),
                        source_examples=({"subject": "Verify your email"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "approve",
                    "--storage-dir",
                    temp_dir,
                    "--provider",
                    "protonmail",
                    "--sender-key",
                    "confirm@eightfold.ai",
                    "--subject-key",
                    "verify your email",
                    "--labels",
                    "account-security",
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("accepted:", stdout.getvalue())

            stdout = io.StringIO()
            exit_code = main(
                [
                    "export-rules",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )
            rules_path = storage_dir / "accepted_shadow_teachable_rules.json"
            payload = json.loads(rules_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertIn("Exported 1 provider-scoped rules", stdout.getvalue())
            self.assertEqual(payload["rules"][0]["label"], "account-security")

    def test_list_reports_status_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            memory = ShadowSuggestionMemory(storage_dir / "shadow_suggestion_memory.json")
            memory.merge_candidates(
                [
                    ShadowSuggestionCandidate(
                        provider="protonmail",
                        sender_key="confirm@eightfold.ai",
                        subject_key="verify your email",
                        split="discovery",
                        count=1,
                        suggested_labels=("account-security",),
                        rationale="Verification flow.",
                        evidence_terms=("verify your email",),
                        source_examples=({"subject": "Verify your email"},),
                        generated_by="openai-shadow-family-suggester",
                        confidence="high",
                    )
                ]
            )
            stdout = io.StringIO()

            exit_code = main(["list", "--storage-dir", temp_dir], stdout=stdout)

            self.assertEqual(exit_code, 0)
            self.assertIn("Candidates: 1", stdout.getvalue())
            self.assertIn("Status counts: pending=1", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
