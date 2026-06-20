import json
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.local_browser_review_ui import LocalBrowserReviewApp, main


class LocalBrowserReviewUiTests(unittest.TestCase):
    def test_browser_review_script_runs_from_repo_root_without_pythonpath(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [sys.executable, "scripts/review_local_batch_in_browser.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Serve a local browser review UI", result.stdout)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_main_prints_local_url_for_one_batch(self) -> None:
        stdout = io.StringIO()
        fake_server = _FakeServer(server_port=43123)

        exit_code = main(
            ["--batch-id", "founder-test-batch-1", "--storage-dir", "/tmp/example"],
            stdout=stdout,
            server_factory=lambda host, port, storage_dir, batch_id, account_id, credentials_dir, client_secret_path, fetch_batch_size: fake_server,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(fake_server.served)
        self.assertTrue(fake_server.closed)
        self.assertIn("http://127.0.0.1:43123", stdout.getvalue())

    def test_main_can_start_workbench_without_batch_id(self) -> None:
        stdout = io.StringIO()
        fake_server = _FakeServer(server_port=43123)

        exit_code = main(
            ["--storage-dir", "/tmp/example"],
            stdout=stdout,
            server_factory=lambda host, port, storage_dir, batch_id, account_id, credentials_dir, client_secret_path, fetch_batch_size: fake_server,
        )

        self.assertEqual(exit_code, 0)
        self.assertTrue(fake_server.served)
        self.assertTrue(fake_server.closed)
        self.assertIn("stored batch review UI", stdout.getvalue())

    def test_workbench_page_lists_stored_batches_and_highlights_pending_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Private Person <person@example.com>",
                        "subject": "Very private subject line",
                        "body": "Sensitive body text",
                        "date": "2024-06-19T08:00:00Z",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "interpretation": "Needs attention.",
                    }
                ],
            )
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-101",
                        "sender": "Store <orders@example.com>",
                        "subject": "Order update",
                        "body": "Private order body",
                        "date": "2024-06-20T08:00:00Z",
                        "applied_labels": ["shopping-order"],
                        "near_misses": [],
                        "confidence_band": "medium",
                        "interpretation": "A routine order confirmation.",
                    }
                ],
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("Stored batch workbench", page)
            self.assertIn("founder-test-batch-1", page)
            self.assertIn("founder-test-batch-2", page)
            self.assertIn("Pending review", page)
            self.assertIn("Open batch", page)
            self.assertIn("Fetch another batch", page)
            self.assertIn("Trusted Personal Senders", page)
            self.assertNotIn("Very private subject line", page)
            self.assertNotIn("Sensitive body text", page)

    def test_workbench_shows_trusted_sender_store_path_and_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "trusted_personal_senders.json").write_text(
                json.dumps(
                    {
                        "trusted_personal_senders": [
                            {
                                "address": "sophielyneriding@gmail.com",
                                "source": "review_history",
                                "kind": "direct",
                                "notes": "Auto-seeded from 2 reviewed personal messages.",
                            }
                        ]
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("Allowlist file:", page)
            self.assertIn("sophielyneriding@gmail.com", page)
            self.assertIn("review_history", page)

    def test_workbench_lists_shadow_evaluation_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            evaluations_dir = storage_dir / "evaluations"
            evaluations_dir.mkdir(parents=True, exist_ok=True)
            (evaluations_dir / "shadow-label-eval-20260619T131806Z.json").write_text(
                json.dumps(
                    {
                        "overall": {
                            "reviewed_count": 100,
                            "heuristic": {"exact_match_rate": 77.0},
                        },
                        "comparison_candidates": [{"batch_id": "b1", "message_id": "m1"}],
                        "disagreements": {"model_better_than_heuristic": [{"batch_id": "b1", "message_id": "m1"}]},
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("Shadow Evaluations", page)
            self.assertIn("Open evaluation", page)
            self.assertIn("77.0%", page)
            self.assertIn("OpenAI vs your final result", page)

    def test_workbench_lists_grouped_unsubscribe_candidates_and_excludes_transactional_mail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = storage_dir / "batches" / "founder-test-batch-1.json"
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            batch_path.write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "provider": "gmail",
                        "raw_messages": [
                            {
                                "id": "gmail-live-001",
                                "snippet": "20% off this weekend.",
                                "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                                        {"name": "Subject", "value": "Weekend sale"},
                                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                                        {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                                        {"name": "Precedence", "value": "bulk"},
                                    ]
                                },
                            },
                            {
                                "id": "gmail-live-002",
                                "snippet": "New arrivals are here.",
                                "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                                        {"name": "Subject", "value": "New arrivals"},
                                        {"name": "Date", "value": "Thu, 20 Jun 2024 08:00:00 +0000"},
                                        {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                                    ]
                                },
                            },
                            {
                                "id": "gmail-live-003",
                                "snippet": "Your code is 123456.",
                                "labelIds": ["INBOX"],
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Microsoft <account@example.com>"},
                                        {"name": "Subject", "value": "Your single-use code"},
                                        {"name": "Date", "value": "Thu, 20 Jun 2024 09:00:00 +0000"},
                                        {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                                    ]
                                },
                            },
                        ],
                        "fetch_failures": [],
                        "items": [
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-001",
                                "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                                "subject": "Weekend sale",
                                "date": "2024-06-19T08:00:00Z",
                                "snippet": "20% off this weekend.",
                                "body": "20% off this weekend.",
                                "interpretation": "A promotional discount email.",
                                "applied_labels": ["promotions"],
                                "near_misses": [],
                                "confidence_band": "high",
                            },
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-002",
                                "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                                "subject": "New arrivals",
                                "date": "2024-06-20T08:00:00Z",
                                "snippet": "New arrivals are here.",
                                "body": "New arrivals are here.",
                                "interpretation": "A newsletter from a recurring retail sender.",
                                "applied_labels": ["newsletter"],
                                "near_misses": [],
                                "confidence_band": "high",
                            },
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-003",
                                "sender": "Microsoft <account@example.com>",
                                "subject": "Your single-use code",
                                "date": "2024-06-20T09:00:00Z",
                                "snippet": "Your code is 123456.",
                                "body": "Your code is 123456.",
                                "interpretation": "Account security or account-access alert.",
                                "applied_labels": ["account-security"],
                                "near_misses": [],
                                "confidence_band": "high",
                            },
                        ],
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("Unsubscribe inventory", page)
            self.assertIn("Healthy Planet", page)
            self.assertIn("Evidence:</strong> 2 messages", page)
            self.assertIn("Most recent:</strong> 2024-06-20T08:00:00Z", page)
            self.assertIn("Qualified because:", page)
            self.assertNotIn("Microsoft <account@example.com>", page)

    def test_unsubscribe_selection_post_persists_provider_aware_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            batch_path = storage_dir / "batches" / "founder-test-batch-1.json"
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            batch_path.write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "provider": "gmail",
                        "raw_messages": [
                            {
                                "id": "gmail-live-001",
                                "snippet": "20% off this weekend.",
                                "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>"},
                                        {"name": "Subject", "value": "Weekend sale"},
                                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                                        {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                                    ]
                                },
                            }
                        ],
                        "fetch_failures": [],
                        "items": [
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-001",
                                "sender": "Healthy Planet <newsletters@mail.healthyplanetcanada.com>",
                                "subject": "Weekend sale",
                                "date": "2024-06-19T08:00:00Z",
                                "snippet": "20% off this weekend.",
                                "body": "20% off this weekend.",
                                "interpretation": "A promotional discount email.",
                                "applied_labels": ["promotions"],
                                "near_misses": [],
                                "confidence_band": "high",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            candidate_key = "gmail:founder-test:newsletters@mail.healthyplanetcanada.com"
            status_code, response = app.handle_api_request(
                "POST",
                "/api/unsubscribe-candidates/selections",
                {
                    "candidate_keys": [candidate_key],
                    "selected_candidate_keys": [candidate_key],
                },
            )

            saved = json.loads((storage_dir / "unsubscribe_selections.json").read_text())
            page = app.render_page()

            self.assertEqual(status_code, 200)
            self.assertEqual(response["saved_count"], 1)
            self.assertEqual(response["candidates"][0]["decision_state"], "selected")
            self.assertEqual(saved["candidates"][candidate_key]["provider"], "gmail")
            self.assertEqual(saved["candidates"][candidate_key]["account_id"], "founder-test")
            self.assertEqual(saved["candidates"][candidate_key]["decision_state"], "selected")
            self.assertEqual(saved["candidates"][candidate_key]["list_unsubscribe"], "<https://example.com/unsub>")
            self.assertIn("Selected for later unsubscribe", page)

    def test_unsubscribe_execution_post_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:promo@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:promo@example.com",
                                "display_name": "Promo Sender",
                                "sender": "Promo Sender <promo@example.com>",
                                "sender_address": "promo@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://example.com/unsub>",
                                "list_unsubscribe_post": "List-Unsubscribe=One-Click",
                            }
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            status_code, response = app.handle_api_request("POST", "/api/unsubscribe-executions", {"confirmation": "NOPE"})

            self.assertEqual(status_code, 409)
            self.assertIn("UNSUBSCRIBE", response["error"])

    def test_workbench_shows_latest_unsubscribe_execution_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:promo@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:promo@example.com",
                                "display_name": "Promo Sender",
                                "sender": "Promo Sender <promo@example.com>",
                                "sender_address": "promo@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://example.com/unsub>",
                                "list_unsubscribe_post": "List-Unsubscribe=One-Click",
                            }
                        }
                    },
                    indent=2,
                )
            )
            (storage_dir / "unsubscribe_execution_audit.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:promo@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "display_name": "Promo Sender",
                                "sender": "Promo Sender <promo@example.com>",
                                "attempts": [
                                    {
                                        "attempted_at": "2026-06-20T09:00:00Z",
                                        "status": "executed",
                                        "method": "one-click-post",
                                        "url": "https://example.com/unsub",
                                        "notes": "Ready for one-click HTTPS unsubscribe.",
                                    }
                                ],
                            }
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("Latest unsubscribe:</strong> executed via one-click-post", page)
            self.assertIn("Ready for one-click HTTPS unsubscribe.", page)

    def test_workbench_shows_manual_mailto_unsubscribe_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:newsletter@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:newsletter@example.com",
                                "display_name": "Newsletter",
                                "sender": "Newsletter <newsletter@example.com>",
                                "sender_address": "newsletter@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<mailto:unsubscribe@example.com>",
                                "list_unsubscribe_post": "",
                            }
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn('href="mailto:unsubscribe@example.com"', page)
            self.assertIn("Manual mail unsubscribe", page)

    def test_workbench_shows_manual_http_unsubscribe_action_for_non_one_click_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:offers@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:offers@example.com",
                                "display_name": "Offers",
                                "sender": "Offers <offers@example.com>",
                                "sender_address": "offers@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://example.com/unsub>",
                                "list_unsubscribe_post": "",
                            }
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn('href="https://example.com/unsub"', page)
            self.assertIn("Open unsubscribe link manually", page)

    def test_workbench_does_not_show_manual_only_action_for_one_click_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:promo@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:promo@example.com",
                                "display_name": "Promo Sender",
                                "sender": "Promo Sender <promo@example.com>",
                                "sender_address": "promo@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://example.com/unsub>",
                                "list_unsubscribe_post": "List-Unsubscribe=One-Click",
                            }
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertNotIn("Open unsubscribe link manually", page)
            self.assertNotIn("Manual mail unsubscribe", page)

    def test_workbench_shows_unsubscribe_execution_summary_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            (storage_dir / "unsubscribe_selections.json").write_text(
                json.dumps(
                    {
                        "candidates": {
                            "gmail:founder-test:promo@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:promo@example.com",
                                "display_name": "Promo Sender",
                                "sender": "Promo Sender <promo@example.com>",
                                "sender_address": "promo@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<https://example.com/unsub>",
                                "list_unsubscribe_post": "List-Unsubscribe=One-Click",
                            },
                            "gmail:founder-test:newsletter@example.com": {
                                "provider": "gmail",
                                "account_id": "founder-test",
                                "list_key": "gmail:founder-test:newsletter@example.com",
                                "display_name": "Newsletter",
                                "sender": "Newsletter <newsletter@example.com>",
                                "sender_address": "newsletter@example.com",
                                "decision_state": "selected",
                                "evidence_count": 1,
                                "latest_message_date": "2024-06-20T08:00:00Z",
                                "qualification_reasons": ["List-Unsubscribe header"],
                                "list_unsubscribe": "<mailto:unsubscribe@example.com>",
                                "list_unsubscribe_post": "",
                            }
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("Execution preview", page)
            self.assertIn("<strong>1</strong><div class=\"meta\">Ready now</div>", page)
            self.assertIn("<strong>1</strong><div class=\"meta\">Manual follow-up</div>", page)

    def test_page_can_render_shadow_evaluation_disagreements(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            evaluations_dir = storage_dir / "evaluations"
            evaluations_dir.mkdir(parents=True, exist_ok=True)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "snippet": "Can you sign this off before lunch?",
                        "body": "Please approve the revised budget before lunch so finance can submit it.",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": ["job-related"],
                    }
                ],
            )
            (evaluations_dir / "shadow-label-eval-20260619T131806Z.json").write_text(
                json.dumps(
                    {
                        "overall": {
                            "reviewed_count": 100,
                            "heuristic": {"exact_match_rate": 77.0},
                            "model": {"exact_match_rate": 82.0},
                        },
                        "comparison_candidates": [
                            {
                                "batch_id": "founder-test-batch-1",
                                "message_id": "gmail-live-001",
                                "sender": "Manager <boss@example.com>",
                                "subject": "Need your approval today",
                                "ground_truth": ["job-related"],
                                "heuristic_labels": ["reply-needed"],
                                "model_labels": ["job-related", "reply-needed"],
                                "model_reason": "This appears to be a work message that still expects a response.",
                            }
                        ],
                        "disagreements": {"model_better_than_heuristic": []},
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page(selected_evaluation_id="shadow-label-eval-20260619T131806Z")

            self.assertIn("OpenAI shadow suggestion", page)
            self.assertIn("Current system suggestion (background only)", page)
            self.assertIn("Your final reviewed result", page)
            self.assertIn("Prefer your final reviewed result", page)
            self.assertIn("Prefer OpenAI", page)
            self.assertIn("You are choosing between your final reviewed result and the OpenAI shadow suggestion on 1 differing messages.", page)
            self.assertIn("Current system suggestion is shown only as background context. It is not one of the two choices.", page)
            self.assertIn("Preview:</strong> Can you sign this off before lunch?", page)
            self.assertIn("Date:</strong> 2024-06-19T08:00:00Z", page)
            self.assertIn("More context", page)
            self.assertIn("Body:</strong> Please approve the revised budget before lunch so finance can submit it.", page)
            self.assertNotIn("Approve suggested", page)

    def test_evaluation_preference_post_persists_vote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            evaluations_dir = storage_dir / "evaluations"
            evaluations_dir.mkdir(parents=True, exist_ok=True)
            evaluation_id = "shadow-label-eval-20260619T131806Z"
            (evaluations_dir / f"{evaluation_id}.json").write_text(
                json.dumps(
                    {
                        "comparison_candidates": [
                            {
                                "batch_id": "founder-test-batch-1",
                                "message_id": "gmail-live-001",
                                "sender": "Manager <boss@example.com>",
                                "subject": "Need your approval today",
                                "ground_truth": ["job-related"],
                                "heuristic_labels": ["job-related"],
                                "model_labels": ["reply-needed", "job-related"],
                                "model_reason": "Likely needs a response.",
                            }
                        ],
                        "disagreements": {
                            "model_better_than_heuristic": [
                                {
                                    "batch_id": "founder-test-batch-1",
                                    "message_id": "gmail-live-001",
                                    "sender": "Manager <boss@example.com>",
                                    "subject": "Need your approval today",
                                    "ground_truth": ["job-related"],
                                    "heuristic_labels": ["job-related"],
                                    "model_labels": ["reply-needed", "job-related"],
                                    "model_reason": "Likely needs a response.",
                                }
                            ]
                        }
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            status_code, response = app.handle_api_request(
                "POST",
                f"/api/evaluations/{evaluation_id}/preferences",
                {"item_key": "founder-test-batch-1:gmail-live-001", "preference": "openai"},
            )

            saved = json.loads((evaluations_dir / f"{evaluation_id}-preferences.json").read_text())

            self.assertEqual(status_code, 200)
            self.assertEqual(response["preferences"]["founder-test-batch-1:gmail-live-001"], "openai")
            self.assertEqual(saved["founder-test-batch-1:gmail-live-001"], "openai")

    def test_legacy_current_preference_renders_as_reviewed_preference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            evaluations_dir = storage_dir / "evaluations"
            evaluations_dir.mkdir(parents=True, exist_ok=True)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "snippet": "Can you sign this off before lunch?",
                        "body": "Please approve the revised budget before lunch so finance can submit it.",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "edit",
                        "final_labels": ["job-related"],
                    }
                ],
            )
            evaluation_id = "shadow-label-eval-20260619T131806Z"
            (evaluations_dir / f"{evaluation_id}.json").write_text(
                json.dumps(
                    {
                        "overall": {
                            "reviewed_count": 1,
                            "heuristic": {"exact_match_rate": 0.0},
                            "model": {"exact_match_rate": 0.0},
                        },
                        "comparison_candidates": [
                            {
                                "batch_id": "founder-test-batch-1",
                                "message_id": "gmail-live-001",
                                "sender": "Manager <boss@example.com>",
                                "subject": "Need your approval today",
                                "ground_truth": ["job-related"],
                                "heuristic_labels": ["job-related"],
                                "model_labels": ["reply-needed"],
                                "model_reason": "Likely needs a response.",
                            }
                        ],
                        "disagreements": {
                            "model_better_than_heuristic": [
                                {
                                    "batch_id": "founder-test-batch-1",
                                    "message_id": "gmail-live-001",
                                    "sender": "Manager <boss@example.com>",
                                    "subject": "Need your approval today",
                                    "ground_truth": ["job-related"],
                                    "heuristic_labels": ["job-related"],
                                    "model_labels": ["reply-needed"],
                                    "model_reason": "Likely needs a response.",
                                }
                            ]
                        },
                    },
                    indent=2,
                )
            )
            (evaluations_dir / f"{evaluation_id}-preferences.json").write_text(
                json.dumps({"founder-test-batch-1:gmail-live-001": "current"}, indent=2)
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page(selected_evaluation_id=evaluation_id)

            self.assertIn("Prefer your final reviewed result", page)

    def test_workbench_can_run_shadow_evaluation_for_100_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[],
            )

            captured = {}

            def fake_run_shadow_eval(limit: int) -> dict:
                captured["limit"] = limit
                return {
                    "evaluation_id": "shadow-label-eval-20260619T150000Z",
                    "reviewed_count": 100,
                    "comparison_count": 17,
                    "report_path": str(storage_dir / "evaluations" / "shadow-label-eval-20260619T150000Z.json"),
                }

            app = LocalBrowserReviewApp(storage_dir, None, run_shadow_eval_fn=fake_run_shadow_eval)
            status_code, response = app.handle_api_request("POST", "/api/evaluations", {})

            self.assertEqual(status_code, 200)
            self.assertEqual(captured["limit"], 100)
            self.assertEqual(response["evaluation_id"], "shadow-label-eval-20260619T150000Z")
            self.assertEqual(response["comparison_count"], 17)

    def test_workbench_surfaces_shadow_evaluation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[],
            )

            def failing_run_shadow_eval(limit: int) -> dict:
                raise RuntimeError("OpenAI API request failed")

            app = LocalBrowserReviewApp(storage_dir, None, run_shadow_eval_fn=failing_run_shadow_eval)
            status_code, response = app.handle_api_request("POST", "/api/evaluations", {})

            self.assertEqual(status_code, 500)
            self.assertIn("OpenAI API request failed", response["error"])

    def test_workbench_fetch_action_creates_new_batch_and_returns_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <offers@example.com>",
                        "subject": "20% off today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A promotional discount email.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            fetched = {}

            def fake_fetcher(account_id: str) -> dict:
                fetched["account_id"] = account_id
                return {
                    "batch_id": "founder-test-batch-2",
                    "items": [
                        {
                            "message_id": "gmail-live-101",
                            "review_state": "pending",
                        }
                    ],
                }

            app = LocalBrowserReviewApp(storage_dir, None, fetch_batch_fn=fake_fetcher)
            status_code, response = app.handle_api_request("POST", "/api/fetch-batches", {})

            self.assertEqual(status_code, 200)
            self.assertEqual(fetched["account_id"], "founder-test")
            self.assertEqual(response["batch_id"], "founder-test-batch-2")
            self.assertEqual(response["fetched_count"], 1)

    def test_workbench_fetch_action_reports_no_new_mail_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[],
            )

            app = LocalBrowserReviewApp(storage_dir, None, fetch_batch_fn=lambda account_id: None)
            status_code, response = app.handle_api_request("POST", "/api/fetch-batches", {})

            self.assertEqual(status_code, 200)
            self.assertIsNone(response["batch_id"])
            self.assertEqual(response["fetched_count"], 0)

    def test_workbench_fetch_action_surfaces_fetch_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[],
            )

            def failing_fetcher(account_id: str) -> dict:
                raise RuntimeError("OAuth setup failed")

            app = LocalBrowserReviewApp(storage_dir, None, fetch_batch_fn=failing_fetcher)
            status_code, response = app.handle_api_request("POST", "/api/fetch-batches", {})

            self.assertEqual(status_code, 500)
            self.assertIn("OAuth setup failed", response["error"])

    def test_page_for_pending_batch_includes_review_context_and_action_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed", "job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            page = app.render_page()

            self.assertIn("<title>Stored Batch Review</title>", page)
            self.assertIn("Review stored batch founder-test-batch-1", page)
            self.assertIn("Item 1 of 1", page)
            self.assertIn("<strong>Message ID:</strong> gmail-live-001", page)
            self.assertIn("From:</strong> Manager &lt;boss@example.com&gt;", page)
            self.assertIn("Subject:</strong> Need your approval today", page)
            self.assertIn("Date:</strong> 2024-06-19T08:00:00Z", page)
            self.assertIn("Preview:</strong> Need your approval today", page)
            self.assertIn("Suggested labels:</strong> EA/ReplyNeeded, EA/Work", page)
            self.assertIn("Why:</strong> Work request that likely needs a response.", page)
            self.assertIn("Approve suggested", page)
            self.assertIn("Save selected labels", page)
            self.assertIn("Use Save selected labels after changing labels.", page)
            self.assertIn("Mark unlabeled", page)
            self.assertIn("Reject", page)

    def test_page_for_pending_batch_can_expand_fuller_email_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Travel Desk <travel@example.com>",
                        "subject": "Your itinerary and booking details",
                        "date": "2024-06-19T08:00:00Z",
                        "snippet": "Train departs at 08:14 from platform 3.",
                        "body": "Full itinerary body with booking reference ABC123 and seat details.",
                        "interpretation": "Travel booking details that may need fuller review context.",
                        "applied_labels": ["travel"],
                        "near_misses": [],
                        "confidence_band": "medium",
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            page = app.render_page()

            self.assertIn("More context", page)
            self.assertIn("Preview:</strong> Train departs at 08:14 from platform 3.", page)
            self.assertIn("Snippet:</strong> Train departs at 08:14 from platform 3.", page)
            self.assertIn("Body:</strong> Full itinerary body with booking reference ABC123 and seat details.", page)

    def test_allowed_ea_labels_are_rendered_as_clickable_options(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            page = app.render_page()

            self.assertIn('class="taxonomy-option"', page)
            self.assertIn('data-label="EA/Account"', page)
            self.assertIn('data-label="EA/ReplyNeeded"', page)

    def test_page_can_open_specific_batch_from_workbench_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-101",
                        "sender": "Store <orders@example.com>",
                        "subject": "Order update",
                        "date": "2024-06-20T08:00:00Z",
                        "interpretation": "A routine order confirmation.",
                        "applied_labels": ["shopping-order"],
                        "near_misses": [],
                        "confidence_band": "medium",
                    }
                ],
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            status_code, response = app.handle_api_request("GET", "/api/batches/founder-test-batch-2")

            self.assertEqual(status_code, 200)
            self.assertEqual(response["batch_id"], "founder-test-batch-2")
            self.assertEqual(response["items"][0]["message_id"], "gmail-live-101")

    def test_root_request_can_render_selected_batch_from_query_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-2",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-101",
                        "sender": "Store <orders@example.com>",
                        "subject": "Order update",
                        "date": "2024-06-20T08:00:00Z",
                        "interpretation": "A routine order confirmation.",
                        "applied_labels": ["shopping-order"],
                        "near_misses": [],
                        "confidence_band": "medium",
                    }
                ],
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            handler = _FakeHandler("GET", "/?batch_id=founder-test-batch-2")

            app.handle_request(handler)

            rendered = handler.wfile.getvalue().decode("utf-8")
            self.assertEqual(handler.status_code, 200)
            self.assertIn("Review stored batch founder-test-batch-2", rendered)
            self.assertIn("Order update", rendered)

    def test_plausible_inbox_removal_candidate_shows_actionability_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = Path(temp_dir) / "batches" / "founder-test-batch-1.json"
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            batch_path.write_text(
                json.dumps(
                    {
                        "batch_id": "founder-test-batch-1",
                        "account_id": "founder-test",
                        "raw_messages": [
                            {
                                "id": "gmail-live-001",
                                "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
                                "snippet": "20% off today",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Store <offers@example.com>"},
                                        {"name": "Subject", "value": "20% off today"},
                                        {"name": "Date", "value": "Wed, 19 Jun 2024 08:00:00 +0000"},
                                        {
                                            "name": "List-Unsubscribe",
                                            "value": "<mailto:unsubscribe@example.com>, <https://example.com/unsub>",
                                        },
                                    ]
                                },
                            }
                        ],
                        "fetch_failures": [],
                        "items": [
                            {
                                "source": "gmail",
                                "account_id": "founder-test",
                                "message_id": "gmail-live-001",
                                "sender": "Store <offers@example.com>",
                                "subject": "20% off today",
                                "date": "2024-06-19T08:00:00Z",
                                "interpretation": "A promotional discount email.",
                                "applied_labels": ["promotions"],
                                "near_misses": [],
                                "confidence_band": "high",
                            }
                        ],
                    },
                    indent=2,
                )
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            page = app.render_page()

            self.assertIn("Actionability", page)
            self.assertIn("Safe to remove from inbox", page)
            self.assertIn("Keep in inbox", page)

    def test_batch_api_returns_stored_batch_items_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed", "job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            status_code, response = app.handle_api_request("GET", "/api/batches/founder-test-batch-1")

            self.assertEqual(status_code, 200)
            self.assertEqual(response["batch_id"], "founder-test-batch-1")
            self.assertEqual(response["summary"]["total_items"], 1)
            self.assertEqual(response["summary"]["reviewed_items"], 0)
            self.assertEqual(response["summary"]["remaining_items"], 1)
            self.assertEqual(response["items"][0]["message_id"], "gmail-live-001")
            self.assertEqual(response["items"][0]["suggested_labels"], ["EA/ReplyNeeded", "EA/Work"])
            self.assertEqual(response["items"][0]["snippet"], "Need your approval today")
            self.assertEqual(response["items"][0]["body"], "Need your approval today")
            self.assertEqual(response["items"][0]["review_state"], "pending")
            self.assertIn("EA/Account", response["allowed_labels"])

    def test_decision_post_persists_review_choice_and_updates_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Google <no-reply@accounts.google.com>",
                        "subject": "Security alert",
                        "date": "2026-06-15T18:43:06Z",
                        "interpretation": "Account security or account-access alert that likely needs to stay easy to find.",
                        "applied_labels": ["account-security"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            status_code, response = app.handle_api_request(
                "POST",
                "/api/batches/founder-test-batch-1/decisions",
                {
                    "message_id": "gmail-live-001",
                    "decision": "edit",
                    "final_labels": ["reply-needed", "account-security"],
                },
            )

            reloaded_status, reloaded = app.handle_api_request(
                "GET",
                "/api/batches/founder-test-batch-1",
            )

            stored_batch = json.loads(batch_path.read_text())

            self.assertEqual(status_code, 200)
            self.assertEqual(response["item"]["review_action"], "edit")
            self.assertEqual(response["item"]["final_labels"], ["EA/ReplyNeeded", "EA/Account"])
            self.assertEqual(response["summary"]["reviewed_items"], 1)
            self.assertEqual(response["summary"]["remaining_items"], 0)
            self.assertEqual(response["summary"]["label_counts"], {"EA/Account": 1, "EA/ReplyNeeded": 1})
            self.assertEqual(stored_batch["items"][0]["review_state"], "reviewed")
            self.assertEqual(stored_batch["items"][0]["review_action"], "edit")
            self.assertEqual(stored_batch["items"][0]["final_labels"], ["reply-needed", "account-security"])
            self.assertFalse((Path(temp_dir) / "founder-test-batch-1_write_status.json").exists())
            self.assertEqual(reloaded_status, 200)
            self.assertEqual(reloaded["summary"]["reviewed_items"], 1)
            self.assertEqual(reloaded["items"][0]["final_labels"], ["EA/ReplyNeeded", "EA/Account"])

    def test_decision_post_persists_actionability_for_plausible_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_path = self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Store <offers@example.com>",
                        "subject": "20% off today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A promotional discount email.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            status_code, response = app.handle_api_request(
                "POST",
                "/api/batches/founder-test-batch-1/decisions",
                {
                    "message_id": "gmail-live-001",
                    "decision": "approve",
                    "actionability": "keep-in-inbox",
                },
            )

            stored_batch = json.loads(batch_path.read_text())
            reloaded_status, reloaded = app.handle_api_request("GET", "/api/batches/founder-test-batch-1")

            self.assertEqual(status_code, 200)
            self.assertEqual(response["item"]["actionability"], "keep-in-inbox")
            self.assertEqual(stored_batch["items"][0]["actionability"], "keep-in-inbox")
            self.assertEqual(reloaded_status, 200)
            self.assertEqual(reloaded["items"][0]["actionability"], "keep-in-inbox")

    def test_page_for_batch_with_no_pending_items_shows_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            page = app.render_page()

            self.assertIn("No pending items remain for this batch.", page)
            self.assertNotIn("Approve suggested", page)

    def test_workbench_surfaces_50_reviewed_message_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": f"gmail-live-{index:03d}",
                        "sender": "Store <offers@example.com>",
                        "subject": f"Promo {index}",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A promotional discount email.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                        "actionability": "safe-to-remove-from-inbox",
                    }
                    for index in range(50)
                ],
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("50 reviewed messages reached", page)

    def test_workbench_computes_100_message_gate_from_explicit_actionability_reviews_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            self._write_named_batch(
                storage_dir,
                "founder-test-batch-1",
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": f"gmail-live-{index:03d}",
                        "sender": "Manager <boss@example.com>",
                        "subject": f"Work item {index}",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A work message.",
                        "applied_labels": ["job-related"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["job-related"],
                    }
                    for index in range(98)
                ]
                + [
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-998",
                        "sender": "Store <offers@example.com>",
                        "subject": "20% off today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A promotional discount email.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                        "actionability": "safe-to-remove-from-inbox",
                    },
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-999",
                        "sender": "Store <offers@example.com>",
                        "subject": "Clearance sale",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "Another promotional discount email.",
                        "applied_labels": ["promotions"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["promotions"],
                        "actionability": "keep-in-inbox",
                    },
                ],
            )

            app = LocalBrowserReviewApp(storage_dir, None)
            page = app.render_page()

            self.assertIn("100 reviewed messages reached", page)
            self.assertIn("100-message automation gate is ready for founder review", page)
            self.assertIn("Low-value actionability precision: 50%", page)
            self.assertIn("1 of 2 explicitly reviewed low-value candidates marked safe to remove", page)

    def test_reviewed_item_decision_post_is_rejected_to_preserve_frozen_review_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_batch(
                Path(temp_dir),
                items=[
                    {
                        "source": "gmail",
                        "account_id": "founder-test",
                        "message_id": "gmail-live-001",
                        "sender": "Manager <boss@example.com>",
                        "subject": "Need your approval today",
                        "date": "2024-06-19T08:00:00Z",
                        "interpretation": "A manager asks for a same-day approval.",
                        "applied_labels": ["reply-needed"],
                        "near_misses": [],
                        "confidence_band": "high",
                        "review_state": "reviewed",
                        "review_action": "approve",
                        "final_labels": ["reply-needed"],
                    }
                ],
            )

            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            status_code, response = app.handle_api_request(
                "POST",
                "/api/batches/founder-test-batch-1/decisions",
                {
                    "message_id": "gmail-live-001",
                    "decision": "reject",
                },
            )

            self.assertEqual(status_code, 409)
            self.assertIn("already been reviewed", response["error"])

    def test_page_for_missing_or_invalid_batch_shows_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            page = app.render_page()

            self.assertIn("Could not load stored batch.", page)
            self.assertIn("Unknown batch id: founder-test-batch-1", page)

    def test_unknown_batch_returns_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = LocalBrowserReviewApp(Path(temp_dir), "founder-test-batch-1")
            status_code, response = app.handle_api_request("GET", "/api/batches/missing-batch")

            self.assertEqual(status_code, 404)
            self.assertEqual(response["error"], "Unknown batch id")

    def _write_batch(self, storage_dir: Path, items: list[dict]) -> Path:
        return self._write_named_batch(storage_dir, "founder-test-batch-1", items)

    def _write_named_batch(self, storage_dir: Path, batch_id: str, items: list[dict]) -> Path:
        batch_path = storage_dir / "batches" / f"{batch_id}.json"
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        batch_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "account_id": "founder-test",
                    "raw_messages": [
                        {
                            "id": item["message_id"],
                            "snippet": item.get("snippet", item.get("body", item["subject"])),
                        }
                        for item in items
                    ],
                    "fetch_failures": [],
                    "items": items,
                },
                indent=2,
            )
        )
        return batch_path


if __name__ == "__main__":
    unittest.main()


class _FakeServer:
    def __init__(self, server_port: int) -> None:
        self.server_port = server_port
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True

    def server_close(self) -> None:
        self.closed = True


class _FakeHandler:
    def __init__(self, command: str, path: str) -> None:
        self.command = command
        self.path = path
        self.headers = {}
        self.wfile = io.BytesIO()
        self.status_code = None
        self.response_headers = {}

    def send_response(self, status_code: int) -> None:
        self.status_code = status_code

    def send_header(self, name: str, value: str) -> None:
        self.response_headers[name] = value

    def end_headers(self) -> None:
        return
