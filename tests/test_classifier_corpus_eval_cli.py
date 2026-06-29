import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.classifier_corpus_eval_cli import main


class ClassifierCorpusEvalCliTests(unittest.TestCase):
    class _FakeFamilySuggestionClient:
        def suggest_for_family(self, provider: str, family: dict) -> dict:
            return {
                "labels": ["account-security"],
                "rationale": "Looks like an account flow.",
                "evidence_terms": ["verify your email"],
                "confidence": "high",
            }

    def test_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_classifier_corpus.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Evaluate the current classifier", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_writes_local_report_for_configured_storage_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            protonmail_dir = root / "protonmail"
            outlookmail_dir = root / "outlookmail"
            output_dir = root / "reports"
            self._write_batch(gmail_dir, "founder-test-batch-1", "founder-test", "gmail")
            self._write_batch(protonmail_dir, "personal-proton-batch-1", "personal-proton", "protonmail")
            self._write_batch(outlookmail_dir, "founder-hotmail-batch-1", "founder-hotmail", "outlookmail")
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(gmail_dir),
                    "--protonmail-storage-dir",
                    str(protonmail_dir),
                    "--outlookmail-storage-dir",
                    str(outlookmail_dir),
                    "--output-storage-dir",
                    str(output_dir),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("Eval contract: docs/current-multi-inbox-eval-contract-2026-06-28.md", rendered)
            self.assertIn("Provider: gmail | total=1", rendered)
            self.assertIn("Provider: protonmail | total=1", rendered)
            self.assertIn("Provider: outlookmail | total=1", rendered)
            self.assertIn("suggestion candidates:", rendered)
            self.assertIn("safety memory:", rendered)
            self.assertIn("safety validation:", rendered)
            self.assertIn("safety holdout:", rendered)
            self.assertIn("discovery:", rendered)
            self.assertIn("validation:", rendered)
            self.assertIn("holdout:", rendered)
            self.assertIn("Saved report:", rendered)
            self.assertIn("Saved suggestion memory:", rendered)
            report_path = Path(rendered.split("Saved report:", 1)[1].splitlines()[0].strip())
            self.assertTrue(report_path.exists())
            report = json.loads(report_path.read_text())
            self.assertIn("eval_contract", report)
            self.assertEqual(
                report["eval_contract"]["corpora"]["outlookmail_shadow"]["contamination_status"],
                "debug-inspected",
            )
            self.assertIn("shadow_suggestion_candidates", report)
            self.assertIn("shadow_suggestion_memory_path", report)

    def test_main_loads_exposed_family_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            protonmail_dir = root / "protonmail"
            output_dir = root / "reports"
            exposed_path = root / "exposed.json"
            self._write_batch(protonmail_dir, "personal-proton-batch-1", "personal-proton", "protonmail")
            exposed_path.write_text(
                json.dumps(
                    {
                        "protonmail": [
                            {
                                "sender_key": "account-update@amazon.ca",
                                "subject_key": "passkey added to your account",
                            }
                        ]
                    }
                )
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(root / "empty-gmail"),
                    "--protonmail-storage-dir",
                    str(protonmail_dir),
                    "--output-storage-dir",
                    str(output_dir),
                    "--exposed-family-path",
                    str(exposed_path),
                ],
                stdout=stdout,
            )

            report_path = Path(stdout.getvalue().split("Saved report:", 1)[1].splitlines()[0].strip())
            report = json.loads(report_path.read_text())
            family = report["providers"]["protonmail"]["family_splits"][0]

            self.assertEqual(exit_code, 0)
            self.assertEqual(family["split"], "discovery")
            self.assertTrue(family["exposed"])
            self.assertIn("shadow_suggestion_candidates", report)

    def test_main_can_use_model_backed_family_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            protonmail_dir = root / "protonmail"
            output_dir = root / "reports"
            self._write_batch(
                protonmail_dir,
                "personal-proton-batch-1",
                "personal-proton",
                "protonmail",
                sender="Eightfold <confirm@eightfold.ai>",
                subject="Verify your email",
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(root / "empty-gmail"),
                    "--protonmail-storage-dir",
                    str(protonmail_dir),
                    "--outlookmail-storage-dir",
                    str(root / "empty-outlook"),
                    "--output-storage-dir",
                    str(output_dir),
                    "--suggestion-model",
                    "fake-model",
                ],
                stdout=stdout,
                family_suggestion_client_factory=lambda model: self._FakeFamilySuggestionClient(),
            )

            report_path = Path(stdout.getvalue().split("Saved report:", 1)[1].splitlines()[0].strip())
            report = json.loads(report_path.read_text())
            proton_candidates = report["shadow_suggestion_candidates"]["protonmail"]

            self.assertEqual(exit_code, 0)
            self.assertEqual(proton_candidates[0]["suggested_labels"], ["account-security"])
            self.assertEqual(proton_candidates[0]["generated_by"], "openai-shadow-family-suggester")

    def test_accepted_shadow_rules_are_provider_scoped_in_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            protonmail_dir = root / "protonmail"
            output_dir = root / "reports"
            rules_path = output_dir / "accepted_shadow_teachable_rules.json"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                sender="Sony <account@example.com>",
                subject="Change your Password",
            )
            self._write_batch(
                protonmail_dir,
                "personal-proton-batch-1",
                "personal-proton",
                "protonmail",
                sender="Sony <account@example.com>",
                subject="Change your Password",
            )
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            rules_path.write_text(
                json.dumps(
                    {
                        "rules": [
                            {
                                "id": "shadow-001",
                                "instruction": "Anything from sony with subject like change your password should be account-security.",
                                "label": "account-security",
                                "terms": ["sony", "change your password"],
                                "keep_visible": True,
                                "created_at": "2026-06-27T00:00:00Z",
                                "providers": ["protonmail"],
                                "enabled": True,
                                "source_examples": [],
                            }
                        ]
                    }
                )
            )
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(gmail_dir),
                    "--protonmail-storage-dir",
                    str(protonmail_dir),
                    "--outlookmail-storage-dir",
                    str(root / "empty-outlook"),
                    "--output-storage-dir",
                    str(output_dir),
                    "--accepted-shadow-rules-path",
                    str(rules_path),
                ],
                stdout=stdout,
            )

            report_path = Path(stdout.getvalue().split("Saved report:", 1)[1].splitlines()[0].strip())
            report = json.loads(report_path.read_text())

            self.assertEqual(exit_code, 0)
            self.assertEqual(report["providers"]["gmail"]["matched_shadow_rule_count"], 0)
            self.assertEqual(report["providers"]["protonmail"]["matched_shadow_rule_count"], 1)
            self.assertIn("accepted_shadow_rule_projection", report)
            self.assertIn("unlabeled delta from baseline", stdout.getvalue())

    def test_main_surfaces_top_safety_caution_family_when_dispositions_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            output_dir = root / "reports"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                sender='"Pest Solutions" <alerts@pestsolutions.test>',
                subject="Service report 123456",
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
                                "preview": {"match_count": 1, "matches": []},
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
            stdout = io.StringIO()

            exit_code = main(
                [
                    "--gmail-storage-dir",
                    str(gmail_dir),
                    "--protonmail-storage-dir",
                    str(root / "empty-proton"),
                    "--outlookmail-storage-dir",
                    str(root / "empty-outlook"),
                    "--output-storage-dir",
                    str(output_dir),
                ],
                stdout=stdout,
            )

            rendered = stdout.getvalue()

            self.assertEqual(exit_code, 0)
            self.assertIn("top safety", rendered)
            self.assertIn("alerts@pestsolutions.test", rendered)

    def _write_batch(
        self,
        storage_dir: Path,
        batch_id: str,
        account_id: str,
        provider: str,
        sender: str = "Amazon <account-update@amazon.ca>",
        subject: str = "Passkey added to your account",
    ) -> None:
        batches_dir = storage_dir / "batches"
        batches_dir.mkdir(parents=True, exist_ok=True)
        (batches_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": account_id,
                    "provider": provider,
                    "items": [
                        {
                            "message_id": "m1",
                            "sender": sender,
                            "subject": subject,
                            "snippet": "A passkey was added to your Amazon account.",
                            "body": "A passkey was added to your Amazon account.",
                        }
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
