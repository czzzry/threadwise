import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return load_json(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def batch_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / "batches" / f"{batch_id}.json"


def reports_dir(storage_dir: Path) -> Path:
    return storage_dir / "reports"


def daily_report_path(storage_dir: Path, batch_id: str) -> Path:
    return reports_dir(storage_dir) / f"{batch_id}_daily_report.json"


def weekly_report_path(storage_dir: Path, account_id: str, window_start: str, window_end: str) -> Path:
    return reports_dir(storage_dir) / f"{account_id}_weekly_report_{window_start}_{window_end}.json"


def evaluations_dir(storage_dir: Path) -> Path:
    return storage_dir / "evaluations"


def evaluation_report_path(storage_dir: Path, evaluation_id: str) -> Path:
    return evaluations_dir(storage_dir) / f"{evaluation_id}.json"


def evaluation_preferences_path(storage_dir: Path, evaluation_id: str) -> Path:
    return evaluations_dir(storage_dir) / f"{evaluation_id}-preferences.json"


def write_status_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_write_status.json"


def write_attempts_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_write_attempts.json"


def inbox_removal_status_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_inbox_removal_status.json"


def inbox_removal_attempts_path(storage_dir: Path, batch_id: str) -> Path:
    return storage_dir / f"{batch_id}_inbox_removal_attempts.json"


def unsubscribe_selections_path(storage_dir: Path) -> Path:
    return storage_dir / "unsubscribe_selections.json"


def unsubscribe_execution_audit_path(storage_dir: Path) -> Path:
    return storage_dir / "unsubscribe_execution_audit.json"
