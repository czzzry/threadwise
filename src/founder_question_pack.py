from datetime import UTC, datetime
from pathlib import Path

from src.local_artifacts import founder_question_pack_path, write_json


QUESTION_THEME_CONFIG = {
    "marketing-preference": {
        "title": "How should recurring marketing mail be handled?",
        "prompt": (
            "For recurring promos, coupons, and low-value list mail from these families, do you want them "
            "defaulted to low-value/promo handling, or kept visible by default?"
        ),
    },
    "account-security-handling": {
        "title": "How strict should account and verification mail stay?",
        "prompt": (
            "For recurring verification, sign-in, and account-security style messages, should they always stay "
            "visible, or can some be treated as lower-priority unless tied to active account use?"
        ),
    },
    "events-and-confirmations": {
        "title": "How should registrations and confirmations be categorized?",
        "prompt": (
            "For event registrations, confirmations, and appointment-like mail, should these default to "
            "calendar/travel/personal handling, and which of those should take precedence?"
        ),
    },
    "taxonomy-gap": {
        "title": "Which missing concept best fits these unresolved families?",
        "prompt": (
            "These recurring families do not fit the current taxonomy cleanly. Should one existing label be used, "
            "or is this evidence that we need a tighter concept before teaching memory?"
        ),
    },
    "personal-vs-low-value": {
        "title": "What is personal enough to stay visible?",
        "prompt": (
            "For recurring families that look semi-personal but low urgency, should they stay visible as personal, "
            "or be treated as low-value by default?"
        ),
    },
    "direct-message-handling": {
        "title": "How should direct person-to-person message alerts be handled?",
        "prompt": (
            "For recurring message notifications from named people or networks, should these stay visible as personal "
            "by default, or can they be treated as lower-priority unless they come from specific senders you care about?"
        ),
    },
    "terms-and-policy-updates": {
        "title": "How should terms, policy, and program-update mail be handled?",
        "prompt": (
            "For recurring terms updates, policy notices, and rewards-program changes, do you want these treated as "
            "newsletter/low-value updates by default, or kept visible unless they affect an account you actively use?"
        ),
    },
    "shopping-and-order-confirmations": {
        "title": "How should registrations, purchases, and confirmations be categorized?",
        "prompt": (
            "For registrations, purchases, confirmations, and service bookings, should these default to shopping/order, "
            "calendar/event, or personal handling?"
        ),
    },
}


