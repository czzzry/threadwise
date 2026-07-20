import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.run_gmail_companion_simulator import main as run_simulator_main

from src.attention_feedback import load_attention_feedback
from src.attention_rules import attention_rules_path
from src.candidate_change_store import CandidateChange, CandidateChangeStore
from src.companion_teaching_workflow import TeachingWorkflowResult
from src.founder_feedback import load_founder_feedback
from src.gmail_run_control import load_gmail_dashboard_run_status, write_gmail_dashboard_run_status
from src.gmail_companion_rendering import (
    escape_html,
    render_dashboard_email_cards,
    render_dashboard_unsubscribe_cards,
    server_origin,
    unsubscribe_section_key,
)
from src.gmail_companion_state import (
    build_companion_runtime_payload,
    build_runtime_item,
    build_selected_email_state,
    classify_handling_status,
    load_latest_batch,
    selected_email_understanding_state,
    selected_context_from_query,
    selected_email_contract,
)
from src.gmail_companion_ui import GmailCompanionApp, main, script_safe_json
from src.gmail_writer import MockGmailLabelClient, MockGmailLabelWriter
from src.local_artifacts import candidate_changes_path
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore
from src.unsubscribe_execution import UnsubscribeExecutor


class GmailCompanionUiTests(unittest.TestCase):
    def test_suspicious_cannot_use_ordinary_teach_apply_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "safety"):
            GmailCompanionApp(Path("/tmp/example")).teach_apply({
                "selected_context": {"provider": "gmail", "message_id": "phish-1"},
                "target_label": "suspicious",
                "note": "phishing",
                "mode": "current-only",
            })

    def test_suspicious_preview_uses_authoritative_selected_sender_and_exact_sender_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [{
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": "phish-1",
                    "sender": "Fake delivery <bait@bad.example>",
                    "subject": "Delivery suspended",
                    "review_state": "pending",
                    "final_labels": [],
                    "applied_labels": [],
                }],
            )

            preview = GmailCompanionApp(storage_dir).safety_preview({
                "selected_context": {"provider": "gmail", "message_id": "phish-1"},
                "scope": "sender",
                "sender": "attacker-controlled@different.example",
            })

            self.assertEqual(preview["match"], "bait@bad.example")
            self.assertTrue(preview["requires_confirmation"])

    def test_suspicious_apply_requests_safety_scope_and_applies_confirmed_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [{
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": "phish-1",
                    "sender": "Fake delivery <bait@bad.example>",
                    "subject": "Delivery suspended",
                    "review_state": "pending",
                    "final_labels": [],
                    "applied_labels": [],
                }],
            )
            gmail_client = MockGmailLabelClient()
            gmail_client.create_trash_filter = lambda match, label_id: "filter-1"
            gmail_client.trash_message = lambda message_id: gmail_client.calls.append(("trash_message", message_id))
            gmail_client.delete_filter = lambda filter_id: gmail_client.calls.append(("delete_filter", filter_id))
            requested_scopes = []

            def factory(account_id, credentials_dir, client_secret_path, required_scope):
                requested_scopes.append(required_scope)
                return gmail_client

            result = GmailCompanionApp(storage_dir, gmail_client_factory=factory).safety_apply({
                "selected_context": {"provider": "gmail", "message_id": "phish-1"},
                "scope": "sender",
                "confirmed": True,
            })

            self.assertEqual(result["status"], "applied")
            self.assertIn("gmail.settings.basic", requested_scopes[0])
            self.assertIn(("trash_message", "phish-1"), gmail_client.calls)

    def test_review_queue_refreshes_five_amazon_variants_without_turning_security_into_orders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)

            def raw(message_id: str, sender: str, subject: str, snippet: str, labels: list[str] | None = None) -> dict:
                return {
                    "id": message_id,
                    "internalDate": "1718784000000",
                    "snippet": snippet,
                    "labelIds": labels or ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": sender},
                            {"name": "Subject", "value": subject},
                            {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                        ]
                    },
                }

            raw_messages = [
                raw("amazon-dispatched", '"Amazon.de" <versandbestaetigung@amazon.de>', "Dispatched: hammock", "Your order was dispatched."),
                raw("amazon-order", '"Amazon.de" <bestellbestaetigung@amazon.de>', "Ihre Amazon.de Bestellung von Rushmore", "Bestellung bestätigt."),
                raw("amazon-return", '"rueckgabe@amazon.de" <rueckgabe@amazon.de>', "Your return drop-off confirmation", "Your return was dropped off."),
                raw("amazon-security", 'Amazon <account-update@amazon.de>', "amazon.de: Account data access attempt", "Someone is attempting to access your account data."),
                raw("amazon-prime-welcome", 'Amazon Prime <prime@amazon.com>', "Welcome back to Prime!", "See your Prime benefits.", ["INBOX", "CATEGORY_PROMOTIONS"]),
            ]
            stale_items = [
                {
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": message["id"],
                    "sender": next(header["value"] for header in message["payload"]["headers"] if header["name"] == "From"),
                    "subject": next(header["value"] for header in message["payload"]["headers"] if header["name"] == "Subject"),
                    "review_state": "pending",
                    "final_labels": [],
                    "applied_labels": [],
                    "near_misses": [],
                }
                for message in raw_messages
            ]
            self._write_batch(storage_dir, "founder-test-batch-1", stale_items, raw_messages)

            payload = build_companion_runtime_payload(storage_dir)
            queue = {item["message_id"]: item for item in payload["needs_attention_items"]}

            self.assertEqual(queue["amazon-dispatched"]["suggested_label"], "shopping-order")
            self.assertEqual(queue["amazon-order"]["suggested_label"], "shopping-order")
            self.assertEqual(queue["amazon-return"]["suggested_label"], "shopping-order")
            self.assertEqual(queue["amazon-security"]["suggested_label"], "account-security")
            self.assertNotEqual(queue["amazon-prime-welcome"]["suggested_label"], "shopping-order")

    def test_selected_email_uses_the_same_refreshed_classification_as_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            raw_message = {
                "id": "bad-axe-visit",
                "internalDate": "1716027383000",
                "snippet": "Your visit is booked for Saturday at 12:00.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Piotr from BAD AXE <badaxe@badaxe.pl>"},
                        {"name": "Subject", "value": "Wizyta BAD AXE"},
                        {"name": "Date", "value": "Sat, 18 May 2024 10:16:23 +0000"},
                    ]
                },
            }
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "bad-axe-visit",
                        "sender": "Piotr from BAD AXE <badaxe@badaxe.pl>",
                        "subject": "Wizyta BAD AXE",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
                [raw_message],
            )

            state = GmailCompanionApp(storage_dir).harness_state(
                {"provider": "gmail", "message_id": "bad-axe-visit"}
            )
            queue_item = state["needs_attention_items"][0]
            selected = state["sidebar_state"]["selected_email"]

            self.assertEqual(queue_item["internal_label"], "calendar-event")
            self.assertEqual(selected["internal_label"], queue_item["internal_label"])
            self.assertEqual(selected["classification"], queue_item["classification"])
            self.assertEqual(selected["suggested_label"], queue_item["suggested_label"])
            self.assertIn("EA/Calendar", selected["reason"])
            self.assertNotIn("no confident category", selected["reason"])

    def test_live_review_queue_excludes_locally_stale_messages_no_longer_in_gmail_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            items = []
            raw_messages = []
            for message_id, subject in (("still-in-inbox", "Keep reviewing"), ("now-in-trash", "Deleted in Gmail")):
                items.append(
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": message_id,
                        "sender": "Store <store@example.com>",
                        "subject": subject,
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                )
                raw_messages.append(
                    {
                        "id": message_id,
                        "internalDate": "1716027383000",
                        "snippet": "Stored before the Gmail deletion.",
                        "labelIds": ["INBOX"],
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <store@example.com>"},
                                {"name": "Subject", "value": subject},
                                {"name": "Date", "value": "Sat, 18 May 2024 10:16:23 +0000"},
                            ]
                        },
                    }
                )
            self._write_batch(storage_dir, "founder-test-batch-1", items, raw_messages)
            gmail_client = SimpleNamespace(
                search_message_ids=lambda query, max_results: ["still-in-inbox"]
            )
            app = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda *args, **kwargs: gmail_client,
                live_inbox_reconciliation_enabled=True,
            )

            state = app.harness_state({})

            self.assertEqual(
                [item["message_id"] for item in state["needs_attention_items"]],
                ["still-in-inbox"],
            )
            self.assertEqual(state["sidebar_state"]["daily_summary"]["needs_attention_count"], 1)

    def test_review_cards_distinguish_same_subject_messages_by_received_time(self) -> None:
        runtime_item = build_runtime_item(
            {"provider": "gmail", "account_id": "founder-test", "batch_id": "batch-1"},
            {
                "message_id": "message-1",
                "subject": "Repeated subject",
                "sender": "sender@example.com",
                "date": "2024-03-29T21:53:42Z",
            },
            {},
            None,
            None,
        )
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertEqual(runtime_item["received_at"], "2024-03-29T21:53:42Z")
        self.assertIn("function reviewReceivedLabel", content_js)
        self.assertIn('data-ea-review-received-at', content_js)
        self.assertIn("reviewReceivedLabel(selected.received_at)", content_js)

    def test_home_surfaces_analytics_delivery_health_without_claiming_remote_ingestion(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("Analytics delivery issue", content_js)
        self.assertIn("Analytics active", content_js)
        self.assertIn("No SDK delivery errors detected", content_js)
        self.assertIn("PostHog arrival is checked separately", content_js)

    def test_extension_analytics_failure_cannot_block_product_actions(self) -> None:
        analytics_js = Path("extensions/gmail_companion/analytics.js").read_text()

        self.assertIn("Analytics is an observer and must never block the user workflow.", analytics_js)
        self.assertIn("catch (_error)", analytics_js)
        self.assertIn("return false;", analytics_js)

    def test_review_identity_does_not_collapse_distinct_gmail_messages_with_the_same_subject(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("if (current.messageId && itemMessageId)", content_js)
        self.assertIn("return itemMessageId === current.messageId;", content_js)
        self.assertIn("if (current.threadId && itemThreadId)", content_js)
        self.assertIn("return itemThreadId === current.threadId;", content_js)

    def test_handled_receipt_offers_a_direct_looks_right_next_action(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn('data-ea-action="confirm-handled-and-next"', content_js)
        self.assertIn("Looks right · Next", content_js)
        self.assertIn("confirmHandledAndOpenNext", content_js)
        self.assertIn('confirmHandledButton.textContent = "Opening next…"', content_js)
        self.assertIn("currentBelongsToActiveQueue ? activeSummaryFilter", content_js)
        self.assertIn("Product actions must continue even when optional analytics is unavailable.", content_js)
        self.assertIn('path: "/api/handled-review-acknowledge"', content_js)
        self.assertIn("Threadwise will not offer this email again", content_js)

    def test_current_email_apply_reconciles_an_uncertain_transport_result(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("reconcileCurrentApplyAfterTransportFailure", content_js)
        self.assertIn('type: "email-agent:get-state"', content_js)
        self.assertIn('selected.details?.write_status === "applied"', content_js)
        self.assertIn("sameMessage && appliedLabel === targetLabel && writeApplied", content_js)
        self.assertIn("Threadwise confirmed the completed Gmail change after reconnecting.", content_js)

    def test_opening_a_queue_email_in_gmail_keeps_the_review_context_pinned(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()
        refresh_body = content_js.split("function refreshSelection(force = false)", 1)[1].split(
            "function asyncFollowUpIsWorking", 1
        )[0]

        self.assertIn("const context = chooseRefreshContext();", refresh_body)
        self.assertNotIn("manualPreviewContext = null", refresh_body)
        self.assertIn("if (manualPreviewContext)", content_js)
        self.assertIn("return manualPreviewContext;", content_js)

    def test_clicking_gmail_after_a_completed_queue_receipt_follows_the_new_email(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("releaseCompletedQueuePreviewOnGmailClick(event)", content_js)
        self.assertIn('[data-ea-selected-state="receipt"]', content_js)
        self.assertIn('[data-ea-selected-state="teach-result-receipt"]', content_js)
        self.assertIn("manualPreviewContext = null;", content_js)
        self.assertIn("resetPerEmailInteraction();", content_js)
        self.assertIn('document.addEventListener("click", documentClickListener, true);', content_js)

    def test_explicit_home_survives_transient_gmail_identity_changes(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()
        home_body = content_js.split("function openThreadwiseHome(event)", 1)[1].split(
            "function handleBrandToggle", 1
        )[0]
        refresh_body = content_js.split("function refreshSelection(force = false)", 1)[1].split(
            "function asyncFollowUpIsWorking", 1
        )[0]

        self.assertIn("forcedHomeLiveContext = { ...selectedContext() };", home_body)
        self.assertIn("lastLiveContext.page_url !== forcedHomeLiveContext.page_url", refresh_body)
        self.assertNotIn("!contextsMatch(lastLiveContext, forcedHomeLiveContext)", refresh_body)

    def test_every_successful_broader_correction_can_continue_the_review_queue(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()
        receipt_body = content_js.split('workspaceMode === "teach-result-receipt"', 1)[1].split(
            'workspaceMode === "current-receipt"', 1
        )[0]

        self.assertIn("remainingNeedsAttentionItems().length > 0", receipt_body)
        self.assertIn('data-ea-action="open-needs-attention"', receipt_body)
        self.assertIn("Next email", receipt_body)
        self.assertIn("Review queue complete.", receipt_body)

    def test_completed_receipt_does_not_pin_the_previous_gmail_message(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()
        hold_body = content_js.split("function shouldHoldSelectedContext()", 1)[1].split(
            "function hasTeachDraftChanges", 1
        )[0]

        self.assertIn('"previewing", "applying", "scope-confirmation"', hold_body)
        self.assertIn("correctionInProgress", hold_body)
        self.assertNotIn("hasTeachDraftChanges()", hold_body)

    def test_refining_a_rule_preserves_the_founder_note_instead_of_the_model_summary(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("previousTeachPreview = teachPreview", content_js)
        self.assertNotIn("note: previousTeachPreview.plain_english_rule", content_js)

    def test_review_navigation_never_falls_back_to_the_completed_current_item(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertNotIn(
            "items.find((item) => !currentMessageId || item.message_id !== currentMessageId) || items[0]",
            content_js,
        )
        self.assertIn('title: filter === "needs_attention_items" ? "Review queue complete"', content_js)

    def test_new_gmail_selection_leaves_home_for_a_reading_transition_immediately(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("renderSelectedEmailTransition(context)", content_js)
        self.assertIn("Reading this email…", content_js)

    def test_capped_live_preview_discloses_that_unreviewed_messages_will_not_change(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn("More inbox emails may match, but they will not be changed.", content_js)
        self.assertIn("The live inbox scan was capped; unreviewed messages will not be changed.", content_js)

    def test_teach_preview_inspects_remote_candidates_and_exposes_only_semantic_matches(self) -> None:
        class InspectableSearchClient(MockGmailLabelClient):
            def __init__(self, payloads: dict[str, dict]) -> None:
                super().__init__()
                self.payloads = payloads

            def search_message_ids(self, query: str, max_results: int) -> list[str]:
                self.calls.append(("search_message_ids", query, max_results))
                return list(self.payloads)[:max_results]

            def get_message(self, message_id: str) -> dict:
                self.calls.append(("get_message", message_id))
                return self.payloads[message_id]

        def payload(message_id: str, sender: str, subject: str, snippet: str) -> dict:
            return {
                "id": message_id,
                "threadId": f"thread-{message_id}",
                "internalDate": "1718784000000",
                "snippet": snippet,
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": sender},
                        {"name": "Subject", "value": subject},
                    ]
                },
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "amazon-shipment",
                        "sender": "Amazon <dispatch@amazon.example>",
                        "subject": "Your order shipped",
                        "snippet": "Track your delivery",
                        "body": "Your purchase is on its way.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            gmail_client = InspectableSearchClient(
                {
                    "remote-security": payload(
                        "remote-security",
                        "Amazon <dispatch@amazon.example>",
                        "Someone signed in to your account",
                        "Reset your password after this suspicious login.",
                    ),
                    "remote-shipment": payload(
                        "remote-shipment",
                        "DHL <tracking@dhl.example>",
                        "Shipment out for delivery",
                        "Track your package arriving today.",
                    ),
                }
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                preview = GmailCompanionApp(
                    storage_dir,
                    gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
                ).teach_preview(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "amazon-shipment"},
                        "target_label": "shopping-order",
                        "note": (
                            "Apply to shipment and delivery messages from any merchant. "
                            "Never include account-security, login, or password-reset emails."
                        ),
                    }
                )

            self.assertEqual(
                [item["message_id"] for item in preview["inbox_backfill"]["matches"]],
                ["remote-shipment"],
            )
            self.assertEqual(preview["inbox_backfill"]["estimated_count"], 1)
            self.assertIn("remote-shipment", {
                item["message_id"] for item in preview["impact"]["matching_existing_items"]
            })
            self.assertNotIn("remote-security", {
                item["message_id"] for item in preview["impact"]["matching_existing_items"]
            })

    def test_initial_teach_preview_does_not_wait_for_live_gmail_impact_scan(self) -> None:
        class FailingIfScannedClient(MockGmailLabelClient):
            def search_message_ids(self, query: str, max_results: int) -> list[str]:
                raise AssertionError("the initial rule preview must not scan Gmail")

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "current-order",
                        "sender": "Merchant <orders@example.com>",
                        "subject": "Your order shipped",
                        "snippet": "Track your package.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            gmail_client = FailingIfScannedClient()

            with (
                patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None),
                patch("src.teaching_loop.load_storage_items", side_effect=AssertionError("initial preview must not scan stored inbox history")),
            ):
                preview = GmailCompanionApp(
                    storage_dir,
                    gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
                ).teach_preview_initial(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "current-order"},
                        "target_label": "shopping-order",
                        "note": "Apply to order and shipment emails from any merchant.",
                    }
                )

            self.assertEqual(preview["inbox_backfill"]["state"], "working")
            self.assertEqual(gmail_client.calls, [])

    def test_teach_preview_impact_finishes_the_deferred_live_gmail_scan(self) -> None:
        class InspectableClient(MockGmailLabelClient):
            def search_message_ids(self, query: str, max_results: int) -> list[str]:
                return ["remote-order"]

            def get_message(self, message_id: str) -> dict:
                return {
                    "id": message_id,
                    "threadId": f"thread-{message_id}",
                    "internalDate": "1718784000000",
                    "snippet": "Shipment dispatched and arriving today.",
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Merchant <orders@example.com>"},
                            {"name": "Subject", "value": "Shipment dispatched"},
                        ]
                    },
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "current-order",
                        "sender": "Merchant <orders@example.com>",
                        "subject": "Your order shipped",
                        "snippet": "Track your package.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            gmail_client = InspectableClient()
            app = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                initial = app.teach_preview_initial(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "current-order"},
                        "target_label": "shopping-order",
                        "note": "Apply to order and shipment emails from any merchant.",
                    }
                )
            completed = app.teach_preview_impact({"preview": initial})

            self.assertEqual(completed["inbox_backfill"]["state"], "ready")
            self.assertEqual(completed["inbox_backfill"]["estimated_count"], 1)
            self.assertIn("remote-order", {
                item["message_id"] for item in completed["impact"]["matching_existing_items"]
            })

    def test_extension_renders_rule_before_requesting_deferred_inbox_impact(self) -> None:
        content_js = Path("extensions/gmail_companion/content.js").read_text()

        self.assertIn('path: "/api/teach-preview-impact"', content_js)
        self.assertIn("Checking matching inbox emails…", content_js)
        self.assertIn("Inbox match scan couldn’t finish", content_js)
        self.assertIn('state: "unavailable"', content_js)
        self.assertIn("loadTeachPreviewImpact", content_js)

    def test_teach_preview_inspects_remote_candidates_concurrently(self) -> None:
        class ConcurrentInspectableClient(MockGmailLabelClient):
            def __init__(self) -> None:
                super().__init__()
                self.active = 0
                self.max_active = 0
                self.lock = threading.Lock()

            def search_message_ids(self, query: str, max_results: int) -> list[str]:
                return [f"remote-order-{index}" for index in range(12)]

            def get_message(self, message_id: str) -> dict:
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                time.sleep(0.02)
                with self.lock:
                    self.active -= 1
                return {
                    "id": message_id,
                    "threadId": f"thread-{message_id}",
                    "internalDate": "1718784000000",
                    "snippet": "Shipment dispatched and arriving today.",
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Merchant <orders@example.com>"},
                            {"name": "Subject", "value": "Shipment dispatched"},
                        ]
                    },
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "current-order",
                        "sender": "Merchant <orders@example.com>",
                        "subject": "Your order shipped",
                        "snippet": "Track your package.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            gmail_client = ConcurrentInspectableClient()

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                preview = GmailCompanionApp(
                    storage_dir,
                    gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
                ).teach_preview(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "current-order"},
                        "target_label": "shopping-order",
                        "note": "Apply to order and shipment emails from any merchant.",
                    }
                )

            self.assertGreater(gmail_client.max_active, 1)
            self.assertEqual(preview["inbox_backfill"]["estimated_count"], 12)

    def test_combined_local_and_live_preview_is_capped_to_reviewable_exact_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": f"order-{index}",
                        "sender": f"Merchant {index} <orders-{index}@example.com>",
                        "subject": f"Shipment {index} dispatched",
                        "snippet": "Delivery status for your purchase.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                    for index in range(31)
                ],
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                preview = GmailCompanionApp(
                    storage_dir,
                    gmail_write_through_enabled=False,
                ).teach_preview(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "order-0"},
                        "target_label": "shopping-order",
                        "note": "Apply to shipment and delivery emails from any merchant.",
                    }
                )

            reviewed_ids = [item["message_id"] for item in preview["impact"]["matching_existing_items"]]
            self.assertEqual(len(reviewed_ids), 25)
            self.assertEqual(len(set(reviewed_ids)), 25)
            self.assertEqual(preview["impact"]["matching_existing_count"], 25)
            self.assertEqual(preview["structured_rule"]["applies_to_existing_count"], 25)
            self.assertTrue(preview["inbox_backfill"]["is_capped"])
            self.assertTrue(preview["inbox_backfill"]["requires_confirmation"])

    def test_apply_included_writes_only_explicitly_reviewed_message_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient(
                search_results_by_query={
                    "{shipment shipping delivery dispatched tracking order}": [
                        "amazon-shipment",
                        "remote-shipment",
                        "remote-security",
                    ]
                }
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "amazon-shipment",
                        "sender": "Amazon <dispatch@amazon.example>",
                        "subject": "Your order shipped",
                        "snippet": "Track your delivery",
                        "body": "Your purchase is on its way.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                result = GmailCompanionApp(
                    storage_dir,
                    gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
                ).teach_apply(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "amazon-shipment"},
                        "target_label": "shopping-order",
                        "note": (
                            "Apply to shipment and delivery messages from any merchant. "
                            "Never include account-security or login emails."
                        ),
                        "mode": "apply-included",
                        "included_message_ids": ["remote-shipment"],
                    }
                )

            written_ids = {
                call[1]
                for call in gmail_client.calls
                if call[0] == "replace_threadwise_labels"
            }
            self.assertEqual(written_ids, {"amazon-shipment", "remote-shipment"})
            self.assertEqual(result["gmail_write_through"]["remote_match_count"], 1)


    def test_script_safe_json_round_trips_hostile_unsubscribe_candidate_key(self) -> None:
        hostile_key = "gmail:test:</script><script>window.pwned=1</script>&@example.com"

        encoded = script_safe_json([hostile_key])

        self.assertNotIn("</script>", encoded)
        self.assertIn("\\u003c/script\\u003e", encoded)
        self.assertIn("\\u0026", encoded)
        self.assertEqual(json.loads(encoded), [hostile_key])

    def test_unsubscribe_page_embeds_candidate_keys_in_script_safe_json(self) -> None:
        hostile_key = "gmail:test:</script><script>window.pwned=1</script>&@example.com"
        app = GmailCompanionApp(Path("/tmp/example"))
        candidate = {"list_key": hostile_key}
        detail = {
            "list_key": hostile_key,
            "display_name": "Hostile fixture",
            "sender": "fixture@example.com",
            "decision_state": "undecided",
            "evidence_count": 1,
            "latest_execution": None,
            "preview": {"status": "unsupported", "method": "unsupported", "notes": "Manual follow-up", "url": ""},
        }
        with (
            patch.object(app._unsubscribe_store, "list_candidates", return_value=[candidate]),
            patch("src.gmail_companion_ui.build_unsubscribe_detail", return_value=detail),
        ):
            page = app.render_unsubscribe_review_page()

        candidate_script = page.split("const candidateKeys = ", 1)[1].split(";", 1)[0]
        self.assertNotIn("</script>", candidate_script)
        self.assertEqual(json.loads(candidate_script), [hostile_key])
        self.assertIn("data-unsubscribe-candidate=\"gmail:test:&lt;/script&gt;&lt;script&gt;window.pwned=1&lt;/script&gt;&amp;@example.com\"", page)

    def test_companion_state_module_preserves_selected_context_contract(self) -> None:
        context = selected_context_from_query(
            {
                "provider": ["gmail"],
                "message_id": ["msg-1"],
                "thread_id": ["thread-1"],
                "subject": ["Subject"],
                "sender": ["Sender <sender@example.com>"],
                "page_url": ["https://mail.google.com"],
                "selected_at": ["2026-06-30T10:00:00Z"],
                "gmail_labels": ["EA/Finance"],
            }
        )

        self.assertEqual(
            context,
            {
                "provider": "gmail",
                "message_id": "msg-1",
                "thread_id": "thread-1",
                "subject": "Subject",
                "sender": "Sender <sender@example.com>",
                "page_url": "https://mail.google.com",
                "selected_at": "2026-06-30T10:00:00Z",
                "gmail_labels": "EA/Finance",
            },
        )
        self.assertEqual(selected_email_contract()["contract_version"], "gmail-companion-selected-email-v1")

    def test_companion_state_module_preserves_selected_email_status_rules(self) -> None:
        self.assertEqual(
            classify_handling_status({"review_state": "pending", "applied_labels": []}, None, None),
            ("needs-attention", "Needs attention"),
        )
        self.assertEqual(
            classify_handling_status({"review_state": "reviewed", "final_labels": ["promotions"]}, "applied", "applied"),
            ("auto-handled", "Auto-handled"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            selected = build_selected_email_state(
                Path(temp_dir),
                [],
                {"message_id": "missing-1", "subject": "Fresh email", "sender": "New <new@example.com>"},
            )

        self.assertFalse(selected["found"])
        self.assertEqual(selected["status"], "not-in-snapshot")
        self.assertEqual(selected["status_label"], "Not in local snapshot")

    def test_selected_email_understanding_state_progresses_from_reading_to_ready(self) -> None:
        context = {
            "message_id": "gmail-live-001",
            "subject": "Interview update",
            "sender": "notifications@example.com",
            "selected_at": "2026-07-10T10:00:00Z",
        }

        reading = selected_email_understanding_state(
            context,
            now=datetime.fromisoformat("2026-07-10T10:00:00+00:00"),
        )
        understanding = selected_email_understanding_state(
            context,
            now=datetime.fromisoformat("2026-07-10T10:00:01+00:00"),
        )
        ready = selected_email_understanding_state(
            context,
            now=datetime.fromisoformat("2026-07-10T10:00:02+00:00"),
        )

        self.assertEqual(reading["understanding_state"], "reading")
        self.assertEqual(understanding["understanding_state"], "understanding")
        self.assertEqual(ready["understanding_state"], "ready")

    def test_companion_state_exposes_all_classifications_when_message_has_multiple_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_dir = storage_dir / "batches"
            batch_dir.mkdir(parents=True, exist_ok=True)
            (batch_dir / "founder-test-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "items": [
                            {
                                "message_id": "gmail-live-001",
                                "sender": "Emma from Alltricks <contact@alltricks.com>",
                                "subject": "Welcome on Alltricks 👋",
                                "review_state": "reviewed",
                                "review_action": "auto-approve",
                                "final_labels": ["newsletter", "travel", "personal"],
                                "applied_labels": ["newsletter", "travel", "personal"],
                            }
                        ],
                    }
                )
            )

            selected = build_selected_email_state(
                storage_dir,
                [],
                {
                    "message_id": "gmail-live-001",
                    "subject": "Welcome on Alltricks 👋",
                    "sender": "Emma from Alltricks <contact@alltricks.com>",
                },
            )

        self.assertEqual(selected["classification"], "EA/Newsletter")
        self.assertEqual(selected["all_classifications"], ["EA/Newsletter", "EA/Travel", "EA/Personal"])

    def test_selected_message_id_wins_over_newer_sender_subject_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batches_dir = storage_dir / "batches"
            batches_dir.mkdir(parents=True, exist_ok=True)
            shared = {
                "sender": '"return@amazon.com" <return@amazon.com>',
                "subject": "Let us know how we did - Amazon Product Support",
            }
            (batches_dir / "founder-test-batch-1.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "items": [
                            {
                                **shared,
                                "message_id": "older-exact-message",
                                "review_state": "pending",
                                "final_labels": [],
                                "applied_labels": [],
                            }
                        ],
                    }
                )
            )
            (batches_dir / "founder-test-batch-2.json").write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-2",
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "items": [
                            {
                                **shared,
                                "message_id": "newer-same-subject",
                                "review_state": "reviewed",
                                "final_labels": ["spam-low-value"],
                                "applied_labels": ["spam-low-value"],
                            }
                        ],
                    }
                )
            )

            selected = build_selected_email_state(
                storage_dir,
                [],
                {"provider": "gmail", "message_id": "older-exact-message", **shared},
            )

        self.assertEqual(selected["message_id"], "older-exact-message")
        self.assertEqual(selected["status"], "needs-attention")

    def test_companion_rendering_module_preserves_shared_helpers(self) -> None:
        self.assertEqual(escape_html('<a href="x">Tom & Jerry</a>'), "&lt;a href=&quot;x&quot;&gt;Tom &amp; Jerry&lt;/a&gt;")
        self.assertEqual(server_origin("127.0.0.1:8021"), "http://127.0.0.1:8021")
        self.assertEqual(server_origin("https://example.test"), "https://example.test")
        self.assertEqual(unsubscribe_section_key({"decision_state": "selected"}, {"status": "ready"}), "queued")
        empty_cards = render_dashboard_email_cards([], empty_label="No recent mail")
        self.assertIn("No recent mail", empty_cards)
        self.assertIn('class="empty-state"', empty_cards)
        self.assertNotIn('class="email-card"', empty_cards)
        rendered_card = render_dashboard_email_cards(
            [
                {
                    "subject": "Google Account Closure Notice",
                    "sender": "Google <accounts@example.com>",
                    "classification": "EA/LowValue",
                    "status_label": "Kept visible",
                }
            ],
            empty_label="No recent mail",
        )
        self.assertIn("Open in Gmail", rendered_card)
        self.assertIn("https://mail.google.com/mail/u/0/#search/", rendered_card)
        empty_subscriptions = render_dashboard_unsubscribe_cards([])
        self.assertIn('class="empty-state"', empty_subscriptions)
        self.assertNotIn('class="email-card"', empty_subscriptions)
        queued_subscription = render_dashboard_unsubscribe_cards(
            [
                {
                    "display_name": "Store updates",
                    "sender": "news@example.com",
                    "handoff_path": "/unsubscribe-review?list_key=store",
                }
            ]
        )
        self.assertIn('class="email-card subscription-row"', queued_subscription)
        self.assertIn('<span class="pill">Queued</span>', queued_subscription)
        self.assertIn('class="action action--secondary"', queued_subscription)
        self.assertIn("Open focused review", queued_subscription)

    def test_extension_assets_have_valid_javascript_and_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent

        manifest_result = subprocess.run(
            [sys.executable, "-m", "json.tool", "extensions/gmail_companion/manifest.json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        content_result = subprocess.run(
            ["node", "--check", "extensions/gmail_companion/content.js"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        background_result = subprocess.run(
            ["node", "--check", "extensions/gmail_companion/background.js"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        analytics_result = subprocess.run(
            ["node", "tests/gmail_companion_analytics_test.js"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        self.assertEqual(content_result.returncode, 0, content_result.stderr)
        self.assertEqual(background_result.returncode, 0, background_result.stderr)
        self.assertEqual(analytics_result.returncode, 0, analytics_result.stderr)

    def test_extension_offers_apply_suggestion_for_unconfirmed_selected_email(self) -> None:
        content_js = (
            Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js"
        ).read_text()

        self.assertIn('selected.status === "write-unconfirmed"', content_js)
        self.assertIn('data-ea-action="accept-suggestion"', content_js)
        self.assertIn("Apply ${escapeHtml(label)}", content_js)
        self.assertIn("Finish Gmail update", content_js)
        self.assertIn('["needs-attention", "write-unconfirmed"].includes(selected?.status)', content_js)

    def test_extension_keeps_refreshing_until_selected_email_is_ready(self) -> None:
        content_js = (
            Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js"
        ).read_text()

        self.assertIn("function scheduleUnderstandingRefresh", content_js)
        self.assertIn("selectedUnderstandingActive(selected)", content_js)
        self.assertIn("UNDERSTANDING_REFRESH_INTERVAL_MS", content_js)

    def test_extension_uses_harness_state_and_clickable_summary_filters(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        background_js = (repo_root / "extensions" / "gmail_companion" / "background.js").read_text()
        content_js = (repo_root / "extensions" / "gmail_companion" / "content.js").read_text()
        manifest = json.loads((repo_root / "extensions" / "gmail_companion" / "manifest.json").read_text())

        self.assertIn("/api/harness-state", background_js)
        self.assertIn("/api/health", background_js)
        self.assertIn("Helper unreachable", background_js)
        self.assertIn("Wrong service on port", background_js)
        self.assertIn("HARNESS_STATE_TIMEOUT_MS", background_js)
        self.assertIn("/api/analytics/capture", background_js)
        self.assertIn("X-PostHog-Distinct-Id", background_js)
        self.assertIn("storage", manifest["permissions"])
        self.assertEqual(manifest["content_scripts"][0]["js"][0], "analytics.js")
        self.assertIn("data-ea-summary-filter", content_js)
        self.assertIn('previousPayload = "";', content_js)
        self.assertIn("refreshInFlight", content_js)
        self.assertIn("REFRESH_INTERVAL_MS = 5000", content_js)
        self.assertIn("Threadwise is connected but the inbox state is still loading.", content_js)
        self.assertIn("/api/founder-feedback", content_js)
        self.assertIn("data-ea-action=\"open-feedback\"", content_js)
        self.assertIn("overflow-y:auto", content_js)
        self.assertIn("flex:0 0 auto", content_js)
        self.assertIn("What should Threadwise do better here?", content_js)
        self.assertIn("ea-selected-email-secondary", content_js)
        self.assertIn("Open an email to inspect or teach Threadwise.", content_js)
        self.assertIn("Gmail label", content_js)
        self.assertIn("Human meaning", content_js)
        self.assertIn("Likely why", content_js)
        self.assertIn("likelyReasonForSelected", content_js)
        self.assertIn("humanMeaningForSelected", content_js)
        self.assertIn("renderChangedTodayGroups", content_js)
        self.assertIn("Future rule", content_js)
        self.assertIn("rule_type_label", content_js)
        self.assertIn("rule_confidence_label", content_js)
        self.assertIn("Structured rule", content_js)
        self.assertIn("Similar emails found", content_js)
        self.assertIn("Similar candidates:", content_js)
        self.assertIn("Exact sender matches:", content_js)
        self.assertIn("Broader rule candidate:", content_js)
        self.assertIn("Saved locally for review.", content_js)
        self.assertIn('let minimized = true;', content_js)
        self.assertIn('PANEL_WIDTH_MINIMIZED = "70px"', content_js)
        self.assertIn('id="ea-brand-toggle"', content_js)
        self.assertIn('addEventListener("click", handleBrandToggle)', content_js)
        self.assertIn("function handleBrandToggle", content_js)
        self.assertIn("selected_at: previous.selected_at || nextContext.selected_at", content_js)
        self.assertIn("function openThreadwiseHome", content_js)
        self.assertIn("let forcedHome = false", content_js)
        self.assertIn('return "home";', content_js)
        self.assertIn("Review next", content_js)
        self.assertNotIn("Review queue needs a refresh", content_js)
        self.assertIn("No emails need review", content_js)
        self.assertIn("Gmail sync completed. Threadwise handled everything automatically.", content_js)
        self.assertIn("function noteExplicitlyAssignsLabel", content_js)
        self.assertIn("function defaultManualRuleNote", content_js)
        self.assertIn("teachDraft.note = defaultManualRuleNote()", content_js)
        self.assertIn("data-ea-brand-img", content_js)
        self.assertIn('id="ea-editorial-utility-styles"', content_js)
        self.assertIn("#ea-panel [data-tw-primary-action]", content_js)
        self.assertIn(":focus-visible", content_js)
        self.assertIn('id="ea-header-tagline"', content_js)
        self.assertIn("founderFeedbackVisible = false", content_js)
        self.assertIn("setFounderFeedbackVisible", content_js)
        self.assertIn("!minimized && founderFeedbackVisible", content_js)
        self.assertIn("grid-template-columns: 36px minmax(0, 1fr) auto", content_js)
        self.assertIn('chrome.runtime.getURL("assets/brand/threadwise-app-icon.png")', content_js)
        self.assertIn("open Threadwise", content_js)
        self.assertIn("Check again", content_js)
        self.assertIn("Running Gmail sync...", content_js)
        background_js = (Path(__file__).parent.parent / "extensions/gmail_companion/background.js").read_text()
        self.assertIn("const GMAIL_CHECK_TIMEOUT_MS = 180000", background_js)
        self.assertIn("const GMAIL_MUTATION_TIMEOUT_MS = 180000", background_js)
        self.assertIn('path === "/api/gmail-check-run"', background_js)
        self.assertIn('path === "/api/teach-apply"', background_js)
        self.assertIn("return GMAIL_MUTATION_TIMEOUT_MS", background_js)
        self.assertIn("return HARNESS_STATE_TIMEOUT_MS", background_js)
        self.assertIn("timeoutMs: apiTimeoutMs(message.path)", background_js)
        self.assertIn("data-ea-action=\"force-refresh\"", content_js)
        self.assertIn("friendlyErrorMessage", content_js)
        self.assertIn("Reading this email...", content_js)
        self.assertIn("Understanding this email...", content_js)
        self.assertIn("Threadwise is still understanding this email. Teaching controls will appear when the email is ready.", content_js)
        self.assertIn('id="ea-status"', content_js)
        self.assertIn("Needs attention", content_js)
        self.assertIn("Health check failed", content_js)
        self.assertIn("Wrong service on port", content_js)
        self.assertIn("Reconnect Threadwise before teaching corrections.", content_js)
        self.assertIn("Threadwise has not synced this email yet.", content_js)
        self.assertIn("Threadwise can explain emails it has already synced.", content_js)
        self.assertIn("Run Gmail sync now", content_js)
        self.assertIn("/api/gmail-check-run", content_js)
        self.assertIn("Connection details", content_js)
        self.assertNotIn("This email is not in the current local sync.", content_js)
        self.assertIn("Current Queue", content_js)
        self.assertIn("Previous interpretation", content_js)
        self.assertIn("data-ea-previous-preview", content_js)
        self.assertIn("Review unsubscribe candidates", content_js)
        self.assertIn("select-unsubscribe", content_js)
        self.assertIn("Report details", content_js)
        self.assertIn("What Changed Today", content_js)
        self.assertIn("Decision source", content_js)
        self.assertIn("All labels:", content_js)
        self.assertNotIn("Live Gmail sidebar mode is using the same stored inbox snapshot and queue buckets as the local harness.", content_js)

        self.assertIn("data-ea-summary-item", content_js)
        self.assertIn("data-ea-action=\"open-selected-gmail\"", content_js)
        self.assertIn("Open this email in Gmail", content_js)
        self.assertIn("data-ea-open-changed-gmail", content_js)
        self.assertIn("Preview in Threadwise", content_js)
        self.assertIn("findChangedTodayItem", content_js)
        self.assertIn("openSelectedEmailInGmail", content_js)
        self.assertIn("window.location.href = gmailSearchUrl(item)", content_js)
        self.assertIn("const messageNode = subject ? selectedMessageNode() : null;", content_js)
        self.assertIn("box-sizing:border-box;width:100%", content_js)
        self.assertIn("teachErrorResult", content_js)
        self.assertIn("renderTeachResultHtml", content_js)
        self.assertIn("Preview blocked", content_js)
        self.assertIn("Lesson blocked", content_js)
        self.assertIn("Retry available", content_js)
        self.assertIn("Preview accepted", content_js)
        self.assertIn("Fix accepted", content_js)
        self.assertIn("Fix + future accepted", content_js)
        self.assertIn("Fix + inbox accepted", content_js)
        self.assertIn("Working", content_js)
        self.assertIn("Done", content_js)
        self.assertIn("Preparing rule...", content_js)
        self.assertIn("renderAsyncFollowUpHtml", content_js)
        self.assertIn("renderRecentActivityHtml", content_js)
        self.assertIn("recentActivityItems", content_js)
        self.assertIn("Recent activity", content_js)
        self.assertIn("data-ea-activity-item", content_js)
        self.assertIn("teach-apply-refresh", content_js)
        self.assertIn("Background refresh", content_js)
        self.assertIn("Nothing was stored or changed. The preview is still here", content_js)
        self.assertIn("Try fix again", content_js)
        self.assertIn("data-ea-action=\"retry-preview-teach\"", content_js)
        self.assertIn("max-width:100%;overflow-wrap:anywhere;word-break:break-word", content_js)
        self.assertIn("Nothing was changed. Check the local companion connection and try Preview again.", content_js)
        self.assertNotIn("No confirmed lesson was applied from this failed request", content_js)
        self.assertIn("isTeachPending()", content_js)
        self.assertIn('teachFlowState = "previewing"', content_js)
        self.assertIn('teachResult = teachPendingResult("preview")', content_js)
        self.assertIn('teachResult = teachPendingResult("apply", mode)', content_js)
        self.assertIn('activeTeachApplyMode = mode', content_js)
        self.assertIn('return "teach-result-receipt"', content_js)
        self.assertIn('data-ea-selected-state="teach-result-receipt"', content_js)
        self.assertIn("Updating this email and matching inbox emails…", content_js)
        self.assertIn("response.payload?.error", background_js)
        self.assertIn("status: response.status", background_js)
        self.assertIn("Queue preview", content_js)
        self.assertNotIn("Back to inbox email", content_js)
        self.assertIn("Close preview", content_js)
        self.assertIn("Choose label manually", content_js)
        self.assertIn("Infer from note", content_js)
        self.assertIn("What should Threadwise understand?", content_js)
        self.assertIn("gmailSearchUrl", content_js)
        self.assertIn("data-ea-open-gmail", content_js)
        self.assertIn("What to do now", content_js)
        self.assertIn("Viewing", content_js)
        self.assertIn("Closest synced emails", content_js)
        self.assertIn("kept visible", content_js)
        self.assertIn("selectedMessageNode", content_js)
        self.assertIn("Fix this email", content_js)
        self.assertIn("Affected existing emails", content_js)
        self.assertIn("Show affected emails", content_js)
        self.assertIn('PANEL_WIDTH_EXPANDED', content_js)
        self.assertIn('data-ea-action="open-affected-review"', content_js)
        self.assertIn('data-ea-affected-review="true"', content_js)
        self.assertIn("Reviewing affected emails", content_js)
        self.assertIn("data-ea-open-affected-gmail", content_js)
        self.assertIn("/api/teach-exclude", content_js)
        self.assertIn("data-ea-exclude-affected", content_js)
        self.assertIn("Exception saved", content_js)
        self.assertIn('data-ea-apply="apply-included"', content_js)
        self.assertIn("Apply to included", content_js)
        self.assertIn("/api/teach-amendment", content_js)
        self.assertIn("Possible rule amendment", content_js)
        self.assertIn("Accept amendment", content_js)
        self.assertIn("Teach future rule", content_js)
        self.assertIn('data-ea-apply="future-only"', content_js)
        self.assertNotIn('data-ea-apply="save-future-rule"', content_js)
        self.assertIn("Keep discussing", content_js)
        self.assertIn("Choose a label or describe the correction", content_js)
        self.assertIn("Threadwise currently applies one EA label at a time", content_js)
        self.assertIn("explicitMultiLabelRequest", content_js)
        self.assertIn("teachDraft.targetLabel = previewTargetLabel", content_js)
        self.assertIn("teachPreview?.target_label || teachPreview?.proposed_label", content_js)
        self.assertIn("manualPreviewOriginContext = lastLiveContext ? { ...lastLiveContext } : null", content_js)
        self.assertIn("releaseCompletedQueuePreviewOnGmailClick", content_js)
        self.assertIn("function asyncFollowUpIsWorking", content_js)
        self.assertIn("payload === previousPayload && !asyncFollowUpIsWorking()", content_js)
        self.assertIn("liveNeedsAttentionCount", content_js)
        self.assertIn('title: filter === "needs_attention_items" ? "Review queue complete"', content_js)
        self.assertNotIn('selectedDecisionConflict = "Choose a label before previewing the change."', content_js)
        self.assertIn("Fix this email only updates the message you are reviewing.", content_js)
        self.assertIn("Queue unsubscribe review", content_js)
        self.assertIn("Clear draft", content_js)
        self.assertIn("box-shadow:none", content_js)
        self.assertIn("Open queued review", content_js)
        self.assertIn('data-ea-unsubscribe-card="true"', content_js)
        self.assertIn('data-ea-unsubscribe-action="queue"', content_js)
        self.assertIn('data-ea-unsubscribe-action="review"', content_js)
        self.assertIn("const canOpenUnsubscribeUrl = unsubscribePreview", content_js)
        self.assertIn('unsubscribePreview.status !== "ready"', content_js)
        self.assertIn('unsubscribePreview.url.startsWith("mailto:")', content_js)
        self.assertIn("data-ea-changed-item", content_js)
        self.assertIn("Queued subscriptions", content_js)
        self.assertIn("Preview closest synced match", content_js)
        self.assertIn("data-ea-related-item", content_js)
        self.assertIn("open-needs-attention", content_js)
        self.assertIn("selectSummaryFilter", content_js)
        self.assertIn("setDraft", content_js)
        self.assertIn("forceRefresh", content_js)
        self.assertIn("Show technical details", content_js)
        self.assertIn("Technical details", content_js)
        self.assertIn("toggle-details", content_js)
        self.assertIn("Open daily dashboard", content_js)
        manifest = json.loads((repo_root / "extensions" / "gmail_companion" / "manifest.json").read_text())
        self.assertIn("web_accessible_resources", manifest)
        self.assertIn("assets/brand/threadwise-app-icon.png", manifest["web_accessible_resources"][0]["resources"])

    def test_empty_home_does_not_offer_repeated_sync_as_the_primary_action(self) -> None:
        content_js = (Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js").read_text()

        self.assertIn('needsReviewCount ? \'<button type="button" data-ea-action="open-needs-attention"', content_js)
        self.assertIn("No emails need review", content_js)
        self.assertNotIn('${gmailCheckPending ? "Running Gmail sync..." : "Run Gmail sync"}', content_js)

    def test_final_review_receipt_does_not_offer_a_nonexistent_next_email(self) -> None:
        content_js = (Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js").read_text()

        self.assertIn("function remainingNeedsAttentionItems", content_js)
        self.assertIn("remainingNeedsAttentionItems().length > 0", content_js)
        self.assertIn("Review queue complete", content_js)
        self.assertIn('data-ea-action="return-home-after-receipt"', content_js)

    def test_review_and_scope_screens_can_open_the_exact_gmail_message(self) -> None:
        content_js = (Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js").read_text()

        self.assertGreaterEqual(content_js.count('data-ea-action="open-selected-gmail"'), 4)
        self.assertIn('data-ea-action="open-selected-gmail" style="border:0;background:transparent', content_js)
        self.assertIn('return `https://mail.google.com/mail/u/0/#all/${encodeURIComponent(messageId)}`', content_js)
        self.assertIn("Opening the email preserves the current correction draft", content_js)

    def test_label_change_preview_uses_one_compact_three_scope_chooser(self) -> None:
        content_js = (Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js").read_text()

        self.assertIn('scopeCard("current-only", "Just this email"', content_js)
        self.assertIn('scopeCard("future-only", "This email + future emails"', content_js)
        self.assertIn('`Also update ${matchingCount} reviewed inbox email', content_js)
        self.assertIn('data-ea-action="confirm-selected-scope"', content_js)
        self.assertIn("Where should this change apply?", content_js)
        self.assertIn("How Threadwise understood this", content_js)
        self.assertIn("Matching evidence", content_js)
        self.assertIn('let selectedTeachScope = "current-only"', content_js)
        self.assertIn('return startTeachApply(selectedTeachScope)', content_js)
        self.assertIn('selectedTeachScope === "apply-included"', content_js)
        self.assertIn('requires_confirmation && !affectedReviewOpen', content_js)

    def test_extension_update_refreshes_open_gmail_tabs_once_so_stale_content_scripts_cannot_survive(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        manifest = json.loads((repo_root / "extensions" / "gmail_companion" / "manifest.json").read_text())
        background_js = (repo_root / "extensions" / "gmail_companion" / "background.js").read_text()

        self.assertEqual(manifest["version"], "0.2.0")
        self.assertIn("threadwise_active_extension_version", background_js)
        self.assertIn("chrome.runtime.getManifest().version", background_js)
        self.assertIn('chrome.tabs.query({ url: "https://mail.google.com/*" })', background_js)
        self.assertIn("chrome.tabs.reload(tab.id)", background_js)
        self.assertIn("await chrome.storage.local.set", background_js)

    def test_suspicious_preview_routes_to_the_dedicated_destructive_confirmation(self) -> None:
        content_js = (Path(__file__).parent.parent / "extensions" / "gmail_companion" / "content.js").read_text()
        preview_success = content_js.split("function previewTeach()", 1)[1].split(
            "function previewSafety", 1
        )[0]

        self.assertIn('previewTargetLabel === "suspicious"', preview_success)
        self.assertIn('previewSafety("sender")', preview_success)
        self.assertIn('data-ea-action="confirm-safety-action"', content_js)
        self.assertIn("Label, trash, and protect future mail", content_js)
        self.assertIn('path: "/api/safety-apply"', content_js)
        self.assertIn("confirmed: true", content_js)

    def test_companion_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/run_gmail_companion.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Serve the Gmail companion sidebar prototype", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_simulator_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/run_gmail_companion_simulator.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("safe local inbox simulator", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_simulator_launcher_disables_gmail_check_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            simulator_dir = root / "simulator"
            source_dir.mkdir()
            with patch(
                "scripts.run_gmail_companion_simulator.run_companion_main",
                return_value=0,
            ) as run_main:
                exit_code = run_simulator_main(
                    [
                        "--source-storage-dir",
                        str(source_dir),
                        "--simulator-storage-dir",
                        str(simulator_dir),
                    ]
                )

        self.assertEqual(exit_code, 0)
        companion_args = run_main.call_args.args[0]
        self.assertIn("--disable-gmail-write-through", companion_args)
        self.assertIn("--disable-gmail-check", companion_args)

    def test_main_prints_local_url(self) -> None:
        stdout = io.StringIO()
        fake_server = _FakeServer(server_port=45123)

        exit_code = main(
            ["--storage-dir", "/tmp/example"],
            stdout=stdout,
            server_factory=lambda host, port, storage_dir, gmail_write_through_enabled=True, gmail_check_enabled=True: fake_server,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(fake_server.served)
        self.assertTrue(fake_server.closed)
        self.assertIn("http://127.0.0.1:45123", stdout.getvalue())

    def test_panel_html_is_minimizable_and_contains_local_harness_controls(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        page = app.render_panel()

        self.assertIn("Minimize", page)
        self.assertIn("CLEAR THREADS. BETTER INBOX.", page)
        self.assertIn("Agent View", page)
        self.assertIn("Today", page)
        self.assertIn("Synced Inbox Fixtures", page)
        self.assertIn("Preview", page)
        self.assertIn("Clear draft", page)
        self.assertIn("action-button quiet", page)
        self.assertIn("Fix this email", page)
        self.assertIn("Affected existing emails", page)
        self.assertIn("Show affected emails", page)
        self.assertIn("expanded-review", page)
        self.assertIn("open-affected-review", page)
        self.assertIn("Reviewing affected emails", page)
        selected_renderer = page.split("function renderSelectedEmail", 1)[1].split(
            "function renderPreviousTeachPreview", 1
        )[0]
        self.assertEqual(selected_renderer.count("syncAffectedReviewLayout();"), 3)
        self.assertIn("data-affected-open-gmail", page)
        self.assertIn("data-affected-exclude", page)
        self.assertIn("/api/teach-exclude", page)
        self.assertIn("data-apply-mode=\"apply-included\"", page)
        self.assertIn("Apply to included", page)
        self.assertIn("/api/teach-amendment", page)
        self.assertIn("Possible rule amendment", page)
        self.assertIn("Previous interpretation", page)
        self.assertIn("data-previous-preview", page)
        self.assertIn("Review unsubscribe candidates", page)
        self.assertIn("Report details", page)
        self.assertIn("What Changed Today", page)
        self.assertIn("Correct / Teach", page)
        self.assertIn("Local harness mode is backed by real synced inbox artifacts", page)
        self.assertIn("Queued subscriptions", page)
        self.assertIn("Preview closest synced match", page)
        self.assertIn("Show details", page)
        self.assertIn("Open daily dashboard", page)
        self.assertIn("Nothing was stored or changed. The preview is still here", page)
        self.assertIn("Try fix again", page)
        self.assertIn("data-action=\"refresh-state\"", page)
        self.assertIn("overflow-wrap: anywhere", page)

    def test_simulator_page_contains_inbox_and_safe_local_only_language(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"), gmail_write_through_enabled=False)
        page = app.render_simulator()

        self.assertIn("Threadwise Inbox Simulator", page)
        self.assertIn("Simulated Inbox", page)
        self.assertIn("Load unsynced message", page)
        self.assertIn("Threadwise has not synced this email yet", page)
        self.assertIn("Pick a synced queue item below", page)
        self.assertIn("Return to fixture list", page)
        self.assertNotIn("/api/gmail-check-run", page)
        self.assertNotIn("Current category", page)
        self.assertNotIn("Handling status", page)
        self.assertNotIn("Short reason", page)
        self.assertIn("disables Gmail write-through", page)
        self.assertIn("Minimize", page)
        self.assertIn("Previous interpretation", page)
        self.assertIn("data-previous-preview", page)
        self.assertIn("Proposed rule:", page)
        self.assertIn("Looks right", page)
        self.assertIn("Choose how broadly to apply this rule.", page)
        self.assertIn("Propose rule", page)
        self.assertIn("data-apply-mode=\"apply-included\"", page)
        self.assertIn("future-only", page)
        self.assertIn("Fix + inbox", page)
        self.assertIn("Apply to inbox?", page)
        self.assertIn("What changed", page)
        self.assertIn("Subscription cleanup", page)
        self.assertNotIn("Report details", page)
        self.assertNotIn("What Changed Today", page)
        self.assertNotIn("Correct / Teach", page)
        self.assertIn("data-queue-message-id", page)
        self.assertNotIn("Current Queue", page)
        self.assertIn("What to do now", page)
        self.assertNotIn("Viewing", page)
        self.assertIn("Rule applied", page)
        self.assertIn("Try fix again", page)
        self.assertIn("data-action=\"refresh-state\"", page)
        self.assertIn("overflow-wrap:anywhere", page)
        self.assertIn("padding: clamp(8px, 3vw, 34px)", page)
        self.assertIn(".brand-kicker { display:none", page)
        self.assertIn('[data-tw-primary-action] { border:2px solid #241812;box-shadow:3px 3px 0 #241812; }', page)
        self.assertIn(":focus-visible", page)
        self.assertIn("@media (max-width: 480px)", page)
        self.assertIn('<div class="brand-kicker" aria-hidden="true">', page)

    def test_simulator_page_exposes_one_decision_copilot_workspace_contract(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"), gmail_write_through_enabled=False)

        page = app.render_simulator()

        self.assertIn('id="sim-workspace"', page)
        self.assertIn('data-ea-workspace-body="selected-email"', page)
        self.assertIn('data-ea-workspace-body="home"', page)
        self.assertIn('data-ea-selected-state="review"', page)
        self.assertIn('data-ea-selected-state="change"', page)
        self.assertIn('data-tw-primary-action', page)
        self.assertIn("Threadwise suggests", page)
        self.assertIn("Preview change", page)
        self.assertIn("let applyInFlight = false", page)
        self.assertIn("finally {", page)
        self.assertIn("Future rule saved for review", page)
        self.assertIn("Saved as a learning candidate. No Gmail messages were changed.", page)
        self.assertIn("Inbox removal needs attention. Open Activity for details.", page)
        self.assertIn('<option value="" selected disabled>Choose a label</option>', page)
        self.assertIn('data-ea-handled-kind="${escapeHtml(handledKind)}"', page)
        self.assertIn("Threadwise classified this email and kept it visible. Gmail label not confirmed.", page)
        self.assertIn('"Gmail label applied. Kept in Inbox."', page)
        self.assertIn('"Gmail label applied. Removed from Inbox."', page)
        self.assertNotIn('<div class="eyebrow">Agent View</div>', page)

    def test_unsubscribe_review_page_lists_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/unsub>",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Digest <digest@example.com>",
                        "subject": "Weekly digest",
                        "snippet": "News roundup",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["newsletter"],
                        "applied_labels": ["newsletter"],
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <news@example.com>"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    },
                    {
                        "id": "gmail-live-002",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Digest <digest@example.com>"},
                                {"name": "Precedence", "value": "bulk"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )

            page = GmailCompanionApp(storage_dir).render_unsubscribe_review_page()

            self.assertIn("Subscription cleanup", page)
            self.assertIn("Store", page)
            self.assertIn("Open provider page · does not execute here", page)
            self.assertIn("Manual follow-up", page)
            self.assertEqual(page.count("data-unsubscribe-safety-note"), 1)
            self.assertIn("Manual mail or provider links leave Threadwise and do not count as execution.", page)
            self.assertNotIn("Open unsubscribe link", page)
            self.assertIn("All candidates: 2", page)

    def test_unsubscribe_review_page_does_not_open_one_click_https_directly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/unsub>",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <news@example.com>"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                                {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )

            page = GmailCompanionApp(storage_dir).render_unsubscribe_review_page()

            self.assertIn("Ready now", page)
            self.assertEqual(page.count("data-unsubscribe-safety-note"), 1)
            self.assertIn("Ready one-click HTTPS actions require a separate explicit confirmation.", page)
            self.assertNotIn('href="https://example.com/unsub"', page)
            self.assertNotIn("Open provider page · does not execute here", page)
            self.assertNotIn("Open unsubscribe link", page)
            self.assertIn("data-unsubscribe-batch-bar hidden", page)

    def test_unsubscribe_review_groups_each_candidate_once_in_ready_queued_manual_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-ready",
                        "sender": "Ready Store <ready@example.com>",
                        "subject": "Ready sale",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/ready>",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-queued",
                        "sender": "Queued Store <queued@example.com>",
                        "subject": "Queued sale",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/queued>",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-manual",
                        "sender": "Manual Digest <manual@example.com>",
                        "subject": "Manual digest",
                        "review_state": "reviewed",
                        "final_labels": ["newsletter"],
                        "list_unsubscribe": "<mailto:leave@example.com>",
                    },
                ],
                raw_messages=[
                    {
                        "id": "gmail-ready",
                        "payload": {"headers": [
                            {"name": "From", "value": "Ready Store <ready@example.com>"},
                            {"name": "List-Unsubscribe", "value": "<https://example.com/ready>"},
                            {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
                        ]},
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    },
                    {
                        "id": "gmail-queued",
                        "payload": {"headers": [
                            {"name": "From", "value": "Queued Store <queued@example.com>"},
                            {"name": "List-Unsubscribe", "value": "<https://example.com/queued>"},
                            {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
                        ]},
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    },
                    {
                        "id": "gmail-manual",
                        "payload": {"headers": [
                            {"name": "From", "value": "Manual Digest <manual@example.com>"},
                            {"name": "List-Unsubscribe", "value": "<mailto:leave@example.com>"},
                        ]},
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    },
                ],
            )
            store = UnsubscribeInventoryStore(storage_dir)
            candidates = store.list_candidates()
            queued_key = next(item["list_key"] for item in candidates if item["display_name"] == "Queued Store")
            store.save_selection_states(
                [item["list_key"] for item in candidates],
                [queued_key],
            )

            page = GmailCompanionApp(storage_dir).render_unsubscribe_review_page()
            markers = [
                'data-unsubscribe-group="ready"',
                'data-unsubscribe-group="queued"',
                'data-unsubscribe-group="manual"',
            ]

            self.assertEqual([page.count(marker) for marker in markers], [1, 1, 1])
            self.assertEqual(
                [page.index(marker) for marker in markers],
                sorted(page.index(marker) for marker in markers),
            )
            self.assertEqual(page.count("data-unsubscribe-row"), 3)
            self.assertEqual(page.count("<h3>Ready Store</h3>"), 1)
            self.assertEqual(page.count("<h3>Queued Store</h3>"), 1)
            self.assertEqual(page.count("<h3>Manual Digest</h3>"), 1)
            self.assertIn("Ready now: 1", page)
            self.assertIn("Queued: 1", page)
            self.assertIn("Manual follow-up: 1", page)
            self.assertEqual(page.count('type="checkbox" data-unsubscribe-selection'), 3)
            self.assertEqual(page.count("<strong>Latest attempt</strong>"), 3)
            self.assertIn("one-click-post", page)
            self.assertIn("unsupported", page)
            self.assertIn('href="mailto:leave@example.com"', page)
            self.assertIn("Open mail app · does not execute here", page)
            queued_group = page.split(markers[1], 1)[1].split(markers[2], 1)[0]
            self.assertIn("Queued Store", queued_group)
            self.assertNotIn("Ready Store", queued_group)

    def test_unsubscribe_selection_endpoint_persists_only_selection_and_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-ready",
                        "sender": "Ready Store <ready@example.com>",
                        "subject": "Ready sale",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/ready>",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-ready",
                        "payload": {"headers": [
                            {"name": "From", "value": "Ready Store <ready@example.com>"},
                            {"name": "List-Unsubscribe", "value": "<https://example.com/ready>"},
                            {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
                        ]},
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )
            app = GmailCompanionApp(storage_dir)
            candidate_key = app._runtime_state.unsubscribe_candidates()[0]["list_key"]
            handler = _FakeRequestHandler(
                "/api/unsubscribe-candidates/selections",
                method="POST",
                json_body={
                    "candidate_keys": [candidate_key],
                    "selected_candidate_keys": [candidate_key],
                },
            )

            with (
                patch.object(
                    UnsubscribeExecutor,
                    "execute_selected_candidates",
                    side_effect=AssertionError("selection endpoint must not execute"),
                ) as execute,
                patch.object(
                    app._runtime_state,
                    "invalidate",
                    wraps=app._runtime_state.invalidate,
                ) as invalidate,
            ):
                app.handle_request(handler)

            response = json.loads(handler.wfile.value.decode("utf-8"))
            saved = UnsubscribeInventoryStore(storage_dir).list_candidates()
            self.assertEqual(handler.code, 200)
            self.assertEqual(response["candidate_count"], 1)
            self.assertEqual(response["selected_count"], 1)
            self.assertEqual(response["execution"], "none")
            self.assertEqual(response["gmail_mutation"], "none")
            self.assertIn("Nothing was unsubscribed", response["acknowledgment"])
            self.assertEqual(saved[0]["decision_state"], "selected")
            invalidate.assert_called_once_with()
            execute.assert_not_called()

    def test_unsubscribe_batch_bar_is_selection_only_and_mobile_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-ready",
                        "sender": "A Very Long Subscription Address <newsletter-and-updates@example.com>",
                        "subject": "Ready sale",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/ready>",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-ready",
                        "payload": {"headers": [
                            {"name": "From", "value": "A Very Long Subscription Address <newsletter-and-updates@example.com>"},
                            {"name": "List-Unsubscribe", "value": "<https://example.com/ready>"},
                            {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
                        ]},
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )
            store = UnsubscribeInventoryStore(storage_dir)
            candidate_key = store.list_candidates()[0]["list_key"]
            store.save_selection_states([candidate_key], [candidate_key])

            page = GmailCompanionApp(storage_dir).render_unsubscribe_review_page()

            self.assertIn("data-unsubscribe-batch-bar", page)
            self.assertNotIn("data-unsubscribe-batch-bar hidden", page)
            self.assertIn("Save selection", page)
            self.assertIn("Clear queued selections", page)
            self.assertIn("/api/unsubscribe-candidates/selections", page)
            self.assertIn("position:sticky", page)
            self.assertIn(".batch-bar[hidden] { display:none; }", page)
            self.assertIn("@media (max-width: 880px)", page)
            self.assertIn("overflow-wrap:anywhere", page)
            self.assertIn("let selectionSaveInFlight = false", page)
            self.assertIn("selectionSaveInFlight = true", page)
            self.assertIn("let reloadScheduled = false", page)
            self.assertIn("reloadScheduled = true", page)
            self.assertIn("if (!reloadScheduled)", page)
            self.assertIn("window.location.reload()", page)
            self.assertIn("finally", page)
            script = page.split("<script>", 1)[1].split("</script>", 1)[0]
            self.assertLess(script.index("reloadScheduled = true"), script.index("window.location.reload()"))
            conditional_unlock = script.split("if (!reloadScheduled)", 1)[1]
            self.assertIn("selectionSaveInFlight = false", conditional_unlock)
            self.assertIn("saveSelectionButton.disabled = false", conditional_unlock)
            self.assertIn("clearSelectionButton.disabled = false", conditional_unlock)
            self.assertNotIn("execute_selected_candidates", page)
            self.assertNotIn("/api/unsubscribe-executions", page)
            self.assertNotIn("Execute selected", page)
            self.assertNotIn("Unsubscribe now", page)

    def test_unsubscribe_selection_endpoint_rejects_non_list_and_non_subset_payloads(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        invalid_lists = _FakeRequestHandler(
            "/api/unsubscribe-candidates/selections",
            method="POST",
            json_body={"candidate_keys": "not-a-list", "selected_candidate_keys": []},
        )
        invalid_subset = _FakeRequestHandler(
            "/api/unsubscribe-candidates/selections",
            method="POST",
            json_body={"candidate_keys": [], "selected_candidate_keys": ["unknown"]},
        )

        app.handle_request(invalid_lists)
        app.handle_request(invalid_subset)

        list_error = json.loads(invalid_lists.wfile.value.decode("utf-8"))
        subset_error = json.loads(invalid_subset.wfile.value.decode("utf-8"))
        self.assertEqual(invalid_lists.code, 400)
        self.assertIn("must be lists", list_error["error"])
        self.assertEqual(invalid_subset.code, 400)
        self.assertIn("must be a subset", subset_error["error"])

    def test_daily_dashboard_page_has_four_default_sections_in_operational_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/unsub>",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Founder <person@example.com>",
                        "subject": "Planning for Finland 2027",
                        "snippet": "Trip planning",
                        "interpretation": "Personal planning email that should stay visible.",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["personal"],
                        "applied_labels": ["personal"],
                    },
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <news@example.com>"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    },
                    {
                        "id": "gmail-live-002",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Founder <person@example.com>"},
                            ]
                        },
                        "labelIds": ["INBOX"],
                    },
                ],
            )
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "founder-test-batch-1_daily_report.json").write_text(
                json.dumps(
                    {
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "batch_id": "founder-test-batch-1",
                        "report_date": "2026-06-29",
                        "processed_count": 2,
                        "inbox_removed_count": 1,
                        "unlabeled_count": 0,
                        "label_counts": {
                            "EA/Promotions": 1,
                            "EA/Personal": 1,
                        },
                    }
                )
            )
            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertIn("What Threadwise did today", page)
            section_markers = [
                'data-dashboard-section="needs-review"',
                'data-dashboard-section="activity"',
                'data-dashboard-section="subscriptions"',
                'data-dashboard-section="proton-review"',
            ]
            self.assertEqual([page.count(marker) for marker in section_markers], [1, 1, 1, 1])
            self.assertEqual(
                sorted(page.index(marker) for marker in section_markers),
                [page.index(marker) for marker in section_markers],
            )
            self.assertNotIn('data-dashboard-section="kept-visible"', page)
            self.assertNotIn('data-dashboard-section="auto-handled"', page)
            self.assertNotIn('data-dashboard-section="recent-queue"', page)
            self.assertEqual(page.count("<details data-dashboard-diagnostics"), 1)
            self.assertIn("Open unsubscribe review", page)
            self.assertIn("Open Proton review", page)
            self.assertIn("<main data-dashboard-shell>", page)
            self.assertEqual(page.count("data-dashboard-primary-action"), 3)
            self.assertIn(".action--primary", page)
            self.assertIn(":focus-visible", page)
            self.assertIn("padding:clamp(8px,3vw,28px)", page)
            self.assertIn("main > .card", page)

    def test_daily_dashboard_uses_live_inbox_reconciliation_for_review_count_and_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "still-in-inbox",
                        "sender": "Current <current@example.com>",
                        "subject": "Current review email",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "now-in-trash",
                        "sender": "Deleted <deleted@example.com>",
                        "subject": "Deleted review email",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )
            app = GmailCompanionApp(storage_dir, live_inbox_reconciliation_enabled=True)

            with patch.object(app._runtime_state, "_live_inbox_ids_loader", return_value={"still-in-inbox"}):
                page = app.render_daily_dashboard_page()

            needs_review = page.split('data-dashboard-section="needs-review"', 1)[1].split(
                'data-dashboard-section="activity"', 1
            )[0]
            self.assertIn("Current review email", needs_review)
            self.assertNotIn("Deleted review email", needs_review)
            self.assertIn("<strong>1</strong><span>need attention</span>", page)

    def test_daily_dashboard_page_renders_attention_now_and_possible_from_daily_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "thread_id": "thread-001",
                        "sender": "Airline <alerts@airline.example>",
                        "subject": "Flight check-in closes tonight",
                        "snippet": "Check in before 21:00.",
                        "interpretation": "Travel reminder.",
                        "review_state": "reviewed",
                        "final_labels": ["travel"],
                        "applied_labels": ["travel"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "thread_id": "thread-002",
                        "sender": "Recruiter <recruiter@example.com>",
                        "subject": "Choose an interview slot",
                        "snippet": "Please book a time next week.",
                        "interpretation": "Hiring workflow.",
                        "review_state": "reviewed",
                        "final_labels": ["job-related"],
                        "applied_labels": ["job-related"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-003",
                        "thread_id": "thread-003",
                        "sender": "Unknown <unknown@example.com>",
                        "subject": "Choose a label for this email",
                        "snippet": "Classification review fixture.",
                        "interpretation": "This email still needs a label decision.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )
            self._write_daily_report(
                storage_dir,
                "founder-test-batch-1",
                attention_items=[
                    {
                        "message_id": "gmail-live-001",
                        "thread_id": "thread-001",
                        "level": "needs_attention_now",
                        "category": "travel",
                        "reason": "Check-in closes tonight.",
                        "evidence": "Email says check-in closes at 21:00.",
                        "source": "compact_payload",
                        "handled_state": "appears_unhandled",
                        "feedback_state": "unset",
                        "gmail_mutation": "none",
                    },
                    {
                        "message_id": "gmail-live-002",
                        "thread_id": "thread-002",
                        "level": "possible_attention",
                        "category": "job_opportunity",
                        "reason": "Recruiter scheduling link may need action.",
                        "evidence": "Message asks the founder to book an interview slot.",
                        "source": "compact_payload",
                        "handled_state": "unknown",
                        "feedback_state": "unset",
                        "gmail_mutation": "none",
                    },
                ],
            )

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertIn("Needs Attention Now", page)
            self.assertIn("Possible Attention", page)
            self.assertIn("Flight check-in closes tonight", page)
            self.assertIn("Airline &lt;alerts@airline.example&gt;", page)
            self.assertIn("travel", page)
            self.assertIn("Check-in closes tonight.", page)
            self.assertIn("Email says check-in closes at 21:00.", page)
            self.assertIn("compact_payload | Gmail message gmail-live-001 | thread thread-001 | batch founder-test-batch-1", page)
            self.assertIn("Attention pass: no Gmail changes", page)
            self.assertIn("Choose an interview slot", page)
            self.assertIn("job_opportunity", page)
            needs_review = page.split('data-dashboard-section="needs-review"', 1)[1].split(
                'data-dashboard-section="activity"', 1
            )[0]
            self.assertIn("Classification review", needs_review)
            self.assertIn("Choose a label for this email", needs_review)
            self.assertLess(
                needs_review.index('data-dashboard-attention-lane="now"'),
                needs_review.index("Choose a label for this email"),
            )

    def test_daily_dashboard_deduplicates_review_items_and_keeps_rich_attention_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-duplicate",
                        "thread_id": "thread-duplicate",
                        "sender": "Airline <alerts@airline.example>",
                        "subject": "Check in before tonight",
                        "snippet": "Check in before 21:00.",
                        "interpretation": "This email still needs a classification decision.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_daily_report(
                storage_dir,
                "founder-test-batch-1",
                attention_items=[
                    {
                        "message_id": "gmail-live-duplicate",
                        "thread_id": "thread-duplicate",
                        "level": "needs_attention_now",
                        "category": "travel",
                        "reason": "Check-in closes tonight.",
                        "evidence": "The airline gives a 21:00 deadline.",
                        "source": "compact_payload",
                        "handled_state": "appears_unhandled",
                        "feedback_state": "unset",
                        "gmail_mutation": "none",
                    },
                    {
                        "message_id": "gmail-live-hidden",
                        "thread_id": "thread-hidden",
                        "level": "insufficient_context",
                        "category": "newsletter",
                        "reason": "The reading-list summary is too vague to evaluate.",
                        "evidence": "Only a generic newsletter snippet is available.",
                        "source": "compact_payload",
                        "gmail_mutation": "none",
                    },
                ],
            )

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()
            needs_review = page.split('data-dashboard-section="needs-review"', 1)[1].split(
                'data-dashboard-section="activity"', 1
            )[0]

            self.assertEqual(needs_review.count("<h3>Check in before tonight</h3>"), 1)
            self.assertIn("Check-in closes tonight.", needs_review)
            self.assertIn("The airline gives a 21:00 deadline.", needs_review)
            self.assertIn("Good catch", needs_review)
            self.assertIn("Not attention", needs_review)
            self.assertIn("Wrong reason", needs_review)
            self.assertIn("1 lower-risk insufficient-context item kept out of this daily attention view.", needs_review)

    def test_daily_dashboard_page_surfaces_only_high_consequence_insufficient_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "thread_id": "thread-001",
                        "sender": "Bank <security@bank.example>",
                        "subject": "Confirm account activity",
                        "snippet": "We noticed a sign-in.",
                        "interpretation": "Account security notice.",
                        "review_state": "reviewed",
                        "final_labels": ["account-security"],
                        "applied_labels": ["account-security"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "thread_id": "thread-002",
                        "sender": "News <news@example.com>",
                        "subject": "Weekly reading list",
                        "snippet": "Links for later.",
                        "interpretation": "Newsletter.",
                        "review_state": "reviewed",
                        "final_labels": ["newsletter"],
                        "applied_labels": ["newsletter"],
                    },
                ],
            )
            self._write_daily_report(
                storage_dir,
                "founder-test-batch-1",
                attention_items=[
                    {
                        "message_id": "gmail-live-001",
                        "thread_id": "thread-001",
                        "level": "insufficient_context",
                        "category": "security",
                        "reason": "Could be account-risk mail, but compact context is not enough.",
                        "evidence": "Mentions new sign-in and account activity.",
                        "source": "compact_payload",
                        "gmail_mutation": "none",
                    },
                    {
                        "message_id": "gmail-live-002",
                        "thread_id": "thread-002",
                        "level": "insufficient_context",
                        "category": "",
                        "reason": "Not enough context to classify the reading list.",
                        "evidence": "Newsletter snippet is vague.",
                        "source": "compact_payload",
                        "gmail_mutation": "none",
                    },
                ],
            )

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()
            attention_section = page.split('data-dashboard-section="needs-review"', 1)[1].split(
                'data-dashboard-section="activity"', 1
            )[0]

            self.assertIn("Confirm account activity", attention_section)
            self.assertIn("Insufficient context, high-consequence cue", attention_section)
            self.assertIn("Could be account-risk mail, but compact context is not enough.", attention_section)
            self.assertIn("1 lower-risk insufficient-context item kept out of this daily attention view.", attention_section)
            self.assertNotIn(
                'class="email-card attention-card"><h3>Weekly reading list',
                attention_section,
            )
            self.assertIn("Weekly reading list", attention_section)
            self.assertIn("Gmail update needs confirmation", attention_section)
            self.assertIn("Possible Attention", attention_section)
            self.assertNotIn("Needs Attention Now", attention_section)
            self.assertNotIn("No attention-now items in the latest Gmail daily report.", attention_section)
            self.assertNotIn("Now: 0", attention_section)

    def test_daily_dashboard_page_has_useful_empty_attention_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_daily_report(storage_dir, "founder-test-batch-1", attention_items=[])

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertEqual(page.count('data-dashboard-attention-status="clear"'), 1)
            self.assertIn("Latest attention pass found no attention-now or possible-attention items.", page)
            self.assertNotIn("Needs Attention Now", page)
            self.assertNotIn("Possible Attention", page)
            self.assertNotIn("No attention-now items in the latest Gmail daily report.", page)
            self.assertNotIn("No possible-attention items in the latest Gmail daily report.", page)
            self.assertIn("Latest attention report: 2026-07-01", page)
            self.assertIn("Evaluated: 2", page)
            self.assertNotIn("Now: 0", page)
            self.assertNotIn("Possible: 0", page)

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-classification",
                        "sender": "Sender <sender@example.com>",
                        "subject": "Choose a classification",
                        "snippet": "Classification review fixture",
                        "interpretation": "The email still needs a label decision.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "founder-test-batch-2_daily_report.json").write_text(
                json.dumps(
                    {
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "batch_id": "founder-test-batch-2",
                        "report_date": "2026-07-02",
                        "processed_count": 1,
                    }
                )
            )

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()
            needs_review = page.split('data-dashboard-section="needs-review"', 1)[1].split(
                'data-dashboard-section="activity"', 1
            )[0]

            self.assertEqual(needs_review.count('data-dashboard-attention-status="unavailable"'), 1)
            self.assertIn("Classification review", needs_review)
            self.assertIn("Needs a label decision", needs_review)
            self.assertIn("Choose a classification", needs_review)
            self.assertLess(
                needs_review.index("Choose a classification"),
                needs_review.index('data-dashboard-attention-status="unavailable"'),
            )
            self.assertNotIn("Needs Attention Now", needs_review)
            self.assertNotIn("Possible Attention", needs_review)
            self.assertNotIn("Evaluated:", needs_review)

    def test_daily_dashboard_exposes_confirmed_run_gmail_check_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()
            hero = page.split('<section class="hero">', 1)[1].split("</section>", 1)[0]

            self.assertIn("Run Gmail check", hero)
            self.assertIn("confirm-run-gmail-check", hero)
            self.assertIn("may apply existing safe EA/ labels", hero)
            self.assertIn("remove INBOX only for approved low-value categories", hero)
            self.assertIn("may call the LLM for attention detection", hero)

    def test_daily_dashboard_omits_gmail_check_form_when_disabled(self) -> None:
        page = GmailCompanionApp(
            Path("/tmp/example"),
            gmail_check_enabled=False,
        ).render_daily_dashboard_page()

        self.assertIn("Gmail check is disabled for this server.", page)
        self.assertNotIn('action="/api/gmail-check-run"', page)
        self.assertNotIn('id="confirm-run-gmail-check"', page)

    def test_dashboard_gmail_check_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            app = GmailCompanionApp(storage_dir, gmail_run_runner=lambda _payload: None)

            with self.assertRaises(ValueError):
                app.trigger_gmail_check({"account_id": "founder-test"})

    def test_disabled_gmail_check_fails_closed_without_calling_supplied_runner(self) -> None:
        calls = []
        app = GmailCompanionApp(
            Path("/tmp/example"),
            gmail_check_enabled=False,
            gmail_run_runner=lambda payload: calls.append(payload),
        )

        with self.assertRaisesRegex(ValueError, "Gmail checks are disabled"):
            app.trigger_gmail_check({"confirmed": "true", "account_id": "founder-test"})

        self.assertEqual(calls, [])

    def test_dashboard_gmail_check_blocks_duplicate_active_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            write_gmail_dashboard_run_status(
                storage_dir,
                {"status": "running", "run_id": "existing-run", "started_at": "2026-07-01T10:00:00Z"},
            )
            app = GmailCompanionApp(storage_dir, gmail_run_runner=lambda _payload: None)

            with self.assertRaises(ValueError):
                app.trigger_gmail_check({"confirmed": "true", "account_id": "founder-test"})

            self.assertEqual(load_gmail_dashboard_run_status(storage_dir)["run_id"], "existing-run")

    def test_dashboard_gmail_check_persists_success_status_with_safe_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            calls = []

            def runner(payload: dict):
                calls.append(payload)
                return SimpleNamespace(
                    batch_id="founder-test-batch-2",
                    fetched_count=3,
                    label_write_count=2,
                    inbox_removal_count=1,
                    unlabeled_exceptions=[],
                )

            result = GmailCompanionApp(storage_dir, gmail_run_runner=runner).trigger_gmail_check(
                {"confirmed": "true", "account_id": "founder-test", "batch_size": "7"}
            )
            saved = load_gmail_dashboard_run_status(storage_dir)

            self.assertEqual(calls[0]["account_id"], "founder-test")
            self.assertEqual(calls[0]["batch_size"], 7)
            self.assertEqual(calls[0]["safety_boundaries"]["label_writes"], "existing_safe_ea_labels_only")
            self.assertEqual(calls[0]["safety_boundaries"]["attention_gmail_mutation"], "none")
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(saved["status"], "succeeded")
            self.assertEqual(saved["result"]["batch_id"], "founder-test-batch-2")

    def test_dashboard_gmail_check_persists_failure_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)

            def runner(_payload: dict):
                raise RuntimeError("gmail unavailable")

            with self.assertRaises(RuntimeError):
                GmailCompanionApp(storage_dir, gmail_run_runner=runner).trigger_gmail_check(
                    {"confirmed": "true", "account_id": "founder-test"}
                )
            saved = load_gmail_dashboard_run_status(storage_dir)

            self.assertEqual(saved["status"], "failed")
            self.assertIn("gmail unavailable", saved["error"])

    def test_gmail_check_endpoint_and_sidebar_expose_run_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            app = GmailCompanionApp(storage_dir, gmail_run_runner=lambda _payload: None)
            handler = _FakeRequestHandler(
                "/api/gmail-check-run",
                method="POST",
                json_body={"confirmed": "true", "account_id": "founder-test"},
            )

            app.handle_request(handler)
            payload = json.loads(handler.wfile.value.decode("utf-8"))
            sidebar = app.sidebar_state({})

            self.assertEqual(handler.code, 200)
            self.assertEqual(payload["status"], "succeeded")
            self.assertEqual(sidebar["run_status"]["status"], "succeeded")
            self.assertEqual(sidebar["run_status"]["dashboard_path"], "/daily-dashboard#run-gmail-check")

    def test_attention_rule_proposal_endpoints_preview_and_approve_without_gmail_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            app = GmailCompanionApp(storage_dir)
            app.attention_feedback(
                {
                    "action": "mark_needs_attention",
                    "message_id": "gmail-live-002",
                    "thread_id": "thread-002",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Choose an interview slot",
                    "sender": "Recruiter <recruiter@example.com>",
                    "note": "Recruiter scheduling emails should stay visible.",
                    "corrected_category": "job_opportunity",
                }
            )
            preview_handler = _FakeRequestHandler(
                "/api/attention-rule-proposal/preview",
                method="POST",
                json_body={"message_id": "gmail-live-002"},
            )

            app.handle_request(preview_handler)
            preview = json.loads(preview_handler.wfile.value.decode("utf-8"))
            proposal_id = preview["proposal"]["id"]
            review_handler = _FakeRequestHandler(
                "/api/attention-rule-proposal/review",
                method="POST",
                json_body={
                    "decision": "approve",
                    "proposal_id": proposal_id,
                    "application_mode": "future_only",
                },
            )
            app.handle_request(review_handler)
            reviewed = json.loads(review_handler.wfile.value.decode("utf-8"))

            self.assertEqual(preview_handler.code, 200)
            self.assertEqual(preview["gmail_mutation"], "none")
            self.assertEqual(preview["proposal"]["rule_type"], "attention_promotion")
            self.assertNotIn("label", preview["proposal"])
            self.assertEqual(review_handler.code, 200)
            self.assertEqual(reviewed["proposal"]["status"], "approved")
            self.assertEqual(reviewed["gmail_mutation"], "none")
            self.assertTrue(attention_rules_path(storage_dir).exists())

    def test_attention_rule_proposal_endpoint_can_reject(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            app = GmailCompanionApp(storage_dir)
            app.attention_feedback(
                {
                    "action": "mark_needs_attention",
                    "message_id": "gmail-live-002",
                    "thread_id": "thread-002",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Choose an interview slot",
                    "sender": "Recruiter <recruiter@example.com>",
                    "note": "Recruiter scheduling emails should stay visible.",
                    "corrected_category": "job_opportunity",
                }
            )
            proposal = app.preview_attention_rule_proposal({"message_id": "gmail-live-002"})["proposal"]
            handler = _FakeRequestHandler(
                "/api/attention-rule-proposal/review",
                method="POST",
                json_body={"decision": "reject", "proposal_id": proposal["id"], "notes": "Too broad."},
            )

            app.handle_request(handler)
            reviewed = json.loads(handler.wfile.value.decode("utf-8"))

            self.assertEqual(handler.code, 200)
            self.assertEqual(reviewed["proposal"]["status"], "rejected")
            self.assertEqual(reviewed["proposal"]["review_notes"], "Too broad.")
            self.assertFalse(attention_rules_path(storage_dir).exists())

    def test_attention_feedback_good_catch_persists_and_reflects_in_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)

            result = GmailCompanionApp(storage_dir).attention_feedback(
                {
                    "action": "good_catch",
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Flight check-in closes tonight",
                    "sender": "Airline <alerts@airline.example>",
                    "note": "Good catch for a same-day travel reminder.",
                }
            )
            saved = load_attention_feedback(storage_dir)
            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertIn("Recorded attention feedback.", result["acknowledgment"])
            self.assertEqual(saved["entries"]["gmail-live-001"]["latest_action"], "good_catch")
            self.assertFalse(saved["entries"]["gmail-live-001"]["creates_broader_rule"])
            self.assertIn("Feedback: good_catch", page)
            self.assertIn("Good catch for a same-day travel reminder.", page)

    def test_attention_feedback_not_attention_hides_item_from_attention_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)

            GmailCompanionApp(storage_dir).attention_feedback(
                {
                    "action": "not_attention",
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Flight check-in closes tonight",
                    "sender": "Airline <alerts@airline.example>",
                    "note": "This was already handled elsewhere.",
                }
            )
            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()
            attention_section = page.split('data-dashboard-section="needs-review"', 1)[1].split(
                'data-dashboard-section="activity"', 1
            )[0]

            self.assertNotIn(
                'class="email-card attention-card"><h3>Flight check-in closes tonight',
                attention_section,
            )
            self.assertIn("Flight check-in closes tonight", attention_section)
            self.assertIn("Gmail update needs confirmation", attention_section)
            self.assertIn('data-dashboard-attention-status="clear"', attention_section)
            self.assertIn("Latest attention pass found no attention-now or possible-attention items.", attention_section)

    def test_attention_feedback_wrong_reason_captures_correction_without_gmail_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)

            result = GmailCompanionApp(storage_dir).attention_feedback(
                {
                    "action": "wrong_reason",
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Flight check-in closes tonight",
                    "sender": "Airline <alerts@airline.example>",
                    "corrected_reason": "This matters because check-in closes today, not because of general travel.",
                    "corrected_category": "travel",
                }
            )
            saved = load_attention_feedback(storage_dir)
            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertEqual(result["gmail_mutation"], "none")
            self.assertEqual(saved["entries"]["gmail-live-001"]["corrected_reason"], "This matters because check-in closes today, not because of general travel.")
            self.assertIn("Feedback: wrong_reason", page)
            self.assertIn("<strong>Corrected:</strong> travel", page)
            self.assertIn("This matters because check-in closes today, not because of general travel.", page)

    def test_attention_feedback_can_mark_non_surfaced_email_as_needs_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)

            result = GmailCompanionApp(storage_dir).attention_feedback(
                {
                    "action": "mark_needs_attention",
                    "message_id": "gmail-live-002",
                    "thread_id": "thread-002",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Choose an interview slot",
                    "sender": "Recruiter <recruiter@example.com>",
                    "note": "Recruiter scheduling emails should be visible until I book.",
                    "corrected_category": "job_opportunity",
                }
            )
            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertEqual(result["feedback"]["latest_action"], "mark_needs_attention")
            self.assertIn("Choose an interview slot", page)
            self.assertIn("founder_marked", page)
            self.assertIn("Recruiter scheduling emails should be visible until I book.", page)

    def test_attention_feedback_endpoint_accepts_json_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            app = GmailCompanionApp(storage_dir)
            handler = _FakeRequestHandler(
                "/api/attention-feedback",
                method="POST",
                json_body={
                    "action": "good_catch",
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Flight check-in closes tonight",
                    "sender": "Airline <alerts@airline.example>",
                },
            )

            app.handle_request(handler)
            payload = json.loads(handler.wfile.value.decode("utf-8"))

            self.assertEqual(handler.code, 200)
            self.assertEqual(payload["feedback"]["latest_action"], "good_catch")
            self.assertEqual(payload["gmail_mutation"], "none")

    def test_attention_feedback_endpoint_accepts_dashboard_form_post(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_attention_fixture(storage_dir)
            app = GmailCompanionApp(storage_dir)
            handler = _FakeRequestHandler(
                "/api/attention-feedback",
                method="POST",
                form_body={
                    "action": "wrong_reason",
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "batch_id": "founder-test-batch-1",
                    "subject": "Flight check-in closes tonight",
                    "sender": "Airline <alerts@airline.example>",
                    "corrected_reason": "The concrete deadline is the important part.",
                    "corrected_category": "travel",
                },
            )

            app.handle_request(handler)
            payload = json.loads(handler.wfile.value.decode("utf-8"))

            self.assertEqual(handler.code, 200)
            self.assertEqual(payload["feedback"]["latest_action"], "wrong_reason")
            self.assertEqual(payload["feedback"]["corrected_reason"], "The concrete deadline is the important part.")

    def test_founder_feedback_endpoint_persists_note_with_minimal_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            app = GmailCompanionApp(storage_dir)
            handler = _FakeRequestHandler(
                "/api/founder-feedback",
                method="POST",
                json_body={
                    "source": "gmail_companion_extension",
                    "note": "The attention badge should be more visible here.",
                    "context": {
                        "surface": "gmail_companion_extension",
                        "page_url": "https://mail.google.com/mail/u/0/#inbox",
                        "connection_kind": "ready",
                        "active_summary_filter": "needs_attention_items",
                        "selected_context": {
                            "provider": "gmail",
                            "message_id": "msg-urgent-1",
                            "thread_id": "thread-urgent-1",
                            "subject": "Flight tomorrow",
                            "sender": "Airline <alerts@example.com>",
                        },
                        "selected_email": {
                            "found": True,
                            "status": "needs-attention",
                            "status_label": "Needs attention",
                            "classification": "EA/Travel",
                            "unsubscribe_available": False,
                            "body": "Do not persist full email body.",
                        },
                    },
                },
            )

            app.handle_request(handler)
            payload = json.loads(handler.wfile.value.decode("utf-8"))
            saved = load_founder_feedback(storage_dir)

            self.assertEqual(handler.code, 200)
            self.assertEqual(payload["acknowledgment"], "Saved feedback locally for later product review.")
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["note"], "The attention badge should be more visible here.")
            self.assertEqual(saved[0]["surface"], "gmail_companion_extension")
            self.assertEqual(saved[0]["selected_context"]["message_id"], "msg-urgent-1")
            self.assertEqual(saved[0]["selected_email"]["status"], "needs-attention")
            self.assertNotIn("body", saved[0]["selected_email"])

    def test_unsubscribe_review_page_can_focus_candidate_opened_from_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/unsub>",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <news@example.com>"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )

            page = GmailCompanionApp(storage_dir).render_unsubscribe_review_page(
                {"list_key": ["gmail:founder-test:news@example.com"]}
            )

            self.assertIn("Opened from inbox", page)
            self.assertIn("focused", page)

    def test_sidebar_state_returns_selected_email_and_daily_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                        "list_unsubscribe": "<https://example.com/unsub>",
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <news@example.com>"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )
            (storage_dir / "founder-test-batch-1_write_status.json").write_text(
                json.dumps({"gmail-live-001": "applied"}, indent=2)
            )
            (storage_dir / "founder-test-batch-1_inbox_removal_status.json").write_text(
                json.dumps({"gmail-live-001": "applied"}, indent=2)
            )
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "founder-test-batch-1_daily_report.json").write_text(
                json.dumps(
                    {
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "batch_id": "founder-test-batch-1",
                        "report_date": "2026-06-29",
                        "processed_count": 6,
                        "inbox_removed_count": 2,
                        "unlabeled_count": 1,
                        "label_counts": {
                            "EA/Promotions": 3,
                            "EA/Orders": 2,
                            "EA/Personal": 1,
                        },
                    },
                    indent=2,
                )
            )

            app = GmailCompanionApp(storage_dir)
            state = app.sidebar_state(
                {
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "subject": "Big sale this week",
                    "sender": "news@example.com",
                    "selected_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
            )

            self.assertEqual(state["contract_version"], "gmail-companion-sidebar-v1")
            self.assertTrue(state["selected_email"]["found"])
            self.assertEqual(state["selected_email"]["classification"], "EA/Promotions")
            self.assertEqual(state["selected_email"]["status"], "auto-handled")
            self.assertEqual(state["selected_email"]["status_label"], "Auto-handled")
            self.assertEqual(state["selected_email"]["reason"], "Promotional mail from a recurring sender.")
            self.assertTrue(state["selected_email"]["unsubscribe_available"])
            self.assertEqual(state["selected_email"]["unsubscribe"]["display_name"], "Store")
            self.assertIn("list_key=gmail%3Afounder-test%3Anews%40example.com", state["selected_email"]["unsubscribe"]["handoff_path"])
            self.assertEqual(state["selected_email"]["details"]["write_status"], "applied")
            self.assertEqual(state["selected_email"]["details"]["inbox_status"], "applied")
            self.assertIn(state["selected_email"]["understanding_state"], {"reading", "understanding"})
            self.assertEqual(state["daily_summary"]["processed_count"], 6)
            self.assertEqual(state["daily_summary"]["auto_handled_count"], 2)
            self.assertEqual(state["daily_summary"]["needs_attention_count"], 1)
            self.assertEqual(state["daily_summary"]["top_labels"][0]["label"], "EA/Promotions")
            self.assertEqual(state["daily_summary"]["run_count"], 1)
            self.assertEqual(state["daily_summary"]["report_date"], "2026-06-29")
            self.assertEqual(state["daily_summary"]["changed_today"]["label_writes_count"], 0)
            self.assertEqual(state["daily_summary"]["changed_today"]["inbox_removed_count"], 1)

    def test_harness_state_preserves_empty_context_for_home_and_exposes_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Friend <friend@example.com>",
                        "subject": "Trip planning",
                        "snippet": "Need your input",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                        "near_misses": ["job-related", "promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                ],
            )
            (storage_dir / "founder-test-batch-1_write_status.json").write_text(
                json.dumps({"gmail-live-002": "applied"}, indent=2)
            )

            state = GmailCompanionApp(storage_dir).harness_state({})

            self.assertEqual(state["selected_context"], {})
            self.assertFalse(state["sidebar_state"]["selected_email"]["found"])
            self.assertEqual(state["sidebar_state"]["selected_email"]["status"], "idle")
            self.assertEqual(len(state["needs_attention_items"]), 1)
            self.assertEqual(len(state["recent_items"]), 2)
            self.assertEqual(state["auto_handled_items"], [])
            self.assertEqual(len(state["kept_visible_items"]), 1)

    def test_harness_queue_includes_failed_gmail_write_with_confirmation_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    }
                ],
            )
            (storage_dir / "founder-test-batch-1_write_status.json").write_text(
                json.dumps({"gmail-live-001": "failed"}, indent=2)
            )

            state = GmailCompanionApp(storage_dir).harness_state({})

            self.assertEqual(len(state["needs_attention_items"]), 1)
            self.assertEqual(state["needs_attention_items"][0]["status"], "write-unconfirmed")
            self.assertEqual(
                state["needs_attention_items"][0]["action_reason"],
                "Finish Gmail update",
            )
            self.assertEqual(state["kept_visible_items"], [])

    def test_selected_reviewed_email_without_visible_or_recorded_label_write_needs_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    }
                ],
            )

            selected = GmailCompanionApp(storage_dir).sidebar_state(
                {
                    "provider": "gmail",
                    "message_id": "gmail-live-001",
                    "subject": "Big sale this week",
                    "sender": "news@example.com",
                    "gmail_labels": "Inbox",
                }
            )["selected_email"]

            self.assertEqual(selected["status"], "write-unconfirmed")
            self.assertEqual(selected["status_label"], "Gmail update needs confirmation")

    def test_harness_queue_finds_unconfirmed_email_beyond_recent_activity_batches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            for batch_number in range(1, 7):
                item = {
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": f"gmail-live-00{batch_number}",
                    "sender": "Store <news@example.com>",
                    "subject": f"Message {batch_number}",
                    "review_state": "reviewed",
                    "review_action": "approve",
                    "final_labels": ["promotions"],
                    "applied_labels": ["promotions"],
                }
                self._write_batch(
                    storage_dir,
                    f"founder-test-batch-{batch_number}",
                    items=[item],
                )
                if batch_number > 1:
                    (storage_dir / f"founder-test-batch-{batch_number}_write_status.json").write_text(
                        json.dumps({item["message_id"]: "applied"}, indent=2)
                    )

            state = GmailCompanionApp(storage_dir).harness_state({})

            self.assertEqual(
                [item["message_id"] for item in state["needs_attention_items"]],
                ["gmail-live-001"],
            )
            self.assertEqual(state["needs_attention_items"][0]["status"], "write-unconfirmed")

    def test_harness_queue_count_tracks_live_actionable_backlog_not_report_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "message_id": "still-needs-review",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                    {
                        "message_id": "already-taught",
                        "review_state": "reviewed",
                        "review_action": "sidebar-current-only",
                        "final_labels": ["personal"],
                        "applied_labels": ["personal"],
                    },
                ],
            )
            (storage_dir / "founder-test-batch-1_write_status.json").write_text(
                json.dumps({"already-taught": "applied"}, indent=2)
            )
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "founder-test-batch-1_daily_report.json").write_text(
                json.dumps(
                    {
                        "provider": "gmail",
                        "account_id": "founder-test",
                        "batch_id": "founder-test-batch-1",
                        "report_date": "2026-07-13",
                        "processed_count": 12,
                        "inbox_removed_count": 0,
                        "unlabeled_count": 12,
                        "label_counts": {},
                    },
                    indent=2,
                )
            )

            state = GmailCompanionApp(storage_dir).harness_state({})

            self.assertEqual([item["message_id"] for item in state["needs_attention_items"]], ["still-needs-review"])
            self.assertEqual(state["sidebar_state"]["daily_summary"]["needs_attention_count"], 1)

    def test_harness_state_orders_numbered_batches_naturally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-9",
                items=[
                    {
                        "message_id": "older-reviewed",
                        "review_state": "reviewed",
                        "final_labels": ["personal"],
                        "applied_labels": ["personal"],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-10",
                items=[
                    {
                        "message_id": "newer-needs-review",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            state = GmailCompanionApp(storage_dir).harness_state({})

            self.assertEqual(state["recent_items"][0]["message_id"], "newer-needs-review")
            self.assertEqual(state["needs_attention_items"][0]["message_id"], "newer-needs-review")
            self.assertEqual(state["sidebar_state"]["daily_summary"]["batch_id"], "founder-test-batch-10")

    def test_sidebar_state_has_safe_empty_selected_email_when_message_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            app = GmailCompanionApp(storage_dir)

            state = app.sidebar_state(
                {
                    "provider": "gmail",
                    "message_id": "missing-id",
                    "subject": "Unknown",
                    "sender": "nobody@example.com",
                }
            )

            self.assertFalse(state["selected_email"]["found"])
            self.assertEqual(state["selected_email"]["status"], "not-in-snapshot")
            self.assertEqual(state["daily_summary"]["processed_count"], 0)
            self.assertTrue(state["ui_state"]["can_minimize"])

    def test_sidebar_state_explains_when_selected_email_is_not_in_local_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            app = GmailCompanionApp(storage_dir)

            state = app.sidebar_state(
                {
                    "provider": "gmail",
                    "message_id": "gmail-live-999",
                    "subject": "Fresh message",
                    "sender": "person@example.com",
                }
            )

            self.assertFalse(state["selected_email"]["found"])
            self.assertEqual(state["selected_email"]["status"], "not-in-snapshot")
            self.assertIn("Run a fresh Gmail sync", state["selected_email"]["reason"])

    def test_sidebar_state_prefers_visible_gmail_ea_label_over_stale_local_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[{
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": "gmail-live-001",
                    "sender": "Sun Life <sunlife@info.sunlife.ca>",
                    "subject": "Your statement is ready",
                    "review_state": "pending",
                    "final_labels": [],
                    "applied_labels": [],
                }],
            )

            selected = GmailCompanionApp(storage_dir).sidebar_state({
                "provider": "gmail",
                "message_id": "gmail-live-001",
                "subject": "Your statement is ready",
                "sender": "sunlife@info.sunlife.ca",
                "gmail_labels": "EA/Finance",
            })["selected_email"]

            self.assertEqual(selected["internal_label"], "financial-account")
            self.assertEqual(selected["classification"], "EA/Finance")
            self.assertEqual(selected["status"], "kept-visible")

    def test_sidebar_state_uses_latest_mutation_receipt_for_visible_gmail_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[{
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": "privacy-update",
                    "sender": "OpenAI <noreply@email.openai.com>",
                    "subject": "Updates to OpenAI's Privacy Policy",
                    "review_state": "reviewed",
                    "final_labels": ["spam-low-value"],
                    "applied_labels": ["spam-low-value"],
                }],
            )
            (storage_dir / "gmail-companion-backfill-test_write_status.json").write_text(
                json.dumps({"privacy-update": "applied"})
            )
            (storage_dir / "gmail-companion-backfill-test_inbox_removal_status.json").write_text(
                json.dumps({"privacy-update": "applied"})
            )

            selected = GmailCompanionApp(storage_dir).sidebar_state({
                "provider": "gmail",
                "message_id": "privacy-update",
                "subject": "Updates to OpenAI's Privacy Policy",
                "sender": "noreply@email.openai.com",
                "gmail_labels": "EA/LowValue",
            })["selected_email"]

            self.assertEqual(selected["classification"], "EA/LowValue")
            self.assertEqual(selected["status"], "auto-handled")
            self.assertEqual(selected["details"]["inbox_status"], "applied")

    def test_daily_summary_rolls_up_recent_gmail_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            reports_dir = storage_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            reports = [
                {
                    "provider": "gmail",
                    "account_id": "founder-test",
                    "batch_id": "founder-test-batch-1",
                    "report_date": "2026-06-27",
                    "processed_count": 6,
                    "inbox_removed_count": 2,
                    "unlabeled_count": 1,
                    "label_counts": {"EA/Promotions": 3, "EA/Orders": 2},
                },
                {
                    "provider": "gmail",
                    "account_id": "founder-test",
                    "batch_id": "founder-test-batch-2",
                    "report_date": "2026-06-28",
                    "processed_count": 4,
                    "inbox_removed_count": 1,
                    "unlabeled_count": 2,
                    "label_counts": {"EA/LowValue": 2, "EA/Promotions": 1},
                },
                {
                    "provider": "protonmail",
                    "account_id": "founder-proton",
                    "batch_id": "founder-proton-batch-1",
                    "report_date": "2026-06-28",
                    "processed_count": 99,
                    "inbox_removed_count": 0,
                    "unlabeled_count": 99,
                    "label_counts": {"EA/Other": 99},
                },
            ]
            for report in reports:
                (reports_dir / f"{report['batch_id']}_daily_report.json").write_text(json.dumps(report, indent=2))

            summary = GmailCompanionApp(storage_dir).sidebar_state({})["daily_summary"]

            self.assertEqual(summary["source_label"], "last 2 Gmail runs")
            self.assertEqual(summary["processed_count"], 10)
            self.assertEqual(summary["auto_handled_count"], 3)
            self.assertEqual(summary["needs_attention_count"], 3)
            self.assertEqual(summary["run_count"], 2)
            self.assertEqual(summary["report_date"], "2026-06-28")
            self.assertEqual(summary["top_labels"][0]["label"], "EA/Promotions")

    def test_teach_preview_reports_existing_match_impact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "LinkedIn <messages-noreply@linkedin.com>",
                        "subject": "Sophie Riding sent you a message",
                        "snippet": "Let's catch up",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "LinkedIn <messages-noreply@linkedin.com>",
                        "subject": "Sean commented on a post",
                        "snippet": "New activity",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = GmailCompanionApp(storage_dir, gmail_write_through_enabled=False).teach_preview(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Sophie Riding sent you a message",
                        "sender": "messages-noreply@linkedin.com",
                    },
                    "target_label": "personal",
                    "note": "All future emails from this sender should be personal.",
                }
            )

            self.assertIn("I can relabel this email to EA/Personal.", preview["acknowledgment"])
            self.assertEqual(preview["impact"]["matching_existing_count"], 1)
            self.assertEqual(preview["selected_label_after"], ["personal"])
            self.assertEqual(preview["current_label_name"], "Uncategorized")
            self.assertEqual(preview["target_label_name"], "EA/Personal")
            self.assertIn("Treat future messages from messages-noreply@linkedin.com as EA/Personal.", preview["plain_english_rule"])
            self.assertEqual(preview["rule_type"], "sender")
            self.assertEqual(preview["rule_type_label"], "Sender rule")
            self.assertEqual(preview["structured_rule"]["to_label"], "EA/Personal")
            self.assertEqual(preview["structured_rule"]["applies_to_existing_count"], 1)
            self.assertEqual(preview["impact"]["matching_existing_examples"][0]["labels_after"], ["personal"])

    def test_domain_wide_low_value_instruction_matches_all_existing_domain_messages(self) -> None:
        class LiveDomainClient(MockGmailLabelClient):
            def search_message_ids(self, query: str, max_results: int) -> list[str]:
                self.calls.append(("search_message_ids", query, max_results))
                return ["bad-axe-current", "bad-axe-same-address", "bad-axe-other-address"]

            def get_message(self, message_id: str) -> dict:
                senders = {
                    "bad-axe-same-address": "Martyna <badaxe@badaxe.pl>",
                    "bad-axe-other-address": "Bookings <bookings@badaxe.pl>",
                }
                return {
                    "id": message_id,
                    "threadId": f"thread-{message_id}",
                    "internalDate": "1718784000000",
                    "snippet": "Unsolicited deposit request.",
                    "labelIds": ["Label_14"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": senders[message_id]},
                            {"name": "Subject", "value": "BAD AXE deposit reminder"},
                        ]
                    },
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "bad-axe-current",
                        "sender": "Piotr <badaxe@badaxe.pl>",
                        "subject": "Wizyta BAD AXE",
                        "body": "Unsolicited reservation requiring a deposit.",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "bad-axe-same-address",
                        "sender": "Martyna <badaxe@badaxe.pl>",
                        "subject": "BAD AXE - przypomnienie o zadatku",
                        "body": "A second unsolicited request for the same deposit.",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "bad-axe-other-address",
                        "sender": "Bookings <bookings@badaxe.pl>",
                        "subject": "Another payment request",
                        "body": "Different wording from another address at the same domain.",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "unrelated-domain",
                        "sender": "Bookings <bookings@example.com>",
                        "subject": "Another payment request",
                        "body": "Similar wording, but a different domain.",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "bad-axe-deleted",
                        "sender": "Old record <old@badaxe.pl>",
                        "subject": "Deleted from Gmail",
                        "body": "This historical record no longer exists in the mailbox.",
                        "review_state": "reviewed",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                ],
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=None):
                preview = GmailCompanionApp(
                    storage_dir,
                    gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: LiveDomainClient(),
                ).teach_preview(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "bad-axe-current"},
                        "target_label": "spam-low-value",
                        "note": "All emails from this domain are phishing and should be lowvalue.",
                    }
                )

            self.assertEqual(preview["semantic_rule"]["scope"], "sender-domain")
            self.assertEqual(preview["semantic_rule"]["sender_domain"], "badaxe.pl")
            self.assertEqual(preview["rule_type"], "sender-domain")
            self.assertEqual(
                {item["message_id"] for item in preview["impact"]["matching_existing_items"]},
                {"bad-axe-same-address", "bad-axe-other-address"},
            )

            self.assertEqual(preview["inbox_backfill"]["query"], "from:badaxe.pl")

    def test_all_messages_from_exact_sender_is_not_narrowed_by_llm_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "contact-1",
                        "sender": "Mary <mary@example.com>",
                        "subject": "Hello",
                        "body": "A personal note.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            fake_intent = {
                "target_label": "personal",
                "semantic_pattern": "personal conversation and informal updates",
                "cross_sender": False,
                "confidence": "high",
            }
            with patch("src.teaching_loop.interpret_teaching_intent", return_value=fake_intent):
                preview = GmailCompanionApp(storage_dir, gmail_write_through_enabled=False).teach_preview(
                    {
                        "selected_context": {"provider": "gmail", "message_id": "contact-1"},
                        "target_label": "personal",
                        "note": "All future emails from this exact sender are personal.",
                    }
                )

            self.assertEqual(preview["rule_type"], "sender")
            self.assertEqual(preview["semantic_rule"]["semantic_pattern"], "")
            self.assertEqual(preview["plain_english_rule"], "Treat future messages from mary@example.com as EA/Personal.")

    def test_unsubscribe_select_current_queues_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "auto-approve",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Store <news@example.com>"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                                {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
                            ]
                        },
                        "labelIds": ["CATEGORY_PROMOTIONS"],
                    }
                ],
            )

            result = GmailCompanionApp(storage_dir).unsubscribe_select_current(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Big sale this week",
                        "sender": "news@example.com",
                    }
                }
            )

            saved = json.loads((storage_dir / "unsubscribe_selections.json").read_text())
            candidate = next(iter(saved["candidates"].values()))
            self.assertEqual(candidate["decision_state"], "selected")
            self.assertIn("Queued Store for unsubscribe review.", result["acknowledgment"])
            self.assertIn("Nothing has been unsubscribed yet.", result["acknowledgment"])

    def test_daily_summary_reports_changed_today_counts_and_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <news@example.com>",
                        "subject": "Big sale this week",
                        "snippet": "Save 20% today",
                        "interpretation": "Promotional mail from a recurring sender.",
                        "review_state": "reviewed",
                        "review_action": "sidebar-current-only",
                        "final_labels": ["promotions"],
                        "applied_labels": ["promotions"],
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Shop <shop@example.com>",
                        "subject": "Shipping update",
                        "snippet": "Out for delivery",
                        "interpretation": "Shipping confirmation for a recent online purchase.",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["shopping-order"],
                        "applied_labels": ["shopping-order"],
                    },
                ],
            )
            (storage_dir / "founder-test-batch-1_write_status.json").write_text(
                json.dumps({"gmail-live-001": "applied"}, indent=2)
            )
            (storage_dir / "founder-test-batch-1_inbox_removal_status.json").write_text(
                json.dumps({"gmail-live-002": "applied"}, indent=2)
            )
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:news@example.com": {
                                "decision_state": "selected"
                            }
                        }
                    },
                    indent=2,
                )
            )
            CandidateChangeStore(candidate_changes_path(storage_dir)).save_candidate(
                CandidateChange(
                    id="candidate-future-rule-001",
                    kind="future-rule",
                    source="sidebar-teach",
                    title="Teach vendor digest as newsletter",
                    description="Future rule candidate from inbox teaching.",
                    affected_scope_summary="vendor digest family",
                    latest_recommendation="Review",
                    status="recommended-review",
                )
            )
            CandidateChangeStore(candidate_changes_path(storage_dir)).save_candidate(
                CandidateChange(
                    id="candidate-future-rule-002",
                    kind="future-rule",
                    source="sidebar-teach",
                    title="Teach another sender family",
                    description="Promoted future rule.",
                    affected_scope_summary="sender family",
                    latest_recommendation="Promote",
                    status="promoted",
                )
            )

            summary = GmailCompanionApp(storage_dir).sidebar_state({})["daily_summary"]["changed_today"]

            self.assertEqual(summary["label_writes_count"], 1)
            self.assertEqual(summary["inbox_removed_count"], 1)
            self.assertEqual(summary["selected_unsubscribe_count"], 1)
            self.assertEqual(summary["candidate_pending_count"], 1)
            self.assertEqual(summary["candidate_promoted_count"], 1)
            self.assertEqual(len(summary["items"]), 2)
            self.assertEqual(summary["items"][0]["change_group"], "Labels written")
            self.assertEqual(summary["items"][1]["change_group"], "Removed from inbox")
            self.assertEqual(summary["groups"][0]["label"], "Labels written")
            self.assertEqual(summary["groups"][1]["label"], "Removed from inbox")
            self.assertEqual(summary["selected_unsubscribe_examples"][0]["display_name"], "Store")
            self.assertEqual(summary["candidate_examples"][0]["title"], "Teach another sender family")
            self.assertIn("list_key=gmail%3Afounder-test%3Anews%40example.com", summary["selected_unsubscribe_examples"][0]["handoff_path"])

    def test_teach_apply_matching_existing_relabels_current_without_saving_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient()
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Application portal reminder",
                        "snippet": "Reminder",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Interview update",
                        "sender": "notifications@ashbyhq.com",
                    },
                    "target_label": "job-related",
                    "note": "Ashby interview workflow messages should be job-related and kept visible.",
                    "mode": "matching-existing",
                }
            )

            batch_one = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            batch_two = json.loads((storage_dir / "batches" / "founder-test-batch-2.json").read_text())

            self.assertIn("rewrote 1 matching stored emails", result["acknowledgment"])
            self.assertIn("did not save a future rule", result["acknowledgment"])
            self.assertEqual(result["matched_existing_count"], 1)
            self.assertEqual(batch_one["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(batch_two["items"][0]["final_labels"], ["job-related"])
            self.assertFalse((storage_dir / "teachable_classification_rules.json").exists())
            self.assertIn(("replace_threadwise_labels", "gmail-live-001", [gmail_client.labels["EA/Work"]], "EA/"), gmail_client.calls)
            self.assertIn(("replace_threadwise_labels", "gmail-live-002", [gmail_client.labels["EA/Work"]], "EA/"), gmail_client.calls)
            self.assertEqual(result["gmail_write_through"]["messages_written"], 2)

    def test_teach_exclude_saves_exception_and_refreshes_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-002",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Application portal reminder",
                        "snippet": "Reminder",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(storage_dir).teach_exclude(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Interview update",
                        "sender": "notifications@ashbyhq.com",
                    },
                    "target_label": "job-related",
                    "note": "Ashby interview workflow messages should be job-related and kept visible.",
                    "excluded_message_id": "gmail-live-002",
                    "reason": "",
                }
            )

            saved = json.loads((storage_dir / "teaching_exclusions.json").read_text())
            self.assertIn("Exception saved", result["acknowledgment"])
            self.assertEqual(saved["exclusions"][0]["message_id"], "gmail-live-002")
            self.assertEqual(result["preview"]["impact"]["matching_existing_count"], 0)

    def test_teach_amendment_accepts_proposed_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "Informational message with no confident category.",
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
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    },
                ],
            )
            app = GmailCompanionApp(storage_dir)
            exclusion = app.teach_exclude(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Interview update",
                        "sender": "notifications@ashbyhq.com",
                    },
                    "target_label": "job-related",
                    "note": "Ashby interview workflow messages should be job-related and kept visible.",
                    "excluded_message_id": "gmail-live-002",
                    "reason": "This one is a marketing newsletter, not an interview or recruiter message.",
                }
            )
            result = app.teach_amendment(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Interview update",
                        "sender": "notifications@ashbyhq.com",
                    },
                    "target_label": "job-related",
                    "note": "Ashby interview workflow messages should be job-related and kept visible.",
                    "amendment": exclusion["amendment_proposal"],
                    "decision": "accept",
                }
            )

            self.assertEqual(result["amendment_status"], "accepted")
            self.assertIn("Updated the proposed rule boundary", result["acknowledgment"])
            self.assertIn("except", result["preview"]["plain_english_rule"])
            self.assertEqual(result["preview"]["impact"]["matching_existing_count"], 0)

    def test_teach_apply_save_future_rule_only_does_not_write_gmail_or_relabel_existing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient()
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            app = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            )
            with patch.object(app._runtime_state, "start_teaching_refresh"):
                result = app.teach_apply(
                    {
                        "selected_context": {
                            "provider": "gmail",
                            "message_id": "gmail-live-001",
                            "subject": "Interview update",
                            "sender": "notifications@ashbyhq.com",
                        },
                        "target_label": "job-related",
                        "note": "Ashby interview workflow messages should be job-related and kept visible.",
                        "mode": "save-future-rule",
                    }
                )

            candidate_payload = json.loads((storage_dir / "candidate_changes.json").read_text())
            batch_one = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())

            self.assertIn("saved a future rule", result["acknowledgment"])
            self.assertEqual(candidate_payload["candidates"][0]["kind"], "future-rule")
            self.assertEqual(candidate_payload["candidates"][0]["metadata"]["rules"][0]["label"], "job-related")
            self.assertEqual(batch_one["items"][0]["final_labels"], [])
            self.assertEqual(gmail_client.calls, [])
            self.assertEqual(result["gmail_write_through"]["messages_written"], 0)
            self.assertEqual(result["gmail_write_through"]["mode"], "no-gmail-write-future-rule-only")
            self.assertEqual(
                result["outcome"],
                {
                    "state": "future-rule-saved",
                    "scope": "future-rule",
                    "current_email_changed_locally": False,
                    "current_email_written_to_gmail": False,
                    "matching_existing_changed_locally": 0,
                    "future_rule_saved": True,
                    "gmail_write_mode": "no-gmail-write-future-rule-only",
                    "gmail_label_write_failed": 0,
                },
            )

    def test_teach_apply_current_only_writes_current_message_to_gmail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient()
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Boss <boss@example.com>",
                        "subject": "Need a response",
                        "snippet": "Please reply",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Need a response",
                        "sender": "boss@example.com",
                    },
                    "target_label": "reply-needed",
                    "note": "This needs a reply.",
                    "mode": "current-only",
                }
            )

            self.assertIn(("replace_threadwise_labels", "gmail-live-001", [gmail_client.labels["EA/NeedsAction"]], "EA/"), gmail_client.calls)
            self.assertEqual(result["gmail_write_through"]["messages_written"], 1)
            self.assertEqual(result["gmail_write_through"]["inbox_removed"], 0)
            self.assertEqual(
                result["outcome"],
                {
                    "state": "changed",
                    "scope": "current-email",
                    "current_email_changed_locally": True,
                    "current_email_written_to_gmail": True,
                    "matching_existing_changed_locally": 0,
                    "future_rule_saved": False,
                    "gmail_write_mode": "applied",
                    "gmail_label_write_failed": 0,
                },
            )
            self.assertIn("relabeled only this email", result["acknowledgment"])

    def test_teach_preview_reports_inbox_backfill_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient(
                search_results_by_query={
                    "from:notifications@ashbyhq.com {job jobs recruiter interview application}": [
                        f"remote-{index}" for index in range(205)
                    ]
                }
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            preview = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_preview(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Interview update",
                        "sender": "notifications@ashbyhq.com",
                    },
                    "target_label": "job-related",
                    "note": "Ashby interview workflow messages should be job-related and kept visible.",
                }
            )

            self.assertEqual(
                preview["inbox_backfill"],
                {
                    "available": False,
                    "estimated_count": 0,
                    "is_capped": False,
                    "requires_confirmation": False,
                    "query": "from:notifications@ashbyhq.com {subject:job subject:recruiter subject:interview subject:application subject:hiring}",
                    "matches": [],
                },
            )

    def test_teach_apply_apply_included_backfills_matching_inbox_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient(
                search_results_by_query={
                    "from:notifications@ashbyhq.com {job jobs recruiter interview application}": [
                        "gmail-live-001",
                        "gmail-remote-003",
                    ]
                }
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Ashby <notifications@ashbyhq.com>",
                        "subject": "Interview update",
                        "snippet": "Status changed",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Interview update",
                        "sender": "notifications@ashbyhq.com",
                    },
                    "target_label": "job-related",
                    "note": "Ashby interview workflow messages should be job-related and kept visible.",
                    "mode": "apply-included",
                    "included_message_ids": ["gmail-remote-003"],
                }
            )

            self.assertNotIn(("search_message_ids", "from:notifications@ashbyhq.com {job jobs recruiter interview application}", 1000), gmail_client.calls)
            self.assertIn(("replace_threadwise_labels", "gmail-remote-003", [gmail_client.labels["EA/Work"]], "EA/"), gmail_client.calls)
            self.assertEqual(result["gmail_write_through"]["remote_match_count"], 1)
            self.assertEqual(result["gmail_write_through"]["remote_applied_count"], 1)
            self.assertEqual(result["gmail_write_through"]["messages_written"], 2)
            remote_batch_id = result["gmail_write_through"]["remote_batch_id"]
            writer = MockGmailLabelWriter(
                gmail_client=gmail_client,
                storage_dir=storage_dir,
                label_name_resolver=lambda label: {"job-related": "EA/Work"}[label],
            )
            self.assertEqual(writer.get_write_status(remote_batch_id, "gmail-remote-003"), "applied")
            self.assertEqual(writer.get_inbox_removal_status(remote_batch_id, "gmail-remote-003"), "ineligible")
            self.assertEqual(
                writer.get_write_attempt_history(remote_batch_id, "gmail-remote-003"),
                [{"status": "applied", "final_labels": ["job-related"]}],
            )
            self.assertEqual(load_latest_batch(storage_dir)["batch_id"], "founder-test-batch-1")

    def test_teach_apply_remote_backfill_preserves_label_success_when_inbox_removal_fails(self) -> None:
        class InboxRemovalFailingClient(MockGmailLabelClient):
            def remove_inbox_label(self, message_id: str) -> None:
                self.calls.append(("remove_inbox_label", message_id))
                if message_id == "gmail-remote-003":
                    raise RuntimeError("Temporary INBOX removal failure")

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = InboxRemovalFailingClient(
                search_results_by_query={
                    "from:news@example.com {summer sale}": [
                        "gmail-live-001",
                        "gmail-remote-003",
                    ]
                }
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "News <news@example.com>",
                        "subject": "Summer sale",
                        "snippet": "Offers",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Summer sale",
                        "sender": "news@example.com",
                    },
                    "target_label": "promotions",
                    "note": "Marketing email that should be treated as a promotion.",
                    "mode": "apply-included",
                    "included_message_ids": ["gmail-remote-003"],
                }
            )

            summary = result["gmail_write_through"]
            writer = MockGmailLabelWriter(
                gmail_client=gmail_client,
                storage_dir=storage_dir,
                label_name_resolver=lambda label: {"promotions": "EA/Promotions"}[label],
            )
            self.assertEqual(summary["remote_applied_count"], 1)
            self.assertEqual(summary["remote_failed_count"], 0)
            self.assertEqual(summary["remote_inbox_failed_count"], 1)
            self.assertEqual(summary["label_write_failed"], 0)
            self.assertEqual(summary["inbox_remove_failed"], 1)
            self.assertEqual(writer.get_write_status(summary["remote_batch_id"], "gmail-remote-003"), "applied")
            self.assertEqual(writer.get_inbox_removal_status(summary["remote_batch_id"], "gmail-remote-003"), "failed")
            self.assertIn("Inbox removal: 1 applied, 1 failed", result["acknowledgment"])

    def test_teach_apply_remote_backfill_does_not_remove_inbox_after_label_failure(self) -> None:
        class RemoteLabelFailingClient(MockGmailLabelClient):
            def replace_threadwise_labels(
                self,
                message_id: str,
                label_ids: list[str],
                namespace_prefix: str = "EA/",
            ) -> None:
                if message_id == "gmail-remote-003":
                    self.calls.append(("replace_threadwise_labels", message_id, label_ids, namespace_prefix))
                    raise RuntimeError("Temporary label write failure")
                super().replace_threadwise_labels(message_id, label_ids, namespace_prefix)

        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = RemoteLabelFailingClient(
                search_results_by_query={
                    "from:news@example.com {summer sale}": [
                        "gmail-live-001",
                        "gmail-remote-003",
                    ]
                }
            )
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "News <news@example.com>",
                        "subject": "Summer sale",
                        "snippet": "Offers",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Summer sale",
                        "sender": "news@example.com",
                    },
                    "target_label": "promotions",
                    "note": "Marketing email that should be treated as a promotion.",
                    "mode": "apply-included",
                    "included_message_ids": ["gmail-remote-003"],
                }
            )

            summary = result["gmail_write_through"]
            writer = MockGmailLabelWriter(gmail_client, storage_dir)
            self.assertEqual(summary["remote_applied_count"], 0)
            self.assertEqual(summary["remote_failed_count"], 1)
            self.assertEqual(summary["remote_inbox_skipped_count"], 1)
            self.assertEqual(writer.get_write_status(summary["remote_batch_id"], "gmail-remote-003"), "failed")
            self.assertEqual(writer.get_inbox_removal_status(summary["remote_batch_id"], "gmail-remote-003"), "skipped")
            self.assertNotIn(("remove_inbox_label", "gmail-remote-003"), gmail_client.calls)

    def test_teach_apply_can_disable_gmail_write_through_for_simulator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient()
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Boss <boss@example.com>",
                        "subject": "Need a response",
                        "snippet": "Please reply",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
                gmail_write_through_enabled=False,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Need a response",
                        "sender": "boss@example.com",
                    },
                    "target_label": "reply-needed",
                    "note": "This needs a reply.",
                    "mode": "current-only",
                }
            )

            self.assertEqual(gmail_client.calls, [])
            self.assertEqual(result["gmail_write_through"]["mode"], "disabled")
            self.assertEqual(result["gmail_write_through"]["messages_written"], 0)

    def test_teach_apply_future_only_calls_out_no_existing_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            gmail_client = MockGmailLabelClient()
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Alerts <alerts@example.com>",
                        "subject": "System reminder",
                        "snippet": "Reminder",
                        "interpretation": "Informational message with no confident category.",
                        "review_state": "pending",
                        "final_labels": [],
                        "applied_labels": [],
                    }
                ],
            )

            result = GmailCompanionApp(
                storage_dir,
                gmail_client_factory=lambda account_id, credentials_dir, client_secret_path, required_scope: gmail_client,
            ).teach_apply(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "System reminder",
                        "sender": "alerts@example.com",
                    },
                    "target_label": "account-security",
                    "note": "Future alerts from this sender should be account-related.",
                    "mode": "future-only",
                }
            )

            batch = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            self.assertIn("saved a future rule", result["acknowledgment"])
            self.assertIn("No other existing stored emails were rewritten", result["acknowledgment"])
            self.assertEqual(batch["items"][0]["final_labels"], ["account-security"])
            self.assertIn(
                (
                    "replace_threadwise_labels",
                    "gmail-live-001",
                    [gmail_client.labels["EA/Account"]],
                    "EA/",
                ),
                gmail_client.calls,
            )
            self.assertEqual(result["matched_existing_count"], 0)
            self.assertEqual(result["outcome"]["scope"], "current-email-and-future-rule")
            self.assertTrue(result["outcome"]["current_email_written_to_gmail"])
            self.assertTrue(result["outcome"]["future_rule_saved"])

    def test_teach_apply_returns_fast_sidebar_state_and_starts_follow_up_refresh(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        selected_context = {
            "provider": "gmail",
            "message_id": "gmail-live-001",
            "subject": "Need a response",
            "sender": "boss@example.com",
        }
        write_through = {
            "mode": "mock",
            "messages_written": 1,
            "label_write_failed": 0,
            "label_write_skipped": 0,
            "inbox_removed": 0,
            "inbox_remove_failed": 0,
        }
        workflow_result = TeachingWorkflowResult(
            response={
                "acknowledgment": "Lesson applied.",
                "mode": "current-only",
                "matched_existing_count": 0,
                "proposal": None,
                "gmail_write_through": write_through,
                "outcome": {"future_rule_saved": False},
            },
            selected_context=selected_context,
            write_summary=write_through,
        )
        fast_sidebar = {
            "selected_email": {"message_id": "gmail-live-001"},
            "daily_summary": {"processed_count": 12},
            "ui_state": {
                "async_follow_up": {
                    "kind": "teach-apply-refresh",
                    "state": "working",
                    "label": "Background refresh running",
                    "message": "Refreshing the queue summary and follow-up context in the background.",
                }
            },
        }

        with (
            patch.object(app._teaching_workflow, "apply", return_value=workflow_result),
            patch.object(app._runtime_state, "start_teaching_refresh") as start_follow_up_mock,
            patch.object(app._runtime_state, "sidebar", return_value=fast_sidebar) as fast_sidebar_mock,
        ):
            result = app.teach_apply(
                {
                    "selected_context": selected_context,
                    "target_label": "reply-needed",
                    "note": "This needs a reply.",
                    "mode": "current-only",
                }
            )

        start_follow_up_mock.assert_called_once_with(selected_context)
        fast_sidebar_mock.assert_called_once_with(selected_context)
        self.assertEqual(result["sidebar_state"]["ui_state"]["async_follow_up"]["state"], "working")
        self.assertEqual(result["acknowledgment"], "Lesson applied.")




    def test_install_page_is_extension_first_and_mentions_gmail_surface(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        page = app.render_install_page("127.0.0.1:8021")

        self.assertIn("Load unpacked", page)
        self.assertIn("brave://extensions", page)
        self.assertIn("The product itself lives in Gmail", page)
        self.assertNotIn("javascript:", page)
        self.assertNotIn("Copy launcher", page)

    def test_selected_email_contract_endpoint_shape_is_stable(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        status_code, payload = self._get_contract(app)

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["contract_version"], "gmail-companion-selected-email-v1")
        self.assertIn("message_id", payload["selected_context_fields"])
        self.assertIn("selected_email", payload["sidebar_state_fields"])

    def test_health_endpoint_reports_service_identity_and_stays_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Airline <alerts@airline.example>",
                        "subject": "Flight check-in closes tonight",
                        "snippet": "Check in before 21:00.",
                        "interpretation": "Travel reminder.",
                        "review_state": "reviewed",
                        "final_labels": ["travel"],
                        "applied_labels": ["travel"],
                    }
                ],
                raw_messages=[
                    {
                        "id": "gmail-live-001",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Airline <alerts@airline.example>"},
                            ]
                        },
                        "labelIds": ["INBOX"],
                    }
                ],
            )
            app = GmailCompanionApp(storage_dir)
            handler = _FakeRequestHandler("/api/health", method="GET")

            app.handle_request(handler)
            payload = json.loads(handler.wfile.value.decode("utf-8"))

            self.assertEqual(handler.code, 200)
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["service_id"], "threadwise-gmail-companion")
            self.assertEqual(payload["service_name"], "Threadwise Gmail Companion")
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["bound_origin"], "http://127.0.0.1:8021")
            self.assertEqual(payload["dashboard_path"], "/daily-dashboard#run-gmail-check")
            self.assertEqual(payload["health_path"], "/api/health")
            self.assertFalse(payload["analytics_enabled"])
            self.assertEqual(payload["storage_summary"]["storage_dir_name"], storage_dir.name)
            self.assertEqual(payload["storage_summary"]["batch_count"], 1)
            self.assertEqual(payload["storage_summary"]["report_count"], 0)
            self.assertNotIn("items", payload)
            self.assertNotIn("body", payload)
            self.assertNotIn("raw_messages", payload)
            self.assertNotIn("credentials", payload)
            self.assertNotIn("oauth", payload)
            self.assertNotIn("token", payload)

    def test_harness_state_reuses_short_lived_cache_for_same_context(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        context = {"provider": "gmail", "message_id": "cached-msg", "selected_at": "2026-07-10T10:00:00Z"}

        with patch("src.companion_runtime_state.build_companion_runtime_payload") as runtime_mock:
            runtime_mock.return_value = {"items": []}
            with patch("src.companion_runtime_state.selected_email_understanding_state") as understanding_mock:
                understanding_mock.side_effect = [
                    {
                        "understanding_state": "reading",
                        "understanding_label": "Reading",
                        "understanding_message": "Reading this email...",
                    },
                    {
                        "understanding_state": "ready",
                        "understanding_label": "Ready",
                        "understanding_message": "Threadwise is ready with the current email.",
                    },
                ]
                first = app.harness_state(context)
                second = app.harness_state(context)

        self.assertNotEqual(first["sidebar_state"]["selected_email"]["understanding_state"], second["sidebar_state"]["selected_email"]["understanding_state"])
        self.assertEqual(runtime_mock.call_count, 1)
        self.assertEqual(first["sidebar_state"]["selected_email"]["understanding_state"], "reading")
        self.assertEqual(second["sidebar_state"]["selected_email"]["understanding_state"], "ready")

    def test_harness_state_endpoint_includes_cors_headers(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        handler = _FakeRequestHandler("/api/harness-state", method="GET")

        app.handle_request(handler)

        self.assertEqual(handler.code, 200)
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(
            handler.sent_headers["Access-Control-Allow-Headers"],
            "Content-Type, X-PostHog-Distinct-Id",
        )
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Private-Network"], "true")

    def test_options_request_returns_cors_preflight_headers(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        handler = _FakeRequestHandler("/api/teach-apply", method="OPTIONS")

        app.handle_request(handler)

        self.assertEqual(handler.code, 204)
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(
            handler.sent_headers["Access-Control-Allow-Headers"],
            "Content-Type, X-PostHog-Distinct-Id",
        )
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Private-Network"], "true")
        self.assertEqual(handler.sent_headers["Content-Length"], "0")

    def _get_contract(self, app: GmailCompanionApp) -> tuple[int, dict]:
        class _HeaderOnlyHandler:
            path = "/api/selected-email-contract"
            command = "GET"
            headers = {}
            response = None

            def send_response(self, code):
                self.code = code

            def send_header(self, *_args):
                return

            def end_headers(self):
                return

            class _Writer:
                def write(self, value):
                    self.value = value

            wfile = _Writer()

        handler = _HeaderOnlyHandler()
        app.handle_request(handler)
        return handler.code, json.loads(handler.wfile.value.decode("utf-8"))

    def _write_batch(self, storage_dir: Path, batch_id: str, items: list[dict], raw_messages: list[dict] | None = None) -> None:
        batch_dir = storage_dir / "batches"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / f"{batch_id}.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "provider": "gmail",
                    "items": items,
                    "raw_messages": raw_messages or [],
                },
                indent=2,
            )
        )

    def _write_daily_report(self, storage_dir: Path, batch_id: str, attention_items: list[dict]) -> None:
        reports_dir = storage_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        grouped_counts = {
            "needs_attention_now": 0,
            "possible_attention": 0,
            "not_attention": 0,
            "insufficient_context": 0,
        }
        for item in attention_items:
            level = item.get("level")
            if level in grouped_counts:
                grouped_counts[level] += 1
        (reports_dir / f"{batch_id}_daily_report.json").write_text(
            json.dumps(
                {
                    "provider": "gmail",
                    "account_id": "founder-test",
                    "batch_id": batch_id,
                    "report_date": "2026-07-01",
                    "processed_count": 2,
                    "inbox_removed_count": 0,
                    "unlabeled_count": 0,
                    "label_counts": {},
                    "attention": {
                        "schema_version": 1,
                        "evaluated_message_count": 2,
                        "lookback_window": {
                            "latest_batch_id": batch_id,
                            "stored_lookback_batch_ids": [],
                            "max_evaluated_messages": 50,
                        },
                        "model": {"provider": "fake", "name": "fixture-attention-model"},
                        "usage": {"input_tokens": 100, "output_tokens": 20, "estimated_cost_usd": 0.001},
                        "grouped_counts": grouped_counts,
                        "items": attention_items,
                    },
                },
                indent=2,
            )
        )

    def _write_attention_fixture(self, storage_dir: Path) -> None:
        self._write_batch(
            storage_dir,
            "founder-test-batch-1",
            items=[
                {
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "sender": "Airline <alerts@airline.example>",
                    "subject": "Flight check-in closes tonight",
                    "snippet": "Check in before 21:00.",
                    "interpretation": "Travel reminder.",
                    "review_state": "reviewed",
                    "final_labels": ["travel"],
                    "applied_labels": ["travel"],
                },
                {
                    "source": "gmail",
                    "account_id": "founder-test",
                    "message_id": "gmail-live-002",
                    "thread_id": "thread-002",
                    "sender": "Recruiter <recruiter@example.com>",
                    "subject": "Choose an interview slot",
                    "snippet": "Please book a time next week.",
                    "interpretation": "Hiring workflow.",
                    "review_state": "reviewed",
                    "final_labels": ["job-related"],
                    "applied_labels": ["job-related"],
                },
            ],
        )
        self._write_daily_report(
            storage_dir,
            "founder-test-batch-1",
            attention_items=[
                {
                    "message_id": "gmail-live-001",
                    "thread_id": "thread-001",
                    "level": "needs_attention_now",
                    "category": "travel",
                    "reason": "Check-in closes tonight.",
                    "evidence": "Email says check-in closes at 21:00.",
                    "source": "compact_payload",
                    "handled_state": "appears_unhandled",
                    "feedback_state": "unset",
                    "gmail_mutation": "none",
                }
            ],
        )


class _FakeServer:
    def __init__(self, server_port: int) -> None:
        self.server_port = server_port
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True
        raise KeyboardInterrupt

    def server_close(self) -> None:
        self.closed = True


class _FakeRequestHandler:
    def __init__(
        self,
        path: str,
        *,
        method: str,
        json_body: dict | None = None,
        form_body: dict | None = None,
    ) -> None:
        self.path = path
        self.command = method
        if form_body is not None:
            from urllib.parse import urlencode

            body = urlencode(form_body).encode("utf-8")
            content_type = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(json_body).encode("utf-8") if json_body is not None else b""
            content_type = "application/json" if json_body is not None else ""
        self.headers = {"Content-Length": str(len(body)), "Content-Type": content_type} if body else {}
        self.server = SimpleNamespace(server_address=("127.0.0.1", 8021), server_port=8021)
        self.sent_headers: dict[str, str] = {}
        self.code = None
        self.rfile = io.BytesIO(body)
        self.wfile = self._Writer()

    def send_response(self, code):
        self.code = code

    def send_header(self, key, value):
        self.sent_headers[key] = value

    def end_headers(self):
        return

    class _Writer:
        def __init__(self) -> None:
            self.value = b""

        def write(self, value):
            self.value += value
