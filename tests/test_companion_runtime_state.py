import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.companion_runtime_state import CompanionRuntimeState
from src.handled_review_store import HandledReviewStore
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore


class CompanionRuntimeStateTests(unittest.TestCase):
    def test_rapid_gmail_accepts_share_one_serial_background_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            calls: list[str] = []
            runtime = _runtime(Path(temp_dir), background_runner=queued.append)

            runtime.start_teaching_write(lambda: calls.append("first") or {})
            runtime.start_teaching_write(lambda: calls.append("second") or {})

            self.assertEqual(len(queued), 1)
            self.assertEqual(runtime._provider_write_status()["state"], "working")
            queued[0]()

            self.assertEqual(calls, ["first", "second"])
            self.assertEqual(runtime._provider_write_status()["state"], "done")

    def test_sidebar_snapshot_caches_local_inputs_until_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_dir = Path(temp_dir)
            runtime = _runtime(storage_dir)
            selected = {"provider": "gmail", "message_id": "message-1"}

            with (
                patch(
                    "src.companion_runtime_state.build_selected_email_state",
                    return_value={"found": True, "message_id": "message-1"},
                ) as selected_state,
                patch(
                    "src.companion_runtime_state.build_daily_summary",
                    return_value={"processed_count": 3},
                ) as daily_summary,
            ):
                first = runtime.sidebar(selected)
                second = runtime.sidebar(selected)
                runtime.invalidate()
                third = runtime.sidebar(selected)

            self.assertEqual(first["selected_email"]["message_id"], "message-1")
            self.assertEqual(second["daily_summary"]["processed_count"], 3)
            self.assertEqual(third["contract_version"], "gmail-companion-sidebar-v1")
            self.assertEqual(selected_state.call_count, 3)
            self.assertEqual(daily_summary.call_count, 2)

    def test_teaching_refresh_has_deterministic_working_then_done_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            runtime = _runtime(Path(temp_dir), background_runner=queued.append)
            selected = {"provider": "gmail", "message_id": "message-1"}

            with (
                patch(
                    "src.companion_runtime_state.build_selected_email_state",
                    return_value={"found": False},
                ),
                patch(
                    "src.companion_runtime_state.build_daily_summary",
                    return_value={},
                ),
                patch(
                    "src.companion_runtime_state.build_companion_runtime_payload",
                    return_value={"items": [], "daily_summary": {}},
                ),
            ):
                runtime.start_teaching_refresh(selected)
                self.assertEqual(runtime.sidebar(selected)["ui_state"]["async_follow_up"]["state"], "working")
                self.assertEqual(len(queued), 1)
                queued[0]()
                refreshed = runtime.harness(selected)

            self.assertEqual(refreshed["sidebar_state"]["ui_state"]["async_follow_up"]["state"], "done")
            self.assertEqual(refreshed["recent_items"], [])

    def test_runtime_payload_reconciles_live_inbox_ids_in_background(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            live_ids = Mock(return_value={"still-in-inbox"})
            runtime = _runtime(
                Path(temp_dir),
                background_runner=queued.append,
                live_inbox_ids_loader=live_ids,
            )

            with patch(
                "src.companion_runtime_state.build_companion_runtime_payload",
                return_value={"items": []},
            ) as build_runtime:
                runtime.runtime_payload()
                runtime.runtime_payload()
                self.assertEqual(len(queued), 1)
                live_ids.assert_not_called()
                self.assertIsNone(
                    build_runtime.call_args.kwargs["allowed_review_message_ids"]
                )

                queued[0]()
                runtime.runtime_payload()

            live_ids.assert_called_once_with()
            self.assertEqual(
                build_runtime.call_args.kwargs["allowed_review_message_ids"],
                {"still-in-inbox"},
            )

    def test_failed_live_inbox_reconciliation_does_not_block_first_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            runtime = _runtime(
                Path(temp_dir),
                background_runner=queued.append,
                live_inbox_ids_loader=Mock(side_effect=RuntimeError("provider unavailable")),
            )

            with patch(
                "src.companion_runtime_state.build_companion_runtime_payload",
                return_value={"items": []},
            ) as build_runtime:
                self.assertEqual(runtime.runtime_payload(), {"items": []})
                self.assertEqual(len(queued), 1)
                queued[0]()
                self.assertEqual(runtime.runtime_payload(), {"items": []})

            self.assertIsNone(
                build_runtime.call_args.kwargs["allowed_review_message_ids"]
            )

    def test_unchanged_unknown_reconciliation_preserves_cached_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            runtime = _runtime(
                Path(temp_dir),
                background_runner=queued.append,
                live_inbox_ids_loader=Mock(return_value=None),
            )
            selected = {"provider": "gmail", "message_id": "message-1"}

            with (
                patch(
                    "src.companion_runtime_state.build_companion_runtime_payload",
                    return_value={"items": []},
                ) as build_runtime,
                patch(
                    "src.companion_runtime_state.build_selected_email_state",
                    return_value={"found": False},
                ),
                patch(
                    "src.companion_runtime_state.build_daily_summary",
                    return_value={},
                ),
            ):
                first = runtime.harness(selected)
                queued.pop(0)()
                second = runtime.harness(selected)

            self.assertEqual(first["recent_items"], [])
            self.assertEqual(second["recent_items"], [])
            build_runtime.assert_called_once_with(
                Path(temp_dir),
                provider="gmail",
                allowed_review_message_ids=None,
            )

    def test_reconciliation_finishing_during_first_build_cannot_cache_stale_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            runtime = _runtime(
                Path(temp_dir),
                background_runner=queued.append,
                live_inbox_ids_loader=Mock(return_value={"still-in-inbox"}),
            )
            allowed_ids: list[set[str] | None] = []

            def build_runtime(*args, **kwargs):
                del args
                allowed_ids.append(kwargs["allowed_review_message_ids"])
                if len(allowed_ids) == 1:
                    queued.pop(0)()
                return {"items": []}

            with patch(
                "src.companion_runtime_state.build_companion_runtime_payload",
                side_effect=build_runtime,
            ):
                runtime.runtime_payload()
                runtime.runtime_payload()

            self.assertEqual(allowed_ids, [None, {"still-in-inbox"}])

    def test_teaching_refresh_failure_surfaces_retry_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            runtime = _runtime(Path(temp_dir), background_runner=queued.append)
            runtime.start_teaching_refresh({})

            with patch.object(runtime, "invalidate", side_effect=RuntimeError("timeout")):
                queued[0]()
            with (
                patch(
                    "src.companion_runtime_state.build_selected_email_state",
                    return_value={"found": False},
                ),
                patch(
                    "src.companion_runtime_state.build_daily_summary",
                    return_value={},
                ),
            ):
                state = runtime.sidebar({})

            activity = state["ui_state"]["activity_feed"][0]
            self.assertEqual(activity["state"], "retry")
            self.assertIn("timeout", activity["message"])

    def test_gmail_setup_failure_surfaces_provider_retry_in_sidebar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            queued: list = []
            runtime = _runtime(Path(temp_dir), background_runner=queued.append)
            runtime.start_teaching_write(
                lambda: {
                    "mode": "gmail-write-failed",
                    "error": "Gmail client secret is unavailable",
                    "label_write_failed": 0,
                    "inbox_remove_failed": 0,
                }
            )
            queued.pop(0)()

            with (
                patch(
                    "src.companion_runtime_state.build_selected_email_state",
                    return_value={"found": False},
                ),
                patch(
                    "src.companion_runtime_state.build_daily_summary",
                    return_value={},
                ),
            ):
                state = runtime.sidebar({})

            provider_write = state["ui_state"]["provider_write"]
            activity = state["ui_state"]["activity_feed"][0]
            self.assertEqual(provider_write["state"], "error")
            self.assertEqual(activity["action"], "retry-provider-write")
            self.assertEqual(activity["action_label"], "Try again")
            self.assertNotEqual(activity["label"], "Gmail labels applied")


def _runtime(
    storage_dir: Path,
    *,
    background_runner=None,
    live_inbox_ids_loader=None,
) -> CompanionRuntimeState:
    return CompanionRuntimeState(
        storage_dir,
        unsubscribe_store=UnsubscribeInventoryStore(storage_dir),
        handled_review_store=HandledReviewStore(storage_dir),
        analytics_status=lambda: {"state": "disabled"},
        live_inbox_ids_loader=live_inbox_ids_loader or (lambda: None),
        background_runner=background_runner,
    )


if __name__ == "__main__":
    unittest.main()
