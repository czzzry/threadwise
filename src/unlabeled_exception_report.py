import re
from pathlib import Path

from src.local_batch_summary import load_batch


def collect_recurring_unlabeled_exceptions(
    storage_dir: Path,
    account_id: str,
    provider: str = "gmail",
) -> dict:
    batches_dir = storage_dir / "batches"
    clusters: dict[tuple[str, str], dict] = {}
    reviewed_unlabeled_count = 0

    for batch_path in _sorted_batch_paths(batches_dir):
        batch = load_batch(batch_path)
        if batch.get("account_id") != account_id:
            continue
        if batch.get("provider", "gmail") != provider:
            continue

        for item in batch.get("items", []):
            if item.get("review_state") != "reviewed":
                continue
            if item.get("final_labels"):
                continue

            reviewed_unlabeled_count += 1
            sender = item.get("sender", "(unknown sender)")
            subject = item.get("subject", "(no subject)")
            sender_key = sender.strip().lower()
            subject_pattern = _normalize_subject_pattern(subject)
            key = (sender_key, subject_pattern)
            cluster = clusters.setdefault(
                key,
                {
                    "sender": sender,
                    "subject_pattern": subject_pattern,
                    "count": 0,
                    "batch_ids": set(),
                    "examples": [],
                },
            )
            cluster["count"] += 1
            cluster["batch_ids"].add(batch["batch_id"])
            cluster["examples"].append(
                {
                    "batch_id": batch["batch_id"],
                    "subject": subject,
                }
            )

    recurring_clusters = [
        {
            "sender": cluster["sender"],
            "subject_pattern": cluster["subject_pattern"],
            "count": cluster["count"],
            "recent_batch_ids": _recent_batch_ids(cluster["batch_ids"]),
            "recent_examples": _recent_examples(cluster["examples"]),
        }
        for cluster in clusters.values()
        if cluster["count"] > 1
    ]
    recurring_clusters.sort(
        key=lambda cluster: (
            -cluster["count"],
            cluster["sender"].lower(),
            cluster["subject_pattern"],
        )
    )

    return {
        "account_id": account_id,
        "provider": provider,
        "reviewed_unlabeled_count": reviewed_unlabeled_count,
        "recurring_clusters": recurring_clusters,
    }


def _sorted_batch_paths(batches_dir: Path) -> list[Path]:
    if not batches_dir.exists():
        return []
    return sorted(
        batches_dir.glob("*.json"),
        key=lambda path: (_batch_sort_key(path.stem)),
    )


def _batch_sort_key(batch_id: str) -> tuple[str, int]:
    prefix, separator, suffix = batch_id.rpartition("-batch-")
    if separator and suffix.isdigit():
        return prefix, int(suffix)
    return batch_id, -1


def _normalize_subject_pattern(subject: str) -> str:
    normalized = subject.strip().lower()
    normalized = re.sub(r"\d+", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _recent_batch_ids(batch_ids: set[str]) -> list[str]:
    return sorted(batch_ids, key=_batch_sort_key, reverse=True)[:3]


def _recent_examples(examples: list[dict]) -> list[dict]:
    sorted_examples = sorted(
        examples,
        key=lambda example: _batch_sort_key(example["batch_id"]),
        reverse=True,
    )
    deduped: list[dict] = []
    seen = set()
    for example in sorted_examples:
        key = (example["batch_id"], example["subject"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(example)
        if len(deduped) == 2:
            break
    return deduped
