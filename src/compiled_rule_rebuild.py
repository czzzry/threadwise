from pathlib import Path

from src.local_artifacts import accepted_shadow_rules_path, memory_proposals_path, write_json
from src.memory_proposal_store import MemoryProposalStore, rule_from_memory_proposal
from src.shadow_suggestion_memory import ShadowSuggestionMemory


def rebuild_compiled_rules(output_storage_dir: Path) -> dict:
    rules_path = accepted_shadow_rules_path(output_storage_dir)
    proposal_store = MemoryProposalStore(memory_proposals_path(output_storage_dir))
    approved_proposals = [proposal for proposal in proposal_store.list_proposals() if proposal.status == "approved"]
    proposal_rules = [
        rule_from_memory_proposal(proposal, existing_count=index)
        for index, proposal in enumerate(approved_proposals)
    ]
    write_json(
        rules_path,
        {
            "status": "PROTOTYPE - rebuilt compiled rules",
            "source": "approved-memory-proposals",
            "approved_proposal_count": len(approved_proposals),
            "rules": [rule.to_dict() for rule in proposal_rules],
        },
    )
    shadow_memory = ShadowSuggestionMemory(output_storage_dir / "shadow_suggestion_memory.json")
    shadow_rules = shadow_memory.export_accepted_rules(rules_path)
    return {
        "rules_path": str(rules_path),
        "approved_proposal_count": len(approved_proposals),
        "proposal_rule_count": len(proposal_rules),
        "shadow_rule_count": len(shadow_rules),
        "total_rule_count": len(proposal_rules) + len(shadow_rules),
    }
