from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.local_artifacts import load_json_or_default, write_json


LLM_USAGE_SCHEMA_VERSION = 1
COST_BASIS = "estimated_cost_usd_not_billing_truth"


def llm_usage_ledger_path(storage_dir: Path) -> Path:
    return storage_dir / "llm_usage_ledger.json"


def build_llm_usage_event(
    *,
    feature: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    run_id: str,
    timestamp: str | datetime | None = None,
) -> dict:
    return normalize_llm_usage_event(
        {
            "timestamp": _timestamp_iso(timestamp),
            "feature": feature,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "run_id": run_id,
            "cost_is_estimate": True,
        }
    )


def append_llm_usage_event(storage_dir: Path, event: dict) -> dict:
    ledger = load_llm_usage_ledger(storage_dir)
    normalized = normalize_llm_usage_event(event)
    ledger["events"].append(normalized)
    write_json(llm_usage_ledger_path(storage_dir), ledger)
    return normalized


def load_llm_usage_ledger(storage_dir: Path) -> dict:
    payload = load_json_or_default(llm_usage_ledger_path(storage_dir), _empty_ledger())
    if not isinstance(payload, dict):
        raise ValueError("LLM usage ledger must be a JSON object")

    events = payload.get("events", [])
    if not isinstance(events, list):
        raise ValueError("LLM usage ledger events must be a list")

    return {
        "schema_version": int(payload.get("schema_version", LLM_USAGE_SCHEMA_VERSION)),
        "cost_basis": payload.get("cost_basis", COST_BASIS),
        "events": [normalize_llm_usage_event(event) for event in events],
    }


def load_llm_usage_events(storage_dir: Path) -> list[dict]:
    return load_llm_usage_ledger(storage_dir)["events"]


def summarize_llm_usage(events: list[dict]) -> dict:
    summary = {
        "schema_version": LLM_USAGE_SCHEMA_VERSION,
        "cost_basis": COST_BASIS,
        "total": _empty_totals(),
        "by_day": {},
        "by_week": {},
        "by_month": {},
        "by_feature": {},
    }

    for event in [normalize_llm_usage_event(item) for item in events]:
        timestamp = _parse_timestamp(event["timestamp"])
        day_key = timestamp.date().isoformat()
        iso_year, iso_week, _ = timestamp.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        month_key = f"{timestamp.year:04d}-{timestamp.month:02d}"

        _add_event(summary["total"], event)
        _add_event(_bucket(summary["by_day"], day_key), event)
        _add_event(_bucket(summary["by_week"], week_key), event)
        _add_event(_bucket(summary["by_month"], month_key), event)
        _add_event(_bucket(summary["by_feature"], event["feature"]), event)

    return summary


def usage_metadata_for_run(events: list[dict], *, run_id: str, feature: str | None = None) -> dict:
    matching_events = []
    for event in events:
        normalized = normalize_llm_usage_event(event)
        if normalized["run_id"] != run_id:
            continue
        if feature is not None and normalized["feature"] != feature:
            continue
        matching_events.append(normalized)

    totals = summarize_llm_usage(matching_events)["total"]
    return {
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "estimated_cost_usd": totals["estimated_cost_usd"],
        "event_count": totals["event_count"],
        "cost_is_estimate": True,
        "cost_basis": COST_BASIS,
    }


def normalize_llm_usage_event(event: dict) -> dict:
    if not isinstance(event, dict):
        raise ValueError("LLM usage event must be a JSON object")

    return {
        "timestamp": _timestamp_iso(_required(event, "timestamp")),
        "feature": _non_empty_string(event.get("feature"), "feature"),
        "model": _non_empty_string(event.get("model"), "model"),
        "input_tokens": _non_negative_int(event.get("input_tokens"), "input_tokens"),
        "output_tokens": _non_negative_int(event.get("output_tokens"), "output_tokens"),
        "estimated_cost_usd": _non_negative_float(event.get("estimated_cost_usd"), "estimated_cost_usd"),
        "run_id": _non_empty_string(event.get("run_id"), "run_id"),
        "cost_is_estimate": True,
    }


def _empty_ledger() -> dict:
    return {
        "schema_version": LLM_USAGE_SCHEMA_VERSION,
        "cost_basis": COST_BASIS,
        "events": [],
    }


def _empty_totals() -> dict:
    return {
        "event_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def _bucket(buckets: dict[str, dict], key: str) -> dict:
    if key not in buckets:
        buckets[key] = _empty_totals()
    return buckets[key]


def _add_event(totals: dict, event: dict) -> None:
    totals["event_count"] += 1
    totals["input_tokens"] += event["input_tokens"]
    totals["output_tokens"] += event["output_tokens"]
    totals["total_tokens"] += event["input_tokens"] + event["output_tokens"]
    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"] + event["estimated_cost_usd"], 12)


def _required(event: dict, field: str) -> Any:
    if field not in event:
        raise ValueError(f"LLM usage event missing required field: {field}")
    return event[field]


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LLM usage event field must be a non-empty string: {field}")
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"LLM usage event field must be a non-negative integer: {field}")
    return value


def _non_negative_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ValueError(f"LLM usage event field must be a non-negative number: {field}")
    return float(value)


def _timestamp_iso(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        _parse_timestamp(value)
        return value
    raise ValueError("LLM usage event field must be an ISO timestamp: timestamp")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("LLM usage event field must be an ISO timestamp: timestamp") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
