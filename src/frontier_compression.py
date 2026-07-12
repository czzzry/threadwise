from collections import defaultdict
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from src.classifier_corpus_eval import _apply_extra_rules, _classify_messages, _family_key, _load_corpus_messages
from src.local_artifacts import frontier_plan_path, safety_dispositions_path, write_json
from src.safety_disposition_store import SafetyDispositionStore
from src.sender_utils import normalized_sender_email
from src.teachable_rule_memory import TeachableRule


LOW_VALUE_TERMS = (
    "discount",
    "coupon",
    "gutschein",
    "rabatt",
    "sale",
    "% off",
    "new posts",
    "in your feed",
    "newsletter",
    "season",
    "rewards program terms",
    "terms and conditions",
    "privacy policy",
    "waits for you",
    "free delivery",
)

SECURITY_TERMS = (
    "security",
    "verify",
    "verification",
    "confirm your registration",
    "sign-in",
    "sign in",
    "login",
    "password",
    "account",
    "trust",
    "alert",
    "code",
)

PERSONAL_MESSAGE_TERMS = (
    "sent you a message",
    "group conversation",
)


class OpenAIFrontierClusterClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls, model: str) -> "OpenAIFrontierClusterClient":
        api_key = os.environ.get("EMAIL_AGENT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("EMAIL_AGENT_OPENAI_API_KEY or OPENAI_API_KEY is required for frontier clustering.")
        return cls(api_key=api_key, model=model)

    def analyze_cluster(self, cluster: dict) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You analyze unresolved inbox sender clusters. "
                        "Return strict JSON with keys review_mode, labels, confidence, rationale. "
                        "review_mode must be one of auto-low-value, safety-review, preference-review, personal-review, unclear. "
                        "labels must contain 0 to 3 values from: personal, receipt-billing, account-security, travel, "
                        "shopping-order, spam-low-value, promotions, newsletter, job-related, financial-account, "
                        "reply-needed, calendar-event."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(cluster, ensure_ascii=False),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
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
            "review_mode": parsed.get("review_mode", "unclear"),
            "labels": list(parsed.get("labels", []))[:3],
            "confidence": parsed.get("confidence", "low"),
            "rationale": parsed.get("rationale", ""),
        }


def build_frontier_compression_plan(
    provider_storage_dirs: list[tuple[str, Path]],
    extra_rules: list[TeachableRule] | None = None,
    llm_client: OpenAIFrontierClusterClient | None = None,
    llm_limit: int = 8,
) -> dict:
    safety_contexts_by_provider = {
        provider: _approved_safety_contexts(storage_dir)
        for provider, storage_dir in provider_storage_dirs
    }
    clusters = _build_sender_clusters(provider_storage_dirs, extra_rules or [], safety_contexts_by_provider)
    auto_low_value = []
    safety_review = []
    personal_review = []
    preference_review = []
    unclear = []

    ambiguous_for_llm = []
    for cluster in clusters:
        heuristics = _heuristic_review_mode(cluster)
        cluster["review_mode"] = heuristics["review_mode"]
        cluster["suggested_labels"] = heuristics["labels"]
        cluster["heuristic_rationale"] = heuristics["rationale"]
        cluster["confidence"] = heuristics["confidence"]
        cluster["safety_priority"] = _cluster_safety_priority(cluster)
        if llm_client is not None and cluster["review_mode"] == "unclear" and len(ambiguous_for_llm) < llm_limit:
            ambiguous_for_llm.append(cluster)

    for cluster in ambiguous_for_llm:
        llm_result = llm_client.analyze_cluster(_llm_cluster_payload(cluster))
        cluster["llm_review_mode"] = llm_result["review_mode"]
        cluster["llm_labels"] = llm_result["labels"]
        cluster["llm_confidence"] = llm_result["confidence"]
        cluster["llm_rationale"] = llm_result["rationale"]
        if llm_result["review_mode"] != "unclear":
            cluster["review_mode"] = llm_result["review_mode"]
            cluster["suggested_labels"] = llm_result["labels"]
            cluster["confidence"] = llm_result["confidence"]
        cluster["safety_priority"] = _cluster_safety_priority(cluster)

    for cluster in clusters:
        if cluster["review_mode"] == "auto-low-value":
            auto_low_value.append(cluster)
        elif cluster["review_mode"] == "safety-review":
            safety_review.append(cluster)
        elif cluster["review_mode"] == "personal-review":
            personal_review.append(cluster)
        elif cluster["review_mode"] == "preference-review":
            preference_review.append(cluster)
        else:
            unclear.append(cluster)

    return {
        "generated_at": _now_iso(),
        "artifact_type": "frontier-compression-plan",
        "summary": {
            "total_unresolved_sender_clusters": len(clusters),
            "total_unresolved_messages": sum(cluster["message_count"] for cluster in clusters),
            "total_unresolved_families": sum(cluster["family_count"] for cluster in clusters),
            "auto_low_value_clusters": len(auto_low_value),
            "safety_review_clusters": len(safety_review),
            "personal_review_clusters": len(personal_review),
            "preference_review_clusters": len(preference_review),
            "unclear_clusters": len(unclear),
            "safety_priority_clusters": sum(1 for cluster in clusters if cluster["safety_priority"]["priority_score"] > 0),
        },
        "top_safety_priority_clusters": _top_safety_clusters(clusters),
        "auto_low_value_clusters": auto_low_value[:50],
        "safety_review_clusters": safety_review[:50],
        "personal_review_clusters": personal_review[:50],
        "preference_review_clusters": preference_review[:50],
        "unclear_clusters": unclear[:50],
    }


