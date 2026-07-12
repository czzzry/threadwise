import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.cluster_decision_pack import load_frontier_plan
from src.founder_policy_batch import write_founder_policy_batch_pack
from src.local_artifacts import accepted_shadow_rules_path
from src.teachable_rule_memory import TeachableRuleMemory


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a batch founder policy pack from accepted memory and unresolved cluster decision units."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--accepted-shadow-rules-path", type=Path)
    parser.add_argument("--cluster-decision-pack-path", type=Path, required=True)
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
    rules_path = resolve_optional_path(args.accepted_shadow_rules_path, repo_root) or accepted_shadow_rules_path(output_storage_dir)
    cluster_decision_pack = load_frontier_plan(resolve_path(args.cluster_decision_pack_path, repo_root))
    accepted_rules = TeachableRuleMemory(rules_path).list_rules() if rules_path.exists() else []

    pack = write_founder_policy_batch_pack(
        output_storage_dir,
        cluster_decision_pack=cluster_decision_pack,
        accepted_rules=accepted_rules,
        provider_storage_dirs=[
            ("gmail", resolve_path(args.gmail_storage_dir, repo_root)),
            ("protonmail", resolve_path(args.protonmail_storage_dir, repo_root)),
            ("outlookmail", resolve_path(args.outlookmail_storage_dir, repo_root)),
        ],
    )
    summary = pack["summary"]
    output.write(
        f"Founder policy batches: batches={summary['batch_count']} | proposals={summary['proposal_count']} | "
        f"messages={summary['message_coverage']} | families={summary['family_coverage']}\n"
    )
    for batch in pack.get("batches", [])[:5]:
        output.write(
            f"Batch: {batch['policy_key']} | labels={','.join(batch['labels'])} | "
            f"clusters={batch['cluster_count']} | messages={batch['message_coverage']}\n"
        )
    output.write(f"Saved pack: {pack['pack_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
