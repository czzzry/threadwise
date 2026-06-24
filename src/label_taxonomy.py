CANONICAL_LABEL_ORDER = [
    "travel",
    "receipt-billing",
    "shopping-order",
    "financial-account",
    "newsletter",
    "promotions",
    "account-security",
    "calendar-event",
    "personal",
    "job-related",
    "spam-low-value",
    "reply-needed",
]

# Canonical internal taxonomy from docs/archive/alignment-v1-gmail-mvp.md and docs/archive/prd-v1-gmail-mvp.md.
DEFAULT_GMAIL_LABEL_NAMES = {
    "travel": "EA/Travel",
    "receipt-billing": "EA/Receipts",
    "shopping-order": "EA/Orders",
    "financial-account": "EA/Finance",
    "newsletter": "EA/Newsletter",
    "promotions": "EA/Promotions",
    "account-security": "EA/Account",
    "calendar-event": "EA/Calendar",
    "personal": "EA/Personal",
    "job-related": "EA/Work",
    "spam-low-value": "EA/LowValue",
    "reply-needed": "EA/ReplyNeeded",
}


def gmail_label_name(internal_label: str) -> str:
    return DEFAULT_GMAIL_LABEL_NAMES[internal_label]


def allowed_gmail_labels() -> list[str]:
    return [DEFAULT_GMAIL_LABEL_NAMES[label] for label in CANONICAL_LABEL_ORDER]
