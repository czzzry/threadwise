from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import founder_policy_batch_pack_path, write_json
from src.memory_proposal_store import build_memory_proposal, load_storage_items
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRule

PROTECTED_LABELS = {
    "account-security",
    "financial-account",
    "personal",
    "reply-needed",
    "receipt-billing",
    "shopping-order",
    "travel",
    "calendar-event",
}


POLICY_DEFINITIONS = {
    "low-value-opt-in": {
        "title": "Legitimate but unwanted opt-in mail",
        "description": (
            "Recurring newsletters, promos, feeds, and similar opt-in mail that the founder no longer wants in normal attention."
        ),
        "labels": ("promotions", "spam-low-value"),
        "review_types": {"policy-review"},
        "match_labels": {"promotions", "spam-low-value", "newsletter"},
        "default_label": "spam-low-value",
    },
    "personal-keep-visible": {
        "title": "Known-person or direct-message alerts",
        "description": "Recurring direct-message style alerts that should stay visible as personal or reply-needed.",
        "labels": ("personal", "reply-needed"),
        "review_types": {"policy-review"},
        "match_labels": {"personal", "reply-needed"},
        "default_label": "personal",
    },
    "account-security-keep-visible": {
        "title": "Account and security mail",
        "description": "Recurring verification, sign-in, and account-security mail that should stay visible.",
        "labels": ("account-security",),
        "review_types": {"safety-review", "policy-review"},
        "match_labels": {"account-security"},
        "default_label": "account-security",
    },
    "event-confirmation": {
        "title": "Registrations and event confirmations",
        "description": "Recurring booking or registration confirmations that should stay visible as calendar or event-related mail.",
        "labels": ("calendar-event",),
        "review_types": {"policy-review", "preference-review"},
        "match_labels": {"calendar-event", "travel"},
        "default_label": "calendar-event",
    },
    "receipt-billing": {
        "title": "Receipts and billing confirmations",
        "description": "Recurring purchase, invoice, and billing confirmations.",
        "labels": ("receipt-billing",),
        "review_types": {"policy-review", "preference-review"},
        "match_labels": {"receipt-billing"},
        "default_label": "receipt-billing",
    },
}


def build_founder_policy_batch_pack(
    *,
    cluster_decision_pack: dict,
    accepted_rules: list[TeachableRule],
    provider_storage_dirs: list[tuple[str, Path]],
) -> dict:
    accepted_policy_keys = _accepted_policy_keys(accepted_rules)
    storage_items_by_provider = {
        provider: load_storage_items(path, provider)
        for provider, path in provider_storage_dirs
    }

    batches = []
    for policy_key in accepted_policy_keys:
        definition = POLICY_DEFINITIONS[policy_key]
        cluster_units = _matching_clusters(cluster_decision_pack, policy_key)
        if not cluster_units:
            continue
        proposal_drafts = []
        for unit in cluster_units:
            examples = list(unit.get("examples", []))
            if not examples:
                continue
            provider = unit.get("provider", "")
            storage_items = storage_items_by_provider.get(provider, [])
            label = _proposal_label_for(unit, definition)
            proposal = build_memory_proposal(
                provider=provider,
                account_id=examples[0].get("account_id", ""),
                source_batch_id=examples[0].get("batch_id", ""),
                selected_items=examples,
                scope=_proposal_scope_for(policy_key, unit, storage_items),
                label=label,
                explanation=_proposal_explanation(policy_key, unit),
                storage_items=storage_items,
            )
            payload = proposal.to_dict()
            payload["preview_match_count"] = proposal.preview.get("match_count", 0)
            payload["sender_key"] = unit.get("sender_key", "")
            payload["message_count"] = unit.get("message_count", 0)
            payload["family_count"] = unit.get("family_count", 0)
            proposal_drafts.append(payload)

        batches.append(
            {
                "batch_id": _batch_id(policy_key),
                "policy_key": policy_key,
                "title": definition["title"],
                "description": definition["description"],
                "labels": list(definition["labels"]),
                "cluster_count": len(cluster_units),
                "message_coverage": sum(int(unit.get("message_count", 0)) for unit in cluster_units),
                "family_coverage": sum(int(unit.get("family_count", 0)) for unit in cluster_units),
                "providers": sorted({unit.get("provider", "") for unit in cluster_units if unit.get("provider", "")}),
                "clusters": [
                    {
                        "decision_id": unit.get("decision_id", ""),
                        "provider": unit.get("provider", ""),
                        "sender_key": unit.get("sender_key", ""),
                        "message_count": unit.get("message_count", 0),
                        "family_count": unit.get("family_count", 0),
                        "suggested_labels": list(unit.get("suggested_labels", [])),
                        "review_type": unit.get("review_type", ""),
                        "review_mode": unit.get("review_mode", ""),
                        "confidence": unit.get("confidence", ""),
                    }
                    for unit in cluster_units
                ],
                "proposal_drafts": proposal_drafts,
            }
        )

    batches.sort(
        key=lambda batch: (
            -batch["message_coverage"],
            -batch["cluster_count"],
            batch["policy_key"],
        )
    )
    return {
        "generated_at": _now_iso(),
        "artifact_type": "founder-policy-batch-pack",
        "summary": {
            "accepted_policy_count": len(accepted_policy_keys),
            "batch_count": len(batches),
            "proposal_count": sum(len(batch.get("proposal_drafts", [])) for batch in batches),
            "message_coverage": sum(batch.get("message_coverage", 0) for batch in batches),
            "family_coverage": sum(batch.get("family_coverage", 0) for batch in batches),
        },
        "batches": batches,
    }


