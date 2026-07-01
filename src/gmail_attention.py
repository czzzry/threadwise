from pathlib import Path
from typing import Any

from src.daily_report import ATTENTION_LEVELS, build_attention_section
from src.local_artifacts import batch_path, load_json


ATTENTION_CATEGORIES = (
    "travel",
    "bill_due",
    "account_risk",
    "security",
    "reply_deadline",
    "appointment",
    "job_opportunity",
)
DEFAULT_MAX_EVALUATED_MESSAGES = 50
DEFAULT_COMPACT_BODY_CHARS = 500
HIGH_CONSEQUENCE_CATEGORIES = {
    "travel",
    "bill_due",
    "account_risk",
    "security",
    "reply_deadline",
    "appointment",
    "job_opportunity",
}


def evaluate_gmail_attention(
    *,
    storage_dir: Path,
    latest_batch_id: str,
    model_client: object,
    max_evaluated_messages: int = DEFAULT_MAX_EVALUATED_MESSAGES,
    compact_body_chars: int = DEFAULT_COMPACT_BODY_CHARS,
) -> dict:
    try:
        evaluation_context = _collect_evaluation_context(
            storage_dir=storage_dir,
            latest_batch_id=latest_batch_id,
            max_evaluated_messages=max_evaluated_messages,
        )
        payloads = [
            _compact_payload(candidate, compact_body_chars=compact_body_chars)
            for candidate in evaluation_context["candidates"]
        ]
        response = _evaluate_compact_batch(model_client, payloads)
        items, response_model, usage = _parse_batch_response(response)
        normalized_items = [
            _normalize_attention_item(item, evaluation_context["candidate_by_id"])
            for item in items
        ]
        normalized_items = _run_full_body_second_passes(
            model_client=model_client,
            items=normalized_items,
            candidate_by_id=evaluation_context["candidate_by_id"],
        )
        return build_attention_section(
            evaluated_message_count=len(payloads),
            lookback_window={
                "latest_batch_id": latest_batch_id,
                "stored_lookback_batch_ids": evaluation_context["stored_lookback_batch_ids"],
                "max_evaluated_messages": max_evaluated_messages,
            },
            model=response_model or _model_metadata(model_client),
            usage=usage,
            items=normalized_items,
        )
    except Exception as exc:
        return build_attention_section(
            evaluated_message_count=0,
            lookback_window={
                "latest_batch_id": latest_batch_id,
                "stored_lookback_batch_ids": [],
                "max_evaluated_messages": max_evaluated_messages,
            },
            model={**_model_metadata(model_client), "error": str(exc), "status": "failed_soft"},
            usage={},
            items=[],
        )


def _collect_evaluation_context(
    *,
    storage_dir: Path,
    latest_batch_id: str,
    max_evaluated_messages: int,
) -> dict:
    latest_batch = load_json(batch_path(storage_dir, latest_batch_id))
    account_id = latest_batch.get("account_id", "")
    candidates: list[dict] = []
    stored_lookback_batch_ids: list[str] = []
    seen_message_ids: set[str] = set()

    _append_candidates(
        candidates,
        latest_batch,
        seen_message_ids=seen_message_ids,
        remaining=max_evaluated_messages - len(candidates),
    )

    for lookback_batch in _stored_lookback_batches(storage_dir, account_id, latest_batch_id):
        if len(candidates) >= max_evaluated_messages:
            break
        before_count = len(candidates)
        _append_candidates(
            candidates,
            lookback_batch,
            seen_message_ids=seen_message_ids,
            remaining=max_evaluated_messages - len(candidates),
        )
        if len(candidates) > before_count:
            stored_lookback_batch_ids.append(lookback_batch.get("batch_id", ""))

    candidate_by_id = {candidate["message_id"]: candidate for candidate in candidates}
    return {
        "candidates": candidates,
        "candidate_by_id": candidate_by_id,
        "stored_lookback_batch_ids": stored_lookback_batch_ids,
    }


def _append_candidates(
    candidates: list[dict],
    batch: dict,
    *,
    seen_message_ids: set[str],
    remaining: int,
) -> None:
    if remaining <= 0:
        return
    target_count = len(candidates) + remaining
    thread_ids = _thread_ids_by_message_id(batch)
    for item in batch.get("items", []):
        message_id = item.get("message_id", "")
        if not message_id or message_id in seen_message_ids:
            continue
        candidate = dict(item)
        candidate["batch_id"] = batch.get("batch_id", "")
        if not candidate.get("thread_id"):
            candidate["thread_id"] = thread_ids.get(message_id, "")
        candidates.append(candidate)
        seen_message_ids.add(message_id)
        if len(candidates) >= target_count:
            return


def _stored_lookback_batches(storage_dir: Path, account_id: str, latest_batch_id: str) -> list[dict]:
    batches_dir = storage_dir / "batches"
    if not batches_dir.exists():
        return []

    batches: list[dict] = []
    for path in batches_dir.glob(f"{account_id}-batch-*.json"):
        if path.stem == latest_batch_id:
            continue
        batch = load_json(path)
        if batch.get("provider", "gmail") != "gmail":
            continue
        if batch.get("account_id") != account_id:
            continue
        batches.append(batch)
    return sorted(batches, key=lambda batch: _batch_number(batch.get("batch_id", "")), reverse=True)


