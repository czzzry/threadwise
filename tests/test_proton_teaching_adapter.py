from __future__ import annotations

import unittest

from src.companion_teaching_workflow import TeachingWriteRequest
from src.proton_teaching_adapter import ProtonTeachingAdapter


class FakeConsole:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def apply_companion_label(self, message_id: str, internal_label: str) -> dict:
        self.calls.append((message_id, internal_label))
        return {"provider_verified": True, "inbox_preserved": True}

    def live_message_ids(self) -> set[str]:
        return {"message-1", "message-2"}


class ProtonTeachingAdapterTests(unittest.TestCase):
    def test_current_email_uses_verified_proton_write(self) -> None:
        console = FakeConsole()
        adapter = ProtonTeachingAdapter(lambda: console)

        summary = adapter.apply(self._request())

        self.assertEqual(console.calls, [("message-1", "personal")])
        self.assertEqual(summary["provider"], "protonmail")
        self.assertEqual(summary["messages_written"], 1)
        self.assertEqual(summary["label_write_failed"], 0)

    def test_apply_included_deduplicates_current_and_matching_messages(self) -> None:
        console = FakeConsole()
        adapter = ProtonTeachingAdapter(lambda: console)

        summary = adapter.apply(self._request(
            mode="apply-included",
            included_message_ids=frozenset({"message-1", "message-2"}),
        ))

        self.assertEqual(
            console.calls,
            [("message-1", "personal"), ("message-2", "personal")],
        )
        self.assertEqual(summary["messages_written"], 2)

    def test_future_rule_does_not_write_to_proton(self) -> None:
        console = FakeConsole()
        adapter = ProtonTeachingAdapter(lambda: console)

        summary = adapter.apply(self._request(mode="save-future-rule"))

        self.assertEqual(console.calls, [])
        self.assertEqual(summary["mode"], "no-gmail-write-future-rule-only")

    def test_preview_backfill_excludes_messages_no_longer_in_live_inbox(self) -> None:
        console = FakeConsole()
        adapter = ProtonTeachingAdapter(lambda: console)

        result = adapter.preview_backfill({
            "impact": {
                "matching_existing_items": [
                    {"message_id": "message-1"},
                    {"message_id": "deleted-message"},
                ],
            },
        })

        self.assertEqual(result["estimated_count"], 1)
        self.assertEqual(result["matches"], [{"message_id": "message-1"}])

    def _request(self, **overrides) -> TeachingWriteRequest:
        values = {
            "account_id": "founder-proton",
            "current_message_id": "message-1",
            "mode": "current-only",
            "preview_matches": [],
            "semantic_rule": {"target_label": "personal"},
            "current_subject": "Subject",
            "current_sender": "sender@example.test",
            "included_message_ids": frozenset(),
            "provider": "protonmail",
        }
        values.update(overrides)
        return TeachingWriteRequest(**values)


if __name__ == "__main__":
    unittest.main()
