import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.classifier_corpus_eval import write_classifier_corpus_report
from src.cli_paths import resolve_optional_path, resolve_path
from src.cluster_decision_pack import write_cluster_decision_pack
from src.frontier_compression import write_frontier_compression_plan
from src.founder_answer_pack import write_founder_answer_pack
from src.founder_question_pack import write_founder_question_pack
from src.local_artifacts import accepted_shadow_rules_path, shadow_suggestion_memory_path
from src.memory_impact_report import write_memory_impact_report
from src.safety_backlog_report import write_safety_backlog_report
from src.safety_review_digest import write_safety_review_digest
from src.safety_triage_manifest import write_safety_triage_manifest
from src.shadow_review_pack import write_shadow_review_pack
from src.teachable_rule_memory import TeachableRuleMemory


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an unattended local safety triage pass across eval, frontier, decision-pack, review-pack, digest, and backlog artifacts."
    )
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--accepted-shadow-rules-path", type=Path)
    parser.add_argument("--exposed-family-path", type=Path)
    parser.add_argument("--top-limit", type=int, default=10)
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

    gmail_storage_dir = resolve_path(args.gmail_storage_dir, repo_root)
    protonmail_storage_dir = resolve_path(args.protonmail_storage_dir, repo_root)
    outlookmail_storage_dir = resolve_path(args.outlookmail_storage_dir, repo_root)
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    rules_path = resolve_optional_path(args.accepted_shadow_rules_path, repo_root) or accepted_shadow_rules_path(output_storage_dir)
    extra_rules = TeachableRuleMemory(rules_path).list_rules() if rules_path.exists() else []

    report = write_classifier_corpus_report(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        top_limit=args.top_limit,
        extra_rules=extra_rules,
    )
    frontier_plan = write_frontier_compression_plan(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        extra_rules=extra_rules,
    )
    cluster_pack = write_cluster_decision_pack(output_storage_dir, frontier_plan)
    review_pack = write_shadow_review_pack(
        output_storage_dir,
        report,
        suggestion_memory_path=shadow_suggestion_memory_path(output_storage_dir),
        max_families_per_provider=args.max_families_per_provider,
    )
    digest = write_safety_review_digest(
        output_storage_dir,
        report=report,
        frontier_plan=frontier_plan,
        cluster_pack=cluster_pack,
        review_pack=review_pack,
    )
    provider_storage_dirs = [
        ("gmail", gmail_storage_dir),
        ("protonmail", protonmail_storage_dir),
        ("outlookmail", outlookmail_storage_dir),
    ]
    backlog = write_safety_backlog_report(
        output_storage_dir,
        provider_storage_dirs=provider_storage_dirs,
        report=report,
        frontier_plan=frontier_plan,
        cluster_pack=cluster_pack,
        review_pack=review_pack,
        digest=digest,
    )
    memory_impact = write_memory_impact_report(
        output_storage_dir,
        provider_storage_dirs,
        accepted_rules=extra_rules,
        review_pack=review_pack,
    )
    founder_question_pack = write_founder_question_pack(
        output_storage_dir,
        review_pack=review_pack,
        memory_impact=memory_impact,
        provider_drivers=backlog.get("provider_drivers", []),
    )
    founder_answer_pack = write_founder_answer_pack(
        output_storage_dir,
        founder_question_pack=founder_question_pack,
        review_pack=review_pack,
        provider_storage_dirs=provider_storage_dirs,
    )
    manifest = write_safety_triage_manifest(
        output_storage_dir,
        report=report,
        frontier_plan=frontier_plan,
        cluster_pack=cluster_pack,
        review_pack=review_pack,
        digest=digest,
        backlog=backlog,
        memory_impact=memory_impact,
        founder_question_pack=founder_question_pack,
        founder_answer_pack=founder_answer_pack,
    )

    output.write(
        f"Safety triage pass: targets={digest['summary']['top_target_count']} | "
        f"pressure={backlog['summary']['backlog_pressure']} | "
        f"pending-dispositions={backlog['summary']['pending_disposition_count']}\n"
    )
    if digest["top_targets"]:
        top = digest["top_targets"][0]
        output.write(
            f"Top target: {top['provider']} | {top['sender_key']} | {top['subject_key']} | "
            f"score={top['priority_score']} | source={top['source']}\n"
        )
    output.write(f"Eval report: {report['report_path']}\n")
    output.write(f"Frontier plan: {frontier_plan['plan_path']}\n")
    output.write(f"Cluster pack: {cluster_pack['pack_path']}\n")
    output.write(f"Review pack: {review_pack['pack_path']}\n")
    output.write(f"Safety digest: {digest['digest_path']}\n")
    output.write(f"Backlog report: {backlog['report_path']}\n")
    output.write(f"Memory impact: {memory_impact['report_path']}\n")
    output.write(f"Founder questions: {founder_question_pack['pack_path']}\n")
    output.write(f"Founder answers: {founder_answer_pack['pack_path']}\n")
    output.write(f"Latest manifest: {manifest['manifest_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