def write_founder_policy_batch_pack(
    output_storage_dir: Path,
    *,
    cluster_decision_pack: dict,
    accepted_rules: list[TeachableRule],
    provider_storage_dirs: list[tuple[str, Path]],
) -> dict:
    payload = build_founder_policy_batch_pack(
        cluster_decision_pack=cluster_decision_pack,
        accepted_rules=accepted_rules,
        provider_storage_dirs=provider_storage_dirs,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = founder_policy_batch_pack_path(output_storage_dir, f"founder-policy-batch-pack-{timestamp}")
    write_json(path, payload)
    payload["pack_path"] = str(path)
    return payload


def _accepted_policy_keys(accepted_rules: list[TeachableRule]) -> set[str]:
    keys = set()
    for rule in accepted_rules:
        labels = {rule.label}
        if labels & POLICY_DEFINITIONS["low-value-opt-in"]["match_labels"]:
            keys.add("low-value-opt-in")
        if labels & POLICY_DEFINITIONS["personal-keep-visible"]["match_labels"]:
            keys.add("personal-keep-visible")
        if labels & POLICY_DEFINITIONS["account-security-keep-visible"]["match_labels"]:
            keys.add("account-security-keep-visible")
        if labels & POLICY_DEFINITIONS["event-confirmation"]["match_labels"]:
            keys.add("event-confirmation")
        if labels & POLICY_DEFINITIONS["receipt-billing"]["match_labels"]:
            keys.add("receipt-billing")
    return keys


def _matching_clusters(cluster_decision_pack: dict, policy_key: str) -> list[dict]:
    definition = POLICY_DEFINITIONS[policy_key]
    sections = [
        *cluster_decision_pack.get("auto_low_value_policies", []),
        *cluster_decision_pack.get("personal_policies", []),
        *cluster_decision_pack.get("preference_reviews", []),
        *cluster_decision_pack.get("safety_reviews", []),
    ]
    matches = []
    for unit in sections:
        if unit.get("review_type", "") not in definition["review_types"]:
            continue
        labels = set(unit.get("suggested_labels", []))
        if labels & definition["match_labels"]:
            matches.append(unit)
    return matches


def _proposal_label_for(unit: dict, definition: dict) -> str:
    labels = list(unit.get("suggested_labels", []))
    if definition["default_label"] in labels:
        return definition["default_label"]
    if labels:
        return labels[0]
    return definition["default_label"]


def _proposal_explanation(policy_key: str, unit: dict) -> str:
    return (
        f"Drafted from accepted founder policy '{policy_key}' for recurring unresolved cluster "
        f"{unit.get('provider', '')}:{unit.get('sender_key', '')}."
    )


def _proposal_scope_for(policy_key: str, unit: dict, storage_items: list[dict]) -> str:
    if policy_key != "low-value-opt-in":
        return "sender-cluster"
    sender_key = (unit.get("sender_key", "") or "").strip().lower()
    if not sender_key:
        return "sender-cluster"
    if _sender_has_protected_labels(sender_key, storage_items):
        return "sender-cluster"
    return "sender"


def _sender_has_protected_labels(sender_key: str, storage_items: list[dict]) -> bool:
    for item in storage_items:
        item_sender_key = normalized_sender_email(item.get("sender")) or (item.get("sender", "").strip().lower())
        if item_sender_key != sender_key:
            continue
        labels = set(item.get("applied_labels", [])) | set(item.get("final_labels", []))
        if labels & PROTECTED_LABELS:
            return True
    return False


def _batch_id(policy_key: str) -> str:
    return f"policy-batch-{policy_key}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