def _batch_number(batch_id: str) -> int:
    suffix = batch_id.rsplit("-batch-", 1)[-1]
    return int(suffix) if suffix.isdigit() else 0


def _thread_ids_by_message_id(batch: dict) -> dict[str, str]:
    return {
        raw_message.get("id", ""): raw_message.get("threadId", "")
        for raw_message in batch.get("raw_messages", [])
        if raw_message.get("id")
    }


def _compact_payload(candidate: dict, *, compact_body_chars: int) -> dict:
    return {
        "message_id": candidate.get("message_id", ""),
        "thread_id": candidate.get("thread_id", ""),
        "batch_id": candidate.get("batch_id", ""),
        "sender": candidate.get("sender", ""),
        "subject": candidate.get("subject", ""),
        "date": candidate.get("date", ""),
        "snippet": candidate.get("snippet", ""),
        "body_excerpt": (candidate.get("body") or "")[:compact_body_chars],
        "current_labels": list(candidate.get("final_labels") or candidate.get("applied_labels") or []),
        "gmail_state": {
            "label_ids": list(candidate.get("gmail_label_ids") or []),
        },
        "local_state": {
            "review_state": candidate.get("review_state", ""),
            "review_action": candidate.get("review_action", ""),
            "final_labels": list(candidate.get("final_labels") or []),
            "applied_labels": list(candidate.get("applied_labels") or []),
        },
        "allowed_levels": list(ATTENTION_LEVELS),
        "allowed_categories": list(ATTENTION_CATEGORIES),
    }


def _evaluate_compact_batch(model_client: object, payloads: list[dict]) -> Any:
    if hasattr(model_client, "evaluate_gmail_attention_batch"):
        return model_client.evaluate_gmail_attention_batch(payloads)
    if callable(model_client):
        return model_client(payloads)
    raise TypeError("attention model client must expose evaluate_gmail_attention_batch")


def _parse_batch_response(response: Any) -> tuple[list[dict], dict, dict]:
    if isinstance(response, list):
        return response, {}, {}
    if isinstance(response, dict):
        return (
            list(response.get("items") or []),
            dict(response.get("model") or {}),
            dict(response.get("usage") or {}),
        )
    raise TypeError("attention model response must be a list or object")


def _normalize_attention_item(item: dict, candidate_by_id: dict[str, dict]) -> dict:
    message_id = item.get("message_id", "")
    candidate = candidate_by_id.get(message_id, {})
    level = item.get("level", "insufficient_context")
    category = item.get("category", "")
    return {
        "message_id": message_id,
        "thread_id": item.get("thread_id") or candidate.get("thread_id", ""),
        "level": level if level in ATTENTION_LEVELS else "insufficient_context",
        "category": category if category in ATTENTION_CATEGORIES else "",
        "reason": item.get("reason", ""),
        "evidence": item.get("evidence", ""),
        "source": item.get("source", "llm_compact"),
        "handled_state": item.get("handled_state", "unknown"),
        "feedback_state": item.get("feedback_state", "unset"),
        "full_body_used": bool(item.get("full_body_used", False)),
    }


def _run_full_body_second_passes(
    *,
    model_client: object,
    items: list[dict],
    candidate_by_id: dict[str, dict],
) -> list[dict]:
    if not hasattr(model_client, "evaluate_gmail_attention_full_body"):
        return items

    expanded_items: list[dict] = []
    for item in items:
        if not _needs_full_body_second_pass(item):
            expanded_items.append(item)
            continue
        candidate = candidate_by_id.get(item["message_id"])
        if not candidate:
            expanded_items.append(item)
            continue
        try:
            full_response = model_client.evaluate_gmail_attention_full_body(_full_body_payload(candidate))
        except Exception:
            expanded_items.append(item)
            continue
        normalized = _normalize_attention_item(full_response, candidate_by_id)
        normalized["source"] = full_response.get("source", "llm_full_body")
        normalized["full_body_used"] = True
        expanded_items.append(normalized)
    return expanded_items


def _needs_full_body_second_pass(item: dict) -> bool:
    return (
        item.get("level") == "insufficient_context"
        and item.get("category") in HIGH_CONSEQUENCE_CATEGORIES
        and not item.get("full_body_used")
    )


def _full_body_payload(candidate: dict) -> dict:
    return {
        "message_id": candidate.get("message_id", ""),
        "thread_id": candidate.get("thread_id", ""),
        "sender": candidate.get("sender", ""),
        "subject": candidate.get("subject", ""),
        "date": candidate.get("date", ""),
        "snippet": candidate.get("snippet", ""),
        "body": candidate.get("body", ""),
        "current_labels": list(candidate.get("final_labels") or candidate.get("applied_labels") or []),
        "allowed_levels": list(ATTENTION_LEVELS),
        "allowed_categories": list(ATTENTION_CATEGORIES),
    }


def _model_metadata(model_client: object) -> dict:
    metadata = getattr(model_client, "model_metadata", {})
    return dict(metadata) if isinstance(metadata, dict) else {}
