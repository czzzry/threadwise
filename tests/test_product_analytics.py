import tempfile
import threading
import unittest
from pathlib import Path

from src.product_analytics import (
    AnalyticsValidationError,
    AnonymousDistinctIdStore,
    ProductAnalytics,
    bucket_count,
)
from src.gmail_companion_ui import GmailCompanionApp


class FakePostHogClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.shutdown_called = False

    def capture(self, event: str, **kwargs) -> None:
        self.calls.append({"event": event, **kwargs})

    def shutdown(self) -> None:
        self.shutdown_called = True


class ProductAnalyticsTests(unittest.TestCase):
    def test_new_async_and_unsubscribe_events_match_the_tracking_plan(self) -> None:
        analytics = ProductAnalytics(client=FakePostHogClient(), environment="production", enabled=True)
        common = {
            "app_version": "0.1.0",
            "workflow_version": "gmail-companion-v1",
            "source": "companion_service",
        }
        events = [
            ("teach/fix flow started", {"surface": "gmail_companion"}),
            ("teach/fix preview shown", {"surface": "gmail_companion", "preview_outcome": "ready"}),
            ("teach/fix completed", {"surface": "gmail_companion", "flow_outcome": "completed"}),
            ("teach/fix failed", {"surface": "gmail_companion", "error_category": "teaching_model_error"}),
            ("teach/fix retry clicked", {"surface": "gmail_companion", "retry_count": 1}),
            ("unsubscribe review opened", {"surface": "gmail_companion"}),
            (
                "unsubscribe review completed",
                {
                    "surface": "gmail_companion",
                    "reviewed_count_bucket": "2-5",
                    "review_outcome": "saved",
                },
            ),
            (
                "proton review opened",
                {"surface": "proton_review", "queue_size_bucket": "11-25"},
            ),
            (
                "proton review completed",
                {
                    "surface": "proton_review",
                    "decision_type": "looks_right",
                    "queue_size_bucket": "6-10",
                    "provider_verified": False,
                },
            ),
            (
                "proton review failed",
                {
                    "surface": "proton_review",
                    "decision_type": "add_label",
                    "error_category": "provider_write_error",
                },
            ),
        ]

        for event, properties in events:
            with self.subTest(event=event):
                self.assertTrue(
                    analytics.capture(
                        distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
                        event=event,
                        properties={**common, **properties},
                    )
                )

    def test_delivery_status_distinguishes_disabled_configured_active_and_degraded(self) -> None:
        disabled = ProductAnalytics(environment="production")
        self.assertEqual(disabled.delivery_status()["state"], "disabled")

        client = FakePostHogClient()
        analytics = ProductAnalytics(client=client, environment="production", enabled=True)
        self.assertEqual(analytics.delivery_status()["state"], "configured")

        analytics.capture(
            distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
            event="extension opened",
            properties={
                "app_version": "0.1.0",
                "workflow_version": "gmail-companion-v1",
                "source": "extension",
                "surface": "gmail_companion",
            },
        )
        self.assertEqual(analytics.delivery_status()["state"], "active")
        self.assertEqual(analytics.delivery_status()["queued_count"], 1)

        analytics.record_delivery_error(RuntimeError("network unavailable"), [])
        degraded = analytics.delivery_status()
        self.assertEqual(degraded["state"], "degraded")
        self.assertEqual(degraded["error_category"], "delivery_error")
        self.assertNotIn("network unavailable", str(degraded))

    def test_environment_client_reports_background_delivery_errors(self) -> None:
        created: list[dict] = []

        def client_factory(**kwargs):
            created.append(kwargs)
            return FakePostHogClient()

        analytics = ProductAnalytics.from_environment(
            {
                "POSTHOG_PROJECT_TOKEN": "phc_local_test_only",
                "POSTHOG_HOST": "https://eu.i.posthog.com",
                "THREADWISE_ANALYTICS_ENABLED": "true",
                "THREADWISE_ENVIRONMENT": "production",
            },
            client_factory=client_factory,
        )

        self.assertEqual(analytics.delivery_status()["state"], "configured")
        created[0]["on_error"](RuntimeError("upload failed"), [{"event": "extension opened"}])
        self.assertEqual(analytics.delivery_status()["state"], "degraded")

    def test_capture_emits_expected_event_with_required_safe_properties(self) -> None:
        client = FakePostHogClient()
        analytics = ProductAnalytics(client=client, environment="production", enabled=True)

        captured = analytics.capture(
            distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
            event="suggestion decision made",
            properties={
                "app_version": "0.1.0",
                "workflow_version": "gmail-companion-v1",
                "source": "extension",
                "decision_type": "edit",
                "duration_ms": 1250,
            },
        )

        self.assertTrue(captured)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["event"], "suggestion decision made")
        self.assertEqual(client.calls[0]["distinct_id"], "tw_anon_12345678-1234-4234-8234-123456789abc")
        self.assertEqual(client.calls[0]["properties"]["environment"], "production")
        self.assertFalse(client.calls[0]["properties"]["$process_person_profile"])

    def test_capture_rejects_missing_required_properties(self) -> None:
        analytics = ProductAnalytics(client=FakePostHogClient(), environment="production", enabled=True)

        with self.assertRaisesRegex(AnalyticsValidationError, "decision_type"):
            analytics.capture(
                distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
                event="suggestion decision made",
                properties={
                    "app_version": "0.1.0",
                    "workflow_version": "gmail-companion-v1",
                    "source": "extension",
                    "duration_ms": 1250,
                },
            )

    def test_capture_rejects_prohibited_property_names(self) -> None:
        analytics = ProductAnalytics(client=FakePostHogClient(), environment="production", enabled=True)
        base = {
            "app_version": "0.1.0",
            "workflow_version": "gmail-companion-v1",
            "source": "extension",
            "surface": "gmail_companion",
        }

        for property_name in (
            "subject",
            "sender_email",
            "recipient",
            "message_id",
            "thread_id",
            "oauth_token",
            "rule_text",
            "model_output",
            "exception",
        ):
            with self.subTest(property_name=property_name):
                with self.assertRaises(AnalyticsValidationError):
                    analytics.capture(
                        distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
                        event="extension opened",
                        properties={**base, property_name: "sensitive"},
                    )

    def test_capture_rejects_representative_sensitive_values_even_under_safe_keys(self) -> None:
        analytics = ProductAnalytics(client=FakePostHogClient(), environment="production", enabled=True)
        base = {
            "app_version": "0.1.0",
            "workflow_version": "gmail-companion-v1",
            "source": "extension",
        }
        sensitive_values = (
            "person@example.com",
            "Bearer ya29.a0ARrdaM-secret",
            "Please label every invoice from Alice as finance",
        )

        for sensitive_value in sensitive_values:
            with self.subTest(sensitive_value=sensitive_value):
                with self.assertRaises(AnalyticsValidationError):
                    analytics.capture(
                        distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
                        event="label write failed",
                        properties={
                            **base,
                            "rule_scope": "current_email",
                            "error_category": sensitive_value,
                            "retry_count": 0,
                        },
                    )

    def test_development_and_test_are_disabled_without_explicit_synthetic_mode(self) -> None:
        created_clients: list[dict] = []

        def client_factory(**kwargs):
            created_clients.append(kwargs)
            return FakePostHogClient()

        for environment in ("development", "test"):
            with self.subTest(environment=environment):
                analytics = ProductAnalytics.from_environment(
                    {
                        "POSTHOG_PROJECT_TOKEN": "phc_local_test_only",
                        "POSTHOG_HOST": "https://eu.i.posthog.com",
                        "THREADWISE_ANALYTICS_ENABLED": "true",
                        "THREADWISE_ENVIRONMENT": environment,
                    },
                    client_factory=client_factory,
                )
                self.assertFalse(analytics.enabled)

        self.assertEqual(created_clients, [])

    def test_synthetic_mode_only_accepts_synthetic_events(self) -> None:
        client = FakePostHogClient()
        analytics = ProductAnalytics(
            client=client,
            environment="development",
            enabled=True,
            synthetic_only=True,
        )
        properties = {
            "app_version": "0.1.0",
            "workflow_version": "gmail-companion-v1",
            "source": "synthetic",
            "surface": "validation_script",
        }

        self.assertFalse(
            analytics.capture(
                distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
                event="extension opened",
                properties=properties,
            )
        )
        self.assertTrue(
            analytics.capture(
                distinct_id="tw_anon_12345678-1234-4234-8234-123456789abc",
                event="extension opened",
                properties={**properties, "synthetic": True},
            )
        )
        self.assertEqual(len(client.calls), 1)

    def test_anonymous_distinct_id_is_stable_and_accepts_extension_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AnonymousDistinctIdStore(Path(temp_dir))
            generated = store.get_or_create()
            self.assertEqual(store.get_or_create(), generated)

            extension_id = "tw_anon_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            self.assertEqual(store.remember(extension_id), extension_id)
            self.assertEqual(store.get_or_create(), extension_id)

            with self.assertRaises(AnalyticsValidationError):
                store.remember("person@example.com")

    def test_anonymous_distinct_id_remember_tolerates_concurrent_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AnonymousDistinctIdStore(Path(temp_dir))
            distinct_ids = [
                "tw_anon_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "tw_anon_bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            ]
            failures: list[Exception] = []

            def remember(distinct_id: str) -> None:
                try:
                    store.remember(distinct_id)
                except Exception as exc:  # pragma: no cover - captured for assertion
                    failures.append(exc)

            threads = [threading.Thread(target=remember, args=(distinct_id,)) for distinct_id in distinct_ids]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(failures, [])
            self.assertIn(store.get_or_create(), distinct_ids)

    def test_bucket_count_has_bounded_low_cardinality_values(self) -> None:
        self.assertEqual(bucket_count(0), "0")
        self.assertEqual(bucket_count(1), "1")
        self.assertEqual(bucket_count(3), "2-5")
        self.assertEqual(bucket_count(12), "11-25")
        self.assertEqual(bucket_count(100), "51+")

    def test_authoritative_companion_write_outcomes_emit_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = FakePostHogClient()
            analytics = ProductAnalytics(client=client, environment="production", enabled=True)
            app = GmailCompanionApp(Path(temp_dir), analytics=analytics)

            app._capture_label_write_outcomes(
                "tw_anon_12345678-1234-4234-8234-123456789abc",
                "apply-included",
                {
                    "mode": "applied",
                    "messages_written": 2,
                    "label_write_failed": 1,
                },
            )

        self.assertEqual(
            [call["event"] for call in client.calls],
            ["label write completed", "label write failed"],
        )
        self.assertEqual(client.calls[0]["properties"]["write_count_bucket"], "2-5")
        self.assertEqual(client.calls[1]["properties"]["error_category"], "provider_write_error")

    def test_companion_health_and_harness_expose_analytics_delivery_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            analytics = ProductAnalytics(
                client=FakePostHogClient(),
                environment="production",
                enabled=True,
            )
            app = GmailCompanionApp(Path(temp_dir), analytics=analytics)

            self.assertEqual(app.health_status()["analytics"]["state"], "configured")
            self.assertEqual(app.harness_state(None)["analytics_status"]["state"], "configured")


if __name__ == "__main__":
    unittest.main()
