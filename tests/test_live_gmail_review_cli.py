import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_gmail_review_cli import main


class FakeWritableGmailClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.labels: dict[str, str] = {}

    def get_or_create_label(self, label_name: str) -> str:
        self.calls.append(("get_or_create_label", label_name))
        if label_name not in self.labels:
            self.labels[label_name] = f"Label_{len(self.labels) + 1}"
        return self.labels[label_name]

    def apply_labels(self, message_id: str, label_ids: list[str]) -> None:
        self.calls.append(("apply_labels", message_id, label_ids))


class LiveGmailReviewCliTests(unittest.TestCase):
    def test_review_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/review_live_gmail_batch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Review one stored live Gmail batch", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_shows_minimum_review_display_and_dry_run_summary_before_declined_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "19ed98609ae6f513",
                        "sender": "Google <no-reply@accounts.google.com>",
                        "subject": "Learn more about our updated Terms of Service",
                        "date": "2026-06-18T09:15:00Z",
                        "interpretation": "Matched account/service/update language.",
                        "applied_labels": ["account-security"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            stdin = io.StringIO("a\nno\n")
            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            stored_batch = json.loads(batch_path.read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["review_state"], "reviewed")
            self.assertEqual(stored_batch["items"][0]["review_action"], "approve")
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["spam-low-value"])
            self.assertEqual(gmail_client.calls, [])
            self.assertIn("Item 1 of 1", rendered)
            self.assertIn("Message ID: 19ed98609ae6f513", rendered)
            self.assertIn("From: Google <no-reply@accounts.google.com>", rendered)
            self.assertIn("Date: 2026-06-18", rendered)
            self.assertIn("Subject: Learn more about our updated Terms of Service", rendered)
            self.assertIn("Snippet:\nLearn more about our updated Terms of Service", rendered)
            self.assertIn("Suggested label:\nEA/LowValue", rendered)
            self.assertIn("Why:\nService update email that looks informational rather than action-worthy.", rendered)
            self.assertIn("Current decision:\npending", rendered)
            self.assertIn("[a] approve suggested label", rendered)
            self.assertIn("[e] edit label", rendered)
            self.assertIn("[r] reject / do not write", rendered)
            self.assertIn("[u] mark unlabeled", rendered)
            self.assertIn("[s] skip for now", rendered)
            self.assertIn("[q] quit without applying writes", rendered)
            self.assertIn("Allowed labels:", rendered)
            self.assertIn("1. EA/Travel", rendered)
            self.assertIn("7. EA/Account", rendered)
            self.assertIn("12. EA/NeedsAction", rendered)
            self.assertIn("Dry run summary:", rendered)
            self.assertIn("Approved writes: 1", rendered)
            self.assertIn("Rejected: 0", rendered)
            self.assertIn("Unlabeled: 0", rendered)
            self.assertIn("Labels to create/apply:", rendered)
            self.assertIn("EA/LowValue: 1 message", rendered)
            self.assertIn("No Gmail writes have happened yet.", rendered)
            self.assertIn("Type APPLY to apply these labels to Gmail.", rendered)
            self.assertIn("No Gmail labels were applied", rendered)

    def test_main_reprocesses_stored_live_batch_into_useful_suggestions_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                        "subject": "Father's Day Sale: Healthy Snacks and Grooming Essentials he'll love- Up to 40% Off",
                        "date": "2026-06-18T09:15:00Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "labelIds": ["CATEGORY_PROMOTIONS", "UNREAD", "INBOX"],
                        "snippet": "Free Shipping Available. Hurry, while supplies last. Up to 40% off.",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                                {
                                    "name": "Subject",
                                    "value": "Father's Day Sale: Healthy Snacks and Grooming Essentials he'll love- Up to 40% Off",
                                },
                                {"name": "Date", "value": "Thu, 18 Jun 2026 09:15:00 +0000"},
                                {
                                    "name": "List-Unsubscribe",
                                    "value": "<mailto:unsubscribe@example.com>, <https://example.com/unsub>",
                                },
                            ]
                        },
                    }
                ],
            )

            stdin = io.StringIO("s\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["applied_labels"], ["spam-low-value"])
            self.assertIn("Suggested label:\nEA/LowValue", rendered)
            self.assertIn("Why:\nPromotional marketing email that looks low priority to review.", rendered)

    def test_main_reprocesses_account_style_live_messages_into_ea_account_suggestions_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Google <no-reply@accounts.google.com>",
                        "subject": "Security alert",
                        "date": "2026-06-15T18:43:06Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "kasastefczyka@stefczykonline.pl",
                        "subject": "Kasa Stefczyka – dokumenty",
                        "date": "2026-06-16T08:31:42Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    },
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "labelIds": ["CATEGORY_UPDATES", "UNREAD", "INBOX"],
                        "snippet": (
                            "You allowed Google Auth Library access to some of your Google Account data. "
                            "If you didn't allow access, someone else may have access to your account."
                        ),
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Google <no-reply@accounts.google.com>"},
                                {"name": "Subject", "value": "Security alert"},
                                {"name": "Date", "value": "Mon, 15 Jun 2026 18:43:06 +0000"},
                            ]
                        },
                    },
                    {
                        "id": "gmail-live-002",
                        "labelIds": ["CATEGORY_UPDATES", "UNREAD", "INBOX"],
                        "snippet": (
                            "Szanowny Kliencie, przesylamy dokumenty dotyczace zlozonych dyspozycji. "
                            "Pliki zostaly zaszyfrowane."
                        ),
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "kasastefczyka@stefczykonline.pl"},
                                {"name": "Subject", "value": "Kasa Stefczyka – dokumenty"},
                                {"name": "Date", "value": "Tue, 16 Jun 2026 08:31:42 +0000"},
                            ]
                        },
                    },
                ],
            )

            stdin = io.StringIO("s\ns\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["applied_labels"], ["account-security"])
            self.assertEqual(stored_batch["items"][1]["applied_labels"], ["account-security"])
            self.assertIn("Suggested label:\nEA/Account", rendered)
            self.assertIn(
                "Why:\nAccount security or account-access alert that likely needs to stay easy to find.",
                rendered,
            )

    def test_main_keeps_weak_account_like_updates_unlabeled_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Example App <updates@example-app.com>",
                        "subject": "Your account update",
                        "date": "2026-06-16T08:31:42Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "labelIds": ["CATEGORY_UPDATES", "UNREAD", "INBOX"],
                        "snippet": "We refreshed a few settings in your account dashboard. No action is required.",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Example App <updates@example-app.com>"},
                                {"name": "Subject", "value": "Your account update"},
                                {"name": "Date", "value": "Tue, 16 Jun 2026 08:31:42 +0000"},
                            ]
                        },
                    }
                ],
            )

            stdin = io.StringIO("s\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["applied_labels"], [])

    def test_main_reprocesses_financial_statement_messages_into_ea_finance_suggestions_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Sun Life <sunlife@info.sunlife.ca>",
                        "subject": "Your statement is ready",
                        "date": "2026-06-19T08:00:00Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "labelIds": ["INBOX"],
                        "snippet": "View your investment statement online.",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Sun Life <sunlife@info.sunlife.ca>"},
                                {"name": "Subject", "value": "Your statement is ready"},
                                {"name": "Date", "value": "Thu, 19 Jun 2026 08:00:00 +0000"},
                            ]
                        },
                    }
                ],
            )

            stdin = io.StringIO("s\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["applied_labels"], ["financial-account"])
            self.assertIn("Suggested label:\nEA/Finance", stdout.getvalue())

    def test_main_reprocesses_linkedin_direct_messages_into_ea_personal_before_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Kirth Lammens via LinkedIn <messaging-digest-noreply@linkedin.com>",
                        "subject": "Kirth just messaged you",
                        "date": "2026-06-19T08:00:00Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "labelIds": ["INBOX", "CATEGORY_SOCIAL"],
                        "snippet": "1 new message awaits your response.",
                        "payload": {
                            "headers": [
                                {
                                    "name": "From",
                                    "value": "Kirth Lammens via LinkedIn <messaging-digest-noreply@linkedin.com>",
                                },
                                {"name": "Subject", "value": "Kirth just messaged you"},
                                {"name": "Date", "value": "Thu, 19 Jun 2026 08:00:00 +0000"},
                                {"name": "List-Unsubscribe", "value": "<https://www.linkedin.com/unsub>"},
                            ]
                        },
                    }
                ],
            )

            stdin = io.StringIO("s\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["applied_labels"], ["personal"])
            self.assertIn("Suggested label:\nEA/Personal", stdout.getvalue())

    def test_main_accepts_valid_edited_labels_by_number_and_ea_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            stdin = io.StringIO("e\n1,EA/Account\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["review_action"], "edit")
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["travel", "account-security"])
            self.assertIn("Enter label names or numbers separated by commas:", stdout.getvalue())
            self.assertIn("Allowed labels:", stdout.getvalue())

    def test_main_rejects_unknown_edited_labels_with_friendly_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            stdin = io.StringIO("e\nEA/Unknown\nEA/Account\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["account-security"])
            self.assertIn("Unknown label: EA/Unknown", stdout.getvalue())
            self.assertIn("Choose only from the allowed EA labels.", stdout.getvalue())

    def test_main_rejects_non_ea_edited_labels_with_friendly_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            stdin = io.StringIO("e\nPersonal/Keep\n12\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["reply-needed"])
            self.assertIn("Only EA/ labels are allowed here.", stdout.getvalue())

    def test_main_shows_allowed_labels_for_help_commands_and_makes_no_writes_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            stdin = io.StringIO("?\ne\nlabels\nEA/Account\nno\n")
            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            stored_batch = json.loads(batch_path.read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["account-security"])
            self.assertEqual(gmail_client.calls, [])
            self.assertGreaterEqual(rendered.count("Allowed labels:"), 2)
            self.assertIn("Type ? or labels to list allowed labels again.", rendered)

    def test_main_applies_confirmed_ea_labels_with_modify_scope_and_persists_write_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed", "job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            stdin = io.StringIO("a\nAPPLY\n")
            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()
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
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: self._capture_client(
                    gmail_client,
                    captured_scope,
                    required_scope,
                ),
            )

            write_status_path = storage_dir / "founder-test-batch-1_write_status.json"
            write_status = json.loads(write_status_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(captured_scope, ["https://www.googleapis.com/auth/gmail.modify"])
            self.assertEqual(
                gmail_client.calls,
                [
                    ("get_or_create_label", "EA/NeedsAction"),
                    ("get_or_create_label", "EA/Work"),
                    ("apply_labels", "gmail-live-001", ["Label_1", "Label_2"]),
                ],
            )
            self.assertEqual(write_status["gmail-live-001"], "applied")
            self.assertIn("Applied 1 reviewed Gmail label updates", stdout.getvalue())

    def test_main_quits_before_dry_run_and_persists_completed_reviews_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Approval needed today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Store <orders@example.com>",
                        "subject": "Your receipt",
                        "date": "2024-06-19T09:00:00Z",
                        "interpretation": "A purchase receipt.",
                        "applied_labels": ["receipt-billing"],
                        "near_misses": [],
                        "confidence_band": "high",
                    },
                ],
            )

            stdin = io.StringIO("a\nq\n")
            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["review_state"], "reviewed")
            self.assertEqual(stored_batch["items"][1]["review_state"], "pending")
            self.assertEqual(gmail_client.calls, [])
            self.assertIn("Quit before Gmail write-back", stdout.getvalue())

    def test_main_preserves_reviewed_items_when_reprocessing_stored_live_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed", "job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed", "job-related"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                        "subject": "Father's Day Sale is live",
                        "date": "2024-06-19T09:00:00Z",
                        "interpretation": "Informational message with no confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                    },
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "labelIds": ["INBOX", "UNREAD"],
                        "snippet": "Please review the budget update and reply today with your approval.",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Manager <boss@example.com>"},
                                {"name": "Subject", "value": "Need your approval today"},
                                {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                            ]
                        },
                    },
                    {
                        "id": "gmail-live-002",
                        "labelIds": ["INBOX", "CATEGORY_PROMOTIONS", "UNREAD"],
                        "snippet": "Free shipping this weekend. Hurry, while supplies last.",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                                {"name": "Subject", "value": "Father's Day Sale is live"},
                                {"name": "Date", "value": "Wed, 19 Jun 2024 09:00:00 +0000"},
                                {
                                    "name": "List-Unsubscribe",
                                    "value": "<mailto:unsubscribe@example.com>, <https://example.com/unsub>",
                                },
                            ]
                        },
                    },
                ],
            )

            stdin = io.StringIO("s\nno\n")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: FakeWritableGmailClient(),
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(stored_batch["items"][0]["review_state"], "reviewed")
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["reply-needed", "job-related"])
            self.assertEqual(stored_batch["items"][1]["applied_labels"], ["spam-low-value"])

    def test_main_applies_already_reviewed_browser_decisions_without_re_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Google <no-reply@accounts.google.com>",
                        "subject": "Security alert",
                        "date": "2026-06-15T18:43:06Z",
                        "interpretation": "Account security or account-access alert that likely needs to stay easy to find.",
                        "applied_labels": ["account-security"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": ["reply-needed", "account-security"],
                    }
                ],
            )

            stdin = io.StringIO("APPLY\n")
            stdout = io.StringIO()
            gmail_client = FakeWritableGmailClient()

            exit_code = main(
                [
                    "--batch-id",
                    "founder-test-batch-1",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdin=stdin,
                stdout=stdout,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            write_status = json.loads((storage_dir / "founder-test-batch-1_write_status.json").read_text())
            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertNotIn("Item 1 of 1", rendered)
            self.assertIn("Dry run summary:", rendered)
            self.assertIn("Approved writes: 1", rendered)
            self.assertEqual(
                gmail_client.calls,
                [
                    ("get_or_create_label", "EA/NeedsAction"),
                    ("get_or_create_label", "EA/Account"),
                    ("apply_labels", "gmail-live-001", ["Label_1", "Label_2"]),
                ],
            )
            self.assertEqual(write_status["gmail-live-001"], "applied")

    def _capture_client(
        self,
        gmail_client: FakeWritableGmailClient,
        captured_scope: list[str],
        required_scope: str,
    ) -> FakeWritableGmailClient:
        captured_scope.append(required_scope)
        return gmail_client

    def _write_batch(self, storage_dir: Path, items: list[dict], raw_messages: list[dict] | None = None) -> Path:
        batch_path = storage_dir / "batches" / "founder-test-batch-1.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": "founder-test-batch-1",
                    "account_id": "founder-test",
                    "raw_messages": raw_messages
                    or [
                        {
                            "id": item["message_id"],
                            "snippet": item.get("body", item["subject"]),
                        }
                        for item in items
                    ],
                    "fetch_failures": [],
                    "items": items,
                },
                indent=2,
            )
        )
        return batch_path


if __name__ == "__main__":
    unittest.main()
