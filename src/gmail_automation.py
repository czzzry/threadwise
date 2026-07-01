from dataclasses import dataclass
from pathlib import Path

from src.daily_report import build_gmail_daily_report, write_daily_report
from src.gmail_attention import DEFAULT_MAX_EVALUATED_MESSAGES, evaluate_gmail_attention
from src.gmail_batch_review_store import GmailBatchReviewStore
from src.gmail_fetcher import GmailBatchFetcher
from src.gmail_writer import MockGmailLabelWriter
from src.label_taxonomy import gmail_label_name
from src.local_artifacts import load_json_or_default, write_status_path


@dataclass
class AutoApplyPlan:
    batch_id: str
    account_id: str
    stored_batch: dict
    pending_count: int
    auto_items: list[dict]


@dataclass
class GmailMutationResult:
    write_summary: dict
    inbox_summary: dict


@dataclass
class DailyGmailRunResult:
    batch_id: str
    account_id: str
    fetched_count: int
    label_write_count: int
    inbox_removal_count: int
    unlabeled_exceptions: list[dict]
    report: dict


@dataclass
class RetryFailedWritesResult:
    retried_items: list[dict]
    blocked_messages: list[str]
    retried_successfully_count: int
    still_failed_count: int


def build_gmail_label_writer(gmail_client, storage_dir: Path) -> MockGmailLabelWriter:
    return MockGmailLabelWriter(
        gmail_client=gmail_client,
        storage_dir=storage_dir,
        label_name_resolver=gmail_label_name,
    )


def load_write_status_map(storage_dir: Path, batch_id: str) -> dict[str, str]:
    return load_json_or_default(write_status_path(storage_dir, batch_id), {})


def auto_approve_items(items: list[dict], write_status_map: dict[str, str]) -> list[dict]:
    auto_items: list[dict] = []
    for item in items:
        labels = list(item.get("applied_labels") or [])
        final_labels = list(item.get("final_labels") or [])
        if item.get("review_state") == "reviewed":
            if item.get("review_action") != "auto-approve":
                continue
            if write_status_map.get(item["message_id"]) == "applied":
                continue
            if not final_labels:
                continue
            auto_items.append(item)
            continue
        if not labels:
            continue
        item["review_state"] = "reviewed"
        item["review_action"] = "auto-approve"
        item["final_labels"] = list(labels)
        auto_items.append(item)
    return auto_items


def prepare_auto_apply_batch(storage_dir: Path, batch_id: str) -> AutoApplyPlan:
    batch_store = GmailBatchReviewStore(storage_dir)
    stored_batch = batch_store.load_batch(batch_id)
    pending_count = sum(1 for item in stored_batch["items"] if item.get("review_state") != "reviewed")
    write_status_map = load_write_status_map(storage_dir, batch_id)
    auto_items = auto_approve_items(stored_batch["items"], write_status_map)
    return AutoApplyPlan(
        batch_id=batch_id,
        account_id=stored_batch["account_id"],
        stored_batch=stored_batch,
        pending_count=pending_count,
        auto_items=auto_items,
    )


def execute_auto_apply_plan(
    storage_dir: Path,
    plan: AutoApplyPlan,
    gmail_client,
) -> GmailMutationResult:
    GmailBatchReviewStore(storage_dir).persist_reviewed_items(plan.batch_id, plan.stored_batch["items"])
    writer = build_gmail_label_writer(gmail_client, storage_dir)
    write_summary = writer.write_reviewed_labels(plan.batch_id, plan.auto_items)
    inbox_summary = writer.remove_inbox_for_low_value_messages(plan.batch_id, plan.auto_items)
    return GmailMutationResult(write_summary=write_summary, inbox_summary=inbox_summary)


