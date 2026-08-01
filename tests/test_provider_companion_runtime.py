import unittest
from unittest.mock import Mock

from src.provider_companion_runtime import (
    CompanionProviderRuntimes,
    ProviderCompanionRuntime,
)


class ProviderCompanionRuntimeTests(unittest.TestCase):
    def test_registry_routes_supported_payload_shapes_and_defaults_to_gmail(self) -> None:
        gmail = Mock(provider="gmail")
        proton = Mock(provider="protonmail")
        runtimes = CompanionProviderRuntimes([gmail, proton])

        self.assertIs(runtimes.for_provider("gmail"), gmail)
        self.assertIs(runtimes.for_provider("unknown"), gmail)
        self.assertIs(
            runtimes.for_payload({"selected_context": {"provider": "protonmail"}}),
            proton,
        )
        self.assertIs(
            runtimes.for_payload({"preview": {"proposal": {"provider": "protonmail"}}}),
            proton,
        )
        self.assertIs(
            runtimes.for_payload({"preview": {"provider": "protonmail"}}),
            proton,
        )

    def test_delegates_teaching_and_surface_operations(self) -> None:
        workflow = Mock()
        adapter = Mock()
        surface = Mock()
        runtime = ProviderCompanionRuntime(
            provider="gmail",
            workflow=workflow,
            teaching_adapter=adapter,
            surface=surface,
        )
        payload = {"selected_context": {"provider": "gmail"}}
        preview = {"provider": "gmail"}

        runtime.build_preview(payload, include_existing_impact=False)
        runtime.finish_preview_impact(preview)
        runtime.preview_backfill(preview)
        runtime.exclude_match(payload)
        runtime.decide_amendment(payload)
        runtime.apply(payload, defer_provider_write=True)
        runtime.complete_deferred_write("request")
        runtime.sidebar(payload["selected_context"])
        runtime.harness(payload["selected_context"])
        runtime.retry_write()
        runtime.after_apply(payload["selected_context"])
        runtime.after_write()

        workflow.build_preview.assert_called_once_with(
            payload,
            include_existing_impact=False,
        )
        workflow.finish_preview_impact.assert_called_once_with(preview)
        adapter.preview_backfill.assert_called_once_with(preview)
        workflow.exclude_match.assert_called_once_with(payload)
        workflow.decide_amendment.assert_called_once_with(payload)
        workflow.apply.assert_called_once_with(payload, defer_provider_write=True)
        workflow.complete_deferred_write.assert_called_once_with("request")
        surface.sidebar.assert_called_once_with(payload["selected_context"])
        surface.harness.assert_called_once_with(payload["selected_context"])
        surface.retry_write.assert_called_once_with()
        surface.after_apply.assert_called_once_with(payload["selected_context"])
        surface.after_write.assert_called_once_with()

    def test_snapshots_sidebar_before_submitting_when_surface_requires_it(self) -> None:
        calls = []
        surface = Mock()
        surface.snapshot_before_write = True
        surface.sidebar.side_effect = lambda context: calls.append("sidebar") or {"next": True}
        surface.start_write.side_effect = lambda work: calls.append("write")
        runtime = ProviderCompanionRuntime(
            provider="protonmail",
            workflow=Mock(),
            teaching_adapter=Mock(),
            surface=surface,
        )

        snapshot = runtime.submit_deferred_write(lambda: {}, {"provider": "protonmail"})

        self.assertEqual(calls, ["sidebar", "write"])
        self.assertEqual(snapshot, {"next": True})

    def test_submits_without_loading_sidebar_when_snapshot_is_not_required(self) -> None:
        surface = Mock()
        surface.snapshot_before_write = False
        runtime = ProviderCompanionRuntime(
            provider="gmail",
            workflow=Mock(),
            teaching_adapter=Mock(),
            surface=surface,
        )
        work = lambda: {}

        snapshot = runtime.submit_deferred_write(work, {"provider": "gmail"})

        self.assertIsNone(snapshot)
        surface.sidebar.assert_not_called()
        surface.start_write.assert_called_once_with(work)


if __name__ == "__main__":
    unittest.main()
