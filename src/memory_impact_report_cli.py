import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.local_artifacts import accepted_shadow_rules_path, load_json
from src.memory_impact_report import write_memory_impact_report
from src.teachable_rule_memory import TeachableRuleMemory


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure accepted-memory impact and next-review payoff across stored provider corpora."
    )
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--accepted-shadow-rules-path", type=Path)
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

    gmail_storage_dir = resolve_path(args.gmail_storage_dir, repo_root)
    protonmail_storage_dir = resolve_path(args.protonmail_storage_dir, repo_root)
    outlookmail_storage_dir = resolve_path(args.outlookmail_storage_dir, repo_root)
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    rules_path = resolve_path(args.accepted_shadow_rules_path, repo_root) if args.accepted_shadow_rules_path else accepted_shadow_rules_path(output_storage_dir)
    review_pack = load_json(resolve_path(args.review_pack_path, repo_root)) if args.review_pack_path else {}
    rules = TeachableRuleMemory(rules_path).list_rules() if rules_path.exists() else []

    report = write_memory_impact_report(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        accepted_rules=rules,
        review_pack=review_pack,
    )
    summary = report["summary"]
    output.write(
        f"Memory impact: rules={summary['accepted_rule_count']} | impacted={summary['impacted_rule_count']} | "
        f"unresolved before={summary['unresolved_before']} | after={summary['unresolved_after']}\n"
    )
    if report["top_memory_impacts"]:
        top = report["top_memory_impacts"][0]
        output.write(
            f"Top memory impact: {top['rule_id']} | resolved={top['resolved_message_count']} | "
            f"matched={top['matched_message_count']}\n"
        )
    if report["next_review_payoffs"]:
        top = report["next_review_payoffs"][0]
        output.write(
            f"Top review payoff: {top['provider']} | {top['sender_key']} | "
            f"expected gain={top['expected_resolved_messages']} | bucket={top['expected_gain_band']}\n"
        )
    output.write(f"Saved report: {report['report_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
