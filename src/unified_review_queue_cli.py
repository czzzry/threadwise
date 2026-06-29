import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.local_artifacts import load_json
from src.unified_review_queue import UnifiedReviewQueue


DEFAULT_GMAIL_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and review the unified inbox-learning queue.")
    parser.add_argument("command", choices=["build", "list", "approve", "reject", "answer"])
    parser.add_argument("--gmail-storage-dir", type=Path, default=DEFAULT_GMAIL_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--runtime-report-path", type=Path)
    parser.add_argument("--founder-answer-pack-path", type=Path)
    parser.add_argument("--item-id")
    parser.add_argument("--labels", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--answer-key")
    parser.add_argument("--response-text")
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
    queue = UnifiedReviewQueue(
        output_storage_dir,
        [
            ("gmail", resolve_path(args.gmail_storage_dir, repo_root)),
            ("protonmail", resolve_path(args.protonmail_storage_dir, repo_root)),
            ("outlookmail", resolve_path(args.outlookmail_storage_dir, repo_root)),
        ],
    )

    if args.command == "build":
        payload = queue.build_queue(
            runtime_report=_load_optional_json(resolve_optional_path(args.runtime_report_path, repo_root)),
            founder_answer_pack=_load_optional_json(resolve_optional_path(args.founder_answer_pack_path, repo_root)),
        )
        output.write(
            f"Unified review queue: items={payload['summary']['item_count']} | "
            f"pending={payload['summary']['status_counts'].get('pending', 0)} | "
            f"path={queue.path}\n"
        )
        return 0

    if args.command == "list":
        payload = queue.load_queue()
        summary = payload.get("summary", {})
        output.write(
            f"Unified review queue: items={summary.get('item_count', 0)} | "
            f"pending={summary.get('status_counts', {}).get('pending', 0)}\n"
        )
        for item in payload.get("items", [])[:25]:
            output.write(
                f"{item.get('status', 'pending')} | {item.get('item_type', '')} | "
                f"{item.get('item_id', '')} | {item.get('title', '')}\n"
            )
        return 0

    if not args.item_id:
        raise SystemExit("--item-id is required for approve, reject, and answer.")
    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    result = queue.review_item(
        args.item_id,
        action=args.command,
        notes=args.notes,
        labels=labels,
        answer_key=args.answer_key,
        response_text=args.response_text,
    )
    output.write(
        f"{result['status']}: {result['item_type']} | {result['item_id']} | "
        f"rules={len(result.get('approved_rule_ids', []))}\n"
    )
    return 0


def _load_optional_json(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    payload = load_json(path)
    if "pack_path" not in payload and "report_path" not in payload:
        if "questions" in payload:
            payload["pack_path"] = str(path)
        else:
            payload["report_path"] = str(path)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
