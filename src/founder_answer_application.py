from datetime import UTC, datetime
from pathlib import Path

from src.founder_answer_decision import _normalize_proposal_payload
from src.founder_answer_pack import write_founder_answer_pack
from src.founder_question_pack import write_founder_question_pack
from src.local_artifacts import (
    accepted_shadow_rules_path,
    founder_answer_application_path,
    founder_answer_applications_dir,
    founder_answer_decisions_dir,
    latest_safety_triage_manifest_path,
    load_json,
    memory_proposals_path,
    write_json,
)
from src.memory_impact_report import build_memory_impact_report, write_memory_impact_report
from src.memory_proposal_store import MemoryProposal, MemoryProposalStore
from src.safety_triage_manifest import _top_founder_answer_previews
from src.teachable_rule_memory import TeachableRuleMemory


def apply_founder_answer_decision(
    output_storage_dir: Path,
    *,
    decision: dict,
    provider_storage_dirs: list[tuple[str, Path]],
    review_notes: str = "",
    review_pack: dict | None = None,
) -> dict:
    proposal_store = MemoryProposalStore(memory_proposals_path(output_storage_dir))
    rules_memory = TeachableRuleMemory(accepted_shadow_rules_path(output_storage_dir))
    before_rules = rules_memory.list_rules()
    before_impact = build_memory_impact_report(
        provider_storage_dirs,
        accepted_rules=before_rules,
        review_pack=review_pack or {},
    )

    approved_proposals = []
    for payload in decision.get("proposal_drafts", []):
        proposal_payload = _normalize_proposal_payload(payload)
        proposal = MemoryProposal.from_dict(proposal_payload)
        proposal_store.save_proposal(proposal)
        approved = proposal_store.review_proposal(
            proposal.id,
            "approved",
            rules_memory=rules_memory,
            review_notes=review_notes,
        )
        approved_proposals.append(approved.to_dict())

    after_rules = rules_memory.list_rules()
    after_impact = write_memory_impact_report(
        output_storage_dir,
        provider_storage_dirs,
        accepted_rules=after_rules,
        review_pack=review_pack or {},
    )

    application = {
        "application_id": _application_id(decision.get("decision_id", "")),
        "generated_at": _now_iso(),
        "artifact_type": "founder-answer-application",
        "decision_id": decision.get("decision_id", ""),
        "question_id": decision.get("question_id", ""),
        "theme": decision.get("theme", ""),
        "matched_answer_key": decision.get("matched_answer_key", ""),
        "review_notes": review_notes,
        "approved_proposal_count": len(approved_proposals),
        "approved_rule_ids": [proposal.get("approved_rule_id", "") for proposal in approved_proposals if proposal.get("approved_rule_id")],
        "approved_proposals": approved_proposals,
        "impact_before": dict(before_impact.get("summary", {})),
        "impact_after": dict(after_impact.get("summary", {})),
        "impact_delta": {
            "accepted_rule_count": after_impact.get("summary", {}).get("accepted_rule_count", 0)
            - before_impact.get("summary", {}).get("accepted_rule_count", 0),
            "impacted_rule_count": after_impact.get("summary", {}).get("impacted_rule_count", 0)
            - before_impact.get("summary", {}).get("impacted_rule_count", 0),
            "unresolved_delta_change": after_impact.get("summary", {}).get("unresolved_delta", 0)
            - before_impact.get("summary", {}).get("unresolved_delta", 0),
            "resolved_gain": before_impact.get("summary", {}).get("unresolved_after", 0)
            - after_impact.get("summary", {}).get("unresolved_after", 0),
        },
        "memory_impact_report_path": after_impact.get("report_path", ""),
    }
    path = founder_answer_application_path(output_storage_dir, application["application_id"])
    application["application_path"] = str(path)
    # Persist the application before refreshing downstream founder queues so
    # concurrent apply runs can see this answered question and exclude it.
    write_json(path, application)
    refreshed = _refresh_founder_review_state(
        output_storage_dir,
        review_pack=review_pack or {},
        provider_storage_dirs=provider_storage_dirs,
        memory_impact=after_impact,
        current_application=application,
    )
    application["refreshed_founder_question_pack_path"] = refreshed.get("founder_question_pack_path", "")
    application["refreshed_founder_answer_pack_path"] = refreshed.get("founder_answer_pack_path", "")
    write_json(path, application)
    _refresh_manifest_with_application(output_storage_dir, after_impact, application, refreshed=refreshed)
    return application


