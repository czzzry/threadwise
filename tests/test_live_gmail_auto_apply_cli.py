import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.live_gmail_auto_apply_cli import main


class FakeAutoWritableGmailClient:
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

    def remove_inbox_label(self, message_id: str) -> None:
        self.calls.append(("remove_inbox_label", message_id))


class LiveGmailAutoApplyCliTests(unittest.TestCase):
    def test_auto_apply_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/auto_apply_live_gmail_batch.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Auto-apply Gmail labels", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_auto_applies_all_suggested_pending_items_and_keeps_unsuggested_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Promo <promo@example.com>",
                        "subject": "Low value noise",
                        "date": "2026-06-20T08:00:00Z",
                        "interpretation": "Low value.",
                        "applied_labels": ["spam-low-value"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "pending",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Amazon <order@example.com>",
                        "subject": "Your order receipt",
                        "date": "2026-06-20T08:01:00Z",
                        "interpretation": "Order record.",
                        "applied_labels": ["shopping-order"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "pending",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-003",
                        "sender": "LinkedIn <jobs-noreply@linkedin.com>",
                        "subject": "Your saved job is expiring",
                        "date": "2026-06-20T08:02:00Z",
                        "interpretation": "Job reminder.",
                        "applied_labels": ["job-related"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "pending",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-004",
                        "sender": "Friend <friend@example.com>",
                        "subject": "Lunch?",
                        "date": "2026-06-20T08:03:00Z",
                        "interpretation": "Personal message.",
                        "applied_labels": ["personal"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "pending",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-005",
                        "sender": "Bank <alerts@example.com>",
                        "subject": "Security alert",
                        "date": "2026-06-20T08:04:00Z",
                        "interpretation": "Account alert.",
                        "applied_labels": ["account-security"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "pending",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-006",
                        "sender": "Unknown <unknown@example.com>",
                        "subject": "Unclear message",
                        "date": "2026-06-20T08:05:00Z",
                        "interpretation": "No confident category.",
                        "applied_labels": [],
                        "near_misses": [],
                        "confidence_band": "low",
                        "review_state": "pending",
                    },
                ],
            )

            stdin = io.StringIO("AUTOAPPLY\n")
            stdout = io.StringIO()
            gmail_client = FakeAutoWritableGmailClient()

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
            approved_ids = {
                item["message_id"]
                for item in stored_batch["items"]
                if item.get("review_state") == "reviewed"
            }
            self.assertEqual(
                approved_ids,
                {"gmail-live-001", "gmail-live-002", "gmail-live-003", "gmail-live-004", "gmail-live-005"},
            )
            for item in stored_batch["items"]:
                if item["message_id"] in approved_ids:
                    self.assertEqual(item["review_action"], "auto-approve")
                    self.assertEqual(item["final_labels"], item["applied_labels"])
                if item["message_id"] == "gmail-live-006":
                    self.assertEqual(item["review_state"], "pending")

            self.assertIn(("remove_inbox_label", "gmail-live-001"), gmail_client.calls)
            self.assertNotIn(("remove_inbox_label", "gmail-live-002"), gmail_client.calls)
            self.assertNotIn(("remove_inbox_label", "gmail-live-003"), gmail_client.calls)
            self.assertNotIn(("remove_inbox_label", "gmail-live-004"), gmail_client.calls)
            self.assertNotIn(("remove_inbox_label", "gmail-live-005"), gmail_client.calls)
            self.assertIn("Auto-apply dry run:", rendered)
            self.assertIn("Eligible for auto-apply: 5", rendered)
            self.assertIn("Remaining pending review: 1", rendered)
            self.assertIn("Auto-applied Gmail label updates: 5", rendered)
            self.assertIn("Removed from INBOX: 1", rendered)

    def test_main_can_resume_previously_auto_approved_items_when_write_status_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = self._write_batch(
                storage_dir,
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Promo <promo@example.com>",
                        "subject": "Low value noise",
                        "date": "2026-06-20T08:00:00Z",
                        "interpretation": "Low value.",
                        "applied_labels": ["spam-low-value"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["spam-low-value"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Amazon <order@example.com>",
                        "subject": "Your order receipt",
                        "date": "2026-06-20T08:01:00Z",
                        "interpretation": "Order record.",
                        "applied_labels": ["shopping-order"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["shopping-order"],
                    },
                ],
            )

            stdin = io.StringIO("AUTOAPPLY\n")
            stdout = io.StringIO()
            gmail_client = FakeAutoWritableGmailClient()

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
            self.assertEqual(
                [call for call in gmail_client.calls if call[0] == "apply_labels"],
                [
                    ("apply_labels", "gmail-live-001", [gmail_client.labels["EA/LowValue"]]),
                    ("apply_labels", "gmail-live-002", [gmail_client.labels["EA/Orders"]]),
                ],
            )
            self.assertIn(("remove_inbox_label", "gmail-live-001"), gmail_client.calls)
            self.assertEqual(stored_batch["items"][0]["review_action"], "auto-approve")
            self.assertIn("Eligible for auto-apply: 2", rendered)
            self.assertIn("Auto-applied Gmail label updates: 2", rendered)

    def _write_batch(self, storage_dir: Path, items: list[dict]) -> Path:
        batch_path = storage_dir / "batches" / "founder-test-batch-1.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": "founder-test-batch-1",
                    "account_id": "founder-test",
                    "items": items,
                    "raw_messages": [],
                },
                indent=2,
            )
        )
        return batch_path


if __name__ == "__main__":
    unittest.main()
