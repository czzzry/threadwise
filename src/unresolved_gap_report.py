from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import load_json, write_json


TARGET_UNRESOLVED_RATE = 0.10


def build_unresolved_gap_report(output_storage_dir: Path) -> dict:
    runtime_report = _latest_runtime_report(output_storage_dir)
    if runtime_report is None:
        return {
            "generated_at": _now_iso(),
            "artifact_type": "unresolved-gap-report",
            "summary": {
                "current_unresolved_count": 0,
                "target_unresolved_count": 0,
                "remaining_gap_count": 0,
            },
            "recommended_actions": [],
            "provider_hotspots": [],
        }
    manifest = _latest_triage_manifest(output_storage_dir)
    payload = build_unresolved_gap_report_from_runtime(runtime_report, manifest=manifest)
    payload["sources"] = {
        "runtime_report_path": runtime_report.get("report_path", ""),
        "triage_manifest_path": manifest.get("manifest_path", "") if manifest else "",
    }
    return payload


def build_unresolved_gap_report_from_runtime(runtime_report: dict, *, manifest: dict | None = None) -> dict:
    summary = runtime_report.get("summary", {})
    current_unresolved_count = int(summary.get("unresolved_count", 0))
    message_count = int(summary.get("message_count", 0))
    target_unresolved_count = int(message_count * TARGET_UNRESOLVED_RATE)
    remaining_gap_count = max(0, current_unresolved_count - target_unresolved_count)
    provider_hotspots = _provider_hotspots(runtime_report)
    recommended_actions = _recommended_actions(manifest, provider_hotspots, remaining_gap_count)
    cumulative_gain = sum(item.get("expected_gain", 0) for item in recommended_actions)
    return {
        "generated_at": _now_iso(),
        "artifact_type": "unresolved-gap-report",
        "summary": {
            "current_unresolved_count": current_unresolved_count,
            "target_unresolved_count": target_unresolved_count,
            "remaining_gap_count": remaining_gap_count,
            "message_count": message_count,
            "target_unresolved_rate": TARGET_UNRESOLVED_RATE,
            "recommended_action_count": len(recommended_actions),
            "recommended_cumulative_gain": cumulative_gain,
        },
        "recommended_actions": recommended_actions,
        "provider_hotspots": provider_hotspots,
        "sources": {},
    }


def write_unresolved_gap_report(output_storage_dir: Path) -> dict:
    payload = build_unresolved_gap_report(output_storage_dir)
    reports_dir = output_storage_dir / "unresolved_gap_reports"
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = reports_dir / f"unresolved-gap-report-{timestamp}.json"
    write_json(path, payload)
    payload["report_path"] = str(path)
    return payload


