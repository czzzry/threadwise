import base64
import hashlib
import json
import secrets
import socket
import ssl
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


OUTLOOKMAIL_GRAPH_SCOPE = "https://graph.microsoft.com/Mail.Read"
DEFAULT_HTTP_TIMEOUT_SECONDS = 15
DEFAULT_HTTP_MAX_ATTEMPTS = 3
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class SetupError(Exception):
    pass


class LiveOutlookMailGraphClient:
    def __init__(self, access_token: str, transport: Callable[..., dict] | None = None) -> None:
        self._access_token = access_token
        self._transport = transport or _default_transport

    @classmethod
    def from_local_oauth(
        cls,
        account_id: str,
        credentials_dir: Path,
        oauth_config_path: Path | None = None,
        oauth_session_factory=None,
        transport: Callable[..., dict] | None = None,
        scope: str = OUTLOOKMAIL_GRAPH_SCOPE,
    ) -> "LiveOutlookMailGraphClient":
        config = _load_oauth_config(credentials_dir, oauth_config_path)
        token_path = credentials_dir / "outlook_tokens" / f"{account_id}.json"
        token = _load_token(token_path)

        oauth_session_factory = oauth_session_factory or (
            lambda oauth_config, oauth_account_id, oauth_scope: MicrosoftLoopbackOAuthSession(
                oauth_config,
                oauth_account_id,
                oauth_scope,
            )
        )

        if token and _token_is_usable(token) and _token_has_scope(token, scope):
            access_token = token["access_token"]
        else:
            oauth_session = oauth_session_factory(config, account_id, scope)
            try:
                if token and token.get("refresh_token") and _token_has_scope(token, scope):
                    refreshed_token = oauth_session.refresh_access_token(token["refresh_token"])
                    token = _normalize_token(refreshed_token, existing_refresh_token=token["refresh_token"])
                else:
                    authorized_token = oauth_session.authorize()
                    token = _normalize_token(authorized_token)
            except Exception as exc:
                if _is_ssl_certificate_error(exc):
                    raise SetupError(_certificate_verification_error_message()) from exc
                raise
            token["scope"] = scope
            _persist_token(token_path, token)
            access_token = token["access_token"]

        return cls(access_token=access_token, transport=transport)

    def list_messages(self, max_results: int) -> list[str]:
        message_ids: list[str] = []
        next_url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
        params: dict | None = {
            "$select": "id",
            "$orderby": "receivedDateTime DESC",
            "$top": min(max_results, 100),
        }

        while next_url and len(message_ids) < max_results:
            response = self._transport(
                "GET",
                next_url,
                params=params,
                access_token=self._access_token,
            )
            message_ids.extend(message["id"] for message in response.get("value", []))
            next_url = response.get("@odata.nextLink")
            params = None

        return message_ids[:max_results]

    def get_message(self, message_id: str) -> dict:
        response = self._transport(
            "GET",
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            params={
                "$select": "subject,from,receivedDateTime,bodyPreview,body,internetMessageHeaders",
            },
            access_token=self._access_token,
            headers={"Prefer": 'outlook.body-content-type="text"'},
        )
        headers = {
            header.get("name", ""): header.get("value", "")
            for header in response.get("internetMessageHeaders", [])
        }
        sender = _sender_from_graph_message(response)
        received_at = response.get("receivedDateTime") or datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        body = (response.get("body") or {}).get("content") or response.get("bodyPreview", "") or response.get("subject", "")
        snippet = response.get("bodyPreview", "") or body[:160]
        return {
            "id": message_id,
            "mailbox": "inbox",
            "sender": sender,
            "subject": response.get("subject", ""),
            "date": received_at,
            "snippet": snippet,
            "body": body,
            "list_unsubscribe": headers.get("List-Unsubscribe"),
            "precedence": headers.get("Precedence", ""),
        }


