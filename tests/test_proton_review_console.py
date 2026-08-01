from __future__ import annotations

import json
import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.proton_review_console import ProtonReviewConsole, render_proton_review_page
from src.gmail_companion_ui import GmailCompanionApp
from src.product_analytics import ProductAnalytics


class FakeProtonClient:
    def __init__(self, message_ids: list[str] | None = None) -> None:
        self.message_ids = message_ids or ["101", "102"]
        self.messages = {
            "101": {
                "id": "101",
                "sender": "First sender <first@example.test>",
                "subject": "First subject",
                "date": "2026-07-16T08:00:00Z",
                "body": "First line\nThe complete first message context.",
                "rfc_message_id": "<first@example.test>",
            },
            "102": {
                "id": "102",
                "sender": "Second sender <second@example.test>",
                "subject": "Second subject",
                "date": "2026-07-16T09:00:00Z",
                "body": "Second complete message.",
                "rfc_message_id": "<second@example.test>",
            },
        }
        self.label_calls: list[tuple[str, str]] = []
        self.verify_result = True
        self.write_result = {
            "inbox_preserved": True,
            "destructive_actions": [],
            "mailbox": "Labels/EA-Personal",
        }

    def list_messages(self, max_results: int) -> list[str]:
        return self.message_ids[-max_results:]

    def get_message(self, message_id: str) -> dict:
        return dict(self.messages[message_id])

    def apply_label(self, message_id: str, label_name: str) -> dict:
        self.label_calls.append((message_id, label_name))
        return {"message_id": message_id, "label": label_name, **self.write_result}

    def message_has_label(self, rfc_message_id: str, label_name: str) -> bool:
        return self.verify_result