def summarize_inbox_removal_candidates(
    batch_id: str,
    items: list[dict],
    writer: MockGmailLabelWriter,
) -> tuple[int, int, int]:
    eligible_count = 0
    skipped_count = 0
    ineligible_count = 0
    for item in items:
        final_labels = list(item.get("final_labels") or [])
        if item.get("review_state") != "reviewed" or not is_inbox_removal_label_eligible(final_labels):
            ineligible_count += 1
            continue
        if writer.get_write_status(batch_id, item["message_id"]) != "applied":
            skipped_count += 1
            continue
        eligible_count += 1
    return eligible_count, skipped_count, ineligible_count


def is_inbox_removal_label_eligible(final_labels: list[str]) -> bool:
    return "promotions" in final_labels or "spam-low-value" in final_labels


def failed_write_items(items: list[dict], writer: MockGmailLabelWriter, batch_id: str) -> list[dict]:
    failed_items: list[dict] = []
    for item in items:
        if writer.get_write_status(batch_id, item["message_id"]) != "failed":
            continue
        failed_items.append(item)
    return failed_items


def retry_failed_writes(
    batch_id: str,
    items: list[dict],
    writer: MockGmailLabelWriter,
) -> RetryFailedWritesResult:
    retried_items: list[dict] = []
    blocked_messages: list[str] = []
    for item in failed_write_items(items, writer, batch_id):
        try:
            writer.retry_failed_write(batch_id, item)
            retried_items.append(item)
        except ValueError as exc:
            blocked_messages.append(str(exc))

    return RetryFailedWritesResult(
        retried_items=retried_items,
        blocked_messages=blocked_messages,
        retried_successfully_count=sum(
            1 for item in retried_items
            if writer.get_write_status(batch_id, item["message_id"]) == "applied"
        ),
        still_failed_count=sum(
            1 for item in retried_items
            if writer.get_write_status(batch_id, item["message_id"]) == "failed"
        ),
    )


def run_daily_gmail_automation(
    *,
    account_id: str,
    batch_size: int,
    storage_dir: Path,
    gmail_client,
    attention_model_client: object | None = None,
    attention_max_evaluated_messages: int = DEFAULT_MAX_EVALUATED_MESSAGES,
) -> DailyGmailRunResult | None:
    fetcher = GmailBatchFetcher(gmail_client=gmail_client, storage_dir=storage_dir)
    review_queue = fetcher.fetch_gmail_batch(account_id, batch_size)
    if review_queue is None:
        return None

    batch_store = GmailBatchReviewStore(storage_dir)
    stored_batch = batch_store.load_batch(review_queue["batch_id"])
    write_status_map = load_write_status_map(storage_dir, review_queue["batch_id"])
    auto_items = auto_approve_items(stored_batch["items"], write_status_map)
    batch_store.persist_reviewed_items(review_queue["batch_id"], stored_batch["items"])

    writer = build_gmail_label_writer(gmail_client, storage_dir)
    write_summary = writer.write_reviewed_labels(review_queue["batch_id"], auto_items)
    inbox_summary = writer.remove_inbox_for_low_value_messages(review_queue["batch_id"], auto_items)
    unlabeled_exceptions = [
        item for item in stored_batch["items"] if item.get("review_state") != "reviewed"
    ]
    attention = None
    if attention_model_client is not None:
        attention = evaluate_gmail_attention(
            storage_dir=storage_dir,
            latest_batch_id=review_queue["batch_id"],
            model_client=attention_model_client,
            max_evaluated_messages=attention_max_evaluated_messages,
        )
    report = build_gmail_daily_report(
        storage_dir,
        review_queue["batch_id"],
        stored_batch["account_id"],
        len(review_queue["items"]),
        write_summary["applied_count"],
        inbox_summary["applied_count"],
        unlabeled_exceptions,
        attention=attention,
    )
    write_daily_report(storage_dir, review_queue["batch_id"], report)
    return DailyGmailRunResult(
        batch_id=review_queue["batch_id"],
        account_id=stored_batch["account_id"],
        fetched_count=len(review_queue["items"]),
        label_write_count=write_summary["applied_count"],
        inbox_removal_count=inbox_summary["applied_count"],
        unlabeled_exceptions=unlabeled_exceptions,
        report=report,
    )