def load_founder_answer_decision(output_storage_dir: Path, *, decision_path: Path | None = None, question_id: str | None = None) -> dict:
    if decision_path is not None:
        return load_json(decision_path)
    if not question_id:
        raise ValueError("question_id is required when decision_path is not provided.")
    decisions_dir = founder_answer_decisions_dir(output_storage_dir)
    matches = []
    for path in sorted(decisions_dir.glob("*.json")):
        decision = load_json(path)
        if decision.get("question_id") == question_id:
            matches.append(decision)
    if not matches:
        raise KeyError(f"No founder answer decision found for question: {question_id}")
    return matches[-1]


def _refresh_manifest_with_application(output_storage_dir: Path, memory_impact: dict, application: dict, *, refreshed: dict | None = None) -> None:
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
    manifest["artifacts"]["latest_founder_answer_application_path"] = application.get("application_path")
    refreshed = refreshed or {}
    if refreshed:
        question_pack = refreshed.get("founder_question_pack", {})
        answer_pack = refreshed.get("founder_answer_pack", {})
        manifest["founder_question_summary"] = {
            "question_count": question_pack.get("summary", {}).get("question_count", 0),
            "estimated_unblocked_messages": question_pack.get("summary", {}).get("estimated_unblocked_messages", 0),
        }
        manifest["founder_questions"] = list(question_pack.get("questions", []))[:5]
        manifest["founder_answer_summary"] = {
            "actionable_answer_count": answer_pack.get("summary", {}).get("actionable_answer_count", 0),
            "answer_option_count": answer_pack.get("summary", {}).get("answer_option_count", 0),
        }
        manifest["founder_answer_previews"] = _top_founder_answer_previews(answer_pack)
        manifest["artifacts"]["founder_question_pack_path"] = refreshed.get("founder_question_pack_path")
        manifest["artifacts"]["founder_answer_pack_path"] = refreshed.get("founder_answer_pack_path")
    manifest["latest_founder_answer_application"] = {
        "decision_id": application.get("decision_id", ""),
        "question_id": application.get("question_id", ""),
        "theme": application.get("theme", ""),
        "matched_answer_key": application.get("matched_answer_key", ""),
        "approved_proposal_count": application.get("approved_proposal_count", 0),
        "approved_rule_ids": list(application.get("approved_rule_ids", [])),
        "resolved_gain": application.get("impact_delta", {}).get("resolved_gain", 0),
    }
    write_json(manifest_path, manifest)


def _refresh_founder_review_state(
    output_storage_dir: Path,
    *,
    review_pack: dict,
    provider_storage_dirs: list[tuple[str, Path]],
    memory_impact: dict,
    current_application: dict,
) -> dict:
    manifest_path = latest_safety_triage_manifest_path(output_storage_dir)
    provider_drivers = []
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        provider_drivers = list(manifest.get("provider_drivers", []))

    excluded_question_ids = _applied_question_ids(output_storage_dir)
    current_question_id = current_application.get("question_id", "")
    if current_question_id:
        excluded_question_ids.add(current_question_id)

    founder_question_pack = write_founder_question_pack(
        output_storage_dir,
        review_pack=review_pack,
        memory_impact=memory_impact,
        provider_drivers=provider_drivers,
        exclude_question_ids=excluded_question_ids,
    )
    founder_answer_pack = write_founder_answer_pack(
        output_storage_dir,
        founder_question_pack=founder_question_pack,
        review_pack=review_pack,
        provider_storage_dirs=provider_storage_dirs,
    )
    return {
        "founder_question_pack": founder_question_pack,
        "founder_answer_pack": founder_answer_pack,
        "founder_question_pack_path": founder_question_pack.get("pack_path", ""),
        "founder_answer_pack_path": founder_answer_pack.get("pack_path", ""),
    }


def _applied_question_ids(output_storage_dir: Path) -> set[str]:
    applications_dir = founder_answer_applications_dir(output_storage_dir)
    if not applications_dir.exists():
        return set()
    ids = set()
    for path in applications_dir.glob("*.json"):
        payload = load_json(path)
        question_id = payload.get("question_id", "")
        if question_id:
            ids.add(question_id)
    return ids


def _application_id(decision_id: str) -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    fragment = decision_id or "founder-answer"
    return f"{fragment}-apply-{timestamp}"


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
