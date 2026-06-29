import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.local_batch_summary import load_batch, summarize_batch
from src.protonmail_fetch_cli import main
from src.review_loop import FixtureReviewLoop


class ProtonMailFetchCliTests(unittest.TestCase):
    def test_manual_fetch_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/manual_protonmail_fetch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Fetch ProtonMail export messages into the review queue", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_persists_provider_aware_batch_from_protonmail_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            export_path = storage_dir / "proton_export.json"
            export_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "pm-001",
                            "mailbox": "inbox",
                            "sender": "Bank Alerts <alerts@example-bank.com>",
                            "subject": "Your June statement is ready",
                            "date": "2026-06-19T08:00:00Z",
                            "snippet": "Your latest statement is ready to review.",
                            "body": "Your latest statement is ready to review in the app.",
                        }
                    ]
                )
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--source-path",
                    str(export_path),
                ],
                stdout=stdout,
            )

            batch_path = storage_dir / "batches" / "founder-proton-batch-1.json"
            stored_batch = load_batch(batch_path)
            summary = summarize_batch(storage_dir, stored_batch)
            review_loop = FixtureReviewLoop(fixtures_dir=storage_dir)
            loaded_batch = review_loop.load_review_queue(
                {
                    "batch_id": stored_batch["batch_id"],
                    "items": stored_batch["items"],
                }
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Fetched 1 new messages", stdout.getvalue())
            self.assertEqual(stored_batch["provider"], "protonmail")
            self.assertEqual(stored_batch["raw_messages"][0]["id"], "pm-001")
            self.assertEqual(stored_batch["items"][0]["message_id"], "pm-001")
            self.assertEqual(stored_batch["items"][0]["source"], "protonmail")
            self.assertEqual(stored_batch["items"][0]["account_id"], "founder-proton")
            self.assertEqual(summary["provider"], "protonmail")
            self.assertEqual(summary["item_count"], 1)
            self.assertEqual(loaded_batch["items"][0]["review_state"], "pending")

    def test_main_skips_already_processed_protonmail_messages_on_repeat_import(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            export_path = storage_dir / "proton_export.json"
            export_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "pm-001",
                            "mailbox": "inbox",
                            "sender": "Shop <orders@example.com>",
                            "subject": "Your order has shipped",
                            "date": "2026-06-19T08:00:00Z",
                            "snippet": "Your order has shipped.",
                            "body": "Tracking is now available.",
                        }
                    ]
                )
            )

            first_stdout = io.StringIO()
            second_stdout = io.StringIO()

            first_exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--source-path",
                    str(export_path),
                ],
                stdout=first_stdout,
            )
            second_exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--source-path",
                    str(export_path),
                ],
                stdout=second_stdout,
            )

            processed_ids = json.loads((storage_dir / "processed_message_ids.json").read_text())

            self.assertEqual(first_exit_code, 0)
            self.assertEqual(second_exit_code, 0)
            self.assertEqual(processed_ids, ["founder-proton:pm-001"])
            self.assertIn("No new messages found", second_stdout.getvalue())

    def test_main_decodes_rfc2047_sender_and_subject_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            export_path = storage_dir / "proton_export.json"
            export_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "pm-001",
                            "mailbox": "inbox",
                            "sender": "=?utf-8?q?Bj=C3=B6rn_from_Nuclino?= <hello@nuclino.com>",
                            "subject": "=?utf-8?q?You=E2=80=99re_now_on_Jira_Free_plan?=",
                            "date": "2026-06-19T08:00:00Z",
                            "snippet": "Welcome.",
                            "body": "Welcome.",
                        }
                    ]
                )
            )

            exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--source-path",
                    str(export_path),
                ],
                stdout=io.StringIO(),
            )

            stored_batch = load_batch(storage_dir / "batches" / "founder-proton-batch-1.json")

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["sender"], "Björn from Nuclino <hello@nuclino.com>")
            self.assertEqual(stored_batch["items"][0]["subject"], "You’re now on Jira Free plan")


if __name__ == "__main__":
    unittest.main()
