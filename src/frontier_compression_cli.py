import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.frontier_compression import OpenAIFrontierClusterClient, write_frontier_compression_plan
from src.teachable_rule_memory import TeachableRuleMemory


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a sender-cluster frontier compression plan from unresolved stored shadow corpora."
    )
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--accepted-shadow-rules-path", type=Path, required=True)
    parser.add_argument("--llm-model")
    parser.add_argument("--llm-limit", type=int, default=8)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    cwd: Path | None = None,
    llm_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    repo_root = cwd or Path.cwd()

    gmail_storage_dir = resolve_path(args.gmail_storage_dir, repo_root)
    protonmail_storage_dir = resolve_path(args.protonmail_storage_dir, repo_root)
    outlookmail_storage_dir = resolve_path(args.outlookmail_storage_dir, repo_root)
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    rules_path = resolve_path(args.accepted_shadow_rules_path, repo_root)
    extra_rules = TeachableRuleMemory(rules_path).list_rules()

    llm_client = None
    if args.llm_model:
        llm_client_factory = llm_client_factory or (lambda model: OpenAIFrontierClusterClient.from_env(model))
        llm_client = llm_client_factory(args.llm_model)

    plan = write_frontier_compression_plan(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        extra_rules=extra_rules,
        llm_client=llm_client,
        llm_limit=args.llm_limit,
    )
    summary = plan["summary"]
    output.write(
        f"Frontier clusters: {summary['total_unresolved_sender_clusters']} "
        f"| messages: {summary['total_unresolved_messages']} "
        f"| families: {summary['total_unresolved_families']}\n"
    )
    output.write(
        f"Auto-low-value: {summary['auto_low_value_clusters']} | "
        f"Safety-review: {summary['safety_review_clusters']} | "
        f"Personal-review: {summary['personal_review_clusters']} | "
        f"Preference-review: {summary['preference_review_clusters']} | "
        f"Unclear: {summary['unclear_clusters']} | "
        f"Safety-priority: {summary['safety_priority_clusters']}\n"
    )
    top_safety = (plan.get("top_safety_priority_clusters") or [])
    if top_safety:
        output.write(
            f"Top safety priority: {top_safety[0]['provider']} | {top_safety[0]['sender_key']} | "
            f"score={top_safety[0]['safety_priority']['priority_score']}\n"
        )
    output.write(f"Saved plan: {plan['plan_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
