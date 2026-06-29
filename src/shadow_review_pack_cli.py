import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.local_artifacts import shadow_suggestion_memory_path
from src.shadow_review_pack import load_report, write_shadow_review_pack


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a family-level review pack from a stored classifier corpus report."
    )
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--suggestion-memory-path", type=Path)
    parser.add_argument("--max-families-per-provider", type=int, default=6)
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

    report_path = resolve_path(args.report_path, repo_root)
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    suggestion_memory = (
        resolve_path(args.suggestion_memory_path, repo_root)
        if args.suggestion_memory_path is not None
        else shadow_suggestion_memory_path(output_storage_dir)
    )

    pack = write_shadow_review_pack(
        output_storage_dir,
        load_report(report_path),
        suggestion_memory_path=suggestion_memory,
        max_families_per_provider=args.max_families_per_provider,
    )
    summary = pack["summary"]
    output.write(
        f"Built review pack: objective={summary['objective_review_count']} "
        f"| preference={summary['preference_question_count']} "
        f"| taxonomy={summary['taxonomy_question_count']} "
        f"| safety-priority={summary['safety_priority_review_count']} "
        f"| coverage={summary['message_coverage']}\n"
    )
    top_safety_unit = _top_safety_priority_unit(pack)
    if top_safety_unit is not None:
        output.write(
            f"Top safety priority: {top_safety_unit['provider']} | "
            f"{top_safety_unit['sender_key']} | {top_safety_unit['subject_key']} | "
            f"score={top_safety_unit['safety_priority']['priority_score']}\n"
        )
    output.write(f"Saved pack: {pack['pack_path']}\n")
    return 0


def _top_safety_priority_unit(pack: dict) -> dict | None:
    all_units = [
        *pack.get("objective_reviews", []),
        *pack.get("preference_questions", []),
        *pack.get("taxonomy_questions", []),
    ]
    prioritized = [
        unit for unit in all_units
        if unit.get("safety_priority", {}).get("priority_score", 0) > 0
    ]
    if not prioritized:
        return None
    return prioritized[0]


if __name__ == "__main__":
    raise SystemExit(main())
