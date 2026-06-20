import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_gmail_daily_run_cli import main


class FakeDailyRunGmailClient:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = {message["id"]: message for message in messages}
        self.calls: list[tuple] = []
        self.labels: dict[str, str] = {}

    def list_messages(self, label_ids: tuple[str, ...], max_results: int) -> list[str]:
        del label_ids
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]

    def get_or_create_label(self, label_name: str) -> str:
        self.calls.append(("get_or_create_label", label_name))
        if label_name not in self.labels:
            self.labels[label_name] = f"Label_{len(self.labels) + 1}"
        return self.labels[label_name]

    def apply_labels(self, message_id: str, label_ids: list[str]) -> None:
        self.calls.append(("apply_labels", message_id, label_ids))

    def remove_inbox_label(self, message_id: str) -> None:
        self.calls.append(("remove_inbox_label", message_id))


class LiveGmailDailyRunCliTests(unittest.TestCase):
    def test_daily_run_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/daily_live_gmail_run.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Fetch and auto-apply Gmail labels", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

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
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope=None: FakeDailyRunGmailClient([]),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("No new messages found.", stdout.getvalue())

    def test_main_fetches_auto_applies_and_reports_unlabeled_exceptions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            messages = [
                {
                    "id": "gmail-live-001",
                    "internalDate": "1777504007000",
                    "snippet": "Weekly sale with unsubscribe link.",
                    "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                            {"name": "Subject", "value": "Father's Day Sale starts now"},
                            {"name": "Date", "value": "Wed, 29 Apr 2026 23:06:47 +0000"},
                            {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                        ]
                    },
                },
                {
                    "id": "gmail-live-002",
                    "internalDate": "1777504008000",
                    "snippet": "Your package has shipped.",
                    "labelIds": ["INBOX", "CATEGORY_UPDATES"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "\"Amazon.de\" <versandbestaetigung@amazon.de>"},
                            {"name": "Subject", "value": "Dispatched: 'GEWAGE CO2 Bicycle Pump -...'"},
                            {"name": "Date", "value": "Wed, 29 Apr 2026 23:06:48 +0000"},
                        ]
                    },
                },
                {
                    "id": "gmail-live-003",
                    "internalDate": "1777504009000",
                    "snippet": "Kirth just messaged you.",
                    "labelIds": ["INBOX", "CATEGORY_SOCIAL"],
                    "payload": {
                        "headers": [
                            {
                                "name": "From",
                                "value": "Kirth Lammens via LinkedIn <messaging-digest-noreply@linkedin.com>",
                            },
                            {"name": "Subject", "value": "Kirth just messaged you"},
                            {"name": "Date", "value": "Wed, 29 Apr 2026 23:06:49 +0000"},
                            {"name": "List-Unsubscribe", "value": "<https://linkedin.com/unsub>"},
                        ]
                    },
                },
                {
                    "id": "gmail-live-004",
                    "internalDate": "1777504010000",
                    "snippet": "A reserved seat is available in your name.",
                    "labelIds": ["INBOX", "CATEGORY_UPDATES"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "upGrad KnowledgeHut <mailer@certs.knowledgehut.com>"},
                            {"name": "Subject", "value": "A reserved seat is available in your name"},
                            {"name": "Date", "value": "Wed, 29 Apr 2026 23:06:50 +0000"},
                        ]
                    },
                },
            ]

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
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope=None: FakeDailyRunGmailClient(messages),
            )

            batch_path = Path(temp_dir) / "batches" / "founder-test-batch-1.json"
            stored_batch = json.loads(batch_path.read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                [item["review_action"] for item in stored_batch["items"] if item.get("review_action") == "auto-approve"],
                ["auto-approve", "auto-approve", "auto-approve"],
            )
            self.assertEqual(
                sum(1 for item in stored_batch["items"] if item.get("review_state") != "reviewed"),
                1,
            )
            self.assertIn("Batch: founder-test-batch-1", rendered)
            self.assertIn("Fetched: 4", rendered)
            self.assertIn("Auto-applied label writes: 3", rendered)
            self.assertIn("INBOX removals: 1", rendered)
            self.assertIn("Classified messages: 3", rendered)
            self.assertIn("Unlabeled exceptions: 1", rendered)
            self.assertIn("upGrad KnowledgeHut <mailer@certs.knowledgehut.com> || A reserved seat is available in your name", rendered)

            report_path = Path(temp_dir) / "reports" / "founder-test-batch-1_daily_report.json"
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text())
            self.assertEqual(report["account_id"], "founder-test")
            self.assertEqual(report["batch_id"], "founder-test-batch-1")
            self.assertEqual(report["provider"], "gmail")
            self.assertEqual(report["processed_count"], 4)
            self.assertEqual(report["auto_applied_count"], 3)
            self.assertEqual(report["inbox_removed_count"], 1)
            self.assertEqual(report["classified_count"], 3)
            self.assertEqual(report["unlabeled_count"], 1)
            self.assertEqual(
                report["label_counts"],
                {
                    "EA/LowValue": 1,
                    "EA/Orders": 1,
                    "EA/Personal": 1,
                },
            )
            self.assertEqual(
                report["suggested_label_counts"],
                {
                    "EA/LowValue": 1,
                    "EA/Orders": 1,
                    "EA/Personal": 1,
                },
            )
            self.assertEqual(
                report["unlabeled_exceptions"],
                [
                    {
                        "sender": "upGrad KnowledgeHut <mailer@certs.knowledgehut.com>",
                        "subject": "A reserved seat is available in your name",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
