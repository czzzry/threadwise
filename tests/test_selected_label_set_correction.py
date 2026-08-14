import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.gmail_writer import MockGmailLabelClient, MockGmailLabelWriter
from src.proton_teaching_adapter import ProtonTeachingAdapter
from src.companion_teaching_workflow import TeachingWriteRequest
from src.teaching_loop import apply_sidebar_teaching, build_sidebar_teach_preview, infer_label_change_from_note


class SelectedLabelSetCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._private_model_environment = patch.dict(
            "os.environ",
            {"EMAIL_AGENT_OPENAI_API_KEY": "", "OPENAI_API_KEY": ""},
        )
        self._private_model_environment.start()
        self.addCleanup(self._private_model_environment.stop)

    def write_batch(self, storage_dir: Path, labels: list[str]) -> None:
        batches = storage_dir / "batches"
        batches.mkdir(parents=True)
        (batches / "batch.json").write_text(json.dumps({
            "batch_id": "batch", "provider": "gmail", "account_id": "founder-test",
            "items": [{
                "message_id": "message-1", "sender": "Shop <shop@example.com>",
                "subject": "Your order receipt", "review_state": "pending",
                "final_labels": labels, "applied_labels": labels,
            }],
        }))

    def test_preview_and_apply_consumes_exact_approved_add_without_second_llm_call(self):
        with tempfile.TemporaryDirectory() as temp:
            storage = Path(temp)
            self.write_batch(storage, ["shopping-order"])
            preview = build_sidebar_teach_preview(
                storage, selected_context={"provider": "gmail", "message_id": "message-1"},
                target_label="shopping-order", note="keep Orders and add Receipts", scope="sender",
            )
            self.assertEqual(preview["label_change"]["operation"], "add")
            self.assertEqual(preview["selected_label_after"], ["shopping-order", "receipt-billing"])
            with patch("src.teaching_loop.interpret_teaching_intent") as interpret:
                result = apply_sidebar_teaching(
                    storage, selected_context={"provider": "gmail", "message_id": "message-1"},
                    target_label="shopping-order", note="keep Orders and add Receipts", scope="sender",
                    mode="current-only", approved_label_change=preview["label_change"],
                )
            interpret.assert_not_called()
            self.assertEqual(result["label_change"]["labels_after"], ["shopping-order", "receipt-billing"])
            stored = json.loads((storage / "batches" / "batch.json").read_text())
            self.assertEqual(stored["items"][0]["final_labels"], ["shopping-order", "receipt-billing"])

    def test_llm_label_change_repairs_safe_structural_inconsistencies(self):
        scenarios = [
            {
                "before": ["shopping-order"],
                "note": "keep Orders and add Receipts",
                "response": {
                    "target_label": "receipt-billing",
                    "operation": "add",
                    "target_labels": ["receipt-billing"],
                    "source_labels": ["shopping-order"],
                    "resolution_status": "resolved",
                },
                "operation": "add",
                "sources": [],
            },
            {
                "before": ["shopping-order"],
                "note": "replace Orders with Receipts",
                "response": {
                    "target_label": "receipt-billing",
                    "operation": "replace",
                    "target_labels": ["receipt-billing"],
                    "source_labels": [],
                    "resolution_status": "resolved",
                },
                "operation": "replace",
                "sources": ["shopping-order"],
            },
            {
                "before": ["job-related", "newsletter"],
                "note": "Newsletter is correct, but this is not Work.",
                "response": {
                    "target_label": "newsletter",
                    "operation": "replace",
                    "target_labels": ["newsletter"],
                    "source_labels": ["job-related", "newsletter"],
                    "resolution_status": "resolved",
                },
                "operation": "replace",
                "sources": ["job-related"],
            },
        ]
        for scenario in scenarios:
            with self.subTest(operation=scenario["operation"]), tempfile.TemporaryDirectory() as temp:
                storage = Path(temp)
                self.write_batch(storage, scenario["before"])
                client = Mock()
                client.interpret.return_value = scenario["response"]
                with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=client):
                    preview = build_sidebar_teach_preview(
                        storage,
                        selected_context={"provider": "gmail", "message_id": "message-1"},
                        target_label="shopping-order",
                        note=scenario["note"],
                        scope="sender",
                    )

                self.assertEqual(preview["label_change"]["operation"], scenario["operation"])
                self.assertEqual(preview["label_change"]["source_labels"], scenario["sources"])
                expected_after = (
                    ["newsletter"]
                    if scenario["before"] == ["job-related", "newsletter"]
                    else ["receipt-billing"]
                    if scenario["operation"] == "replace"
                    else ["shopping-order", "receipt-billing"]
                )
                self.assertEqual(preview["selected_label_after"], expected_after)

    def test_natural_only_remove_replace_and_contradiction_are_bounded(self):
        scenarios = [
            (["travel"], "use both Orders and Receipts labels", "only", ["shopping-order", "receipt-billing"]),
            (["financial-account", "reply-needed"], "remove Needs Action", "remove", ["financial-account"]),
            (["shopping-order", "personal"], "replace Orders with Receipts", "replace", ["receipt-billing", "personal"]),
        ]
        for before, note, operation, after in scenarios:
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as temp:
                storage = Path(temp)
                self.write_batch(storage, before)
                preview = build_sidebar_teach_preview(
                    storage, selected_context={"provider": "gmail", "message_id": "message-1"},
                    target_label="", note=note, scope="sender",
                )
                self.assertEqual(preview["label_change"]["operation"], operation)
                self.assertEqual(preview["selected_label_after"], after)

        with tempfile.TemporaryDirectory() as temp:
            storage = Path(temp)
            self.write_batch(storage, ["shopping-order"])
            with self.assertRaisesRegex(ValueError, "add and remove"):
                build_sidebar_teach_preview(
                    storage, selected_context={"provider": "gmail", "message_id": "message-1"},
                    target_label="shopping-order", note="add Receipts but remove Receipts", scope="sender",
                )

    def test_deterministic_note_parser_prefers_complete_label_names(self):
        self.assertEqual(
            infer_label_change_from_note("add Financial Account", ["shopping-order"]),
            {
                "operation": "add",
                "source_labels": [],
                "target_labels": ["financial-account"],
            },
        )
        self.assertEqual(
            infer_label_change_from_note("add Finance and Account", ["shopping-order"]),
            {
                "operation": "add",
                "source_labels": [],
                "target_labels": ["account-security", "financial-account"],
            },
        )

    def test_gmail_writer_requires_exact_readback_and_preserves_unrelated_label(self):
        with tempfile.TemporaryDirectory() as temp:
            client = MockGmailLabelClient(
                existing_labels={"EA/Orders": "orders", "EA/Receipts": "receipts", "STARRED": "starred"},
                message_labels_by_id={"message-1": ["starred", "orders"]},
            )
            writer = MockGmailLabelWriter(client, Path(temp), label_name_resolver={
                "shopping-order": "EA/Orders", "receipt-billing": "EA/Receipts",
            }.get)
            result = writer.write_reviewed_labels("batch", [{
                "message_id": "message-1", "review_state": "reviewed",
                "final_labels": ["shopping-order", "receipt-billing"],
                "require_exact_label_set_verification": True,
            }])
            self.assertEqual(result["applied_count"], 1)
            self.assertEqual(client._message_labels_by_id["message-1"], ["starred", "orders", "receipts"])

            client.get_threadwise_label_names = Mock(return_value=["EA/Orders"])
            mismatch = writer.write_reviewed_labels("batch-2", [{
                "message_id": "message-1", "review_state": "reviewed",
                "final_labels": ["shopping-order", "receipt-billing"],
                "require_exact_label_set_verification": True,
            }])
            self.assertEqual(mismatch["failed_count"], 1)

    def test_proton_blocks_non_additive_label_change_before_console_load(self):
        loader = Mock()
        adapter = ProtonTeachingAdapter(loader)
        request = TeachingWriteRequest(
            account_id="account", current_message_id="message-1", mode="current-only",
            preview_matches=[], semantic_rule={"target_label": "receipt-billing"},
            current_subject="Receipt", current_sender="shop@example.com",
            included_message_ids=frozenset(), provider="protonmail",
            label_change={"operation": "replace", "target_labels": ["receipt-billing"]},
        )
        with self.assertRaisesRegex(ValueError, "additive"):
            adapter.apply(request)
        loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