class MicrosoftLoopbackOAuthSession:
    def __init__(self, config: dict, account_id: str, scope: str) -> None:
        self._config = config
        self._account_id = account_id
        self._scope = scope

    def authorize(self) -> dict:
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(24)
        host, path = _resolve_loopback_target(self._config.get("redirect_uris", []))
        auth_code_receiver = LoopbackCodeReceiver(host=host, path=path, expected_state=state)
        redirect_uri = auth_code_receiver.redirect_uri

        scope = f"offline_access openid {self._scope}"
        authorization_url = (
            f"{self._config['auth_uri']}?"
            + urllib.parse.urlencode(
                {
                    "client_id": self._config["client_id"],
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "response_mode": "query",
                    "scope": scope,
                    "prompt": "consent",
                    "state": state,
                    "login_hint": self._account_id,
                    "code_challenge": code_challenge,
                    "code_challenge_method": "S256",
                }
            )
        )
        auth_code_receiver.start()
        try:
            webbrowser.open(authorization_url)
            code = auth_code_receiver.wait_for_code()
        finally:
            auth_code_receiver.stop()

        return _exchange_token(
            self._config["token_uri"],
            {
                "client_id": self._config["client_id"],
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "scope": scope,
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        return _exchange_token(
            self._config["token_uri"],
            {
                "client_id": self._config["client_id"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": f"offline_access openid {self._scope}",
            },
        )


class LoopbackCodeReceiver:
    def __init__(
        self,
        host: str,
        path: str,
        expected_state: str,
        port: int = 0,
        server_factory=None,
    ) -> None:
        self._expected_state = expected_state
        self._code: str | None = None
        self._error: str | None = None
        self._event = threading.Event()
        self._path = path or "/"

        receiver = self

        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                request_url = urllib.parse.urlparse(self.path)
                if request_url.path != receiver._path:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not found.")
                    return

                query = urllib.parse.parse_qs(request_url.query)
                state = query.get("state", [""])[0]
                if state != receiver._expected_state:
                    receiver._error = "OAuth state mismatch"
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"OAuth state mismatch.")
                    receiver._event.set()
                    return

                if "error" in query:
                    receiver._error = query["error"][0]
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"OAuth authorization failed.")
                    receiver._event.set()
                    return

                receiver._code = query.get("code", [""])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorization received. You can close this window.")
                receiver._event.set()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                del format, args

        server_factory = server_factory or HTTPServer
        self._server = server_factory((host, port), OAuthHandler)
        resolved_port = self._server.server_address[1]
        self.redirect_uri = f"http://{host}:{resolved_port}{self._path}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def wait_for_code(self, timeout_seconds: int = 300) -> str:
        if not self._event.wait(timeout_seconds):
            raise TimeoutError("Timed out waiting for OAuth authorization response")
        if self._error:
            raise RuntimeError(self._error)
        if not self._code:
            raise RuntimeError("OAuth authorization completed without a code")
        return self._code

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=1)


