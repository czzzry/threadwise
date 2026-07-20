import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.local_artifacts import (
    batch_path,
    inbox_removal_status_path,
    load_json,
    reports_dir,
    write_status_path,
)


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
UNLABELED_THRESHOLD = 5
EXCEPTION_RATE_THRESHOLD = 0.10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether a Gmail daily run still satisfies the current readiness policy."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--batch-id")
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    cwd: Path | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output = stdout or sys.stdout
    repo_root = cwd or Path.cwd()
    storage_dir = resolve_path(args.storage_dir, repo_root)

    matching_reports = _load_reports(storage_dir, args.account_id)
    report = _select_report(matching_reports, args.batch_id)
    if report is None:
        output.write("No Gmail daily reports found for that account.\n")
        return 1

    status = _evaluate_report(storage_dir, matching_reports, report)
    output.write(f"Status: {status}\n")
    output.write(f"Batch: {report['batch_id']}\n")
    output.write(f"Report date: {report['report_date']}\n")
    output.write(f"Processed: {report['processed_count']}\n")
    output.write(f"Unlabeled exceptions: {report['unlabeled_count']}\n")
    output.write(f"Exception rate: {_exception_rate(report) * 100:.2f}%\n")
    return 0


def _load_reports(storage_dir: Path, account_id: str) -> list[dict]:
    matching_reports = []
    for path in sorted(reports_dir(storage_dir).glob("*_daily_report.json")):
        report = load_json(path)
        if report.get("provider") != "gmail" or report.get("account_id") != account_id:
            continue
        matching_reports.append(report)
    return sorted(matching_reports, key=lambda report: (report["report_date"], report["batch_id"]))


def _select_report(matching_reports: list[dict], batch_id: str | None) -> dict | None:
    if batch_id is not None:
        for report in matching_reports:
            if report.get("batch_id") == batch_id:
                return report
        return None

    if not matching_reports:
        return None

    return matching_reports[-1]


def _evaluate_report(storage_dir: Path, matching_reports: list[dict], report: dict) -> str:
    batch_file = batch_path(storage_dir, report["batch_id"])
    write_status_file = write_status_path(storage_dir, report["batch_id"])
    inbox_status_file = inbox_removal_status_path(storage_dir, report["batch_id"])

    if not batch_file.exists():
        return "PAUSE"
    if not write_status_file.exists():
        return "PAUSE"
    if not inbox_status_file.exists():
        return "PAUSE"

    if _has_inbox_removal_policy_violation(
        load_json(batch_file),
        load_json(write_status_file),
        load_json(inbox_status_file),
    ):
        return "PAUSE"

    if _report_exceeds_threshold(report) and _previous_report_exceeded_threshold(matching_reports, report):
        return "PAUSE"
    if _report_exceeds_threshold(report):
        return "WARN"
    return "PASS"


def _exception_rate(report: dict) -> float:
    processed_count = report.get("processed_count", 0)
    if not processed_count:
        return 0.0
    return report.get("unlabeled_count", 0) / processed_count


def _report_exceeds_threshold(report: dict) -> bool:
    return (
        report.get("unlabeled_count", 0) > UNLABELED_THRESHOLD
        or _exception_rate(report) > EXCEPTION_RATE_THRESHOLD
    )


def _previous_report_exceeded_threshold(matching_reports: list[dict], report: dict) -> bool:
    report_index = next(
        (index for index, candidate in enumerate(matching_reports) if candidate["batch_id"] == report["batch_id"]),
        None,
    )
    if report_index is None or report_index == 0:
        return False
    return _report_exceeds_threshold(matching_reports[report_index - 1])


def _has_inbox_removal_policy_violation(batch: dict, write_status: dict, inbox_status: dict) -> bool:
    items_by_id = {item["message_id"]: item for item in batch.get("items", [])}
    allowed_labels = {"spam-low-value", "promotions"}

    for message_id, status in inbox_status.items():
        if status != "applied":
            continue
        item = items_by_id.get(message_id)
        if item is None:
            return True
        final_labels = set(item.get("final_labels") or [])
        if not final_labels.intersection(allowed_labels):
            return True
        if write_status.get(message_id) != "applied":
            return True

    return False


if __name__ == "__main__":
    raise SystemExit(main())
