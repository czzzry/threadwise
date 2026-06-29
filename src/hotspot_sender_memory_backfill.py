from pathlib import Path

from src.local_artifacts import accepted_shadow_rules_path, founder_answer_applications_dir, memory_proposals_path, load_json
from src.memory_proposal_store import MemoryProposalStore, build_memory_proposal, load_storage_items
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRuleMemory


SENDER_WIDE_THEMES = {"marketing-preference", "direct-message-handling"}


def backfill_hotspot_sender_memory(output_storage_dir: Path, provider_storage_dirs: list[tuple[str, Path]]) -> dict:
    proposal_store = MemoryProposalStore(memory_proposals_path(output_storage_dir))
    rules_memory = TeachableRuleMemory(accepted_shadow_rules_path(output_storage_dir))
    storage_items_by_provider = {
        provider: load_storage_items(path, provider)
        for provider, path in provider_storage_dirs
    }
    existing_sender_rules = {
        _sender_rule_key(rule)
        for rule in rules_memory.list_rules()
        if rule.scope == "sender"
    }
    created_rules = []
    created_proposals = []
    applications_dir = founder_answer_applications_dir(output_storage_dir)
    if not applications_dir.exists():
        return {"created_rule_ids": [], "created_proposal_ids": [], "processed_application_count": 0}

    processed_application_count = 0
    for path in sorted(applications_dir.glob("*.json")):
        application = load_json(path)
        if not _is_sender_wide_hotspot_application(application):
            continue
        processed_application_count += 1
        for approved in application.get("approved_proposals", []):
            if approved.get("scope") != "sender-cluster":
                continue
            provider = approved.get("provider", "")
            label = approved.get("label", "")
            sender_key = _proposal_sender_key(approved)
            key = (provider, label, sender_key)
            if not provider or not label or not sender_key or key in existing_sender_rules:
                continue
            source_examples = list(approved.get("source_examples", []))
            if not source_examples:
                continue
            proposal = build_memory_proposal(
                provider=provider,
                account_id=approved.get("account_id", ""),
                source_batch_id=approved.get("source_batch_id", ""),
                selected_items=source_examples,
                scope="sender",
                label=label,
                explanation=(
                    f"Backfilled broader sender-wide memory from hotspot founder answer "
                    f"{application.get('question_id', '')}."
                ),
                storage_items=storage_items_by_provider.get(provider, []),
            )
            proposal_store.save_proposal(proposal)
            updated = proposal_store.review_proposal(
                proposal.id,
                "approved",
                rules_memory=rules_memory,
                review_notes="Backfilled sender-wide hotspot memory.",
            )
            existing_sender_rules.add(key)
            created_proposals.append(updated.id)
            if updated.approved_rule_id:
                created_rules.append(updated.approved_rule_id)
    return {
        "created_rule_ids": created_rules,
        "created_proposal_ids": created_proposals,
        "processed_application_count": processed_application_count,
    }


def _is_sender_wide_hotspot_application(application: dict) -> bool:
    return (
        application.get("question_id", "").startswith("question-hotspot-")
        and application.get("theme", "") in SENDER_WIDE_THEMES
    )


def _proposal_sender_key(proposal: dict) -> str:
    sender_key = proposal.get("sender_key", "")
    if sender_key:
        return sender_key
    examples = proposal.get("source_examples", [])
    if not examples:
        return ""
    sender = examples[0].get("sender", "")
    return normalized_sender_email(sender) or sender.strip().lower()


def _sender_rule_key(rule) -> tuple[str, str, str]:
    sender = ""
    for example in rule.source_examples:
        sender = normalized_sender_email(example.get("sender", "")) or example.get("sender", "").strip().lower()
        if sender:
            break
    return (rule.providers[0] if rule.providers else "", rule.label, sender)
