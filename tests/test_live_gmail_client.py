import json
import socket
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.live_gmail_client import (
    GMAIL_MODIFY_SCOPE,
    GMAIL_READONLY_SCOPE,
    LiveGmailClient,
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
        self.calls: list[tuple[str, str, dict, str]] = []

    def __call__(self, method: str, url: str, params: dict | None = None, access_token: str | None = None) -> dict:
        self.calls.append((method, url, params or {}, access_token or ""))
        if url.endswith("/messages"):
            return {"messages": [{"id": "gmail-live-001"}, {"id": "gmail-live-002"}]}
        if url.endswith("/messages/gmail-live-001"):
            return {"id": "gmail-live-001", "snippet": "Hello"}
        raise AssertionError(f"Unexpected transport call: {url}")


class LabelTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, str]] = []

    def __call__(self, method: str, url: str, params: dict | None = None, access_token: str | None = None) -> dict:
        payload = params or {}
        self.calls.append((method, url, payload, access_token or ""))
        if method == "GET" and url.endswith("/labels"):
            return {"labels": [{"id": "Label_existing", "name": "EA/reply-needed"}]}
        if method == "POST" and url.endswith("/labels"):
            return {"id": "Label_new", "name": payload["name"]}
        if method == "POST" and url.endswith("/messages/gmail-live-001/modify"):
            return {
                "id": "gmail-live-001",
                "labelIds": payload.get("addLabelIds", []),
                "removedLabelIds": payload.get("removeLabelIds", []),
            }
        raise AssertionError(f"Unexpected transport call: {method} {url}")


class PaginatedListTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, str]] = []

    def __call__(self, method: str, url: str, params: dict | None = None, access_token: str | None = None) -> dict:
        payload = params or {}
        self.calls.append((method, url, payload, access_token or ""))
        page_token = payload.get("pageToken")
        if page_token is None:
            return {
                "messages": [{"id": f"page1-{index}"} for index in range(500)],
                "nextPageToken": "page-2",
            }
        if page_token == "page-2":
            return {
                "messages": [{"id": f"page2-{index}"} for index in range(500)],
                "nextPageToken": "page-3",
            }
        if page_token == "page-3":
            return {
                "messages": [{"id": f"page3-{index}"} for index in range(200)],
            }
        raise AssertionError(f"Unexpected page token: {page_token}")


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


