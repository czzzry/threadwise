import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.weekly_inbox_report_cli import main


class WeeklyInboxReportCliTests(unittest.TestCase):
    def test_weekly_report_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/weekly_inbox_report.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Generate a weekly inbox report", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_generates_weekly_report_from_daily_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            self._write_report(
                reports_dir / "founder-test-batch-21_daily_report.json",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-21",
                    "report_date": "2026-06-14",
                    "processed_count": 10,
                    "auto_applied_count": 8,
                    "inbox_removed_count": 4,
                    "classified_count": 8,
                    "unlabeled_count": 2,
                    "label_counts": {
                        "EA/LowValue": 4,
                        "EA/Orders": 2,
                        "EA/Work": 2,
                    },
                    "suggested_label_counts": {
                        "EA/LowValue": 4,
                        "EA/Orders": 2,
                        "EA/Work": 2,
                    },
                    "unlabeled_exceptions": [
                        {"sender": "List A <a@example.com>", "subject": "Unknown one"},
                        {"sender": "List B <b@example.com>", "subject": "Unknown two"},
                    ],
                },
            )
            self._write_report(
                reports_dir / "founder-test-batch-22_daily_report.json",
                {
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "batch_id": "founder-test-batch-22",
                    "report_date": "2026-06-16",
                    "processed_count": 20,
                    "auto_applied_count": 18,
                    "inbox_removed_count": 9,
                    "classified_count": 18,
                    "unlabeled_count": 2,
                    "label_counts": {
                        "EA/LowValue": 9,
                        "EA/Orders": 5,
                        "EA/Personal": 1,
                        "EA/Work": 3,
                    },
                    "suggested_label_counts": {
                        "EA/LowValue": 9,
                        "EA/Orders": 5,
                        "EA/Personal": 1,
                        "EA/Work": 3,
                    },
                    "unlabeled_exceptions": [
                        {"sender": "List C <c@example.com>", "subject": "Unknown three"},
                        {"sender": "List D <d@example.com>", "subject": "Unknown four"},
                    ],
                },
            )
            self._write_report(
                reports_dir / "other-batch_daily_report.json",
                {
                    "account_id": "other-account",
                    "provider": "gmail",
                    "batch_id": "other-batch",
                    "report_date": "2026-06-16",
                    "processed_count": 99,
                    "auto_applied_count": 99,
                    "inbox_removed_count": 99,
                    "classified_count": 99,
                    "unlabeled_count": 0,
                    "label_counts": {"EA/LowValue": 99},
                    "suggested_label_counts": {"EA/LowValue": 99},
                    "unlabeled_exceptions": [],
                },
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "--account-id",
                    "founder-test",
                    "--storage-dir",
                    temp_dir,
                    "--end-date",
                    "2026-06-20",
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            report_path = reports_dir / "founder-test_weekly_report_2026-06-14_2026-06-20.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(report_path.exists())

            report = json.loads(report_path.read_text())
            self.assertEqual(report["account_id"], "founder-test")
            self.assertEqual(report["provider"], "gmail")
            self.assertEqual(report["window_start"], "2026-06-14")
            self.assertEqual(report["window_end"], "2026-06-20")
            self.assertEqual(report["processed_count"], 30)
            self.assertEqual(report["auto_applied_count"], 26)
            self.assertEqual(report["inbox_removed_count"], 13)
            self.assertEqual(report["classified_count"], 26)
            self.assertEqual(report["unlabeled_count"], 4)
            self.assertEqual(report["exception_rate"], 0.1333)
            self.assertEqual(
                report["label_counts"],
                {
                    "EA/LowValue": 13,
                    "EA/Orders": 7,
                    "EA/Personal": 1,
                    "EA/Work": 5,
                },
            )
            self.assertEqual(
                report["suggested_label_counts"],
                {
                    "EA/LowValue": 13,
                    "EA/Orders": 7,
                    "EA/Personal": 1,
                    "EA/Work": 5,
                },
            )
            self.assertEqual(
                report["largest_categories"],
                [
                    {"label": "EA/LowValue", "count": 13},
                    {"label": "EA/Orders", "count": 7},
                    {"label": "EA/Work", "count": 5},
                ],
            )
            self.assertEqual(
                report["daily_trends"],
                [
                    {
                        "report_date": "2026-06-14",
                        "processed_count": 10,
                        "auto_applied_count": 8,
                        "inbox_removed_count": 4,
                        "classified_count": 8,
                        "unlabeled_count": 2,
                    },
                    {
                        "report_date": "2026-06-16",
                        "processed_count": 20,
                        "auto_applied_count": 18,
                        "inbox_removed_count": 9,
                        "classified_count": 18,
                        "unlabeled_count": 2,
                    },
                ],
            )
            self.assertIn("Account: founder-test", rendered)
            self.assertIn("Window: 2026-06-14 to 2026-06-20", rendered)
            self.assertIn("Processed: 30", rendered)
            self.assertIn("Exception rate: 13.33%", rendered)

    def test_main_generates_weekly_report_from_protonmail_daily_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)

            self._write_report(
                reports_dir / "founder-proton-batch-1_daily_report.json",
                {
                    "account_id": "founder-proton",
                    "provider": "protonmail",
                    "batch_id": "founder-proton-batch-1",
                    "report_date": "2026-06-18",
                    "processed_count": 3,
                    "auto_applied_count": 0,
                    "inbox_removed_count": 0,
                    "classified_count": 2,
                    "unlabeled_count": 1,
                    "label_counts": {},
                    "suggested_label_counts": {
                        "EA/LowValue": 1,
                        "EA/Orders": 1,
                    },
                    "unlabeled_exceptions": [
                        {"sender": "Unknown <u@example.com>", "subject": "Unknown one"},
                    ],
                },
            )
            self._write_report(
                reports_dir / "founder-proton-batch-2_daily_report.json",
                {
                    "account_id": "founder-proton",
                    "provider": "protonmail",
                    "batch_id": "founder-proton-batch-2",
                    "report_date": "2026-06-19",
                    "processed_count": 2,
                    "auto_applied_count": 0,
                    "inbox_removed_count": 0,
                    "classified_count": 1,
                    "unlabeled_count": 1,
                    "label_counts": {},
                    "suggested_label_counts": {
                        "EA/Personal": 1,
                    },
                    "unlabeled_exceptions": [
                        {"sender": "Unknown <v@example.com>", "subject": "Unknown two"},
                    ],
                },
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--end-date",
                    "2026-06-20",
                ],
                stdout=stdout,
            )

            report_path = reports_dir / "founder-proton_weekly_report_2026-06-14_2026-06-20.json"
            self.assertEqual(exit_code, 0)
            self.assertTrue(report_path.exists())

            report = json.loads(report_path.read_text())
            self.assertEqual(report["provider"], "protonmail")
            self.assertEqual(report["processed_count"], 5)
            self.assertEqual(report["auto_applied_count"], 0)
            self.assertEqual(report["inbox_removed_count"], 0)
            self.assertEqual(report["classified_count"], 3)
            self.assertEqual(report["unlabeled_count"], 2)
            self.assertEqual(report["label_counts"], {})
            self.assertEqual(
                report["suggested_label_counts"],
                {"EA/LowValue": 1, "EA/Orders": 1, "EA/Personal": 1},
            )

    def _write_report(self, path: Path, report: dict) -> None:
        path.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    unittest.main()
