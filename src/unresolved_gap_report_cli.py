import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.unresolved_gap_report import write_unresolved_gap_report


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show the next best actions to close the remaining unresolved gap."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
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

    report = write_unresolved_gap_report(output_storage_dir)
    summary = report["summary"]
    output.write(
        f"Unresolved gap: {summary['current_unresolved_count']}/{summary['target_unresolved_count']} "
        f"target unresolved (remaining gap {summary['remaining_gap_count']})\n"
    )
    output.write(f"Recommended actions: {summary['recommended_action_count']}\n")
    output.write(f"Estimated cumulative gain from listed actions: {summary['recommended_cumulative_gain']}\n")
    output.write("Top actions:\n")
    for action in report.get("recommended_actions", []):
        output.write(
            f"- {action['action_type']} | {action['provider_scope']} | {action['title']} | "
            f"expected gain={action['expected_gain']}\n"
        )
    output.write("Provider hotspots:\n")
    for hotspot in report.get("provider_hotspots", []):
        output.write(f"- {hotspot['provider']} | unresolved={hotspot['unresolved_count']}\n")
        for family in hotspot.get("top_families", [])[:5]:
            output.write(
                f"  - {family['count']} | {family['sender_key']} | {family['top_subject']}\n"
            )
    output.write(f"Saved report: {report['report_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
