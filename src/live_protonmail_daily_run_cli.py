import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from src.cli_paths import resolve_optional_path, resolve_path
from src.daily_report import build_protonmail_daily_report, suggested_label_counts, write_daily_report
from src.fixture_classifier import CLASSIFIER_POLICY_VERSION, FixtureBatchClassifier
from src.gmail_initial_classifier import configure_initial_classifier
from src.label_taxonomy import gmail_label_name
from src.live_protonmail_client import LiveProtonMailClient, SetupError
from src.live_protonmail_fetch_cli import DEFAULT_CREDENTIALS_DIR, DEFAULT_STORAGE_DIR
from src.protonmail_fetcher import ProtonMailBatchFetcher
from src.protonmail_message_normalizer import normalize_protonmail_message
from src.proton_review_console import sync_proton_review_ledger
from src.stored_batch_review_store import StoredBatchReviewStore
from src.trusted_sender_store import TrustedSenderStore


PROTON_REVIEW_URL = "https://mail.proton.me/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch and classify ProtonMail messages for one inbox batch."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--bridge-config-path", type=Path)
    parser.add_argument("--batch-size", type=int, default=50)
    return parser


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    cwd: Path | None = None,
    protonmail_client_factory=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    repo_root = cwd or Path.cwd()
    storage_dir = resolve_path(args.storage_dir, repo_root)
    credentials_dir = resolve_path(args.credentials_dir, repo_root)
    bridge_config_path = resolve_optional_path(args.bridge_config_path, repo_root)

    storage_dir.mkdir(parents=True, exist_ok=True)
    credentials_dir.mkdir(parents=True, exist_ok=True)

    selected_model = str(os.environ.get("THREADWISE_CLASSIFICATION_MODEL") or "").strip()
    classifier, classifier_status = configure_initial_classifier(
        selected_model,
        deterministic_classifier=FixtureBatchClassifier(
            fixtures_dir=Path("."),
            trusted_personal_senders=TrustedSenderStore(storage_dir).load_or_rebuild(),
        ),
    )
    if selected_model and classifier is None:
        reason = str(classifier_status.get("reason") or "configuration-unavailable")
        error_output.write(
            "Threadwise model classification is not ready "
            f"({reason}). Check the private API configuration before the Proton run.\n"
        )
        return 2

    protonmail_client_factory = protonmail_client_factory or _default_protonmail_client_factory

    try:
        protonmail_client = protonmail_client_factory(args.account_id, credentials_dir, bridge_config_path)
        result = run_live_protonmail_daily_batch(
            account_id=args.account_id,
            batch_size=args.batch_size,
            storage_dir=storage_dir,
            protonmail_client=protonmail_client,
            classifier=classifier,
        )
        if result is None:
            output.write("No new messages found.\n")
            return 0
        if result.get("outcome") == "repaired_existing":
            output.write(f"Rechecked: {result['reprocessed_count']} previously unresolved messages\n")
            output.write(f"Provider label writes: {result['auto_applied_count']} (Inbox preserved and verified)\n")
            output.write(f"Needs a label decision: {len(result['unlabeled_exceptions'])}\n")
            output.write(f"Provider write verification failures for review: {result['write_failure_count']}\n")
            return 0
        _print_summary(
            result["batch_id"],
            result["account_id"],
            result["fetched_count"],
            result["classified_count"],
            result["unlabeled_exceptions"],
            result["auto_applied_count"],
            result["write_failure_count"],
            storage_dir,
            output,
        )
        return 0
    except SetupError as exc:
        error_output.write(f"{exc}\n")
        return 2


