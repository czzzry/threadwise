from email.utils import parseaddr


def normalized_sender_email(sender: str | None) -> str | None:
    if not sender:
        return None

    _, address = parseaddr(sender)
    address = address.strip().lower()
    if "@" not in address:
        return None
    return address
