import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.classifier_corpus_eval import build_classifier_corpus_report, write_classifier_corpus_report
from src.cli_paths import resolve_path
from src.local_artifacts import (
    accepted_shadow_rules_path,
    load_json,
    shadow_suggestion_memory_path,
    write_json,
)
from src.shadow_suggestion_memory import (
    OpenAIShadowFamilySuggestionClient,
    ShadowSuggestionCandidate,
    ShadowSuggestionMemory,
    build_shadow_suggestion_candidates,
)
from src.teachable_rule_memory import TeachableRuleMemory


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the current classifier against stored Gmail reviewed data and "
            "stored ProtonMail and Outlook/Hotmail shadow data without provider calls."
        )
    )
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--top-limit", type=int, default=10)
    parser.add_argument("--suggestion-limit", type=int, default=12)
    parser.add_argument("--suggestion-model")
    parser.add_argument("--no-model-suggestions", action="store_true")
    parser.add_argument("--accepted-shadow-rules-path", type=Path)
    parser.add_argument("--split-salt", default="2026-06-27-v2-unseen-holdout")
    parser.add_argument("--exposed-family-path", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    family_suggestion_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()

    gmail_storage_dir = resolve_path(args.gmail_storage_dir, repo_root)
    protonmail_storage_dir = resolve_path(args.protonmail_storage_dir, repo_root)
    outlookmail_storage_dir = resolve_path(args.outlookmail_storage_dir, repo_root)
    output_storage_dir = resolve_path(args.output_storage_dir, repo_root)
    exposed_families = {}
    if args.exposed_family_path is not None:
        exposed_families = _load_exposed_families(resolve_path(args.exposed_family_path, repo_root))
    compiled_rules_path = None
    extra_rules = []
    if args.accepted_shadow_rules_path is not None:
        compiled_rules_path = resolve_path(args.accepted_shadow_rules_path, repo_root)
        extra_rules = TeachableRuleMemory(compiled_rules_path).list_rules()
    baseline_report = None
    if extra_rules:
        baseline_report = build_classifier_corpus_report(
            [
                ("gmail", gmail_storage_dir),
                ("protonmail", protonmail_storage_dir),
                ("outlookmail", outlookmail_storage_dir),
            ],
            top_limit=args.top_limit,
            split_salt=args.split_salt,
            exposed_families=exposed_families,
            extra_rules=[],
        )
    family_suggestion_client = None
    if args.suggestion_model and not args.no_model_suggestions:
        selected_model = args.suggestion_model
        family_suggestion_client_factory = (
            family_suggestion_client_factory
            or (lambda model: OpenAIShadowFamilySuggestionClient.from_env(model))
        )
        try:
            family_suggestion_client = family_suggestion_client_factory(selected_model)
        except RuntimeError as exc:
            error_output.write(f"{exc}\n")
            return 2

    report = write_classifier_corpus_report(
        output_storage_dir,
        [
            ("gmail", gmail_storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        top_limit=args.top_limit,
        split_salt=args.split_salt,
        exposed_families=exposed_families,
        extra_rules=extra_rules,
    )
    suggestion_candidates = build_shadow_suggestion_candidates(
        report,
        limit_per_provider=args.suggestion_limit,
        model_client=family_suggestion_client,
    )
    suggestion_memory = ShadowSuggestionMemory(shadow_suggestion_memory_path(output_storage_dir))
    merged_candidates = suggestion_memory.merge_candidates(
        [
            ShadowSuggestionCandidate.from_dict(candidate)
            for provider_candidates in suggestion_candidates.values()
            for candidate in provider_candidates
        ]
    )
    report["shadow_suggestion_candidates"] = suggestion_candidates
    report["shadow_suggestion_memory_path"] = str(suggestion_memory.path)
    if compiled_rules_path is not None:
        report["accepted_shadow_rules_path"] = str(compiled_rules_path)
        report["accepted_shadow_rule_count"] = len(extra_rules)
    if baseline_report is not None:
        report["accepted_shadow_rule_projection"] = _projection_summary(baseline_report, report)
    write_json(Path(report["report_path"]), report)

    output.write(
        f"Eval contract: {report['eval_contract']['current_doc']} "
        f"({report['eval_contract']['current_as_of']})\n"
    )
    for provider, provider_report in report["providers"].items():
        output.write(
            f"Provider: {provider} | total={provider_report['total_count']} "
            f"| reviewed={provider_report['reviewed_count']} "
            f"| shadow={provider_report['shadow_count']} "
            f"| unlabeled={provider_report['unlabeled_count']} "
            f"({provider_report['unlabeled_rate']}%)\n"
        )
        if "reviewed_metrics" in provider_report:
            metrics = provider_report["reviewed_metrics"]
            output.write(
                f"  Reviewed exact-match: {metrics['exact_match_count']} "
                f"({metrics['exact_match_rate']}%)\n"
            )
        for split in ("discovery", "validation", "holdout"):
            split_counts = provider_report["split_counts"][split]
            output.write(
                f"  {split}: total={split_counts['total_count']} "
                f"| unlabeled={split_counts['unlabeled_count']} "
                f"({split_counts['unlabeled_rate']}%)\n"
            )
        output.write(
            f"  suggestion candidates: {len(suggestion_candidates.get(provider, []))}\n"
        )
        safety_projection = provider_report["safety_memory_projection"]
        output.write(
            f"  safety memory: approved={safety_projection['approved_disposition_count']} "
            f"| hits={safety_projection['projected']['safety_memory_hit_count']} "
            f"| caution delta={safety_projection['delta']['caution_count_delta']} "
            f"| heuristic false-hide after={safety_projection['projected']['heuristic_false_hide_risk_count']}\n"
        )
        for split in ("validation", "holdout"):
            split_projection = safety_projection["by_split"][split]
            output.write(
                f"  safety {split}: caution delta={split_projection['delta']['caution_count_delta']} "
                f"| heuristic false-hide after={split_projection['projected']['heuristic_false_hide_risk_count']}\n"
            )
        false_hide_families = safety_projection["top_projected_false_hide_risk_families"]
        if false_hide_families:
            family = false_hide_families[0]
            output.write(
                f"  top safety false-hide risk: {family['sender_key']} | {family['subject_key']} "
                f"| count={family['count']}\n"
            )
        for split in ("validation", "holdout"):
            caution_families = safety_projection["top_projected_caution_families_by_split"][split]
            if not caution_families:
                continue
            family = caution_families[0]
            output.write(
                f"  top safety {split} caution family: {family['sender_key']} | {family['subject_key']} "
                f"| count={family['count']}\n"
            )
        if extra_rules:
            output.write(
                f"  matched accepted shadow rules: {provider_report['matched_shadow_rule_count']}\n"
            )
            projection = report["accepted_shadow_rule_projection"][provider]
            output.write(
                f"  unlabeled delta from baseline: {projection['unlabeled_delta']} "
                f"({projection['unlabeled_rate_delta']} pts)\n"
            )
    output.write(f"Saved report: {report['report_path']}\n")
    output.write(f"Saved suggestion memory: {suggestion_memory.path} ({len(merged_candidates)} candidates)\n")
    return 0


def _load_exposed_families(path: Path) -> dict[str, set[tuple[str, str]]]:
    raw = load_json(path)
    return {
        provider: {
            (item["sender_key"], item["subject_key"])
            for item in families
        }
        for provider, families in raw.items()
    }


def _projection_summary(baseline_report: dict, projected_report: dict) -> dict[str, dict]:
    summary = {}
    for provider, provider_report in projected_report["providers"].items():
        baseline_provider = baseline_report["providers"][provider]
        summary[provider] = {
            "unlabeled_before": baseline_provider["unlabeled_count"],
            "unlabeled_after": provider_report["unlabeled_count"],
            "unlabeled_delta": provider_report["unlabeled_count"] - baseline_provider["unlabeled_count"],
            "unlabeled_rate_before": baseline_provider["unlabeled_rate"],
            "unlabeled_rate_after": provider_report["unlabeled_rate"],
            "unlabeled_rate_delta": round(provider_report["unlabeled_rate"] - baseline_provider["unlabeled_rate"], 1),
        }
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