def _default_transport(
    method: str,
    url: str,
    params: dict | None = None,
    access_token: str | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    request_data = None
    request_url = url

    if method.upper() == "GET":
        encoded_query = urllib.parse.urlencode(params or {})
        request_url = f"{url}?{encoded_query}" if encoded_query else url
    elif params is not None:
        request_data = json.dumps(params).encode()

    request = urllib.request.Request(request_url, data=request_data, method=method)
    if access_token:
        request.add_header("Authorization", f"Bearer {access_token}")
    request.add_header("Accept", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if request_data is not None:
        request.add_header("Content-Type", "application/json")

    return _urlopen_json(request)


def _exchange_token(token_uri: str, form_data: dict) -> dict:
    encoded_form = urllib.parse.urlencode({key: value for key, value in form_data.items() if value}).encode()
    request = urllib.request.Request(token_uri, data=encoded_form, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    return _urlopen_json(request)


def _load_oauth_config(credentials_dir: Path, oauth_config_path: Path | None = None) -> dict:
    resolved_path = _resolve_oauth_config_path(credentials_dir, oauth_config_path)
    try:
        raw = json.loads(resolved_path.read_text())
    except json.JSONDecodeError as exc:
        raise SetupError(f"Outlook OAuth config file is not valid JSON: {resolved_path}") from exc

    tenant = raw.get("tenant", "consumers")
    return {
        "client_id": raw["client_id"],
        "tenant": tenant,
        "auth_uri": raw.get("auth_uri", f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"),
        "token_uri": raw.get("token_uri", f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"),
        "redirect_uris": raw.get("redirect_uris", ["http://127.0.0.1"]),
    }


def _resolve_oauth_config_path(credentials_dir: Path, oauth_config_path: Path | None = None) -> Path:
    if oauth_config_path is not None:
        if oauth_config_path.exists():
            return oauth_config_path
        raise SetupError(
            "Outlook OAuth config file was not found at "
            f"{oauth_config_path}. Pass a valid --oauth-config-path or place the file in "
            f"{credentials_dir / 'oauth_client.json'}."
        )

    default_path = credentials_dir / "oauth_client.json"
    if default_path.exists():
        return default_path

    raise SetupError(
        "No Outlook OAuth config found. Put a JSON file with client_id at "
        f"{default_path}."
    )


def _load_token(token_path: Path) -> dict | None:
    if not token_path.exists():
        return None
    return json.loads(token_path.read_text())


def _persist_token(token_path: Path, token: dict) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(token, indent=2))


def _token_is_usable(token: dict) -> bool:
    expires_at = token.get("expires_at")
    if not expires_at:
        return False
    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    return expiry > datetime.now(tz=UTC) + timedelta(minutes=1)


def _token_has_scope(token: dict, required_scope: str) -> bool:
    stored_scope = token.get("scope")
    if not stored_scope:
        return False
    return required_scope in stored_scope.split()


def _normalize_token(token_response: dict, existing_refresh_token: str | None = None) -> dict:
    expires_in = int(token_response.get("expires_in", 3600))
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=expires_in)
    return {
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token") or existing_refresh_token,
        "expires_at": token_response.get("expires_at")
        or expires_at.isoformat().replace("+00:00", "Z"),
    }


def _generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def _generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _resolve_loopback_target(redirect_uris: list[str]) -> tuple[str, str]:
    for redirect_uri in redirect_uris:
        parsed = urllib.parse.urlparse(redirect_uri)
        if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
            return "127.0.0.1", parsed.path or "/"
    return "127.0.0.1", "/"


def _urlopen_json(
    request: urllib.request.Request,
    *,
    timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_HTTP_MAX_ATTEMPTS,
) -> dict:
    attempt = 0
    while True:
        attempt += 1
        try:
            with urllib.request.urlopen(
                request,
                context=_build_verified_ssl_context(),
                timeout=timeout_seconds,
            ) as response:
                return json.loads(response.read())
        except Exception as exc:
            if _is_ssl_certificate_error(exc):
                raise SetupError(_certificate_verification_error_message()) from exc
            if attempt >= max_attempts or not _is_transient_network_error(exc):
                raise


def _build_verified_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _is_ssl_certificate_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    if isinstance(exc, urllib.error.URLError) and exc.reason is not None:
        if _is_ssl_certificate_error(exc.reason):
            return True
    message = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in message or "certificate verify failed" in message.lower():
        return True
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc and _is_ssl_certificate_error(cause):
        return True
    context = getattr(exc, "__context__", None)
    if context is not None and context is not exc and _is_ssl_certificate_error(context):
        return True
    return False


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in TRANSIENT_HTTP_STATUS_CODES
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError)):
        return True
    if isinstance(exc, urllib.error.URLError) and exc.reason is not None:
        return _is_transient_network_error(exc.reason)
    if isinstance(exc, ssl.SSLError) and "timed out" in str(exc).lower():
        return True
    message = str(exc).lower()
    return "timed out" in message or "temporarily unavailable" in message


def _certificate_verification_error_message() -> str:
    install_command = _macos_install_certificates_command()
    command_hint = f' Run: {install_command} and then retry.' if install_command else ""
    return (
        "TLS certificate verification failed while talking to Microsoft. "
        "SSL verification is still enabled and was not bypassed. "
        "This commonly happens with python.org Python on macOS before the bundled root certificates are installed."
        f"{command_hint}"
    )


def _macos_install_certificates_command() -> str | None:
    install_script_path = Path(
        f"/Applications/Python {sys.version_info.major}.{sys.version_info.minor}/Install Certificates.command"
    )
    if install_script_path.exists():
        return f'open "{install_script_path}"'
    return None


def _sender_from_graph_message(message: dict) -> str:
    email_address = ((message.get("from") or {}).get("emailAddress") or {})
    name = email_address.get("name", "")
    address = email_address.get("address", "")
    if name and address:
        return f"{name} <{address}>"
    return address or name
