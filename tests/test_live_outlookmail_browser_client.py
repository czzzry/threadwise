import unittest
from datetime import UTC, datetime

from src.live_outlookmail_browser_client import LiveOutlookMailBrowserClient, SetupError


class LiveOutlookMailBrowserClientTests(unittest.TestCase):
    def test_list_messages_reads_visible_inbox_rows_from_signed_in_browser(self) -> None:
        rows = [
            {
                "message_id": "row-001",
                "conversation_id": "conv-001",
                "aria_label": "Unread Microsoft account team Microsoft account security info was added 3:19 PM ...",
                "lines": [
                    "MT",
                    "Microsoft account team",
                    "Microsoft account security info was added",
                    "Microsoft account Security info was added",
                    "3:19 PM",
                ],
            },
            {
                "message_id": "row-002",
                "conversation_id": "conv-002",
                "aria_label": "Unread Microsoft Updates to our terms of use 2025-09-04 ...",
                "lines": [
                    "M",
                    "Microsoft",
                    "Updates to our terms of use",
                    "Hello, You're receiving this email because we are updating...",
                    "2025-09-04",
                ],
            },
        ]
        client = LiveOutlookMailBrowserClient(
            target_lister=lambda: [{"url": "https://outlook.live.com/mail/0/", "webSocketDebuggerUrl": "ws://outlook"}],
            row_loader=lambda ws_url, limit: rows[:limit],
            now_fn=lambda: datetime(2026, 6, 27, 16, 0, tzinfo=UTC),
        )

        message_ids = client.list_messages(max_results=2)
        first_message = client.get_message("row-001")
        second_message = client.get_message("row-002")

        self.assertEqual(message_ids, ["row-001", "row-002"])
        self.assertEqual(first_message["sender"], "Microsoft account team")
        self.assertEqual(first_message["subject"], "Microsoft account security info was added")
        self.assertEqual(first_message["body"], "Microsoft account Security info was added")
        self.assertEqual(first_message["date"], "2026-06-27T15:19:00Z")
        self.assertEqual(second_message["date"], "2025-09-04T00:00:00Z")

    def test_list_messages_raises_clear_error_when_no_outlook_tab_exists(self) -> None:
        client = LiveOutlookMailBrowserClient(target_lister=lambda: [])

        with self.assertRaisesRegex(SetupError, "No signed-in Outlook inbox tab"):
            client.list_messages(max_results=5)

    def test_get_message_raises_when_message_not_cached(self) -> None:
        client = LiveOutlookMailBrowserClient(
            target_lister=lambda: [{"url": "https://outlook.live.com/mail/0/", "webSocketDebuggerUrl": "ws://outlook"}],
            row_loader=lambda ws_url, limit: [],
        )

        with self.assertRaisesRegex(SetupError, "Run list_messages first"):
            client.get_message("missing-row")
