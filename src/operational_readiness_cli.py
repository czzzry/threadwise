import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.operational_readiness import write_operational_readiness_report


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether the recent multi-inbox classification loop looks operationally stable."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--window", type=int, default=5)
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
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)

    report = write_operational_readiness_report(output_storage_dir, window=args.window)
    summary = report["summary"]
    output.write(f"Overall status: {report['overall_status']}\n")
    output.write(f"Recent runs considered: {summary['run_count']}\n")
    output.write(f"Latest run: {summary.get('latest_run_id', '(missing)')}\n")
    output.write(f"Latest unresolved rate: {summary.get('latest_unresolved_rate', 0) * 100:.2f}%\n")
    output.write(f"Recent average unresolved rate: {summary.get('recent_avg_unresolved_rate', 0) * 100:.2f}%\n")
    output.write(f"Latest queue pending count: {summary.get('latest_queue_pending_count', 0)}\n")
    output.write(f"Latest founder-question count: {summary.get('latest_queue_founder_question_count', 0)}\n")
    output.write(f"Founder applications recorded: {summary.get('founder_application_count', 0)}\n")
    output.write(f"Founder resolved-gain total: {summary.get('founder_resolved_gain_total', 0)}\n")
    progress = report.get("progress", {})
    output.write(
        f"Unresolved progress: {progress.get('unresolved_current_count', 0)}/"
        f"{progress.get('unresolved_target_count', 0)} target unresolved on latest corpus "
        f"(remaining gap {progress.get('unresolved_remaining_gap_count', 0)})\n"
    )
    output.write(
        f"Unresolved progress fraction: {progress.get('unresolved_progress_fraction', 0) * 100:.2f}% "
        f"of the way from worst-seen recent rate to target\n"
    )
    output.write(
        f"Founder questions: {progress.get('founder_question_count', 0)}/"
        f"{progress.get('founder_question_limit', 0)}\n"
    )
    output.write("Reasons:\n")
    for reason in report.get("reasons", []):
        output.write(f"- {reason}\n")
    output.write("Recent runs:\n")
    for run in report.get("runs", []):
        output.write(
            f"- {run['run_id']} | messages={run['message_count']} | unresolved={run['unresolved_count']} "
            f"({run['unresolved_rate'] * 100:.2f}%) | caution={run['caution_count']} "
            f"({run['caution_rate'] * 100:.2f}%) | memory={run['memory_count']} | llm={run['llm_escalation_count']}\n"
        )
    output.write(f"Saved report: {report['report_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
