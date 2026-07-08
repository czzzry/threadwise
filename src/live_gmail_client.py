import base64
import hashlib
from importlib.util import find_spec
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

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
DEFAULT_HTTP_TIMEOUT_SECONDS = 15
DEFAULT_HTTP_MAX_ATTEMPTS = 3
TRANSIENT_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class SetupError(Exception):
    pass


class LiveGmailClient:
    def __init__(self, access_token: str, transport: Callable[..., dict] | None = None) -> None:
        self._access_token = access_token
        self._transport = transport or _default_transport

    @classmethod
    def from_local_oauth(
        cls,
        account_id: str,
        credentials_dir: Path,
        client_secret_path: Path | None = None,
        oauth_session_factory=None,
        transport: Callable[..., dict] | None = None,
        scope: str = GMAIL_READONLY_SCOPE,
    ) -> "LiveGmailClient":
        resolved_client_secret_path = _resolve_client_secret_path(
            credentials_dir=credentials_dir,
            client_secret_path=client_secret_path,
        )
        config = _load_client_config(resolved_client_secret_path)
        token_path = credentials_dir / "gmail_tokens" / f"{account_id}.json"
        token = _load_token(token_path)

        oauth_session_factory = oauth_session_factory or (
            lambda oauth_config, oauth_client_secret_path, oauth_account_id, scope: _build_default_oauth_session(
                oauth_config,
                oauth_client_secret_path,
                oauth_account_id,
                scope,
            )
        )

        if token and _token_is_usable(token) and _token_has_scope(token, scope):
            access_token = token["access_token"]
        else:
            oauth_session = oauth_session_factory(
                config,
                resolved_client_secret_path,
                account_id,
                scope,
            )
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

    def list_messages(self, label_ids: tuple[str, ...], max_results: int) -> list[str]:
        message_ids: list[str] = []
        page_token: str | None = None

        while len(message_ids) < max_results:
            remaining = max_results - len(message_ids)
            params = {
                "labelIds": list(label_ids),
                "maxResults": min(remaining, 500),
            }
            if page_token is not None:
                params["pageToken"] = page_token

            response = self._transport(
                "GET",
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                params=params,
                access_token=self._access_token,
            )
            message_ids.extend(message["id"] for message in response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return message_ids[:max_results]

    def search_message_ids(self, query: str, max_results: int) -> list[str]:
        message_ids: list[str] = []
        page_token: str | None = None

        while len(message_ids) < max_results:
            remaining = max_results - len(message_ids)
            params = {
                "q": query,
                "maxResults": min(remaining, 500),
            }
            if page_token is not None:
                params["pageToken"] = page_token

            response = self._transport(
                "GET",
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                params=params,
                access_token=self._access_token,
            )
            message_ids.extend(message["id"] for message in response.get("messages", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return message_ids[:max_results]

    def get_message(self, message_id: str) -> dict:
        return self._transport(
            "GET",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            params={"format": "full"},
            access_token=self._access_token,
        )

    def get_or_create_label(self, label_name: str) -> str:
        response = self._transport(
            "GET",
            "https://gmail.googleapis.com/gmail/v1/users/me/labels",
            access_token=self._access_token,
        )
        for label in response.get("labels", []):
            if label.get("name") == label_name:
                return label["id"]

        created_label = self._transport(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/labels",
            params={
                "name": label_name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
            access_token=self._access_token,
        )
        return created_label["id"]

    def apply_labels(self, message_id: str, label_ids: list[str]) -> None:
        self._transport(
            "POST",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
            params={"addLabelIds": label_ids},
            access_token=self._access_token,
        )

    def remove_inbox_label(self, message_id: str) -> None:
        self._transport(
            "POST",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
            params={"removeLabelIds": ["INBOX"]},
            access_token=self._access_token,
        )


class LoopbackOAuthSession:
    def __init__(self, config: dict, account_id: str, scope: str) -> None:
        self._config = config["installed"]
        self._account_id = account_id
        self._scope = scope

    def authorize(self) -> dict:
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(24)
        host, path = _resolve_loopback_target(self._config.get("redirect_uris", []))
        auth_code_receiver = LoopbackCodeReceiver(host=host, path=path, expected_state=state)
        redirect_uri = auth_code_receiver.redirect_uri

        authorization_url = (
            f"{self._config['auth_uri']}?"
            + urllib.parse.urlencode(
                {
                    "client_id": self._config["client_id"],
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": self._scope,
                    "access_type": "offline",
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
                "client_secret": self._config.get("client_secret", ""),
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )

    def refresh_access_token(self, refresh_token: str) -> dict:
        return _exchange_token(
            self._config["token_uri"],
            {
                "client_id": self._config["client_id"],
                "client_secret": self._config.get("client_secret", ""),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )


class GoogleInstalledAppOAuthSession:
    def __init__(self, config: dict, client_secret_path: Path, scope: str) -> None:
        self._config = config["installed"]
        self._client_secret_path = client_secret_path
        self._scope = scope

    def authorize(self) -> dict:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(self._client_secret_path), [self._scope])
        credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)
        return _google_credentials_to_token(credentials)

    def refresh_access_token(self, refresh_token: str) -> dict:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=self._config["token_uri"],
            client_id=self._config["client_id"],
            client_secret=self._config.get("client_secret", ""),
            scopes=[self._scope],
        )
        credentials.refresh(Request())
        return _google_credentials_to_token(credentials)


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


def _default_transport(method: str, url: str, params: dict | None = None, access_token: str | None = None) -> dict:
    request_data = None
    request_url = url

    if method.upper() == "GET":
        query_params = []
        for key, value in (params or {}).items():
            if isinstance(value, list):
                query_params.extend((key, item) for item in value)
            else:
                query_params.append((key, value))
        encoded_query = urllib.parse.urlencode(query_params)
        request_url = f"{url}?{encoded_query}" if encoded_query else url
    elif params is not None:
        request_data = json.dumps(params).encode()

    request = urllib.request.Request(request_url, data=request_data, method=method)
    if access_token:
        request.add_header("Authorization", f"Bearer {access_token}")
    request.add_header("Accept", "application/json")
    if request_data is not None:
        request.add_header("Content-Type", "application/json")

    return _urlopen_json(request)


def _exchange_token(token_uri: str, form_data: dict) -> dict:
    encoded_form = urllib.parse.urlencode({key: value for key, value in form_data.items() if value}).encode()
    request = urllib.request.Request(token_uri, data=encoded_form, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")

    return _urlopen_json(request)


def _load_client_config(client_secret_path: Path) -> dict:
    try:
        return json.loads(client_secret_path.read_text())
    except json.JSONDecodeError as exc:
        raise SetupError(f"OAuth client secret file is not valid JSON: {client_secret_path}") from exc


def _resolve_client_secret_path(credentials_dir: Path, client_secret_path: Path | None = None) -> Path:
    if client_secret_path is not None:
        if client_secret_path.exists():
            return client_secret_path
        raise SetupError(
            "OAuth client secret file was not found at "
            f"{client_secret_path}. Pass a valid --client-secret-path or place the file in "
            f"{credentials_dir / 'client_secret.json'}."
        )

    preferred_path = credentials_dir / "client_secret.json"
    if preferred_path.exists():
        return preferred_path

    matching_paths = sorted(credentials_dir.glob("client_secret*.json"))
    if len(matching_paths) == 1:
        return matching_paths[0]
    if not matching_paths:
        raise SetupError(
            "No OAuth client secret found. Put your Google Desktop OAuth JSON at "
            f"{preferred_path} or pass --client-secret-path /path/to/client_secret.json."
        )

    candidate_list = ", ".join(str(path.name) for path in matching_paths)
    raise SetupError(
        "Multiple OAuth client secret files found in "
        f"{credentials_dir}: {candidate_list}. Keep only one file, rename the intended file to "
        f"{preferred_path.name}, or pass --client-secret-path explicitly."
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
        return required_scope == GMAIL_READONLY_SCOPE
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


def _build_default_oauth_session(
    config: dict,
    client_secret_path: Path,
    account_id: str,
    scope: str,
) -> object:
    if _google_oauth_libraries_available():
        return GoogleInstalledAppOAuthSession(config, client_secret_path, scope)
    return LoopbackOAuthSession(config, account_id, scope)


def _google_oauth_libraries_available() -> bool:
    try:
        return find_spec("google_auth_oauthlib.flow") is not None
    except (ImportError, AttributeError, ModuleNotFoundError, ValueError):
        return False


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
        "TLS certificate verification failed while talking to Google. "
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


def _google_credentials_to_token(credentials: object) -> dict:
    expiry = getattr(credentials, "expiry", None)
    expires_at = None
    if expiry is not None:
        expires_at = expiry.astimezone(UTC).isoformat().replace("+00:00", "Z")

    return {
        "access_token": getattr(credentials, "token"),
        "refresh_token": getattr(credentials, "refresh_token", None),
        "expires_at": expires_at,
    }
