from collections import Counter
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from src.classifier_corpus_eval import _apply_extra_rules, _classify_messages, _family_key, _load_corpus_messages
from src.local_artifacts import load_json, runtime_cascade_path, safety_dispositions_path, write_json
from src.safety_disposition_store import SafetyDispositionStore, approved_safety_context, matches_safety_context
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRule


class OpenAIRuntimeCascadeClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @classmethod
    def from_env(cls, model: str) -> "OpenAIRuntimeCascadeClient":
        api_key = os.environ.get("EMAIL_AGENT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("EMAIL_AGENT_OPENAI_API_KEY or OPENAI_API_KEY is required for runtime cascade.")
        return cls(api_key=api_key, model=model)

    def analyze_message(self, payload: dict) -> dict:
        request_payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You classify one email using a bounded label taxonomy and optional prior memory. "
                        "Return strict JSON with keys labels, confidence, rationale, unresolved. "
                        "labels must contain 0 to 3 values from: personal, receipt-billing, account-security, "
                        "travel, shopping-order, spam-low-value, promotions, newsletter, job-related, "
                        "financial-account, reply-needed, calendar-event. "
                        "Set unresolved to true when the email should stay for human follow-up."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API request failed: {exc.code} {body}") from exc

        parsed = json.loads(raw["choices"][0]["message"]["content"])
        return {
            "labels": list(parsed.get("labels", []))[:3],
            "confidence": _normalize_confidence(parsed.get("confidence", "low")),
            "rationale": parsed.get("rationale", ""),
            "unresolved": bool(parsed.get("unresolved", False)),
        }


def build_runtime_cascade_report(
    provider_storage_dirs: list[tuple[str, Path]],
    extra_rules: list[TeachableRule] | None = None,
    cluster_decision_pack: dict | None = None,
    llm_client: OpenAIRuntimeCascadeClient | None = None,
    llm_limit: int = 25,
) -> dict:
    memory_context_by_key = _memory_context_by_key(cluster_decision_pack or {})
    provider_reports = {}
    provider_outcomes_by_name: dict[str, list[dict]] = {}
    provider_base_predictions: dict[str, dict[str, list[str]]] = {}
    pending_llm_by_provider: dict[str, list[dict]] = {}
    safety_contexts_by_provider = {
        provider: _approved_safety_contexts(storage_dir)
        for provider, storage_dir in provider_storage_dirs
    }

    for provider, storage_dir in provider_storage_dirs:
        messages = _load_corpus_messages(provider, storage_dir)
        base_predictions = _classify_messages(provider, messages)
        provider_base_predictions[provider] = base_predictions
        provider_outcomes = []
        pending_llm = []

        for message in messages:
            base_memory_context = memory_context_by_key.get((provider, _family_key(message)[0])) or {}
            safety_context = _matching_safety_context(
                safety_contexts_by_provider.get(provider, []),
                message,
            )
            combined_memory_context = _merge_memory_contexts(base_memory_context, safety_context)
            base_labels = list(base_predictions.get(message["classifier_message_id"], []))
            outcome = {
                "provider": provider,
                "account_id": message["account_id"],
                "batch_id": message["batch_id"],
                "message_id": message["message_id"],
                "sender": message["sender"],
                "subject": message["subject"],
                "sender_key": _family_key(message)[0],
                "stage": "",
                "labels": [],
                "matched_rule_ids": [],
                "memory_context_used": False,
                "llm_rationale": "",
                "llm_confidence": "",
                "memory_context": combined_memory_context,
                "decision_provenance": {
                    "decision_source": "",
                    "matched_rule_ids": [],
                    "retrieved_memory_keys": [],
                    "retrieved_safety_keys": [],
                    "llm_used": False,
                    "llm_model": "",
                    "llm_confidence": "",
                    "llm_abstained": False,
                    "safety_memory_used": False,
                    "human_review_state": message.get("review_state"),
                },
            }

            if base_labels:
                outcome["stage"] = "deterministic"
                outcome["labels"] = base_labels
                outcome["decision_provenance"] = _decision_provenance(
                    decision_source="deterministic",
                    message=message,
                    retrieved_memory_keys=_retrieved_memory_keys(combined_memory_context),
                    retrieved_safety_keys=_retrieved_safety_keys(combined_memory_context),
                    safety_memory_used=bool(_retrieved_safety_keys(combined_memory_context)),
                )
                outcome["memory_context_used"] = bool(combined_memory_context)
            else:
                applied = _apply_extra_rules([], message, extra_rules or [])
                if applied["labels"]:
                    outcome["stage"] = "accepted-memory"
                    outcome["labels"] = list(applied["labels"])
                    outcome["matched_rule_ids"] = list(applied["matched_rule_ids"])
                    outcome["decision_provenance"] = _decision_provenance(
                        decision_source="accepted-memory",
                        message=message,
                        matched_rule_ids=outcome["matched_rule_ids"],
                        retrieved_memory_keys=_retrieved_memory_keys(combined_memory_context),
                        retrieved_safety_keys=_retrieved_safety_keys(combined_memory_context),
                        safety_memory_used=bool(_retrieved_safety_keys(combined_memory_context)),
                    )
                    outcome["memory_context_used"] = bool(combined_memory_context)
                else:
                    outcome["stage"] = "unresolved"
                    outcome["decision_provenance"] = _decision_provenance(
                        decision_source="unresolved",
                        message=message,
                        retrieved_memory_keys=_retrieved_memory_keys(combined_memory_context),
                        retrieved_safety_keys=_retrieved_safety_keys(combined_memory_context),
                        safety_memory_used=bool(safety_context),
                    )
                    pending_llm.append({"message": message, "outcome": outcome})
            outcome["decision"] = _decision_envelope(outcome, memory_context=combined_memory_context)
            provider_outcomes.append(outcome)
        pending_llm.sort(key=lambda item: (not bool(item["outcome"]["memory_context"]), item["message"]["date"]))
        provider_outcomes_by_name[provider] = provider_outcomes
        pending_llm_by_provider[provider] = pending_llm

    total_llm_calls = 0
    if llm_client is not None and llm_limit > 0:
        total_llm_calls = _apply_llm_round_robin(
            llm_client=llm_client,
            pending_llm_by_provider=pending_llm_by_provider,
            llm_limit=llm_limit,
        )

    all_outcomes = []
    for provider, _storage_dir in provider_storage_dirs:
        provider_outcomes = provider_outcomes_by_name.get(provider, [])
        base_predictions = provider_base_predictions.get(provider, {})
        stage_counts = Counter(item["stage"] for item in provider_outcomes)
        label_counts = Counter(label for item in provider_outcomes for label in item["labels"])
        safety_counts = Counter(item["decision"]["safety_lane"] for item in provider_outcomes)
        safety_reviews = [
            _serialize_outcome(item)
            for item in provider_outcomes
            if item["decision"]["requires_caution"]
        ]
        unresolved_examples = [
            {
                "sender": item["sender"],
                "subject": item["subject"],
                "sender_key": item["sender_key"],
            }
            for item in provider_outcomes
            if item["stage"] == "unresolved"
        ][:10]
        provider_reports[provider] = {
            "message_count": len(provider_outcomes),
            "resolved_count": len([item for item in provider_outcomes if item["stage"] != "unresolved"]),
            "unresolved_count": stage_counts["unresolved"],
            "stage_counts": dict(stage_counts),
            "label_counts": dict(label_counts),
            "safety_counts": {
                "security-sensitive": safety_counts.get("security-sensitive", 0),
                "suspicious": safety_counts.get("suspicious", 0),
            },
            "safety_review_count": len(safety_reviews),
            "safety_reviews": safety_reviews,
            "llm_call_count": len([item for item in provider_outcomes if item["llm_confidence"]]),
            "memory_context_hit_count": sum(1 for item in provider_outcomes if item["memory_context_used"]),
            "safety_memory_hit_count": sum(
                1 for item in provider_outcomes if item["decision_provenance"].get("safety_memory_used")
            ),
            "baseline_unresolved_count": len([item for item in provider_outcomes if not base_predictions.get(item["provider"] + ":" + item["batch_id"] + ":" + item["message_id"], [])]),
            "unresolved_examples": unresolved_examples,
            "outcomes": [_serialize_outcome(item) for item in provider_outcomes],
        }
        all_outcomes.extend(provider_outcomes)

    safety_counts = Counter(item["decision"]["safety_lane"] for item in all_outcomes)
    summary = {
        "message_count": len(all_outcomes),
        "resolved_count": len([item for item in all_outcomes if item["stage"] != "unresolved"]),
        "unresolved_count": len([item for item in all_outcomes if item["stage"] == "unresolved"]),
        "deterministic_count": len([item for item in all_outcomes if item["stage"] == "deterministic"]),
        "accepted_memory_count": len([item for item in all_outcomes if item["stage"] == "accepted-memory"]),
        "llm_escalation_count": len([item for item in all_outcomes if item["stage"] == "llm-escalation"]),
        "llm_call_count": total_llm_calls,
        "memory_context_hit_count": sum(1 for item in all_outcomes if item["memory_context_used"]),
        "safety_memory_hit_count": sum(
            1 for item in all_outcomes if item["decision_provenance"].get("safety_memory_used")
        ),
        "safety_counts": {
            "security-sensitive": safety_counts.get("security-sensitive", 0),
            "suspicious": safety_counts.get("suspicious", 0),
        },
        "safety_review_count": sum(1 for item in all_outcomes if item["decision"]["requires_caution"]),
    }
    return {
        "generated_at": _now_iso(),
        "artifact_type": "runtime-cascade-report",
        "providers": provider_reports,
        "summary": summary,
        "method": {
            "stages": [
                "deterministic",
                "accepted-memory",
                "llm-escalation",
                "unresolved",
            ],
            "cluster_memory_usage": (
                "If a cluster decision pack is supplied, matching sender-cluster memory is attached to "
                "LLM escalation payloads as soft prior context."
            ),
            "safety_memory_usage": (
                "If approved safety dispositions exist for a provider-scoped sender or sender-cluster, "
                "that human-reviewed safety context is attached separately during unresolved escalation."
            ),
            "safety_lane": (
                "Messages marked suspicious or security-sensitive are surfaced separately in safety_reviews "
                "and must not be treated as ordinary low-value categorization outcomes."
            ),
        },
    }


def _apply_llm_round_robin(
    llm_client: OpenAIRuntimeCascadeClient,
    pending_llm_by_provider: dict[str, list[dict]],
    llm_limit: int,
) -> int:
    total_llm_calls = 0
    provider_order = [provider for provider, queue in pending_llm_by_provider.items() if queue]
    while provider_order and total_llm_calls < llm_limit:
        next_round = []
        for provider in provider_order:
            queue = pending_llm_by_provider.get(provider, [])
            if not queue or total_llm_calls >= llm_limit:
                continue
            pending = queue.pop(0)
            message = pending["message"]
            outcome = pending["outcome"]
            memory_context = outcome.get("memory_context") or {}
            llm_result = llm_client.analyze_message(_llm_payload(message, memory_context))
            total_llm_calls += 1
            outcome["memory_context_used"] = bool(memory_context)
            outcome["llm_rationale"] = llm_result.get("rationale", "")
            outcome["llm_confidence"] = llm_result.get("confidence", "low")
            if llm_result["labels"] and not llm_result.get("unresolved", False):
                outcome["stage"] = "llm-escalation"
                outcome["labels"] = list(llm_result["labels"])
            outcome["decision_provenance"] = _decision_provenance(
                decision_source=outcome["stage"],
                message=message,
                retrieved_memory_keys=_retrieved_memory_keys(memory_context),
                llm_used=True,
                llm_model=getattr(llm_client, "model", ""),
                llm_confidence=outcome["llm_confidence"],
                llm_abstained=bool(llm_result.get("unresolved", False) or not llm_result["labels"]),
                retrieved_safety_keys=_retrieved_safety_keys(memory_context),
                safety_memory_used=bool(_retrieved_safety_keys(memory_context)),
            )
            outcome["decision"] = _decision_envelope(outcome, memory_context=memory_context)
            if queue:
                next_round.append(provider)
        provider_order = next_round
    return total_llm_calls


def write_runtime_cascade_report(
    output_storage_dir: Path,
    provider_storage_dirs: list[tuple[str, Path]],
    extra_rules: list[TeachableRule] | None = None,
    cluster_decision_pack: dict | None = None,
    llm_client: OpenAIRuntimeCascadeClient | None = None,
    llm_limit: int = 25,
) -> dict:
    report = build_runtime_cascade_report(
        provider_storage_dirs,
        extra_rules=extra_rules,
        cluster_decision_pack=cluster_decision_pack,
        llm_client=llm_client,
        llm_limit=llm_limit,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = runtime_cascade_path(output_storage_dir, f"runtime-cascade-{timestamp}")
    write_json(path, report)
    report["report_path"] = str(path)
    return report


def load_cluster_decision_pack(path: Path) -> dict:
    pack = load_json(path)
    pack["pack_path"] = str(path)
    return pack


def _memory_context_by_key(cluster_decision_pack: dict) -> dict[tuple[str, str], dict]:
    contexts = {}
    for section in (
        "auto_low_value_policies",
        "safety_reviews",
        "personal_policies",
        "preference_reviews",
        "unclear_reviews",
    ):
        for unit in cluster_decision_pack.get(section, []):
            contexts[(unit["provider"], unit["sender_key"])] = unit.get("memory_seed", {})
    return contexts


def _llm_payload(message: dict, memory_context: dict | None) -> dict:
    return {
        "provider": message["provider"],
        "account_id": message["account_id"],
        "sender": message["sender"],
        "subject": message["subject"],
        "snippet": message["snippet"],
        "body": message["body"][:8000],
        "memory_context": memory_context or {},
    }


def _decision_provenance(
    *,
    decision_source: str,
    message: dict,
    matched_rule_ids: list[str] | None = None,
    retrieved_memory_keys: list[str] | None = None,
    retrieved_safety_keys: list[str] | None = None,
    llm_used: bool = False,
    llm_model: str = "",
    llm_confidence: str = "",
    llm_abstained: bool = False,
    safety_memory_used: bool = False,
) -> dict:
    return {
        "decision_source": decision_source,
        "matched_rule_ids": list(matched_rule_ids or []),
        "retrieved_memory_keys": list(retrieved_memory_keys or []),
        "retrieved_safety_keys": list(retrieved_safety_keys or []),
        "llm_used": llm_used,
        "llm_model": llm_model,
        "llm_confidence": llm_confidence,
        "llm_abstained": llm_abstained,
        "safety_memory_used": safety_memory_used,
        "human_review_state": message.get("review_state"),
    }


def _retrieved_memory_keys(memory_context: dict | None) -> list[str]:
    if not memory_context:
        return []
    keys = []
    cluster_policy_key = memory_context.get("cluster_policy_key")
    if cluster_policy_key:
        keys.append(cluster_policy_key)
    sender_key = memory_context.get("sender_key")
    provider_scope = memory_context.get("provider_scope")
    if not keys and sender_key and provider_scope:
        keys.append(f"{provider_scope}:{sender_key}")
    return keys


def _retrieved_safety_keys(memory_context: dict | None) -> list[str]:
    if not memory_context:
        return []
    safety_context = memory_context.get("safety_context")
    if not isinstance(safety_context, dict):
        return []
    disposition_id = safety_context.get("disposition_id")
    return [disposition_id] if disposition_id else []


def _serialize_outcome(outcome: dict) -> dict:
    return {
        "provider": outcome["provider"],
        "account_id": outcome["account_id"],
        "batch_id": outcome["batch_id"],
        "message_id": outcome["message_id"],
        "sender": outcome["sender"],
        "subject": outcome["subject"],
        "sender_key": outcome["sender_key"],
        "subject_key": _normalized_subject(outcome["subject"]),
        "stage": outcome["stage"],
        "labels": list(outcome["labels"]),
        "matched_rule_ids": list(outcome["matched_rule_ids"]),
        "llm_rationale": outcome.get("llm_rationale", ""),
        "llm_confidence": outcome.get("llm_confidence", ""),
        "decision_provenance": dict(outcome["decision_provenance"]),
        "decision": dict(outcome.get("decision", {})),
    }


def _decision_envelope(outcome: dict, memory_context: dict | None = None) -> dict:
    labels = list(outcome.get("labels", []))
    provenance = outcome["decision_provenance"]
    safety_lane = _risk_state(labels, outcome["stage"], memory_context or {}, outcome)
    return {
        "topic_labels": labels,
        "attention_priority": _attention_priority(labels, outcome["stage"]),
        "actionability": _actionability(labels, outcome["stage"]),
        "risk_state": safety_lane,
        "safety_lane": safety_lane,
        "requires_caution": safety_lane != "ordinary",
        "confidence": outcome.get("llm_confidence") or ("medium" if outcome["stage"] != "unresolved" else "low"),
        "abstained": provenance.get("llm_abstained", False) or outcome["stage"] == "unresolved",
        "provenance": dict(provenance),
    }


def _attention_priority(labels: list[str], stage: str) -> str:
    if "reply-needed" in labels or "account-security" in labels:
        return "high"
    if any(label in labels for label in {"financial-account", "shopping-order", "travel", "personal", "job-related"}):
        return "medium"
    if stage == "unresolved":
        return "medium"
    return "low"


def _actionability(labels: list[str], stage: str) -> str:
    if stage == "unresolved":
        return "review"
    if "reply-needed" in labels:
        return "act"
    if "account-security" in labels:
        return "review"
    if any(label in labels for label in {"promotions", "spam-low-value", "newsletter"}):
        return "ignore"
    return "track"


def _risk_state(labels: list[str], stage: str, memory_context: dict, outcome: dict) -> str:
    safety_context = memory_context.get("safety_context") or {}
    if safety_context.get("disposition") == "phishing":
        return "suspicious"
    if safety_context.get("disposition") == "benign-but-watch":
        return "suspicious"
    if safety_context.get("disposition") == "legitimate-security":
        return "security-sensitive"
    if "account-security" in labels or memory_context.get("review_type") == "safety-review":
        return "security-sensitive"
    if safety_context.get("disposition") == "not-safety":
        return "ordinary"
    text = f"{outcome.get('sender','')} {outcome.get('subject','')}".lower()
    suspicious_terms = ("verify your account", "verification code", "invoice", "payment", "package", "urgent")
    if stage == "unresolved" and any(term in text for term in suspicious_terms):
        return "suspicious"
    return "ordinary"


def _approved_safety_contexts(storage_dir: Path) -> list[dict]:
    store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
    contexts = []
    for disposition in store.list_dispositions():
        if disposition.status != "approved":
            continue
        contexts.append(approved_safety_context(disposition))
    return contexts


def _matching_safety_context(safety_contexts: list[dict], message: dict) -> dict:
    for context in safety_contexts:
        if matches_safety_context(message, context):
            return {"safety_context": context}
    return {}


def _merge_memory_contexts(primary: dict, safety_context: dict) -> dict:
    if not primary:
        return dict(safety_context)
    if not safety_context:
        return dict(primary)
    merged = dict(primary)
    merged.update(safety_context)
    return merged


def _normalized_sender_token(sender: str) -> str:
    return normalized_sender_email(sender) or (sender or "").strip().lower()


def _normalized_subject(subject: str) -> str:
    return "".join("#" if char.isdigit() else char for char in (subject or "").strip().lower())


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_confidence(value) -> str:
    if isinstance(value, (int, float)):
        if value >= 0.8:
            return "high"
        if value >= 0.45:
            return "medium"
        return "low"
    if isinstance(value, str) and value in {"low", "medium", "high"}:
        return value
    return "low"