def run_live_protonmail_daily_batch(
    *,
    account_id: str,
    batch_size: int,
    storage_dir: Path,
    protonmail_client: object,
    classifier: object | None = None,
) -> dict | None:
    """Repair stale unresolved items, then incrementally classify new Proton messages."""
    repair = repair_stored_low_confidence_messages(
        account_id=account_id,
        batch_size=batch_size,
        storage_dir=storage_dir,
        protonmail_client=protonmail_client,
        classifier=classifier,
    )
    fetcher = ProtonMailBatchFetcher(
        protonmail_client=protonmail_client,
        storage_dir=storage_dir,
        classifier=classifier,
    )
    review_queue = fetcher.fetch_protonmail_batch(account_id, batch_size)
    if review_queue is None:
        if not repair["reprocessed_count"]:
            return None
        return {
            "outcome": "repaired_existing",
            "batch_id": "",
            "account_id": account_id,
            "fetched_count": 0,
            "reprocessed_count": repair["reprocessed_count"],
            "classified_count": repair["classified_count"],
            "unlabeled_exceptions": repair["unlabeled_exceptions"],
            "auto_applied_count": repair["auto_applied_count"],
            "write_failure_count": repair["write_failure_count"],
        }

    batch_id = str(review_queue["batch_id"])
    batch_store = StoredBatchReviewStore(storage_dir)
    stored_batch = batch_store.load_batch(batch_id)
    auto_applied_count, write_failure_count = _auto_apply_confident_labels(
        protonmail_client,
        stored_batch,
    )
    batch_store.persist_reviewed_items(batch_id, stored_batch["items"])
    sync_proton_review_ledger(storage_dir, batch_id)
    unlabeled_exceptions = [
        item for item in stored_batch["items"] if not item.get("applied_labels")
    ]
    classified_count = len(stored_batch["items"]) - len(unlabeled_exceptions)
    report = build_protonmail_daily_report(
        storage_dir,
        batch_id,
        str(stored_batch["account_id"]),
        len(review_queue["items"]),
        classified_count,
        unlabeled_exceptions,
        auto_applied_count,
    )
    write_daily_report(storage_dir, batch_id, report)
    return {
        "batch_id": batch_id,
        "outcome": "completed",
        "account_id": str(stored_batch["account_id"]),
        "fetched_count": len(review_queue["items"]),
        "classified_count": classified_count,
        "unlabeled_exceptions": unlabeled_exceptions,
        "auto_applied_count": auto_applied_count,
        "write_failure_count": write_failure_count,
        "reprocessed_count": repair["reprocessed_count"],
    }


def repair_stored_low_confidence_messages(
    *,
    account_id: str,
    batch_size: int,
    storage_dir: Path,
    protonmail_client: object,
    classifier: object | None = None,
) -> dict:
    """Reclassify bounded unresolved local items when the classifier policy changes."""
    candidates: list[dict] = []
    batch_store = StoredBatchReviewStore(storage_dir)
    batch_paths = sorted(
        (storage_dir / "batches").glob(f"{account_id}-batch-*.json"),
        key=_batch_number,
        reverse=True,
    )
    for batch_path in batch_paths:
        batch = json.loads(batch_path.read_text())
        if batch.get("provider") != "protonmail":
            continue
        raw_by_id = {
            str(message.get("id") or ""): message
            for message in batch.get("raw_messages") or []
        }
        for item in batch.get("items") or []:
            if item.get("applied_labels") or item.get("review_state") == "reviewed":
                continue
            if item.get("confidence_band") != "low":
                continue
            if (
                classifier is None
                and item.get("classifier_policy_version") == CLASSIFIER_POLICY_VERSION
            ):
                continue
            raw_message = raw_by_id.get(str(item.get("message_id") or ""))
            if raw_message:
                candidates.append(
                    {
                        "batch_id": str(batch.get("batch_id") or batch_path.stem),
                        "batch": batch,
                        "raw_message": raw_message,
                    }
                )
            if len(candidates) >= batch_size:
                break
        if len(candidates) >= batch_size:
            break

    if not candidates:
        return _empty_repair_result()

    live_ids = set(protonmail_client.list_messages(max_results=max(10_000, len(candidates))))
    candidates = [
        candidate
        for candidate in candidates
        if str(candidate["raw_message"].get("id")) in live_ids
    ]
    if not candidates:
        return _empty_repair_result()

    fetcher = ProtonMailBatchFetcher(
        protonmail_client=protonmail_client,
        storage_dir=storage_dir,
    )
    active_classifier = classifier or FixtureBatchClassifier(
        fixtures_dir=Path("."),
        trusted_personal_senders=TrustedSenderStore(storage_dir).load_or_rebuild(),
    )
    by_batch: dict[str, list[dict]] = {}
    for candidate in candidates:
        by_batch.setdefault(candidate["batch_id"], []).append(candidate)

    reprocessed_count = 0
    classified_count = 0
    auto_applied_count = 0
    write_failure_count = 0
    unlabeled_exceptions: list[dict] = []
    for batch_id, batch_candidates in by_batch.items():
        normalized = [
            normalize_protonmail_message(account_id, candidate["raw_message"])
            for candidate in batch_candidates
        ]
        review_queue = active_classifier.classify_messages(batch_id, normalized)
        review_queue = fetcher._postprocess_review_queue(review_queue, normalized)
        classified_by_id = {
            str(item["message_id"]): item
            for item in review_queue["items"]
        }
        updated_items = list(batch_candidates[0]["batch"].get("items") or [])
        updated_by_id = {
            str(item.get("message_id") or ""): item
            for item in updated_items
        }
        for candidate in batch_candidates:
            message_id = str(candidate["raw_message"].get("id") or "")
            replacement = classified_by_id.get(message_id)
            if replacement is None:
                continue
            updated_by_id[message_id] = replacement
            reprocessed_count += 1
            if replacement.get("applied_labels"):
                classified_count += 1
            else:
                unlabeled_exceptions.append(replacement)

        updated_batch = dict(batch_candidates[0]["batch"])
        updated_batch["items"] = list(updated_by_id.values())
        repair_batch = {
            "raw_messages": updated_batch.get("raw_messages") or [],
            "items": [
                updated_by_id[str(candidate["raw_message"].get("id") or "")]
                for candidate in batch_candidates
                if str(candidate["raw_message"].get("id") or "") in updated_by_id
            ],
        }
        applied, failures = _auto_apply_confident_labels(protonmail_client, repair_batch)
        auto_applied_count += applied
        write_failure_count += failures
        batch_store.persist_reviewed_items(batch_id, updated_batch["items"])
        sync_proton_review_ledger(storage_dir, batch_id)

    return {
        "reprocessed_count": reprocessed_count,
        "classified_count": classified_count,
        "auto_applied_count": auto_applied_count,
        "write_failure_count": write_failure_count,
        "unlabeled_exceptions": unlabeled_exceptions,
    }


