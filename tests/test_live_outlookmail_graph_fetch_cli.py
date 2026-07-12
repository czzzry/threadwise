import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_outlookmail_graph_client import SetupError
from src.live_outlookmail_graph_fetch_cli import DEFAULT_CREDENTIALS_DIR, DEFAULT_STORAGE_DIR, main


class FakeLiveOutlookMailGraphClient:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = {message["id"]: message for message in messages}

    def list_messages(self, max_results: int) -> list[str]:
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]


class LiveOutlookMailGraphFetchCliTests(unittest.TestCase):
    def test_live_fetch_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/live_outlookmail_graph_fetch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Fetch live Outlook.com messages via Microsoft Graph", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_defaults_to_repo_data_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            stdout = io.StringIO()
            credentials_dir = repo_root / DEFAULT_CREDENTIALS_DIR
            storage_dir = repo_root / DEFAULT_STORAGE_DIR

            exit_code = main(
                ["--account-id", "founder-hotmail"],
                stdout=stdout,
                cwd=repo_root,
                outlookmail_client_factory=lambda account_id, discovered_credentials_dir, oauth_config_path: FakeLiveOutlookMailGraphClient(
                    []
                ),
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(credentials_dir.exists())
            self.assertTrue(storage_dir.exists())
            self.assertIn("No new messages found", stdout.getvalue())

    def test_main_persists_review_ready_items_for_live_outlook_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            message = {
                "id": "outlook-live-001",
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
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                outlookmail_client_factory=lambda account_id, credentials_dir, oauth_config_path: FakeLiveOutlookMailGraphClient(
                    [message]
                ),
            )

            batch_path = Path(temp_dir) / "batches" / "founder-hotmail-batch-1.json"
            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertIn("Fetched 1 new messages", stdout.getvalue())
            self.assertEqual(stored_batch["provider"], "outlookmail")
            self.assertEqual(stored_batch["raw_messages"][0]["id"], "outlook-live-001")
            self.assertEqual(stored_batch["items"][0]["message_id"], "outlook-live-001")
            self.assertEqual(stored_batch["items"][0]["source"], "outlookmail")

    def test_main_shows_friendly_error_when_oauth_config_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-hotmail",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                stderr=stderr,
                outlookmail_client_factory=lambda account_id, credentials_dir, oauth_config_path: self._raise_setup_error(),
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("No Outlook OAuth config found", stderr.getvalue())

    def _raise_setup_error(self):
        raise SetupError("No Outlook OAuth config found.")


if __name__ == "__main__":
    unittest.main()
