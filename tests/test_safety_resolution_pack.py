import io
import json
import tempfile
import unittest
from pathlib import Path

from src.safety_resolution_pack import build_safety_resolution_pack
from src.safety_resolution_pack_cli import main


class SafetyResolutionPackTests(unittest.TestCase):
    def test_build_resolution_pack_groups_legit_billing_and_scams(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proton_dir = root / "protonmail"
            outlook_dir = root / "outlookmail"
            self._write_batch(
                proton_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": '"Atlassian" <noreply@po.atlassian.net>',
                        "subject": "Add payment details before Jira Premium trial ends",
                        "snippet": "Add payment details before Jira Premium trial ends",
                        "body": "Add payment details before Jira Premium trial ends",
                    },
                    {
                        "message_id": "p2",
                        "sender": '"Atlassian Confluence" <noreply@po.atlassian.net>',
                        "subject": "Add payment details to keep your subscription",
                        "snippet": "Add payment details to keep your subscription",
                        "body": "Add payment details to keep your subscription",
                    },
                ],
            )
            self._write_batch(
                outlook_dir,
                "founder-hotmail-batch-6",
                "founder-hotmail",
                "outlookmail",
                [
                    {
                        "message_id": "o1",
                        "sender": "Purchase Confirmation",
                        "subject": "[Statement Review Account] Reminders : Invoice Payment Transaction",
                        "snippet": "You sent a payment of $45.00 USD to Google CHASE",
                        "body": "You sent a payment of $45.00 USD to Google CHASE",
                    },
                    {
                        "message_id": "o2",
                        "sender": "RewardsDeals",
                        "subject": "Grand Mondial Welcome Package",
                        "snippet": "Welcome Package reward claim",
                        "body": "Welcome Package reward claim",
                    },
                ],
            )
            report = {
                "providers": {
                    "protonmail": {
                        "outcomes": [
                                    self._build_outcome("protonmail", "founder-proton-batch-1", "p1", '"Atlassian" <noreply@po.atlassian.net>', "Add payment details before Jira Premium trial ends"),
                                    self._build_outcome("protonmail", "founder-proton-batch-1", "p2", '"Atlassian Confluence" <noreply@po.atlassian.net>', "Add payment details to keep your subscription"),
                        ]
                    },
                    "outlookmail": {
                        "outcomes": [
                                    self._build_outcome("outlookmail", "founder-hotmail-batch-6", "o1", "Purchase Confirmation", "[Statement Review Account] Reminders : Invoice Payment Transaction"),
                                    self._build_outcome("outlookmail", "founder-hotmail-batch-6", "o2", "RewardsDeals", "Grand Mondial Welcome Package"),
                        ]
                    },
                }
            }

            pack = build_safety_resolution_pack(
                report=report,
                provider_storage_dirs=[("protonmail", proton_dir), ("outlookmail", outlook_dir)],
            )

            self.assertEqual(pack["summary"]["candidate_count"], 3)
            self.assertEqual(pack["summary"]["not_safety_candidate_count"], 1)
            self.assertEqual(pack["summary"]["phishing_candidate_count"], 2)
            atlassian = next(item for item in pack["candidates"] if item["group_key"] == "noreply@po.atlassian.net")
            self.assertEqual(atlassian["suggested_disposition"], "not-safety")
            self.assertEqual(atlassian["message_count"], 2)

    def test_cli_writes_pack_and_prints_top_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proton_dir = root / "protonmail"
            self._write_batch(
                proton_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": '"Atlassian" <noreply@po.atlassian.net>',
                        "subject": "Add payment details before Jira Premium trial ends",
                        "snippet": "Add payment details before Jira Premium trial ends",
                        "body": "Add payment details before Jira Premium trial ends",
                    }
                ],
            )
            report_path = root / "report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "protonmail": {
                                "outcomes": [
                                    self._build_outcome(
                                        "protonmail",
                                        "founder-proton-batch-1",
                                        "p1",
                                        '"Atlassian" <noreply@po.atlassian.net>',
                                        "Add payment details before Jira Premium trial ends",
                                    )
                                ]
                            }
                        }
                    },
                    indent=2,
                )
            )
            stdout = io.StringIO()
            exit_code = main(
                [
                    "--report-path",
                    str(report_path),
                    "--protonmail-storage-dir",
                    str(proton_dir),
                    "--gmail-storage-dir",
                    str(root / "gmail"),
                    "--outlookmail-storage-dir",
                    str(root / "outlookmail"),
                    "--output-storage-dir",
                    str(root / "classifier_eval"),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Built safety resolution pack:", rendered)
            self.assertIn("Top candidate: protonmail | not-safety", rendered)
            self.assertIn("Saved pack:", rendered)

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        items: list[dict],
    ) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            item.setdefault("source", provider)
            item.setdefault("account_id", account_id)
            item.setdefault("date", "2026-06-28T00:00:00Z")
            item.setdefault("interpretation", "Informational message with no confident category.")
            item.setdefault("applied_labels", [])
            item.setdefault("near_misses", [])
            item.setdefault("confidence_band", "low")
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "items": items,
                },
                indent=2,
            )
        )

    def _build_outcome(self, provider: str, batch_id: str, message_id: str, sender: str, subject: str) -> dict:
        return {
            "provider": provider,
            "batch_id": batch_id,
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "decision": {"safety_lane": "suspicious"},
            "decision_provenance": {"safety_memory_used": False},
        }


if __name__ == "__main__":
    unittest.main()
