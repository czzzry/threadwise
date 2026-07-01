from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, write_json


GMAIL_DASHBOARD_RUN_STATUS_SCHEMA_VERSION = 1
GMAIL_DASHBOARD_RUN_CONFIRMATION = "true"


def gmail_dashboard_run_status_path(storage_dir: Path) -> Path:
    return storage_dir / "gmail_dashboard_run_status.json"


def load_gmail_dashboard_run_status(storage_dir: Path) -> dict:
    payload = load_json_or_default(gmail_dashboard_run_status_path(storage_dir), {})
    if not isinstance(payload, dict) or not payload:
        return idle_gmail_dashboard_run_status()
    payload.setdefault("schema_version", GMAIL_DASHBOARD_RUN_STATUS_SCHEMA_VERSION)
    payload.setdefault("status", "idle")
    payload.setdefault("dashboard_path", "/daily-dashboard#run-gmail-check")
    return payload


def write_gmail_dashboard_run_status(storage_dir: Path, status: dict) -> dict:
    payload = {
        "schema_version": GMAIL_DASHBOARD_RUN_STATUS_SCHEMA_VERSION,
        "dashboard_path": "/daily-dashboard#run-gmail-check",
        **status,
    }
    write_json(gmail_dashboard_run_status_path(storage_dir), payload)
    return payload


def trigger_dashboard_gmail_check(
    storage_dir: Path,
    payload: dict,
    runner,
    *,
    now: datetime | None = None,
) -> dict:
    if str(payload.get("confirmed", "")).lower() != GMAIL_DASHBOARD_RUN_CONFIRMATION:
        raise ValueError("Confirm the Gmail check before starting a run.")
    current = load_gmail_dashboard_run_status(storage_dir)
    if current.get("status") == "running":
        raise ValueError("A Gmail check is already running.")

    timestamp = (now or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    run_id = f"dashboard-gmail-check-{timestamp.replace(':', '').replace('.', '-')}"
    runner_payload = build_runner_payload(payload, run_id)
    write_gmail_dashboard_run_status(
        storage_dir,
        {
            "status": "running",
            "run_id": run_id,
            "started_at": timestamp,
            "account_id": runner_payload["account_id"],
            "batch_size": runner_payload["batch_size"],
            "safety_boundaries": runner_payload["safety_boundaries"],
        },
    )
    try:
        result = runner(runner_payload)
    except Exception as exc:
        write_gmail_dashboard_run_status(
            storage_dir,
            {
                "status": "failed",
                "run_id": run_id,
                "started_at": timestamp,
                "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "account_id": runner_payload["account_id"],
                "batch_size": runner_payload["batch_size"],
                "error": str(exc),
                "safety_boundaries": runner_payload["safety_boundaries"],
            },
        )
        raise

    saved = write_gmail_dashboard_run_status(
        storage_dir,
        {
            "status": "succeeded",
            "run_id": run_id,
            "started_at": timestamp,
            "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "account_id": runner_payload["account_id"],
            "batch_size": runner_payload["batch_size"],
            "result": summarize_run_result(result),
            "safety_boundaries": runner_payload["safety_boundaries"],
        },
    )
    return saved


def build_runner_payload(payload: dict, run_id: str) -> dict:
    return {
        "run_id": run_id,
        "account_id": (payload.get("account_id") or "").strip(),
        "batch_size": int(payload.get("batch_size") or 50),
        "safety_boundaries": {
            "label_writes": "existing_safe_ea_labels_only",
            "inbox_removal": "approved_low_value_categories_only",
            "attention_gmail_mutation": "none",
            "llm_attention": "may_call_llm_when_configured",
        },
    }


def summarize_run_result(result) -> dict:
    if result is None:
        return {
            "outcome": "no_new_messages",
            "batch_id": "",
            "fetched_count": 0,
            "label_write_count": 0,
            "inbox_removal_count": 0,
            "unlabeled_exception_count": 0,
        }
    return {
        "outcome": "completed",
        "batch_id": getattr(result, "batch_id", ""),
        "fetched_count": getattr(result, "fetched_count", 0),
        "label_write_count": getattr(result, "label_write_count", 0),
        "inbox_removal_count": getattr(result, "inbox_removal_count", 0),
        "unlabeled_exception_count": len(getattr(result, "unlabeled_exceptions", []) or []),
    }


def idle_gmail_dashboard_run_status() -> dict:
    return {
        "schema_version": GMAIL_DASHBOARD_RUN_STATUS_SCHEMA_VERSION,
        "status": "idle",
        "dashboard_path": "/daily-dashboard#run-gmail-check",
    }
