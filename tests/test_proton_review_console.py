from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path

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
            self.assertIn("Looks right · Next", page)
            self.assertIn("Add label · Next", page)
            self.assertIn("No email will be archived, deleted, moved, or sent", page)

    def _console(self, root: Path, client: FakeProtonClient) -> ProtonReviewConsole:
        return ProtonReviewConsole(
            proton_client=client,
            classification_ledger_path=root / "classification.json",
            review_state_path=root / "console.json",
        )

    def _write_classification_ledger(self, root: Path) -> None:
        (root / "classification.json").write_text(json.dumps({
            "provider": "protonmail",
            "messages": {
                "101": {
                    "status": "applied",
                    "internal_label": "newsletter",
                    "label": "EA/Newsletter",
                    "reason": "An opted-in editorial digest.",
                    "double_check": {"confidence": 0.42},
                },
                "102": {
                    "status": "applied",
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
