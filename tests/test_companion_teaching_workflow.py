import unittest
from pathlib import Path
from unittest.mock import patch

from src.companion_teaching_workflow import (
    CompanionTeachingWorkflow,
    TeachingWriteRequest,
)


class CompanionTeachingWorkflowTests(unittest.TestCase):
    def test_build_and_finish_preview_keep_local_teaching_contract_together(self) -> None:
        workflow = CompanionTeachingWorkflow(
            Path("/tmp/threadwise-test"),
            write_through=lambda request: self.fail(f"unexpected write: {request}"),
        )
        preview = {"selected_message_id": "message-1", "impact": {"state": "deferred"}}
        completed = {"selected_message_id": "message-1", "impact": {"state": "complete"}}
        payload = {
            "selected_context": {"provider": "gmail", "message_id": "message-1"},
            "target_label": "reply-needed",
            "target_label_explicit": False,
            "note": "Needs my answer",
            "scope": "sender",
        }

        with (
            patch(
                "src.companion_teaching_workflow.build_sidebar_teach_preview",
                return_value=preview,
            ) as build_preview,
            patch(
                "src.companion_teaching_workflow.finish_sidebar_teach_preview_impact",
                return_value=completed,
            ) as finish_impact,
        ):
            self.assertIs(
                workflow.build_preview(payload, include_existing_impact=False),
                preview,
            )
            self.assertIs(workflow.finish_preview_impact(dict(preview)), completed)

        self.assertFalse(build_preview.call_args.kwargs["target_label_explicit"])
        self.assertFalse(build_preview.call_args.kwargs["include_existing_impact"])
        finish_impact.assert_called_once_with(Path("/tmp/threadwise-test"), preview)

    def test_exclude_match_rebuilds_preview_with_amendment_proposal(self) -> None:
        workflow = CompanionTeachingWorkflow(
            Path("/tmp/threadwise-test"),
            write_through=lambda request: self.fail(f"unexpected write: {request}"),
        )
        exclusion = {
            "excluded_message_id": "message-2",
            "amendment_proposal": {"proposal_id": "proposal-1"},
        }

        with (
            patch(
                "src.companion_teaching_workflow.exclude_sidebar_teaching_match",
                return_value=exclusion,
            ),
            patch(
                "src.companion_teaching_workflow.build_sidebar_teach_preview",
                return_value={"selected_message_id": "message-1"},
            ),
        ):
            result = workflow.exclude_match(
                {
                    "selected_context": {"provider": "gmail", "message_id": "message-1"},
                    "target_label": "reply-needed",
                    "note": "Needs my answer",
                    "scope": "sender",
                    "excluded_message_id": "message-2",
                    "reason": "Automated notice",
                }
            )

        self.assertEqual(result["excluded_message_id"], "message-2")
        self.assertEqual(result["preview"]["amendment_proposal"]["proposal_id"], "proposal-1")

    def test_decide_amendment_owns_the_user_facing_outcome(self) -> None:
        workflow = CompanionTeachingWorkflow(
            Path("/tmp/threadwise-test"),
            write_through=lambda request: self.fail(f"unexpected write: {request}"),
        )

        with patch(
            "src.companion_teaching_workflow.apply_rule_amendment_decision",
            return_value={"amendment_status": "accepted", "preview": {}},
        ):
            result = workflow.decide_amendment(
                {
                    "selected_context": {"provider": "gmail", "message_id": "message-1"},
                    "target_label": "reply-needed",
                    "note": "Needs my answer",
                    "scope": "sender",
                    "amendment": {"proposal_id": "proposal-1"},
                    "decision": "accept",
                }
            )

        self.assertEqual(result["amendment_status"], "accepted")
        self.assertIn("Updated the proposed rule boundary", result["acknowledgment"])

    def test_apply_concentrates_local_teaching_write_request_and_exact_outcome(self) -> None:
        write_requests: list[TeachingWriteRequest] = []
        write_summary = {
            "mode": "applied",
            "messages_written": 2,
            "label_write_failed": 0,
            "label_write_skipped": 0,
            "inbox_removed": 0,
            "inbox_remove_failed": 0,
        }
        workflow = CompanionTeachingWorkflow(
            Path("/tmp/threadwise-test"),
            write_through=lambda request: write_requests.append(request) or write_summary,
        )
        teaching_result = {
            "acknowledgment": "Updated this email and one matching email.",
            "current": {
                "account_id": "founder@example.test",
                "message_id": "message-1",
                "subject": "Receipt ready",
                "sender": "Shop <orders@example.test>",
            },
            "mode": "apply-included",
            "preview_matches": [{"message_id": "message-2"}],
            "semantic_rule": {"rule_type": "sender"},
            "matched_existing_count": 1,
            "proposal": {"status": "pending"},
            "current_changed": True,
            "future_rule_saved": False,
        }

        with patch(
            "src.companion_teaching_workflow.apply_sidebar_teaching",
            return_value=teaching_result,
        ) as apply_teaching:
            result = workflow.apply(
                {
                    "selected_context": {"provider": "gmail", "message_id": "message-1"},
                    "target_label": "shopping-order",
                    "note": "Receipts from this shop",
                    "mode": "apply-included",
                    "included_message_ids": ["message-2"],
                }
            )

        self.assertEqual(apply_teaching.call_args.kwargs["included_message_ids"], ["message-2"])
        self.assertEqual(len(write_requests), 1)
        self.assertEqual(write_requests[0].included_message_ids, frozenset({"message-2"}))
        self.assertEqual(write_requests[0].semantic_rule["target_label"], "shopping-order")
        self.assertEqual(result.response["outcome"]["state"], "changed")
        self.assertTrue(result.response["outcome"]["current_email_written_to_gmail"])
        self.assertEqual(result.write_summary, write_summary)

    def test_apply_rejects_suspicious_before_local_or_provider_mutation(self) -> None:
        workflow = CompanionTeachingWorkflow(
            Path("/tmp/threadwise-test"),
            write_through=lambda request: self.fail(f"unexpected write: {request}"),
        )

        with (
            patch("src.companion_teaching_workflow.apply_sidebar_teaching") as apply_teaching,
            self.assertRaisesRegex(ValueError, "safety"),
        ):
            workflow.apply(
                {
                    "selected_context": {"provider": "gmail", "message_id": "message-1"},
                    "target_label": "suspicious",
                    "mode": "current-only",
                }
            )

        apply_teaching.assert_not_called()


if __name__ == "__main__":
    unittest.main()
