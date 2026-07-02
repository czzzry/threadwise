import json
import tempfile
import unittest
from pathlib import Path

from src.teaching_loop import (
    apply_sidebar_teaching,
    build_sidebar_teach_preview,
    exclude_sidebar_teaching_match,
    load_items_for_gmail_write_through,
)
from src.teaching_exclusions import is_rule_message_excluded
from src.teachable_rule_memory import TeachableRuleMemory


class TeachingLoopTests(unittest.TestCase):
    def test_preview_reports_matching_existing_emails_without_app_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "LinkedIn <messages-noreply@linkedin.com>",
                        "subject": "Sophie Riding sent you a message",
                        "snippet": "Let's catch up",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "LinkedIn <messages-noreply@linkedin.com>",
                        "subject": "Sean commented on a post",
                        "snippet": "New activity",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "messages-noreply@linkedin.com",
                    "subject": "Sophie Riding sent you a message",
                },
                target_label="personal",
                note="LinkedIn direct messages from real people should be personal.",
                scope="sender",
            )

            self.assertEqual(preview["selected_message_id"], "gmail-live-001")
            self.assertEqual(preview["impact"]["matching_existing_count"], 1)
            self.assertEqual(preview["impact"]["matching_existing_examples"][0]["message_id"], "gmail-live-002")
            self.assertEqual(preview["impact"]["matching_existing_examples"][0]["labels_after"], ["personal"])

    def test_preview_can_infer_target_label_from_note_when_dropdown_is_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Komoot <notification@komoot.de>",
                        "subject": "Week 3: Discover local landmarks this week",
                        "snippet": "New routes nearby",
                        "interpretation": "Newsletter content.",
                        "review_state": "reviewed",
                        "final_labels": ["newsletter"],
                        "applied_labels": ["newsletter"],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notification@komoot.de",
                    "subject": "Week 3: Discover local landmarks this week",
                },
                target_label="",
                note="this is spam!!!",
                scope="sender",
            )

            self.assertEqual(preview["selected_label_after"], ["spam-low-value"])
            self.assertEqual(preview["target_label_name"], "EA/LowValue")

    def test_preview_can_infer_low_value_from_phishing_note_when_dropdown_is_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-phish-001",
                        "sender": '"Przelewy24.pl" <no-reply@przelewy24.pl>',
                        "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                        "snippet": "Informacja o transakcji",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-phish-001",
                    "sender": "no-reply@przelewy24.pl",
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                },
                target_label="",
                note="this is phishing. I never want emails like this again",
                scope="sender",
            )

            self.assertEqual(preview["selected_label_after"], ["spam-low-value"])
            self.assertEqual(preview["target_label_name"], "EA/LowValue")
            self.assertIn("EA/LowValue", preview["acknowledgment"])

    def test_preview_proposes_semantic_sender_rule_instead_of_all_sender_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "wealthsimple-001",
                        "sender": "Wealthsimple <notifications@m.wealthsimple.com>",
                        "subject": "Your account statement is ready",
                        "snippet": "Your monthly account statement is available.",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "wealthsimple-001",
                    "sender": "notifications@m.wealthsimple.com",
                    "subject": "Your account statement is ready",
                },
                target_label="",
                note="this is an account email that I need",
                scope="sender",
            )

            self.assertEqual(preview["selected_label_after"], ["account-security"])
            self.assertEqual(preview["rule_type"], "sender-semantic")
            self.assertEqual(preview["rule_type_label"], "Sender + semantic rule")
            self.assertIn("account, security, or statement notices", preview["plain_english_rule"])
            self.assertIn("wealthsimple", preview["plain_english_rule"])
            self.assertNotIn("future messages from notifications@m.wealthsimple.com", preview["plain_english_rule"])

    def test_preview_proposes_cross_sender_semantic_rule_for_phishing_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-phish-001",
                        "sender": '"Przelewy24.pl" <no-reply@przelewy24.pl>',
                        "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                        "snippet": "Informacja o transakcji",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-phish-001",
                    "sender": "no-reply@przelewy24.pl",
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                },
                target_label="",
                note="this is phishing. I never want emails like this again",
                scope="sender",
            )

            self.assertEqual(preview["rule_type"], "cross-sender-semantic")
            self.assertEqual(preview["rule_type_label"], "Cross-sender semantic rule")
            self.assertIn("payment or account notices that look suspicious", preview["plain_english_rule"])

    def test_preview_surfaces_broader_similar_candidates_separately_from_exact_sender_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-phish-001",
                        "sender": '"Przelewy24.pl" <no-reply@przelewy24.pl>',
                        "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                        "snippet": "Informacja o transakcji",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-phish-002",
                        "sender": '"Przelewy24.pl" <info@przelewy24.pl>',
                        "subject": "Nowa transakcja płatnicza (P24-G1M-B3Y-D5T)",
                        "snippet": "Informacja o transakcji",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-unrelated",
                        "sender": "Store <news@example.com>",
                        "subject": "Weekly sale",
                        "snippet": "Discounts",
                        "interpretation": "Promotion.",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-phish-001",
                    "sender": "no-reply@przelewy24.pl",
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                },
                target_label="",
                note="this is phishing. I never want emails like this again",
                scope="sender",
            )

            self.assertEqual(preview["impact"]["matching_existing_count"], 0)
            self.assertEqual(preview["impact"]["similar_candidate_count"], 1)
            self.assertEqual(preview["impact"]["similar_candidate_examples"][0]["message_id"], "gmail-live-phish-002")
            self.assertEqual(preview["impact"]["similar_candidate_examples"][0]["labels_after"], ["spam-low-value"])
            group_ids = {group["id"] for group in preview["impact"]["similar_candidate_groups"]}
            self.assertIn("same-domain", group_ids)
            self.assertIn("subject-pattern", group_ids)
            self.assertIn("przelewy24.pl", preview["impact"]["broader_rule_candidates"][0]["plain_english_rule"])

    def test_preview_requires_clearer_note_when_label_is_blank_and_intent_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Person <person@example.com>",
                        "subject": "Question",
                        "snippet": "What should this be?",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            with self.assertRaisesRegex(ValueError, "Choose a label"):
                build_sidebar_teach_preview(
                    storage_dir,
                    selected_context={
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                    },
                    target_label="",
                    note="this is wrong",
                    scope="sender",
                )

    def test_apply_matching_existing_relabels_current_and_matches_without_saving_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Application portal reminder",
                        "snippet": "Reminder",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = apply_sidebar_teaching(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                mode="matching-existing",
            )

            batch_one = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            batch_two = json.loads((storage_dir / "batches" / "founder-test-batch-2.json").read_text())

            self.assertIn("rewrote 1 matching stored emails", result["acknowledgment"])
            self.assertIn("did not save a future rule", result["acknowledgment"])
            self.assertEqual(result["matched_existing_count"], 1)
            self.assertEqual(batch_one["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(batch_two["items"][0]["final_labels"], ["job-related"])
            self.assertFalse((storage_dir / "teachable_classification_rules.json").exists())
            self.assertEqual(result["current"]["message_id"], "gmail-live-001")
            self.assertEqual([match["message_id"] for match in result["preview_matches"]], ["gmail-live-001", "gmail-live-002"])

    def test_excluded_matching_email_is_saved_and_protected_from_same_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Application portal reminder",
                        "snippet": "Reminder",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            exclusion = exclude_sidebar_teaching_match(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                excluded_message_id="gmail-live-002",
            )
            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
            )
            result = apply_sidebar_teaching(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                mode="matching-existing",
            )
            future_result = apply_sidebar_teaching(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                mode="save-future-rule",
            )
            batch_two = json.loads((storage_dir / "batches" / "founder-test-batch-2.json").read_text())
            saved_rule = TeachableRuleMemory(storage_dir / "teachable_classification_rules.json").list_rules()[0]

            self.assertIn("Exception saved", exclusion["acknowledgment"])
            self.assertEqual(exclusion["excluded_message_id"], "gmail-live-002")
            self.assertEqual(preview["impact"]["matching_existing_count"], 0)
            self.assertEqual(result["matched_existing_count"], 0)
            self.assertIn("saved a future rule", future_result["acknowledgment"])
            self.assertTrue(
                is_rule_message_excluded(
                    storage_dir,
                    rule=saved_rule.to_dict(),
                    message_id="gmail-live-002",
                )
            )
            self.assertEqual(batch_two["items"][0]["final_labels"], [])

    def test_apply_matching_existing_does_not_relabel_broader_similar_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-phish-001",
                        "sender": '"Przelewy24.pl" <no-reply@przelewy24.pl>',
                        "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                        "snippet": "Informacja o transakcji",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-phish-002",
                        "sender": '"Przelewy24.pl" <info@przelewy24.pl>',
                        "subject": "Nowa transakcja płatnicza (P24-G1M-B3Y-D5T)",
                        "snippet": "Informacja o transakcji",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-phish-001",
                    "sender": "no-reply@przelewy24.pl",
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                },
                target_label="",
                note="this is phishing. I never want emails like this again",
                scope="sender",
            )
            result = apply_sidebar_teaching(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-phish-001",
                    "sender": "no-reply@przelewy24.pl",
                    "subject": "Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)",
                },
                target_label="",
                note="this is phishing. I never want emails like this again",
                scope="sender",
                mode="matching-existing",
            )
            batch = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())

            self.assertEqual(preview["impact"]["matching_existing_count"], 0)
            self.assertEqual(preview["impact"]["similar_candidate_count"], 1)
            self.assertEqual(result["matched_existing_count"], 0)
            self.assertEqual(batch["items"][0]["final_labels"], ["spam-low-value"])
            self.assertEqual(batch["items"][1]["final_labels"], [])

    def test_save_future_rule_only_saves_rule_without_relabeling_existing_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Application portal reminder",
                        "snippet": "Reminder",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )

            result = apply_sidebar_teaching(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "sender": "notifications@ashbyhq.com",
                    "subject": "Interview update",
                },
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                mode="save-future-rule",
            )

            batch_one = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            rules = json.loads((storage_dir / "teachable_classification_rules.json").read_text())

            self.assertIn("saved a future rule", result["acknowledgment"])
            self.assertFalse(result["current_changed"])
            self.assertEqual(result["matched_existing_count"], 0)
            self.assertEqual(batch_one["items"][0]["final_labels"], [])
            self.assertEqual(batch_one["items"][1]["final_labels"], [])
            self.assertEqual(rules["rules"][0]["label"], "job-related")

    def test_write_through_selection_skips_future_rule_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {"message_id": "gmail-live-001", "final_labels": ["job-related"]},
                    {"message_id": "gmail-live-002", "final_labels": ["job-related"]},
                ],
            )

            selected = load_items_for_gmail_write_through(
                storage_dir,
                selected_message_id="gmail-live-001",
                mode="save-future-rule",
                preview_matches=[{"message_id": "gmail-live-002"}],
            )

            self.assertEqual(selected, {})

    def _write_batch(self, storage_dir: Path, batch_id: str, items: list[dict]) -> None:
        batch_dir = storage_dir / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "items": items,
                    "raw_messages": [],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
