#!/usr/bin/env python3
"""Validate the complete analytics event contract with synthetic data only."""

import argparse
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.product_analytics import ProductAnalytics  # noqa: E402


SYNTHETIC_DISTINCT_ID = "tw_anon_00000000-0000-4000-8000-000000000001"
COMMON = {
    "app_version": "0.1.0",
    "workflow_version": "gmail-companion-v1",
    "source": "synthetic",
    "synthetic": True,
}
SYNTHETIC_EVENTS = (
    ("extension opened", {**COMMON, "surface": "validation_script"}),
    ("review queue opened", {**COMMON, "queue_size_bucket": "2-5"}),
    (
        "email review started",
        {**COMMON, "queue_size_bucket": "2-5", "review_origin": "needs_attention_queue"},
    ),
    ("suggestion decision made", {**COMMON, "decision_type": "edit", "duration_ms": 1200}),
    (
        "rule confirmed",
        {**COMMON, "rule_scope": "current_email", "affected_count_bucket": "1", "dry_run": True},
    ),
    (
        "label write completed",
        {**COMMON, "rule_scope": "current_email", "write_count_bucket": "1", "retry_count": 0},
    ),
    (
        "label write failed",
        {
            **COMMON,
            "rule_scope": "current_email",
            "error_category": "provider_write_error",
            "retry_count": 0,
        },
    ),
    (
        "label write retried",
        {
            **COMMON,
            "rule_scope": "current_email",
            "retry_count": 1,
            "retry_outcome": "completed",
        },
    ),
    ("review batch completed", {**COMMON, "reviewed_count_bucket": "2-5", "duration_ms": 4200}),
)


class LocalValidationClient:
    def __init__(self) -> None:
        self.events: list[str] = []

    def capture(self, event: str, **_kwargs) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Threadwise PostHog events using synthetic data only.")
    parser.add_argument("--send", action="store_true", help="Send tagged synthetic events to the configured PostHog project.")
    args = parser.parse_args(argv)

    if args.send:
        analytics = ProductAnalytics.from_environment(os.environ)
        if not analytics.enabled or not analytics.synthetic_only:
            parser.error(
                "--send requires THREADWISE_ANALYTICS_ENABLED=true, "
                "THREADWISE_ANALYTICS_ALLOW_SYNTHETIC=true, and THREADWISE_ENVIRONMENT=development."
            )
    else:
        analytics = ProductAnalytics(
            client=LocalValidationClient(),
            environment="development",
            enabled=True,
            synthetic_only=True,
        )

    captured = 0
    for event, properties in SYNTHETIC_EVENTS:
        captured += int(
            analytics.capture(
                distinct_id=SYNTHETIC_DISTINCT_ID,
                event=event,
                properties=properties,
            )
        )
    analytics.shutdown()
    if captured != len(SYNTHETIC_EVENTS):
        raise SystemExit(f"Expected {len(SYNTHETIC_EVENTS)} events, validated {captured}.")
    print(f"Validated {captured} synthetic Threadwise analytics events; no email data was read.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
