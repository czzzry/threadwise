import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.local_artifacts import accepted_shadow_rules_path
from src.runtime_cascade import OpenAIRuntimeCascadeClient, load_cluster_decision_pack, write_runtime_cascade_report
from src.teachable_rule_memory import TeachableRuleMemory
from src.unified_review_queue import UnifiedReviewQueue


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the stored-corpus runtime cascade prototype with optional cluster-memory-aware LLM escalation."
    )
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--accepted-shadow-rules-path", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR / "accepted_shadow_teachable_rules.json")
    parser.add_argument("--cluster-decision-pack-path", type=Path)
    parser.add_argument("--llm-model")
    parser.add_argument("--llm-limit", type=int, default=25)
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
    rules = TeachableRuleMemory(rules_path).list_rules()
    cluster_pack = (
        load_cluster_decision_pack(resolve_path(args.cluster_decision_pack_path, repo_root))
        if args.cluster_decision_pack_path
        else None
    )

    llm_client = None
    if args.llm_model:
        llm_client_factory = llm_client_factory or (lambda model: OpenAIRuntimeCascadeClient.from_env(model))
        llm_client = llm_client_factory(args.llm_model)

    report = write_runtime_cascade_report(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        extra_rules=rules,
        cluster_decision_pack=cluster_pack,
        llm_client=llm_client,
        llm_limit=args.llm_limit,
    )
    UnifiedReviewQueue(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
    ).build_queue(runtime_report=report)
    summary = report["summary"]
    output.write(
        f"Runtime cascade: messages={summary['message_count']} | resolved={summary['resolved_count']} "
        f"| unresolved={summary['unresolved_count']}\n"
    )
    output.write(
        f"Deterministic={summary['deterministic_count']} | Memory={summary['accepted_memory_count']} | "
        f"LLM={summary['llm_escalation_count']} | LLM calls={summary['llm_call_count']} | "
        f"Memory context hits={summary['memory_context_hit_count']} | "
        f"Safety memory hits={summary['safety_memory_hit_count']}\n"
    )
    output.write(
        f"Safety lane: security-sensitive={summary['safety_counts']['security-sensitive']} | "
        f"suspicious={summary['safety_counts']['suspicious']} | "
        f"total caution={summary['safety_review_count']}\n"
    )
    output.write(f"Saved report: {report['report_path']}\n")
    output.write(f"Refreshed review queue: {output_storage_dir / 'unified_review_queue.json'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