def build_founder_question_pack(
    *,
    review_pack: dict,
    memory_impact: dict | None = None,
    provider_drivers: list[dict] | None = None,
    max_questions: int = 8,
    exclude_question_ids: set[str] | None = None,
) -> dict:
    excluded = exclude_question_ids or set()
    grouped = {}
    for target in review_pack.get("top_review_targets", []):
        theme = _question_theme(target)
        key = (theme, _scope_key(target, theme))
        group = grouped.setdefault(
            key,
            {
                "theme": theme,
                "scope_key": key[1],
                "providers": set(),
                "targets": [],
                "estimated_message_gain": 0,
                "family_count": 0,
                "priority_score": 0,
                "example_senders": [],
                "suggested_labels": set(),
            },
        )
        group["providers"].add(target.get("provider", ""))
        group["targets"].append(target)
        group["estimated_message_gain"] += int(target.get("review_priority", {}).get("estimated_message_gain", target.get("count", 0)))
        group["family_count"] += 1
        group["priority_score"] = max(group["priority_score"], int(target.get("review_priority", {}).get("score", 0)))
        sender_key = target.get("sender_key", "")
        if sender_key and sender_key not in group["example_senders"]:
            group["example_senders"].append(sender_key)
        for label in target.get("suggested_labels", []):
            group["suggested_labels"].add(label)

    questions = []
    driver_score_by_provider = {item.get("provider", ""): item.get("driver_score", 0) for item in (provider_drivers or [])}
    next_payoffs = (memory_impact or {}).get("next_review_payoffs", [])
    payoff_index = {
        (item.get("provider", ""), item.get("sender_key", ""), item.get("subject_key", "")): item
        for item in next_payoffs
    }

    for group in grouped.values():
        payoff_total = 0
        for target in group["targets"]:
            payoff = payoff_index.get((target.get("provider", ""), target.get("sender_key", ""), target.get("subject_key", "")))
            if payoff is not None:
                payoff_total += int(payoff.get("expected_resolved_messages", 0))
        config = QUESTION_THEME_CONFIG[group["theme"]]
        providers = sorted(provider for provider in group["providers"] if provider)
        driver_bonus = max((driver_score_by_provider.get(provider, 0) for provider in providers), default=0)
        score = group["priority_score"] + group["estimated_message_gain"] + driver_bonus
        questions.append(
            {
                "question_id": _question_id(group["theme"], group["scope_key"]),
                "theme": group["theme"],
                "title": config["title"],
                "prompt": config["prompt"],
                "providers": providers,
                "provider_driver_score": driver_bonus,
                "family_count": group["family_count"],
                "estimated_message_gain": group["estimated_message_gain"],
                "estimated_unblocked_messages": payoff_total or group["estimated_message_gain"],
                "priority_score": score,
                "example_senders": group["example_senders"][:5],
                "suggested_labels": sorted(group["suggested_labels"]),
                "example_targets": [
                    {
                        "provider": target.get("provider", ""),
                        "sender_key": target.get("sender_key", ""),
                        "subject_key": target.get("subject_key", ""),
                        "question_lane": target.get("question_lane", ""),
                        "count": target.get("count", 0),
                    }
                    for target in group["targets"][:5]
                ],
                "draft_answers": _draft_answers(group["theme"], sorted(group["suggested_labels"])),
            }
        )

    questions.sort(
        key=lambda item: (
            -item["priority_score"],
            -item["estimated_unblocked_messages"],
            -item["family_count"],
            item["theme"],
            ",".join(item["providers"]),
        )
    )
    questions = [question for question in questions if question["question_id"] not in excluded]
    return {
        "generated_at": _now_iso(),
        "artifact_type": "founder-question-pack",
        "summary": {
            "question_count": min(len(questions), max_questions),
            "raw_question_count": len(questions),
            "estimated_unblocked_messages": sum(item["estimated_unblocked_messages"] for item in questions[:max_questions]),
        },
        "questions": questions[:max_questions],
    }


def write_founder_question_pack(
    output_storage_dir: Path,
    *,
    review_pack: dict,
    memory_impact: dict | None = None,
    provider_drivers: list[dict] | None = None,
    max_questions: int = 8,
    exclude_question_ids: set[str] | None = None,
) -> dict:
    payload = build_founder_question_pack(
        review_pack=review_pack,
        memory_impact=memory_impact,
        provider_drivers=provider_drivers,
        max_questions=max_questions,
        exclude_question_ids=exclude_question_ids,
    )
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    path = founder_question_pack_path(output_storage_dir, f"founder-question-pack-{timestamp}")
    write_json(path, payload)
    payload["pack_path"] = str(path)
    return payload


def _question_theme(target: dict) -> str:
    labels = set(target.get("suggested_labels", []))
    lane = target.get("question_lane", "")
    text = _target_text(target)
    if {"promotions", "spam-low-value", "newsletter"} & labels:
        return "marketing-preference"
    if "account-security" in labels:
        return "account-security-handling"
    if {"calendar-event", "travel"} & labels:
        return "events-and-confirmations"
    if "personal" in labels and lane == "preference-question":
        return "personal-vs-low-value"
    if _contains_any(text, ("rabatt", "gutschein", "coupon", "sale", "discount", "offer", "einkaufen", "lieferando", "deal")):
        return "marketing-preference"
    if _contains_any(text, ("verify", "verification", "passkey", "password", "sign-in", "login", "account will close", "paypal account")):
        return "account-security-handling"
    if _contains_any(
        text,
        ("[task update]", "task update", "weekly reflection", "plan ahead", "morning routine", "publish your", "reflect on"),
    ):
        return "personal-vs-low-value"
    if _contains_any(text, ("terms and conditions", "terms of use", "terms", "policy", "rewards program", "program terms")):
        return "terms-and-policy-updates"
    if _contains_any(text, ("kauf", "purchase", "receipt", "invoice", "billing", "order", "checkout")):
        return "shopping-and-order-confirmations"
    if _contains_any(text, ("anmeldung", "registration", "booking", "reservation", "appointment", "event", "ticket", "class", "eversports")):
        return "events-and-confirmations"
    if _contains_any(
        text,
        ("sent you a message", "messaged you", "message.", "message ", "replied", "direct message", "via linkedin"),
    ):
        return "direct-message-handling"
    if lane == "taxonomy-question":
        return "taxonomy-gap"
    return "marketing-preference" if lane == "preference-question" else "taxonomy-gap"


