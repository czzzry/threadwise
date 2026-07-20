import imaplib
import json
import ssl
from collections.abc import Callable
from datetime import UTC, datetime
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from pathlib import Path
import re

from src.rfc822_readable_content import extract_readable_content


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

    def list_messages(self, max_results: int, mailbox: str = "INBOX") -> list[str]:
        connection = self._open_connection(mailbox=mailbox)
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

    def list_mailboxes(self) -> list[str]:
        connection = self._open_connection()
        try:
            status, data = connection.list()
            _require_ok(status, "list mailboxes")
            return [
                mailbox
                for raw_entry in data or []
                if raw_entry and (mailbox := _mailbox_name_from_list_entry(raw_entry))
            ]
        finally:
            _safe_close(connection)

    def get_message(self, message_id: str) -> dict:
        connection = self._open_connection()
        try:
            status, data = connection.uid("fetch", message_id, "(RFC822)")
            _require_ok(status, f"fetch message {message_id}")
            raw_message = _extract_rfc822_bytes(data)
            parsed_message = message_from_bytes(raw_message)
            body = extract_readable_content(parsed_message)
            snippet = body.splitlines()[0][:160] if body else parsed_message.get("Subject", "")[:160]
            date_header = parsed_message.get("Date", "")
            if date_header:
                date = parsedate_to_datetime(date_header).astimezone(UTC)
            else:
                date = datetime.now(tz=UTC)
            return {
                "id": message_id,
                "rfc_message_id": parsed_message.get("Message-ID", ""),
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

    def message_has_label(self, rfc_message_id: str, label_name: str) -> bool:
        if not rfc_message_id.strip():
            return False
        mailbox = _proton_label_mailbox(label_name)
        connection = self._open_connection(mailbox=mailbox)
        try:
            status, data = connection.uid("SEARCH", None, "HEADER", "Message-ID", rfc_message_id)
            _require_ok(status, f"verify label {label_name}")
            raw_ids = data[0].decode("utf-8").strip() if data and data[0] else ""
            return bool(raw_ids)
        finally:
            _safe_close(connection)

    def apply_label(self, message_id: str, label_name: str) -> dict:
        mailbox = _proton_label_mailbox(label_name)
        connection = self._open_connection(mailbox="INBOX", readonly=False)
        try:
            status, data = connection.list()
            _require_ok(status, "list mailboxes before label write")
            existing = {
                parsed
                for raw_entry in data or []
                if raw_entry and (parsed := _mailbox_name_from_list_entry(raw_entry))
            }
            if mailbox not in existing:
                status, _ = connection.create(mailbox)
                _require_ok(status, f"create label {label_name}")
            status, _ = connection.uid("COPY", message_id, mailbox)
            _require_ok(status, f"apply label {label_name} to message {message_id}")
            return {
                "message_id": message_id,
                "label": label_name,
                "mailbox": mailbox,
                "inbox_preserved": True,
                "destructive_actions": [],
            }
        finally:
            _safe_close(connection)

    def _open_connection(self, *, mailbox: str = "INBOX", readonly: bool = True):
        connection = self._imap_factory(self._host, self._port)
        if self._security == "STARTTLS":
            connection.starttls(ssl_context=_starttls_context_for_host(self._host))
        connection.login(self._username, self._password)
        connection.select(mailbox, readonly=readonly)
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


def _mailbox_name_from_list_entry(raw_entry: bytes) -> str:
    entry = raw_entry.decode("utf-8", errors="replace").strip()
    quoted = re.search(r'"((?:[^"\\]|\\.)*)"\s*$', entry)
    if quoted:
        return quoted.group(1).replace(r'\"', '"').replace(r'\\', '\\')
    parts = entry.rsplit(" ", 1)
    return parts[-1].strip('"') if parts else ""


def _proton_label_mailbox(label_name: str) -> str:
    if not label_name.startswith("EA/"):
        raise ValueError("Threadwise Proton labels must use the EA/ namespace.")
    suffix = label_name.removeprefix("EA/").strip()
    if not suffix or not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", suffix):
        raise ValueError("Threadwise Proton label contains unsupported characters.")
    # Bridge exposes Proton labels beneath Labels/. A hyphen preserves the
    # Threadwise namespace without turning the slash into a mailbox hierarchy.
    return f"Labels/EA-{suffix}"
