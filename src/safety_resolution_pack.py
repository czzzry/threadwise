from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json, safety_resolution_pack_path, write_json
from src.memory_proposal_store import load_storage_items
from src.safety_disposition_store import SAFETY_SIGNAL_PHRASES, SAFETY_SIGNAL_TOKENS, matches_safety_context
from src.sender_utils import normalized_sender_email


LEGITIMATE_BILLING_DOMAINS = {
    "noreply@po.atlassian.net",
    "support@taxfix.de",
}


def build_safety_resolution_pack(
    *,
    report: dict,
    provider_storage_dirs: list[tuple[str, Path]],
) -> dict:
    provider_items = {
        provider: load_storage_items(storage_dir, provider)
        for provider, storage_dir in provider_storage_dirs
    }
    provider_indexes = {
        provider: {
            (item.get("batch_id", ""), item.get("message_id", "")): item
            for item in items
        }
        for provider, items in provider_items.items()
    }

    candidates_by_key: dict[tuple[str, str, str], dict] = {}
    for provider, provider_report in report.get("providers", {}).items():
        for outcome in provider_report.get("outcomes", []):
            if outcome.get("decision", {}).get("safety_lane") != "suspicious":
                continue
            if outcome.get("decision_provenance", {}).get("safety_memory_used"):
                continue
            storage_item = provider_indexes.get(provider, {}).get((outcome.get("batch_id", ""), outcome.get("message_id", "")))
            if storage_item is None:
                continue
            suggestion = _suggest_resolution(storage_item)
            group_key = (provider, suggestion["disposition"], suggestion["group_key"])
            candidate = candidates_by_key.get(group_key)
            if candidate is None:
                candidate = {
                    "provider": provider,
                    "account_id": storage_item.get("account_id", ""),
                    "suggested_disposition": suggestion["disposition"],
                    "suggested_scope": suggestion["scope"],
                    "group_key": suggestion["group_key"],
                    "reason": suggestion["reason"],
                    "message_count": 0,
                    "unique_sender_count": 0,
                    "senders": [],
                    "message_refs": [],
                    "example_subjects": [],
                }
                candidates_by_key[group_key] = candidate
            candidate["message_count"] += 1
            sender = storage_item.get("sender", "")
            if sender and sender not in candidate["senders"]:
                candidate["senders"].append(sender)
            candidate["message_refs"].append(
                {
                    "batch_id": storage_item.get("batch_id", ""),
                    "message_id": storage_item.get("message_id", ""),
                    "sender": sender,
                    "subject": storage_item.get("subject", ""),
                }
            )
            subject = storage_item.get("subject", "")
            if subject and subject not in candidate["example_subjects"]:
                candidate["example_subjects"].append(subject)

    candidates = []
    for candidate in candidates_by_key.values():
        candidate["unique_sender_count"] = len(candidate["senders"])
        candidate["senders"] = sorted(candidate["senders"])
        candidate["message_refs"] = sorted(
            candidate["message_refs"],
            key=lambda item: (item["batch_id"], item["sender"], item["subject"], item["message_id"]),
        )
        candidate["example_subjects"] = candidate["example_subjects"][:5]
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            item["suggested_disposition"] != "phishing",
            -item["message_count"],
            -item["unique_sender_count"],
            item["provider"],
            item["group_key"],
        )
    )

    return {
        "generated_at": _now_iso(),
        "artifact_type": "safety-resolution-pack",
        "summary": {
            "candidate_count": len(candidates),
            "phishing_candidate_count": sum(1 for item in candidates if item["suggested_disposition"] == "phishing"),
            "not_safety_candidate_count": sum(1 for item in candidates if item["suggested_disposition"] == "not-safety"),
        },
        "candidates": candidates,
    }


def write_safety_resolution_pack(
    output_storage_dir: Path,
    *,
    report: dict,
    provider_storage_dirs: list[tuple[str, Path]],
) -> dict:
    payload = build_safety_resolution_pack(
        report=report,
        provider_storage_dirs=provider_storage_dirs,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = safety_resolution_pack_path(output_storage_dir, f"safety-resolution-pack-{timestamp}")
    write_json(path, payload)
    payload["pack_path"] = str(path)
    return payload


def load_artifact(path: Path) -> dict:
    payload = load_json(path)
    payload["artifact_path"] = str(path)
    return payload


def _suggest_resolution(item: dict) -> dict:
    sender_key = normalized_sender_email(item.get("sender")) or (item.get("sender", "").strip().lower())
    normalized_text = _normalized_text(item)
    if sender_key in LEGITIMATE_BILLING_DOMAINS:
        return {
            "disposition": "not-safety",
            "scope": "sender-cluster",
            "group_key": sender_key,
            "reason": "known billing sender with payment or subscription reminder language",
        }
    if _looks_payment_scam(item):
        return {
            "disposition": "phishing",
            "scope": "sender",
            "group_key": sender_key or item.get("subject", "").strip().lower(),
            "reason": "payment or invoice themed scam pattern",
        }
    if _looks_reward_scam(item):
        archetype_key = "reward-giveaway"
        return {
            "disposition": "phishing",
            "scope": "family-cluster",
            "group_key": archetype_key,
            "reason": "reward or survey bait with fake package or gift claim language",
        }
    return {
        "disposition": "phishing",
        "scope": "sender",
        "group_key": sender_key or normalized_text[:80],
        "reason": "remaining suspicious unresolved message without approved safety memory",
    }


def _looks_payment_scam(item: dict) -> bool:
    text = _normalized_text(item)
    payment_terms = (
        "invoice payment",
        "statement review account",
        "payment information",
        "you sent a payment",
        "paypal notice",
        "authorization received",
        "recurring transaction",
    )
    return any(term in text for term in payment_terms)


def _looks_reward_scam(item: dict) -> bool:
    text = _normalized_text(item)
    reward_terms = (
        "gift card",
        "reward",
        "welcome package",
        "grand mondial",
        "survey",
        "congratulations",
        "free coffee maker",
        "free airpods",
    )
    return any(term in text for term in reward_terms)


def _normalized_text(item: dict) -> str:
    combined = " ".join(
        [
            item.get("sender", "") or "",
            item.get("subject", "") or "",
            item.get("snippet", "") or "",
            item.get("body", "") or "",
        ]
    ).lower()
    return " ".join(combined.split())


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
