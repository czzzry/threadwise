import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.live_protonmail_client import LiveProtonMailClient, SetupError


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


class LiveProtonMailClientTests(unittest.TestCase):
    def test_from_bridge_config_reads_recent_inbox_messages_via_read_only_imap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_bridge_config(credentials_dir)
            raw_message = (
                b"From: Billing <billing@example.com>\r\n"
                b"Subject: Monthly statement ready\r\n"
                b"Date: Fri, 19 Jun 2026 08:00:00 +0000\r\n"
                b"\r\n"
                b"Your latest statement is ready to review."
            )
            imap_connection = FakeIMAPConnection({"101": raw_message, "102": raw_message})

            client = LiveProtonMailClient.from_bridge_config(
                "founder-proton",
                credentials_dir,
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
                    ("login", "bridge-user", "bridge-pass"),
                    ("select", "INBOX", True),
                    ("uid", "search", None, "ALL"),
                    ("close",),
                    ("logout",),
                    ("login", "bridge-user", "bridge-pass"),
                    ("select", "INBOX", True),
                    ("uid", "fetch", "102", "(RFC822)"),
                    ("close",),
                    ("logout",),
                ],
            )

    def test_from_bridge_config_starts_tls_when_security_is_starttls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_bridge_config(credentials_dir, security="STARTTLS")
            raw_message = (
                b"From: Billing <billing@example.com>\r\n"
                b"Subject: Monthly statement ready\r\n"
                b"Date: Fri, 19 Jun 2026 08:00:00 +0000\r\n"
                b"\r\n"
                b"Your latest statement is ready to review."
            )
            imap_connection = FakeIMAPConnection({"101": raw_message})

            client = LiveProtonMailClient.from_bridge_config(
                "founder-proton",
                credentials_dir,
                imap_factory=lambda host, port: imap_connection,
            )

            message_ids = client.list_messages(max_results=1)

            self.assertEqual(message_ids, ["101"])
            self.assertTrue(imap_connection.started_tls)
            self.assertEqual(
                imap_connection.calls,
                [
                    ("starttls",),
                    ("login", "bridge-user", "bridge-pass"),
                    ("select", "INBOX", True),
                    ("uid", "search", None, "ALL"),
                    ("close",),
                    ("logout",),
                ],
            )

    def test_from_bridge_config_uses_unverified_tls_context_for_local_starttls_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_bridge_config(credentials_dir, security="STARTTLS")
            raw_message = (
                b"From: Billing <billing@example.com>\r\n"
                b"Subject: Monthly statement ready\r\n"
                b"Date: Fri, 19 Jun 2026 08:00:00 +0000\r\n"
                b"\r\n"
                b"Your latest statement is ready to review."
            )
            imap_connection = FakeIMAPConnection({"101": raw_message})

            with patch("src.live_protonmail_client.ssl._create_unverified_context", return_value="UNVERIFIED") as patched_context:
                client = LiveProtonMailClient.from_bridge_config(
                    "founder-proton",
                    credentials_dir,
                    imap_factory=lambda host, port: imap_connection,
                )

                client.list_messages(max_results=1)

            patched_context.assert_called_once()

    def test_from_bridge_config_raises_setup_error_when_config_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(SetupError) as raised:
                LiveProtonMailClient.from_bridge_config("founder-proton", Path(temp_dir))

        self.assertIn("No ProtonMail Bridge config found", str(raised.exception))

    def _write_bridge_config(self, credentials_dir: Path, security: str | None = None) -> None:
        bridge_dir = credentials_dir / "protonmail_bridge"
        bridge_dir.mkdir(parents=True, exist_ok=True)
        (bridge_dir / "founder-proton.json").write_text(
            json.dumps(
                {
                    "host": "127.0.0.1",
                    "port": 1143,
                    "username": "bridge-user",
                    "password": "bridge-pass",
                    "ssl": False,
                    "security": security,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
