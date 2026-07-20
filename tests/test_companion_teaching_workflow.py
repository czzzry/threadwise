import unittest
from pathlib import Path
from unittest.mock import patch

from src.companion_teaching_workflow import (
    CompanionTeachingWorkflow,
    TeachingWriteRequest,
)


class CompanionTeachingWorkflowTests(unittest.TestCase):
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
