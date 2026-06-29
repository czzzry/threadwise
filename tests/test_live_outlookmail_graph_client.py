import json
import socket
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.live_outlookmail_graph_client import (
    OUTLOOKMAIL_GRAPH_SCOPE,
    LiveOutlookMailGraphClient,
    LoopbackCodeReceiver,
    SetupError,
    _build_verified_ssl_context,
    _exchange_token,
    _urlopen_json,
)


class FakeOAuthSession:
    def __init__(self, token_response: dict | None = None, authorize_error: Exception | None = None) -> None:
        self._token_response = token_response
        self._authorize_error = authorize_error
        self.authorize_calls = 0
        self.refresh_calls = 0
        self.configs: list[dict] = []

    def authorize(self) -> dict:
        self.authorize_calls += 1
        if self._authorize_error is not None:
            raise self._authorize_error
        return dict(self._token_response)

    def refresh_access_token(self, refresh_token: str) -> dict:
        self.refresh_calls += 1
        return {
            "access_token": f"refreshed-for-{refresh_token}",
            "refresh_token": refresh_token,
            "expires_at": "2999-01-01T00:00:00Z",
        }


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, str, dict]] = []

    def __call__(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        access_token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict:
        self.calls.append((method, url, params or {}, access_token or "", headers or {}))
        if url.endswith("/mailFolders/inbox/messages"):
            return {"value": [{"id": "outlook-live-001"}, {"id": "outlook-live-002"}]}
        if url.endswith("/messages/outlook-live-001"):
            return {
                "id": "outlook-live-001",
                "subject": "Hello",
                "bodyPreview": "Preview",
                "body": {"content": "Body text"},
                "receivedDateTime": "2026-06-27T10:00:00Z",
                "from": {"emailAddress": {"name": "Boss", "address": "boss@example.com"}},
                "internetMessageHeaders": [{"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"}],
            }
        raise AssertionError(f"Unexpected transport call: {url}")


class FakeHTTPServer:
    def __init__(self, server_address: tuple[str, int], handler_class) -> None:
        del handler_class
        self.server_address = (server_address[0], 49152)

    def shutdown(self) -> None:
        return None

    def server_close(self) -> None:
        return None

    def serve_forever(self) -> None:
        return None


class LiveOutlookMailGraphClientTests(unittest.TestCase):
    def test_from_local_oauth_uses_existing_token_without_reauthorizing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_oauth_config(credentials_dir)
            token_path = credentials_dir / "outlook_tokens" / "founder-hotmail.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(
                json.dumps(
                    {
                        "access_token": "cached-token",
                        "refresh_token": "cached-refresh",
                        "expires_at": "2999-01-01T00:00:00Z",
                        "scope": OUTLOOKMAIL_GRAPH_SCOPE,
                    }
                )
            )
            oauth_session = FakeOAuthSession(
                {
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            )
            transport = RecordingTransport()

            client = LiveOutlookMailGraphClient.from_local_oauth(
                "founder-hotmail",
                credentials_dir,
                oauth_session_factory=lambda config, account_id, scope: oauth_session,
                transport=transport,
            )
            message_ids = client.list_messages(2)

            self.assertEqual(message_ids, ["outlook-live-001", "outlook-live-002"])
            self.assertEqual(oauth_session.authorize_calls, 0)
            self.assertEqual(oauth_session.refresh_calls, 0)
            self.assertEqual(transport.calls[0][3], "cached-token")

    def test_from_local_oauth_authorizes_and_persists_token_on_first_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_oauth_config(credentials_dir)
            oauth_session = FakeOAuthSession(
                {
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            )
            transport = RecordingTransport()

            client = LiveOutlookMailGraphClient.from_local_oauth(
                "founder-hotmail",
                credentials_dir,
                oauth_session_factory=lambda config, account_id, scope: oauth_session,
                transport=transport,
            )
            message = client.get_message("outlook-live-001")

            token_path = credentials_dir / "outlook_tokens" / "founder-hotmail.json"
            stored_token = json.loads(token_path.read_text())

            self.assertEqual(message["id"], "outlook-live-001")
            self.assertEqual(message["sender"], "Boss <boss@example.com>")
            self.assertEqual(message["list_unsubscribe"], "<https://example.com/unsub>")
            self.assertEqual(oauth_session.authorize_calls, 1)
            self.assertEqual(stored_token["access_token"], "new-token")
            self.assertEqual(stored_token["refresh_token"], "new-refresh")
            self.assertEqual(stored_token["scope"], OUTLOOKMAIL_GRAPH_SCOPE)

    def test_from_local_oauth_raises_clear_error_when_no_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(SetupError, "No Outlook OAuth config found"):
                LiveOutlookMailGraphClient.from_local_oauth("founder-hotmail", Path(temp_dir))

    def test_loopback_code_receiver_uses_ephemeral_port_instead_of_port_80(self) -> None:
        receiver = LoopbackCodeReceiver(
            host="127.0.0.1",
            path="/oauth2callback",
            expected_state="state",
            server_factory=FakeHTTPServer,
        )

        try:
            self.assertTrue(receiver.redirect_uri.startswith("http://127.0.0.1:"))
            self.assertNotIn(":80/", receiver.redirect_uri)
        finally:
            receiver.stop()

    def test_from_local_oauth_wraps_ssl_certificate_failure_with_clear_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_oauth_config(credentials_dir)
            oauth_session = FakeOAuthSession(
                authorize_error=urllib.error.URLError(
                    ssl.SSLCertVerificationError("certificate verify failed: unable to get local issuer certificate")
                )
            )

            with self.assertRaisesRegex(SetupError, "Install Certificates.command"):
                LiveOutlookMailGraphClient.from_local_oauth(
                    "founder-hotmail",
                    credentials_dir,
                    oauth_session_factory=lambda config, account_id, scope: oauth_session,
                )

    def test_exchange_token_uses_verified_ssl_context(self) -> None:
        captured_context = None
        captured_timeout = None

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self) -> bytes:
                return b'{"access_token":"token","expires_in":3600}'

        def fake_urlopen(request, context=None, timeout=None):
            del request
            nonlocal captured_context, captured_timeout
            captured_context = context
            captured_timeout = timeout
            return FakeResponse()

        with patch("src.live_outlookmail_graph_client.urllib.request.urlopen", side_effect=fake_urlopen):
            response = _exchange_token(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                {"client_id": "id", "code": "code", "grant_type": "authorization_code"},
            )

        self.assertEqual(response["access_token"], "token")
        self.assertIsNotNone(captured_context)
        self.assertEqual(captured_context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(captured_context.check_hostname)
        self.assertIsNotNone(captured_timeout)

    def test_urlopen_json_retries_transient_timeout_and_succeeds(self) -> None:
        attempts = 0

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self) -> bytes:
                return b'{"value":[]}'

        def fake_urlopen(request, context=None, timeout=None):
            del request, context, timeout
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise socket.timeout("timed out")
            return FakeResponse()

        request = urllib.request.Request("https://graph.microsoft.com/v1.0/me/messages")
        with patch("src.live_outlookmail_graph_client.urllib.request.urlopen", side_effect=fake_urlopen):
            response = _urlopen_json(request)

        self.assertEqual(response, {"value": []})
        self.assertEqual(attempts, 3)

    def test_build_verified_ssl_context_requires_certificate_validation(self) -> None:
        context = _build_verified_ssl_context()

        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def _write_oauth_config(self, credentials_dir: Path) -> None:
        (credentials_dir / "oauth_client.json").write_text(
            json.dumps(
                {
                    "client_id": "outlook-client-id",
                    "tenant": "consumers",
                    "redirect_uris": ["http://127.0.0.1"],
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
