import re

from src.sender_utils import normalized_sender_email


SEMANTIC_FAMILY_TERMS = {
    "orders": (
        "order confirmation",
        "order status",
        "order update",
        "shipment",
        "shipping",
        "delivery",
        "dispatched",
        "out for delivery",
        "track package",
        "tracking",
    ),
    "account-security": (
        "account security",
        "account locked",
        "locked your account",
        "sign-in",
        "signed in",
        "login",
        "password reset",
        "password-reset",
        "verification",
        "suspicious login",
    ),
    "privacy-legal": (
        "privacy policy",
        "privacy-policy",
        "privacy notice",
        "user agreement",
        "user-agreement",
        "terms update",
        "terms-update",
        "terms of service",
    ),
    "promotions": (
        "promotion",
        "promotional",
        "marketing",
        "discount",
        "sale",
        "special offer",
    ),
    "receipts": (
        "receipt",
        "invoice",
        "billing",
        "charged",
        "payment confirmation",
    ),
    "newsletter": ("newsletter", "digest", "roundup"),
    "travel": ("flight", "hotel", "booking", "reservation", "itinerary"),
    "jobs": ("job", "recruiter", "interview", "application", "hiring"),
    "reply": ("reply", "respond", "response required", "answer needed"),
}

FAMILY_DESCRIPTIONS = {
    "orders": "purchase confirmations and shipment, delivery, or order-status emails",
    "account-security": "account, security, or statement notices",
    "privacy-legal": "privacy-policy, user-agreement, or terms-update notices",
    "promotions": "marketing or promotional emails",
    "receipts": "billing, receipt, invoice, or payment notices",
    "newsletter": "newsletter or digest emails",
    "travel": "travel and booking emails",
    "jobs": "job, recruiter, or interview emails",
    "reply": "emails that directly require a reply",
}

LABEL_FAMILIES = {
    "shopping-order": "orders",
    "account-security": "account-security",
    "promotions": "promotions",
    "receipt-billing": "receipts",
    "newsletter": "newsletter",
    "travel": "travel",
    "job-related": "jobs",
    "reply-needed": "reply",
}

NEGATIVE_MARKERS = (
    "do not",
    "don't",
    "dont",
    "never",
    "exclude",
    "excluding",
    "except",
    "must not",
    "should not",
    "shouldn't",
    "not include",
)


def build_semantic_boundary(
    *,
    note: str,
    target_label: str,
    llm_pattern: str = "",
    llm_cross_sender: bool = False,
    llm_confidence: str = "",
) -> dict:
    normalized_note = _normalize(note)
    positive_families: list[str] = []
    excluded_families: list[str] = []
    for clause in _clauses(normalized_note):
        destination = excluded_families if any(marker in clause for marker in NEGATIVE_MARKERS) else positive_families
        for family in _families_in_text(clause):
            if family not in destination:
                destination.append(family)

    target_family = LABEL_FAMILIES.get(target_label)
    if target_family:
        if target_family in excluded_families:
            excluded_families.remove(target_family)
        positive_families = [target_family]

    llm_families = _families_in_text(_normalize(llm_pattern))
    llm_contradicts_note = any(family in excluded_families for family in llm_families)
    if llm_pattern and not llm_contradicts_note and not positive_families:
        pattern = " ".join(str(llm_pattern).split())
    else:
        pattern = _pattern_for_families(positive_families)

    cross_sender = bool(llm_cross_sender) or bool(
        re.search(
            r"\b(?:any|all|every) (?:merchant|sender|retailer|store|company|service)s?\b|"
            r"\bregardless of (?:merchant|sender|domain)\b|\bacross (?:merchants|senders|domains)\b",
            normalized_note,
        )
    )
    has_strong_signal = bool(positive_families) and (
        bool(excluded_families)
        or cross_sender
        or (bool(llm_pattern) and str(llm_confidence).lower() in {"medium", "high"})
        or bool(re.search(r"\b(?:only|specifically|apply this to|classify only)\b", normalized_note))
    )
    return {
        "name": pattern,
        "include_families": positive_families,
        "exclude_families": excluded_families,
        "cross_sender": cross_sender,
        "has_strong_signal": has_strong_signal,
        "llm_contradicted_note": llm_contradicts_note,
    }


def semantic_rule_matches_message(rule: dict, message: dict) -> bool:
    sender = normalized_sender_email(message.get("sender") or "") or ""
    rule_sender = normalized_sender_email(rule.get("sender") or "") or str(rule.get("sender") or "").lower()
    if not rule.get("cross_sender") and rule_sender and sender != rule_sender:
        return False

    text = _normalize(
        " ".join(
            str(message.get(field) or "")
            for field in ("subject", "snippet", "body", "interpretation")
        )
    )
    message_families = set(_families_in_text(text))
    excluded = set(rule.get("exclude_families") or [])
    if message_families & excluded:
        return False
    included = set(rule.get("include_families") or [])
    if included:
        return bool(message_families & included)
    return False


def semantic_search_keywords(rule: dict) -> list[str]:
    keywords: list[str] = []
    for family in rule.get("include_families") or []:
        for phrase in SEMANTIC_FAMILY_TERMS.get(family, ()):
            keyword = phrase.split()[0]
            if keyword not in keywords:
                keywords.append(keyword)
            if len(keywords) >= 6:
                return keywords
    return keywords


def semantic_gmail_search_clauses(rule: dict) -> tuple[list[str], list[str]]:
    include_clauses = _gmail_subject_clauses(rule.get("include_families") or [], limit=10)
    exclude_clauses = _gmail_subject_clauses(rule.get("exclude_families") or [], limit=12)
    return include_clauses, [f"-{clause}" for clause in exclude_clauses]


def _gmail_subject_clauses(families: list[str], *, limit: int) -> list[str]:
    clauses: list[str] = []
    family_terms = [list(SEMANTIC_FAMILY_TERMS.get(family, ())) for family in families]
    term_index = 0
    while len(clauses) < limit and any(term_index < len(terms) for terms in family_terms):
        for terms in family_terms:
            if term_index >= len(terms):
                continue
            term = terms[term_index]
            clause = f'subject:"{term}"' if " " in term else f"subject:{term}"
            if clause not in clauses:
                clauses.append(clause)
            if len(clauses) >= limit:
                break
        term_index += 1
    return clauses


def _families_in_text(text: str) -> list[str]:
    families: list[str] = []
    for family, terms in SEMANTIC_FAMILY_TERMS.items():
        if any(_contains_term(text, term) for term in terms):
            families.append(family)
    return families


def _contains_term(text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", text))


def _clauses(text: str) -> list[str]:
    return [clause.strip() for clause in re.split(r"[.!?;]+", text) if clause.strip()]


def _pattern_for_families(families: list[str]) -> str:
    descriptions = [FAMILY_DESCRIPTIONS[family] for family in families if family in FAMILY_DESCRIPTIONS]
    return " or ".join(descriptions)


def _normalize(value: str) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").split())
