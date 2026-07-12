import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.shadow_label_eval import OpenAIShadowLabelClient, ShadowLabelEvaluator

DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare local heuristic label suggestions against reviewed outcomes and an optional OpenAI shadow model."
    )
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--disagreement-limit", type=int, default=25)
    parser.add_argument("--model")
    parser.add_argument("--no-model", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    model_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = _resolve_path(args.storage_dir, repo_root)

    model_client = None
    if not args.no_model:
        selected_model = args.model or "gpt-4.1-mini"
        model_client_factory = model_client_factory or (lambda model: OpenAIShadowLabelClient.from_env(model))
        try:
            model_client = model_client_factory(selected_model)
        except RuntimeError as exc:
            error_output.write(f"{exc}\n")
            return 2

    evaluator = ShadowLabelEvaluator(storage_dir=storage_dir, model_client=model_client)
    report = evaluator.run(limit=args.limit, disagreement_limit=args.disagreement_limit)

    output.write(f"Reviewed messages evaluated: {report['overall']['reviewed_count']}\n")
    output.write(
        f"Heuristic exact-match rate: {report['overall']['heuristic']['exact_match_rate']}%\n"
    )
    if "model" in report["overall"]:
        output.write(f"Model exact-match rate: {report['overall']['model']['exact_match_rate']}%\n")
        output.write(
            "Model-better disagreements: "
            f"{len(report['disagreements']['model_better_than_heuristic'])}\n"
        )
        output.write(
            "Heuristic-better disagreements: "
            f"{len(report['disagreements']['heuristic_better_than_model'])}\n"
        )
    output.write(f"Saved report: {report['report_path']}\n")
    return 0


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
