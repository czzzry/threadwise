import imaplib
import json
import ssl
from collections.abc import Callable
from datetime import UTC, datetime
from email import message_from_bytes
from email.message import Message
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re


class SetupError(Exception):
    pass


class LiveProtonMailClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        ssl_enabled: bool = True,
        security: str | None = None,
        imap_factory: Callable[[str, int], object] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssl_enabled = ssl_enabled
        self._security = (security or "").upper()
        self._imap_factory = imap_factory or self._default_imap_factory

    @classmethod
    def from_bridge_config(
        cls,
        account_id: str,
        credentials_dir: Path,
        bridge_config_path: Path | None = None,
        imap_factory: Callable[[str, int], object] | None = None,
    ) -> "LiveProtonMailClient":
        resolved_config_path = _resolve_bridge_config_path(credentials_dir, account_id, bridge_config_path)
        config = json.loads(resolved_config_path.read_text())
        return cls(
            host=config["host"],
            port=int(config["port"]),
            username=config["username"],
            password=config["password"],
            ssl_enabled=config.get("ssl", True),
            security=config.get("security"),
            imap_factory=imap_factory,
        )

    def list_messages(self, max_results: int) -> list[str]:
        connection = self._open_connection()
        try:
            status, data = connection.uid("search", None, "ALL")
            _require_ok(status, "search inbox")
            raw_ids = data[0].decode("utf-8").strip() if data and data[0] else ""
            if not raw_ids:
                return []
            message_ids = raw_ids.split()
            return message_ids[-max_results:]
        finally:
            _safe_close(connection)

    def get_message(self, message_id: str) -> dict:
        connection = self._open_connection()
        try:
            status, data = connection.uid("fetch", message_id, "(RFC822)")
            _require_ok(status, f"fetch message {message_id}")
            raw_message = _extract_rfc822_bytes(data)
            parsed_message = message_from_bytes(raw_message)
            body = _extract_readable_body(parsed_message)
            snippet = body.splitlines()[0][:160] if body else parsed_message.get("Subject", "")[:160]
            date_header = parsed_message.get("Date", "")
            if date_header:
                date = parsedate_to_datetime(date_header).astimezone(UTC)
            else:
                date = datetime.now(tz=UTC)
            return {
                "id": message_id,
                "mailbox": "inbox",
                "sender": parsed_message.get("From", ""),
                "subject": parsed_message.get("Subject", ""),
                "date": date.isoformat().replace("+00:00", "Z"),
                "snippet": snippet,
                "body": body or snippet,
                "list_unsubscribe": parsed_message.get("List-Unsubscribe"),
                "precedence": parsed_message.get("Precedence", ""),
            }
        finally:
            _safe_close(connection)

    def _open_connection(self):
        connection = self._imap_factory(self._host, self._port)
        if self._security == "STARTTLS":
            connection.starttls(ssl_context=_starttls_context_for_host(self._host))
        connection.login(self._username, self._password)
        connection.select("INBOX", readonly=True)
        return connection

    def _default_imap_factory(self, host: str, port: int):
        if self._security == "STARTTLS":
            return imaplib.IMAP4(host, port)
        if self._ssl_enabled:
            return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
        return imaplib.IMAP4(host, port)


def _resolve_bridge_config_path(credentials_dir: Path, account_id: str, bridge_config_path: Path | None) -> Path:
    if bridge_config_path is not None:
        if bridge_config_path.exists():
            return bridge_config_path
        raise SetupError(f"ProtonMail Bridge config not found: {bridge_config_path}")

    default_path = credentials_dir / "protonmail_bridge" / f"{account_id}.json"
    if default_path.exists():
        return default_path

    raise SetupError(
        "No ProtonMail Bridge config found. Expected "
        f"{default_path}. Create it with host, port, username, password, and optional ssl."
    )


def _starttls_context_for_host(host: str):
    if host in {"127.0.0.1", "localhost", "::1"}:
        return ssl._create_unverified_context()
    return ssl.create_default_context()


def _require_ok(status: str, action: str) -> None:
    if status != "OK":
        raise SetupError(f"Could not {action} via ProtonMail Bridge IMAP.")


def _extract_rfc822_bytes(data: list[bytes | tuple[bytes, bytes]]) -> bytes:
    for part in data:
        if isinstance(part, tuple) and len(part) > 1:
            payload = part[1]
            if isinstance(payload, bytes):
                return payload
    raise SetupError("ProtonMail Bridge fetch did not return RFC822 message content.")


def _safe_close(connection) -> None:
    try:
        connection.close()
    finally:
        connection.logout()


def _extract_readable_body(message: Message) -> str:
    plain_text = _extract_first_part_text(message, "text/plain")
    if plain_text:
        return _sanitize_text(plain_text)

    html_text = _extract_first_part_text(message, "text/html")
    if html_text:
        return _sanitize_text(_html_to_text(html_text))

    return ""


def _extract_first_part_text(message: Message, content_type: str) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == content_type:
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace").strip()
        return ""

    if message.get_content_type() != content_type:
        return ""

    payload = message.get_payload(decode=True) or b""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip()


def _sanitize_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        lines.append(line)
        if len(lines) >= 8:
            break
    return "\n".join(lines)[:1200]


def _html_to_text(value: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(value)
    parser.close()
    return re.sub(r"\s+([.,!?;:])", r"\1", parser.text()).strip()


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._block_tags = {"p", "div", "br", "li", "ul", "ol", "section", "tr", "td", "h1", "h2", "h3", "h4"}

    def handle_data(self, data: str) -> None:
        cleaned = unescape(data).strip()
        if cleaned:
            if self._chunks and self._chunks[-1] and self._chunks[-1][-1].isalnum() and cleaned[0].isalnum():
                self._chunks.append(" ")
            self._chunks.append(cleaned)

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag in self._block_tags:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._block_tags:
            self._chunks.append("\n")

    def text(self) -> str:
        return "".join(self._chunks)