def _scope_key(target: dict, theme: str) -> str:
    lane = target.get("question_lane", "")
    if theme in {
        "marketing-preference",
        "account-security-handling",
        "events-and-confirmations",
        "personal-vs-low-value",
        "direct-message-handling",
        "terms-and-policy-updates",
        "shopping-and-order-confirmations",
    }:
        return theme
    provider = target.get("provider", "")
    return f"{provider}:{theme}:{lane}"


def _draft_answers(theme: str, suggested_labels: list[str]) -> list[dict]:
    if theme == "marketing-preference":
        return [
            {"answer_key": "low_value_default", "description": "Default these families to promo/low-value handling."},
            {"answer_key": "keep_visible", "description": "Keep these visible unless a narrower rule is approved."},
        ]
    if theme == "account-security-handling":
        return [
            {"answer_key": "always_visible", "description": "Keep account/security families visible by default."},
            {"answer_key": "known_service_low_priority", "description": "Lower priority for known service security flows unless urgent."},
        ]
    if theme == "events-and-confirmations":
        return [
            {"answer_key": "calendar_event_default", "description": "Treat these as calendar/event style mail by default."},
            {"answer_key": "personal_default", "description": "Treat these as personal confirmations by default."},
        ]
    if theme == "personal-vs-low-value":
        return [
            {"answer_key": "personal_default", "description": "Keep semi-personal families visible as personal."},
            {"answer_key": "low_value_default", "description": "Treat semi-personal low-urgency families as low-value by default."},
        ]
    if theme == "direct-message-handling":
        return [
            {"answer_key": "personal_default", "description": "Keep direct-message alerts visible as personal by default."},
            {"answer_key": "sender_allowlist_only", "description": "Keep only specific senders visible and lower-prioritize the rest."},
        ]
    if theme == "terms-and-policy-updates":
        return [
            {"answer_key": "low_value_update_default", "description": "Treat most terms/policy updates as low-value updates."},
            {"answer_key": "keep_account_related_visible", "description": "Keep terms/policy mail visible when it affects accounts you actively use."},
        ]
    if theme == "shopping-and-order-confirmations":
        return [
            {"answer_key": "shopping_order_default", "description": "Treat these as shopping/order or purchase confirmations by default."},
            {"answer_key": "receipt_billing_default", "description": "Treat these as receipts, invoices, or billing confirmations by default."},
            {"answer_key": "calendar_or_personal_default", "description": "Treat these as event/personal confirmations instead."},
        ]
    labels = ", ".join(suggested_labels) if suggested_labels else "one current label or none"
    return [
        {"answer_key": "map_existing_label", "description": f"Choose {labels} or another existing label."},
        {"answer_key": "leave_unresolved", "description": "Do not teach memory until the taxonomy is clearer."},
    ]


def _question_id(theme: str, scope_key: str) -> str:
    fragment = scope_key.replace(":", "-").replace(",", "-")
    return f"question-{theme}-{fragment}"


def _target_text(target: dict) -> str:
    parts = [
        target.get("sender_key", ""),
        target.get("subject_key", ""),
        *[example.get("sender", "") for example in target.get("examples", [])],
        *[example.get("subject", "") for example in target.get("examples", [])],
    ]
    return " ".join(parts).lower()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
