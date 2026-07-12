import unittest

from src.safety_triage_manifest import build_safety_triage_manifest


class SafetyTriageManifestTests(unittest.TestCase):
    def test_build_manifest_captures_summary_and_paths(self) -> None:
        manifest = build_safety_triage_manifest(
            report={"report_path": "/tmp/eval.json"},
            frontier_plan={"plan_path": "/tmp/frontier.json"},
            cluster_pack={"pack_path": "/tmp/cluster.json"},
            review_pack={
                "pack_path": "/tmp/review.json",
                "top_review_targets": [{"provider": "gmail", "sender_key": "alerts@example.com"}],
            },
            digest={
                "digest_path": "/tmp/digest.json",
                "summary": {"provider_count": 2, "top_target_count": 3},
                "top_targets": [{"provider": "gmail", "sender_key": "alerts@example.com"}],
            },
            backlog={
                "report_path": "/tmp/backlog.json",
                "provider_drivers": [{"provider": "gmail", "driver_score": 5}],
                "summary": {
                    "backlog_pressure": "elevated",
                    "pending_disposition_count": 4,
                    "approved_disposition_count": 1,
                    "rejected_disposition_count": 2,
                },
            },
            memory_impact={
                "report_path": "/tmp/memory-impact.json",
                "summary": {
                    "accepted_rule_count": 4,
                    "impacted_rule_count": 2,
                    "unresolved_before": 10,
                    "unresolved_after": 6,
                    "unresolved_delta": -4,
                },
                "top_memory_impacts": [{"rule_id": "shadow-gmail-001"}],
                "next_review_payoffs": [{"provider": "outlookmail", "sender_key": "mystery@example.com"}],
            },
            founder_question_pack={
                "pack_path": "/tmp/founder-questions.json",
                "summary": {
                    "question_count": 3,
                    "estimated_unblocked_messages": 42,
                },
                "questions": [{"theme": "marketing-preference", "providers": ["outlookmail"]}],
            },
            founder_answer_pack={
                "pack_path": "/tmp/founder-answers.json",
                "summary": {
                    "actionable_answer_count": 4,
                    "answer_option_count": 7,
                },
                "questions": [],
            },
        )

        self.assertEqual(manifest["artifact_type"], "latest-safety-triage-pass")
        self.assertEqual(manifest["summary"]["provider_count"], 2)
        self.assertEqual(manifest["summary"]["backlog_pressure"], "elevated")
        self.assertEqual(manifest["top_target"]["provider"], "gmail")
        self.assertEqual(manifest["provider_drivers"][0]["provider"], "gmail")
        self.assertEqual(manifest["top_review_targets"][0]["provider"], "gmail")
        self.assertEqual(manifest["memory_impact_summary"]["accepted_rule_count"], 4)
        self.assertEqual(manifest["top_memory_impacts"][0]["rule_id"], "shadow-gmail-001")
        self.assertEqual(manifest["next_review_payoffs"][0]["provider"], "outlookmail")
        self.assertEqual(manifest["founder_question_summary"]["question_count"], 3)
        self.assertEqual(manifest["founder_questions"][0]["theme"], "marketing-preference")
        self.assertEqual(manifest["founder_answer_summary"]["actionable_answer_count"], 4)
        self.assertEqual(manifest["artifacts"]["backlog_report_path"], "/tmp/backlog.json")
        self.assertEqual(manifest["artifacts"]["memory_impact_report_path"], "/tmp/memory-impact.json")
        self.assertEqual(manifest["artifacts"]["founder_question_pack_path"], "/tmp/founder-questions.json")
        self.assertEqual(manifest["artifacts"]["founder_answer_pack_path"], "/tmp/founder-answers.json")


if __name__ == "__main__":
    unittest.main()
