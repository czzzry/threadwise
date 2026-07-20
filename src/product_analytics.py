"""Privacy-first PostHog product analytics for Threadwise.

This is the only module allowed to call the PostHog SDK. It accepts a small,
static event vocabulary and rejects every property outside the tracking plan.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Literal, Mapping, Protocol, TypedDict, cast


POSTHOG_EU_HOST = "https://eu.i.posthog.com"
ANALYTICS_WORKFLOW_VERSION = "gmail-companion-v1"

AnalyticsEventName = Literal[
    "extension opened",
    "review queue opened",
    "email review started",
    "suggestion decision made",
    "rule confirmed",
    "label write completed",
    "label write failed",
    "label write retried",
    "review batch completed",
    "teach/fix flow started",
    "teach/fix preview shown",
    "teach/fix completed",
    "teach/fix failed",
    "teach/fix retry clicked",
    "unsubscribe review opened",
    "unsubscribe review completed",
    "proton review opened",
    "proton review completed",
    "proton review failed",
]


class AnalyticsProperties(TypedDict, total=False):
    app_version: str
    workflow_version: str
    source: str
    surface: str
    queue_size_bucket: str
    review_origin: str
    decision_type: str
    rule_scope: str
    affected_count_bucket: str
    write_count_bucket: str
    reviewed_count_bucket: str
    duration_ms: int
    retry_count: int
    dry_run: bool
    error_category: str
    retry_outcome: str
    preview_outcome: str
    flow_outcome: str
    review_outcome: str
    provider_verified: bool
    synthetic: bool


class PostHogClient(Protocol):
    def capture(self, event: str, **kwargs) -> object: ...

    def shutdown(self) -> object: ...


class AnalyticsValidationError(ValueError):
    """Raised when an event does not match the privacy-safe tracking plan."""


@dataclass(frozen=True)
class EventSpec:
    required: frozenset[str]
    optional: frozenset[str] = frozenset()


COMMON_REQUIRED = frozenset({"app_version", "workflow_version", "source"})
COMMON_OPTIONAL = frozenset({"synthetic"})
EVENT_SPECS: dict[str, EventSpec] = {
    "extension opened": EventSpec(COMMON_REQUIRED | {"surface"}, COMMON_OPTIONAL),
    "review queue opened": EventSpec(COMMON_REQUIRED | {"queue_size_bucket"}, COMMON_OPTIONAL),
    "email review started": EventSpec(
        COMMON_REQUIRED | {"queue_size_bucket", "review_origin"}, COMMON_OPTIONAL
    ),
    "suggestion decision made": EventSpec(
        COMMON_REQUIRED | {"decision_type", "duration_ms"}, COMMON_OPTIONAL
    ),
    "rule confirmed": EventSpec(
        COMMON_REQUIRED | {"rule_scope", "affected_count_bucket", "dry_run"}, COMMON_OPTIONAL
    ),
    "label write completed": EventSpec(
        COMMON_REQUIRED | {"rule_scope", "write_count_bucket", "retry_count"}, COMMON_OPTIONAL
    ),
    "label write failed": EventSpec(
        COMMON_REQUIRED | {"rule_scope", "error_category", "retry_count"}, COMMON_OPTIONAL
    ),
    "label write retried": EventSpec(
        COMMON_REQUIRED | {"rule_scope", "retry_count", "retry_outcome"},
        COMMON_OPTIONAL | {"error_category"},
    ),
    "review batch completed": EventSpec(
        COMMON_REQUIRED | {"reviewed_count_bucket", "duration_ms"}, COMMON_OPTIONAL
    ),
    "teach/fix flow started": EventSpec(COMMON_REQUIRED | {"surface"}, COMMON_OPTIONAL),
    "teach/fix preview shown": EventSpec(
        COMMON_REQUIRED | {"surface", "preview_outcome"}, COMMON_OPTIONAL
    ),
    "teach/fix completed": EventSpec(
        COMMON_REQUIRED | {"surface", "flow_outcome"}, COMMON_OPTIONAL
    ),
    "teach/fix failed": EventSpec(
        COMMON_REQUIRED | {"surface", "error_category"}, COMMON_OPTIONAL
    ),
    "teach/fix retry clicked": EventSpec(
        COMMON_REQUIRED | {"surface", "retry_count"}, COMMON_OPTIONAL
    ),
    "unsubscribe review opened": EventSpec(COMMON_REQUIRED | {"surface"}, COMMON_OPTIONAL),
    "unsubscribe review completed": EventSpec(
        COMMON_REQUIRED | {"surface", "reviewed_count_bucket", "review_outcome"}, COMMON_OPTIONAL
    ),
    "proton review opened": EventSpec(
        COMMON_REQUIRED | {"surface", "queue_size_bucket"}, COMMON_OPTIONAL
    ),
    "proton review completed": EventSpec(
        COMMON_REQUIRED | {"surface", "decision_type", "queue_size_bucket", "provider_verified"},
        COMMON_OPTIONAL,
    ),
    "proton review failed": EventSpec(
        COMMON_REQUIRED | {"surface", "decision_type", "error_category"}, COMMON_OPTIONAL
    ),
}

COUNT_BUCKETS = frozenset({"0", "1", "2-5", "6-10", "11-25", "26-50", "51+"})
PROPERTY_ENUMS: dict[str, frozenset[str]] = {
    "workflow_version": frozenset({ANALYTICS_WORKFLOW_VERSION}),
    "source": frozenset({"extension", "companion_service", "retry_cli", "synthetic"}),
    "surface": frozenset({"gmail_companion", "proton_review", "validation_script"}),
    "queue_size_bucket": COUNT_BUCKETS,
    "review_origin": frozenset({"gmail_selected_email", "needs_attention_queue"}),
    "decision_type": frozenset({"approve", "edit", "reject", "open", "looks_right", "add_label"}),
    "rule_scope": frozenset({"current_email", "included_existing", "future_email"}),
    "affected_count_bucket": COUNT_BUCKETS,
    "write_count_bucket": COUNT_BUCKETS,
    "reviewed_count_bucket": COUNT_BUCKETS,
    "error_category": frozenset(
        {
            "gmail_client_initialization",
            "provider_write_error",
            "changed_labels",
            "not_retryable",
            "invalid_request",
            "teaching_model_error",
            "unknown_safe_category",
        }
    ),
    "retry_outcome": frozenset({"completed", "failed", "blocked"}),
    "preview_outcome": frozenset({"ready", "needs_clarification", "failed"}),
    "flow_outcome": frozenset({"completed", "failed"}),
    "review_outcome": frozenset({"saved", "cleared"}),
}

PROHIBITED_KEY_PARTS = frozenset(
    {
        "body",
        "preview_text",
        "subject",
        "sender",
        "recipient",
        "email",
        "message_id",
        "thread_id",
        "oauth",
        "authorization",
        "token",
        "rule_text",
        "model_text",
        "model_output",
        "generated_text",
        "exception",
        "stack",
        "error_message",
    }
)
EMAIL_VALUE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", re.IGNORECASE)
AUTH_VALUE = re.compile(r"\b(?:bearer\s+|ya29\.)", re.IGNORECASE)
RULE_TEXT_VALUE = re.compile(r"\b(?:label|categorize|classify)\s+(?:all|every|messages?|emails?)\b", re.IGNORECASE)
APP_VERSION_VALUE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
ANONYMOUS_ID_VALUE = re.compile(
    r"^tw_anon_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def bucket_count(count: int) -> str:
    value = max(0, int(count))
    if value == 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 5:
        return "2-5"
    if value <= 10:
        return "6-10"
    if value <= 25:
        return "11-25"
    if value <= 50:
        return "26-50"
    return "51+"


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def _validate_distinct_id(distinct_id: str) -> None:
    if not ANONYMOUS_ID_VALUE.fullmatch(distinct_id or ""):
        raise AnalyticsValidationError("distinct_id must be a Threadwise anonymous installation id")


def _validate_property_value(name: str, value: object) -> None:
    if isinstance(value, str):
        if EMAIL_VALUE.search(value) or AUTH_VALUE.search(value) or RULE_TEXT_VALUE.search(value):
            raise AnalyticsValidationError(f"Sensitive value rejected for analytics property {name}")
    if name in PROPERTY_ENUMS and value not in PROPERTY_ENUMS[name]:
        raise AnalyticsValidationError(f"Invalid value for analytics property {name}")
    if name == "app_version" and (not isinstance(value, str) or not APP_VERSION_VALUE.fullmatch(value)):
        raise AnalyticsValidationError("app_version must be a semantic version")
    if name == "duration_ms" and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 86_400_000
    ):
        raise AnalyticsValidationError("duration_ms must be an integer between 0 and 86400000")
    if name == "retry_count" and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 100
    ):
        raise AnalyticsValidationError("retry_count must be an integer between 0 and 100")
    if name in {"dry_run", "synthetic", "provider_verified"} and not isinstance(value, bool):
        raise AnalyticsValidationError(f"{name} must be a boolean")


def validate_event(event: str, properties: Mapping[str, object]) -> AnalyticsEventName:
    spec = EVENT_SPECS.get(event)
    if spec is None:
        raise AnalyticsValidationError(f"Unknown analytics event: {event}")

    keys = set(properties)
    for key in keys:
        normalized = _normalized_key(key)
        if any(part in normalized for part in PROHIBITED_KEY_PARTS):
            raise AnalyticsValidationError(f"Prohibited analytics property: {key}")

    missing = spec.required - keys
    if missing:
        raise AnalyticsValidationError(f"Missing required analytics properties: {', '.join(sorted(missing))}")
    unexpected = keys - spec.required - spec.optional
    if unexpected:
        raise AnalyticsValidationError(f"Unexpected analytics properties: {', '.join(sorted(unexpected))}")

    for name, value in properties.items():
        _validate_property_value(name, value)
    return cast(AnalyticsEventName, event)


class AnonymousDistinctIdStore:
    def __init__(self, storage_dir: Path) -> None:
        self._path = storage_dir / "analytics" / "anonymous_distinct_id.json"

    def get_or_create(self) -> str:
        existing = self._load()
        if existing:
            return existing
        return self.remember(f"tw_anon_{uuid.uuid4()}")

    def remember(self, distinct_id: str) -> str:
        _validate_distinct_id(distinct_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_name(f"{self._path.stem}.{uuid.uuid4().hex}.tmp")
        temporary_path.write_text(json.dumps({"distinct_id": distinct_id}, indent=2) + "\n")
        temporary_path.replace(self._path)
        return distinct_id

    def _load(self) -> str | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text())
            distinct_id = str(payload.get("distinct_id") or "")
            _validate_distinct_id(distinct_id)
            return distinct_id
        except (OSError, ValueError, json.JSONDecodeError, AnalyticsValidationError):
            return None


def _default_client_factory(**kwargs) -> PostHogClient:
    from posthog import Posthog

    project_api_key = kwargs.pop("project_api_key")
    return Posthog(project_api_key, **kwargs)


class ProductAnalytics:
    def __init__(
        self,
        *,
        client: PostHogClient | None = None,
        environment: str = "development",
        enabled: bool = False,
        synthetic_only: bool = False,
    ) -> None:
        self._client = client
        self.environment = environment
        self.enabled = bool(enabled and client is not None)
        self.synthetic_only = synthetic_only
        self._delivery_lock = threading.Lock()
        self._queued_count = 0
        self._last_queued_at: str | None = None
        self._delivery_error_count = 0
        self._last_delivery_error_at: str | None = None

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        client_factory: Callable[..., PostHogClient] | None = None,
    ) -> "ProductAnalytics":
        values = environ or os.environ
        environment = values.get("THREADWISE_ENVIRONMENT", "development").strip().lower()
        requested = values.get("THREADWISE_ANALYTICS_ENABLED", "false").strip().lower() == "true"
        allow_synthetic = (
            values.get("THREADWISE_ANALYTICS_ALLOW_SYNTHETIC", "false").strip().lower() == "true"
        )
        production_enabled = requested and environment == "production"
        synthetic_enabled = requested and allow_synthetic and environment in {"development", "test"}
        token = values.get("POSTHOG_PROJECT_TOKEN", "").strip()
        if not token or not (production_enabled or synthetic_enabled):
            return cls(environment=environment)

        host = values.get("POSTHOG_HOST", POSTHOG_EU_HOST).strip().rstrip("/")
        if host not in {POSTHOG_EU_HOST, "https://us.i.posthog.com"}:
            raise AnalyticsValidationError("POSTHOG_HOST must be an official PostHog Cloud ingestion host")
        factory = client_factory or _default_client_factory
        analytics = cls(
            environment=environment,
            synthetic_only=synthetic_enabled,
        )
        client = factory(
            project_api_key=token,
            host=host,
            enable_exception_autocapture=False,
            disable_geoip=True,
            flush_at=20,
            flush_interval=1,
            on_error=analytics.record_delivery_error,
        )
        analytics._client = client
        analytics.enabled = True
        return analytics

    def record_delivery_error(self, error: object, batch: object) -> None:
        """Record an SDK upload failure without retaining its potentially sensitive payload."""
        del error, batch
        with self._delivery_lock:
            self._delivery_error_count += 1
            self._last_delivery_error_at = datetime.now(UTC).isoformat()

    def delivery_status(self) -> dict[str, object]:
        """Return local SDK health; this deliberately does not claim remote ingestion."""
        with self._delivery_lock:
            if not self.enabled or self._client is None:
                state = "disabled"
            elif self._delivery_error_count:
                state = "degraded"
            elif self._queued_count:
                state = "active"
            else:
                state = "configured"
            return {
                "state": state,
                "configured": bool(self.enabled and self._client is not None),
                "queued_count": self._queued_count,
                "last_queued_at": self._last_queued_at,
                "last_delivery_error_at": self._last_delivery_error_at,
                "error_category": "delivery_error" if self._delivery_error_count else None,
                "assurance": "local_sdk",
            }

    def capture(
        self,
        *,
        distinct_id: str,
        event: AnalyticsEventName | str,
        properties: AnalyticsProperties | Mapping[str, object],
    ) -> bool:
        if not self.enabled or self._client is None:
            return False
        if self.synthetic_only and properties.get("synthetic") is not True:
            return False

        _validate_distinct_id(distinct_id)
        validated_event = validate_event(str(event), properties)
        safe_properties = dict(properties)
        safe_properties["environment"] = self.environment
        safe_properties["$process_person_profile"] = False
        try:
            self._client.capture(
                validated_event,
                distinct_id=distinct_id,
                properties=safe_properties,
                disable_geoip=True,
            )
        except Exception as error:
            self.record_delivery_error(error, [])
            return False
        with self._delivery_lock:
            self._queued_count += 1
            self._last_queued_at = datetime.now(UTC).isoformat()
        return True

    def shutdown(self) -> None:
        if self._client is None:
            return
        try:
            self._client.shutdown()
        except Exception:
            return
