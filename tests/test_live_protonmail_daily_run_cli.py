import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_protonmail_daily_run_cli import main


class FakeDailyRunProtonMailClient:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = {message["id"]: message for message in messages}

    def list_messages(self, max_results: int) -> list[str]:
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]


class LiveProtonMailDailyRunCliTests(unittest.TestCase):
    def test_daily_run_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/daily_live_protonmail_run.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Fetch and classify ProtonMail messages", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_exits_cleanly_when_no_new_messages_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                protonmail_client_factory=lambda account_id, credentials_dir, bridge_config_path: FakeDailyRunProtonMailClient([]),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("No new messages found.", stdout.getvalue())

    def test_main_fetches_classifies_and_writes_daily_report_without_provider_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            messages = [
                {
                    "id": "pm-live-001",
                    "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                    "subject": "Father's Day Sale starts now",
                    "date": "2026-04-29T23:06:47Z",
                    "snippet": "Weekly sale with unsubscribe link.",
                    "body": "Weekly sale with unsubscribe link.",
                    "mailbox": "inbox",
                    "list_unsubscribe": "<https://example.com/unsub>",
                },
                {
                    "id": "pm-live-002",
                    "sender": "\"Amazon.de\" <versandbestaetigung@amazon.de>",
                    "subject": "Dispatched: 'GEWAGE CO2 Bicycle Pump -...'",
                    "date": "2026-04-29T23:06:48Z",
                    "snippet": "Your package has shipped.",
                    "body": "Your package has shipped.",
                    "mailbox": "inbox",
                },
                {
                    "id": "pm-live-003",
                    "sender": "upGrad KnowledgeHut <mailer@certs.knowledgehut.com>",
                    "subject": "A reserved seat is available in your name",
                    "date": "2026-04-29T23:06:50Z",
                    "snippet": "A reserved seat is available in your name.",
                    "body": "A reserved seat is available in your name.",
                    "mailbox": "inbox",
                },
            ]

            exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=stdout,
                protonmail_client_factory=lambda account_id, credentials_dir, bridge_config_path: FakeDailyRunProtonMailClient(messages),
            )

            batch_path = Path(temp_dir) / "batches" / "founder-proton-batch-1.json"
            stored_batch = json.loads(batch_path.read_text())
            report_path = Path(temp_dir) / "reports" / "founder-proton-batch-1_daily_report.json"
            report = json.loads(report_path.read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(stored_batch["items"]), 3)
            self.assertIn("Batch: founder-proton-batch-1", rendered)
            self.assertIn("Fetched: 3", rendered)
            self.assertIn("Auto-applied label writes: 0", rendered)
            self.assertIn("INBOX removals: 0", rendered)
            self.assertIn("Classified messages: 3", rendered)
            self.assertIn("Unlabeled exceptions: 0", rendered)
            self.assertEqual(report["provider"], "protonmail")
            self.assertEqual(report["processed_count"], 3)
            self.assertEqual(report["auto_applied_count"], 0)
            self.assertEqual(report["inbox_removed_count"], 0)
            self.assertEqual(report["classified_count"], 3)
            self.assertEqual(
                report["suggested_label_counts"],
                {
                    "EA/LowValue": 2,
                    "EA/Orders": 1,
                },
            )
            self.assertEqual(report["unlabeled_count"], 0)
            self.assertEqual(report["unlabeled_exceptions"], [])


if __name__ == "__main__":
    unittest.main()
