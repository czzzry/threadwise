import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import TextIO


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a weekly inbox report from daily run artifacts."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--end-date", required=True)
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
    storage_dir = _resolve_path(args.storage_dir, repo_root)
    reports_dir = storage_dir / "reports"
    window_end = date.fromisoformat(args.end_date)
    window_start = window_end - timedelta(days=6)

    reports = _load_reports_for_window(reports_dir, args.account_id, window_start, window_end)
    report = _build_weekly_report(args.account_id, window_start, window_end, reports)
    _write_weekly_report(reports_dir, report)
    _print_summary(report, output)
    return 0


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _load_reports_for_window(
    reports_dir: Path,
    account_id: str,
    window_start: date,
    window_end: date,
) -> list[dict]:
    reports: list[dict] = []
    for path in sorted(reports_dir.glob("*_daily_report.json")):
        report = json.loads(path.read_text())
        if report.get("account_id") != account_id:
            continue
        report_date = date.fromisoformat(report["report_date"])
        if window_start <= report_date <= window_end:
            reports.append(report)
    return reports


def _build_weekly_report(
    account_id: str,
    window_start: date,
    window_end: date,
    reports: list[dict],
) -> dict:
    provider = reports[0].get("provider", "gmail") if reports else "gmail"
    label_counts = Counter()
    suggested_label_counts = Counter()
    processed_count = 0
    auto_applied_count = 0
    inbox_removed_count = 0
    classified_count = 0
    unlabeled_count = 0
    daily_trends = []

    for report in sorted(reports, key=lambda item: item["report_date"]):
        processed_count += report.get("processed_count", 0)
        auto_applied_count += report.get("auto_applied_count", 0)
        inbox_removed_count += report.get("inbox_removed_count", 0)
        classified_count += report.get("classified_count", report.get("auto_applied_count", 0))
        unlabeled_count += report.get("unlabeled_count", 0)
        label_counts.update(report.get("label_counts", {}))
        suggested_label_counts.update(report.get("suggested_label_counts", report.get("label_counts", {})))
        daily_trends.append(
            {
                "report_date": report["report_date"],
                "processed_count": report.get("processed_count", 0),
                "auto_applied_count": report.get("auto_applied_count", 0),
                "inbox_removed_count": report.get("inbox_removed_count", 0),
                "classified_count": report.get("classified_count", report.get("auto_applied_count", 0)),
                "unlabeled_count": report.get("unlabeled_count", 0),
            }
        )

    exception_rate = round((unlabeled_count / processed_count), 4) if processed_count else 0.0
    largest_categories = [
        {"label": label, "count": count}
        for label, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]

    return {
        "account_id": account_id,
        "provider": provider,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "processed_count": processed_count,
        "auto_applied_count": auto_applied_count,
        "inbox_removed_count": inbox_removed_count,
        "classified_count": classified_count,
        "unlabeled_count": unlabeled_count,
        "exception_rate": exception_rate,
        "label_counts": dict(sorted(label_counts.items())),
        "suggested_label_counts": dict(sorted(suggested_label_counts.items())),
        "largest_categories": largest_categories,
        "daily_trends": daily_trends,
    }


def _write_weekly_report(reports_dir: Path, report: dict) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / (
        f"{report['account_id']}_weekly_report_{report['window_start']}_{report['window_end']}.json"
    )
    path.write_text(json.dumps(report, indent=2))


def _print_summary(report: dict, output: TextIO) -> None:
    output.write(f"Account: {report['account_id']}\n")
    output.write(f"Window: {report['window_start']} to {report['window_end']}\n")
    output.write(f"Processed: {report['processed_count']}\n")
    output.write(f"Auto-applied: {report['auto_applied_count']}\n")
    output.write(f"INBOX removals: {report['inbox_removed_count']}\n")
    output.write(f"Classified: {report['classified_count']}\n")
    output.write(f"Unlabeled: {report['unlabeled_count']}\n")
    output.write(f"Exception rate: {report['exception_rate'] * 100:.2f}%\n")


if __name__ == "__main__":
    raise SystemExit(main())
