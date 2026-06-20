import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_gmail_fetch_cli import DEFAULT_CREDENTIALS_DIR, DEFAULT_STORAGE_DIR, main
from src.live_gmail_client import SetupError
from src.review_loop import FixtureReviewLoop


class FakeGmailClient:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = {message["id"]: message for message in messages}

    def list_messages(self, label_ids: tuple[str, ...], max_results: int) -> list[str]:
        del label_ids
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        if message_id.endswith("002"):
            raise RuntimeError(f"Failed to fetch message {message_id}")
        return self._messages[message_id]


class LiveGmailFetchCliTests(unittest.TestCase):
    def test_manual_fetch_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/manual_gmail_fetch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Fetch live Gmail messages into the review queue", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_defaults_to_repo_data_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            stdout = io.StringIO()
            credentials_dir = repo_root / DEFAULT_CREDENTIALS_DIR
            storage_dir = repo_root / DEFAULT_STORAGE_DIR

            exit_code = main(
                ["--account-id", "founder-test"],
                stdout=stdout,
                cwd=repo_root,
                gmail_client_factory=lambda account_id, discovered_credentials_dir, client_secret_path: FakeGmailClient(
                    []
                ),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(credentials_dir, repo_root / "data" / "gmail_credentials")
            self.assertTrue(credentials_dir.exists())
            self.assertTrue(storage_dir.exists())
            self.assertIn("No new messages found", stdout.getvalue())

    def test_main_exits_cleanly_when_no_new_messages_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path: FakeGmailClient([]),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("No new messages found", stdout.getvalue())
            self.assertFalse((Path(temp_dir) / "batches").exists())

    def test_main_persists_review_ready_items_for_fetched_live_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            message = {
                "id": "gmail-live-001",
                "internalDate": "1718784000000",
                "snippet": "Please reply with approval today.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Manager <boss@example.com>"},
                        {"name": "Subject", "value": "Approval needed today"},
                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                    ]
                },
            }

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path: FakeGmailClient([message]),
            )

            batch_path = Path(temp_dir) / "batches" / "founder-test-batch-1.json"
            stored_batch = json.loads(batch_path.read_text())
            review_loop = FixtureReviewLoop(fixtures_dir=Path(temp_dir))
            review_queue = {
                "batch_id": stored_batch["batch_id"],
                "items": stored_batch["items"],
            }

            self.assertEqual(exit_code, 0)
            self.assertIn("Fetched 1 new messages", stdout.getvalue())
            self.assertEqual(stored_batch["raw_messages"][0]["id"], "gmail-live-001")
            self.assertEqual(stored_batch["items"][0]["message_id"], "gmail-live-001")
            self.assertEqual(stored_batch["items"][0]["source"], "gmail")
            self.assertEqual(stored_batch["provider"], "gmail")
            self.assertEqual(stored_batch["items"][0]["account_id"], "founder-test")

            loaded_batch = review_loop.load_review_queue(review_queue)

            self.assertEqual(loaded_batch["items"][0]["review_state"], "pending")

    def test_main_skips_already_processed_messages_by_account_and_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            message = {
                "id": "gmail-live-001",
                "internalDate": "1718784000000",
                "snippet": "Please reply with approval today.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Manager <boss@example.com>"},
                        {"name": "Subject", "value": "Approval needed today"},
                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                    ]
                },
            }

            first_exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path: FakeGmailClient([message]),
            )

            second_stdout = io.StringIO()
            second_exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=second_stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path: FakeGmailClient([message]),
            )

            processed_ids = json.loads((Path(temp_dir) / "processed_message_ids.json").read_text())

            self.assertEqual(first_exit_code, 0)
            self.assertEqual(second_exit_code, 0)
            self.assertEqual(processed_ids, ["founder-test:gmail-live-001"])
            self.assertIn("No new messages found", second_stdout.getvalue())

    def test_main_records_partial_fetch_failures_and_keeps_successful_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            working_message = {
                "id": "gmail-live-001",
                "internalDate": "1718784000000",
                "snippet": "Please reply with approval today.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Manager <boss@example.com>"},
                        {"name": "Subject", "value": "Approval needed today"},
                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                    ]
                },
            }
            failing_message = {
                "id": "gmail-live-002",
                "internalDate": "1718785000000",
                "snippet": "Suspicious sign-in attempt.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Security <alerts@example.com>"},
                        {"name": "Subject", "value": "Secure your account"},
                        {"name": "Date", "value": "Wed, 19 Jun 2024 09:00:00 +0000"},
                    ]
                },
            }

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                    "--batch-size",
                    "2",
                ],
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path: FakeGmailClient(
                    [working_message, failing_message]
                ),
            )

            batch_path = Path(temp_dir) / "batches" / "founder-test-batch-1.json"
            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual([item["message_id"] for item in stored_batch["items"]], ["gmail-live-001"])
            self.assertEqual(stored_batch["fetch_failures"][0]["message_id"], "gmail-live-002")
            self.assertIn("Fetched 1 new messages", stdout.getvalue())

    def test_main_shows_friendly_error_when_no_client_secret_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                stderr=stderr,
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("No OAuth client secret found", stderr.getvalue())
            self.assertIn("client_secret.json", stderr.getvalue())

    def test_main_shows_friendly_error_when_multiple_client_secrets_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()
            credentials_dir = Path(temp_dir)
            (credentials_dir / "client_secret_one.json").write_text("{}")
            (credentials_dir / "client_secret_two.json").write_text("{}")

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                stderr=stderr,
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("Multiple OAuth client secret files found", stderr.getvalue())
            self.assertIn("--client-secret-path", stderr.getvalue())

    def test_main_shows_friendly_ssl_setup_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                stderr=stderr,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path: self._raise_setup_error(),
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("Install Certificates.command", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def _raise_setup_error(self) -> FakeGmailClient:
        raise SetupError(
            "TLS certificate verification failed while talking to Google. "
            'Run: open "/Applications/Python 3.13/Install Certificates.command"'
        )


if __name__ == "__main__":
    unittest.main()
