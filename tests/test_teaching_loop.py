import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.candidate_change_store import CandidateChangeStore
from src.local_artifacts import candidate_changes_path, teachable_rules_path
from src.teaching_loop import (
    OpenAITeachingIntentClient,
    apply_rule_amendment_decision,
    apply_sidebar_teaching,
    build_sidebar_teach_preview,
    exclude_sidebar_teaching_match,
    load_items_for_gmail_write_through,
)
from src.teaching_exclusions import is_rule_message_excluded
from src.teachable_rule_memory import TeachableRule, TeachableRuleMemory, matching_rules_for_message


class TeachingLoopTests(unittest.TestCase):
    def test_teaching_intent_client_has_a_bounded_ui_timeout(self) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "target_label": "shopping-order",
                                    "semantic_pattern": "shipment emails",
                                    "cross_sender": True,
                                    "confidence": "high",
                                    "rationale": "Order shipment",
                                }
                            )
                        }
                    }
                ]
            }
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch("src.teaching_loop.urllib.request.urlopen", return_value=response) as urlopen:
            result = OpenAITeachingIntentClient("test-key", "test-model").interpret({"note": "shipment"})

        self.assertEqual(result["target_label"], "shopping-order")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 8)

        with patch("src.teaching_loop.urllib.request.urlopen", side_effect=TimeoutError("slow model")):
            self.assertEqual(OpenAITeachingIntentClient("test-key", "test-model").interpret({"note": "shipment"}), {})

    def test_saved_semantic_rule_keeps_same_sender_security_mail_out_of_orders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "amazon-shipment",
                        "sender": "Amazon <dispatch@amazon.example>",
                        "subject": "Your package was dispatched",
                        "snippet": "Track delivery",
                        "body": "Your order is on its way.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            note = (
                "Only shipment, delivery, and order-status messages should be Orders. "
                "Never include account-security, login, or password-reset messages."
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                result = apply_sidebar_teaching(
                    storage_dir,
                    selected_context={"provider": "gmail", "message_id": "amazon-shipment"},
                    target_label="shopping-order",
                    note=note,
                    scope="sender",
                    mode="save-future-rule",
                )

            saved_rules = result["candidate_change"]["metadata"]["rules"]
            memory_rules = [TeachableRule.from_dict(rule) for rule in saved_rules]
            self.assertEqual(
                [rule.id for rule in matching_rules_for_message(
                    {
                        "provider": "gmail",
                        "sender": "Amazon <dispatch@amazon.example>",
                        "subject": "Someone signed in to your account",
                        "snippet": "Reset your password",
                        "body": "We locked your account after a suspicious login.",
                    },
                    memory_rules,
                )],
                [],
            )
            self.assertTrue(saved_rules)

    def test_explicit_label_still_uses_llm_for_semantic_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "merchant-shipment",
                        "sender": "Merchant <dispatch@merchant.example>",
                        "subject": "Your parcel shipped",
                        "snippet": "Delivery update",
                        "body": "Your purchase is on its way.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            client = Mock()
            client.interpret.return_value = {
                "target_label": "account-security",
                "semantic_pattern": "shipment and delivery status emails",
                "cross_sender": True,
                "confidence": "high",
                "rationale": "The note describes a message family across merchants.",
            }

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=client):
                preview = build_sidebar_teach_preview(
                    storage_dir,
                    selected_context={"provider": "gmail", "message_id": "merchant-shipment"},
                    target_label="shopping-order",
                    note="Orders from any merchant, but never account-security messages.",
                    scope="sender",
                )

            client.interpret.assert_called_once()
            llm_payload = client.interpret.call_args.args[0]
            self.assertEqual(llm_payload["explicit_target_label"], "shopping-order")
            self.assertIn("purchase is on its way", llm_payload["current_body"])
            self.assertEqual(preview["selected_label_after"], ["shopping-order"])
            self.assertIn("shipment", preview["semantic_rule"]["semantic_pattern"])

    def test_explicit_order_lesson_uses_meaning_not_sender_for_existing_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "amazon-shipment",
                        "sender": "Amazon <dispatch@amazon.example>",
                        "subject": "Your package was dispatched",
                        "snippet": "Track your delivery",
                        "body": "Order 123 is on its way.",
                        "review_state": "reviewed",
                        "final_labels": ["shopping-order"],
                        "applied_labels": ["shopping-order"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "amazon-security",
                        "sender": "Amazon <dispatch@amazon.example>",
                        "subject": "Someone signed in to your account",
                        "snippet": "Reset your password if this was not you",
                        "body": "We locked your account after a suspicious login.",
                        "review_state": "pending",
                        "final_labels": ["account-security"],
                        "applied_labels": ["account-security"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "dhl-shipment",
                        "sender": "DHL <tracking@dhl.example>",
                        "subject": "Your shipment is out for delivery",
                        "snippet": "Track package 456",
                        "body": "Delivery is expected today.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "linkedin-delivery-job",
                        "sender": "LinkedIn Job Alerts <jobalerts@linkedin.example>",
                        "subject": "Technical Delivery Manager at Shopware",
                        "snippet": "A new project-management job matches your alert.",
                        "body": "Apply for this role. Email delivery preferences are in the footer.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "healthy-planet-newsletter",
                        "sender": "Healthy Planet <newsletter@healthy.example>",
                        "subject": "Mother's Day Beauty Sale",
                        "snippet": "Up to 40% off home spa products.",
                        "body": "Free shipping and delivery are available. Manage newsletter preferences.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                preview = build_sidebar_teach_preview(
                    storage_dir,
                    selected_context={"provider": "gmail", "message_id": "amazon-shipment"},
                    target_label="shopping-order",
                    note=(
                        "Apply this to shipment, delivery, order-confirmation, and order-status emails from any merchant. "
                        "Never include account-security, login, password-reset, privacy-policy, or promotional emails "
                        "merely because they come from the same merchant."
                    ),
                    scope="sender",
                )

            affected_ids = {
                item["message_id"] for item in preview["impact"]["matching_existing_items"]
            }
            self.assertEqual(affected_ids, {"dhl-shipment"})
            self.assertIn("shipment", preview["plain_english_rule"].lower())
            self.assertNotIn("account, security", preview["plain_english_rule"].lower())

    def test_low_value_privacy_note_is_not_reduced_to_generic_low_value_mail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "reddit-privacy",
                        "sender": "Reddit <noreply@redditmail.com>",
                        "subject": "Updates to Reddit's Privacy Policy and User Agreement",
                        "snippet": "We updated our privacy terms.",
                        "review_state": "pending",
                        "final_labels": ["spam-low-value"],
                        "applied_labels": ["spam-low-value"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "service-terms",
                        "sender": "Service <legal@service.example>",
                        "subject": "User Agreement update",
                        "snippet": "Our terms have changed.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "reddit-security",
                        "sender": "Reddit <noreply@redditmail.com>",
                        "subject": "Your Reddit account was locked",
                        "snippet": "Review the privacy policy linked in the footer.",
                        "review_state": "pending",
                        "final_labels": ["account-security"],
                        "applied_labels": ["account-security"],
                    },
                ],
            )
            note = (
                "Keep this as LowValue because it is a privacy-policy or user-agreement update that I do not need to act on. "
                "Apply this lesson to privacy-policy, terms-of-service, and user-agreement notices from any service, "
                "but do not include unrelated account-security, login, or password-reset emails."
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                preview = build_sidebar_teach_preview(
                    storage_dir,
                    selected_context={"provider": "gmail", "message_id": "reddit-privacy"},
                    target_label="spam-low-value",
                    note=note,
                    scope="sender",
                )

            self.assertIn("privacy-policy", preview["plain_english_rule"].lower())
            self.assertNotIn("low-value or suspicious", preview["plain_english_rule"].lower())
            self.assertEqual(
                {item["message_id"] for item in preview["impact"]["matching_existing_items"]},
                {"service-terms"},
            )

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
                        "subject": "Sophie Friend sent you a message",
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
                    "subject": "Sophie Friend sent you a message",
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

    def test_preview_accepts_explicitly_narrowed_newsletter_boundary_without_reasking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "zevi-001",
                        "sender": "Zevi Arnovitz <zevi@example.com>",
                        "subject": "The resource guide you requested",
                        "snippet": "Here is this week's guide and digest.",
                        "interpretation": "Looks promotional.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            vague_preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={"provider": "gmail", "message_id": "zevi-001"},
                target_label="newsletter",
                note="Keep newsletters from Zevi as Newsletter.",
                scope="sender",
            )
            narrowed_preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={"provider": "gmail", "message_id": "zevi-001"},
                target_label="newsletter",
                note=(
                    "Only resource, guide, newsletter, or digest emails that I requested should be Newsletter. "
                    "Exclude unrelated account or transactional mail. ReplyNeeded wins if a future message "
                    "directly asks me to respond."
                ),
                scope="sender",
            )

            self.assertTrue(vague_preview["clarifying_question"])
            self.assertEqual(narrowed_preview["selected_label_after"], ["newsletter"])
            self.assertEqual(narrowed_preview["semantic_rule"]["semantic_pattern"], "newsletter or digest emails")
            self.assertEqual(narrowed_preview["clarifying_question"], "")
            self.assertEqual(narrowed_preview["rule_confidence"], "medium")

    def test_preview_interprets_rejection_note_as_account_correction_not_wrong_existing_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "alltricks-001",
                        "sender": "Emma from Alltricks <contact@alltricks.com>",
                        "subject": "Welcome on Alltricks 👋",
                        "snippet": "Discover your customer area",
                        "body": "Your account has just been created. Choose a password. In your Client Account, you can find detailed information on your orders and choose your newsletter preferences.",
                        "interpretation": "General newsletter roundup with offers.",
                        "review_state": "reviewed",
                        "final_labels": ["newsletter", "travel", "personal"],
                        "applied_labels": ["newsletter", "travel", "personal"],
                    }
                ],
            )

            preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context={
                    "provider": "gmail",
                    "message_id": "alltricks-001",
                    "sender": "contact@alltricks.com",
                    "subject": "Welcome on Alltricks 👋",
                },
                target_label="",
                note="why is this also labelled as personal and travel??? That should not be the case. This isn't even newsletter as you should clearly be able to tell it is regarding my ACCOUNT",
                scope="sender",
            )

            self.assertEqual(preview["selected_label_after"], ["account-security"])
            self.assertEqual(preview["target_label_name"], "EA/Account")
            self.assertIn("account, security, or statement notices", preview["plain_english_rule"])

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
            saved_rule = future_result["candidate_change"]["metadata"]["rules"][0]

            self.assertIn("Exception saved", exclusion["acknowledgment"])
            self.assertEqual(exclusion["excluded_message_id"], "gmail-live-002")
            self.assertEqual(preview["impact"]["matching_existing_count"], 0)
            self.assertEqual(result["matched_existing_count"], 0)
            self.assertIn("saved a future rule", future_result["acknowledgment"])
            self.assertTrue(
                is_rule_message_excluded(storage_dir, rule=saved_rule, message_id="gmail-live-002")
            )
            self.assertEqual(batch_two["items"][0]["final_labels"], [])

    def test_apply_included_relabels_only_included_matches_and_saves_future_rule(self) -> None:
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
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-003",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview scheduling link",
                        "snippet": "Choose a calendar slot",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )
            selected_context = {
                "provider": "gmail",
                "message_id": "gmail-live-001",
                "sender": "notifications@ashbyhq.com",
                "subject": "Interview update",
            }

            exclude_sidebar_teaching_match(
                storage_dir,
                selected_context=selected_context,
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                excluded_message_id="gmail-live-002",
            )
            result = apply_sidebar_teaching(
                storage_dir,
                selected_context=selected_context,
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                mode="apply-included",
                included_message_ids=["gmail-live-003"],
            )
            batch = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            candidates = CandidateChangeStore(candidate_changes_path(storage_dir)).list_candidates()

            self.assertIn("saved a future rule", result["acknowledgment"])
            self.assertEqual(result["matched_existing_count"], 1)
            self.assertEqual(result["exceptions_saved_count"], 1)
            self.assertEqual(result["future_rule_saved"], True)
            self.assertEqual(batch["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(batch["items"][1]["final_labels"], [])
            self.assertEqual(batch["items"][2]["final_labels"], ["job-related"])
            self.assertEqual(len(candidates), 1)

    def test_future_only_activates_the_rule_after_explicit_user_confirmation(self) -> None:
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
                        "sender": "noreply@1se.co",
                        "subject": "[1SE] Your 1SE account is inactive and will be deleted soon.",
                        "snippet": "Your inactive account is scheduled for deletion.",
                        "body": "Sign in if you do not want your account deleted.",
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
                    "sender": "noreply@1se.co",
                    "subject": "[1SE] Your 1SE account is inactive and will be deleted soon.",
                },
                target_label="account-security",
                note="This is clearly an account email.",
                scope="sender",
                mode="future-only",
            )

            rules = TeachableRuleMemory(teachable_rules_path(storage_dir)).list_rules()
            candidates = CandidateChangeStore(candidate_changes_path(storage_dir)).list_candidates()

            self.assertEqual(result["proposal"]["status"], "approved")
            self.assertTrue(result["proposal"]["approved_rule_id"])
            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0].label, "account-security")
            self.assertEqual(candidates[0].status, "promoted")
            self.assertIn("saved a future rule", result["acknowledgment"])
            self.assertNotIn("candidate for evaluation", result["acknowledgment"])

    def test_exclusion_proposes_rule_amendment_without_applying_it_silently(self) -> None:
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
                        "subject": "Marketing newsletter from Ashby",
                        "snippet": "Product updates",
                        "interpretation": "No confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )
            selected_context = {
                "provider": "gmail",
                "message_id": "gmail-live-001",
                "sender": "notifications@ashbyhq.com",
                "subject": "Interview update",
            }

            exclusion = exclude_sidebar_teaching_match(
                storage_dir,
                selected_context=selected_context,
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                excluded_message_id="gmail-live-002",
                reason="This one is a marketing newsletter, not an interview or recruiter message.",
            )
            original_preview = build_sidebar_teach_preview(
                storage_dir,
                selected_context=selected_context,
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
            )
            accepted = apply_rule_amendment_decision(
                storage_dir,
                selected_context=selected_context,
                target_label="job-related",
                note="Ashby interview workflow messages should be job-related and kept visible.",
                scope="sender",
                amendment=exclusion["amendment_proposal"],
                decision="accept",
            )

            self.assertEqual(exclusion["amendment_proposal"]["status"], "proposed")
            self.assertIn("marketing newsletter", exclusion["amendment_proposal"]["plain_english_rule"])
            self.assertIn("Treat job, recruiter, or interview emails", original_preview["plain_english_rule"])
            self.assertNotIn("except", original_preview["plain_english_rule"])
            self.assertEqual(accepted["amendment_status"], "accepted")
            self.assertIn("except", accepted["preview"]["plain_english_rule"])
            self.assertEqual(accepted["preview"]["impact"]["matching_existing_count"], 0)

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
            candidates = CandidateChangeStore(candidate_changes_path(storage_dir)).list_candidates()

            self.assertIn("saved a future rule", result["acknowledgment"])
            self.assertFalse(result["current_changed"])
            self.assertEqual(result["matched_existing_count"], 0)
            self.assertEqual(batch_one["items"][0]["final_labels"], [])
            self.assertEqual(batch_one["items"][1]["final_labels"], [])
            self.assertEqual(candidates[0].kind, "future-rule")
            self.assertEqual(candidates[0].metadata["rules"][0]["label"], "job-related")

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
