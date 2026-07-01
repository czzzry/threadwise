import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.attention_feedback import load_attention_feedback
from src.gmail_companion_rendering import (
    escape_html,
    render_dashboard_email_cards,
    server_origin,
    unsubscribe_section_key,
)
from src.gmail_companion_state import (
    build_selected_email_state,
    classify_handling_status,
    selected_context_from_query,
    selected_email_contract,
)
from src.gmail_companion_ui import GmailCompanionApp, main
from src.gmail_writer import MockGmailLabelClient


class GmailCompanionUiTests(unittest.TestCase):
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

    def test_companion_rendering_module_preserves_shared_helpers(self) -> None:
        self.assertEqual(escape_html('<a href="x">Tom & Jerry</a>'), "&lt;a href=&quot;x&quot;&gt;Tom &amp; Jerry&lt;/a&gt;")
        self.assertEqual(server_origin("127.0.0.1:8021"), "http://127.0.0.1:8021")
        self.assertEqual(server_origin("https://example.test"), "https://example.test")
        self.assertEqual(unsubscribe_section_key({"decision_state": "selected"}, {"status": "ready"}), "selected")
        self.assertIn(
            "No recent mail",
            render_dashboard_email_cards([], empty_label="No recent mail"),
        )

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

        self.assertEqual(manifest_result.returncode, 0, manifest_result.stderr)
        self.assertEqual(content_result.returncode, 0, content_result.stderr)
        self.assertEqual(background_result.returncode, 0, background_result.stderr)

    def test_extension_uses_harness_state_and_clickable_summary_filters(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        background_js = (repo_root / "extensions" / "gmail_companion" / "background.js").read_text()
        content_js = (repo_root / "extensions" / "gmail_companion" / "content.js").read_text()

        self.assertIn("/api/harness-state", background_js)
        self.assertIn("data-ea-summary-filter", content_js)
        self.assertIn("Current Queue", content_js)
        self.assertIn("Previous interpretation", content_js)
        self.assertIn("data-ea-previous-preview", content_js)
        self.assertIn("Review unsubscribe candidates", content_js)
        self.assertIn("select-unsubscribe", content_js)
        self.assertIn("What Changed Today", content_js)
        self.assertIn("Decision source", content_js)
        self.assertIn("Live Gmail sidebar mode is using the same stored inbox snapshot and queue buckets as the local harness.", content_js)
        self.assertIn("data-ea-summary-item", content_js)
        self.assertIn("Queue preview", content_js)
        self.assertIn("Back to inbox email", content_js)
        self.assertIn("What to do now", content_js)
        self.assertIn("Viewing", content_js)
        self.assertIn("Closest synced emails", content_js)
        self.assertIn("kept visible", content_js)
        self.assertIn("selectedMessageNode", content_js)
        self.assertIn("Apply only to this email", content_js)
        self.assertIn("Apply to current +", content_js)
        self.assertIn("Keep discussing", content_js)
        self.assertIn("changes the current message only", content_js)
        self.assertIn("Queue unsubscribe review", content_js)
        self.assertIn("Open queued review", content_js)
        self.assertIn("data-ea-changed-item", content_js)
        self.assertIn("Queued subscriptions", content_js)
        self.assertIn("Preview closest synced match", content_js)
        self.assertIn("data-ea-related-item", content_js)
        self.assertIn("open-needs-attention", content_js)
        self.assertIn("selectSummaryFilter", content_js)
        self.assertIn("setDraft", content_js)
        self.assertIn("forceRefresh", content_js)
        self.assertIn("Show details", content_js)
        self.assertIn("toggle-details", content_js)
        self.assertIn("Open daily dashboard", content_js)

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

    def test_main_prints_local_url(self) -> None:
        stdout = io.StringIO()
        fake_server = _FakeServer(server_port=45123)

        exit_code = main(
            ["--storage-dir", "/tmp/example"],
            stdout=stdout,
            server_factory=lambda host, port, storage_dir, gmail_write_through_enabled=True: fake_server,
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
        self.assertIn("Preview lesson", page)
        self.assertIn("Previous interpretation", page)
        self.assertIn("data-previous-preview", page)
        self.assertIn("Review unsubscribe candidates", page)
        self.assertIn("What Changed Today", page)
        self.assertIn("Correct / Teach", page)
        self.assertIn("Local harness mode is backed by real synced inbox artifacts", page)
        self.assertIn("Queued subscriptions", page)
        self.assertIn("Preview closest synced match", page)
        self.assertIn("Show details", page)
        self.assertIn("Open daily dashboard", page)

    def test_simulator_page_contains_inbox_and_safe_local_only_language(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"), gmail_write_through_enabled=False)
        page = app.render_simulator()

        self.assertIn("Threadwise Inbox Simulator", page)
        self.assertIn("Simulated Inbox", page)
        self.assertIn("Load unsynced message", page)
        self.assertIn("disables Gmail write-through", page)
        self.assertIn("Minimize", page)
        self.assertIn("Previous interpretation", page)
        self.assertIn("data-previous-preview", page)
        self.assertIn("Review unsubscribe candidates", page)
        self.assertIn("What Changed Today", page)
        self.assertIn("Correct / Teach", page)
        self.assertIn("data-queue-message-id", page)
        self.assertIn("Current Queue", page)
        self.assertIn("What to do now", page)
        self.assertIn("Viewing", page)

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
            self.assertIn("Open unsubscribe link", page)
            self.assertIn("Manual Follow-Up", page)
            self.assertIn("All candidates: 2", page)

    def test_daily_dashboard_page_lists_operational_sections(self) -> None:
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
            self.assertIn("Needs Attention", page)
            self.assertIn("Kept Visible", page)
            self.assertIn("Auto-Handled", page)
            self.assertIn("Queued unsubscribe review", page)
            self.assertIn("Open unsubscribe review", page)

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
            attention_section = page.split('<div class="eyebrow">What Changed Today</div>', 1)[0]

            self.assertIn("Confirm account activity", attention_section)
            self.assertIn("Insufficient context, high-consequence cue", attention_section)
            self.assertIn("Could be account-risk mail, but compact context is not enough.", attention_section)
            self.assertIn("1 lower-risk insufficient-context item kept out of this daily attention view.", attention_section)
            self.assertNotIn("Weekly reading list", attention_section)

    def test_daily_dashboard_page_has_useful_empty_attention_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_daily_report(storage_dir, "founder-test-batch-1", attention_items=[])

            page = GmailCompanionApp(storage_dir).render_daily_dashboard_page()

            self.assertIn("Needs Attention Now", page)
            self.assertIn("No attention-now items in the latest Gmail daily report.", page)
            self.assertIn("Possible Attention", page)
            self.assertIn("No possible-attention items in the latest Gmail daily report.", page)
            self.assertIn("Latest attention report: 2026-07-01", page)

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
            attention_section = page.split('<div class="eyebrow">What Changed Today</div>', 1)[0]

            self.assertNotIn("Flight check-in closes tonight", attention_section)
            self.assertIn("No attention-now items in the latest Gmail daily report.", attention_section)

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
            self.assertEqual(state["daily_summary"]["processed_count"], 6)
            self.assertEqual(state["daily_summary"]["auto_handled_count"], 2)
            self.assertEqual(state["daily_summary"]["needs_attention_count"], 1)
            self.assertEqual(state["daily_summary"]["top_labels"][0]["label"], "EA/Promotions")
            self.assertEqual(state["daily_summary"]["run_count"], 1)
            self.assertEqual(state["daily_summary"]["report_date"], "2026-06-29")
            self.assertEqual(state["daily_summary"]["changed_today"]["label_writes_count"], 0)
            self.assertEqual(state["daily_summary"]["changed_today"]["inbox_removed_count"], 1)

    def test_harness_state_defaults_to_a_needs_attention_email_and_exposes_buckets(self) -> None:
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

            self.assertEqual(state["selected_context"]["message_id"], "gmail-live-001")
            self.assertTrue(state["sidebar_state"]["selected_email"]["found"])
            self.assertEqual(state["sidebar_state"]["selected_email"]["status"], "needs-attention")
            self.assertEqual(state["sidebar_state"]["selected_email"]["suggested_label"], "job-related")
            self.assertEqual(len(state["needs_attention_items"]), 1)
            self.assertEqual(len(state["recent_items"]), 2)
            self.assertEqual(state["auto_handled_items"], [])
            self.assertEqual(len(state["kept_visible_items"]), 1)

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

            preview = GmailCompanionApp(storage_dir).teach_preview(
                {
                    "selected_context": {
                        "provider": "gmail",
                        "message_id": "gmail-live-001",
                        "subject": "Sophie Riding sent you a message",
                        "sender": "messages-noreply@linkedin.com",
                    },
                    "target_label": "personal",
                    "note": "LinkedIn direct messages from real people should be personal.",
                }
            )

            self.assertIn("I can relabel this email to EA/Personal.", preview["acknowledgment"])
            self.assertEqual(preview["impact"]["matching_existing_count"], 1)
            self.assertEqual(preview["selected_label_after"], ["personal"])
            self.assertEqual(preview["impact"]["matching_existing_examples"][0]["labels_after"], ["personal"])

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

            summary = GmailCompanionApp(storage_dir).sidebar_state({})["daily_summary"]["changed_today"]

            self.assertEqual(summary["label_writes_count"], 1)
            self.assertEqual(summary["inbox_removed_count"], 1)
            self.assertEqual(summary["selected_unsubscribe_count"], 1)
            self.assertEqual(len(summary["items"]), 2)
            self.assertEqual(summary["selected_unsubscribe_examples"][0]["display_name"], "Store")
            self.assertIn("list_key=gmail%3Afounder-test%3Anews%40example.com", summary["selected_unsubscribe_examples"][0]["handoff_path"])

    def test_teach_apply_matching_existing_relabels_current_and_saves_rule(self) -> None:
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

            rule_payload = json.loads((storage_dir / "teachable_classification_rules.json").read_text())
            batch_one = json.loads((storage_dir / "batches" / "founder-test-batch-1.json").read_text())
            batch_two = json.loads((storage_dir / "batches" / "founder-test-batch-2.json").read_text())

            self.assertIn("rewrote 1 matching stored emails", result["acknowledgment"])
            self.assertIn("saved the sender-level lesson for future mail", result["acknowledgment"])
            self.assertEqual(result["matched_existing_count"], 1)
            self.assertEqual(batch_one["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(batch_two["items"][0]["final_labels"], ["job-related"])
            self.assertEqual(rule_payload["rules"][0]["label"], "job-related")
            self.assertIn(("apply_labels", "gmail-live-001", [gmail_client.labels["EA/Work"]]), gmail_client.calls)
            self.assertIn(("apply_labels", "gmail-live-002", [gmail_client.labels["EA/Work"]]), gmail_client.calls)
            self.assertEqual(result["gmail_write_through"]["messages_written"], 2)

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

            self.assertIn(("apply_labels", "gmail-live-001", [gmail_client.labels["EA/ReplyNeeded"]]), gmail_client.calls)
            self.assertEqual(result["gmail_write_through"]["messages_written"], 1)
            self.assertEqual(result["gmail_write_through"]["inbox_removed"], 0)
            self.assertIn("relabeled only this email", result["acknowledgment"])

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

            self.assertIn("saved a sender-level lesson for future mail", result["acknowledgment"])
            self.assertIn("No other existing stored emails were rewritten", result["acknowledgment"])

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

    def test_harness_state_endpoint_includes_cors_headers(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        handler = _FakeRequestHandler("/api/harness-state", method="GET")

        app.handle_request(handler)

        self.assertEqual(handler.code, 200)
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Headers"], "Content-Type")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Private-Network"], "true")

    def test_options_request_returns_cors_preflight_headers(self) -> None:
        app = GmailCompanionApp(Path("/tmp/example"))
        handler = _FakeRequestHandler("/api/teach-apply", method="OPTIONS")

        app.handle_request(handler)

        self.assertEqual(handler.code, 204)
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Methods"], "GET, POST, OPTIONS")
        self.assertEqual(handler.sent_headers["Access-Control-Allow-Headers"], "Content-Type")
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
