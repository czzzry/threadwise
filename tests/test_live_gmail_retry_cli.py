import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_gmail_retry_cli import main


class FakeWritableGmailClient:
    def __init__(self, failing_message_ids: set[str] | None = None) -> None:
        self.calls: list[tuple] = []
        self.labels: dict[str, str] = {}
        self._failing_message_ids = set(failing_message_ids or set())

    def get_or_create_label(self, label_name: str) -> str:
        self.calls.append(("get_or_create_label", label_name))
        if label_name not in self.labels:
            self.labels[label_name] = f"Label_{len(self.labels) + 1}"
        return self.labels[label_name]

    def apply_labels(self, message_id: str, label_ids: list[str]) -> None:
        self.calls.append(("apply_labels", message_id, label_ids))
        if message_id in self._failing_message_ids:
            raise RuntimeError(f"Failed to apply labels to {message_id}")


class LiveGmailRetryCliTests(unittest.TestCase):
    def test_retry_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/retry_live_gmail_failed_writes.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Retry failed EA label writes", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_retries_only_messages_whose_latest_status_is_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
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
                        "subject": "Your receipt",
                        "date": "2024-06-19T09:00:00Z",
                        "interpretation": "A purchase receipt.",
                        "applied_labels": ["receipt-billing"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["receipt-billing"],
                    },
                ],
            )
            self._write_status_map(
                storage_dir,
                {
                    "gmail-live-001": "failed",
                    "gmail-live-002": "applied",
                },
            )
            self._write_attempts(
                storage_dir,
                {
                    "gmail-live-001": [{"status": "failed", "final_labels": ["reply-needed"]}],
                    "gmail-live-002": [{"status": "applied", "final_labels": ["receipt-billing"]}],
                },
            )

            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            write_status = json.loads((storage_dir / "founder-test-batch-1_write_status.json").read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                gmail_client.calls,
                [
                    ("get_or_create_label", "EA/NeedsAction"),
                    ("apply_labels", "gmail-live-001", ["Label_1"]),
                ],
            )
            self.assertEqual(write_status["gmail-live-001"], "applied")
            self.assertEqual(write_status["gmail-live-002"], "applied")
            self.assertIn("Retryable failed writes: 1", stdout.getvalue())
            self.assertIn("Retried successfully: 1", stdout.getvalue())

    def test_main_uses_gmail_modify_scope_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    }
                ],
            )
            self._write_status_map(storage_dir, {"gmail-live-001": "failed"})
            self._write_attempts(
                storage_dir,
                {"gmail-live-001": [{"status": "failed", "final_labels": ["reply-needed"]}]},
            )

            captured_scope: list[str] = []

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=io.StringIO(),
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: self._capture_client(
                    FakeWritableGmailClient(),
                    captured_scope,
                    required_scope,
                ),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(captured_scope, ["https://www.googleapis.com/auth/gmail.modify"])

    def test_main_reports_and_skips_failed_messages_whose_labels_changed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": ["account-security"],
                    }
                ],
            )
            self._write_status_map(storage_dir, {"gmail-live-001": "failed"})
            self._write_attempts(
                storage_dir,
                {"gmail-live-001": [{"status": "failed", "final_labels": ["reply-needed"]}]},
            )

            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            write_status = json.loads((storage_dir / "founder-test-batch-1_write_status.json").read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(gmail_client.calls, [])
            self.assertEqual(write_status["gmail-live-001"], "failed")
            self.assertIn("Retryable failed writes: 0", stdout.getvalue())
            self.assertIn("Blocked by changed labels: 1", stdout.getvalue())
            self.assertIn("gmail-live-001 requires re-review before retry", stdout.getvalue())

    def test_main_preserves_failed_status_and_appends_history_when_retry_fails_again(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    }
                ],
            )
            self._write_status_map(storage_dir, {"gmail-live-001": "failed"})
            self._write_attempts(
                storage_dir,
                {"gmail-live-001": [{"status": "failed", "final_labels": ["reply-needed"]}]},
            )

            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient(failing_message_ids={"gmail-live-001"})

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            write_status = json.loads((storage_dir / "founder-test-batch-1_write_status.json").read_text())
            attempts = json.loads((storage_dir / "founder-test-batch-1_write_attempts.json").read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(write_status["gmail-live-001"], "failed")
            self.assertEqual(
                [entry["status"] for entry in attempts["gmail-live-001"]],
                ["failed", "failed"],
            )
            self.assertIn("Retryable failed writes: 1", stdout.getvalue())
            self.assertIn("Retried successfully: 0", stdout.getvalue())
            self.assertIn("Still failed after retry: 1", stdout.getvalue())

    def _write_batch(self, storage_dir: Path, items: list[dict]) -> None:
        batch_path = storage_dir / "batches" / "founder-test-batch-1.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": "founder-test-batch-1",
                    "account_id": "founder-test",
                    "raw_messages": [],
                    "fetch_failures": [],
                    "items": items,
                },
                indent=2,
            )
        )

    def _write_status_map(self, storage_dir: Path, status_map: dict[str, str]) -> None:
        (storage_dir / "founder-test-batch-1_write_status.json").write_text(json.dumps(status_map, indent=2))

    def _write_attempts(self, storage_dir: Path, attempts: dict[str, list[dict]]) -> None:
        (storage_dir / "founder-test-batch-1_write_attempts.json").write_text(json.dumps(attempts, indent=2))

    def _capture_client(
        self,
        gmail_client: FakeWritableGmailClient,
        captured_scope: list[str],
        required_scope: str,
    ) -> FakeWritableGmailClient:
        captured_scope.append(required_scope)
        return gmail_client


if __name__ == "__main__":
    unittest.main()