def write_frontier_compression_plan(
    output_storage_dir: Path,
    provider_storage_dirs: list[tuple[str, Path]],
    extra_rules: list[TeachableRule] | None = None,
    llm_client: OpenAIFrontierClusterClient | None = None,
    llm_limit: int = 8,
) -> dict:
    plan = build_frontier_compression_plan(
        provider_storage_dirs,
        extra_rules=extra_rules,
        llm_client=llm_client,
        llm_limit=llm_limit,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = frontier_plan_path(output_storage_dir, f"frontier-compression-{timestamp}")
    write_json(path, plan)
    plan["plan_path"] = str(path)
    return plan


def _build_sender_clusters(
    provider_storage_dirs: list[tuple[str, Path]],
    extra_rules: list[TeachableRule],
    safety_contexts_by_provider: dict[str, list[dict]],
) -> list[dict]:
    clusters = []
    for provider, storage_dir in provider_storage_dirs:
        messages = _load_corpus_messages(provider, storage_dir)
        predictions = _classify_messages(provider, messages)
        grouped: dict[str, dict] = {}
        for message in messages:
            if message.get("review_state") == "reviewed":
                continue
            sender_key, subject_key = _family_key(message)
            labels = predictions.get(message["classifier_message_id"], [])
            applied = _apply_extra_rules(labels, message, extra_rules)["labels"]
            if applied:
                continue
            entry = grouped.setdefault(
                sender_key,
                {
                    "provider": provider,
                    "sender_key": sender_key,
                    "message_count": 0,
                    "family_subject_keys": set(),
                    "examples": [],
                    "approved_safety_contexts": [],
                },
            )
            entry["message_count"] += 1
            entry["family_subject_keys"].add(subject_key)
            matching_context = _matching_safety_context(
                safety_contexts_by_provider.get(provider, []),
                message,
            )
            if matching_context and matching_context["disposition_id"] not in {
                context["disposition_id"] for context in entry["approved_safety_contexts"]
            }:
                entry["approved_safety_contexts"].append(matching_context)
            if len(entry["examples"]) < 5:
                entry["examples"].append(
                    {
                        "account_id": message["account_id"],
                        "batch_id": message["batch_id"],
                        "message_id": message["message_id"],
                        "sender": message["sender"],
                        "subject": message["subject"],
                        "subject_key": subject_key,
                    }
                )
        for entry in grouped.values():
            entry["family_count"] = len(entry.pop("family_subject_keys"))
            clusters.append(entry)

    clusters.sort(
        key=lambda cluster: (
            -cluster.get("safety_priority", {}).get("priority_score", 0),
            -cluster["message_count"],
            -cluster["family_count"],
            cluster["provider"],
            cluster["sender_key"],
        )
    )
    return clusters


def _heuristic_review_mode(cluster: dict) -> dict:
    text = " ".join(
        [
            cluster["sender_key"],
            *[example.get("subject_key", "") for example in cluster["examples"]],
            *[example.get("subject", "") for example in cluster["examples"]],
        ]
    ).lower()
    if any(term in text for term in PERSONAL_MESSAGE_TERMS):
        return {
            "review_mode": "personal-review",
            "labels": ["personal", "reply-needed"],
            "confidence": "medium",
            "rationale": "Looks like direct message or conversation notifications.",
        }
    if any(term in text for term in SECURITY_TERMS):
        return {
            "review_mode": "safety-review",
            "labels": ["account-security"],
            "confidence": "medium",
            "rationale": "Looks account, verification, registration, or security related.",
        }
    if _looks_low_value(cluster, text):
        labels = ["spam-low-value"]
        if any(term in text for term in ("discount", "coupon", "gutschein", "rabatt", "% off", "sale", "season", "newsletter")):
            labels = ["promotions", "spam-low-value"]
        return {
            "review_mode": "auto-low-value",
            "labels": labels,
            "confidence": "high",
            "rationale": "Looks like recurring marketing, social feed, or promo noise.",
        }
    if cluster["message_count"] >= 3:
        return {
            "review_mode": "preference-review",
            "labels": [],
            "confidence": "low",
            "rationale": "Recurring unresolved sender cluster without a strong heuristic fit.",
        }
    return {
        "review_mode": "unclear",
        "labels": [],
        "confidence": "low",
        "rationale": "Singleton or weak-signal cluster.",
    }


def _looks_low_value(cluster: dict, text: str) -> bool:
    if any(term in text for term in LOW_VALUE_TERMS):
        return True
    sender = cluster["sender_key"]
    return sender in {
        "instagram",
        "facebook",
        "lieferando",
        "eng-tips forums",
        "john varvatos",
        "awesomebooks",
        "angellist weekly",
        "hunter douglas",
        "yummly",
        "hayneedle",
        "cardschat",
        "calgary philharmonic orchestra",
        "musician's friend",
    }


def _llm_cluster_payload(cluster: dict) -> dict:
    return {
        "provider": cluster["provider"],
        "sender_key": cluster["sender_key"],
        "message_count": cluster["message_count"],
        "family_count": cluster["family_count"],
        "examples": cluster["examples"],
        "approved_safety_contexts": cluster.get("approved_safety_contexts", []),
    }


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _approved_safety_contexts(storage_dir: Path) -> list[dict]:
    store = SafetyDispositionStore(safety_dispositions_path(storage_dir))
    contexts = []
    for disposition in store.list_dispositions():
        if disposition.status != "approved":
            continue
        sender_terms = []
        subject_terms = []
        for example in disposition.source_examples:
            sender = normalized_sender_email(example.get("sender")) or (example.get("sender", "").strip().lower())
            if sender and sender not in sender_terms:
                sender_terms.append(sender)
            subject = _normalized_subject(example.get("subject", ""))
            if subject and subject not in subject_terms:
                subject_terms.append(subject)
        contexts.append(
            {
                "disposition_id": disposition.id,
                "scope": disposition.scope,
                "disposition": disposition.disposition,
                "sender_terms": sender_terms,
                "subject_terms": subject_terms,
            }
        )
    return contexts


def _matching_safety_context(safety_contexts: list[dict], message: dict) -> dict:
    sender = normalized_sender_email(message.get("sender")) or message.get("sender", "").strip().lower()
    subject = _normalized_subject(message.get("subject", ""))
    for context in safety_contexts:
        if sender not in context["sender_terms"]:
            continue
        if context["scope"] == "sender":
            return context
        if subject in context["subject_terms"]:
            return context
    return {}


def _normalized_subject(subject: str) -> str:
    normalized = subject.lower()
    normalized = re.sub(r"\b\d+\b", "#", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:100]


def _cluster_safety_priority(cluster: dict) -> dict:
    score = 0
    reasons = []
    approved_contexts = list(cluster.get("approved_safety_contexts", []))
    if approved_contexts:
        score += 5
        reasons.append("approved-safety-memory")
    if cluster.get("review_mode") == "safety-review":
        score += 3
        reasons.append("safety-review-lane")
    if any(context.get("disposition") == "phishing" for context in approved_contexts):
        score += 2
        reasons.append("phishing-memory")
    if cluster.get("message_count", 0) >= 3:
        score += 1
        reasons.append("repeated-family")
    if any("validation" in reason or "holdout" in reason for reason in reasons):
        score += 1
    return {
        "priority_score": score,
        "reasons": reasons,
        "approved_disposition_ids": [context["disposition_id"] for context in approved_contexts],
        "approved_dispositions": [context.get("disposition", "") for context in approved_contexts],
    }


def _top_safety_clusters(clusters: list[dict], limit: int = 10) -> list[dict]:
    prioritized = [
        {
            "provider": cluster["provider"],
            "sender_key": cluster["sender_key"],
            "message_count": cluster["message_count"],
            "family_count": cluster["family_count"],
            "review_mode": cluster.get("review_mode", ""),
            "safety_priority": dict(cluster.get("safety_priority", {})),
            "examples": list(cluster.get("examples", []))[:3],
        }
        for cluster in clusters
        if cluster.get("safety_priority", {}).get("priority_score", 0) > 0
    ]
    prioritized.sort(
        key=lambda cluster: (
            -cluster["safety_priority"]["priority_score"],
            -cluster["message_count"],
            cluster["provider"],
            cluster["sender_key"],
        )
    )
    return prioritized[:limit]