class LiveGmailClientTests(unittest.TestCase):
    def test_from_local_oauth_uses_existing_token_without_reauthorizing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(credentials_dir)
            token_path = credentials_dir / "gmail_tokens" / "founder-test.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(
                json.dumps(
                    {
                        "access_token": "cached-token",
                        "refresh_token": "cached-refresh",
                        "expires_at": "2999-01-01T00:00:00Z",
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

            client = LiveGmailClient.from_local_oauth(
                "founder-test",
                credentials_dir,
                oauth_session_factory=lambda config, client_secret_path, account_id, scope: oauth_session,
                transport=transport,
            )
            message_ids = client.list_messages(("INBOX",), 2)

            self.assertEqual(message_ids, ["gmail-live-001", "gmail-live-002"])
            self.assertEqual(oauth_session.authorize_calls, 0)
            self.assertEqual(oauth_session.refresh_calls, 0)
            self.assertEqual(transport.calls[0][3], "cached-token")

    def test_from_local_oauth_authorizes_and_persists_token_on_first_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(credentials_dir)
            oauth_session = FakeOAuthSession(
                {
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            )
            transport = RecordingTransport()

            client = LiveGmailClient.from_local_oauth(
                "founder-test",
                credentials_dir,
                oauth_session_factory=lambda config, client_secret_path, account_id, scope: oauth_session,
                transport=transport,
            )
            message = client.get_message("gmail-live-001")

            token_path = credentials_dir / "gmail_tokens" / "founder-test.json"
            stored_token = json.loads(token_path.read_text())

            self.assertEqual(message["id"], "gmail-live-001")
            self.assertEqual(oauth_session.authorize_calls, 1)
            self.assertEqual(stored_token["access_token"], "new-token")
            self.assertEqual(stored_token["refresh_token"], "new-refresh")

    def test_from_local_oauth_surfaces_reconnect_message_when_google_refresh_returns_400(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(credentials_dir)
            token_path = credentials_dir / "gmail_tokens" / "founder-test.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(
                json.dumps(
                    {
                        "access_token": "expired-token",
                        "refresh_token": "stale-refresh",
                        "expires_at": "2000-01-01T00:00:00Z",
                        "scope": GMAIL_MODIFY_SCOPE,
                    }
                )
            )

            class FailingRefreshSession:
                def refresh_access_token(self, refresh_token: str) -> dict:
                    raise urllib.error.HTTPError(
                        "https://oauth2.googleapis.com/token",
                        400,
                        "Bad Request",
                        hdrs=None,
                        fp=None,
                    )

            with self.assertRaises(SetupError) as exc_info:
                LiveGmailClient.from_local_oauth(
                    "founder-test",
                    credentials_dir,
                    oauth_session_factory=lambda config, client_secret_path, account_id, scope: FailingRefreshSession(),
                    scope=GMAIL_MODIFY_SCOPE,
                )

            self.assertIn("Reconnect Gmail", str(exc_info.exception))
            self.assertIn("founder-test", str(exc_info.exception))

    def test_from_local_oauth_reauthorizes_when_cached_token_lacks_required_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(credentials_dir)
            token_path = credentials_dir / "gmail_tokens" / "founder-test.json"
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(
                json.dumps(
                    {
                        "access_token": "cached-readonly-token",
                        "refresh_token": "cached-refresh",
                        "expires_at": "2999-01-01T00:00:00Z",
                        "scope": GMAIL_READONLY_SCOPE,
                    }
                )
            )
            oauth_session = FakeOAuthSession(
                {
                    "access_token": "new-modify-token",
                    "refresh_token": "cached-refresh",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            )
            transport = RecordingTransport()

            client = LiveGmailClient.from_local_oauth(
                "founder-test",
                credentials_dir,
                oauth_session_factory=lambda config, client_secret_path, account_id, scope: oauth_session,
                transport=transport,
                scope=GMAIL_MODIFY_SCOPE,
            )
            client.list_messages(("INBOX",), 1)

            stored_token = json.loads(token_path.read_text())

            self.assertEqual(oauth_session.authorize_calls, 1)
            self.assertEqual(stored_token["access_token"], "new-modify-token")
            self.assertEqual(stored_token["scope"], GMAIL_MODIFY_SCOPE)
            self.assertEqual(transport.calls[0][3], "new-modify-token")

    def test_from_local_oauth_prefers_exact_client_secret_json_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(credentials_dir, filename="client_secret.json", client_id="preferred-client")
            self._write_client_secret(
                credentials_dir,
                filename="client_secret_downloaded.json",
                client_id="fallback-client",
            )
            oauth_session = FakeOAuthSession(
                {
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            )

            LiveGmailClient.from_local_oauth(
                "founder-test",
                credentials_dir,
                oauth_session_factory=lambda config, client_secret_path, account_id, scope: self._recording_oauth_factory(
                    oauth_session, config
                ),
            )

            self.assertEqual(oauth_session.configs[0]["installed"]["client_id"], "preferred-client")

    def test_from_local_oauth_uses_single_google_style_client_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(
                credentials_dir,
                filename="client_secret_abc123.apps.googleusercontent.com.json",
                client_id="downloaded-client",
            )
            oauth_session = FakeOAuthSession(
                {
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            )

            LiveGmailClient.from_local_oauth(
                "founder-test",
                credentials_dir,
                oauth_session_factory=lambda config, client_secret_path, account_id, scope: self._recording_oauth_factory(
                    oauth_session, config
                ),
            )

            self.assertEqual(oauth_session.configs[0]["installed"]["client_id"], "downloaded-client")

    def test_from_local_oauth_raises_clear_error_when_no_client_secret_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)

            with self.assertRaisesRegex(SetupError, "No OAuth client secret found"):
                LiveGmailClient.from_local_oauth("founder-test", credentials_dir)

    def test_from_local_oauth_raises_clear_error_when_multiple_google_style_client_secrets_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials_dir = Path(temp_dir)
            self._write_client_secret(credentials_dir, filename="client_secret_one.json", client_id="client-one")
            self._write_client_secret(credentials_dir, filename="client_secret_two.json", client_id="client-two")

            with self.assertRaisesRegex(SetupError, "Multiple OAuth client secret files found"):
                LiveGmailClient.from_local_oauth("founder-test", credentials_dir)

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
            self._write_client_secret(credentials_dir)
            oauth_session = FakeOAuthSession(
                authorize_error=urllib.error.URLError(
                    ssl.SSLCertVerificationError("certificate verify failed: unable to get local issuer certificate")
                )
            )

            with self.assertRaisesRegex(SetupError, "TLS certificate verification failed while talking to Google"):
                LiveGmailClient.from_local_oauth(
                    "founder-test",
                    credentials_dir,
                    oauth_session_factory=lambda config, client_secret_path, account_id, scope: oauth_session,
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

        with patch("src.live_gmail_client.urllib.request.urlopen", side_effect=fake_urlopen):
            response = _exchange_token(
                "https://oauth2.googleapis.com/token",
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
                return b'{"messages":[]}'

        def fake_urlopen(request, context=None, timeout=None):
            del request, context, timeout
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise socket.timeout("timed out")
            return FakeResponse()

        request = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/messages")
        with patch("src.live_gmail_client.urllib.request.urlopen", side_effect=fake_urlopen):
            response = _urlopen_json(request)

        self.assertEqual(response, {"messages": []})
        self.assertEqual(attempts, 3)

    def test_urlopen_json_retries_transient_http_503_and_succeeds(self) -> None:
        attempts = 0

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def read(self) -> bytes:
                return b'{"id":"gmail-live-001"}'

        def fake_urlopen(request, context=None, timeout=None):
            del context, timeout
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise urllib.error.HTTPError(request.full_url, 503, "service unavailable", hdrs=None, fp=None)
            return FakeResponse()

        request = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/messages/gmail-live-001")
        with patch("src.live_gmail_client.urllib.request.urlopen", side_effect=fake_urlopen):
            response = _urlopen_json(request)

        self.assertEqual(response, {"id": "gmail-live-001"})
        self.assertEqual(attempts, 2)

    def test_urlopen_json_does_not_retry_non_transient_http_error(self) -> None:
        attempts = 0

        def fake_urlopen(request, context=None, timeout=None):
            del context, timeout
            nonlocal attempts
            attempts += 1
            raise urllib.error.HTTPError(request.full_url, 404, "not found", hdrs=None, fp=None)

        request = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/messages/missing")
        with patch("src.live_gmail_client.urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(urllib.error.HTTPError):
                _urlopen_json(request)

        self.assertEqual(attempts, 1)

    def test_build_verified_ssl_context_requires_certificate_validation(self) -> None:
        context = _build_verified_ssl_context()

        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_google_oauth_library_check_falls_back_cleanly_when_find_spec_errors(self) -> None:
        with patch("src.live_gmail_client.find_spec", side_effect=AttributeError("no util")):
            from src.live_gmail_client import _google_oauth_libraries_available

            self.assertFalse(_google_oauth_libraries_available())

    def test_live_client_creates_missing_ea_label_and_applies_it_without_removing_other_labels(self) -> None:
        transport = LabelTransport()
        client = LiveGmailClient(access_token="modify-token", transport=transport)

        existing_label_id = client.get_or_create_label("EA/reply-needed")
        new_label_id = client.get_or_create_label("EA/job-related")
        client.apply_labels("gmail-live-001", [existing_label_id, new_label_id])

        self.assertEqual(existing_label_id, "Label_existing")
        self.assertEqual(new_label_id, "Label_new")
        self.assertEqual(
            transport.calls,
            [
                ("GET", "https://gmail.googleapis.com/gmail/v1/users/me/labels", {}, "modify-token"),
                ("GET", "https://gmail.googleapis.com/gmail/v1/users/me/labels", {}, "modify-token"),
                (
                    "POST",
                    "https://gmail.googleapis.com/gmail/v1/users/me/labels",
                    {"name": "EA/job-related", "labelListVisibility": "labelShow", "messageListVisibility": "show"},
                    "modify-token",
                ),
                (
                    "POST",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/gmail-live-001/modify",
                    {"addLabelIds": ["Label_existing", "Label_new"]},
                    "modify-token",
                ),
            ],
        )

    def test_live_client_can_replace_existing_threadwise_labels_without_touching_non_threadwise_labels(self) -> None:
        class ReplaceTransport(LabelTransport):
            def __call__(self, method: str, url: str, params: dict | None = None, access_token: str | None = None) -> dict:
                payload = params or {}
                self.calls.append((method, url, payload, access_token or ""))
                if method == "GET" and url.endswith("/labels"):
                    return {
                        "labels": [
                            {"id": "Label_news", "name": "EA/newsletter"},
                            {"id": "Label_travel", "name": "EA/travel"},
                            {"id": "Label_keep", "name": "Personal/Keep"},
                            {"id": "Label_account", "name": "EA/account-security"},
                        ]
                    }
                if method == "GET" and url.endswith("/messages/gmail-live-001"):
                    return {"id": "gmail-live-001", "labelIds": ["Label_news", "Label_travel", "Label_keep"]}
                if method == "POST" and url.endswith("/messages/gmail-live-001/modify"):
                    return {"id": "gmail-live-001"}
                raise AssertionError(f"Unexpected transport call: {method} {url}")

        transport = ReplaceTransport()
        client = LiveGmailClient(access_token="modify-token", transport=transport)

        client.replace_threadwise_labels("gmail-live-001", ["Label_account"])

        self.assertEqual(
            transport.calls,
            [
                ("GET", "https://gmail.googleapis.com/gmail/v1/users/me/labels", {}, "modify-token"),
                (
                    "GET",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/gmail-live-001",
                    {"format": "full"},
                    "modify-token",
                ),
                (
                    "POST",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/gmail-live-001/modify",
                    {"addLabelIds": ["Label_account"], "removeLabelIds": ["Label_news", "Label_travel"]},
                    "modify-token",
                ),
            ],
        )

    def test_live_client_removes_inbox_only_without_deleting_message(self) -> None:
        transport = LabelTransport()
        client = LiveGmailClient(access_token="modify-token", transport=transport)

        client.remove_inbox_label("gmail-live-001")

        self.assertEqual(
            transport.calls,
            [
                (
                    "POST",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/gmail-live-001/modify",
                    {"removeLabelIds": ["INBOX"]},
                    "modify-token",
                ),
            ],
        )

    def test_live_client_paginates_message_listing_beyond_first_500_results(self) -> None:
        transport = PaginatedListTransport()
        client = LiveGmailClient(access_token="readonly-token", transport=transport)

        message_ids = client.list_messages(("INBOX",), 1200)

        self.assertEqual(len(message_ids), 1200)
        self.assertEqual(message_ids[0], "page1-0")
        self.assertEqual(message_ids[499], "page1-499")
        self.assertEqual(message_ids[500], "page2-0")
        self.assertEqual(message_ids[999], "page2-499")
        self.assertEqual(message_ids[1000], "page3-0")
        self.assertEqual(message_ids[1199], "page3-199")
        self.assertEqual(
            transport.calls,
            [
                (
                    "GET",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    {"labelIds": ["INBOX"], "maxResults": 500},
                    "readonly-token",
                ),
                (
                    "GET",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    {"labelIds": ["INBOX"], "maxResults": 500, "pageToken": "page-2"},
                    "readonly-token",
                ),
                (
                    "GET",
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    {"labelIds": ["INBOX"], "maxResults": 200, "pageToken": "page-3"},
                    "readonly-token",
                ),
            ],
        )

    def _write_client_secret(
        self,
        credentials_dir: Path,
        filename: str = "client_secret.json",
        client_id: str = "client-id",
    ) -> None:
        (credentials_dir / filename).write_text(
            json.dumps(
                {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": "client-secret",
                        "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://127.0.0.1:8765"],
                    }
                }
            )
        )

    def _recording_oauth_factory(self, oauth_session: FakeOAuthSession, config: dict) -> FakeOAuthSession:
        oauth_session.configs.append(config)
        return oauth_session


if __name__ == "__main__":
    unittest.main()
