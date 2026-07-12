import json
import tempfile
import unittest
from pathlib import Path

from src.shadow_review_pack import build_shadow_review_pack, load_report


class ShadowReviewPackTests(unittest.TestCase):
    def test_build_shadow_review_pack_separates_objective_preference_and_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "shadow_suggestion_memory.json"
            memory_path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "provider": "outlookmail",
                                "sender_key": "alerts@example.com",
                                "subject_key": "security alert",
                                "status": "pending",
                            },
                            {
                                "provider": "outlookmail",
                                "sender_key": "deals@example.com",
                                "subject_key": "big sale today",
                                "status": "pending",
                            },
                            {
                                "provider": "outlookmail",
                                "sender_key": "done@example.com",
                                "subject_key": "already reviewed",
                                "status": "accepted",
                            },
                        ]
                    },
                    indent=2,
                )
            )
            report = {
                "report_path": "/tmp/report.json",
                "eval_contract": {"current_doc": "docs/current-multi-inbox-eval-contract-2026-06-28.md"},
                "providers": {
                    "outlookmail": {
                        "shadow_count": 20,
                        "top_unlabeled_families_by_split": {
                            "discovery": [
                                {
                                    "sender_key": "alerts@example.com",
                                    "subject_key": "security alert",
                                    "count": 8,
                                    "examples": [
                                        {
                                            "account_id": "founder-hotmail",
                                            "sender": "Alerts <alerts@example.com>",
                                            "subject": "Security alert",
                                        }
                                    ],
                                },
                                {
                                    "sender_key": "deals@example.com",
                                    "subject_key": "big sale today",
                                    "count": 6,
                                    "examples": [
                                        {
                                            "account_id": "founder-hotmail",
                                            "sender": "Deals <deals@example.com>",
                                            "subject": "Big sale today",
                                        }
                                    ],
                                },
                                {
                                    "sender_key": "mystery@example.com",
                                    "subject_key": "strange internal memo",
                                    "count": 4,
                                    "examples": [
                                        {
                                            "account_id": "founder-hotmail",
                                            "sender": "Mystery <mystery@example.com>",
                                            "subject": "Strange internal memo",
                                        }
                                    ],
                                },
                                {
                                    "sender_key": "done@example.com",
                                    "subject_key": "already reviewed",
                                    "count": 9,
                                    "examples": [
                                        {
                                            "account_id": "founder-hotmail",
                                            "sender": "Done <done@example.com>",
                                            "subject": "Already reviewed",
                                        }
                                    ],
                                },
                            ]
                        },
                        "safety_memory_projection": {
                            "top_projected_false_hide_risk_families": [
                                {
                                    "sender_key": "alerts@example.com",
                                    "subject_key": "security alert",
                                    "count": 8,
                                    "examples": [],
                                }
                            ],
                            "top_projected_caution_families_by_split": {
                                "discovery": [],
                                "validation": [
                                    {
                                        "sender_key": "alerts@example.com",
                                        "subject_key": "security alert",
                                        "count": 8,
                                        "examples": [],
                                    }
                                ],
                                "holdout": [],
                            },
                        },
                    }
                },
                "shadow_suggestion_candidates": {
                    "outlookmail": [
                        {
                            "provider": "outlookmail",
                            "sender_key": "alerts@example.com",
                            "subject_key": "security alert",
                            "suggested_labels": ["account-security"],
                            "rationale": "Security flow.",
                            "evidence_terms": ["security alert"],
                            "generated_by": "openai-shadow-family-suggester",
                            "confidence": "high",
                            "status": "pending",
                        },
                        {
                            "provider": "outlookmail",
                            "sender_key": "deals@example.com",
                            "subject_key": "big sale today",
                            "suggested_labels": ["promotions"],
                            "rationale": "Marketing mail.",
                            "evidence_terms": ["sale"],
                            "generated_by": "heuristic-shadow-family-suggester",
                            "confidence": "medium",
                            "status": "pending",
                        },
                        {
                            "provider": "outlookmail",
                            "sender_key": "done@example.com",
                            "subject_key": "already reviewed",
                            "suggested_labels": ["account-security"],
                            "rationale": "Security flow.",
                            "evidence_terms": ["security"],
                            "generated_by": "heuristic-shadow-family-suggester",
                            "confidence": "high",
                            "status": "pending",
                        },
                    ]
                },
            }

            pack = build_shadow_review_pack(report, suggestion_memory_path=memory_path)

            self.assertEqual(pack["summary"]["objective_review_count"], 1)
            self.assertEqual(pack["summary"]["preference_question_count"], 1)
            self.assertEqual(pack["summary"]["taxonomy_question_count"], 1)
            self.assertEqual(pack["summary"]["message_coverage"], 18)
            self.assertEqual(pack["summary"]["safety_priority_review_count"], 1)
            self.assertEqual(pack["summary"]["top_review_target_count"], 3)
            self.assertEqual(pack["safety_priority_reviews"][0]["sender_key"], "alerts@example.com")
            self.assertEqual(pack["objective_reviews"][0]["sender_key"], "alerts@example.com")
            self.assertEqual(pack["objective_reviews"][0]["safety_priority"]["priority_score"], 7)
            self.assertEqual(pack["objective_reviews"][0]["review_priority"]["bucket"], "urgent")
            self.assertTrue(pack["objective_reviews"][0]["safety_priority"]["has_false_hide_risk"])
            self.assertEqual(pack["objective_reviews"][0]["account_ids"], ["founder-hotmail"])
            self.assertEqual(pack["preference_questions"][0]["sender_key"], "deals@example.com")
            self.assertEqual(pack["taxonomy_questions"][0]["sender_key"], "mystery@example.com")
            self.assertEqual(pack["top_review_targets"][0]["sender_key"], "alerts@example.com")
            self.assertEqual(pack["provider_summaries"]["outlookmail"]["review_unit_count"], 3)
            self.assertEqual(pack["provider_summaries"]["outlookmail"]["safety_priority_review_count"], 1)
            self.assertEqual(pack["provider_summaries"]["outlookmail"]["priority_message_coverage"], 8)

    def test_load_report_preserves_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.json"
            report_path.write_text(json.dumps({"providers": {}}))

            report = load_report(report_path)

            self.assertEqual(report["report_path"], str(report_path))


if __name__ == "__main__":
    unittest.main()
