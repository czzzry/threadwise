from email.utils import parseaddr
import re


EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.IGNORECASE)


def normalized_sender_email(sender: str | None) -> str | None:
    if not sender:
        return None

    candidate = sender.strip()
    _, parsed_address = parseaddr(candidate)
    if parsed_address and "@" in parsed_address:
        return parsed_address.strip().lower()

    match = EMAIL_PATTERN.search(candidate)
    address = (match.group(0) if match else candidate).strip().lower()
    if "@" not in address:
        return None
    return address
