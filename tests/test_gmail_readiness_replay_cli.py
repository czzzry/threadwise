import base64
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.gmail_readiness_replay_cli import main


class GmailReadinessReplayCliTests(unittest.TestCase):
    def test_replay_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/replay_gmail_readiness.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Replay current Gmail readiness", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_reports_pass_for_clean_stored_replay_and_closed_frontier(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                account_id="founder-test",
                provider="gmail",
                raw_messages=[
                    self._raw_message(
                        "gmail-001",
                        "Google <google-noreply@google.com>",
                        "Learn more about our updated Terms of Service",
                        "Terms of service update for your account.",
                        label_ids=["INBOX", "CATEGORY_UPDATES"],
                        list_unsubscribe="<mailto:unsubscribe@example.com>",
                    ),
                    self._raw_message(
                        "gmail-002",
                        '"Amazon.de" <shipment-tracking@amazon.de>',
                        "Shipped: Example order",
                        "Your package was shipped and track your package here.",
                        label_ids=["INBOX", "CATEGORY_UPDATES"],
                    ),
                ],
                items=[
                    self._stored_item(
                        "gmail-001",
                        "Google <google-noreply@google.com>",
                        "Learn more about our updated Terms of Service",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                    ),
                    self._stored_item(
                        "gmail-002",
                        '"Amazon.de" <shipment-tracking@amazon.de>',
                        "Shipped: Example order",
                        review_state="pending",
                        review_action=None,
                        final_labels=None,
                    ),
                ],
            )
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-2",
                account_id="founder-test",
                provider="gmail",
                raw_messages=[
                    self._raw_message(
                        "gmail-003",
                        "LinkedIn <messages-noreply@linkedin.com>",
                        "We received your report",
                        "We received your report. Track report status here.",
                        label_ids=["INBOX", "CATEGORY_SOCIAL"],
                    ),
                    self._raw_message(
                        "gmail-004",
                        '"Amazon.de" <shipment-tracking@amazon.de>',
                        "Out for delivery: Example order",
                        "Your package is out for delivery.",
                        label_ids=["INBOX", "CATEGORY_UPDATES"],
                    ),
                ],
                items=[
                    self._stored_item(
                        "gmail-003",
                        "LinkedIn <messages-noreply@linkedin.com>",
                        "We received your report",
                        review_state="reviewed",
                        review_action="auto-approve",
                        final_labels=["spam-low-value"],
                    ),
                    self._stored_item(
                        "gmail-004",
                        '"Amazon.de" <shipment-tracking@amazon.de>',
                        "Out for delivery: Example order",
                        review_state="reviewed",
                        review_action="auto-approve",
                        final_labels=["shopping-order"],
                    ),
                ],
            )
            self._write_write_status(
                storage_dir,
                "founder-test-batch-2",
                {
                    "gmail-003": "applied",
                    "gmail-004": "applied",
                },
            )
            self._write_inbox_status(
                storage_dir,
                "founder-test-batch-2",
                {
                    "gmail-003": "applied",
                    "gmail-004": "ineligible",
                },
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
            self.assertIn("Overall status: PASS", rendered)
            self.assertIn("Stored batches: 2", rendered)
            self.assertIn("Stored messages: 4", rendered)
            self.assertIn("Replay pass batches: 2", rendered)
            self.assertIn("Replay warn batches: 0", rendered)
            self.assertIn("Replay pause batches: 0", rendered)
            self.assertIn("Reviewed unlabeled history: 1", rendered)
            self.assertIn("Frontier remaining unlabeled: 0", rendered)
            self.assertIn("Mutation evidence verified batches: 1", rendered)
            self.assertIn("Mutation evidence missing batches: 1", rendered)
            self.assertIn(
                "PASS | founder-test-batch-1 | processed=2 | unlabeled=0 | rate=0.00% | evidence=MISSING",
                rendered,
            )
            self.assertIn(
                "PASS | founder-test-batch-2 | processed=2 | unlabeled=0 | rate=0.00% | evidence=VERIFIED",
                rendered,
            )

    def test_main_pauses_for_consecutive_threshold_breaches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                account_id="founder-test",
                provider="gmail",
                raw_messages=[
                    self._raw_message(
                        f"gmail-warn-{index}",
                        f"Unknown Sender {index} <unknown{index}@example.com>",
                        f"Unclassified message {index}",
                        "No known signals here.",
                    )
                    for index in range(6)
                ],
                items=[
                    self._stored_item(
                        f"gmail-warn-{index}",
                        f"Unknown Sender {index} <unknown{index}@example.com>",
                        f"Unclassified message {index}",
                        review_state="pending",
                        review_action=None,
                        final_labels=None,
                    )
                    for index in range(6)
                ],
            )
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-2",
                account_id="founder-test",
                provider="gmail",
                raw_messages=[
                    self._raw_message(
                        f"gmail-pause-{index}",
                        f"Another Unknown {index} <other{index}@example.com>",
                        f"Still unclassified {index}",
                        "No known signals here either.",
                    )
                    for index in range(6)
                ],
                items=[
                    self._stored_item(
                        f"gmail-pause-{index}",
                        f"Another Unknown {index} <other{index}@example.com>",
                        f"Still unclassified {index}",
                        review_state="pending",
                        review_action=None,
                        final_labels=None,
                    )
                    for index in range(6)
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
            self.assertIn("Overall status: PAUSE", rendered)
            self.assertIn("Replay pass batches: 0", rendered)
            self.assertIn("Replay warn batches: 1", rendered)
            self.assertIn("Replay pause batches: 1", rendered)
            self.assertIn(
                "WARN | founder-test-batch-1 | processed=6 | unlabeled=6 | rate=100.00% | evidence=MISSING",
                rendered,
            )
            self.assertIn(
                "PAUSE | founder-test-batch-2 | processed=6 | unlabeled=6 | rate=100.00% | evidence=MISSING",
                rendered,
            )

    def test_main_pauses_when_frontier_no_longer_closes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                account_id="founder-test",
                provider="gmail",
                raw_messages=[
                    self._raw_message(
                        "gmail-001",
                        "Unknown Sender <unknown@example.com>",
                        "Still unknown",
                        "No known signals here.",
                    )
                ],
                items=[
                    self._stored_item(
                        "gmail-001",
                        "Unknown Sender <unknown@example.com>",
                        "Still unknown",
                        review_state="reviewed",
                        review_action="edit",
                        final_labels=[],
                    )
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
            self.assertIn("Overall status: PAUSE", rendered)
            self.assertIn("Reviewed unlabeled history: 1", rendered)
            self.assertIn("Frontier remaining unlabeled: 1", rendered)

    def test_main_pauses_when_stored_mutation_evidence_shows_policy_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                batch_id="founder-test-batch-1",
                account_id="founder-test",
                provider="gmail",
                raw_messages=[
                    self._raw_message(
                        "gmail-001",
                        '"Amazon.de" <shipment-tracking@amazon.de>',
                        "Shipped: Example order",
                        "Your package was shipped and track your package here.",
                        label_ids=["INBOX", "CATEGORY_UPDATES"],
                    )
                ],
                items=[
                    self._stored_item(
                        "gmail-001",
                        '"Amazon.de" <shipment-tracking@amazon.de>',
                        "Shipped: Example order",
                        review_state="reviewed",
                        review_action="auto-approve",
                        final_labels=["shopping-order"],
                    )
                ],
            )
            self._write_write_status(storage_dir, "founder-test-batch-1", {"gmail-001": "applied"})
            self._write_inbox_status(storage_dir, "founder-test-batch-1", {"gmail-001": "applied"})

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
            self.assertIn("Overall status: PAUSE", rendered)
            self.assertIn("Mutation evidence violation batches: 1", rendered)
            self.assertIn(
                "PASS | founder-test-batch-1 | processed=1 | unlabeled=0 | rate=0.00% | evidence=VIOLATION",
                rendered,
            )

    def test_main_handles_missing_batches_cleanly(self) -> None:
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

            self.assertEqual(exit_code, 1)
            self.assertIn("No stored Gmail batches found for that account.", stdout.getvalue())

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        raw_messages: list[dict],
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
                    "raw_messages": raw_messages,
                    "items": items,
                    "fetch_failures": [],
                },
                indent=2,
            )
        )

    def _write_write_status(self, storage_dir: Path, batch_id: str, status_map: dict[str, str]) -> None:
        (storage_dir / f"{batch_id}_write_status.json").write_text(json.dumps(status_map, indent=2))

    def _write_inbox_status(self, storage_dir: Path, batch_id: str, status_map: dict[str, str]) -> None:
        (storage_dir / f"{batch_id}_inbox_removal_status.json").write_text(json.dumps(status_map, indent=2))

    def _raw_message(
        self,
        message_id: str,
        sender: str,
        subject: str,
        body: str,
        label_ids: list[str] | None = None,
        list_unsubscribe: str | None = None,
    ) -> dict:
        headers = [
            {"name": "From", "value": sender},
            {"name": "Subject", "value": subject},
            {"name": "Date", "value": "Mon, 23 Jun 2026 08:00:00 +0000"},
        ]
        if list_unsubscribe is not None:
            headers.append({"name": "List-Unsubscribe", "value": list_unsubscribe})
        encoded_body = base64.urlsafe_b64encode(body.encode("utf-8")).decode("ascii").rstrip("=")
        return {
            "id": message_id,
            "threadId": message_id,
            "labelIds": label_ids or ["INBOX"],
            "snippet": body,
            "payload": {
                "mimeType": "text/plain",
                "headers": headers,
                "body": {
                    "data": encoded_body,
                },
            },
            "internalDate": "1782192000000",
        }

    def _stored_item(
        self,
        message_id: str,
        sender: str,
        subject: str,
        review_state: str,
        review_action: str | None,
        final_labels: list[str] | None,
    ) -> dict:
        return {
            "source": "gmail",
            "account_id": "founder-test",
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "body": subject,
            "date": "2026-06-23T08:00:00Z",
            "review_state": review_state,
            "review_action": review_action,
            "final_labels": final_labels,
        }


if __name__ == "__main__":
    unittest.main()
