import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.fixture_classifier import CLASSIFIER_POLICY_VERSION
from src.live_protonmail_daily_run_cli import (
    _auto_apply_confident_labels,
    main,
    repair_stored_low_confidence_messages,
)


class FakeDailyRunProtonMailClient:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = {message["id"]: message for message in messages}
        self.label_calls: list[tuple[str, str]] = []

    def list_messages(self, max_results: int) -> list[str]:
        return list(self._messages)[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]

    def apply_label(self, message_id: str, label_name: str) -> dict:
        self.label_calls.append((message_id, label_name))
        return {
            "message_id": message_id,
            "label": label_name,
            "inbox_preserved": True,
            "destructive_actions": [],
        }

    def message_has_label(self, rfc_message_id: str, label_name: str) -> bool:
        return bool(rfc_message_id and label_name)


class LiveProtonMailDailyRunCliTests(unittest.TestCase):
    def test_daily_run_script_loads_repo_local_environment(self) -> None:
        script = (Path(__file__).resolve().parent.parent / "scripts" / "daily_live_protonmail_run.py").read_text()

        self.assertIn("from src.local_environment import load_local_environment", script)
        self.assertIn("load_local_environment(REPO_ROOT)", script)

    def test_main_passes_configured_model_classifier_to_proton_run(self) -> None:
        configured_classifier = object()
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {"THREADWISE_CLASSIFICATION_MODEL": "gpt-test"},
        ), patch(
            "src.live_protonmail_daily_run_cli.configure_initial_classifier",
            return_value=(configured_classifier, {"state": "ready", "model": "gpt-test"}),
        ) as configure, patch(
            "src.live_protonmail_daily_run_cli.run_live_protonmail_daily_batch",
            return_value=None,
        ) as run:
            exit_code = main(
                [
                    "--account-id",
                    "founder-proton",
                    "--storage-dir",
                    temp_dir,
                    "--credentials-dir",
                    temp_dir,
                ],
                stdout=io.StringIO(),
                protonmail_client_factory=lambda *_args: FakeDailyRunProtonMailClient([]),
            )

        self.assertEqual(exit_code, 0)
        configure.assert_called_once()
        self.assertIs(run.call_args.kwargs["classifier"], configured_classifier)

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

    def test_auto_apply_labels_low_confidence_messages_and_skips_only_missing_labels(self) -> None:
        client = FakeDailyRunProtonMailClient([])
        batch = {
            "raw_messages": [
                {"id": "high", "rfc_message_id": "<high@example.com>"},
                {"id": "low", "rfc_message_id": "<low@example.com>"},
                {"id": "unlabeled", "rfc_message_id": "<unlabeled@example.com>"},
            ],
            "items": [
                {"message_id": "high", "confidence_band": "high", "applied_labels": ["personal"]},
                {"message_id": "low", "confidence_band": "low", "applied_labels": ["personal"]},
                {"message_id": "unlabeled", "confidence_band": "low", "applied_labels": []},
            ],
        }

        applied_count, failure_count = _auto_apply_confident_labels(client, batch)

        self.assertEqual((applied_count, failure_count), (2, 0))
        self.assertEqual(client.label_calls, [("high", "EA/Personal"), ("low", "EA/Personal")])
        self.assertEqual(
            [item["provider_write_state"] for item in batch["items"]],
            ["applied", "applied", "not-attempted"],
        )

    def test_main_auto_applies_confident_labels_and_writes_daily_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            messages = [
                {
                    "id": "pm-live-001",
                    "rfc_message_id": "<pm-live-001@example.com>",
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
                    "rfc_message_id": "<pm-live-002@example.com>",
                    "sender": "\"Amazon.de\" <versandbestaetigung@amazon.de>",
                    "subject": "Dispatched: 'GEWAGE CO2 Bicycle Pump -...'",
                    "date": "2026-04-29T23:06:48Z",
                    "snippet": "Your package has shipped.",
                    "body": "Your package has shipped.",
                    "mailbox": "inbox",
                },
                {
                    "id": "pm-live-003",
                    "rfc_message_id": "<pm-live-003@example.com>",
                    "sender": "upGrad KnowledgeHut <mailer@certs.knowledgehut.com>",
                    "subject": "A reserved seat is available in your name",
                    "date": "2026-04-29T23:06:50Z",
                    "snippet": "A reserved seat is available in your name.",
                    "body": "A reserved seat is available in your name.",
                    "mailbox": "inbox",
                },
            ]

            client = FakeDailyRunProtonMailClient(messages)
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
                protonmail_client_factory=lambda account_id, credentials_dir, bridge_config_path: client,
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
            self.assertIn("Provider label writes: 3 (Inbox preserved and verified)", rendered)
            self.assertIn("INBOX removals: 0", rendered)
            self.assertIn("Suggested labels ready for review: 3", rendered)
            self.assertIn("Needs a label decision: 0", rendered)
            self.assertIn("Provider write verification failures for review: 0", rendered)
            self.assertIn("Open Threadwise in Proton Mail: https://mail.proton.me/", rendered)
            self.assertEqual(report["provider"], "protonmail")
            self.assertEqual(report["processed_count"], 3)
            self.assertEqual(report["auto_applied_count"], 3)
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

            ledger_path = Path(temp_dir) / "live_manual_review_ledger.json"
            ledger = json.loads(ledger_path.read_text())
            self.assertEqual(set(ledger["messages"]), {"pm-live-001", "pm-live-002", "pm-live-003"})
            self.assertEqual(ledger["messages"]["pm-live-002"]["labels"], ["EA/Orders"])
            self.assertCountEqual(
                client.label_calls,
                [
                    ("pm-live-001", "EA/LowValue"),
                    ("pm-live-002", "EA/Orders"),
                    ("pm-live-003", "EA/LowValue"),
                ],
            )
            self.assertEqual(ledger["messages"]["pm-live-001"]["status"], "provider-confirmed")

    def test_repair_reclassifies_unresolved_old_items_without_refetching_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_dir = storage_dir / "batches"
            batch_dir.mkdir(parents=True)
            batch = {
                "batch_id": "founder-proton-batch-1",
                "account_id": "founder-proton",
                "provider": "protonmail",
                "raw_messages": [
                    {
                        "id": "dhl-1",
                        "rfc_message_id": "<dhl-1@example.com>",
                        "sender": "DHL Paket <noreply@dhl.de>",
                        "subject": "Ihre YunExpress Sendung ist unterwegs",
                        "date": "2026-08-05T10:00:00Z",
                        "snippet": "Ihre Sendung ist unterwegs.",
                        "body": "Ihre Sendung ist unterwegs.",
                    }
                ],
                "items": [
                    {
                        "message_id": "dhl-1",
                        "sender": "DHL Paket <noreply@dhl.de>",
                        "subject": "Ihre YunExpress Sendung ist unterwegs",
                        "date": "2026-08-05T10:00:00Z",
                        "confidence_band": "low",
                        "applied_labels": [],
                    }
                ],
            }
            (batch_dir / "founder-proton-batch-1.json").write_text(json.dumps(batch))
            client = FakeDailyRunProtonMailClient([{"id": "dhl-1"}])

            result = repair_stored_low_confidence_messages(
                account_id="founder-proton",
                batch_size=25,
                storage_dir=storage_dir,
                protonmail_client=client,
            )

            stored = json.loads((batch_dir / "founder-proton-batch-1.json").read_text())
            item = stored["items"][0]
            self.assertEqual(result["reprocessed_count"], 1)
            self.assertEqual(result["auto_applied_count"], 1)
            self.assertEqual(client.label_calls, [("dhl-1", "EA/Orders")])
            self.assertEqual(item["applied_labels"], ["shopping-order"])
            self.assertEqual(item["classifier_policy_version"], CLASSIFIER_POLICY_VERSION)

    def test_repair_retries_current_policy_unlabeled_item_with_configured_classifier(self) -> None:
        class ConfiguredClassifier:
            def classify_messages(self, batch_id, messages):
                message = messages[0]
                return {
                    "batch_id": batch_id,
                    "items": [{
                        "message_id": message["message_id"],
                        "sender": message["sender"],
                        "subject": message["subject"],
                        "confidence_band": "low",
                        "applied_labels": ["shopping-order"],
                        "review_state": "pending",
                        "classifier_policy_version": CLASSIFIER_POLICY_VERSION,
                    }],
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_dir = storage_dir / "batches"
            batch_dir.mkdir(parents=True)
            batch = {
                "batch_id": "founder-proton-batch-1",
                "account_id": "founder-proton",
                "provider": "protonmail",
                "raw_messages": [{
                    "id": "retry-1",
                    "rfc_message_id": "<retry-1@example.com>",
                    "sender": "DHL Paket <noreply@dhl.de>",
                    "subject": "Your parcel is moving",
                    "date": "2026-08-05T10:00:00Z",
                    "body": "Your package is on its way.",
                }],
                "items": [{
                    "message_id": "retry-1",
                    "confidence_band": "low",
                    "applied_labels": [],
                    "classifier_policy_version": CLASSIFIER_POLICY_VERSION,
                }],
            }
            (batch_dir / "founder-proton-batch-1.json").write_text(json.dumps(batch))
            client = FakeDailyRunProtonMailClient([{"id": "retry-1"}])

            result = repair_stored_low_confidence_messages(
                account_id="founder-proton",
                batch_size=25,
                storage_dir=storage_dir,
                protonmail_client=client,
                classifier=ConfiguredClassifier(),
            )

            self.assertEqual(result["reprocessed_count"], 1)
            self.assertEqual(result["auto_applied_count"], 1)
            self.assertEqual(client.label_calls, [("retry-1", "EA/Orders")])

    def test_repair_does_not_revisit_user_reviewed_unlabeled_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_dir = storage_dir / "batches"
            batch_dir.mkdir(parents=True)
            batch = {
                "batch_id": "founder-proton-batch-1",
                "account_id": "founder-proton",
                "provider": "protonmail",
                "raw_messages": [{"id": "reviewed", "rfc_message_id": "<reviewed@example.com>"}],
                "items": [
                    {
                        "message_id": "reviewed",
                        "confidence_band": "low",
                        "applied_labels": [],
                        "review_state": "reviewed",
                    }
                ],
            }
            (batch_dir / "founder-proton-batch-1.json").write_text(json.dumps(batch))
            client = FakeDailyRunProtonMailClient([{"id": "reviewed"}])

            result = repair_stored_low_confidence_messages(
                account_id="founder-proton",
                batch_size=25,
                storage_dir=storage_dir,
                protonmail_client=client,
            )

            self.assertEqual(result["reprocessed_count"], 0)
            self.assertEqual(client.label_calls, [])


if __name__ == "__main__":
    unittest.main()
