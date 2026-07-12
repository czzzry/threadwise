import json
import tempfile
import unittest
from pathlib import Path

from src.classifier_corpus_eval import build_classifier_corpus_report


class ClassifierCorpusEvalTests(unittest.TestCase):
    def test_report_separates_reviewed_gmail_benchmark_from_protonmail_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            protonmail_dir = root / "protonmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Amazon.de" <order-update@amazon.de>',
                        "subject": "Delivery attempted with your Amazon package.",
                        "snippet": "Unfortunately, DHL ran into an issue when attempting your delivery.",
                        "body": "Delivery attempted with your Amazon package. Track your delivery.",
                        "review_state": "reviewed",
                        "final_labels": ["shopping-order"],
                    }
                ],
            )
            self._write_batch(
                protonmail_dir,
                "personal-proton-batch-1",
                "personal-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Amazon <account-update@amazon.ca>",
                        "subject": "Passkey added to your account",
                        "snippet": "A passkey was added to your Amazon account.",
                        "body": "A passkey was added to your Amazon account.",
                    },
                    {
                        "message_id": "p2",
                        "sender": "Mystery Sender <mystery@example.com>",
                        "subject": "A vague note",
                        "snippet": "Just a vague note.",
                        "body": "Just a vague note.",
                    },
                ],
            )

            report = build_classifier_corpus_report(
                [
                    ("gmail", gmail_dir),
                    ("protonmail", protonmail_dir),
                ]
            )

            gmail = report["providers"]["gmail"]
            protonmail = report["providers"]["protonmail"]
            eval_contract = report["eval_contract"]

            self.assertEqual(gmail["total_count"], 1)
            self.assertEqual(gmail["reviewed_count"], 1)
            self.assertEqual(gmail["shadow_count"], 0)
            self.assertEqual(gmail["reviewed_metrics"]["exact_match_count"], 1)
            self.assertEqual(gmail["label_counts"]["shopping-order"], 1)
            self.assertEqual(gmail["evidence_bucket_counts"]["reviewed_benchmark"], 1)
            self.assertEqual(gmail["evidence_bucket_counts"]["shadow_total"], 0)

            self.assertEqual(protonmail["total_count"], 2)
            self.assertEqual(protonmail["reviewed_count"], 0)
            self.assertEqual(protonmail["shadow_count"], 2)
            self.assertNotIn("reviewed_metrics", protonmail)
            self.assertEqual(protonmail["label_counts"]["account-security"], 1)
            self.assertEqual(protonmail["unlabeled_count"], 1)
            self.assertEqual(protonmail["evidence_bucket_counts"]["reviewed_benchmark"], 0)
            self.assertEqual(protonmail["evidence_bucket_counts"]["shadow_total"], 2)
            self.assertEqual(protonmail["top_unlabeled_families"][0]["sender_key"], "mystery@example.com")
            self.assertEqual(
                sum(split["total_count"] for split in protonmail["split_counts"].values()),
                protonmail["total_count"],
            )
            self.assertEqual(
                set(protonmail["top_unlabeled_families_by_split"]),
                {"discovery", "validation", "holdout"},
            )
            self.assertEqual(
                set(protonmail["top_shadow_unlabeled_families_by_split"]),
                {"discovery", "validation", "holdout"},
            )
            self.assertEqual(
                eval_contract["current_doc"],
                "docs/current-multi-inbox-eval-contract-2026-06-28.md",
            )
            self.assertEqual(eval_contract["corpora"]["gmail_reviewed_history"]["kind"], "reviewed-benchmark")
            self.assertEqual(
                eval_contract["corpora"]["protonmail_shadow"]["contamination_status"],
                "partially-exposed-pre-split",
            )
            self.assertEqual(
                eval_contract["corpora"]["outlookmail_shadow"]["contamination_status"],
                "debug-inspected",
            )
            self.assertEqual(eval_contract["shadow_split"]["shares"]["discovery"], 50)

    def test_report_assigns_same_sender_subject_family_to_one_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            protonmail_dir = Path(temp_dir) / "protonmail"
            self._write_batch(
                protonmail_dir,
                "personal-proton-batch-1",
                "personal-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Statements <statements@example.com>",
                        "subject": "Your statement 123 is available",
                        "snippet": "Statement is available.",
                        "body": "Statement is available.",
                    },
                    {
                        "message_id": "p2",
                        "sender": "Statements <statements@example.com>",
                        "subject": "Your statement 456 is available",
                        "snippet": "Statement is available.",
                        "body": "Statement is available.",
                    },
                ],
            )

            report = build_classifier_corpus_report([("protonmail", protonmail_dir)])

            family_splits = report["providers"]["protonmail"]["family_splits"]
            matching_families = [
                family
                for family in family_splits
                if family["sender_key"] == "statements@example.com"
                and family["subject_key"] == "your statement # is available"
            ]

            self.assertEqual(len(matching_families), 1)
            self.assertEqual(matching_families[0]["count"], 2)

    def test_report_forces_exposed_families_into_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            protonmail_dir = Path(temp_dir) / "protonmail"
            self._write_batch(
                protonmail_dir,
                "personal-proton-batch-1",
                "personal-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Statements <statements@example.com>",
                        "subject": "Your statement is available",
                        "snippet": "Statement is available.",
                        "body": "Statement is available.",
                    }
                ],
            )

            report = build_classifier_corpus_report(
                [("protonmail", protonmail_dir)],
                exposed_families={
                    "protonmail": {
                        ("statements@example.com", "your statement is available"),
                    }
                },
            )

            family = report["providers"]["protonmail"]["family_splits"][0]

            self.assertEqual(family["split"], "discovery")
            self.assertTrue(family["exposed"])

    def test_report_tracks_shadow_bucket_counts_separately_from_reviewed_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "Known <known@example.com>",
                        "subject": "Reviewed message",
                        "snippet": "Reviewed snippet.",
                        "body": "Reviewed body.",
                        "review_state": "reviewed",
                        "final_labels": [],
                    },
                    {
                        "message_id": "g2",
                        "sender": "New <new@example.com>",
                        "subject": "Unreviewed message",
                        "snippet": "Unreviewed snippet.",
                        "body": "Unreviewed body.",
                    },
                ],
            )

            report = build_classifier_corpus_report([("gmail", gmail_dir)])
            buckets = report["providers"]["gmail"]["evidence_bucket_counts"]

            self.assertEqual(buckets["reviewed_benchmark"], 1)
            self.assertEqual(buckets["shadow_total"], 1)
            self.assertEqual(
                buckets["shadow_discovery"] + buckets["shadow_validation"] + buckets["shadow_holdout"],
                buckets["shadow_total"],
            )
            shadow_families = []
            for split in ("discovery", "validation", "holdout"):
                shadow_families.extend(report["providers"]["gmail"]["top_shadow_unlabeled_families_by_split"][split])
            self.assertEqual([family["sender_key"] for family in shadow_families], ["new@example.com"])

    def test_report_ignores_mismatched_provider_batches_in_storage_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gmail_dir = Path(temp_dir) / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "Known <known@example.com>",
                        "subject": "Reviewed message",
                        "snippet": "Reviewed snippet.",
                        "body": "Reviewed body.",
                    }
                ],
            )
            self._write_batch(
                gmail_dir,
                "founder-proton-batch-1",
                "founder-proton",
                "protonmail",
                [
                    {
                        "message_id": "p1",
                        "sender": "Proton <confirm@example.com>",
                        "subject": "Verify your email",
                        "snippet": "Verify your email.",
                        "body": "Verify your email.",
                    }
                ],
            )

            report = build_classifier_corpus_report([("gmail", gmail_dir)])

            self.assertEqual(report["providers"]["gmail"]["total_count"], 1)
            self.assertEqual(report["providers"]["gmail"]["shadow_count"], 1)

    def test_report_projects_approved_safety_memory_and_false_hide_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gmail_dir = Path(temp_dir) / "gmail"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                        "subject": "Service report 123456",
                        "snippet": "Open attached report.",
                        "body": "Open attached report.",
                    },
                    {
                        "message_id": "g2",
                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                        "subject": "Service report 999999",
                        "snippet": "Open attached report.",
                        "body": "Open attached report.",
                    },
                ],
            )
            (gmail_dir / "safety_dispositions.json").write_text(
                json.dumps(
                    {
                        "status": "PROTOTYPE - local safety review dispositions",
                        "generated_at": "2026-06-28T00:00:00Z",
                        "disposition_count": 1,
                        "dispositions": [
                            {
                                "id": "safety-gmail-sender-phishing-alerts-pestsolutions-test",
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "source_batch_id": "seed-batch",
                                "source_message_ids": ["seed-1"],
                                "scope": "sender",
                                "disposition": "phishing",
                                "source_examples": [
                                    {
                                        "provider": "gmail",
                                        "message_id": "seed-1",
                                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                                        "subject": "Service report 555555",
                                        "date": "2026-06-27T00:00:00Z",
                                        "final_labels": [],
                                    }
                                ],
                                "explanation": "Known phishing family.",
                                "preview": {"match_count": 2, "matches": []},
                                "status": "approved",
                                "created_at": "2026-06-28T00:00:00Z",
                                "updated_at": "2026-06-28T00:00:00Z",
                                "review_notes": "Approved by founder.",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            report = build_classifier_corpus_report([("gmail", gmail_dir)])
            projection = report["providers"]["gmail"]["safety_memory_projection"]

            self.assertEqual(projection["approved_disposition_count"], 1)
            self.assertEqual(projection["baseline"]["caution_count"], 0)
            self.assertEqual(projection["projected"]["caution_count"], 2)
            self.assertEqual(projection["projected"]["safety_memory_hit_count"], 2)
            self.assertEqual(projection["delta"]["caution_count_delta"], 2)
            self.assertEqual(projection["projected"]["heuristic_false_hide_risk_count"], 0)
            projected_families = []
            for split in ("discovery", "validation", "holdout"):
                projected_families.extend(projection["top_projected_caution_families_by_split"][split])
            self.assertEqual(projected_families[0]["sender_key"], "alerts@pestsolutions.test")

    def test_report_uses_stored_gmail_fields_without_reparsing_raw_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gmail_dir = Path(temp_dir) / "gmail"
            batches_dir = gmail_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            (batches_dir / "founder-test-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "provider": "gmail",
                        "items": [
                            {
                                "message_id": "g1",
                                "sender": '"Google" <no-reply@accounts.google.com>',
                                "subject": "Security alert for founder@example.test",
                                "date": "2026-06-19T09:50:40Z",
                                "snippet": "Stored snippet.",
                                "body": "Stored normalized body should win.",
                            }
                        ],
                        "raw_messages": [
                            {
                                "id": "g1",
                                "snippet": "Raw snippet.",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": '"Wrong" <wrong@example.com>'},
                                        {"name": "Subject", "value": "Wrong subject"},
                                        {"name": "Date", "value": "Thu, 19 Jun 2026 09:50:40 +0000"},
                                    ],
                                    "mimeType": "text/html",
                                    "body": {"data": ""},
                                },
                            }
                        ],
                    },
                    indent=2,
                )
            )

            report = build_classifier_corpus_report([("gmail", gmail_dir)])
            family = report["providers"]["gmail"]["family_splits"][0]

            self.assertEqual(family["sender_key"], "no-reply@accounts.google.com")
            self.assertEqual(family["subject_key"], "security alert for founder@example.test")

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


if __name__ == "__main__":
    unittest.main()
