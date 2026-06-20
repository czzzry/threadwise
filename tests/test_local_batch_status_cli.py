import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.local_batch_status_cli import main


class LocalBatchStatusCliTests(unittest.TestCase):
    def test_status_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/inspect_local_batch_status.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Inspect one stored local batch", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_summarizes_batch_state_without_printing_private_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Private Person <person@example.com>",
                        "subject": "Very private subject line",
                        "body": "Sensitive body text",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Needs a reply.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Store <orders@example.com>",
                        "subject": "Another private subject line",
                        "body": "Another sensitive body",
                        "date": "2024-06-19T09:00:00Z",
                        "interpretation": "Promotional mail.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": ["promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-003",
                        "sender": "Newsletter <news@example.com>",
                        "subject": "Pending private subject line",
                        "body": "Pending sensitive body",
                        "date": "2024-06-19T10:00:00Z",
                        "interpretation": "Low confidence.",
                        "applied_labels": ["newsletter"],
                        "near_misses": [],
                        "confidence_band": "low",
                        "review_state": "pending",
                        "review_action": None,
                        "final_labels": None,
                    },
                ],
                fetch_failures=[{"message_id": "gmail-live-999", "error": "temporary fetch failure"}],
            )
            self._write_status_map(
                storage_dir,
                {
                    "gmail-live-001": "applied",
                    "gmail-live-002": "failed",
                },
            )
            self._write_attempts(
                storage_dir,
                {
                    "gmail-live-001": [{"status": "applied", "final_labels": ["reply-needed"]}],
                    "gmail-live-002": [
                        {"status": "failed", "final_labels": ["promotions"]},
                        {"status": "failed", "final_labels": ["promotions"]},
                    ],
                },
            )
            self._write_inbox_removal_status_map(
                storage_dir,
                {
                    "gmail-live-001": "applied",
                    "gmail-live-002": "ineligible",
                },
            )
            self._write_inbox_removal_attempts(
                storage_dir,
                {
                    "gmail-live-001": [{"status": "applied", "final_labels": ["reply-needed"]}],
                    "gmail-live-002": [{"status": "ineligible", "final_labels": ["promotions"]}],
                },
            )

            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Batch ID: founder-test-batch-1", rendered)
            self.assertIn("Account ID: founder-test", rendered)
            self.assertIn("Items: 3", rendered)
            self.assertIn("Fetch failures: 1", rendered)
            self.assertIn("Review states: pending=1, reviewed=2", rendered)
            self.assertIn("Review actions: approve=1, edit=1", rendered)
            self.assertIn("Final labels: labeled=2, unlabeled=0", rendered)
            self.assertIn("Label counts: EA/Promotions=1, EA/ReplyNeeded=1", rendered)
            self.assertIn("Write status: applied=1, failed=1, missing=1", rendered)
            self.assertIn("Write attempts: messages_with_history=2, total_attempts=3, retried_messages=1", rendered)
            self.assertIn("Inbox removal: applied=1, ineligible=1, missing=1", rendered)
            self.assertIn(
                "Inbox removal attempts: messages_with_history=2, total_attempts=2, retried_messages=0",
                rendered,
            )
            self.assertNotIn("Very private subject line", rendered)
            self.assertNotIn("Sensitive body text", rendered)
            self.assertNotIn("Private Person", rendered)

    def test_main_handles_missing_optional_write_artifacts_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Private Person <person@example.com>",
                        "subject": "Private subject",
                        "body": "Sensitive body text",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Needs a reply.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": [],
                    }
                ],
                fetch_failures=[],
            )

            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Write status: missing=1", rendered)
            self.assertIn("Write attempts: messages_with_history=0, total_attempts=0, retried_messages=0", rendered)
            self.assertIn("Inbox removal: missing=1", rendered)
            self.assertIn("Inbox removal attempts: messages_with_history=0, total_attempts=0, retried_messages=0", rendered)
            self.assertIn("Label counts: (none)", rendered)
            self.assertIn("Final labels: labeled=0, unlabeled=1", rendered)

    def test_main_derives_label_counts_from_final_labels_not_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Private Person <person@example.com>",
                        "subject": "Private subject",
                        "body": "Sensitive body text",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Needs a reply.",
                        "applied_labels": ["reply-needed", "promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": ["account-security"],
                    }
                ],
                fetch_failures=[],
            )

            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Label counts: EA/Account=1", rendered)
            self.assertNotIn("EA/ReplyNeeded=1", rendered)
            self.assertNotIn("EA/Promotions=1", rendered)


    def _write_batch(self, storage_dir: Path, items: list[dict], fetch_failures: list[dict]) -> None:
        batch_path = storage_dir / "batches" / "founder-test-batch-1.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": "founder-test-batch-1",
                    "account_id": "founder-test",
                    "raw_messages": [],
                    "fetch_failures": fetch_failures,
                    "items": items,
                },
                indent=2,
            )
        )

    def _write_status_map(self, storage_dir: Path, status_map: dict[str, str]) -> None:
        (storage_dir / "founder-test-batch-1_write_status.json").write_text(json.dumps(status_map, indent=2))

    def _write_attempts(self, storage_dir: Path, attempts: dict[str, list[dict]]) -> None:
        (storage_dir / "founder-test-batch-1_write_attempts.json").write_text(json.dumps(attempts, indent=2))

    def _write_inbox_removal_status_map(self, storage_dir: Path, status_map: dict[str, str]) -> None:
        (storage_dir / "founder-test-batch-1_inbox_removal_status.json").write_text(json.dumps(status_map, indent=2))

    def _write_inbox_removal_attempts(self, storage_dir: Path, attempts: dict[str, list[dict]]) -> None:
        (storage_dir / "founder-test-batch-1_inbox_removal_attempts.json").write_text(json.dumps(attempts, indent=2))


if __name__ == "__main__":
    unittest.main()
