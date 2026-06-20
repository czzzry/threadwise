import argparse
import json
from collections import Counter
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

from src.gmail_writer import MockGmailLabelWriter
from src.gmail_message_normalizer import normalize_gmail_message
from src.label_taxonomy import CANONICAL_LABEL_ORDER, allowed_gmail_labels, gmail_label_name
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, LiveGmailClient, SetupError
from src.fixture_classifier import FixtureBatchClassifier
from src.review_loop import FixtureReviewLoop
from src.stored_batch_review_store import StoredBatchReviewStore


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")
DISPLAY_LABEL_TO_INTERNAL = {gmail_label_name(label).lower(): label for label in CANONICAL_LABEL_ORDER}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review one stored live Gmail batch locally and confirm EA label write-back."
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--client-secret-path", type=Path)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    gmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_stream = stdin or sys.stdin
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = _resolve_path(args.storage_dir, repo_root)
    credentials_dir = _resolve_path(args.credentials_dir, repo_root)
    client_secret_path = _resolve_optional_path(args.client_secret_path, repo_root)

    try:
        batch_store = StoredBatchReviewStore(storage_dir)
        stored_batch = batch_store.load_batch(args.batch_id)
        review_queue = batch_store.to_review_queue(stored_batch)
        review_loop = FixtureReviewLoop(fixtures_dir=storage_dir)
        review_loop.load_review_queue(review_queue)
        review_result = _review_pending_items(stored_batch, review_loop, output, input_stream)
        reviewed_batch = review_loop.load_review_queue(review_queue)
        batch_store.persist_reviewed_items(args.batch_id, reviewed_batch["items"])
        if review_result == "quit":
            output.write("Quit before Gmail write-back. No Gmail labels were applied.\n")
            return 0

        dry_run_items = _collect_dry_run_items(reviewed_batch["items"])
        _print_dry_run(reviewed_batch["items"], dry_run_items, output)

        confirmation = input_stream.readline().strip()
        if confirmation.upper() != "APPLY":
            output.write("No Gmail labels were applied.\n")
            return 0

        gmail_client_factory = gmail_client_factory or _default_gmail_client_factory
        gmail_client = gmail_client_factory(
            review_queue["account_id"],
            credentials_dir,
            client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=storage_dir,
            label_name_resolver=_gmail_label_name,
        )
        summary = writer.write_reviewed_labels(args.batch_id, reviewed_batch["items"])
        output.write(f"Applied {summary['applied_count']} reviewed Gmail label updates.\n")
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def _review_pending_items(stored_batch: dict, review_loop: FixtureReviewLoop, output: TextIO, input_stream: TextIO) -> str:
    batch = review_loop.load_fixture_batch(stored_batch["batch_id"])
    raw_messages = {
        message.get("id"): message
        for message in stored_batch.get("raw_messages", [])
    }
    total_items = len(batch["items"])

    for index, item in enumerate(batch["items"], start=1):
        if item["review_state"] == "reviewed":
            continue

        while True:
            _print_review_item(index, total_items, item, raw_messages.get(item["message_id"], {}), output)
            choice = input_stream.readline().strip().lower()
            if choice == "a":
                action = {"type": "approve"}
            elif choice == "e":
                action = {"type": "edit", "final_labels": _prompt_for_labels(input_stream, output)}
            elif choice == "r":
                action = {"type": "reject"}
            elif choice == "u":
                action = {"type": "edit", "final_labels": []}
            elif choice == "s":
                output.write("Skipped for now.\n\n")
                break
            elif choice in {"?", "labels"}:
                _print_allowed_labels(output)
                output.write("\n")
                continue
            elif choice == "q":
                return "quit"
            else:
                output.write("Unrecognized option. Skipped for now.\n\n")
                break
            review_loop.review_message(stored_batch["batch_id"], item["message_id"], action)
            output.write("\n")
            break

    return "complete"


def _collect_dry_run_items(items: list[dict]) -> list[dict]:
    return [
        {
            "message_id": item["message_id"],
            "final_labels": list(item.get("final_labels") or []),
        }
        for item in items
        if item.get("review_state") == "reviewed" and item.get("final_labels")
    ]


