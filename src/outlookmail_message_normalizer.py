from datetime import UTC, datetime
from email.header import decode_header, make_header


def normalize_outlookmail_message(account_id: str, message: dict) -> dict:
    date = _normalize_date(message.get("date"))
    return {
        "source": "outlookmail",
        "account_id": account_id,
        "message_id": message["id"],
        "sender": _decode_header_value(message.get("sender", "")),
        "subject": _decode_header_value(message.get("subject", "")),
        "date": date,
        "snippet": message.get("snippet", ""),
        "body": message.get("body") or message.get("snippet", "") or message.get("subject", ""),
        "gmail_label_ids": [],
        "list_unsubscribe": message.get("list_unsubscribe"),
        "precedence": message.get("precedence", ""),
    }


def _normalize_date(value: str | None) -> str:
    if not value:
        return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    return value


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value
