import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.gmail_readiness_check_cli import main


class GmailReadinessCheckCliTests(unittest.TestCase):
    def test_readiness_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/check_gmail_readiness.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Check whether a Gmail daily run still satisfies", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_reports_pass_for_latest_run_within_policy_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_report(
                storage_dir,
                "founder-test-batch-1",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-1",
                    "report_date": "2026-06-22",
                    "processed_count": 20,
                    "auto_applied_count": 18,
                    "inbox_removed_count": 5,
                    "classified_count": 18,
                    "unlabeled_count": 2,
                    "label_counts": {"EA/LowValue": 5, "EA/Orders": 10, "EA/Personal": 3},
                    "suggested_label_counts": {"EA/LowValue": 5, "EA/Orders": 10, "EA/Personal": 3},
                    "unlabeled_exceptions": [
                        {"sender": "Unknown A <a@example.com>", "subject": "Unknown A"},
                        {"sender": "Unknown B <b@example.com>", "subject": "Unknown B"},
                    ],
                },
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    self._reviewed_item("gmail-live-001", ["spam-low-value"]),
                    self._reviewed_item("gmail-live-002", ["shopping-order"]),
                    self._reviewed_item("gmail-live-003", ["personal"]),
                    self._pending_item("gmail-live-004"),
                    self._pending_item("gmail-live-005"),
                ],
            )
            self._write_json(storage_dir / "founder-test-batch-1_write_status.json", {"gmail-live-001": "applied"})
            self._write_json(storage_dir / "founder-test-batch-1_inbox_removal_status.json", {"gmail-live-001": "applied"})

            stdout = io.StringIO()
            exit_code = main(
                ["--account-id", "founder-test", "--storage-dir", temp_dir],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Status: PASS", rendered)
            self.assertIn("Batch: founder-test-batch-1", rendered)
            self.assertIn("Unlabeled exceptions: 2", rendered)
            self.assertIn("Exception rate: 10.00%", rendered)

    def test_main_returns_error_when_no_reports_exist_for_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()

            exit_code = main(
                ["--account-id", "founder-test", "--storage-dir", temp_dir],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 1)
            self.assertIn("No Gmail daily reports found for that account.", stdout.getvalue())

    def test_main_reports_warn_for_single_threshold_breach(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_report(
                storage_dir,
                "founder-test-batch-1",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-1",
                    "report_date": "2026-06-21",
                    "processed_count": 20,
                    "auto_applied_count": 20,
                    "inbox_removed_count": 4,
                    "classified_count": 20,
                    "unlabeled_count": 0,
                    "label_counts": {"EA/LowValue": 4},
                    "suggested_label_counts": {"EA/LowValue": 4},
                    "unlabeled_exceptions": [],
                },
            )
            self._write_batch(storage_dir, "founder-test-batch-1", [self._reviewed_item("gmail-live-001", ["spam-low-value"])])
            self._write_json(storage_dir / "founder-test-batch-1_write_status.json", {"gmail-live-001": "applied"})
            self._write_json(storage_dir / "founder-test-batch-1_inbox_removal_status.json", {"gmail-live-001": "applied"})

            self._write_report(
                storage_dir,
                "founder-test-batch-2",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-2",
                    "report_date": "2026-06-22",
                    "processed_count": 20,
                    "auto_applied_count": 14,
                    "inbox_removed_count": 3,
                    "classified_count": 14,
                    "unlabeled_count": 6,
                    "label_counts": {"EA/LowValue": 3, "EA/Orders": 11},
                    "suggested_label_counts": {"EA/LowValue": 3, "EA/Orders": 11},
                    "unlabeled_exceptions": [{"sender": "Unknown <u@example.com>", "subject": "Unknown"}] * 6,
                },
            )
            self._write_batch(storage_dir, "founder-test-batch-2", [self._reviewed_item("gmail-live-001", ["spam-low-value"])])
            self._write_json(storage_dir / "founder-test-batch-2_write_status.json", {"gmail-live-001": "applied"})
            self._write_json(storage_dir / "founder-test-batch-2_inbox_removal_status.json", {"gmail-live-001": "applied"})

            stdout = io.StringIO()
            exit_code = main(
                ["--account-id", "founder-test", "--storage-dir", temp_dir],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Status: WARN", stdout.getvalue())

    def test_main_can_check_specific_batch_instead_of_latest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_report(
                storage_dir,
                "founder-test-batch-1",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-1",
                    "report_date": "2026-06-21",
                    "processed_count": 20,
                    "auto_applied_count": 18,
                    "inbox_removed_count": 5,
                    "classified_count": 18,
                    "unlabeled_count": 2,
                    "label_counts": {"EA/LowValue": 5},
                    "suggested_label_counts": {"EA/LowValue": 5},
                    "unlabeled_exceptions": [{"sender": "Unknown <u@example.com>", "subject": "Unknown"}] * 2,
                },
            )
            self._write_batch(storage_dir, "founder-test-batch-1", [self._reviewed_item("gmail-live-001", ["spam-low-value"])])
            self._write_json(storage_dir / "founder-test-batch-1_write_status.json", {"gmail-live-001": "applied"})
            self._write_json(storage_dir / "founder-test-batch-1_inbox_removal_status.json", {"gmail-live-001": "applied"})

            self._write_report(
                storage_dir,
                "founder-test-batch-2",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-2",
                    "report_date": "2026-06-22",
                    "processed_count": 20,
                    "auto_applied_count": 14,
                    "inbox_removed_count": 3,
                    "classified_count": 14,
                    "unlabeled_count": 6,
                    "label_counts": {"EA/LowValue": 3},
                    "suggested_label_counts": {"EA/LowValue": 3},
                    "unlabeled_exceptions": [{"sender": "Unknown <u@example.com>", "subject": "Unknown"}] * 6,
                },
            )
            self._write_batch(storage_dir, "founder-test-batch-2", [self._reviewed_item("gmail-live-001", ["spam-low-value"])])
            self._write_json(storage_dir / "founder-test-batch-2_write_status.json", {"gmail-live-001": "applied"})
            self._write_json(storage_dir / "founder-test-batch-2_inbox_removal_status.json", {"gmail-live-001": "applied"})

            stdout = io.StringIO()
            exit_code = main(
                ["--account-id", "founder-test", "--storage-dir", temp_dir, "--batch-id", "founder-test-batch-1"],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Status: PASS", stdout.getvalue())
            self.assertIn("Batch: founder-test-batch-1", stdout.getvalue())

    def test_main_reports_pause_for_consecutive_threshold_breaches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            for batch_id, report_date in (("founder-test-batch-1", "2026-06-21"), ("founder-test-batch-2", "2026-06-22")):
                self._write_report(
                    storage_dir,
                    batch_id,
                    {
                        "account_id": "founder-test",
                        "provider": "gmail",
                        "batch_id": batch_id,
                        "report_date": report_date,
                        "processed_count": 20,
                        "auto_applied_count": 14,
                        "inbox_removed_count": 3,
                        "classified_count": 14,
                        "unlabeled_count": 6,
                        "label_counts": {"EA/LowValue": 3, "EA/Orders": 11},
                        "suggested_label_counts": {"EA/LowValue": 3, "EA/Orders": 11},
                        "unlabeled_exceptions": [{"sender": "Unknown <u@example.com>", "subject": "Unknown"}] * 6,
                    },
                )
                self._write_batch(storage_dir, batch_id, [self._reviewed_item("gmail-live-001", ["spam-low-value"])])
                self._write_json(storage_dir / f"{batch_id}_write_status.json", {"gmail-live-001": "applied"})
                self._write_json(storage_dir / f"{batch_id}_inbox_removal_status.json", {"gmail-live-001": "applied"})

            stdout = io.StringIO()
            exit_code = main(
                ["--account-id", "founder-test", "--storage-dir", temp_dir],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Status: PAUSE", stdout.getvalue())

    def test_main_reports_pause_when_inbox_removal_is_not_backed_by_low_value_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_report(
                storage_dir,
                "founder-test-batch-1",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-1",
                    "report_date": "2026-06-22",
                    "processed_count": 10,
                    "auto_applied_count": 10,
                    "inbox_removed_count": 1,
                    "classified_count": 10,
                    "unlabeled_count": 0,
                    "label_counts": {"EA/Orders": 10},
                    "suggested_label_counts": {"EA/Orders": 10},
                    "unlabeled_exceptions": [],
                },
            )
            self._write_batch(storage_dir, "founder-test-batch-1", [self._reviewed_item("gmail-live-001", ["shopping-order"])])
            self._write_json(storage_dir / "founder-test-batch-1_write_status.json", {"gmail-live-001": "applied"})
            self._write_json(storage_dir / "founder-test-batch-1_inbox_removal_status.json", {"gmail-live-001": "applied"})

            stdout = io.StringIO()
            exit_code = main(
                ["--account-id", "founder-test", "--storage-dir", temp_dir],
                stdout=stdout,
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("Status: PAUSE", stdout.getvalue())

    def _write_report(self, storage_dir: Path, batch_id: str, report: dict) -> None:
        reports_dir = storage_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{batch_id}_daily_report.json").write_text(json.dumps(report, indent=2))

    def _write_batch(self, storage_dir: Path, batch_id: str, items: list[dict]) -> None:
        batch_path = storage_dir / "batches" / f"{batch_id}.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "raw_messages": [],
                    "fetch_failures": [],
                    "items": items,
                },
                indent=2,
            )
        )

    def _reviewed_item(self, message_id: str, final_labels: list[str]) -> dict:
        return {
            "message_id": message_id,
            "sender": "Sender <sender@example.com>",
            "subject": "Subject",
            "date": "2026-06-22T10:00:00Z",
            "snippet": "",
            "body": "",
            "review_state": "reviewed",
            "review_action": "auto-approve",
            "final_labels": final_labels,
        }

    def _pending_item(self, message_id: str) -> dict:
        return {
            "message_id": message_id,
            "sender": "Sender <sender@example.com>",
            "subject": "Subject",
            "date": "2026-06-22T10:00:00Z",
            "snippet": "",
            "body": "",
            "review_state": "pending",
            "review_action": None,
            "final_labels": None,
        }

    def _write_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, indent=2))