def _print_review_item(index: int, total_items: int, item: dict, raw_message: dict, output: TextIO) -> None:
    formatted_date = _format_date(item["date"])
    snippet = raw_message.get("snippet") or item.get("body") or item.get("subject", "")
    suggested_labels = [_gmail_label_name(label) for label in item.get("applied_labels", [])]

    output.write(f"Item {index} of {total_items}\n")
    output.write(f"Message ID: {item['message_id']}\n")
    output.write(f"From: {item['sender']}\n")
    output.write(f"Date: {formatted_date}\n")
    output.write(f"Subject: {item['subject']}\n\n")
    output.write("Snippet:\n")
    output.write(f"{snippet}\n\n")
    output.write(f"{'Suggested label' if len(suggested_labels) == 1 else 'Suggested labels'}:\n")
    output.write(f"{', '.join(suggested_labels) if suggested_labels else '(none)'}\n\n")
    output.write("Why:\n")
    output.write(f"{item['interpretation']}\n\n")
    output.write("Current decision:\n")
    output.write(f"{item['review_state']}\n\n")
    output.write("Options:\n")
    output.write("[a] approve suggested label\n")
    output.write("[e] edit label\n")
    output.write("[r] reject / do not write\n")
    output.write("[u] mark unlabeled\n")
    output.write("[s] skip for now\n")
    output.write("[q] quit without applying writes\n")
    output.write("[?] or [labels] show allowed labels\n")
    output.write("\n")
    _print_allowed_labels(output)


def _prompt_for_labels(input_stream: TextIO, output: TextIO) -> list[str]:
    while True:
        output.write("Enter label names or numbers separated by commas:\n")
        output.write("Type ? or labels to list allowed labels again.\n")
        raw_value = input_stream.readline().strip()
        if not raw_value:
            return []

        if raw_value.lower() in {"?", "labels"}:
            _print_allowed_labels(output)
            output.write("\n")
            continue

        parsed_labels, error_message = _parse_label_selection(raw_value)
        if error_message is not None:
            output.write(f"{error_message}\n")
            output.write("Choose only from the allowed EA labels.\n\n")
            continue
        return parsed_labels


def _print_dry_run(items: list[dict], dry_run_items: list[dict], output: TextIO) -> None:
    rejected_count = sum(1 for item in items if item.get("review_action") == "reject")
    unlabeled_count = sum(
        1
        for item in items
        if item.get("review_state") == "reviewed"
        and not item.get("final_labels")
        and item.get("review_action") != "reject"
    )
    label_counts = Counter(
        _gmail_label_name(label)
        for item in dry_run_items
        for label in item["final_labels"]
    )

    output.write("Dry run summary:\n")
    output.write(f"Approved writes: {len(dry_run_items)}\n")
    output.write(f"Rejected: {rejected_count}\n")
    output.write(f"Unlabeled: {unlabeled_count}\n\n")
    output.write("Labels to create/apply:\n")
    if label_counts:
        for label_name, count in sorted(label_counts.items()):
            noun = "message" if count == 1 else "messages"
            output.write(f"{label_name}: {count} {noun}\n")
    else:
        output.write("(none)\n")
    output.write("\n")
    output.write("No Gmail writes have happened yet.\n")
    output.write("Type APPLY to apply these labels to Gmail.\n")


def _format_date(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()


def _gmail_label_name(label: str) -> str:
    return gmail_label_name(label)


def _print_allowed_labels(output: TextIO) -> None:
    output.write("Allowed labels:\n")
    for index, label in enumerate(allowed_gmail_labels(), start=1):
        output.write(f"{index}. {label}\n")


def _parse_label_selection(raw_value: str) -> tuple[list[str], str | None]:
    labels: list[str] = []
    for token in [part.strip() for part in raw_value.split(",") if part.strip()]:
        internal_label, error_message = _parse_single_label_token(token)
        if error_message is not None:
            return [], error_message
        if internal_label not in labels:
            labels.append(internal_label)
    return labels, None


def _parse_single_label_token(token: str) -> tuple[str | None, str | None]:
    if token.isdigit():
        index = int(token)
        if 1 <= index <= len(CANONICAL_LABEL_ORDER):
            return CANONICAL_LABEL_ORDER[index - 1], None
        return None, f"Unknown label number: {token}"

    lowered = token.lower()
    if "/" in token and not lowered.startswith("ea/"):
        return None, "Only EA/ labels are allowed here."

    internal_label = DISPLAY_LABEL_TO_INTERNAL.get(lowered)
    if internal_label is not None:
        return internal_label, None

    return None, f"Unknown label: {token}"


def _default_gmail_client_factory(
    account_id: str,
    credentials_dir: Path,
    client_secret_path: Path | None,
    required_scope: str,
) -> object:
    return LiveGmailClient.from_local_oauth(
        account_id,
        credentials_dir,
        client_secret_path=client_secret_path,
        scope=required_scope,
    )


def _resolve_path(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _resolve_optional_path(path: Path | None, repo_root: Path) -> Path | None:
    if path is None:
        return None
    return _resolve_path(path, repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
