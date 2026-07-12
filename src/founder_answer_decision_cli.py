import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.founder_answer_decision import save_founder_answer_decision
from src.local_artifacts import latest_safety_triage_manifest_path, load_json


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Answer one founder question in natural language and save pending memory proposals plus projected impact."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--response-text", required=True)
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
    manifest_path = latest_safety_triage_manifest_path(output_storage_dir)
    if not manifest_path.exists():
        output.write("No latest safety triage manifest found.\n")
        return 1
    manifest = load_json(manifest_path)
    founder_answer_pack_path = manifest.get("artifacts", {}).get("founder_answer_pack_path")
    if not founder_answer_pack_path:
        output.write("No founder answer pack path found in latest manifest.\n")
        return 1
    founder_answer_pack = load_json(Path(founder_answer_pack_path))

    decision = save_founder_answer_decision(
        output_storage_dir,
        founder_answer_pack=founder_answer_pack,
        question_id=args.question_id,
        response_text=args.response_text,
    )
    output.write(
        f"Founder answer: {decision['theme']} | matched={decision['matched_answer_key']} | "
        f"confidence={decision['match_confidence']}\n"
    )
    output.write(
        f"Projected impact: proposals={decision['projection'].get('proposal_count', 0)} | "
        f"resolved={decision['projection'].get('estimated_resolved_messages', 0)}\n"
    )
    output.write(f"Saved decision: {decision['decision_path']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