class ProtonReviewConsoleTests(unittest.TestCase):
    def test_rapid_proton_accepts_are_applied_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            console = self._console(root, FakeProtonClient())
            first_started = threading.Event()
            release_first = threading.Event()
            calls: list[str] = []

            def first() -> dict:
                calls.append("first-start")
                first_started.set()
                release_first.wait(timeout=2)
                calls.append("first-done")
                return {}

            def second() -> dict:
                calls.append("second")
                return {}

            console.start_companion_write(first)
            self.assertTrue(first_started.wait(timeout=1))
            console.start_companion_write(second)
            self.assertEqual(calls, ["first-start"])
            release_first.set()
            self._wait_for_activity(console, "done")

            self.assertEqual(calls, ["first-start", "first-done", "second"])

    def test_forced_llm_review_receives_full_proton_message_context(self) -> None:
        class RecordingIntentClient:
            def __init__(self) -> None:
                self.payload = None

            def interpret(self, payload: dict) -> dict:
                self.payload = payload
                return {
                    "target_label": "personal",
                    "semantic_pattern": "personal project notifications",
                    "cross_sender": True,
                    "confidence": "high",
                    "rationale": "The founder described a project-specific boundary.",
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_root = root / "gmail"
            proton_root = root / "proton"
            (proton_root / "batches").mkdir(parents=True)
            self._write_classification_ledger(proton_root)
            full_body = "First line\nThe complete private message context for this teaching decision."
            (proton_root / "batches" / "proton-batch.json").write_text(json.dumps({
                "batch_id": "proton-batch",
                "provider": "protonmail",
                "account_id": "founder-proton",
                "items": [{
                    "source": "protonmail",
                    "account_id": "founder-proton",
                    "message_id": "101",
                    "sender": "First sender <first@example.test>",
                    "subject": "First subject",
                    "body": full_body,
                    "review_state": "pending",
                    "final_labels": ["newsletter"],
                    "applied_labels": ["newsletter"],
                }],
                "raw_messages": [],
            }))
            client = RecordingIntentClient()
            app = GmailCompanionApp(
                gmail_root,
                proton_storage_dir=proton_root,
                proton_review_console=self._console(proton_root, FakeProtonClient(["101"])),
                analytics=ProductAnalytics(),
            )

            with patch("src.teaching_loop.OpenAITeachingIntentClient.from_env", return_value=client):
                preview = app.teach_preview_initial({
                    "selected_context": {"provider": "protonmail", "message_id": "101"},
                    "target_label": "personal",
                    "target_label_explicit": True,
                    "note": "Only personal AI project notifications should match this lesson.",
                    "scope": "sender",
                    "force_llm_review": True,
                })

            self.assertEqual(client.payload["current_body"], full_body)
            self.assertEqual(client.payload["current_subject"], "First subject")
            self.assertEqual(preview["intent_source"], "llm")

    def test_failed_background_write_can_be_retried_from_shared_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            console = self._console(root, FakeProtonClient())
            calls = []

            def work() -> dict:
                calls.append("called")
                return {"label_write_failed": 1 if len(calls) == 1 else 0}

            console.start_companion_write(work)
            self._wait_for_activity(console, "error")
            self.assertEqual(console.companion_write_activity()["action"], "retry-provider-write")

            console.retry_companion_write()
            self._wait_for_activity(console, "done")

            self.assertEqual(calls, ["called", "called"])

    def test_shared_teaching_advances_while_proton_write_finishes_in_background(self) -> None:
        class BlockingClient(FakeProtonClient):
            def __init__(self) -> None:
                super().__init__(message_ids=["101"])
                self.started = threading.Event()
                self.release = threading.Event()

            def apply_label(self, message_id: str, label_name: str) -> dict:
                self.started.set()
                self.release.wait(timeout=2)
                return super().apply_label(message_id, label_name)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_root = root / "gmail"
            proton_root = root / "proton"
            (proton_root / "batches").mkdir(parents=True)
            self._write_classification_ledger(proton_root)
            (proton_root / "batches" / "proton-batch.json").write_text(json.dumps({
                "batch_id": "proton-batch",
                "provider": "protonmail",
                "account_id": "founder-proton",
                "items": [{
                    "source": "protonmail",
                    "account_id": "founder-proton",
                    "message_id": "101",
                    "sender": "First sender <first@example.test>",
                    "subject": "First subject",
                    "body": "The complete first message context.",
                    "review_state": "pending",
                    "final_labels": ["newsletter"],
                    "applied_labels": ["newsletter"],
                }],
                "raw_messages": [],
            }))
            client = BlockingClient()
            console = self._console(proton_root, client)
            app = GmailCompanionApp(
                gmail_root,
                proton_storage_dir=proton_root,
                proton_review_console=console,
                analytics=ProductAnalytics(),
            )

            result = app.teach_apply({
                "selected_context": {"provider": "protonmail", "message_id": "101"},
                "target_label": "personal",
                "note": "",
                "scope": "sender",
                "mode": "current-only",
                "defer_provider_write": True,
                "included_message_ids": [],
            })

            self.assertEqual(result["provider_write"]["mode"], "pending")
            self.assertTrue(client.started.wait(timeout=1))
            self.assertEqual(console.companion_write_activity()["state"], "working")

            client.release.set()
            deadline = time.monotonic() + 2
            activity = None
            while time.monotonic() < deadline:
                activity = console.companion_write_activity()
                if activity and activity.get("state") == "done":
                    break
                time.sleep(0.01)

            self.assertEqual(activity["state"], "done")
            self.assertEqual(client.label_calls, [("101", "EA/Personal")])

    def test_shared_teaching_apply_routes_a_proton_decision_through_the_proton_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gmail_root = root / "gmail"
            proton_root = root / "proton"
            (proton_root / "batches").mkdir(parents=True)
            self._write_classification_ledger(proton_root)
            (proton_root / "batches" / "proton-batch.json").write_text(json.dumps({
                "batch_id": "proton-batch",
                "provider": "protonmail",
                "account_id": "founder-proton",
                "items": [
                    {
                        "source": "protonmail",
                        "account_id": "founder-proton",
                        "message_id": "101",
                        "sender": "First sender <first@example.test>",
                        "subject": "First subject",
                        "date": "2026-07-16T08:00:00Z",
                        "body": "The complete first message context.",
                        "interpretation": "An opted-in editorial digest.",
                        "review_state": "pending",
                        "final_labels": ["newsletter"],
                        "applied_labels": ["newsletter"],
                    }
                ],
                "raw_messages": [],
            }))
            client = FakeProtonClient(message_ids=["101"])
            console = self._console(proton_root, client)
            app = GmailCompanionApp(
                gmail_root,
                proton_storage_dir=proton_root,
                proton_review_console=console,
                analytics=ProductAnalytics(),
            )

            result = app.teach_apply({
                "selected_context": {"provider": "protonmail", "message_id": "101"},
                "target_label": "personal",
                "note": "",
                "scope": "sender",
                "mode": "current-only",
                "defer_provider_write": False,
                "included_message_ids": [],
            })

            self.assertEqual(client.label_calls, [("101", "EA/Personal")])
            self.assertEqual(result["provider_write"]["provider"], "protonmail")
            self.assertTrue(result["outcome"]["current_email_written_to_provider"])
            self.assertEqual(result["sidebar_state"]["daily_summary"]["needs_attention_count"], 0)

    def test_companion_harness_uses_shared_sidebar_contract_for_proton(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            console = self._console(root, FakeProtonClient())

            state = console.companion_harness({
                "provider": "protonmail",
                "subject": "First subject",
                "sender": "First sender <first@example.test>",
            })

            self.assertEqual(state["sidebar_state"]["contract_version"], "threadwise-sidebar-v2")
            self.assertEqual(state["sidebar_state"]["selected_context"]["provider"], "protonmail")
            self.assertEqual(state["sidebar_state"]["selected_email"]["message_id"], "101")
            self.assertEqual(state["sidebar_state"]["selected_email"]["status"], "needs-attention")
            self.assertEqual(state["sidebar_state"]["daily_summary"]["provider"], "protonmail")
            self.assertEqual(state["sidebar_state"]["daily_summary"]["needs_attention_count"], 2)
            self.assertEqual(
                [item["message_id"] for item in state["needs_attention_items"]],
                ["101", "102"],
            )
            self.assertEqual(state["sidebar_state"]["ui_state"]["provider_name"], "Proton Mail")

    def test_selected_completed_message_is_still_recognized_outside_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            (root / "console.json").write_text(json.dumps({
                "provider": "protonmail",
                "messages": {"101": {"decision": "looks-right"}},
            }))
            console = self._console(root, FakeProtonClient())

            state = console.companion_harness({
                "provider": "protonmail",
                "sender": "First sender <first@example.test>",
                "subject": "First subject",
            })

            self.assertTrue(state["sidebar_state"]["selected_email"]["found"])
            self.assertEqual(state["sidebar_state"]["selected_email"]["status"], "auto-handled")

    def test_companion_harness_does_not_reoffer_acknowledged_proton_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            console = self._console(root, FakeProtonClient())

            console.acknowledge("101")
            state = console.companion_harness({"provider": "protonmail"})

            self.assertEqual(state["sidebar_state"]["daily_summary"]["needs_attention_count"], 1)
            self.assertEqual(
                [item["message_id"] for item in state["needs_attention_items"]],
                ["102"],
            )

    def test_companion_server_exposes_discoverable_proton_review_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            console = self._console(root, FakeProtonClient())
            posthog = FakePostHogClient()
            analytics = ProductAnalytics(client=posthog, environment="production", enabled=True)
            app = GmailCompanionApp(
                root / "gmail",
                proton_review_console=console,
                analytics=analytics,
            )
            get_handler = FakeHandler("GET", "/proton-review")

            app.handle_request(get_handler)

            self.assertEqual(get_handler.status, 200)
            self.assertIn("First subject", get_handler.body_text)
            self.assertIn('/proton-review', app.render_daily_dashboard_page())

            post_handler = FakeHandler(
                "POST",
                "/api/proton-review/acknowledge",
                {"message_id": "101"},
            )
            app.handle_request(post_handler)

            self.assertEqual(post_handler.status, 200)
            self.assertEqual(json.loads(post_handler.body_text)["current"]["message_id"], "102")
            self.assertEqual(
                [call["event"] for call in posthog.calls],
                ["proton review opened", "proton review completed"],
            )
            self.assertEqual(posthog.calls[1]["properties"]["decision_type"], "looks_right")
            self.assertNotIn("message_id", posthog.calls[1]["properties"])

    def test_looks_right_advances_across_messages_and_persists_queue_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            client = FakeProtonClient()
            console = self._console(root, client)

            initial = console.state()
            after_first = console.acknowledge("101")
            resumed = self._console(root, client).state()
            after_second = console.acknowledge("102")

            self.assertEqual(initial["remaining_count"], 2)
            self.assertEqual(initial["current"]["message_id"], "101")
            self.assertEqual(after_first["remaining_count"], 1)
            self.assertEqual(after_first["current"]["message_id"], "102")
            self.assertEqual(resumed["current"]["message_id"], "102")
            self.assertEqual(after_second["remaining_count"], 0)
            self.assertIsNone(after_second["current"])

    def test_added_label_is_verified_and_then_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            client = FakeProtonClient()
            console = self._console(root, client)

            state = console.apply_label("101", "personal")

            self.assertEqual(client.label_calls, [("101", "EA/Personal")])
            self.assertEqual(state["remaining_count"], 1)
            self.assertEqual(state["current"]["message_id"], "102")
            saved = json.loads((root / "console.json").read_text())
            self.assertEqual(saved["messages"]["101"]["decision"], "label-added")
            self.assertTrue(saved["messages"]["101"]["provider_verified"])

    def test_approving_suggested_labels_writes_and_verifies_all_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "classification.json").write_text(json.dumps({
                "provider": "protonmail",
                "messages": {
                    "101": {
                        "status": "suggested",
                        "internal_labels": ["newsletter", "personal"],
                        "labels": ["EA/Newsletter", "EA/Personal"],
                        "reason": "An opted-in digest.",
                    },
                },
            }))
            client = FakeProtonClient(message_ids=["101"])
            console = self._console(root, client)

            state = console.apply_suggested("101")

            self.assertEqual(client.label_calls, [("101", "EA/Newsletter"), ("101", "EA/Personal")])
            self.assertEqual(state["remaining_count"], 0)
            saved = json.loads((root / "console.json").read_text())
            self.assertEqual(saved["messages"]["101"]["decision"], "suggested-labels-applied")
            self.assertTrue(saved["messages"]["101"]["provider_verified"])

    def test_accepting_primary_label_writes_only_the_primary_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "classification.json").write_text(json.dumps({
                "provider": "protonmail",
                "messages": {
                    "101": {
                        "status": "suggested",
                        "internal_labels": ["newsletter", "personal"],
                        "labels": ["EA/Newsletter", "EA/Personal"],
                        "reason": "An opted-in digest.",
                    },
                },
            }))
            client = FakeProtonClient(message_ids=["101"])
            state = self._console(root, client).apply_primary("101")

            self.assertEqual(client.label_calls, [("101", "EA/Newsletter")])
            self.assertEqual(state["remaining_count"], 0)
            saved = json.loads((root / "console.json").read_text())
            self.assertEqual(saved["messages"]["101"]["decision"], "primary-label-applied")

    def test_message_missing_from_live_inbox_is_not_offered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            console = self._console(root, FakeProtonClient(message_ids=["102"]))

            state = console.state()

            self.assertEqual(state["remaining_count"], 1)
            self.assertEqual(state["current"]["message_id"], "102")

    def test_destructive_or_unverified_write_is_rejected_without_advancing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            client = FakeProtonClient()
            client.write_result = {
                "inbox_preserved": False,
                "destructive_actions": ["move"],
                "mailbox": "Archive",
            }
            console = self._console(root, client)

            with self.assertRaisesRegex(RuntimeError, "safety contract"):
                console.apply_label("101", "personal")

            self.assertEqual(console.state()["current"]["message_id"], "101")

    def test_page_renders_full_context_and_label_only_safety_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_classification_ledger(root)
            page = render_proton_review_page(self._console(root, FakeProtonClient()).state())

            self.assertIn("The complete first message context.", page)
            self.assertIn("Accept EA/Newsletter · Next", page)
            self.assertIn("Change label", page)
            self.assertIn("Apply label · Next", page)
            self.assertNotIn("Keep local suggestion", page)
            self.assertIn("No email will be archived, deleted, moved, or sent", page)

    def test_page_exposes_apply_all_only_when_multiple_labels_are_suggested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "classification.json").write_text(json.dumps({
                "provider": "protonmail",
                "messages": {
                    "101": {
                        "status": "suggested",
                        "internal_labels": ["newsletter", "personal"],
                        "labels": ["EA/Newsletter", "EA/Personal"],
                    },
                },
            }))

            page = render_proton_review_page(self._console(root, FakeProtonClient(message_ids=["101"])).state())

            self.assertIn("Accept EA/Newsletter · Next", page)
            self.assertIn("Apply all 2 suggested labels · Next", page)

    def test_provider_applied_messages_are_completed_and_not_reoffered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "classification.json").write_text(json.dumps({
                "provider": "protonmail",
                "messages": {
                    "101": {
                        "status": "applied",
                        "internal_label": "newsletter",
                        "label": "EA/Newsletter",
                    },
                    "102": {
                        "status": "suggested",
                        "internal_label": "shopping-order",
                        "label": "EA/Orders",
                    },
                },
            }))

            state = self._console(root, FakeProtonClient()).state()

            self.assertEqual(state["remaining_count"], 1)
            self.assertEqual(state["completed_count"], 1)
            self.assertEqual(state["current"]["message_id"], "102")

    def _console(self, root: Path, client: FakeProtonClient) -> ProtonReviewConsole:
        return ProtonReviewConsole(
            proton_client=client,
            classification_ledger_path=root / "classification.json",
            review_state_path=root / "console.json",
        )

    def _wait_for_activity(self, console: ProtonReviewConsole, state: str) -> dict:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            activity = console.companion_write_activity()
            if activity and activity.get("state") == state:
                return activity
            time.sleep(0.01)
        self.fail(f"Proton activity did not reach {state!r}.")

    def _write_classification_ledger(self, root: Path) -> None:
        (root / "classification.json").write_text(json.dumps({
            "provider": "protonmail",
            "account_id": "founder-proton",
            "messages": {
                "101": {
                    "status": "suggested",
                    "sender": "First sender <first@example.test>",
                    "subject": "First subject",
                    "date": "2026-07-16T08:00:00Z",
                    "internal_label": "newsletter",
                    "label": "EA/Newsletter",
                    "reason": "An opted-in editorial digest.",
                    "double_check": {"confidence": 0.42},
                },
                "102": {
                    "status": "suggested",
                    "sender": "Second sender <second@example.test>",
                    "subject": "Second subject",
                    "date": "2026-07-16T09:00:00Z",
                    "internal_label": "shopping-order",
                    "label": "EA/Orders",
                    "reason": "A delivery lifecycle update.",
                    "double_check": {"confidence": 0.55},
                },
            },
        }))


class FakeHandler:
    def __init__(self, command: str, path: str, payload: dict | None = None) -> None:
        raw = json.dumps(payload or {}).encode()
        self.command = command
        self.path = path
        self.headers = {"Content-Length": str(len(raw)), "Content-Type": "application/json"}
        self.rfile = io.BytesIO(raw)
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers: dict[str, str] = {}

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, key: str, value: str) -> None:
        self.response_headers[key] = value

    def end_headers(self) -> None:
        return

    @property
    def body_text(self) -> str:
        return self.wfile.getvalue().decode()


class FakePostHogClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def capture(self, event: str, **kwargs) -> None:
        self.calls.append({"event": event, **kwargs})

    def shutdown(self) -> None:
        return


if __name__ == "__main__":
    unittest.main()
