from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import (
    accepted_shadow_rules_path,
    founder_policy_batch_application_path,
    latest_safety_triage_manifest_path,
    load_json,
    memory_proposals_path,
    write_json,
)
from src.memory_impact_report import build_memory_impact_report, write_memory_impact_report
from src.memory_proposal_store import MemoryProposal, MemoryProposalStore
from src.teachable_rule_memory import TeachableRuleMemory


def apply_founder_policy_batch(
    output_storage_dir: Path,
    *,
    policy_batch_pack: dict,
    batch_id: str,
    provider_storage_dirs: list[tuple[str, Path]],
    review_notes: str = "",
    review_pack: dict | None = None,
) -> dict:
    batch = _find_batch(policy_batch_pack, batch_id)
    proposal_store = MemoryProposalStore(memory_proposals_path(output_storage_dir))
    rules_memory = TeachableRuleMemory(accepted_shadow_rules_path(output_storage_dir))
    before_rules = rules_memory.list_rules()
    before_impact = build_memory_impact_report(
        provider_storage_dirs,
        accepted_rules=before_rules,
        review_pack=review_pack or {},
    )

    approved_proposals = []
    for payload in batch.get("proposal_drafts", []):
        proposal = MemoryProposal.from_dict(payload)
        proposal_store.save_proposal(proposal)
        approved = proposal_store.review_proposal(
            proposal.id,
            "approved",
            rules_memory=rules_memory,
            review_notes=review_notes,
        )
        approved_proposals.append(approved.to_dict())

    application = {
        "application_id": _application_id(batch_id),
        "generated_at": _now_iso(),
        "artifact_type": "founder-policy-batch-application",
        "batch_id": batch_id,
        "policy_key": batch.get("policy_key", ""),
        "title": batch.get("title", ""),
        "review_notes": review_notes,
        "approved_proposal_count": len(approved_proposals),
        "approved_rule_ids": [proposal.get("approved_rule_id", "") for proposal in approved_proposals if proposal.get("approved_rule_id")],
        "approved_proposals": approved_proposals,
        "cluster_count": batch.get("cluster_count", 0),
        "message_coverage": batch.get("message_coverage", 0),
        "family_coverage": batch.get("family_coverage", 0),
        "impact_before": dict(before_impact.get("summary", {})),
        "impact_after": {},
        "impact_delta": {},
        "memory_impact_report_path": "",
        "refresh_status": "pending",
    }
    path = founder_policy_batch_application_path(output_storage_dir, application["application_id"])
    application["application_path"] = str(path)
    write_json(path, application)

    after_rules = rules_memory.list_rules()
    after_impact = write_memory_impact_report(
        output_storage_dir,
        provider_storage_dirs,
        accepted_rules=after_rules,
        review_pack=review_pack or {},
    )

    application["impact_after"] = dict(after_impact.get("summary", {}))
    application["impact_delta"] = {
        "accepted_rule_count": after_impact.get("summary", {}).get("accepted_rule_count", 0)
        - before_impact.get("summary", {}).get("accepted_rule_count", 0),
        "impacted_rule_count": after_impact.get("summary", {}).get("impacted_rule_count", 0)
        - before_impact.get("summary", {}).get("impacted_rule_count", 0),
        "unresolved_delta_change": after_impact.get("summary", {}).get("unresolved_delta", 0)
        - before_impact.get("summary", {}).get("unresolved_delta", 0),
        "resolved_gain": before_impact.get("summary", {}).get("unresolved_after", 0)
        - after_impact.get("summary", {}).get("unresolved_after", 0),
    }
    application["memory_impact_report_path"] = after_impact.get("report_path", "")
    application["refresh_status"] = "complete"
    write_json(path, application)
    _refresh_manifest_with_batch_application(output_storage_dir, after_impact, application)
    return application


def _find_batch(policy_batch_pack: dict, batch_id: str) -> dict:
    for batch in policy_batch_pack.get("batches", []):
        if batch.get("batch_id") == batch_id:
            return batch
    raise KeyError(f"Unknown founder policy batch: {batch_id}")


def _refresh_manifest_with_batch_application(output_storage_dir: Path, memory_impact: dict, application: dict) -> None:
    manifest_path = latest_safety_triage_manifest_path(output_storage_dir)
    if not manifest_path.exists():
        return
    manifest = load_json(manifest_path)
    manifest["memory_impact_summary"] = {
        "accepted_rule_count": memory_impact.get("summary", {}).get("accepted_rule_count", 0),
        "impacted_rule_count": memory_impact.get("summary", {}).get("impacted_rule_count", 0),
        "unresolved_before": memory_impact.get("summary", {}).get("unresolved_before", 0),
        "unresolved_after": memory_impact.get("summary", {}).get("unresolved_after", 0),
        "unresolved_delta": memory_impact.get("summary", {}).get("unresolved_delta", 0),
    }
    manifest["top_memory_impacts"] = list(memory_impact.get("top_memory_impacts", []))[:5]
    manifest["next_review_payoffs"] = list(memory_impact.get("next_review_payoffs", []))[:5]
    manifest.setdefault("artifacts", {})
    manifest["artifacts"]["memory_impact_report_path"] = memory_impact.get("report_path")
    manifest["artifacts"]["latest_founder_policy_batch_application_path"] = application.get("application_path")
    manifest["latest_founder_policy_batch_application"] = {
        "batch_id": application.get("batch_id", ""),
        "policy_key": application.get("policy_key", ""),
        "approved_proposal_count": application.get("approved_proposal_count", 0),
        "approved_rule_ids": list(application.get("approved_rule_ids", [])),
        "resolved_gain": application.get("impact_delta", {}).get("resolved_gain", 0),
        "message_coverage": application.get("message_coverage", 0),
    }
    write_json(manifest_path, manifest)


def _application_id(batch_id: str) -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{batch_id}-apply-{timestamp}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
