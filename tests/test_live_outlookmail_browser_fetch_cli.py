import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_outlookmail_browser_client import SetupError
from src.live_outlookmail_browser_fetch_cli import DEFAULT_STORAGE_DIR, main


class FakeLiveOutlookMailBrowserClient:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = {message["id"]: message for message in messages}

    def list_messages(self, max_results: int) -> list[str]:
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]


class LiveOutlookMailBrowserFetchCliTests(unittest.TestCase):
    def test_live_fetch_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/live_outlookmail_browser_fetch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Fetch Outlook.com inbox rows from a signed-in local browser debug session", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_defaults_to_repo_data_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            stdout = io.StringIO()
            storage_dir = repo_root / DEFAULT_STORAGE_DIR

            exit_code = main(
                ["--account-id", "founder-hotmail"],
                stdout=stdout,
                cwd=repo_root,
                outlookmail_client_factory=lambda debug_base_url: FakeLiveOutlookMailBrowserClient([]),
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(storage_dir.exists())
            self.assertIn("No new messages found", stdout.getvalue())

    def test_main_persists_review_ready_items_for_visible_outlook_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            message = {
                "id": "outlook-row-001",
                "sender": "Manager <boss@example.com>",
                "subject": "Approval needed today",
                "date": "2026-06-19T08:00:00Z",
                "snippet": "Please reply with approval today.",
                "body": "Please reply with approval today.",
                "mailbox": "inbox",
            }

            exit_code = main(
                [
                    "--account-id",
                    "founder-hotmail",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
                outlookmail_client_factory=lambda debug_base_url: FakeLiveOutlookMailBrowserClient([message]),
            )

            batch_path = Path(temp_dir) / "batches" / "founder-hotmail-batch-1.json"
            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertIn("Fetched 1 new messages", stdout.getvalue())
            self.assertEqual(stored_batch["provider"], "outlookmail")
            self.assertEqual(stored_batch["raw_messages"][0]["id"], "outlook-row-001")
            self.assertEqual(stored_batch["items"][0]["message_id"], "outlook-row-001")
            self.assertEqual(stored_batch["items"][0]["source"], "outlookmail")

    def test_main_repeats_until_empty_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            messages = [
                {
                    "id": "outlook-row-001",
                    "sender": "One",
                    "subject": "First",
                    "date": "2026-06-19T08:00:00Z",
                    "snippet": "first",
                    "body": "first",
                    "mailbox": "inbox",
                },
                {
                    "id": "outlook-row-002",
                    "sender": "Two",
                    "subject": "Second",
                    "date": "2026-06-19T09:00:00Z",
                    "snippet": "second",
                    "body": "second",
                    "mailbox": "inbox",
                },
            ]

            exit_code = main(
                [
                    "--account-id",
                    "founder-hotmail",
                    "--storage-dir",
                    temp_dir,
                    "--batch-size",
                    "1",
                    "--repeat-until-empty",
                ],
                stdout=stdout,
                outlookmail_client_factory=lambda debug_base_url: FakeLiveOutlookMailBrowserClient(messages),
            )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Fetched 1 new messages into founder-hotmail-batch-1.", output)
            self.assertIn("Fetched 1 new messages into founder-hotmail-batch-2.", output)
            self.assertIn("Completed 2 batches totaling 2 new messages.", output)

    def test_main_stops_at_max_batches_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            messages = [
                {
                    "id": "outlook-row-001",
                    "sender": "One",
                    "subject": "First",
                    "date": "2026-06-19T08:00:00Z",
                    "snippet": "first",
                    "body": "first",
                    "mailbox": "inbox",
                },
                {
                    "id": "outlook-row-002",
                    "sender": "Two",
                    "subject": "Second",
                    "date": "2026-06-19T09:00:00Z",
                    "snippet": "second",
                    "body": "second",
                    "mailbox": "inbox",
                },
            ]

            exit_code = main(
                [
                    "--account-id",
                    "founder-hotmail",
                    "--storage-dir",
                    temp_dir,
                    "--batch-size",
                    "1",
                    "--repeat-until-empty",
                    "--max-batches",
                    "1",
                ],
                stdout=stdout,
                outlookmail_client_factory=lambda debug_base_url: FakeLiveOutlookMailBrowserClient(messages),
            )

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Fetched 1 new messages into founder-hotmail-batch-1.", output)
            self.assertIn("Stopped after 1 batches totaling 1 new messages.", output)

    def test_main_shows_friendly_error_when_browser_session_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-hotmail",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
                stderr=stderr,
                outlookmail_client_factory=lambda debug_base_url: self._raise_setup_error(),
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("No signed-in Outlook inbox tab", stderr.getvalue())

    def _raise_setup_error(self):
        raise SetupError("No signed-in Outlook inbox tab was found on the local browser debug port.")
