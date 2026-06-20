from datetime import UTC, datetime


def normalize_protonmail_message(account_id: str, message: dict) -> dict:
    date = message.get("date") or datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    return {
        "source": "protonmail",
        "account_id": account_id,
        "message_id": message["id"],
        "sender": message.get("sender", ""),
        "subject": message.get("subject", ""),
        "date": date,
        "snippet": message.get("snippet", ""),
        "body": message.get("body") or message.get("snippet", "") or message.get("subject", ""),
        "gmail_label_ids": [],
        "list_unsubscribe": message.get("list_unsubscribe"),
        "precedence": message.get("precedence", ""),
    }
