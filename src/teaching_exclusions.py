from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json_or_default, teaching_exclusions_path, write_json


def save_teaching_exclusion(
    storage_dir: Path,
    *,
    proposal: dict,
    message_id: str,
    reason: str = "",
) -> dict:
    message_id = str(message_id or "").strip()
    if not message_id:
        raise ValueError("Choose an affected email to exclude.")
    proposal_id = str(proposal.get("id") or "").strip()
    signature = rule_signature_from_proposal(proposal)
    now = _now_iso()
    payload = _load_payload(storage_dir)
    exclusions = [
        entry
        for entry in payload.get("exclusions", [])
        if not (
            entry.get("message_id") == message_id
            and (
                (proposal_id and entry.get("proposal_id") == proposal_id)
                or (signature and entry.get("rule_signature") == signature)
            )
        )
    ]
    entry = {
        "id": f"exclude-{len(exclusions) + 1:03d}",
        "proposal_id": proposal_id,
        "rule_signature": signature,
        "message_id": message_id,
        "reason": reason.strip(),
        "created_at": now,
        "updated_at": now,
        "scope": proposal.get("scope", ""),
        "label": proposal.get("label", ""),
        "terms": list(proposal.get("terms", [])),
    }
    exclusions.append(entry)
    write_json(
        teaching_exclusions_path(storage_dir),
        {
            "status": "PROTOTYPE - local teaching exclusions",
            "generated_at": now,
            "exclusions": exclusions,
        },
    )
    return entry


def filter_excluded_preview_matches(storage_dir: Path, proposal: dict, matches: list[dict]) -> list[dict]:
    return [
        match
        for match in matches
        if not is_teaching_match_excluded(storage_dir, proposal=proposal, message_id=match.get("message_id", ""))
    ]


def count_teaching_exclusions_for_proposal(storage_dir: Path, proposal: dict) -> int:
    proposal_id = str(proposal.get("id") or "").strip()
    signature = rule_signature_from_proposal(proposal)
    count = 0
    for entry in _load_payload(storage_dir).get("exclusions", []):
        if proposal_id and entry.get("proposal_id") == proposal_id:
            count += 1
            continue
        if signature and entry.get("rule_signature") == signature:
            count += 1
    return count


def is_teaching_match_excluded(storage_dir: Path, *, proposal: dict, message_id: str) -> bool:
    proposal_id = str(proposal.get("id") or "").strip()
    signature = rule_signature_from_proposal(proposal)
    return _has_exclusion(storage_dir, proposal_id=proposal_id, rule_signature=signature, message_id=message_id)


def is_rule_message_excluded(storage_dir: Path, *, rule: dict, message_id: str) -> bool:
    proposal_id = str((rule.get("provenance") or {}).get("proposal_id") or "").strip()
    signature = rule_signature_from_rule(rule)
    return _has_exclusion(storage_dir, proposal_id=proposal_id, rule_signature=signature, message_id=message_id)


def rule_signature_from_proposal(proposal: dict) -> str:
    return _rule_signature(
        provider=proposal.get("provider", ""),
        scope=proposal.get("scope", ""),
        label=proposal.get("label", ""),
        terms=proposal.get("terms", []),
    )


def rule_signature_from_rule(rule: dict) -> str:
    providers = rule.get("providers") or []
    provider = providers[0] if providers else ""
    return _rule_signature(
        provider=provider,
        scope=rule.get("scope", ""),
        label=rule.get("label", ""),
        terms=rule.get("terms", []),
    )


def _has_exclusion(storage_dir: Path, *, proposal_id: str, rule_signature: str, message_id: str) -> bool:
    message_id = str(message_id or "").strip()
    if not message_id:
        return False
    for entry in _load_payload(storage_dir).get("exclusions", []):
        if entry.get("message_id") != message_id:
            continue
        if proposal_id and entry.get("proposal_id") == proposal_id:
            return True
        if rule_signature and entry.get("rule_signature") == rule_signature:
            return True
    return False


def _rule_signature(*, provider: str, scope: str, label: str, terms: list[str] | tuple[str, ...]) -> str:
    normalized_terms = "|".join(sorted(str(term).strip().lower() for term in terms if str(term).strip()))
    return "::".join(
        [
            str(provider or "").strip().lower(),
            str(scope or "").strip().lower(),
            str(label or "").strip().lower(),
            normalized_terms,
        ]
    )


def _load_payload(storage_dir: Path) -> dict:
    return load_json_or_default(teaching_exclusions_path(storage_dir), {"exclusions": []})


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