def _recommended_actions(manifest: dict | None, provider_hotspots: list[dict], remaining_gap_count: int) -> list[dict]:
    actions: list[dict] = []
    covered_hotspots: set[tuple[str, str]] = set()
    if manifest:
        for question in manifest.get("founder_questions", []):
            gain = int(question.get("estimated_unblocked_messages", 0))
            actions.append(
                {
                    "action_type": "founder-question",
                    "title": question.get("title", question.get("question_id", "Founder question")),
                    "provider_scope": ",".join(question.get("providers", [])),
                    "expected_gain": gain,
                    "reason": f"One answer could unblock about {gain} messages.",
                    "question_id": question.get("question_id", ""),
                }
            )
        for target in manifest.get("top_review_targets", []):
            gain = int(target.get("count", 0))
            covered_hotspots.add((target.get("provider", ""), target.get("sender_key", "")))
            actions.append(
                {
                    "action_type": "family-review",
                    "title": f"{target.get('provider', '')}: {target.get('sender_key', '')}",
                    "provider_scope": target.get("provider", ""),
                    "expected_gain": gain,
                    "reason": f"Reviewing this family could resolve about {gain} messages.",
                    "sender_key": target.get("sender_key", ""),
                    "subject_key": target.get("subject_key", ""),
                }
            )
    hotspot_by_sender = {}
    for provider_hotspot in provider_hotspots:
        provider = provider_hotspot.get("provider", "")
        for family in provider_hotspot.get("top_families", []):
            key = (provider, family.get("sender_key", ""))
            hotspot_by_sender[key] = family
            if key in covered_hotspots:
                continue
            actions.append(
                {
                    "action_type": _hotspot_action_type(provider, family),
                    "title": f"{provider}: {family.get('sender_key', '')}",
                    "provider_scope": provider,
                    "expected_gain": int(family.get("count", 0)),
                    "reason": _hotspot_reason(family),
                    "sender_key": family.get("sender_key", ""),
                    "subject_key": family.get("top_subject", ""),
                    "observed_unresolved_count": int(family.get("count", 0)),
                }
            )
    for action in actions:
        sender_key = action.get("sender_key")
        provider = action.get("provider_scope")
        if sender_key and (provider, sender_key) in hotspot_by_sender:
            action["observed_unresolved_count"] = hotspot_by_sender[(provider, sender_key)].get("count", 0)
    actions.sort(
        key=lambda item: (
            -item.get("expected_gain", 0),
            item.get("action_type", ""),
            item.get("title", ""),
        )
    )
    picked = []
    running_gain = 0
    for action in actions:
        picked.append(action)
        running_gain += int(action.get("expected_gain", 0))
        if running_gain >= remaining_gap_count:
            break
    return picked[:12]


def _hotspot_action_type(provider: str, family: dict) -> str:
    text = f"{provider} {family.get('sender_key', '')} {family.get('top_subject', '')}".lower()
    if any(term in text for term in ("security", "verification", "password", "account", "code")):
        return "safety-review"
    if any(term in text for term in ("messaged you", "sent you a message", "digest", "recipe", "coupon", "rabatt", "gutschein", "promo")):
        return "hotspot-review"
    return "hotspot-review"


def _hotspot_reason(family: dict) -> str:
    return f"This unresolved hotspot appears about {int(family.get('count', 0))} times in the latest runtime run."


def _provider_hotspots(runtime_report: dict) -> list[dict]:
    hotspots = []
    for provider, payload in runtime_report.get("providers", {}).items():
        grouped: dict[str, dict] = {}
        for outcome in payload.get("outcomes", []):
            if outcome.get("stage") != "unresolved":
                continue
            key = outcome.get("sender_key", "")
            entry = grouped.setdefault(
                key,
                {
                    "sender_key": outcome.get("sender_key", ""),
                    "top_subject": outcome.get("subject", ""),
                    "count": 0,
                    "subject_counts": defaultdict(int),
                },
            )
            entry["count"] += 1
            subject = outcome.get("subject", "")
            entry["subject_counts"][subject] += 1
            if entry["subject_counts"][subject] > entry["subject_counts"][entry["top_subject"]]:
                entry["top_subject"] = subject
        ranked = sorted(grouped.values(), key=lambda item: (-item["count"], item["sender_key"]))[:10]
        hotspots.append(
            {
                "provider": provider,
                "unresolved_count": int(payload.get("unresolved_count", 0)),
                "top_families": ranked,
            }
        )
    hotspots.sort(key=lambda item: (-item["unresolved_count"], item["provider"]))
    return hotspots


def _latest_runtime_report(output_storage_dir: Path) -> dict | None:
    runtime_dir = output_storage_dir / "runtime_cascades"
    if not runtime_dir.exists():
        return None
    matches = sorted(runtime_dir.glob("*.json"))
    if not matches:
        return None
    payload = load_json(matches[-1])
    payload["report_path"] = str(matches[-1])
    return payload


def _latest_triage_manifest(output_storage_dir: Path) -> dict | None:
    path = output_storage_dir / "latest_safety_triage_pass.json"
    if not path.exists():
        return None
    payload = load_json(path)
    payload["manifest_path"] = str(path)
    return payload


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
