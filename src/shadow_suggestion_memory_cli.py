import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_path
from src.local_artifacts import accepted_shadow_rules_path, shadow_suggestion_memory_path
from src.shadow_suggestion_memory import ShadowSuggestionMemory


DEFAULT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local shadow suggestion memory candidates.")
    parser.add_argument("command", choices=["list", "approve", "reject", "export-rules"])
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--provider")
    parser.add_argument("--sender-key")
    parser.add_argument("--subject-key")
    parser.add_argument("--labels")
    parser.add_argument("--notes", default="")
    parser.add_argument("--rules-path", type=Path)
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
    storage_dir = resolve_path(args.storage_dir, repo_root)
    memory = ShadowSuggestionMemory(shadow_suggestion_memory_path(storage_dir))

    if args.command == "list":
        candidates = memory.list_candidates()
        output.write(f"Candidates: {len(candidates)}\n")
        status_counts: dict[str, int] = {}
        for candidate in candidates:
            status_counts[candidate.status] = status_counts.get(candidate.status, 0) + 1
        if status_counts:
            rendered_counts = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
            output.write(f"Status counts: {rendered_counts}\n")
        for candidate in candidates[:25]:
            output.write(
                f"{candidate.status} | {candidate.provider} | {candidate.count} | "
                f"{candidate.sender_key} | {candidate.subject_key} | {list(candidate.suggested_labels)}\n"
            )
        return 0

    if args.command in {"approve", "reject"}:
        if not args.provider or not args.sender_key or not args.subject_key:
            raise SystemExit("--provider, --sender-key, and --subject-key are required.")
        labels = [label.strip() for label in (args.labels or "").split(",") if label.strip()]
        updated = memory.review_candidate(
            args.provider,
            args.sender_key,
            args.subject_key,
            "accepted" if args.command == "approve" else "rejected",
            accepted_labels=labels,
            review_notes=args.notes,
        )
        output.write(
            f"{updated.status}: {updated.provider} | {updated.sender_key} | {updated.subject_key} | "
            f"{list(updated.accepted_labels or updated.suggested_labels)}\n"
        )
        return 0

    rules_path = resolve_path(args.rules_path, repo_root) if args.rules_path else accepted_shadow_rules_path(storage_dir)
    exported = memory.export_accepted_rules(rules_path)
    output.write(f"Exported {len(exported)} provider-scoped rules to {rules_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
