import json
import tempfile
import unittest
from pathlib import Path

from src.live_outlookmail_client import LiveOutlookMailClient, SetupError


class FakeIMAPConnection:
    def __init__(self, messages: dict[str, bytes]) -> None:
        self._messages = messages
        self.calls: list[tuple] = []
        self.started_tls = False

    def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
        self.calls.append(("login", username, password))
        return ("OK", [b"logged in"])

    def starttls(self, ssl_context=None) -> tuple[str, list[bytes]]:
        del ssl_context
        self.started_tls = True
        self.calls.append(("starttls",))
        return ("OK", [b"tls started"])

    def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        self.calls.append(("select", mailbox, readonly))
        return ("OK", [b"1"])

    def uid(self, command: str, *args: str) -> tuple[str, list[bytes | tuple[bytes, bytes]]]:
        self.calls.append(("uid", command, *args))
        if command.lower() == "search":
            joined = b" ".join(uid.encode("utf-8") for uid in self._messages)
            return ("OK", [joined])
        if command.lower() == "fetch":
            message_id = args[0]
            return ("OK", [(b"1 (RFC822 {42}", self._messages[message_id])])
        raise AssertionError(f"Unexpected IMAP command: {command}")

    def close(self) -> tuple[str, list[bytes]]:
        self.calls.append(("close",))
        return ("OK", [b"closed"])

    def logout(self) -> tuple[str, list[bytes]]:
        self.calls.append(("logout",))
        return ("BYE", [b"logged out"])


class LiveOutlookMailClientTests(unittest.TestCase):
    def test_from_imap_config_reads_recent_inbox_messages_via_read_only_imap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_imap_config(credentials_dir)
            raw_message = (
                b"From: Billing <billing@example.com>\r\n"
                b"Subject: Monthly statement ready\r\n"
                b"Date: Fri, 19 Jun 2026 08:00:00 +0000\r\n"
                b"\r\n"
                b"Your latest statement is ready to review."
            )
            imap_connection = FakeIMAPConnection({"101": raw_message, "102": raw_message})

            client = LiveOutlookMailClient.from_imap_config(
                "founder-hotmail",
                credentials_dir,
                password_override=None,
                imap_factory=lambda host, port: imap_connection,
            )

            message_ids = client.list_messages(max_results=1)
            message = client.get_message("102")

            self.assertEqual(message_ids, ["102"])
            self.assertEqual(message["id"], "102")
            self.assertEqual(message["sender"], "Billing <billing@example.com>")
            self.assertEqual(message["subject"], "Monthly statement ready")
            self.assertIn("statement is ready", message["body"])
            self.assertEqual(
                imap_connection.calls,
                [
                    ("login", "cbaraniecki@hotmail.com", "mail-pass"),
                    ("select", "INBOX", True),
                    ("uid", "search", None, "ALL"),
                    ("close",),
                    ("logout",),
                    ("login", "cbaraniecki@hotmail.com", "mail-pass"),
                    ("select", "INBOX", True),
                    ("uid", "fetch", "102", "(RFC822)"),
                    ("close",),
                    ("logout",),
                ],
            )

    def test_from_imap_config_starts_tls_when_security_is_starttls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_imap_config(credentials_dir, security="STARTTLS", ssl_enabled=False)
            raw_message = (
                b"From: Billing <billing@example.com>\r\n"
                b"Subject: Monthly statement ready\r\n"
                b"Date: Fri, 19 Jun 2026 08:00:00 +0000\r\n"
                b"\r\n"
                b"Your latest statement is ready to review."
            )
            imap_connection = FakeIMAPConnection({"101": raw_message})

            client = LiveOutlookMailClient.from_imap_config(
                "founder-hotmail",
                credentials_dir,
                password_override=None,
                imap_factory=lambda host, port: imap_connection,
            )

            message_ids = client.list_messages(max_results=1)

            self.assertEqual(message_ids, ["101"])
            self.assertTrue(imap_connection.started_tls)

    def test_from_imap_config_raises_setup_error_when_config_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(SetupError) as raised:
                LiveOutlookMailClient.from_imap_config("founder-hotmail", Path(temp_dir))

        self.assertIn("No Outlook IMAP config found", str(raised.exception))

    def _write_imap_config(self, credentials_dir: Path, security: str = "SSL", ssl_enabled: bool = True) -> None:
        imap_dir = credentials_dir / "imap"
        imap_dir.mkdir(parents=True, exist_ok=True)
        (imap_dir / "founder-hotmail.json").write_text(
            json.dumps(
                {
                    "host": "outlook.office365.com",
                    "port": 993 if security == "SSL" else 143,
                    "username": "cbaraniecki@hotmail.com",
                    "password": "mail-pass",
                    "ssl": ssl_enabled,
                    "security": security,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
