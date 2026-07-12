import json
import tempfile
import unittest
from pathlib import Path

from src.attention_feedback import record_attention_feedback
from src.attention_rules import (
    approve_attention_rule_proposal,
    attention_rule_proposals_path,
    attention_rules_path,
    build_attention_rule_proposal,
    load_attention_rule_proposals,
    reject_attention_rule_proposal,
)


class AttentionRuleTests(unittest.TestCase):
    def test_build_proposal_from_feedback_previews_matching_existing_without_silent_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(storage_dir)
            record_attention_feedback(
                storage_dir,
                {
                    "action": "mark_needs_attention",
                    "message_id": "recruiter-1",
                    "thread_id": "thread-recruiter-1",
                    "batch_id": "batch-1",
                    "subject": "Choose an interview slot",
                    "sender": "Recruiter <jobs@example.com>",
                    "note": "Recruiter scheduling emails should stay visible.",
                    "corrected_category": "job_opportunity",
                },
            )

            proposal = build_attention_rule_proposal(storage_dir, "recruiter-1")

            self.assertEqual(proposal["rule_type"], "attention_promotion")
            self.assertEqual(proposal["attention_priority"], "possible_attention")
            self.assertNotIn("label", proposal)
            self.assertEqual(proposal["status"], "pending")
            self.assertEqual(proposal["condition"]["sender_address"], "jobs@example.com")
            self.assertEqual(proposal["preview"]["match_count"], 2)
            self.assertFalse(attention_rules_path(storage_dir).exists())
            self.assertEqual(load_attention_rule_proposals(storage_dir)["proposals"][proposal["id"]]["status"], "pending")

    def test_concrete_time_or_consequence_promotes_to_needs_attention_now(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(storage_dir)
            record_attention_feedback(
                storage_dir,
                {
                    "action": "mark_needs_attention",
                    "message_id": "travel-1",
                    "thread_id": "thread-travel-1",
                    "batch_id": "batch-1",
                    "subject": "Your flight is tomorrow",
                    "sender": "Airline <alerts@airline.example>",
                    "note": "Flight tomorrow should always be surfaced.",
                    "corrected_category": "travel",
                },
            )

            proposal = build_attention_rule_proposal(storage_dir, "travel-1")

            self.assertEqual(proposal["attention_priority"], "needs_attention_now")
            self.assertEqual(proposal["priority_reason"], "concrete_time_or_consequence_evidence")

    def test_approve_future_only_persists_rule_without_applying_existing_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            proposal = self._build_recruiter_proposal(storage_dir)

            approved = approve_attention_rule_proposal(storage_dir, proposal["id"], application_mode="future_only")
            rules = json.loads(attention_rules_path(storage_dir).read_text())

            self.assertEqual(approved["status"], "approved")
            self.assertEqual(approved["application_mode"], "future_only")
            self.assertEqual(approved["applied_to_message_ids"], [])
            self.assertEqual(rules["rules"][0]["attention_priority"], "possible_attention")
            self.assertTrue(rules["rules"][0]["auto_promote"])
            self.assertEqual(rules["rules"][0]["gmail_mutation"], "none")

    def test_approve_matching_existing_records_application_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            proposal = self._build_recruiter_proposal(storage_dir)

            approved = approve_attention_rule_proposal(storage_dir, proposal["id"], application_mode="matching_existing")

            self.assertEqual(approved["application_mode"], "matching_existing")
            self.assertEqual(approved["applied_to_message_ids"], ["recruiter-1", "recruiter-2"])
            self.assertEqual(approved["gmail_mutation"], "none")

    def test_current_email_only_does_not_create_future_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            proposal = self._build_recruiter_proposal(storage_dir)

            approved = approve_attention_rule_proposal(storage_dir, proposal["id"], application_mode="current_email_only")

            self.assertEqual(approved["application_mode"], "current_email_only")
            self.assertEqual(approved["approved_rule_id"], "")
            self.assertFalse(attention_rules_path(storage_dir).exists())

    def test_reject_proposal_preserves_auditable_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            proposal = self._build_recruiter_proposal(storage_dir)

            rejected = reject_attention_rule_proposal(storage_dir, proposal["id"], notes="Too broad.")
            saved = load_attention_rule_proposals(storage_dir)["proposals"][proposal["id"]]

            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(saved["review_notes"], "Too broad.")

    def _build_recruiter_proposal(self, storage_dir: Path) -> dict:
        self._write_batch(storage_dir)
        record_attention_feedback(
            storage_dir,
            {
                "action": "mark_needs_attention",
                "message_id": "recruiter-1",
                "thread_id": "thread-recruiter-1",
                "batch_id": "batch-1",
                "subject": "Choose an interview slot",
                "sender": "Recruiter <jobs@example.com>",
                "note": "Recruiter scheduling emails should stay visible.",
                "corrected_category": "job_opportunity",
            },
        )
        return build_attention_rule_proposal(storage_dir, "recruiter-1")

    def _write_batch(self, storage_dir: Path) -> None:
        batch_dir = storage_dir / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "batch-1.json").write_text(
            json.dumps(
                {
                    "batch_id": "batch-1",
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "items": [
                        {
                            "message_id": "recruiter-1",
                            "thread_id": "thread-recruiter-1",
                            "sender": "Recruiter <jobs@example.com>",
                            "subject": "Choose an interview slot",
                            "snippet": "Please pick a time.",
                            "final_labels": ["job-related"],
                        },
                        {
                            "message_id": "recruiter-2",
                            "thread_id": "thread-recruiter-2",
                            "sender": "Recruiter <jobs@example.com>",
                            "subject": "Interview next steps",
                            "snippet": "Can you send availability?",
                            "final_labels": ["job-related"],
                        },
                        {
                            "message_id": "travel-1",
                            "thread_id": "thread-travel-1",
                            "sender": "Airline <alerts@airline.example>",
                            "subject": "Your flight is tomorrow",
                            "snippet": "Check in soon.",
                            "final_labels": ["travel"],
                        },
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
