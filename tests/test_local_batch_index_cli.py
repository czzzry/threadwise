import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.local_batch_index_cli import main


class LocalBatchIndexCliTests(unittest.TestCase):
    def test_index_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/list_local_batches.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("List stored local batches", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_lists_multiple_batches_with_privacy_safe_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Private Person <person@example.com>",
                        "subject": "Very private subject line",
                        "body": "Sensitive body text",
                        "date": "2024-06-19T08:00:00Z",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    }
                ],
                fetch_failures=[],
            )
            self._write_status_map(storage_dir, "founder-test-batch-1", {"gmail-live-001": "applied"})
            self._write_attempts(
                storage_dir,
                "founder-test-batch-1",
                {"gmail-live-001": [{"status": "applied", "final_labels": ["reply-needed"]}]},
            )
            self._write_inbox_removal_status_map(
                storage_dir,
                "founder-test-batch-1",
                {"gmail-live-001": "ineligible"},
            )
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-101",
                        "sender": "Another Private Person <person2@example.com>",
                        "subject": "Another private subject line",
                        "body": "Another sensitive body",
                        "date": "2024-06-20T08:00:00Z",
                        "review_state": "pending",
                        "review_action": None,
                        "final_labels": None,
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-102",
                        "sender": "Store <orders@example.com>",
                        "subject": "Private order subject",
                        "body": "Private order body",
                        "date": "2024-06-20T09:00:00Z",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": [],
                    },
                ],
                fetch_failures=[{"message_id": "gmail-live-199", "error": "fetch failed"}],
            )

            stdout = io.StringIO()

            exit_code = main(["--storage-dir", temp_dir], stdout=stdout)

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Stored batches: 2", rendered)
            self.assertIn(
                "founder-test-batch-1 | account=founder-test | items=1 | review=reviewed=1 | labels=labeled=1,unlabeled=0 | writes=applied=1 | inbox_removal=ineligible=1 | retries=0 | fetch_failures=0",
                rendered,
            )
            self.assertIn(
                "founder-test-batch-2 | account=founder-test | items=2 | review=pending=1,reviewed=1 | labels=labeled=0,unlabeled=1 | writes=missing=2 | inbox_removal=missing=2 | retries=0 | fetch_failures=1",
                rendered,
            )
            self.assertLess(
                rendered.index("founder-test-batch-1"),
                rendered.index("founder-test-batch-2"),
            )
            self.assertNotIn("Very private subject line", rendered)
            self.assertNotIn("Sensitive body text", rendered)
            self.assertNotIn("Private Person", rendered)

    def test_main_handles_missing_optional_artifacts_and_empty_storage_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()

            exit_code = main(["--storage-dir", temp_dir], stdout=stdout)

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "Stored batches: 0\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-3",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-201",
                        "sender": "Hidden Sender <hidden@example.com>",
                        "subject": "Hidden subject",
                        "body": "Hidden body",
                        "date": "2024-06-21T08:00:00Z",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": [],
                    }
                ],
                fetch_failures=[],
            )

            stdout = io.StringIO()

            exit_code = main(["--storage-dir", temp_dir], stdout=stdout)

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "founder-test-batch-3 | account=founder-test | items=1 | review=reviewed=1 | labels=labeled=0,unlabeled=1 | writes=missing=1 | inbox_removal=missing=1 | retries=0 | fetch_failures=0",
                rendered,
            )
            self.assertNotIn("Hidden subject", rendered)
            self.assertNotIn("Hidden Sender", rendered)

    def _write_batch(self, storage_dir: Path, batch_id: str, items: list[dict], fetch_failures: list[dict]) -> None:
        batch_path = storage_dir / "batches" / f"{batch_id}.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "raw_messages": [],
                    "fetch_failures": fetch_failures,
                    "items": items,
                },
                indent=2,
            )
        )

    def _write_status_map(self, storage_dir: Path, batch_id: str, status_map: dict[str, str]) -> None:
        (storage_dir / f"{batch_id}_write_status.json").write_text(json.dumps(status_map, indent=2))

    def _write_attempts(self, storage_dir: Path, batch_id: str, attempts: dict[str, list[dict]]) -> None:
        (storage_dir / f"{batch_id}_write_attempts.json").write_text(json.dumps(attempts, indent=2))

    def _write_inbox_removal_status_map(self, storage_dir: Path, batch_id: str, status_map: dict[str, str]) -> None:
        (storage_dir / f"{batch_id}_inbox_removal_status.json").write_text(json.dumps(status_map, indent=2))


if __name__ == "__main__":
    unittest.main()
