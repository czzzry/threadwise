import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.unlabeled_exception_report_cli import main


class UnlabeledExceptionReportCliTests(unittest.TestCase):
    def test_report_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/inspect_unlabeled_exception_clusters.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Inspect recurring reviewed unlabeled exceptions", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_groups_recurring_reviewed_unlabeled_exceptions_for_one_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                account_id="founder-test",
                provider="gmail",
                items=[
                    self._item(
                        "gmail-live-001",
                        "Sender One <sender@example.com>",
                        "Reminder 100 from Example",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                        body="Sensitive body 100",
                    ),
                    self._item(
                        "gmail-live-002",
                        "Store <orders@example.com>",
                        "Your order update",
                        review_state="reviewed",
                        review_action="approve",
                        final_labels=["shopping-order"],
                        body="Private order body",
                    ),
                ],
            )
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-2",
                account_id="founder-test",
                provider="gmail",
                items=[
                    self._item(
                        "gmail-live-003",
                        "Sender One <sender@example.com>",
                        "Reminder 101 from Example",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                        body="Sensitive body 101",
                    ),
                    self._item(
                        "gmail-live-004",
                        "Unique Sender <unique@example.com>",
                        "Only seen once",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                        body="Sensitive unique body",
                    ),
                ],
            )
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-3",
                account_id="founder-test",
                provider="gmail",
                items=[
                    self._item(
                        "gmail-live-005",
                        "Sender One <sender@example.com>",
                        "Reminder 102 from Example",
                        review_state="pending",
                        review_action=None,
                        final_labels=None,
                        body="Pending private body",
                    ),
                ],
            )
            self._write_batch(
                storage_dir,
                batch_id="other-account-batch-1",
                account_id="other-account",
                provider="gmail",
                items=[
                    self._item(
                        "gmail-live-006",
                        "Sender One <sender@example.com>",
                        "Reminder 103 from Example",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                        body="Other account private body",
                    ),
                ],
            )
            self._write_batch(
                storage_dir,
                batch_id="founder-proton-batch-1",
                account_id="founder-test",
                provider="protonmail",
                items=[
                    self._item(
                        "proton-live-001",
                        "Sender One <sender@example.com>",
                        "Reminder 104 from Example",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                        body="Proton private body",
                    ),
                ],
            )

            stdout = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("Account: founder-test", rendered)
            self.assertIn("Provider: gmail", rendered)
            self.assertIn("Reviewed unlabeled items: 3", rendered)
            self.assertIn("Recurring clusters: 1", rendered)
            self.assertIn("2 items | sender=Sender One <sender@example.com> | subject_pattern=reminder # from example", rendered)
            self.assertIn("Recent batches: founder-test-batch-2, founder-test-batch-1", rendered)
            self.assertIn("founder-test-batch-2 || Reminder 101 from Example", rendered)
            self.assertIn("founder-test-batch-1 || Reminder 100 from Example", rendered)
            self.assertNotIn("Sensitive body 100", rendered)
            self.assertNotIn("Only seen once", rendered)
            self.assertNotIn("Reminder 103 from Example", rendered)
            self.assertNotIn("Reminder 104 from Example", rendered)

    def test_main_handles_empty_or_non_recurring_reviewed_unlabeled_state_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Reviewed unlabeled items: 0", stdout.getvalue())
            self.assertIn("No recurring reviewed unlabeled exceptions found.", stdout.getvalue())

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                account_id="founder-test",
                provider="gmail",
                items=[
                    self._item(
                        "gmail-live-001",
                        "Unique Sender <unique@example.com>",
                        "Only seen once",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                        body="Sensitive unique body",
                    ),
                ],
            )

            stdout = io.StringIO()

            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                ],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Reviewed unlabeled items: 1", stdout.getvalue())
            self.assertIn("Recurring clusters: 0", stdout.getvalue())
            self.assertIn("No recurring reviewed unlabeled exceptions found.", stdout.getvalue())

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        items: list[dict],
    ) -> None:
        batch_path = storage_dir / "batches" / f"{batch_id}.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "raw_messages": [],
                    "fetch_failures": [],
                    "items": items,
                },
                indent=2,
            )
        )

    def _item(
        self,
        message_id: str,
        sender: str,
        subject: str,
        review_state: str,
        review_action: str | None,
        final_labels: list[str] | None,
        body: str,
    ) -> dict:
        return {
            "source": "gmail",
            "account_id": "founder-test",
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "body": body,
            "date": "2024-06-19T08:00:00Z",
            "review_state": review_state,
            "review_action": review_action,
            "final_labels": final_labels,
        }


if __name__ == "__main__":
    unittest.main()
