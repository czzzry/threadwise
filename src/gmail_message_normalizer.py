import base64
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
import re
from email.utils import parsedate_to_datetime


def normalize_gmail_message(account_id: str, message: dict, fallback_message: dict | None = None) -> dict:
    fallback_message = fallback_message or {}
    headers = {
        header["name"].lower(): header["value"]
        for header in message.get("payload", {}).get("headers", [])
    }
    date_value = headers.get("date")
    if date_value:
        date = parsedate_to_datetime(date_value).astimezone(UTC).isoformat().replace("+00:00", "Z")
    elif message.get("internalDate"):
        date = datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=UTC).isoformat().replace(
            "+00:00", "Z"
        )
    else:
        date = fallback_message.get("date", datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"))

    snippet = message.get("snippet", fallback_message.get("snippet", ""))
    extracted_body = _extract_readable_body(message.get("payload", {}))
    body = extracted_body or fallback_message.get("body") or snippet or fallback_message.get("subject", "")

    return {
        "source": fallback_message.get("source", "gmail"),
        "account_id": account_id,
        "message_id": message.get("id", fallback_message.get("message_id")),
        "sender": headers.get("from", fallback_message.get("sender", "")),
        "subject": headers.get("subject", fallback_message.get("subject", "")),
        "date": date,
        "snippet": snippet,
        "body": body,
        "gmail_label_ids": list(message.get("labelIds", [])),
        "list_unsubscribe": headers.get("list-unsubscribe", fallback_message.get("list_unsubscribe")),
        "precedence": headers.get("precedence", fallback_message.get("precedence", "")),
    }


def _extract_readable_body(payload: dict) -> str:
    plain_text = _extract_first_part_text(payload, "text/plain")
    if plain_text:
        return _sanitize_extracted_text(plain_text)

    html_text = _extract_first_part_text(payload, "text/html")
    if html_text:
        return _sanitize_extracted_text(_html_to_text(html_text))

    return ""


def _extract_first_part_text(payload: dict, mime_type: str) -> str:
    if payload.get("mimeType") == mime_type:
        return _decode_body_data(payload.get("body", {}).get("data", ""))

    for part in payload.get("parts", []):
        extracted = _extract_first_part_text(part, mime_type)
        if extracted:
            return extracted

    return ""


def _decode_body_data(encoded_body: str) -> str:
    if not encoded_body:
        return ""

    padding = "=" * (-len(encoded_body) % 4)
    decoded_bytes = base64.urlsafe_b64decode(encoded_body + padding)
    return decoded_bytes.decode("utf-8", errors="replace").strip()


def _html_to_text(value: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+([.,!?;:])", r"\1", parser.text()).strip()


def _sanitize_extracted_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for raw_line in text.split("\n"):
        line = re.sub(r"https?://\S+", "", raw_line).strip()
        line = re.sub(r"\s+", " ", line)
        if not line:
            continue
        if _looks_like_noise(line):
            continue
        lines.append(line)

    if not lines:
        collapsed = re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", text)).strip()
        return collapsed[:600]

    cleaned = []
    for line in lines:
        if cleaned and cleaned[-1] == line:
            continue
        cleaned.append(line)
        if len(cleaned) >= 8:
            break

    return "\n".join(cleaned)[:1200]


def _looks_like_noise(line: str) -> bool:
    lower = line.lower()
    if len(line) > 140 and ("unsubscribe" in lower or "privacy notice" in lower):
        return True
    if "http" in lower:
        return True
    if sum(char.isalpha() for char in line) < 6:
        return True
    return lower.startswith(
        (
            "facebook ",
            "instagram ",
            "youtube ",
            "tik tok ",
            "tiktok ",
            "x ",
            "privacy notice",
            "faq & help center",
            "all rights reserved",
            "this email was sent to ",
            "email reference number:",
        )
    )


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._block_tags = {"p", "div", "br", "li", "ul", "ol", "section", "tr", "td", "h1", "h2", "h3", "h4"}

    def handle_data(self, data: str) -> None:
        cleaned = unescape(data).strip()
        if cleaned:
            if (
                self._chunks
                and self._chunks[-1]
                and self._chunks[-1][-1].isalnum()
                and cleaned[0].isalnum()
            ):
                self._chunks.append(" ")
            self._chunks.append(cleaned)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._block_tags:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._block_tags:
            self._chunks.append("\n")

    def text(self) -> str:
        return "".join(self._chunks)
