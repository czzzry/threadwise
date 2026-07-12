import json
import tempfile
import unittest
from pathlib import Path

from src.candidate_change_store import CandidateChange
from src.candidate_evaluation import evaluate_candidate_batch
from src.teachable_rule_memory import TeachableRule


class CandidateEvaluationTests(unittest.TestCase):
    def test_batch_can_recommend_promote_and_reject_for_different_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_dir = root / "gmail"
            protonmail_dir = root / "protonmail"
            output_dir = root / "classifier_eval"
            self._write_batch(
                gmail_dir,
                "founder-test-batch-1",
                "founder-test",
                "gmail",
                [
                    {
                        "message_id": "g1",
                        "sender": "Google <no-reply@accounts.google.com>",
                        "subject": "Security alert",
                        "snippet": "Blocked sign-in attempt.",
                        "body": "Blocked sign-in attempt.",
                        "review_state": "reviewed",
                        "final_labels": ["account-security"],
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
                        "sender": "Vendor Digest <digest@vendor.example>",
                        "subject": "Weekly vendor digest",
                        "snippet": "This week at Vendor.",
                        "body": "This week at Vendor.",
                    }
                ],
            )

            promote_candidate = CandidateChange(
                id="candidate-future-rule-001",
                kind="future-rule",
                source="sidebar-teach",
                title="Teach vendor digest as newsletter",
                description="Save future rule from inbox teaching.",
                affected_scope_summary="vendor digest family",
                metadata={
                    "rules": [
                        TeachableRule(
                            id="teach-001",
                            instruction="Anything from digest@vendor.example should be newsletter.",
                            label="newsletter",
                            terms=("digest@vendor.example",),
                            keep_visible=False,
                            created_at="2026-07-10T10:00:00Z",
                            providers=("protonmail",),
                            updated_at="2026-07-10T10:00:00Z",
                        ).to_dict()
                    ]
                },
                created_at="2026-07-10T10:00:00Z",
                updated_at="2026-07-10T10:00:00Z",
            )
            reject_candidate = CandidateChange(
                id="candidate-future-rule-002",
                kind="future-rule",
                source="sidebar-teach",
                title="Mislabel security alert as promotions",
                description="Bad future rule for a reviewed Gmail pattern.",
                affected_scope_summary="security alert sender family",
                metadata={
                    "rules": [
                        TeachableRule(
                            id="teach-002",
                            instruction="Anything from no-reply@accounts.google.com should be promotions.",
                            label="promotions",
                            terms=("no-reply@accounts.google.com",),
                            keep_visible=False,
                            created_at="2026-07-10T10:05:00Z",
                            providers=("gmail",),
                            updated_at="2026-07-10T10:05:00Z",
                        ).to_dict()
                    ]
                },
                created_at="2026-07-10T10:05:00Z",
                updated_at="2026-07-10T10:05:00Z",
            )

            report = evaluate_candidate_batch(
                candidates=[promote_candidate, reject_candidate],
                provider_storage_dirs=[
                    ("gmail", gmail_dir),
                    ("protonmail", protonmail_dir),
                ],
                output_storage_dir=output_dir,
            )

            self.assertEqual(report["batch_recommendation"], "Review")
            summaries = {item["candidate_id"]: item for item in report["candidate_summaries"]}
            self.assertEqual(summaries["candidate-future-rule-001"]["recommendation"], "Promote")
            self.assertEqual(summaries["candidate-future-rule-002"]["recommendation"], "Reject")
            self.assertLess(
                summaries["candidate-future-rule-001"]["deltas"]["shadow_unlabeled_rate_overall_delta"],
                0,
            )
            self.assertLess(
                summaries["candidate-future-rule-002"]["deltas"]["reviewed_gmail_exact_match_rate_delta"],
                0,
            )
            self.assertTrue(Path(report["report_path"]).exists())

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
