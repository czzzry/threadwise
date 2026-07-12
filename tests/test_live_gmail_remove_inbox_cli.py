import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_gmail_remove_inbox_cli import main


class FakeInboxRemovalGmailClient:
    def __init__(self, failing_message_ids: set[str] | None = None) -> None:
        self.calls: list[tuple] = []
        self._failing_message_ids = set(failing_message_ids or set())

    def remove_inbox_label(self, message_id: str) -> None:
        self.calls.append(("remove_inbox_label", message_id))
        if message_id in self._failing_message_ids:
            raise RuntimeError(f"Failed to remove INBOX from {message_id}")


class LiveGmailRemoveInboxCliTests(unittest.TestCase):
    def test_remove_inbox_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/remove_inbox_for_live_gmail_batch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Remove INBOX for one stored live Gmail batch", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_removes_inbox_only_for_confirmed_low_value_messages_with_applied_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <offers@example.com>",
                        "subject": "Weekend offer",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Promotional marketing email that looks low priority to review.",
                        "applied_labels": ["promotions", "spam-low-value"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions", "spam-low-value"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T09:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    },
                ],
            )
            self._write_write_status_map(
                storage_dir,
                {
                    "gmail-live-001": "applied",
                    "gmail-live-002": "applied",
                },
            )

            stdout = io.StringIO()
            gmail_client = FakeInboxRemovalGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=io.StringIO("REMOVE\n"),
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            inbox_status = json.loads((storage_dir / "founder-test-batch-1_inbox_removal_status.json").read_text())
            inbox_attempts = json.loads((storage_dir / "founder-test-batch-1_inbox_removal_attempts.json").read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(gmail_client.calls, [("remove_inbox_label", "gmail-live-001")])
            self.assertEqual(inbox_status["gmail-live-001"], "applied")
            self.assertEqual(inbox_status["gmail-live-002"], "ineligible")
            self.assertEqual([entry["status"] for entry in inbox_attempts["gmail-live-001"]], ["applied"])
            self.assertEqual([entry["status"] for entry in inbox_attempts["gmail-live-002"]], ["ineligible"])
            self.assertIn("Eligible for INBOX removal: 1", stdout.getvalue())
            self.assertIn("Ineligible: 1", stdout.getvalue())
            self.assertIn("Type REMOVE to remove INBOX from eligible messages.", stdout.getvalue())

    def test_main_blocks_inbox_mutation_until_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <offers@example.com>",
                        "subject": "Weekend offer",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Promotional marketing email that looks low priority to review.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                    }
                ],
            )
            self._write_write_status_map(storage_dir, {"gmail-live-001": "applied"})

            stdout = io.StringIO()
            gmail_client = FakeInboxRemovalGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=io.StringIO("no\n"),
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(gmail_client.calls, [])
            self.assertFalse((storage_dir / "founder-test-batch-1_inbox_removal_status.json").exists())
            self.assertIn("No inbox labels were removed.", stdout.getvalue())

    def test_main_uses_gmail_modify_scope_for_inbox_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <offers@example.com>",
                        "subject": "Weekend offer",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Promotional marketing email that looks low priority to review.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                    }
                ],
            )
            self._write_write_status_map(storage_dir, {"gmail-live-001": "applied"})
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
                stdin=io.StringIO("REMOVE\n"),
                stdout=io.StringIO(),
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: self._capture_client(
                    FakeInboxRemovalGmailClient(),
                    captured_scope,
                    required_scope,
                ),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(captured_scope, ["https://www.googleapis.com/auth/gmail.modify"])

    def test_main_skips_low_value_messages_until_label_writeback_is_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <offers@example.com>",
                        "subject": "Weekend offer",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Promotional marketing email that looks low priority to review.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                    }
                ],
            )
            self._write_write_status_map(storage_dir, {"gmail-live-001": "failed"})

            stdout = io.StringIO()
            gmail_client = FakeInboxRemovalGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=io.StringIO("REMOVE\n"),
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            inbox_status = json.loads((storage_dir / "founder-test-batch-1_inbox_removal_status.json").read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(gmail_client.calls, [])
            self.assertEqual(inbox_status["gmail-live-001"], "skipped")
            self.assertIn("Eligible for INBOX removal: 0", stdout.getvalue())
            self.assertIn("Skipped until label write-back is applied: 1", stdout.getvalue())

    def _capture_client(
        self,
        gmail_client: FakeInboxRemovalGmailClient,
        captured_scope: list[str],
        required_scope: str,
    ) -> FakeInboxRemovalGmailClient:
        captured_scope.append(required_scope)
        return gmail_client


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

    def _write_write_status_map(self, storage_dir: Path, status_map: dict[str, str]) -> None:
        (storage_dir / "founder-test-batch-1_write_status.json").write_text(json.dumps(status_map, indent=2))


if __name__ == "__main__":
    unittest.main()
