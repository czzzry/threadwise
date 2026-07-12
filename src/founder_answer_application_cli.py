import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.founder_answer_application import apply_founder_answer_decision, load_founder_answer_decision
from src.local_artifacts import latest_safety_triage_manifest_path, load_json


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Approve a saved founder answer decision into accepted memory and refresh impact artifacts."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--decision-path", type=Path)
    parser.add_argument("--question-id")
    parser.add_argument("--review-notes", default="")
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

    if not args.decision_path and not args.question_id:
        parser.error("one of --decision-path or --question-id is required")

    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    decision_path = resolve_optional_path(args.decision_path, repo_root)
    decision = load_founder_answer_decision(
        output_storage_dir,
        decision_path=decision_path,
        question_id=args.question_id,
    )

    review_pack = {}
    manifest_path = latest_safety_triage_manifest_path(output_storage_dir)
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        review_pack_path = manifest.get("artifacts", {}).get("review_pack_path")
        if review_pack_path:
            review_pack = load_json(Path(review_pack_path))

    application = apply_founder_answer_decision(
        output_storage_dir,
        decision=decision,
        provider_storage_dirs=[
            ("gmail", resolve_path(args.gmail_storage_dir, repo_root)),
            ("protonmail", resolve_path(args.protonmail_storage_dir, repo_root)),
            ("outlookmail", resolve_path(args.outlookmail_storage_dir, repo_root)),
        ],
        review_notes=args.review_notes,
        review_pack=review_pack,
    )
    output.write(
        f"Applied founder answer: {application['theme']} | matched={application['matched_answer_key']} | "
        f"approved-proposals={application['approved_proposal_count']} | "
        f"approved-rules={len(application['approved_rule_ids'])}\n"
    )
    output.write(
        f"Memory impact: rules {application['impact_before'].get('accepted_rule_count', 0)} -> "
        f"{application['impact_after'].get('accepted_rule_count', 0)} | "
        f"unresolved {application['impact_before'].get('unresolved_after', 0)} -> "
        f"{application['impact_after'].get('unresolved_after', 0)} | "
        f"resolved gain={application['impact_delta'].get('resolved_gain', 0)}\n"
    )
    output.write(f"Saved application: {application['application_path']}\n")
    output.write(f"Saved report: {application['memory_impact_report_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
