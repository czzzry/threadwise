import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.safety_review_digest import load_artifact, write_safety_review_digest


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a compact safety review digest from existing evaluation and review artifacts."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--frontier-plan-path", type=Path)
    parser.add_argument("--cluster-pack-path", type=Path)
    parser.add_argument("--review-pack-path", type=Path)
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

    digest = write_safety_review_digest(
        resolve_path(args.output_storage_dir, repo_root),
        report=load_artifact(resolve_path(args.report_path, repo_root)) if args.report_path else None,
        frontier_plan=load_artifact(resolve_path(args.frontier_plan_path, repo_root)) if args.frontier_plan_path else None,
        cluster_pack=load_artifact(resolve_path(args.cluster_pack_path, repo_root)) if args.cluster_pack_path else None,
        review_pack=load_artifact(resolve_path(args.review_pack_path, repo_root)) if args.review_pack_path else None,
    )
    output.write(
        f"Built safety digest: providers={digest['summary']['provider_count']} | "
        f"top-targets={digest['summary']['top_target_count']}\n"
    )
    if digest["top_targets"]:
        top = digest["top_targets"][0]
        output.write(
            f"Top target: {top['provider']} | {top['sender_key']} | {top['subject_key']} | "
            f"score={top['priority_score']} | source={top['source']}\n"
        )
    output.write(f"Saved digest: {digest['digest_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
