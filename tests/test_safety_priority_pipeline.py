import json
import tempfile
import unittest
from pathlib import Path

from src.classifier_corpus_eval import build_classifier_corpus_report
from src.cluster_decision_pack import build_cluster_decision_pack
from src.frontier_compression import build_frontier_compression_plan
from src.shadow_review_pack import build_shadow_review_pack


class SafetyPriorityPipelineTests(unittest.TestCase):
    def test_approved_safety_memory_propagates_across_artifacts(self) -> None:
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
                        "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                        "subject": "Service report 123456",
                        "snippet": "Open attached report.",
                        "body": "Open attached report.",
                    }
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

            report = build_classifier_corpus_report([("gmail", gmail_dir)])
            family = report["providers"]["gmail"]["family_splits"][0]
            family["split"] = "discovery"
            family["exposed"] = True
            report["providers"]["gmail"]["top_shadow_unlabeled_families_by_split"]["discovery"] = [
                {
                    "sender_key": family["sender_key"],
                    "subject_key": family["subject_key"],
                    "count": family["count"],
                    "examples": [
                        {
                            "account_id": "founder-test",
                            "sender": '"Pest Solutions" <alerts@pestsolutions.test>',
                            "subject": "Service report 123456",
                        }
                    ],
                }
            ]
            report["shadow_suggestion_candidates"] = {
                "gmail": [
                    {
                        "provider": "gmail",
                        "sender_key": "alerts@pestsolutions.test",
                        "subject_key": "service report ######",
                        "suggested_labels": ["account-security"],
                        "rationale": "Security-like service report flow.",
                        "evidence_terms": ["service report"],
                        "generated_by": "heuristic-shadow-family-suggester",
                        "confidence": "high",
                        "status": "pending",
                    }
                ]
            }
            frontier = build_frontier_compression_plan([("gmail", gmail_dir)], extra_rules=[])
            cluster_pack = build_cluster_decision_pack(frontier)
            suggestion_memory_path = root / "shadow_suggestion_memory.json"
            suggestion_memory_path.write_text(json.dumps({"candidates": []}, indent=2))
            review_pack = build_shadow_review_pack(report, suggestion_memory_path=suggestion_memory_path)

            projection = report["providers"]["gmail"]["safety_memory_projection"]
            self.assertEqual(projection["projected"]["safety_memory_hit_count"], 1)
            self.assertEqual(frontier["summary"]["safety_priority_clusters"], 1)
            self.assertEqual(frontier["top_safety_priority_clusters"][0]["sender_key"], "alerts@pestsolutions.test")
            self.assertEqual(cluster_pack["summary"]["safety_priority_review_count"], 1)
            self.assertEqual(cluster_pack["safety_reviews"][0]["escalation_hint"]["level"], "review-immediately")
            self.assertEqual(review_pack["summary"]["safety_priority_review_count"], 1)
            self.assertEqual(review_pack["safety_priority_reviews"][0]["sender_key"], "alerts@pestsolutions.test")

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