def _empty_repair_result() -> dict:
    return {
        "reprocessed_count": 0,
        "classified_count": 0,
        "auto_applied_count": 0,
        "write_failure_count": 0,
        "unlabeled_exceptions": [],
    }


def _batch_number(path: Path) -> int:
    suffix = path.stem.rsplit("-batch-", 1)[-1]
    return int(suffix) if suffix.isdigit() else 0


def _print_summary(
    batch_id: str,
    account_id: str,
    fetched_count: int,
    classified_count: int,
    unlabeled_exceptions: list[dict],
    auto_applied_count: int,
    write_failure_count: int,
    storage_dir: Path,
    output: TextIO,
) -> None:
    output.write(f"Batch: {batch_id}\n")
    output.write(f"Fetched: {fetched_count}\n")
    output.write(f"Provider label writes: {auto_applied_count} (Inbox preserved and verified)\n")
    output.write("INBOX removals: 0\n")
    output.write(f"Suggested labels ready for review: {classified_count}\n")
    output.write(f"Needs a label decision: {len(unlabeled_exceptions)}\n")
    output.write(f"Provider write verification failures for review: {write_failure_count}\n")
    output.write(f"Open Threadwise in Proton Mail: {PROTON_REVIEW_URL}\n")
    for item in unlabeled_exceptions:
        output.write(f"{item['sender']} || {item['subject']}\n")


def _auto_apply_confident_labels(protonmail_client: object, stored_batch: dict) -> tuple[int, int]:
    """Apply every available Proton suggestion and keep uncertain ones reviewable."""
    raw_messages_by_id = {
        str(message.get("id") or ""): message
        for message in stored_batch.get("raw_messages") or []
    }
    applied_count = 0
    failure_count = 0
    for item in stored_batch.get("items") or []:
        labels = [str(label) for label in item.get("applied_labels") or [] if str(label)]
        if not labels:
            item["provider_write_state"] = "not-attempted"
            continue

        message_id = str(item.get("message_id") or "")
        rfc_message_id = str(raw_messages_by_id.get(message_id, {}).get("rfc_message_id") or "").strip()
        try:
            if not message_id or not rfc_message_id:
                raise ValueError("Missing Proton message identity for label verification.")
            for internal_label in labels:
                label_name = gmail_label_name(internal_label)
                write_result = protonmail_client.apply_label(message_id, label_name)
                if not write_result.get("inbox_preserved") or write_result.get("destructive_actions"):
                    raise RuntimeError("Proton label write violated the label-only safety contract.")
                if not protonmail_client.message_has_label(rfc_message_id, label_name):
                    raise RuntimeError("Proton did not confirm the label after the write.")
            item["provider_write_state"] = "applied"
            applied_count += 1
        except Exception as exc:
            item["provider_write_state"] = "failed"
            item["provider_write_error"] = str(exc)
            failure_count += 1
    return applied_count, failure_count


def _suggested_label_counts_for_report(storage_dir: Path, batch_id: str) -> dict[str, int]:
    return suggested_label_counts(storage_dir, batch_id)


def _default_protonmail_client_factory(
    account_id: str,
    credentials_dir: Path,
    bridge_config_path: Path | None,
) -> object:
    return LiveProtonMailClient.from_bridge_config(
        account_id,
        credentials_dir,
        bridge_config_path=bridge_config_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
