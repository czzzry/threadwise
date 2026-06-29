import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.cluster_decision_pack import load_frontier_plan, write_cluster_decision_pack


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a memory-ready cluster decision pack from a frontier compression plan."
    )
    parser.add_argument("--plan-path", type=Path, required=True)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--auto-low-value-limit", type=int, default=8)
    parser.add_argument("--safety-review-limit", type=int, default=8)
    parser.add_argument("--personal-review-limit", type=int, default=8)
    parser.add_argument("--preference-review-limit", type=int, default=8)
    parser.add_argument("--unclear-review-limit", type=int, default=8)
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

    plan_path = resolve_path(args.plan_path, repo_root)
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    pack = write_cluster_decision_pack(
        output_storage_dir,
        load_frontier_plan(plan_path),
        lane_limits={
            "auto_low_value_clusters": args.auto_low_value_limit,
            "safety_review_clusters": args.safety_review_limit,
            "personal_review_clusters": args.personal_review_limit,
            "preference_review_clusters": args.preference_review_limit,
            "unclear_clusters": args.unclear_review_limit,
        },
    )
    summary = pack["summary"]
    output.write(
        f"Built cluster decision pack: units={summary['decision_unit_count']} "
        f"| messages={summary['message_coverage']} | families={summary['family_coverage']}\n"
    )
    output.write(
        f"Policy={summary['auto_low_value_count'] + summary['personal_review_count']} | "
        f"Safety={summary['safety_review_count']} | Preference={summary['preference_review_count']} | "
        f"Unclear={summary['unclear_review_count']} | "
        f"Safety-priority={summary['safety_priority_review_count']}\n"
    )
    top_safety = pack.get("safety_reviews", [])
    prioritized_safety = [unit for unit in top_safety if unit["safety_priority"]["priority_score"] > 0]
    if prioritized_safety:
        unit = prioritized_safety[0]
        output.write(
            f"Top safety review: {unit['provider']} | {unit['sender_key']} | "
            f"score={unit['safety_priority']['priority_score']}\n"
        )
    output.write(f"Saved pack: {pack['pack_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
