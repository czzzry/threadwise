import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.safety_triage_status import build_safety_triage_status


DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize the latest local safety triage pass and recent backlog trend."
    )
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--history-limit", type=int, default=5)
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

    status = build_safety_triage_status(output_storage_dir, history_limit=args.history_limit)
    if status["status"] != "ready":
        output.write(f"{status['message']}\n")
        return 1

    latest = status["latest"]
    trend = status["trend"]
    output.write(f"Latest safety triage: {latest['generated_at']}\n")
    output.write(f"Backlog pressure: {latest['backlog_pressure']}\n")
    output.write(f"Pending dispositions: {latest['pending_disposition_count']}\n")
    output.write(f"Top targets: {latest['top_target_count']}\n")
    output.write(f"Trend: {trend['summary']}\n")
    if latest.get("top_target"):
        top = latest["top_target"]
        output.write(
            f"Top target: {top.get('provider', '')} | {top.get('sender_key', '')} | "
            f"{top.get('subject_key', '')}\n"
        )
    for driver in latest.get("provider_drivers", [])[:3]:
        output.write(
            f"Provider driver: {driver.get('provider', '')} | score={driver.get('driver_score', 0)} | "
            f"targets={driver.get('top_target_count', 0)} | "
            f"false-hide={driver.get('eval_false_hide_risk_count', 0)}\n"
        )
    for target in latest.get("top_review_targets", [])[:3]:
        output.write(
            f"Review target: {target.get('provider', '')} | {target.get('sender_key', '')} | "
            f"{target.get('subject_key', '')} | "
            f"priority={target.get('review_priority', {}).get('score', 0)} | "
            f"bucket={target.get('review_priority', {}).get('bucket', '')}\n"
        )
    memory_summary = latest.get("memory_impact_summary", {})
    if memory_summary:
        output.write(
            f"Memory impact: rules={memory_summary.get('accepted_rule_count', 0)} | "
            f"impacted={memory_summary.get('impacted_rule_count', 0)} | "
            f"unresolved before={memory_summary.get('unresolved_before', 0)} | "
            f"after={memory_summary.get('unresolved_after', 0)}\n"
        )
    for impact in latest.get("top_memory_impacts", [])[:3]:
        top_family = (impact.get("top_resolved_families") or [{}])[0]
        output.write(
            f"Memory winner: {top_family.get('provider', '')} | {top_family.get('sender_key', '')} | "
            f"{impact.get('label', '')} | resolved={impact.get('resolved_message_count', 0)} | "
            f"matched={impact.get('matched_message_count', 0)}\n"
        )
    for payoff in latest.get("next_review_payoffs", [])[:3]:
        output.write(
            f"Next payoff: {payoff.get('provider', '')} | {payoff.get('sender_key', '')} | "
            f"expected gain={payoff.get('expected_resolved_messages', 0)} | "
            f"bucket={payoff.get('expected_gain_band', '')}\n"
        )
    founder_question_summary = latest.get("founder_question_summary", {})
    if founder_question_summary:
        output.write(
            f"Founder questions: count={founder_question_summary.get('question_count', 0)} | "
            f"estimated unlocked={founder_question_summary.get('estimated_unblocked_messages', 0)}\n"
        )
    for question in latest.get("founder_questions", [])[:3]:
        output.write(
            f"Founder question: {question.get('theme', '')} | providers={','.join(question.get('providers', []))} | "
            f"families={question.get('family_count', 0)} | unlocked={question.get('estimated_unblocked_messages', 0)}\n"
        )
    founder_answer_summary = latest.get("founder_answer_summary", {})
    if founder_answer_summary:
        output.write(
            f"Founder answers: options={founder_answer_summary.get('answer_option_count', 0)} | "
            f"actionable={founder_answer_summary.get('actionable_answer_count', 0)}\n"
        )
    for preview in latest.get("founder_answer_previews", [])[:3]:
        output.write(
            f"Founder answer preview: {preview.get('theme', '')} | {preview.get('answer_key', '')} | "
            f"resolved={preview.get('estimated_resolved_messages', 0)} | proposals={preview.get('proposal_count', 0)}\n"
        )
    latest_application = latest.get("latest_founder_answer_application", {})
    if latest_application:
        output.write(
            f"Latest founder application: {latest_application.get('theme', '')} | "
            f"{latest_application.get('matched_answer_key', '')} | "
            f"approved={latest_application.get('approved_proposal_count', 0)} | "
            f"resolved gain={latest_application.get('resolved_gain', 0)}\n"
        )
    output.write(f"Latest manifest: {status['manifest_path']}\n")
    for item in status["history"]:
        output.write(
            f"{item['generated_at']} | pressure={item['backlog_pressure']} | "
            f"pending={item['pending_disposition_count']} | targets={item['top_target_count']}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
