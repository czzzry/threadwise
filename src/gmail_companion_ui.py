import argparse
import json
import threading
import time
from datetime import UTC, datetime
from http.client import HTTPException
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from src.attention_feedback import record_attention_feedback
from src.gmail_automation import run_daily_gmail_automation
from src.gmail_cli_support import default_gmail_client_factory
from src.gmail_run_control import load_gmail_dashboard_run_status, trigger_dashboard_gmail_check
from src.founder_feedback import record_founder_feedback
from src.attention_rules import (
    approve_attention_rule_proposal,
    build_attention_rule_proposal,
    reject_attention_rule_proposal,
)
from src.gmail_writer import MockGmailLabelWriter
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.live_gmail_client import GMAIL_MODIFY_SCOPE
from src.local_artifacts import write_json_artifact
from src.product_analytics import (
    ANALYTICS_WORKFLOW_VERSION,
    AnonymousDistinctIdStore,
    ProductAnalytics,
    bucket_count,
)
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore
from src.unsubscribe_execution import UnsubscribeExecutor

from src.gmail_companion_rendering import (
    escape_html,
    render_dashboard_attention_cards,
    render_dashboard_candidate_cards,
    render_dashboard_changed_cards,
    render_dashboard_email_cards,
    render_dashboard_section,
    render_dashboard_unsubscribe_cards,
    render_unsubscribe_section,
    server_origin,
    unsubscribe_section_key,
)
from src.gmail_companion_state import (
    build_companion_runtime_payload,
    build_daily_attention_summary,
    build_daily_summary,
    build_selected_email_state,
    build_unsubscribe_detail,
    find_matching_item,
    find_unsubscribe_candidate,
    first_query_value,
    load_latest_batch,
    load_latest_report,
    selected_context_from_query,
    selected_email_contract,
    selected_email_understanding_state,
)
from src.teaching_loop import (
    apply_rule_amendment_decision,
    apply_sidebar_teaching,
    build_sidebar_teach_preview,
    exclude_sidebar_teaching_match,
    load_items_for_gmail_write_through,
)


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")
THREADWISE_APP_ICON_PATH = Path("docs/assets/brand/threadwise-app-icon.png")
HEALTH_STATUS_SCHEMA_VERSION = 1
HEALTH_STATUS_PATH = "/api/health"
HEALTH_STATUS_SERVICE_ID = "threadwise-gmail-companion"
HEALTH_STATUS_SERVICE_NAME = "Threadwise Gmail Companion"
HARNESS_STATE_CACHE_SECONDS = 120.0
HEALTH_STATUS_CACHE_SECONDS = 5.0
COMPANION_DATA_CACHE_SECONDS = 120.0
INBOX_BACKFILL_CONFIRM_THRESHOLD = 200
INBOX_BACKFILL_ESTIMATE_CAP = 250
THREADWISE_APP_VERSION = "0.1.0"


def infer_gmail_account_id(storage_dir: Path) -> str:
    latest_report = load_latest_report(storage_dir)
    if latest_report and latest_report.get("account_id"):
        return latest_report["account_id"]
    latest_batch = load_latest_batch(storage_dir)
    if latest_batch and latest_batch.get("account_id"):
        return latest_batch["account_id"]
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve the Gmail companion sidebar prototype backed by stored Gmail artifacts."
    )
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8021)
    parser.add_argument(
        "--disable-gmail-write-through",
        action="store_true",
        help="Keep all teaching/apply behavior local-only and do not write label changes back to Gmail.",
    )
    parser.add_argument(
        "--disable-gmail-check",
        action="store_true",
        help="Disable Gmail check execution for synthetic-only server configurations.",
    )
    return parser


def main(argv: list[str] | None = None, stdout=None, server_factory=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    server_factory = server_factory or create_server
    server = server_factory(
        args.host,
        args.port,
        args.storage_dir,
        gmail_write_through_enabled=not args.disable_gmail_write_through,
        gmail_check_enabled=not args.disable_gmail_check,
    )
    try:
        output.write(f"Serving Gmail companion sidebar at http://{args.host}:{server.server_port}\n")
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        output.write("Stopped Gmail companion sidebar.\n")
        return 0
    finally:
        server.server_close()


def create_server(
    host: str,
    port: int,
    storage_dir: Path,
    *,
    gmail_write_through_enabled: bool = True,
    gmail_check_enabled: bool = True,
) -> ThreadingHTTPServer:
    app = GmailCompanionApp(
        storage_dir=storage_dir,
        gmail_write_through_enabled=gmail_write_through_enabled,
        gmail_check_enabled=gmail_check_enabled,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            app.handle_request(self)

        def do_POST(self) -> None:
            app.handle_request(self)

        def do_OPTIONS(self) -> None:
            app.handle_request(self)

        def log_message(self, format: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


class GmailCompanionApp:
    def __init__(
        self,
        storage_dir: Path,
        *,
        credentials_dir: Path = DEFAULT_CREDENTIALS_DIR,
        client_secret_path: Path | None = None,
        gmail_client_factory=None,
        gmail_write_through_enabled: bool = True,
        gmail_check_enabled: bool = True,
        gmail_run_runner=None,
        attention_model_client: object | None = None,
        analytics: ProductAnalytics | None = None,
    ) -> None:
        self._storage_dir = storage_dir
        self._credentials_dir = credentials_dir
        self._client_secret_path = client_secret_path
        self._gmail_client_factory = gmail_client_factory or default_gmail_client_factory
        self._gmail_write_through_enabled = gmail_write_through_enabled
        self._gmail_check_enabled = gmail_check_enabled
        self._gmail_run_runner = gmail_run_runner
        self._attention_model_client = attention_model_client
        self._analytics = analytics or ProductAnalytics.from_environment()
        self._analytics_distinct_ids = AnonymousDistinctIdStore(storage_dir)
        self._unsubscribe_store = UnsubscribeInventoryStore(storage_dir)
        self._harness_state_cache: dict[str, tuple[float, dict]] = {}
        self._harness_state_lock = threading.Lock()
        self._health_storage_cache: tuple[float, dict] | None = None
        self._health_storage_lock = threading.Lock()
        self._runtime_payload_cache: tuple[float, dict] | None = None
        self._daily_summary_cache: tuple[float, dict] | None = None
        self._unsubscribe_candidates_cache: tuple[float, list[dict]] | None = None
        self._companion_data_lock = threading.Lock()
        self._async_follow_up_state: dict | None = None
        self._async_follow_up_lock = threading.Lock()

    def handle_request(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if handler.command == "OPTIONS":
            self._write_cors_preflight(handler)
            return

        if handler.command == "GET" and parsed.path == "/":
            encoded = self.render_panel().encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/simulator":
            encoded = self.render_simulator().encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/install":
            encoded = self.render_install_page(handler.headers.get("Host", "")).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/unsubscribe-review":
            encoded = self.render_unsubscribe_review_page(parse_qs(parsed.query)).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/daily-dashboard":
            encoded = self.render_daily_dashboard_page().encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/assets/brand/threadwise-app-icon.png":
            if not THREADWISE_APP_ICON_PATH.exists():
                self._write_json(handler, HTTPStatus.NOT_FOUND, {"error": "Brand icon not found"})
                return
            encoded = THREADWISE_APP_ICON_PATH.read_bytes()
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "image/png")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/api/selected-email-contract":
            encoded = json.dumps(selected_email_contract()).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == HEALTH_STATUS_PATH:
            encoded = json.dumps(self.health_status(handler)).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/api/sidebar-state":
            selected_context = selected_context_from_query(parse_qs(parsed.query))
            encoded = json.dumps(self.sidebar_state(selected_context)).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "GET" and parsed.path == "/api/harness-state":
            selected_context = selected_context_from_query(parse_qs(parsed.query))
            encoded = json.dumps(self.harness_state(selected_context)).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(encoded)))
            self._write_cors_headers(handler)
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        if handler.command == "POST" and parsed.path == "/api/teach-preview":
            try:
                payload = self._read_json_body(handler)
                response = self.teach_preview(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/teach-apply":
            try:
                payload = self._read_json_body(handler)
                response = self.teach_apply(
                    payload,
                    analytics_distinct_id=self._analytics_distinct_id_from_request(handler),
                )
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/analytics/capture":
            try:
                payload = self._read_json_body(handler)
                captured = self._analytics.capture(
                    distinct_id=self._analytics_distinct_id_from_request(handler),
                    event=payload["event"],
                    properties=payload["properties"],
                )
                return self._write_json(handler, HTTPStatus.ACCEPTED, {"captured": captured})
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/teach-exclude":
            try:
                payload = self._read_json_body(handler)
                response = self.teach_exclude(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/teach-amendment":
            try:
                payload = self._read_json_body(handler)
                response = self.teach_amendment(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/unsubscribe-select-current":
            try:
                payload = self._read_json_body(handler)
                response = self.unsubscribe_select_current(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/attention-feedback":
            try:
                payload = self._read_request_payload(handler)
                response = self.attention_feedback(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException, json.JSONDecodeError) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/founder-feedback":
            try:
                payload = self._read_request_payload(handler)
                response = self.founder_feedback(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException, json.JSONDecodeError) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/gmail-check-run":
            try:
                payload = self._read_request_payload(handler)
                response = self.trigger_gmail_check(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException, json.JSONDecodeError) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:
                return self._write_json(handler, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/attention-rule-proposal/preview":
            try:
                payload = self._read_request_payload(handler)
                response = self.preview_attention_rule_proposal(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException, json.JSONDecodeError) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/attention-rule-proposal/review":
            try:
                payload = self._read_request_payload(handler)
                response = self.review_attention_rule_proposal(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException, json.JSONDecodeError) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        self._write_json(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def _read_json_body(self, handler: BaseHTTPRequestHandler) -> dict:
        content_length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(content_length) if content_length else b"{}"
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _read_request_payload(self, handler: BaseHTTPRequestHandler) -> dict:
        content_length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(content_length) if content_length else b"{}"
        content_type = handler.headers.get("Content-Type", "")
        if "application/x-www-form-urlencoded" in content_type:
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
            return {key: values[-1] if values else "" for key, values in parsed.items()}
        payload = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("Request body must be an object.")
        return payload

    def _analytics_distinct_id_from_request(self, handler: BaseHTTPRequestHandler) -> str:
        supplied = (handler.headers.get("X-PostHog-Distinct-Id") or "").strip()
        if supplied:
            return self._analytics_distinct_ids.remember(supplied)
        return self._analytics_distinct_ids.get_or_create()

    def _write_json(self, handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        self._write_cors_headers(handler)
        handler.end_headers()
        handler.wfile.write(encoded)

    def _write_cors_headers(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type, X-PostHog-Distinct-Id")
        handler.send_header("Access-Control-Allow-Private-Network", "true")

    def _write_cors_preflight(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(HTTPStatus.NO_CONTENT)
        self._write_cors_headers(handler)
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    def health_status(self, handler: BaseHTTPRequestHandler | None = None) -> dict:
        return {
            "schema_version": HEALTH_STATUS_SCHEMA_VERSION,
            "service_id": HEALTH_STATUS_SERVICE_ID,
            "service_name": HEALTH_STATUS_SERVICE_NAME,
            "status": "ready",
            "bound_origin": self._bound_origin(handler),
            "dashboard_path": "/daily-dashboard#run-gmail-check",
            "health_path": HEALTH_STATUS_PATH,
            "storage_summary": self._cached_storage_summary(),
            "capabilities": [
                "sidebar-state",
                "daily-dashboard",
                "gmail-check",
                "attention-feedback",
                "unsubscribe-review",
            ],
        }

    def _bound_origin(self, handler: BaseHTTPRequestHandler | None = None) -> str:
        if handler is not None:
            host_header = handler.headers.get("Host", "")
            if host_header:
                return server_origin(host_header)
            server_address = getattr(handler.server, "server_address", None)
            if isinstance(server_address, tuple) and len(server_address) >= 2:
                host, port = server_address[0], server_address[1]
                host = host or "127.0.0.1"
                return server_origin(f"{host}:{port}")
        return server_origin("127.0.0.1:8021")

    def _cached_storage_summary(self) -> dict:
        now = time.monotonic()
        with self._health_storage_lock:
            if self._health_storage_cache is not None:
                created_at, payload = self._health_storage_cache
                if now - created_at <= HEALTH_STATUS_CACHE_SECONDS:
                    return payload
            payload = self._storage_summary()
            self._health_storage_cache = (time.monotonic(), payload)
            return payload

    def _storage_summary(self) -> dict:
        batches_dir = self._storage_dir / "batches"
        reports_dir = self._storage_dir / "reports"
        fetch_failures_dir = self._storage_dir / "fetch_failures"
        return {
            "storage_dir_name": self._storage_dir.name,
            "storage_dir_exists": self._storage_dir.exists(),
            "batches_dir_exists": batches_dir.exists(),
            "batch_count": len(list(batches_dir.glob("*.json"))) if batches_dir.exists() else 0,
            "reports_dir_exists": reports_dir.exists(),
            "report_count": len(list(reports_dir.glob("*_daily_report.json"))) if reports_dir.exists() else 0,
            "fetch_failures_dir_exists": fetch_failures_dir.exists(),
            "fetch_failure_count": len(list(fetch_failures_dir.glob("*.json"))) if fetch_failures_dir.exists() else 0,
        }

    def _cached_runtime_payload(self) -> dict:
        now = time.monotonic()
        with self._companion_data_lock:
            if self._runtime_payload_cache is not None:
                created_at, payload = self._runtime_payload_cache
                if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                    return payload
            payload = build_companion_runtime_payload(self._storage_dir)
            self._runtime_payload_cache = (time.monotonic(), payload)
            return payload

    def _cached_daily_summary(self) -> dict:
        now = time.monotonic()
        with self._companion_data_lock:
            if self._daily_summary_cache is not None:
                created_at, payload = self._daily_summary_cache
                if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                    return payload
            payload = build_daily_summary(self._storage_dir)
            self._daily_summary_cache = (time.monotonic(), payload)
            return payload

    def _cached_unsubscribe_candidates(self) -> list[dict]:
        now = time.monotonic()
        with self._companion_data_lock:
            if self._unsubscribe_candidates_cache is not None:
                created_at, payload = self._unsubscribe_candidates_cache
                if now - created_at <= COMPANION_DATA_CACHE_SECONDS:
                    return payload
            payload = self._unsubscribe_store.list_candidates()
            self._unsubscribe_candidates_cache = (time.monotonic(), payload)
            return payload

    def _async_follow_up_payload(self) -> dict | None:
        with self._async_follow_up_lock:
            if self._async_follow_up_state is None:
                return None
            return dict(self._async_follow_up_state)

    def _set_async_follow_up_state(self, payload: dict | None) -> None:
        with self._async_follow_up_lock:
            self._async_follow_up_state = dict(payload) if payload else None

    def _recent_activity_feed(self) -> list[dict]:
        follow_up = self._async_follow_up_payload()
        if not follow_up:
            return []
        return [
            {
                "id": follow_up.get("kind") or "async-follow-up",
                "kind": follow_up.get("kind") or "async-follow-up",
                "state": follow_up.get("state") or "working",
                "label": follow_up.get("label") or "Background refresh",
                "message": follow_up.get("message") or "",
            }
        ]

    def _sidebar_ui_state(self) -> dict:
        return {
            "default_mode": "expanded",
            "can_minimize": True,
            "panel_title": "Threadwise",
            "allowed_labels": [
                {"id": label, "name": gmail_label_name(label)}
                for label in CANONICAL_LABEL_ORDER
            ],
            "async_follow_up": self._async_follow_up_payload(),
            "activity_feed": self._recent_activity_feed(),
        }

    def _fast_sidebar_state(self, selected_context: dict | None) -> dict:
        return {
            "contract_version": "gmail-companion-sidebar-v1",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "selected_context": selected_context or {},
            "selected_email": build_selected_email_state(
                self._storage_dir,
                self._cached_unsubscribe_candidates(),
                selected_context or {},
            ),
            "daily_summary": self._cached_daily_summary(),
            "run_status": load_gmail_dashboard_run_status(self._storage_dir),
            "ui_state": self._sidebar_ui_state(),
        }

    def _invalidate_companion_caches(self) -> None:
        with self._companion_data_lock:
            self._runtime_payload_cache = None
            self._daily_summary_cache = None
            self._unsubscribe_candidates_cache = None
        with self._harness_state_lock:
            self._harness_state_cache.clear()

    def _run_teach_apply_follow_up_refresh(self, selected_context: dict) -> None:
        try:
            self._invalidate_companion_caches()
            self.sidebar_state(selected_context)
            cache_key = json.dumps(selected_context or {}, sort_keys=True)
            payload = self._build_harness_state(selected_context)
            with self._harness_state_lock:
                self._harness_state_cache[cache_key] = (time.monotonic(), payload)
            self._set_async_follow_up_state(
                {
                    "kind": "teach-apply-refresh",
                    "state": "done",
                    "label": "Background refresh done",
                    "message": "Queue summary and follow-up context are ready.",
                }
            )
        except Exception as exc:
            self._set_async_follow_up_state(
                {
                    "kind": "teach-apply-refresh",
                    "state": "retry",
                    "label": "Background refresh stalled",
                    "message": f"Queue summary refresh stalled: {exc}",
                }
            )

    def _start_teach_apply_follow_up_refresh(self, selected_context: dict) -> None:
        self._set_async_follow_up_state(
            {
                "kind": "teach-apply-refresh",
                "state": "working",
                "label": "Background refresh running",
                "message": "Refreshing the queue summary and follow-up context in the background.",
            }
        )
        threading.Thread(
            target=self._run_teach_apply_follow_up_refresh,
            args=(dict(selected_context or {}),),
            daemon=True,
        ).start()

    def sidebar_state(self, selected_context: dict | None) -> dict:
        return self._fast_sidebar_state(selected_context)

    def harness_state(self, selected_context: dict | None) -> dict:
        cache_key = json.dumps(selected_context or {}, sort_keys=True)
        now = time.monotonic()
        with self._harness_state_lock:
            cached = self._harness_state_cache.get(cache_key)
            if cached is not None:
                created_at, payload = cached
                if now - created_at <= HARNESS_STATE_CACHE_SECONDS:
                    return self._with_live_understanding_state(payload, selected_context or {})

            payload = self._build_harness_state(selected_context)
            self._harness_state_cache[cache_key] = (time.monotonic(), payload)
            return self._with_live_understanding_state(payload, selected_context or {})

    def _build_harness_state(self, selected_context: dict | None) -> dict:
        runtime = self._cached_runtime_payload()
        items = runtime.get("items", [])
        selected_context = selected_context or {}
        if not (selected_context.get("message_id") or selected_context.get("subject") or selected_context.get("sender")):
            for item in items:
                if item.get("status") == "needs-attention":
                    selected_context = {
                        "provider": "gmail",
                        "message_id": item.get("message_id", ""),
                        "subject": item.get("subject", ""),
                        "sender": item.get("sender", ""),
                    }
                    break
        return {
            "selected_context": selected_context,
            "sidebar_state": self.sidebar_state(selected_context),
            "recent_items": items[:24],
            "needs_attention_items": [item for item in items if item.get("status") == "needs-attention"][:12],
            "auto_handled_items": [item for item in items if item.get("status") == "auto-handled"][:12],
            "kept_visible_items": [item for item in items if item.get("status") in {"kept-visible", "auto-labeled"}][:12],
        }

    def _with_live_understanding_state(self, payload: dict, selected_context: dict) -> dict:
        sidebar_state = dict(payload.get("sidebar_state") or {})
        selected_email = dict(sidebar_state.get("selected_email") or {})
        live_context = selected_context or payload.get("selected_context") or {}
        selected_email.update(selected_email_understanding_state(live_context))
        sidebar_state["selected_email"] = selected_email
        return {
            **payload,
            "sidebar_state": sidebar_state,
        }

    def teach_preview(self, payload: dict) -> dict:
        selected_context = payload.get("selected_context") or {}
        target_label = payload["target_label"]
        note = (payload.get("note") or "").strip()
        scope = payload.get("scope") or "sender"
        preview = build_sidebar_teach_preview(
            self._storage_dir,
            selected_context=selected_context,
            target_label=target_label,
            note=note,
            scope=scope,
        )
        preview["inbox_backfill"] = self._build_inbox_backfill_preview(preview)
        return preview

    def teach_apply(self, payload: dict, *, analytics_distinct_id: str | None = None) -> dict:
        selected_context = payload.get("selected_context") or {}
        target_label = payload["target_label"]
        note = (payload.get("note") or "").strip()
        scope = payload.get("scope") or "sender"
        mode = payload["mode"]
        teaching_result = apply_sidebar_teaching(
            self._storage_dir,
            selected_context=selected_context,
            target_label=target_label,
            note=note,
            scope=scope,
            mode=mode,
        )
        write_through_summary = self._write_teach_result_to_gmail(
            teaching_result["current"]["account_id"],
            teaching_result["current"]["message_id"],
            teaching_result["mode"],
            teaching_result["preview_matches"],
            semantic_rule={
                **(teaching_result.get("semantic_rule") or {}),
                "target_label": target_label,
            },
            current_subject=teaching_result["current"].get("subject") or "",
            current_sender=teaching_result["current"].get("sender") or "",
        )
        self._capture_label_write_outcomes(
            analytics_distinct_id or self._analytics_distinct_ids.get_or_create(),
            teaching_result["mode"],
            write_through_summary,
        )
        self._start_teach_apply_follow_up_refresh(selected_context)
        refreshed = self._fast_sidebar_state(selected_context)
        return {
            "acknowledgment": self._teach_apply_acknowledgment(teaching_result, write_through_summary),
            "mode": teaching_result["mode"],
            "matched_existing_count": teaching_result["matched_existing_count"],
            "proposal": teaching_result["proposal"],
            "gmail_write_through": write_through_summary,
            "outcome": self._teach_apply_outcome(teaching_result, write_through_summary),
            "sidebar_state": refreshed,
        }

    def _capture_label_write_outcomes(
        self,
        distinct_id: str,
        mode: str,
        write_summary: dict,
    ) -> None:
        if write_summary.get("mode") in {"disabled", "no-gmail-write-future-rule-only"}:
            return
        rule_scope = {
            "current-only": "current_email",
            "matching-existing": "included_existing",
            "apply-included": "included_existing",
            "save-future-rule": "future_email",
            "future-only": "future_email",
        }.get(mode, "current_email")
        common = {
            "app_version": THREADWISE_APP_VERSION,
            "workflow_version": ANALYTICS_WORKFLOW_VERSION,
            "source": "companion_service",
            "rule_scope": rule_scope,
            "retry_count": 0,
        }
        messages_written = int(write_summary.get("messages_written") or 0)
        failed_count = int(write_summary.get("label_write_failed") or 0)
        if messages_written:
            self._analytics.capture(
                distinct_id=distinct_id,
                event="label write completed",
                properties={**common, "write_count_bucket": bucket_count(messages_written)},
            )
        if failed_count or write_summary.get("mode") == "gmail-write-failed":
            error_category = (
                "gmail_client_initialization"
                if write_summary.get("mode") == "gmail-write-failed"
                else "provider_write_error"
            )
            self._analytics.capture(
                distinct_id=distinct_id,
                event="label write failed",
                properties={**common, "error_category": error_category},
            )

    def teach_exclude(self, payload: dict) -> dict:
        selected_context = payload.get("selected_context") or {}
        target_label = payload["target_label"]
        note = (payload.get("note") or "").strip()
        scope = payload.get("scope") or "sender"
        excluded_message_id = payload["excluded_message_id"]
        reason = (payload.get("reason") or "").strip()
        exclusion_result = exclude_sidebar_teaching_match(
            self._storage_dir,
            selected_context=selected_context,
            target_label=target_label,
            note=note,
            scope=scope,
            excluded_message_id=excluded_message_id,
            reason=reason,
        )
        refreshed_preview = build_sidebar_teach_preview(
            self._storage_dir,
            selected_context=selected_context,
            target_label=target_label,
            note=note,
            scope=scope,
        )
        return {
            **exclusion_result,
            "preview": {
                **refreshed_preview,
                "amendment_proposal": exclusion_result.get("amendment_proposal"),
            },
            "sidebar_state": self.sidebar_state(selected_context),
        }

    def teach_amendment(self, payload: dict) -> dict:
        selected_context = payload.get("selected_context") or {}
        target_label = payload["target_label"]
        note = (payload.get("note") or "").strip()
        scope = payload.get("scope") or "sender"
        amendment = payload.get("amendment") or {}
        decision = payload["decision"]
        result = apply_rule_amendment_decision(
            self._storage_dir,
            selected_context=selected_context,
            target_label=target_label,
            note=note,
            scope=scope,
            amendment=amendment,
            decision=decision,
        )
        return {
            **result,
            "acknowledgment": (
                "Updated the proposed rule boundary and recomputed affected emails."
                if result["amendment_status"] == "accepted"
                else "Kept the original proposed rule. No amendment was applied."
            ),
            "sidebar_state": self.sidebar_state(selected_context),
        }

    def unsubscribe_select_current(self, payload: dict) -> dict:
        selected_context = payload.get("selected_context") or {}
        matched = find_matching_item(self._storage_dir, selected_context)
        if matched is None:
            raise ValueError("Selected Gmail message is not in the current local snapshot.")
        item = matched["item"]
        candidate = find_unsubscribe_candidate(
            self._unsubscribe_store.list_candidates(),
            item.get("sender") or selected_context.get("sender") or "",
        )
        if candidate is None:
            raise ValueError("No unsubscribe candidate is available for this email.")
        self._unsubscribe_store.save_selection_states(
            [candidate["list_key"]],
            [candidate["list_key"]],
        )
        refreshed = self.sidebar_state(selected_context)
        return {
            "acknowledgment": (
                f"Queued {candidate.get('display_name') or 'this sender'} for unsubscribe review. "
                "Nothing has been unsubscribed yet."
            ),
            "candidate": build_unsubscribe_detail(candidate, self._storage_dir),
            "sidebar_state": refreshed,
        }

    def attention_feedback(self, payload: dict) -> dict:
        feedback = record_attention_feedback(self._storage_dir, payload)
        return {
            "acknowledgment": "Recorded attention feedback. No broader rule was created.",
            "feedback": feedback,
            "gmail_mutation": "none",
            "creates_broader_rule": False,
            "attention_summary": build_daily_attention_summary(self._storage_dir),
        }

    def founder_feedback(self, payload: dict) -> dict:
        feedback = record_founder_feedback(self._storage_dir, payload)
        return {
            "acknowledgment": "Saved feedback locally for later product review.",
            "feedback": feedback,
            "gmail_mutation": "none",
            "external_sync": "none",
        }

    def trigger_gmail_check(self, payload: dict) -> dict:
        if not self._gmail_check_enabled:
            raise ValueError("Gmail checks are disabled for this server.")
        payload = dict(payload)
        payload.setdefault("account_id", infer_gmail_account_id(self._storage_dir))
        runner = self._gmail_run_runner or self._run_daily_gmail_check
        return trigger_dashboard_gmail_check(self._storage_dir, payload, runner)

    def preview_attention_rule_proposal(self, payload: dict) -> dict:
        message_id = payload.get("message_id") or ""
        proposal = build_attention_rule_proposal(self._storage_dir, message_id)
        return {
            "proposal": proposal,
            "gmail_mutation": "none",
            "acknowledgment": "Prepared attention rule proposal for review. No broader rule was applied.",
        }

    def review_attention_rule_proposal(self, payload: dict) -> dict:
        proposal_id = payload.get("proposal_id") or ""
        decision = payload.get("decision") or ""
        if decision == "approve":
            proposal = approve_attention_rule_proposal(
                self._storage_dir,
                proposal_id,
                application_mode=payload.get("application_mode") or "future_only",
            )
        elif decision == "reject":
            proposal = reject_attention_rule_proposal(
                self._storage_dir,
                proposal_id,
                notes=payload.get("notes") or "",
            )
        else:
            raise ValueError("Attention rule proposal review requires approve or reject.")
        return {
            "proposal": proposal,
            "gmail_mutation": "none",
        }

    def _run_daily_gmail_check(self, payload: dict):
        account_id = payload.get("account_id") or ""
        if not account_id:
            raise ValueError("No Gmail account id is available for the dashboard run.")
        gmail_client = self._gmail_client_factory(
            account_id,
            self._credentials_dir,
            self._client_secret_path,
            GMAIL_MODIFY_SCOPE,
        )
        return run_daily_gmail_automation(
            account_id=account_id,
            batch_size=payload.get("batch_size") or 50,
            storage_dir=self._storage_dir,
            gmail_client=gmail_client,
            attention_model_client=self._attention_model_client,
        )

    def _write_teach_result_to_gmail(
        self,
        account_id: str,
        selected_message_id: str,
        mode: str,
        preview_matches: list[dict],
        *,
        semantic_rule: dict | None = None,
        current_subject: str = "",
        current_sender: str = "",
    ) -> dict:
        if mode == "save-future-rule":
            return {
                "messages_written": 0,
                "inbox_removed": 0,
                "label_write_failed": 0,
                "label_write_skipped": 0,
                "inbox_remove_failed": 0,
                "inbox_remove_skipped": 0,
                "inbox_remove_ineligible": 0,
                "mode": "no-gmail-write-future-rule-only",
            }
        if not self._gmail_write_through_enabled:
            return {
                "messages_written": 0,
                "inbox_removed": 0,
                "label_write_failed": 0,
                "label_write_skipped": 0,
                "inbox_remove_failed": 0,
                "inbox_remove_skipped": 0,
                "inbox_remove_ineligible": 0,
                "mode": "disabled",
            }
        try:
            gmail_client = self._gmail_client_factory(
                account_id,
                self._credentials_dir,
                self._client_secret_path,
                GMAIL_MODIFY_SCOPE,
            )
        except Exception as exc:
            return {
                "messages_written": 0,
                "inbox_removed": 0,
                "label_write_failed": 0,
                "label_write_skipped": 0,
                "inbox_remove_failed": 0,
                "inbox_remove_skipped": 0,
                "inbox_remove_ineligible": 0,
                "mode": "gmail-write-failed",
                "error": str(exc),
            }
        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=self._storage_dir,
            label_name_resolver=gmail_label_name,
        )
        batch_items = load_items_for_gmail_write_through(
            self._storage_dir,
            selected_message_id=selected_message_id,
            mode=mode,
            preview_matches=preview_matches,
        )
        write_applied = 0
        write_failed = 0
        write_skipped = 0
        inbox_removed = 0
        inbox_failed = 0
        inbox_skipped = 0
        inbox_ineligible = 0
        for batch_id, items in batch_items.items():
            mutation = writer.apply_reviewed_mutations(batch_id, items)
            write_summary = mutation["write_summary"]
            inbox_summary = mutation["inbox_summary"]
            write_applied += write_summary["applied_count"]
            write_failed += write_summary["failed_count"]
            write_skipped += write_summary["skipped_count"]
            inbox_removed += inbox_summary["applied_count"]
            inbox_failed += inbox_summary["failed_count"]
            inbox_skipped += inbox_summary["skipped_count"]
            inbox_ineligible += inbox_summary["ineligible_count"]
        remote_search_count = 0
        remote_applied = 0
        remote_failed = 0
        remote_skipped = 0
        remote_batch_id = ""
        remote_inbox_removed = 0
        remote_inbox_failed = 0
        remote_inbox_skipped = 0
        remote_inbox_ineligible = 0
        if mode == "apply-included":
            local_ids = {
                item.get("message_id")
                for items in batch_items.values()
                for item in items
                if item.get("message_id")
            }
            remote_summary = self._apply_rule_to_matching_inbox_messages(
                gmail_client,
                account_id=account_id,
                semantic_rule=semantic_rule or {},
                current_subject=current_subject,
                current_sender=current_sender,
                excluded_message_ids=local_ids,
            )
            remote_search_count = remote_summary["matched_count"]
            remote_applied = remote_summary["applied_count"]
            remote_failed = remote_summary["failed_count"]
            remote_skipped = remote_summary["skipped_count"]
            remote_batch_id = remote_summary["batch_id"]
            remote_inbox_removed = remote_summary["inbox_removed_count"]
            remote_inbox_failed = remote_summary["inbox_failed_count"]
            remote_inbox_skipped = remote_summary["inbox_skipped_count"]
            remote_inbox_ineligible = remote_summary["inbox_ineligible_count"]
            write_applied += remote_applied
            write_failed += remote_failed
            write_skipped += remote_skipped
            inbox_removed += remote_inbox_removed
            inbox_failed += remote_inbox_failed
            inbox_skipped += remote_inbox_skipped
            inbox_ineligible += remote_inbox_ineligible
        return {
            "messages_written": write_applied,
            "inbox_removed": inbox_removed,
            "label_write_failed": write_failed,
            "label_write_skipped": write_skipped,
            "inbox_remove_failed": inbox_failed,
            "inbox_remove_skipped": inbox_skipped,
            "inbox_remove_ineligible": inbox_ineligible,
            "remote_match_count": remote_search_count,
            "remote_applied_count": remote_applied,
            "remote_failed_count": remote_failed,
            "remote_skipped_count": remote_skipped,
            "remote_batch_id": remote_batch_id,
            "remote_inbox_removed_count": remote_inbox_removed,
            "remote_inbox_failed_count": remote_inbox_failed,
            "remote_inbox_skipped_count": remote_inbox_skipped,
            "remote_inbox_ineligible_count": remote_inbox_ineligible,
            "mode": "applied",
        }

    def _build_inbox_backfill_preview(self, preview: dict) -> dict:
        if not self._gmail_write_through_enabled:
            return {
                "available": False,
                "estimated_count": 0,
                "requires_confirmation": False,
                "query": "",
            }
        account_id = preview.get("selected_account_id") or ""
        query = self._build_gmail_backfill_query(
            semantic_rule=preview.get("semantic_rule") or {},
            current_subject=preview.get("selected_subject") or "",
            current_sender=preview.get("selected_sender") or "",
        )
        if not account_id or not query:
            return {
                "available": False,
                "estimated_count": 0,
                "requires_confirmation": False,
                "query": query,
            }
        try:
            gmail_client = self._gmail_client_factory(
                account_id,
                self._credentials_dir,
                self._client_secret_path,
                GMAIL_MODIFY_SCOPE,
            )
            matches = gmail_client.search_message_ids(query, INBOX_BACKFILL_ESTIMATE_CAP + 1)
        except Exception:
            return {
                "available": False,
                "estimated_count": 0,
                "requires_confirmation": False,
                "query": query,
            }
        estimated_count = len(matches)
        capped = estimated_count > INBOX_BACKFILL_ESTIMATE_CAP
        if capped:
            estimated_count = INBOX_BACKFILL_ESTIMATE_CAP
        return {
            "available": True,
            "estimated_count": estimated_count,
            "is_capped": capped,
            "requires_confirmation": estimated_count > INBOX_BACKFILL_CONFIRM_THRESHOLD or capped,
            "query": query,
        }

    def _apply_rule_to_matching_inbox_messages(
        self,
        gmail_client,
        *,
        account_id: str,
        semantic_rule: dict,
        current_subject: str,
        current_sender: str,
        excluded_message_ids: set[str],
    ) -> dict:
        query = self._build_gmail_backfill_query(
            semantic_rule=semantic_rule,
            current_subject=current_subject,
            current_sender=current_sender,
        )
        if not query:
            return self._empty_remote_mutation_summary()
        message_ids = gmail_client.search_message_ids(query, 1000)
        filtered_ids = [message_id for message_id in message_ids if message_id and message_id not in excluded_message_ids]
        target_label = (semantic_rule or {}).get("target_label") or ""
        if not gmail_label_name(target_label):
            return {
                **self._empty_remote_mutation_summary(),
                "matched_count": len(filtered_ids),
                "skipped_count": len(filtered_ids),
            }
        if not filtered_ids:
            return self._empty_remote_mutation_summary()
        batch_id = f"gmail-companion-backfill-{uuid4().hex}"
        reviewed_items = [
            {
                "source": "gmail",
                "account_id": account_id,
                "message_id": message_id,
                "review_state": "reviewed",
                "review_action": "sidebar-remote-backfill",
                "applied_labels": [target_label],
                "final_labels": [target_label],
            }
            for message_id in filtered_ids
        ]
        write_json_artifact(
            "gmail_mutation_batch",
            self._storage_dir,
            {
                "batch_id": batch_id,
                "provider": "gmail",
                "account_id": account_id,
                "items": reviewed_items,
            },
            batch_id,
        )
        writer = MockGmailLabelWriter(
            gmail_client=gmail_client,
            storage_dir=self._storage_dir,
            label_name_resolver=gmail_label_name,
        )
        mutation = writer.apply_reviewed_mutations(batch_id, reviewed_items)
        write_summary = mutation["write_summary"]
        inbox_summary = mutation["inbox_summary"]
        return {
            "matched_count": len(filtered_ids),
            "applied_count": write_summary["applied_count"],
            "failed_count": write_summary["failed_count"],
            "skipped_count": write_summary["skipped_count"],
            "batch_id": batch_id,
            "inbox_removed_count": inbox_summary["applied_count"],
            "inbox_failed_count": inbox_summary["failed_count"],
            "inbox_skipped_count": inbox_summary["skipped_count"],
            "inbox_ineligible_count": inbox_summary["ineligible_count"],
        }

    def _empty_remote_mutation_summary(self) -> dict:
        return {
            "matched_count": 0,
            "applied_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "batch_id": "",
            "inbox_removed_count": 0,
            "inbox_failed_count": 0,
            "inbox_skipped_count": 0,
            "inbox_ineligible_count": 0,
        }

    def _build_gmail_backfill_query(self, *, semantic_rule: dict, current_subject: str, current_sender: str) -> str:
        sender = (semantic_rule or {}).get("sender") or current_sender or ""
        semantic_pattern = (semantic_rule or {}).get("semantic_pattern") or ""
        rule_type = (semantic_rule or {}).get("rule_type") or ""
        subject_keywords = self._query_keywords_for_semantic_pattern(semantic_pattern, current_subject)
        parts: list[str] = []
        if sender and "@" in sender:
            parts.append(f"from:{sender}")
        if subject_keywords:
            if len(subject_keywords) == 1:
                parts.append(subject_keywords[0])
            else:
                parts.append("{" + " ".join(subject_keywords) + "}")
        elif rule_type == "sender":
            return " ".join(parts)
        return " ".join(part for part in parts if part).strip()

    def _query_keywords_for_semantic_pattern(self, semantic_pattern: str, current_subject: str) -> list[str]:
        pattern = str(semantic_pattern or "").lower()
        mappings = {
            "job, recruiter, or interview emails": ["job", "jobs", "recruiter", "interview", "application"],
            "billing, receipt, or payment notices": ["receipt", "invoice", "payment", "billing"],
            "travel and booking emails": ["travel", "flight", "hotel", "booking"],
            "newsletter or marketing emails": ["newsletter", "promo", "sale", "digest"],
            "account, security, or statement notices": ["security", "account", "statement", "login"],
            "financial account notices": ["account", "statement", "payment"],
            "low-value or suspicious emails": ["alert", "promo", "notice"],
        }
        if pattern in mappings:
            return mappings[pattern]
        words = []
        for raw in (current_subject or "").lower().split():
            clean = "".join(ch for ch in raw if ch.isalnum())
            if len(clean) < 4:
                continue
            if clean in {"this", "that", "from", "with", "more", "your", "have"}:
                continue
            words.append(clean)
            if len(words) == 3:
                break
        return words

    def _teach_apply_acknowledgment(self, teaching_result: dict, write_through_summary: dict) -> str:
        base = teaching_result["acknowledgment"]
        mode = write_through_summary.get("mode")
        local_changed = int(bool(teaching_result.get("current_changed"))) + int(teaching_result.get("matched_existing_count") or 0)
        if mode == "no-gmail-write-future-rule-only":
            return f"{base} Gmail was not changed because this action only saved future behavior."
        if mode == "disabled":
            return f"{base} Stored locally for {local_changed} email{'' if local_changed == 1 else 's'}. Gmail write-through is disabled here."
        if mode == "gmail-write-failed":
            error = write_through_summary.get("error") or "unknown Gmail write error"
            return (
                f"{base} Stored locally for {local_changed} email{'' if local_changed == 1 else 's'}, "
                f"but Gmail was not updated: {error}. Retry Gmail write-through after the connection is healthy."
            )
        messages_written = int(write_through_summary.get("messages_written") or 0)
        label_failed = int(write_through_summary.get("label_write_failed") or 0)
        label_skipped = int(write_through_summary.get("label_write_skipped") or 0)
        inbox_removed = int(write_through_summary.get("inbox_removed") or 0)
        inbox_failed = int(write_through_summary.get("inbox_remove_failed") or 0)
        if label_failed or inbox_failed:
            return (
                f"{base} Stored locally for {local_changed} email{'' if local_changed == 1 else 's'}. "
                f"Gmail label writes: {messages_written} applied, {label_failed} failed"
                f"{f', {label_skipped} skipped' if label_skipped else ''}. "
                f"Inbox removal: {inbox_removed} applied, {inbox_failed} failed. Retry failed Gmail writes when ready."
            )
        return (
            f"{base} Gmail label writes: {messages_written} applied"
            f"{f', {label_skipped} skipped' if label_skipped else ''}. "
            f"Inbox removal: {inbox_removed} applied."
        )

    def _teach_apply_outcome(self, teaching_result: dict, write_through_summary: dict) -> dict:
        mode = teaching_result.get("mode") or ""
        gmail_mode = write_through_summary.get("mode") or ""
        label_failed = int(write_through_summary.get("label_write_failed") or 0)
        messages_written = int(write_through_summary.get("messages_written") or 0)
        current_changed = bool(teaching_result.get("current_changed"))
        future_rule_saved = bool(teaching_result.get("future_rule_saved"))
        current_written = current_changed and gmail_mode == "applied" and messages_written > 0 and label_failed == 0
        scope = {
            "current-only": "current-email",
            "matching-existing": "matching-existing",
            "save-future-rule": "future-rule",
            "future-only": "current-email-and-future-rule",
            "apply-included": "included-existing",
        }.get(mode, mode or "unknown")
        changed_count = int(current_changed) + int(teaching_result.get("matched_existing_count") or 0)
        if future_rule_saved and not changed_count:
            state = "future-rule-saved"
        elif changed_count and label_failed:
            state = "partially-changed"
        elif changed_count:
            state = "changed"
        else:
            state = "unchanged"
        return {
            "state": state,
            "scope": scope,
            "current_email_changed_locally": current_changed,
            "current_email_written_to_gmail": current_written,
            "matching_existing_changed_locally": int(teaching_result.get("matched_existing_count") or 0),
            "future_rule_saved": future_rule_saved,
            "gmail_write_mode": gmail_mode,
            "gmail_label_write_failed": label_failed,
        }

    def render_simulator(self) -> str:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Simulator</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3efe4;
      --ink: #1f1a14;
      --muted: #6b6255;
      --line: #d7cfbf;
      --panel: #fffdf8;
      --accent: #0f766e;
      --accent-soft: #d8f3ef;
      --soft: #f5efe2;
      --warn-soft: #fff4dd;
      --warn-ink: #8a4b00;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at 18px 18px, rgba(36,24,18,.05) 2px, transparent 2px) 0 0 / 36px 36px, linear-gradient(135deg,#f7efe0 0%,#fdfaf2 52%,#e7f3ee 100%); color: var(--ink); }
    main { min-height: 100vh; padding: 34px; display: grid; place-items: center; }
    .hero { display: none; }
    .eyebrow { color: var(--muted); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.14em; font-weight: 820; }
    .hero h1 { margin: 6px 0 0; font-size: 1.6rem; }
    .hero p { margin: 6px 0 0; color: var(--muted); line-height: 1.45; max-width: 58rem; }
    .hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .button { border: 2px solid #241812; border-radius: 11px; padding: 10px 14px; cursor: pointer; font: inherit; font-weight: 760; box-shadow: 2px 2px 0 #241812; }
    .button.primary { background: #2eb67d; color: #241812; }
    .button.secondary { background: #e9efe2; color: var(--ink); }
    .layout { width: min(1180px, 100%); min-height: 690px; display: grid; grid-template-columns: 1fr 420px; gap: 28px; align-items: stretch; transition: grid-template-columns .16s ease; }
    .layout.expanded-review { width: min(1320px, 100%); grid-template-columns: minmax(220px, .42fr) minmax(720px, 1fr); }
    .layout > .card:nth-of-type(2) { display: none; }
    .card { border: 1px solid rgba(60,64,67,.22); border-radius: 18px; background: #fff; padding: 0; overflow: hidden; box-shadow: 0 24px 70px rgba(36,24,18,.08); display:grid; grid-template-columns:178px minmax(0,1fr); grid-template-rows:64px 46px 1fr; }
    .card::before { content: "☰  Gmail        Search mail                                      ?   ⚙   Demo account"; grid-column:1 / 3; grid-row:1; height:64px; display:flex; align-items:center; gap:14px; padding:0 18px; border-bottom:1px solid #e8eaed; color:#3c4043; font-size:20px; font-weight:650; white-space:pre; }
    .card > .eyebrow { grid-column:1; grid-row:2 / 4; margin:0; padding:18px 12px 0 24px; border-right:1px solid #e8eaed; color:transparent; position:relative; letter-spacing:0; }
    .card > .eyebrow::before { content:"+   Compose\\a\\a Inbox                 14\\a Starred\\a Snoozed\\a Sent\\a Drafts\\a\\a EA/Work\\a EA/Promotions"; white-space:pre; color:#3c4043; font-size:14px; font-weight:500; line-height:2.35; text-transform:none; letter-spacing:0; }
    .card > .eyebrow::first-line { background:#c2e7ff; border-radius:18px; }
    .card-title { grid-column:2; grid-row:2; height:46px; margin:0; padding:0 16px; display:flex; align-items:center; color:#d93025; border-bottom:3px solid #d93025; font-size:0.84rem; font-weight:800; }
    .card-title::before { content:"□  ↻   ⋮    Primary"; }
    .card-title { font-size:0; }
    .card-title::before { font-size:0.84rem; }
    .label-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .chip-button, .pill { border-radius: 999px; padding: 6px 10px; background: #f1eadb; color: #5d5342; font-size: 0.8rem; }
    .chip-button { border: 0; cursor: pointer; font: inherit; }
    .chip-button.active { background: var(--accent-soft); color: var(--accent); }
    .card > .label-row { grid-column:2; grid-row:2; align-self:stretch; justify-self:stretch; margin:0; padding:0 12px 0 142px; display:flex; align-items:center; gap:12px; border-bottom:3px solid #d93025; overflow:hidden; }
    .card > .label-row .chip-button { height:46px; border-radius:0; padding:0 2px; background:transparent;color:#5f6368;font-weight:700;white-space:nowrap;box-shadow:none; }
    .card > .label-row .chip-button.active { background:transparent;color:#d93025;box-shadow:inset 0 -3px 0 #d93025; }
    .list-stack { grid-column:2; grid-row:3; display:block; margin-top:0; max-height:none; overflow:hidden; }
    .list-item { width:100%; min-height:40px; text-align:left; border:0; border-bottom:1px solid #f1f3f4; border-radius:0; background:#fff; padding:0 12px 0 16px; cursor:pointer; font:inherit; color:#202124; display:grid; grid-template-columns:18px minmax(104px,.24fr) minmax(0,1fr) 58px; column-gap:12px; align-items:center; }
    .list-item::before { content:"□"; color:#b8bec5; font-size:16px; }
    .list-item::after { content:"9:18 AM"; color:#5f6368; font-size:0.78rem; justify-self:end; }
    .list-item.active { border-color: #f1f3f4; background: #f2f6fc; box-shadow: inset 3px 0 0 #d93025; }
    .list-item-subject { font-size: 0.84rem; font-weight: 800; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .list-item-meta { margin-top: 0; color: #5f6368; font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .card .list-item .label-row { display:none; }
    .field-stack .list-item { display:block;min-height:auto;border:2px solid #241812;border-radius:12px;background:#fffdf7;padding:9px 10px;box-shadow:2px 2px 0 rgba(36,24,18,.18); }
    .field-stack .list-item::before, .field-stack .list-item::after { content:none; }
    .field-stack .list-item .label-row { display:flex;margin-top:8px;gap:6px; }
    .field-stack .list-item .pill { font-size:0.68rem;padding:4px 7px;box-shadow:1px 1px 0 rgba(36,24,18,.22); }
    .field-stack .list-item-subject, .field-stack .list-item-meta { white-space:normal; }
    .message-title { margin-top: 8px; font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
    .message-meta { margin-top: 8px; color: var(--muted); line-height: 1.45; overflow-wrap: anywhere; }
    .message-body { margin-top: 14px; border-radius: 16px; background: var(--soft); padding: 14px; color: var(--ink); line-height: 1.55; min-height: 260px; white-space: pre-wrap; }
    .note { margin-top: 12px; border-radius: 14px; background: rgba(255,255,255,0.65); padding: 12px; color: var(--muted); line-height: 1.45; }
    .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
    .summary-grid--three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .metric-button { border: 0; border-radius: 14px; background: var(--soft); padding: 12px; text-align: left; cursor: pointer; font: inherit; color: var(--ink); }
    .metric-button { border: 2px solid #241812; box-shadow: 2px 2px 0 rgba(36,24,18,.18); background: #fffdf7; }
    .metric-button.active { background: #e7f6f4; box-shadow: inset 0 0 0 1px rgba(15,118,110,0.22); }
    .metric-button strong { display:block;font-size:1.15rem;line-height:1; }
    .metric-button span { display:block;margin-top:3px; }
    .teach-card { border: 3px solid #241812; border-radius:18px; background: #ffe1a3; padding: 0; overflow: hidden; box-shadow:2px 2px 0 rgba(36,24,18,.18); }
    .teach-card > .reason-label { display: flex; align-items: center; min-height: 40px; padding: 0 13px; border-bottom: 3px solid #241812; background: #ffc64a; color: #241812; font-weight: 900; }
    .teach-panel { margin: 12px; display: grid; gap: 12px; }
    .teach-panel .field-stack { margin-top: 0; }
    .teach-card > .field-stack, .teach-card > .preview-card, .teach-card > .success-card, .teach-card > .error-card, .teach-card > .note { margin: 12px; }
    .empty { color: var(--muted); line-height: 1.45; }
    .panel { background: var(--paper); border: 3px solid #241812; border-radius: 18px; box-shadow: 6px 6px 0 #241812; overflow: hidden; align-self: start; }
    .panel.minimized .content { display: none; }
    .header { display:flex;align-items:center;justify-content:space-between;gap:12px;padding:17px 18px;border-bottom:3px solid #241812;background:#fff4d7; }
    .header-copy { display:grid;gap:6px;min-width:0; }
    .header-top { display:flex;align-items:center;gap:8px; }
    .brand-lockup { display:flex;align-items:center;gap:10px;min-width:0; }
    .brand-mark { width:42px;height:42px;border-radius:12px;border:2px solid #241812;box-shadow:3px 3px 0 #241812;flex:0 0 auto;background:#fff8df; }
    .brand-kicker { color:#ad6400;font-family:ui-serif,Georgia,"Times New Roman",serif;font-size:0.58rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;white-space:nowrap;line-height:1.05; }
    .dot { width:10px;height:10px;border-radius:999px;background:var(--accent);box-shadow:0 0 0 4px rgba(15,118,110,0.12); }
    .title { font-size:1.35rem;font-weight:840;letter-spacing:-0.04em;line-height:1; }
    .subtitle { color: var(--muted); font-size:0.88rem; line-height:1.35; }
    .minimize { border:2px solid #241812;background:#e9efe2;color:var(--ink);border-radius:11px;font-weight:760;padding:9px 12px;box-shadow:2px 2px 0 #241812;cursor:pointer;font:inherit; }
    .content { padding:14px; display:grid; gap:13px; }
    .hero-card { border:3px solid #241812;border-radius:18px;padding:16px;background:#fffdf7;box-shadow:2px 2px 0 rgba(36,24,18,.18); }
    .secondary-card { border:3px solid #241812;border-radius:18px;padding:16px;background:#e9efe2;box-shadow:2px 2px 0 rgba(36,24,18,.18); }
    .subject { margin-top: 7px; font-size: 1.3rem; font-weight: 840; line-height: 1.04; letter-spacing: -0.015em; }
    .sender { margin-top: 6px; color: var(--muted); font-size: 0.88rem; overflow-wrap: anywhere; }
    .pill-row { display:flex;flex-wrap:wrap;gap:8px;margin-top:12px; }
    .pill { display:inline-flex;align-items:center;padding:7px 10px;font-size:0.78rem;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28); }
    .classification-pill { background:#f1eadf;color:#241812; }
    .status-pill { background:#dff8ed;color:#09633c; }
    .warn-pill { background:var(--warn-soft);color:var(--warn-ink); }
    .agent-copy { margin-top:10px;color:#6f5e4c;line-height:1.36;font-weight:720; }
    .reason-wrap { margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px; }
    .reason-label { font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted); }
    .reason { margin-top:8px;color:var(--ink);line-height:1.45; }
    .field-stack { display:grid;gap:8px;margin-top:10px; }
    .select, .textarea { width:100%;border-radius:11px;border:2px solid #241812;background:#fffdf7;color:var(--ink);font:inherit;box-shadow:2px 2px 0 rgba(36,24,18,.18); }
    .select { padding:10px 12px; }
    .textarea { min-height:84px;padding:10px 12px;resize:vertical; }
    .button-row { display:flex;flex-wrap:wrap;gap:8px; }
    .action-button { border:2px solid #241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812; }
    .action-button.primary { background:#2eb67d;color:#241812; }
    .action-button.secondary { background:#fffdf7;color:var(--ink); }
    .action-button.info { background:#3d6df2;color:#fff; }
    .action-button.future { background:#ffc64a;color:#241812; }
    .action-button.quiet { border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;box-shadow:none;text-decoration:underline;text-underline-offset:3px;font-weight:760; }
    .preview-card, .success-card, .error-card, .note { box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word; }
    .preview-card { margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:var(--ink);line-height:1.45; }
    .success-card { margin-top:12px;border-radius:14px;background:var(--accent-soft);padding:12px;color:var(--accent);line-height:1.45; }
    .error-card { margin-top:12px;border-radius:14px;background:var(--warn-soft);padding:12px;color:var(--warn-ink);line-height:1.45; }
    .affected-review { margin-top:12px;border:3px solid #241812;border-radius:14px;background:#fffdf7;overflow:hidden;box-shadow:3px 3px 0 rgba(36,24,18,.22); }
    .affected-review-header { display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border-bottom:3px solid #241812;background:#fff4d7; }
    .affected-review-table-wrap { overflow:auto;max-height:360px; }
    .affected-review table { width:100%;border-collapse:collapse;font-size:.86rem;line-height:1.35; }
    .affected-review th { padding:8px;text-align:left;background:#f5efe2;color:var(--muted); }
    .affected-review td { padding:9px 8px;vertical-align:top;border-top:1px solid #e2d8c6;overflow-wrap:anywhere; }
    @media (max-width: 1200px) { .layout { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <div class="eyebrow">Simulator</div>
        <h1>Threadwise Inbox Simulator</h1>
        <p>Local-only environment for simulating realistic inbox behavior. This uses copied snapshot data and disables Gmail write-through, so teach/apply flows stay safe while still behaving like the real product.</p>
      </div>
      <div class="hero-actions">
        <button id="sim-refresh" class="button secondary" type="button">Refresh snapshot</button>
        <button id="sim-home" class="button secondary" type="button">Open Home</button>
        <button id="sim-unsynced" class="button primary" type="button">Load unsynced message</button>
      </div>
    </section>
    <section class="layout">
      <section class="card">
        <div class="eyebrow">Inbox List</div>
        <div class="card-title">Simulated Inbox</div>
        <div id="sim-filter-pills" class="label-row"></div>
        <div id="sim-list" class="list-stack"></div>
      </section>
      <section class="card">
        <div class="eyebrow">Reading Pane</div>
        <div id="sim-message"></div>
      </section>
      <section class="panel">
        <header class="header">
          <div class="header-copy">
            <div class="brand-lockup">
              <img class="brand-mark" src="/assets/brand/threadwise-app-icon.png" alt="" aria-hidden="true">
              <div>
                <div class="title">Threadwise</div>
                <div class="brand-kicker">CLEAR THREADS. BETTER INBOX.</div>
              </div>
            </div>
          </div>
          <button id="sim-minimize" class="minimize" type="button">Minimize</button>
        </header>
        <div class="content">
          <div id="sim-workspace"></div>
        </div>
      </section>
    </section>
  </main>
  <script>
    const filterNode = document.getElementById("sim-filter-pills");
    const listNode = document.getElementById("sim-list");
    const messageNode = document.getElementById("sim-message");
    const workspaceNode = document.getElementById("sim-workspace");
    let selectedEmailNode = null;
    let selectedEmailSecondaryNode = null;
    let teachPanelNode = null;
    let dailySummaryNode = null;
    const refreshButton = document.getElementById("sim-refresh");
    const homeButton = document.getElementById("sim-home");
    const unsyncedButton = document.getElementById("sim-unsynced");
    const layoutNode = document.querySelector(".layout");
    const panelNode = document.querySelector('.panel');
    const minimizeButton = document.getElementById('sim-minimize');
    let harnessState = null;
    let currentContext = {};
    let activeFilter = "recent_items";
    let minimized = false;
    let teachPreview = null;
    let previousTeachPreview = null;
    let teachResult = null;
    let teachError = "";
    let teachFlowState = "teaching";
    let inboxApplyConfirmOpen = false;
    let teachOutcome = null;
    let teachWriteThrough = null;
    let unsubscribeResult = "";
    let detailsExpanded = false;
    let autoHandledChangeOpen = false;
    let lastSelectedMessageId = "";
    let affectedReviewOpen = false;
    let applyInFlight = false;
    let lastApplyMode = "";
    let futureLearningSaved = false;
    let draftLabel = "";
    let draftNote = "";
    let selectedDecisionMode = "review";
    let selectedDecisionConflict = "";
    let forceHome = false;
    const unsyncedContext = {
      provider: "gmail",
      message_id: "simulated-unsynced-001",
      subject: "Threadwise has not synced this email yet",
      sender: "new.sender@example.com",
    };

    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function renderWorkspaceShell(mode, selectedState = "") {
      workspaceNode.dataset.eaWorkspaceMode = mode;
      workspaceNode.dataset.eaSelectedState = selectedState;
      if (mode === "home") {
        workspaceNode.innerHTML = `
          <section data-ea-workspace-body="home" class="secondary-card">
            <div class="eyebrow">Home</div>
            <div id="sim-daily-summary"></div>
          </section>
        `;
      } else {
        workspaceNode.innerHTML = `
          <section data-ea-workspace-body="selected-email" class="hero-card">
            <div id="sim-selected-email"></div>
            <div id="sim-teach-panel" class="teach-panel"></div>
            <div id="sim-selected-email-secondary"></div>
          </section>
        `;
      }
      selectedEmailNode = document.getElementById("sim-selected-email");
      selectedEmailSecondaryNode = document.getElementById("sim-selected-email-secondary");
      teachPanelNode = document.getElementById("sim-teach-panel");
      dailySummaryNode = document.getElementById("sim-daily-summary");
    }

    function renderLoadingWorkspace() {
      renderWorkspaceShell("selected-email", "loading");
      selectedEmailNode.innerHTML = `
        <div data-ea-selected-state="loading" aria-live="polite" style="display:grid;gap:12px;margin-top:10px;">
          <div class="subject">Loading Threadwise…</div>
          <div class="preview-card">Refreshing the selected email and its current decision state.</div>
        </div>
      `;
    }

    function humanLabelNameFromId(labelId) {
      if (!labelId) {
        return "Uncategorized";
      }
      const allowedLabels = ((((harnessState || {}).sidebar_state || {}).ui_state || {}).allowed_labels) || [];
      const match = allowedLabels.find((item) => item.id === labelId || item.name === labelId);
      return match ? String(match.name || "").replace(/^EA\\//, "") : String(labelId).replace(/^EA\\//, "");
    }

    function internalLabelId(value) {
      if (!value) {
        return "";
      }
      const allowedLabels = ((((harnessState || {}).sidebar_state || {}).ui_state || {}).allowed_labels) || [];
      const match = allowedLabels.find((item) => item.id === value || item.name === value);
      return match ? String(match.id || "") : "";
    }

    function handledReceiptKind(selected) {
      const status = String((selected || {}).status || "").toLowerCase();
      const details = (selected || {}).details || {};
      const writeStatus = String(details.write_status || "").toLowerCase();
      const inboxStatus = String(details.inbox_status || "").toLowerCase();
      const incomplete = [writeStatus, inboxStatus].some((value) =>
        value && (value.includes("fail") || value.includes("pending") || value.includes("error"))
      );
      if (incomplete) {
        return "";
      }
      if (status === "auto-handled" && writeStatus === "applied" && inboxStatus === "applied") {
        return "auto-handled";
      }
      if (status === "kept-visible" && writeStatus === "applied") {
        return "kept-visible";
      }
      if (status === "auto-labeled") {
        return "auto-labeled";
      }
      return "";
    }

    function labelConflictForDraft() {
      const note = String(draftNote || "").trim().toLowerCase();
      if (!note || !draftLabel) {
        return "";
      }
      const allowedLabels = ((((harnessState || {}).sidebar_state || {}).ui_state || {}).allowed_labels) || [];
      const mentioned = allowedLabels.find((item) => {
        const name = String(item.name || "").replace(/^EA\\//, "").trim().toLowerCase();
        if (!name || item.id === draftLabel) {
          return false;
        }
        const escaped = name.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&");
        return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, "i").test(note);
      });
      if (!mentioned) {
        return "";
      }
      return `Your note sounds like ${humanLabelNameFromId(mentioned.id)}, but ${humanLabelNameFromId(draftLabel)} is selected. Choose which one you mean.`;
    }

    function activeHarnessBucketDescription() {
      return {
        needs_attention_items: "Items still waiting for a confident decision or follow-up.",
        recent_items: "Most recent synced emails across the current local snapshot.",
        auto_handled_items: "Items the agent already handled automatically.",
        kept_visible_items: "Items the agent understood but intentionally left visible.",
      }[activeFilter] || "Current queue slice.";
    }

    function itemsForActiveFilter() {
      return harnessState && Array.isArray(harnessState[activeFilter]) ? harnessState[activeFilter] : [];
    }

    function selectedEmail() {
      return ((harnessState || {}).sidebar_state || {}).selected_email || null;
    }

    function selectedFound() {
      const selected = selectedEmail();
      return !!(selected && selected.found);
    }

    function setContextFromItem(item, clearDraft = true) {
      if (!item) {
        return;
      }
      forceHome = false;
      selectedDecisionMode = "review";
      selectedDecisionConflict = "";
      currentContext = {
        provider: "gmail",
        message_id: item.message_id || "",
        subject: item.subject || "",
        sender: item.sender || "",
      };
      if (clearDraft) {
        resetTeachState(true);
      }
      refreshState();
    }

    function activeBucketLabel() {
      return {
        needs_attention_items: "Needs attention",
        recent_items: "Recent",
        auto_handled_items: "Auto-handled",
        kept_visible_items: "Kept visible",
      }[activeFilter] || "Queue";
    }

    function nextStepCopy(selected) {
      if (!selected || !selected.found) {
        return {
          title: "What to do now",
          body: "Pick a synced queue item below if you want to review or teach the agent before the next sync.",
        };
      }
      if (selected.status === "needs-attention") {
        return {
          title: "What to do now",
          body: "This email still needs a decision. Teach the right label below or leave it visible for later.",
        };
      }
      if (selected.unsubscribe_available) {
        return {
          title: "What to do now",
          body: "The agent already understands this email. If it is recurring, you can queue it for unsubscribe review here.",
        };
      }
      return {
        title: "What to do now",
        body: "The agent has already classified this email. You only need to step in if the label or handling looks wrong.",
      };
    }

    function bucketDescription() {
      return {
        needs_attention_items: "Items still waiting for a confident decision or follow-up.",
        recent_items: "Most recent synced emails across the current local snapshot.",
        auto_handled_items: "Items the agent already handled automatically.",
        kept_visible_items: "Items the agent understood but intentionally left visible.",
      }[activeFilter] || "Current queue slice.";
    }

    function renderQueueCards(items) {
      if (!items.length) {
        return '<div class="empty">No items in this bucket right now.</div>';
      }
      return items.map((item) => `
        <button type="button" class="list-item ${item.message_id === currentContext.message_id ? "active" : ""}" data-queue-message-id="${escapeHtml(item.message_id)}">
          <div class="list-item-subject">${escapeHtml(item.subject || "(no subject)")}</div>
          <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
          <div class="label-row">
            <span class="pill">${escapeHtml(item.classification || "Uncategorized")}</span>
            <span class="pill">${escapeHtml(item.status_label || item.status || "")}</span>
          </div>
        </button>
      `).join("");
    }

    function renderFilterPills() {
      const filters = [
        ["recent_items", `Recent (${((harnessState || {}).recent_items || []).length})`],
        ["auto_handled_items", `Auto-handled (${((harnessState || {}).auto_handled_items || []).length})`],
        ["kept_visible_items", `Kept visible (${((harnessState || {}).kept_visible_items || []).length})`],
      ];
      if (!filters.some(([key]) => key === activeFilter)) {
        activeFilter = "recent_items";
      }
      filterNode.innerHTML = filters.map(([key, label]) => `
        <button type="button" class="chip-button ${key === activeFilter ? "active" : ""}" data-filter="${key}">${escapeHtml(label)}</button>
      `).join("");
    }

    function renderInboxList() {
      const items = itemsForActiveFilter();
      if (!items.length) {
        listNode.innerHTML = '<div class="empty">No items in this simulator bucket right now.</div>';
        return;
      }
      listNode.innerHTML = renderQueueCards(items);
    }

    function renderReadingPane() {
      const selected = selectedEmail();
      const understandingState = String((selected || {}).understanding_state || "ready");
      const understandingActive = understandingState === "reading" || understandingState === "understanding";
      if (understandingActive) {
        messageNode.innerHTML = `
          <div class="message-title">${escapeHtml((selected && selected.subject) || currentContext.subject || "Current email")}</div>
          <div class="message-meta">${escapeHtml((selected && selected.sender) || currentContext.sender || "unknown sender")}</div>
          <div class="message-body">${escapeHtml((selected && selected.understanding_message) || "Understanding this email...")}</div>
          <div class="note">Threadwise is updating the current email view before showing the full judgment.</div>
        `;
        return;
      }
      if (!selected || !selected.found) {
        messageNode.innerHTML = `
          <div class="message-title">${escapeHtml(currentContext.subject || "Unsynced email")}</div>
          <div class="message-meta">${escapeHtml(currentContext.sender || "unknown sender")}</div>
          <div class="message-body">Threadwise has not synced this email yet.\n\nUse this state to test how the companion explains a fresh Gmail message before the next Threadwise check.</div>
          <div class="note">Expected behavior: the companion should explain what to do next while still offering already-synced emails as a fallback.</div>
        `;
        return;
      }
      messageNode.innerHTML = `
        <div class="message-title">${escapeHtml(selected.subject || "(no subject)")}</div>
        <div class="message-meta">${escapeHtml(selected.sender || "(unknown sender)")}</div>
        <div class="label-row">
          <span class="pill">${escapeHtml(selected.classification || "Uncategorized")}</span>
          <span class="pill">${escapeHtml(selected.status_label || "")}</span>
          ${selected.unsubscribe_available ? '<span class="pill">Unsubscribe available</span>' : ""}
        </div>
        <div class="message-body">${escapeHtml(selected.reason || "No stored explanation available yet.")}</div>
        <div class="note">This middle pane simulates what the user is reading while the companion stays anchored to the selected email on the right.</div>
      `;
    }

    function renderPreviousTeachPreview(previousPreview) {
      if (!previousPreview) {
        return "";
      }
      const impact = previousPreview.impact || {};
      return `
        <div class="note" data-previous-preview="true">
          <div class="reason-label">Previous interpretation</div>
          <div style="margin-top:8px;color:var(--ink);line-height:1.45;font-weight:700;">${escapeHtml(previousPreview.acknowledgment || "Previous preview")}</div>
          <div style="margin-top:6px;color:var(--muted);line-height:1.45;">Matching existing emails: ${impact.matching_existing_count || 0}</div>
        </div>
      `;
    }

    function renderTeachPreview(preview) {
      const impact = preview.impact || {};
      const matchingCount = impact.matching_existing_count || 0;
      const examples = (impact.matching_existing_examples || []).map((item) =>
        `<li>${escapeHtml(item.subject || "(no subject)")} · ${escapeHtml(item.sender || "(unknown sender)")}</li>`
      ).join("");
      const ruleMeta = `
        <div class="pill-row">
          <span class="pill">${escapeHtml(preview.rule_type_label || "Future rule")}</span>
          <span class="pill ${preview.rule_confidence === "tentative" ? "warn-pill" : "status-pill"}">${escapeHtml(preview.rule_confidence_label || "Future rule")}</span>
        </div>
        ${preview.clarifying_question ? `<div class="empty">${escapeHtml(preview.clarifying_question)}</div>` : ""}
      `;
      const affectedReviewHtml = renderAffectedReview(preview);
      return `
        <div class="preview-card">
          <div class="reason-label">This email</div>
          <div style="font-weight:700;margin-top:6px;">${escapeHtml(preview.acknowledgment || "Preview ready.")}</div>
          <div class="empty" style="margin-top:8px;">Fix this email only updates the message you are reviewing.</div>
          <div class="button-row" style="margin-top:12px;">
            <button type="button" class="action-button primary" data-apply-mode="current-only">Fix this email</button>
          </div>
          <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;">
            <div class="reason-label">Future rule</div>
            <div style="font-weight:700;margin-top:6px;">${escapeHtml(preview.plain_english_rule || "No future rule proposal was generated.")}</div>
            ${ruleMeta}
            <details class="empty" style="margin-top:8px;">
              <summary style="cursor:pointer;font-weight:800;color:#241812;">Structured rule</summary>
              <div style="margin-top:8px;">Hidden until needed.</div>
            </details>
          </div>
          ${renderRuleAmendment(preview.amendment_proposal)}
          <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;">
            <div class="reason-label">Affected existing emails</div>
            <div class="empty" style="margin-top:6px;">Would affect ${matchingCount} matching emails Threadwise has seen.</div>
            ${examples ? `<details style="margin-top:8px;"><summary style="cursor:pointer;font-weight:800;">Show affected emails</summary><ol style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${examples}</ol></details>` : ""}
            <div class="button-row" style="margin-top:10px;">
              <button type="button" class="action-button future" data-action="open-affected-review">Review ${matchingCount}</button>
              ${affectedReviewOpen ? '<button type="button" class="action-button info" data-apply-mode="apply-included">Apply to included</button>' : ""}
            </div>
          </div>
          ${affectedReviewHtml}
          <div class="button-row" style="margin-top:10px;">
            <button type="button" class="action-button future" data-apply-mode="save-future-rule">Teach future rule</button>
            <button type="button" class="action-button secondary" data-action="refine-teach">Keep discussing</button>
          </div>
        </div>
      `;
    }

    function affectedReviewItems(preview) {
      const impact = ((preview || {}).impact) || {};
      return impact.matching_existing_items || impact.matching_existing_examples || [];
    }

    function renderRuleAmendment(amendment) {
      if (!amendment || !amendment.status || amendment.status === "accepted" || amendment.status === "rejected") {
        return "";
      }
      const proposedRule = amendment.plain_english_rule || amendment.clarifying_question || "Threadwise needs a clearer boundary before changing the rule.";
      const actions = amendment.status === "proposed"
        ? `
          <div class="button-row" style="margin-top:10px;">
            <button type="button" class="action-button primary" data-amendment-decision="accept">Accept amendment</button>
            <button type="button" class="action-button secondary" data-amendment-decision="reject">Reject</button>
            <button type="button" class="action-button quiet" data-action="refine-teach">Keep reviewing</button>
          </div>
        `
        : "";
      return `
        <div class="reason-wrap" style="background:#eef7f5;">
          <div class="reason-label">Possible rule amendment</div>
          <div class="reason" style="font-weight:800;">${escapeHtml(proposedRule)}</div>
          ${amendment.plain_english_rule && amendment.clarifying_question ? `<div class="empty">${escapeHtml(amendment.clarifying_question)}</div>` : ""}
          <div class="empty">This is only a proposal. Threadwise will not change the rule unless you accept it.</div>
          ${actions}
        </div>
      `;
    }

    function renderAffectedReview(preview) {
      if (!affectedReviewOpen || !preview) {
        return "";
      }
      const rows = affectedReviewItems(preview).map((item) => `
        <tr>
          <td><strong>${escapeHtml(item.sender || "(unknown sender)")}</strong></td>
          <td>${escapeHtml(item.subject || "(no subject)")}</td>
          <td style="color:var(--muted);">${escapeHtml((item.labels_before || []).join(", ") || "Uncategorized")}</td>
          <td style="color:var(--accent);font-weight:800;">${escapeHtml((item.labels_after || []).join(", ") || "Uncategorized")}</td>
          <td>
            <div style="display:grid;gap:6px;">
              <button type="button" class="action-button quiet" data-affected-open-gmail="${escapeHtml(item.message_id || "")}">Open in Gmail</button>
              <button type="button" class="action-button secondary" data-affected-exclude="${escapeHtml(item.message_id || "")}">Exclude</button>
              <details class="empty" style="margin:0;">
                <summary style="cursor:pointer;">Why?</summary>
                <textarea class="textarea" data-affected-exclusion-reason="${escapeHtml(item.message_id || "")}" placeholder="Optional reason" style="min-height:54px;margin-top:6px;"></textarea>
              </details>
            </div>
          </td>
        </tr>
      `).join("") || '<tr><td colspan="5" style="color:var(--muted);">No exact affected emails are available in this preview.</td></tr>';
      return `
        <div class="affected-review">
          <div class="affected-review-header">
            <div>
              <div class="reason-label">Reviewing affected emails</div>
              <div style="font-weight:850;margin-top:4px;">${escapeHtml(preview.plain_english_rule || "Pending future rule")}</div>
            </div>
            <button type="button" class="action-button secondary" data-action="collapse-affected-review">Collapse</button>
          </div>
          <div class="empty" style="padding:12px 14px;">Exact affected list from Threadwise's preview. Excluding a row saves an exact exception for this rule/email.</div>
          <div class="affected-review-table-wrap">
            <table>
              <thead><tr><th>Sender</th><th>Subject</th><th>Current</th><th>Proposed</th><th>Inspect</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>
      `;
    }

    function syncAffectedReviewLayout() {
      if (layoutNode) {
        layoutNode.classList.toggle("expanded-review", affectedReviewOpen);
      }
    }

    function renderTeachError(message) {
      return `
        <div class="error-card">
          <div style="font-weight:800;">Lesson not applied</div>
          <div style="margin-top:8px;">${escapeHtml(message || "Nothing was stored or changed. The preview is still here so you can check the connection and retry without rewriting your note.")}</div>
          <div class="button-row" style="margin-top:12px;">
            <button type="button" class="action-button future" data-action="refresh-state">Check again</button>
            <button type="button" class="action-button primary" data-apply-mode="current-only">Try fix again</button>
          </div>
        </div>
      `;
    }

    function renderTeachReceipt() {
      if (!teachResult) {
        return "";
      }
      const outcome = teachOutcome || {};
      const rows = [
        ["This email", outcome.current_email_changed_locally ? "done" : "not changed"],
        ["Gmail label", outcome.current_email_written_to_gmail ? "done" : "not confirmed"],
        ["Other stored emails", (outcome.matching_existing_changed_locally || 0) > 0 ? `${outcome.matching_existing_changed_locally} changed` : "not changed"],
        ["Future rule", outcome.future_rule_saved ? "saved" : "not saved"],
      ];
      return `
        <div class="success-card" data-teach-state="result">
          <div style="font-weight:800;">Rule applied</div>
          <div style="margin-top:8px;">${escapeHtml(teachResult)}</div>
          <div class="reason-wrap" style="margin-top:12px;background:#fffdfa;">
            <div class="reason-label">What changed</div>
            <div class="detail-list">${rows.map(([label, value]) => `
              <div class="list-item" style="cursor:default;">
                <div class="list-item-subject">${escapeHtml(label)}</div>
                <div class="list-item-meta">${escapeHtml(value)}</div>
              </div>
            `).join("")}</div>
          </div>
        </div>
      `;
    }

    function renderTeachProposal(preview) {
      return `
        <div class="preview-card" data-teach-state="rule-proposed">
          <div class="reason-label">Proposed rule:</div>
          <div class="reason" style="font-weight:800;">${escapeHtml(preview.plain_english_rule || "No rule proposed.")}</div>
          <div class="button-row" style="margin-top:12px;">
            <button type="button" class="action-button primary" data-action="accept-teach-rule">Looks right</button>
            <button type="button" class="action-button secondary" data-action="refine-teach">Edit</button>
          </div>
        </div>
      `;
    }

    function renderTeachScope(preview) {
      const backfill = preview.inbox_backfill || {};
      return `
        <div class="preview-card" data-teach-state="${teachFlowState}">
          <div class="reason-label">Accepted rule</div>
          <div class="reason" style="font-weight:800;">${escapeHtml(preview.plain_english_rule || "No rule proposed.")}</div>
          <div class="empty">Choose how broadly to apply this rule.</div>
          <div class="button-row" style="margin-top:12px;">
            <button type="button" class="action-button primary" data-apply-mode="current-only">Fix email</button>
            <button type="button" class="action-button secondary" data-apply-mode="future-only">Fix + future</button>
            <button type="button" class="action-button info" data-apply-mode="apply-included">Fix + inbox</button>
          </div>
          <div class="empty">Fix email applies only to this email. Fix + future also saves the rule. Fix + inbox also applies it to matching inbox emails.</div>
          ${backfill.available ? `<div class="empty">Will update about ${escapeHtml(String(backfill.estimated_count || 0))} matching inbox emails.</div>` : ""}
          ${inboxApplyConfirmOpen ? `
            <div class="error-card">
              <div style="font-weight:800;">Apply to inbox?</div>
              <div style="margin-top:8px;">Will update about ${escapeHtml(String(backfill.estimated_count || 0))} matching inbox emails.</div>
              <div class="button-row" style="margin-top:12px;">
                <button type="button" class="action-button info" data-action="confirm-inbox-apply">Apply to inbox</button>
                <button type="button" class="action-button quiet" data-action="cancel-inbox-apply">Cancel</button>
              </div>
            </div>
          ` : ""}
        </div>
      `;
    }

    function renderTeachComposer(labelOptions) {
      return `
        <div class="field-stack" data-teach-state="${teachFlowState === "refining" ? "refining" : "teaching"}">
          ${teachFlowState === "refining" ? '<div class="empty">You are refining this lesson.</div>' : ""}
          <textarea id="sim-teach-note" class="textarea" placeholder="What should Threadwise understand?">${escapeHtml(draftNote)}</textarea>
          <details class="empty" style="margin-top:0;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Choose label manually</summary>
            <select id="sim-target-label" class="select" style="margin-top:8px;">
              <option value="">Infer from note</option>
              ${labelOptions}
            </select>
          </details>
          <div class="button-row">
            <button type="button" class="action-button primary" data-action="preview-teach">Propose rule</button>
            <button type="button" class="action-button quiet" data-action="clear-teach">Clear draft</button>
          </div>
        </div>
      `;
    }

    function renderSelectedPanel() {
      const selected = selectedEmail();
      const stepCopy = nextStepCopy(selected);
      const selectedMessageId = selected && selected.found ? String(selected.message_id || "") : "";
      if (selectedMessageId !== lastSelectedMessageId) {
        lastSelectedMessageId = selectedMessageId;
        selectedDecisionMode = "review";
        selectedDecisionConflict = "";
        autoHandledChangeOpen = false;
        detailsExpanded = false;
        futureLearningSaved = false;
        if (teachFlowState === "result" && teachOutcome && teachOutcome.scope === "current-email") {
          teachFlowState = "teaching";
          teachResult = null;
          teachOutcome = null;
          teachWriteThrough = null;
          draftLabel = "";
          draftNote = "";
        }
      }

      if (forceHome) {
        renderWorkspaceShell("home", "home");
        return;
      }

      const hasSelectedContext = Boolean(
        currentContext.message_id || currentContext.subject || currentContext.sender
      );
      if ((!selected || !selected.found) && !hasSelectedContext) {
        renderWorkspaceShell("home", "home");
        return;
      }

      const understandingActive = Boolean(
        selected && ["reading", "understanding"].includes(selected.understanding_state)
      );
      const handledKind = handledReceiptKind(selected);
      const decisionState = selectedDecisionMode === "future-learning"
        ? teachFlowState === "applying"
          ? "applying"
          : teachFlowState === "apply-error"
            ? "blocked"
            : futureLearningSaved
              ? "receipt"
              : "future-learning"
        : selectedDecisionMode === "preview" && teachFlowState === "applying"
          ? "applying"
          : selectedDecisionMode === "preview" && teachFlowState === "apply-error"
            ? "blocked"
            : selectedDecisionMode;
      const selectedState = understandingActive
        ? "understanding"
        : (!selected || !selected.found)
          ? "blocked"
          : selected.status === "needs-attention"
            ? decisionState
            : handledKind && !autoHandledChangeOpen
              ? "receipt"
              : handledKind
                ? "change"
                : "blocked";
      renderWorkspaceShell("selected-email", selectedState);

      if (understandingActive) {
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="understanding" style="display:grid;gap:12px;margin-top:10px;">
            <div class="subject">${escapeHtml(selected.subject || currentContext.subject || "(no subject)")}</div>
            <div class="sender">${escapeHtml(selected.sender || currentContext.sender || "(unknown sender)")}</div>
            <div class="preview-card" aria-live="polite">
              <div class="reason-label">${escapeHtml(selected.understanding_label || "Understanding")}</div>
              <div class="reason">${escapeHtml(selected.understanding_message || "Understanding this email...")}</div>
            </div>
          </div>
        `;
        return;
      }

      if (!selected || !selected.found) {
        affectedReviewOpen = false;
        syncAffectedReviewLayout();
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="blocked" style="display:grid;gap:12px;margin-top:10px;">
          <div class="empty">Threadwise has not synced this email yet.</div>
          <div class="error-card">${escapeHtml(selected && selected.reason ? selected.reason : "This simulated fresh email lets you test the pre-sync state safely.")}</div>
          <div class="reason-wrap">
            <div class="reason-label">${escapeHtml(stepCopy.title)}</div>
            <div class="reason">${escapeHtml(stepCopy.body)}</div>
          </div>
          <div class="button-row" style="margin-top:12px;">
            <button type="button" class="action-button future" data-action="return-to-fixture-list" data-tw-primary-action>Return to fixture list</button>
          </div>
          </div>
        `;
        return;
      }

      const allowedLabels = ((((harnessState || {}).sidebar_state || {}).ui_state || {}).allowed_labels) || [];
      const defaultLabel = internalLabelId(draftLabel)
        || internalLabelId(selected.internal_label)
        || internalLabelId(selected.suggested_label)
        || internalLabelId(selected.classification);
      const labelOptions = allowedLabels.map((option) => {
        const selectedAttr = defaultLabel === option.id ? " selected" : "";
        return `<option value="${escapeHtml(option.id)}"${selectedAttr}>${escapeHtml(option.name)}</option>`;
      }).join("");

      if (selectedDecisionMode === "future-learning" && teachOutcome && teachOutcome.scope === "current-email" && teachOutcome.current_email_written_to_gmail) {
        const label = humanLabelNameFromId(draftLabel || selected.internal_label || selected.classification || "");
        if (teachFlowState === "applying") {
          selectedEmailNode.innerHTML = `
            <div data-ea-selected-state="applying" aria-live="polite" style="display:grid;gap:12px;margin-top:10px;">
              <div class="subject">Saving future rule</div>
              <div class="preview-card">Creating a reviewable learning candidate without changing Gmail…</div>
            </div>
          `;
          return;
        }
        if (teachFlowState === "apply-error") {
          selectedEmailNode.innerHTML = `
            <div data-ea-selected-state="blocked" style="display:grid;gap:12px;margin-top:10px;">
              <div class="subject">Couldn’t save the future rule</div>
              <div class="error-card">${escapeHtml(teachError || "The learning candidate was not saved.")}</div>
              <button type="button" class="action-button primary" data-action="retry-future-learning" data-tw-primary-action>Try save again</button>
              <button type="button" class="action-button quiet" data-action="back-to-current-receipt">Not now</button>
            </div>
          `;
          return;
        }
        if (futureLearningSaved) {
          selectedEmailNode.innerHTML = `
            <div data-ea-selected-state="receipt" style="display:grid;gap:12px;margin-top:10px;">
              <div class="subject">Future rule saved for review</div>
              <div class="success-card">Saved as a learning candidate. No Gmail messages were changed.</div>
              <button type="button" class="action-button quiet" data-action="back-to-current-receipt">Not now</button>
            </div>
          `;
          return;
        }
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="future-learning" style="display:grid;gap:12px;margin-top:10px;">
            <div class="eyebrow">Optional follow-up</div>
            <div data-ea-preview-heading class="subject">Teach future emails</div>
            <div class="preview-card">The current email is already changed to ${escapeHtml(label)}. Any lesson you create here applies to future emails only.</div>
            <label class="field-stack">What should Threadwise remember?
              <textarea id="sim-future-note" class="textarea" placeholder="Describe which future emails should be ${escapeHtml(label)}">${escapeHtml(draftNote)}</textarea>
            </label>
            <button type="button" class="action-button primary" data-action="save-future-learning" data-tw-primary-action>Save future rule</button>
            <button type="button" class="action-button quiet" data-action="back-to-current-receipt">Not now</button>
          </div>
        `;
        return;
      }

      if (teachFlowState === "result" && teachOutcome && teachOutcome.scope === "current-email" && teachOutcome.current_email_written_to_gmail) {
        const label = humanLabelNameFromId(draftLabel || selected.internal_label || selected.classification || "");
        const inboxFailed = Number((teachWriteThrough || {}).inbox_remove_failed || 0) > 0;
        const inboxRemoved = Number((teachWriteThrough || {}).inbox_removed || 0) > 0;
        const needsReviewCount = Number(((((harnessState || {}).sidebar_state || {}).daily_summary || {}).needs_attention_count) || 0);
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="receipt" style="display:grid;gap:12px;margin-top:10px;">
            <div data-ea-receipt-heading class="subject">Changed to ${escapeHtml(label)}</div>
            <div class="sender">${escapeHtml(selected.subject || "(no subject)")}</div>
            <div class="success-card" style="display:grid;gap:8px;">
              <div data-ea-receipt-outcome>Gmail label updated.</div>
              <div data-ea-receipt-outcome>${inboxFailed ? "Inbox removal needs attention. Open Activity for details." : inboxRemoved ? "Removed from Inbox." : "Kept in Inbox."}</div>
            </div>
            ${inboxFailed ? '<a class="action-button quiet" data-ea-partial-recovery href="/daily-dashboard" target="_blank" rel="noreferrer">Open Activity</a>' : ""}
            ${needsReviewCount > 0 && !inboxFailed ? '<button type="button" class="action-button primary" data-action="open-needs-attention" data-tw-primary-action>Next email</button>' : ""}
            ${!inboxFailed ? '<button type="button" class="action-button quiet" data-action="teach-future-after-receipt">Teach Threadwise for future emails</button>' : ""}
          </div>
        `;
        return;
      }

      if (handledKind && !autoHandledChangeOpen) {
        const label = humanLabelNameFromId(selected.internal_label || selected.classification || "");
        const heading = handledKind === "auto-handled"
          ? `${label} · Auto-handled`
          : handledKind === "auto-labeled"
            ? `${label} · Auto-labeled`
            : `Labeled ${label}`;
        const receipt = handledKind === "auto-handled"
          ? "Gmail label applied. Removed from Inbox."
          : handledKind === "auto-labeled"
            ? "Threadwise classified this email and kept it visible. Gmail label not confirmed."
            : "Gmail label applied. Kept in Inbox.";
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="receipt" data-ea-handled-kind="${escapeHtml(handledKind)}" style="display:grid;gap:12px;margin-top:10px;">
            <div data-ea-auto-handled-heading class="subject">${escapeHtml(heading)}</div>
            <div class="sender">${escapeHtml(selected.subject || "(no subject)")} · ${escapeHtml(selected.sender || "(unknown sender)")}</div>
            <div data-ea-auto-handled-receipt class="success-card">${escapeHtml(receipt)}</div>
            <div class="button-row">
              <button type="button" class="action-button quiet" data-action="change-auto-handled">Change</button>
              <button type="button" class="action-button quiet" data-action="toggle-details">Why</button>
            </div>
          </div>
        `;
        selectedEmailSecondaryNode.innerHTML = detailsExpanded
          ? `<div class="preview-card">${escapeHtml(selected.reason || "No reason recorded.")}</div>`
          : "";
        return;
      }

      if (selected.status !== "needs-attention" && !handledKind) {
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="blocked" style="display:grid;gap:12px;margin-top:10px;">
            <div class="subject">Handling is not complete</div>
            <div class="sender">${escapeHtml(selected.subject || "(no subject)")}</div>
            <div class="error-card">Threadwise has not recorded a completed label and inbox action for this fixture.</div>
            <a class="action-button quiet" href="/daily-dashboard" target="_blank" rel="noreferrer">Open Activity for details</a>
          </div>
        `;
        return;
      }

      if (selected.status === "needs-attention" && selectedDecisionMode === "review") {
        const labelId = internalLabelId(selected.internal_label)
          || internalLabelId(selected.suggested_label)
          || internalLabelId(draftLabel)
          || internalLabelId(selected.classification);
        const label = humanLabelNameFromId(labelId || selected.classification || "");
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="review" style="display:grid;gap:12px;margin-top:10px;">
            <div class="eyebrow">Needs your review</div>
            <div class="subject">${escapeHtml(selected.subject || "(no subject)")}</div>
            <div class="sender">${escapeHtml(selected.sender || "(unknown sender)")}</div>
            <div data-ea-review-suggestion class="agent-copy">${labelId ? `Threadwise suggests ${escapeHtml(label)}` : "Threadwise needs a label"}</div>
            <div class="preview-card">${escapeHtml(String(selected.reason || stepCopy.body || "").slice(0, 160))}</div>
            ${labelId ? `<button type="button" class="action-button primary" data-action="accept-suggestion" data-tw-primary-action>Accept ${escapeHtml(label)}</button>` : ""}
            <button type="button" class="action-button secondary" data-action="change-suggestion">Change label</button>
          </div>
        `;
        return;
      }

      if (selected.status === "needs-attention" && selectedDecisionMode === "change") {
        const placeholder = defaultLabel ? "" : '<option value="" selected disabled>Choose a label</option>';
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="change" style="display:grid;gap:12px;margin-top:10px;">
            <div class="subject">What should this email be?</div>
            <div class="sender">${escapeHtml(selected.subject || "(no subject)")}</div>
            <label class="field-stack">Label
              <select id="sim-target-label" class="select">${placeholder}${labelOptions}</select>
            </label>
            <label class="field-stack">Anything Threadwise should remember? (optional)
              <textarea id="sim-teach-note" class="textarea">${escapeHtml(draftNote)}</textarea>
            </label>
            ${selectedDecisionConflict ? `<div data-ea-label-conflict class="error-card">${escapeHtml(selectedDecisionConflict)}</div>` : ""}
            <button type="button" class="action-button primary" data-action="preview-current-change" data-tw-primary-action ${defaultLabel ? "" : "disabled"}>Preview change</button>
            <button type="button" class="action-button quiet" data-action="cancel-current-change">Cancel</button>
          </div>
        `;
        bindDraftInputs();
        return;
      }

      if (selected.status === "needs-attention" && selectedDecisionMode === "preview" && teachFlowState === "apply-error") {
        const label = humanLabelNameFromId(draftLabel || defaultLabel);
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="blocked" style="display:grid;gap:12px;margin-top:10px;">
            <div data-ea-preview-heading class="subject">Couldn’t apply ${escapeHtml(label)}</div>
            <div class="error-card">${escapeHtml(teachError || "Nothing was stored or changed. The preview is still here so you can retry.")}</div>
            <button type="button" class="action-button primary" data-action="retry-current-change" data-tw-primary-action>Try fix again</button>
            <button type="button" class="action-button quiet" data-action="edit-current-change">Edit</button>
          </div>
        `;
        return;
      }

      if (selected.status === "needs-attention" && selectedDecisionMode === "preview" && teachFlowState === "applying") {
        const label = humanLabelNameFromId(draftLabel || defaultLabel);
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="applying" aria-live="polite" style="display:grid;gap:12px;margin-top:10px;">
            <div data-ea-preview-heading class="subject">Applying ${escapeHtml(label)}</div>
            <div data-ea-preview-effect class="preview-card">Updating the current email only…</div>
          </div>
        `;
        return;
      }

      if (selected.status === "needs-attention" && selectedDecisionMode === "preview") {
        const label = humanLabelNameFromId(draftLabel || defaultLabel);
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="preview" style="display:grid;gap:12px;margin-top:10px;">
            <div data-ea-preview-heading class="subject">Change this email to ${escapeHtml(label)}</div>
            <div data-ea-preview-effect class="preview-card">This updates the current email only.</div>
            <button type="button" class="action-button primary" data-apply-mode="current-only" data-tw-primary-action>Apply change</button>
            <button type="button" class="action-button quiet" data-action="edit-current-change">Edit</button>
          </div>
        `;
        return;
      }

      if (teachFlowState === "apply-error") {
        renderWorkspaceShell("selected-email", "blocked");
        selectedEmailNode.innerHTML = `
          <div data-ea-selected-state="blocked" style="display:grid;gap:12px;margin-top:10px;">
            <div class="subject">Couldn’t complete the simulated update</div>
            <div class="error-card">${escapeHtml(teachError || "Nothing was stored or changed.")}</div>
            <button type="button" class="action-button primary" data-action="retry-broad-apply" data-tw-primary-action>Try again</button>
            <button type="button" class="action-button quiet" data-action="refine-teach">Edit</button>
          </div>
        `;
        return;
      }

      const unsubscribe = selected.unsubscribe || null;
      const unsubscribePreview = (unsubscribe && unsubscribe.preview) || null;
      const canOpenUnsubscribeUrl = unsubscribePreview
        && unsubscribePreview.url
        && unsubscribePreview.status !== "ready"
        && unsubscribePreview.url.startsWith("mailto:");
      const details = selected.details || {};
      const matchedRuleList = (details.matched_rule_ids || []).length
        ? `<div class="empty">Matched rules: ${escapeHtml((details.matched_rule_ids || []).join(', '))}</div>`
        : "";
      const allClassifications = Array.isArray(selected.all_classifications) ? selected.all_classifications : [];
      const allLabelsList = allClassifications.length > 1
        ? `<div class="empty">All labels: ${escapeHtml(allClassifications.join(", "))}</div>`
        : "";
      const unsubscribeReasonList = (details.unsubscribe_reasons || []).length
        ? `<div class="empty">Unsubscribe qualified because: ${escapeHtml((details.unsubscribe_reasons || []).join(', '))}</div>`
        : "";
      const unsubscribeActions = unsubscribePreview
        ? `
          <div class="button-row" style="margin-top:10px;">
            ${unsubscribePreview.status === "ready" && !unsubscribeResult ? '<button type="button" class="action-button info" data-action="select-unsubscribe">Queue unsubscribe</button>' : ''}
            ${canOpenUnsubscribeUrl ? `<a class="action-button quiet" style="display:inline-flex;align-items:center;" href="${escapeHtml(unsubscribePreview.url)}">Open mail unsubscribe</a>` : ''}
            ${unsubscribe ? `<a class="action-button quiet" style="display:inline-flex;align-items:center;" href="${escapeHtml(unsubscribe.handoff_path || '/unsubscribe-review')}" target="_blank" rel="noreferrer">Review all subscriptions</a>` : ''}
          </div>
        `
        : "";
      const unsubscribeLine = unsubscribe
        ? `
          <div class="reason-wrap">
            <div class="reason-label">Unsubscribe</div>
            <div class="reason">${escapeHtml(unsubscribe.display_name || selected.sender || "Subscription")}</div>
            <div class="empty">${escapeHtml((unsubscribePreview && unsubscribePreview.notes) || "Unsubscribe available")}</div>
            ${unsubscribeResult ? `<div class="success-card">${escapeHtml(unsubscribeResult)}</div>` : ""}
            ${unsubscribeActions}
          </div>
        `
        : "";
      const errorHtml = teachError ? renderTeachError(teachError) : "";
      let flowHtml = renderTeachComposer(labelOptions);
      if (teachFlowState === "rule-proposed" && teachPreview) {
        flowHtml = renderTeachProposal(teachPreview);
      } else if ((teachFlowState === "scope-confirmation" || teachFlowState === "applying") && teachPreview) {
        flowHtml = renderTeachScope(teachPreview);
      } else if (teachFlowState === "result") {
        flowHtml = renderTeachReceipt();
      }
      const feedbackHtml = `${errorHtml}${renderPreviousTeachPreview(previousTeachPreview)}${flowHtml}`;
      selectedEmailNode.innerHTML = `
        <div class="subject">${escapeHtml(selected.subject || "(no subject)")}</div>
        <div class="sender">${escapeHtml(selected.sender || "(unknown sender)")}</div>
        <div class="agent-copy">${escapeHtml(selected.reason || stepCopy.body || "Threadwise reviewed this email and kept the decision visible for approval.")}</div>
        <div class="pill-row">
          <span class="pill classification-pill">${escapeHtml(selected.classification || "Uncategorized")}</span>
          <span class="pill ${selected.status === "needs-attention" ? "warn-pill" : "status-pill"}">${escapeHtml(selected.status_label || "")}</span>
        </div>
        ${allLabelsList}
        ${unsubscribeLine}
      `;
      teachPanelNode.innerHTML = feedbackHtml;
      const labelNode = document.getElementById("sim-target-label");
      const noteNode = document.getElementById("sim-teach-note");
      if (labelNode) {
        labelNode.addEventListener("change", () => {
          draftLabel = labelNode.value;
          const previewButton = document.querySelector('[data-action="preview-current-change"]');
          if (previewButton) {
            previewButton.disabled = !internalLabelId(draftLabel);
          }
        });
      }
      if (noteNode) {
        noteNode.addEventListener("input", () => {
          draftNote = noteNode.value;
        });
      }
      syncAffectedReviewLayout();
    }

    function bindDraftInputs() {
      const labelNode = document.getElementById("sim-target-label");
      const noteNode = document.getElementById("sim-teach-note");
      if (labelNode) {
        labelNode.addEventListener("change", () => {
          draftLabel = labelNode.value;
          const previewButton = document.querySelector('[data-action="preview-current-change"]');
          if (previewButton) {
            previewButton.disabled = !internalLabelId(draftLabel);
          }
        });
      }
      if (noteNode) {
        noteNode.addEventListener("input", () => {
          draftNote = noteNode.value;
        });
      }
    }

    function renderSummary() {
      if (!dailySummaryNode) {
        return;
      }
      const summary = (((harnessState || {}).sidebar_state) || {}).daily_summary || {};
      const needsReviewCount = Number(summary.needs_attention_count || 0);
      const keptVisibleCount = Number(
        summary.kept_visible_count
        ?? (((harnessState || {}).kept_visible_items || []).length)
      );
      dailySummaryNode.innerHTML = `
        <div data-ea-selected-state="home" style="display:grid;gap:12px;margin-top:10px;">
          <div class="subject">${needsReviewCount ? `${needsReviewCount} email${needsReviewCount === 1 ? "" : "s"} need your review` : "Your inbox is caught up"}</div>
          <div class="empty">${Number(summary.processed_count || 0)} processed · ${Number(summary.auto_handled_count || 0)} auto-handled · ${keptVisibleCount} kept visible</div>
          ${needsReviewCount ? '<button type="button" class="action-button primary" data-action="open-needs-attention" data-tw-primary-action>Review next</button>' : ""}
          <div class="button-row">
            <a class="action-button quiet" href="/daily-dashboard" target="_blank" rel="noreferrer">Activity</a>
            <a class="action-button quiet" href="/unsubscribe-review" target="_blank" rel="noreferrer">Subscription cleanup</a>
          </div>
        </div>
      `;
    }

    async function postApi(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return response.json();
    }

    async function refreshState() {
      if (!forceHome) {
        renderLoadingWorkspace();
      }
      const query = new URLSearchParams(currentContext);
      const response = await fetch(`/api/harness-state?${query.toString()}`);
      harnessState = await response.json();
      currentContext = harnessState.selected_context || currentContext;
      const selected = selectedEmail();
      if (selected && selected.found && !draftLabel) {
        draftLabel = internalLabelId(selected.internal_label)
          || internalLabelId(selected.suggested_label)
          || internalLabelId(selected.classification);
      }
      if (!(selected && selected.found)) {
        previousTeachPreview = null;
        unsubscribeResult = "";
      }
      renderFilterPills();
      renderInboxList();
      renderReadingPane();
      renderSelectedPanel();
      renderSummary();
    }

    function resetTeachState(clearDraft) {
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = null;
      teachError = "";
      teachFlowState = "teaching";
      inboxApplyConfirmOpen = false;
      teachOutcome = null;
      teachWriteThrough = null;
      unsubscribeResult = "";
      affectedReviewOpen = false;
      selectedDecisionMode = "review";
      selectedDecisionConflict = "";
      autoHandledChangeOpen = false;
      futureLearningSaved = false;
      lastApplyMode = "";
      syncAffectedReviewLayout();
      if (clearDraft) {
        draftLabel = "";
        draftNote = "";
      }
    }

    async function previewTeach() {
      if (!selectedFound()) {
        return;
      }
      const labelNode = document.getElementById("sim-target-label");
      const noteNode = document.getElementById("sim-teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      const payload = await postApi("/api/teach-preview", {
        selected_context: currentContext,
        target_label: draftLabel,
        note: draftNote,
        scope: "sender",
      });
      if (payload.error) {
        teachError = payload.error;
        teachResult = null;
      } else {
        teachError = "";
        teachResult = null;
        teachPreview = payload;
        teachFlowState = "rule-proposed";
        unsubscribeResult = "";
      }
      renderSelectedPanel();
    }

    async function applyTeach(mode) {
      if (!selectedFound() || applyInFlight) {
        return;
      }
      applyInFlight = true;
      lastApplyMode = mode;
      const labelNode = document.getElementById("sim-target-label");
      const noteNode = document.getElementById("sim-teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      teachError = "";
      teachFlowState = "applying";
      renderSelectedPanel();
      try {
        const payload = await postApi("/api/teach-apply", {
          selected_context: currentContext,
          target_label: draftLabel,
          note: draftNote,
          scope: "sender",
          mode,
        });
        if (payload.error) {
          throw new Error(payload.error);
        }
        teachPreview = null;
        previousTeachPreview = null;
        teachError = "";
        teachResult = payload.acknowledgment || "Lesson applied.";
        if (mode === "save-future-rule") {
          futureLearningSaved = true;
        } else {
          teachOutcome = payload.outcome || null;
          teachWriteThrough = payload.gmail_write_through || null;
        }
        teachFlowState = "result";
        unsubscribeResult = "";
        affectedReviewOpen = false;
        await refreshState();
      } catch (error) {
        teachError = error && error.message
          ? error.message
          : "Threadwise could not complete this simulated update. Nothing else was attempted.";
        teachResult = null;
        teachFlowState = "apply-error";
        renderSelectedPanel();
      } finally {
        applyInFlight = false;
      }
    }

    async function excludeAffectedMatch(messageId, reason) {
      if (!selectedFound() || !teachPreview || !messageId) {
        return;
      }
      const labelNode = document.getElementById("sim-target-label");
      const noteNode = document.getElementById("sim-teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      const payload = await postApi("/api/teach-exclude", {
        selected_context: currentContext,
        target_label: draftLabel,
        note: draftNote,
        scope: "sender",
        excluded_message_id: messageId,
        reason,
      });
      if (payload.error) {
        teachError = payload.error;
        teachResult = "";
      } else {
        teachError = "";
        teachPreview = payload.preview || teachPreview;
        teachResult = "Exception saved. This rule will not apply to this email/pattern later.";
        affectedReviewOpen = true;
      }
      renderSelectedPanel();
    }

    async function decideRuleAmendment(decision) {
      if (!selectedFound() || !teachPreview || !teachPreview.amendment_proposal || !decision) {
        return;
      }
      const labelNode = document.getElementById("sim-target-label");
      const noteNode = document.getElementById("sim-teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      const payload = await postApi("/api/teach-amendment", {
        selected_context: currentContext,
        target_label: draftLabel,
        note: draftNote,
        scope: "sender",
        amendment: teachPreview.amendment_proposal,
        decision,
      });
      if (payload.error) {
        teachError = payload.error;
        teachResult = "";
      } else {
        teachError = "";
        teachPreview = payload.preview || teachPreview;
        draftNote = payload.note || draftNote;
        teachResult = payload.acknowledgment || "Reviewed amendment.";
        affectedReviewOpen = true;
      }
      renderSelectedPanel();
    }

    document.addEventListener("click", (event) => {
      const filterButton = event.target.closest("[data-filter]");
      if (filterButton) {
        activeFilter = filterButton.getAttribute("data-filter");
        renderFilterPills();
        renderInboxList();
        renderSummary();
        return;
      }
      const messageButton = event.target.closest("[data-message-id], [data-queue-message-id]");
      if (messageButton) {
        const targetId = messageButton.getAttribute("data-message-id") || messageButton.getAttribute("data-queue-message-id");
        const item = itemsForActiveFilter().find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).needs_attention_items) || []).find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).recent_items) || []).find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).auto_handled_items) || []).find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).kept_visible_items) || []).find((candidate) => candidate.message_id === targetId);
        setContextFromItem(item);
        return;
      }
      const acceptSuggestionButton = event.target.closest("[data-action='accept-suggestion']");
      if (acceptSuggestionButton) {
        const selected = selectedEmail();
        draftLabel = selected && (
          internalLabelId(selected.internal_label)
          || internalLabelId(selected.suggested_label)
          || internalLabelId(selected.classification)
        ) || "";
        if (!draftLabel) {
          return;
        }
        draftNote = "";
        selectedDecisionMode = "preview";
        applyTeach("current-only");
        return;
      }
      const changeSuggestionButton = event.target.closest("[data-action='change-suggestion']");
      if (changeSuggestionButton) {
        const selected = selectedEmail();
        selectedDecisionMode = "change";
        selectedDecisionConflict = "";
        draftLabel = selected && (
          internalLabelId(selected.internal_label)
          || internalLabelId(selected.suggested_label)
          || internalLabelId(selected.classification)
        ) || "";
        draftNote = "";
        renderSelectedPanel();
        document.getElementById("sim-target-label")?.focus();
        return;
      }
      const cancelCurrentChangeButton = event.target.closest("[data-action='cancel-current-change']");
      if (cancelCurrentChangeButton) {
        selectedDecisionMode = "review";
        selectedDecisionConflict = "";
        draftLabel = "";
        draftNote = "";
        renderSelectedPanel();
        return;
      }
      const previewCurrentChangeButton = event.target.closest("[data-action='preview-current-change']");
      if (previewCurrentChangeButton) {
        const labelNode = document.getElementById("sim-target-label");
        const noteNode = document.getElementById("sim-teach-note");
        draftLabel = labelNode ? labelNode.value : draftLabel;
        draftNote = noteNode ? noteNode.value : draftNote;
        if (!internalLabelId(draftLabel)) {
          return;
        }
        selectedDecisionConflict = labelConflictForDraft();
        if (selectedDecisionConflict) {
          renderSelectedPanel();
          return;
        }
        selectedDecisionMode = "preview";
        renderSelectedPanel();
        return;
      }
      const editCurrentChangeButton = event.target.closest("[data-action='edit-current-change']");
      if (editCurrentChangeButton) {
        selectedDecisionMode = "change";
        selectedDecisionConflict = "";
        teachFlowState = "teaching";
        renderSelectedPanel();
        return;
      }
      const retryCurrentChangeButton = event.target.closest("[data-action='retry-current-change']");
      if (retryCurrentChangeButton) {
        teachError = "";
        applyTeach("current-only");
        return;
      }
      const teachFutureAfterReceiptButton = event.target.closest("[data-action='teach-future-after-receipt']");
      if (teachFutureAfterReceiptButton) {
        selectedDecisionMode = "future-learning";
        renderSelectedPanel();
        return;
      }
      const backToCurrentReceiptButton = event.target.closest("[data-action='back-to-current-receipt']");
      if (backToCurrentReceiptButton) {
        selectedDecisionMode = "review";
        teachFlowState = "result";
        teachError = "";
        renderSelectedPanel();
        return;
      }
      const saveFutureLearningButton = event.target.closest("[data-action='save-future-learning']");
      if (saveFutureLearningButton) {
        const noteNode = document.getElementById("sim-future-note");
        draftNote = noteNode ? noteNode.value : draftNote;
        if (!draftNote.trim()) {
          return;
        }
        applyTeach("save-future-rule");
        return;
      }
      const retryFutureLearningButton = event.target.closest("[data-action='retry-future-learning']");
      if (retryFutureLearningButton) {
        applyTeach("save-future-rule");
        return;
      }
      const retryBroadApplyButton = event.target.closest("[data-action='retry-broad-apply']");
      if (retryBroadApplyButton) {
        applyTeach(lastApplyMode || "apply-included");
        return;
      }
      const changeAutoHandledButton = event.target.closest("[data-action='change-auto-handled']");
      if (changeAutoHandledButton) {
        const selected = selectedEmail();
        autoHandledChangeOpen = true;
        draftLabel = selected && (
          internalLabelId(selected.internal_label)
          || internalLabelId(selected.suggested_label)
          || internalLabelId(selected.classification)
        ) || "";
        draftNote = "";
        renderSelectedPanel();
        return;
      }
      const toggleDetailsButton = event.target.closest("[data-action='toggle-details']");
      if (toggleDetailsButton) {
        detailsExpanded = !detailsExpanded;
        renderSelectedPanel();
        return;
      }
      const openNeedsAttentionButton = event.target.closest("[data-action='open-needs-attention']");
      if (openNeedsAttentionButton) {
        activeFilter = "needs_attention_items";
        const currentMessageId = (selectedEmail() || {}).message_id || "";
        const queue = (((harnessState || {}).needs_attention_items) || []);
        const first = queue.find((item) => item.message_id && item.message_id !== currentMessageId) || queue[0];
        if (first) {
          setContextFromItem(first);
        }
        return;
      }
      const previewButton = event.target.closest("[data-action='preview-teach']");
      if (previewButton) {
        previewTeach();
        return;
      }
      const acceptTeachRuleButton = event.target.closest("[data-action='accept-teach-rule']");
      if (acceptTeachRuleButton) {
        teachFlowState = "scope-confirmation";
        inboxApplyConfirmOpen = false;
        renderSelectedPanel();
        return;
      }
      const refreshButton = event.target.closest("[data-action='refresh-state']");
      if (refreshButton) {
        refreshState();
        return;
      }
      const returnToFixtureListButton = event.target.closest("[data-action='return-to-fixture-list']");
      if (returnToFixtureListButton) {
        forceHome = true;
        currentContext = {};
        resetTeachState(true);
        renderSelectedPanel();
        renderSummary();
        return;
      }
      const openAffectedReviewButton = event.target.closest("[data-action='open-affected-review']");
      if (openAffectedReviewButton) {
        affectedReviewOpen = true;
        renderSelectedPanel();
        return;
      }
      const collapseAffectedReviewButton = event.target.closest("[data-action='collapse-affected-review']");
      if (collapseAffectedReviewButton) {
        affectedReviewOpen = false;
        renderSelectedPanel();
        return;
      }
      const affectedOpenGmailButton = event.target.closest("[data-affected-open-gmail]");
      if (affectedOpenGmailButton) {
        const messageId = affectedOpenGmailButton.getAttribute("data-affected-open-gmail") || "";
        const item = affectedReviewItems(teachPreview).find((candidate) => candidate.message_id === messageId);
        if (item) {
          setContextFromItem(item);
        }
        return;
      }
      const affectedExcludeButton = event.target.closest("[data-affected-exclude]");
      if (affectedExcludeButton) {
        const messageId = affectedExcludeButton.getAttribute("data-affected-exclude") || "";
        const reasonNode = document.querySelector(`[data-affected-exclusion-reason="${CSS.escape(messageId)}"]`);
        excludeAffectedMatch(messageId, reasonNode ? reasonNode.value : "");
        return;
      }
      const amendmentButton = event.target.closest("[data-amendment-decision]");
      if (amendmentButton) {
        decideRuleAmendment(amendmentButton.getAttribute("data-amendment-decision") || "");
        return;
      }
      const clearButton = event.target.closest("[data-action='clear-teach']");
      if (clearButton) {
        resetTeachState(true);
        renderSelectedPanel();
        return;
      }
      const refineButton = event.target.closest("[data-action='refine-teach']");
      if (refineButton) {
        previousTeachPreview = teachPreview;
        teachPreview = null;
        teachError = "";
        teachResult = null;
        draftNote = (previousTeachPreview && previousTeachPreview.plain_english_rule) || draftNote;
        teachFlowState = "refining";
        renderSelectedPanel();
        return;
      }
      const confirmInboxApplyButton = event.target.closest("[data-action='confirm-inbox-apply']");
      if (confirmInboxApplyButton) {
        applyTeach("apply-included");
        return;
      }
      const cancelInboxApplyButton = event.target.closest("[data-action='cancel-inbox-apply']");
      if (cancelInboxApplyButton) {
        inboxApplyConfirmOpen = false;
        renderSelectedPanel();
        return;
      }
      const applyButton = event.target.closest("[data-apply-mode]");
      if (applyButton) {
        const mode = applyButton.getAttribute("data-apply-mode") || "";
        if (mode === "apply-included" && teachPreview && teachPreview.inbox_backfill && teachPreview.inbox_backfill.requires_confirmation && !inboxApplyConfirmOpen) {
          inboxApplyConfirmOpen = true;
          renderSelectedPanel();
          return;
        }
        applyTeach(mode);
        return;
      }
      const unsubscribeButton = event.target.closest("[data-action='select-unsubscribe']");
      if (unsubscribeButton) {
        unsubscribeSelectCurrent();
      }
    });

    refreshButton.addEventListener("click", () => {
      forceHome = false;
      resetTeachState(false);
      refreshState();
    });
    homeButton.addEventListener("click", () => {
      forceHome = true;
      resetTeachState(true);
      renderSelectedPanel();
      renderSummary();
    });
    minimizeButton.addEventListener("click", () => {
      minimized = !minimized;
      panelNode.classList.toggle("minimized", minimized);
      minimizeButton.textContent = minimized ? "Open" : "Minimize";
    });
    unsyncedButton.addEventListener("click", () => {
      forceHome = false;
      currentContext = { ...unsyncedContext };
      resetTeachState(true);
      fetch(`/api/harness-state?${new URLSearchParams(currentContext).toString()}`)
        .then((response) => response.json())
        .then((payload) => {
          harnessState = payload;
          unsubscribeResult = "";
          renderFilterPills();
          renderInboxList();
          renderReadingPane();
          renderSelectedPanel();
          renderSummary();
        });
    });

    async function unsubscribeSelectCurrent() {
      if (!selectedFound()) {
        return;
      }
      const payload = await postApi("/api/unsubscribe-select-current", {
        selected_context: currentContext,
      });
      if (payload.error) {
        unsubscribeResult = payload.error;
      } else {
        unsubscribeResult = payload.acknowledgment || "Queued for unsubscribe review.";
      }
      await refreshState();
      renderSelectedPanel();
    }

    refreshState();
  </script>
</body>
</html>"""

    def render_install_page(self, host_header: str) -> str:
        origin = server_origin(host_header)
        extension_path = str((Path.cwd() / "extensions" / "gmail_companion").resolve())
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Gmail Companion</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1d1a16;
      --muted: #6b6255;
      --line: #d9cfbf;
      --panel: #fffdf8;
      --soft: #f4ecdd;
      --accent: #0f766e;
      --accent-soft: #d8f3ef;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #efe3cb 0%, #f6f0e4 42%, #f8f4eb 100%); color: var(--ink); }}
    main {{ max-width: 980px; margin: 0 auto; padding: 36px 20px 56px; display: grid; gap: 18px; }}
    .hero {{ background: var(--panel); border: 1px solid var(--line); border-radius: 22px; padding: 24px; box-shadow: 0 18px 40px rgba(29, 26, 22, 0.08); }}
    .eyebrow {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem; }}
    h1 {{ margin: 10px 0 12px; font-size: 2rem; line-height: 1.05; }}
    p {{ line-height: 1.5; }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: 1.2fr 0.8fr; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 18px; }}
    ol {{ margin: 10px 0 0; padding-left: 22px; }}
    li + li {{ margin-top: 8px; }}
    .path {{ margin-top: 12px; padding: 12px 14px; border-radius: 14px; border: 1px solid var(--line); background: #fcfaf5; font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }}
    .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 0.84rem; }}
    .meta {{ color: var(--muted); }}
    @media (max-width: 820px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">Gmail Companion</div>
      <h1>Install the local Gmail sidebar once, then use it inside Gmail.</h1>
      <p>The old bookmark launcher path has been retired. The current setup is the local Brave extension plus the companion server on <span class="pill">{origin}</span>.</p>
    </section>
    <section class="grid">
      <section class="card">
        <div class="eyebrow">Brave Setup</div>
        <ol>
          <li>Open <code>brave://extensions</code>.</li>
          <li>Turn on <strong>Developer mode</strong>.</li>
          <li>Choose <strong>Load unpacked</strong>.</li>
          <li>Select this folder:</li>
        </ol>
        <div class="path">{extension_path}</div>
        <ol start="5">
          <li>Keep the companion server running at <code>{origin}</code>.</li>
          <li>Open Gmail and refresh once.</li>
        </ol>
      </section>
      <section class="card">
        <div class="eyebrow">What You Should See</div>
        <p>A right-side panel inside Gmail that shows:</p>
        <ol>
          <li>the current email’s category</li>
          <li>whether it was auto-handled or still needs attention</li>
          <li>a short reason</li>
          <li>a compact view of today’s activity</li>
        </ol>
        <p class="meta">This page is now only for installation and troubleshooting. The product itself lives in Gmail.</p>
      </section>
    </section>
  </main>
</body>
</html>"""

    def render_unsubscribe_review_page(self, query: dict[str, list[str]] | None = None) -> str:
        query = query or {}
        focus_list_key = first_query_value(query, "list_key")
        candidates = self._unsubscribe_store.list_candidates()
        executor = UnsubscribeExecutor(self._storage_dir)
        preview = executor.preview_selected_candidates()
        cards_by_section = {
            "selected": [],
            "ready": [],
            "manual": [],
            "other": [],
        }
        for candidate in candidates:
            detail = build_unsubscribe_detail(candidate, self._storage_dir)
            candidate_preview = detail["preview"]
            latest_execution = detail.get("latest_execution") or {}
            is_focused = bool(focus_list_key and detail.get("list_key") == focus_list_key)
            action_html = ""
            preview_url = candidate_preview.get("url") or ""
            if preview_url.startswith("mailto:"):
                action_html = f'<a class="action" href="{escape_html(preview_url)}">Open mail unsubscribe</a>'
            elif preview_url.startswith("http") and candidate_preview.get("status") == "ready":
                action_html = (
                    '<p class="safety-note"><strong>Audited action only:</strong> '
                    'Threadwise will not open this one-click HTTPS unsubscribe as a raw browser link. '
                    'Queue it for review and execute supported unsubscribes only after explicit confirmation.</p>'
                )
            elif preview_url.startswith("http"):
                action_html = (
                    f'<p class="safety-note"><strong>Manual provider page:</strong> '
                    'This link may require a signed-in provider session or may show a provider error page. '
                    'Opening it does not execute a Threadwise unsubscribe.</p>'
                    f'<a class="action secondary" href="{escape_html(preview_url)}" target="_blank" rel="noreferrer">Open provider page manually</a>'
                )
            focus_html = '<div class="focus-note">Opened from inbox</div>' if is_focused else ""
            latest_execution_html = (
                f'<p><strong>Latest attempt:</strong> {escape_html(latest_execution.get("status") or "none")} - {escape_html(latest_execution.get("notes") or "No recorded execution yet.")}</p>'
                if latest_execution
                else '<p><strong>Latest attempt:</strong> none</p>'
            )
            card_html = (
                f'<article class="card{" focused" if is_focused else ""}">'
                f'{focus_html}'
                f'<div class="eyebrow">Unsubscribe</div>'
                f'<h2>{escape_html(detail.get("display_name") or "(unknown list)")}</h2>'
                f'<p><strong>Sender:</strong> {escape_html(detail.get("sender") or "(unknown sender)")}</p>'
                f'<p><strong>Status:</strong> {escape_html(candidate_preview.get("notes") or "(none)")}</p>'
                f'<p><strong>Selection:</strong> {escape_html(detail.get("decision_state") or "undecided")}</p>'
                f'<p><strong>Evidence:</strong> {detail.get("evidence_count", 0)} messages</p>'
                f'{latest_execution_html}'
                f'{action_html}'
                '</article>'
            )
            section_key = unsubscribe_section_key(detail, candidate_preview)
            cards_by_section[section_key].append(card_html)

        if not any(cards_by_section.values()):
            cards_by_section["other"].append('<article class="card"><h2>No unsubscribe candidates</h2><p>No unsubscribe candidates are stored yet.</p></article>')

        sections_html = "".join(
            render_unsubscribe_section(title, description, cards_by_section[key])
            for key, title, description in [
                ("selected", "Queued From Inbox", "These are the subscriptions you already queued for later review from the inbox."),
                ("ready", "Ready Now", "These have a supported unsubscribe path and are not queued yet."),
                ("manual", "Manual Follow-Up", "These look like subscriptions, but the unsubscribe path still needs a manual step."),
                ("other", "All Other Candidates", "Everything else the agent thinks may be a subscription family."),
            ]
            if cards_by_section[key]
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Unsubscribe Review</title>
  <style>
    body {{ margin:0; min-height:100vh; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at 18px 18px, rgba(36,24,18,.05) 2px, transparent 2px) 0 0 / 36px 36px, linear-gradient(135deg,#f7efe0 0%,#fdfaf2 52%,#e7f3ee 100%); color:#241812; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px; display:grid; gap:18px; }}
    .hero,.card {{ background:#fffdf7; border:3px solid #241812; border-radius:18px; padding:18px; box-shadow:5px 5px 0 #241812; }}
    .hero {{ background:#fff7e8; }}
    .hero-heading {{ display:flex; align-items:center; gap:12px; }}
    .brand-mark {{ width:42px; height:42px; border-radius:12px; border:2px solid #241812; box-shadow:3px 3px 0 #241812; flex:0 0 auto; background:#fff8df; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
    .section {{ display:grid; gap:12px; }}
    .eyebrow {{ color:#6b6255; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.14em; font-weight:820; }}
    h1,h2 {{ margin:8px 0 10px; }}
    h1 {{ font-size:2rem; line-height:1.05; }}
    p {{ line-height:1.45; }}
    .action {{ display:inline-block; margin-top:10px; border:2px solid #241812; border-radius:11px; background:#2eb67d; color:#241812; padding:9px 12px; text-decoration:none; font-weight:800; box-shadow:3px 3px 0 #241812; }}
    .action.secondary {{ background:#fffdf7; color:#5d5342; }}
    .safety-note {{ border:2px solid #241812; border-radius:12px; background:#fff7e8; padding:10px 12px; color:#4d4134; }}
    .pill-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .pill {{ border:2px solid #241812; border-radius:999px; padding:6px 10px; background:#f1eadf; color:#241812; font-size:0.8rem; font-weight:760; box-shadow:2px 2px 0 rgba(36,24,18,.28); }}
    .focused {{ border-color:#2eb67d; background:#f5fbfa; }}
    .focus-note {{ display:inline-flex; align-items:center; padding:6px 10px; border:2px solid #241812; border-radius:999px; background:#dff8ed; color:#09633c; font-size:0.82rem; font-weight:760; }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-heading">
        <img class="brand-mark" src="/assets/brand/threadwise-app-icon.png" alt="" aria-hidden="true">
        <div>
          <div class="eyebrow">Unsubscribe Review</div>
          <h1>Subscription cleanup</h1>
        </div>
      </div>
      <p>Selected for later unsubscribe: {preview.get("selected_count", 0)}. Ready now: {preview.get("ready_count", 0)}. Manual follow-up needed: {preview.get("unsupported_count", 0)}.</p>
      <div class="pill-row">
        <span class="pill">Queued: {preview.get("selected_count", 0)}</span>
        <span class="pill">Ready now: {preview.get("ready_count", 0)}</span>
        <span class="pill">Manual follow-up: {preview.get("unsupported_count", 0)}</span>
        <span class="pill">All candidates: {len(candidates)}</span>
      </div>
    </section>
    <section class="section">
      {sections_html}
    </section>
  </main>
</body>
</html>"""

    def render_daily_dashboard_page(self) -> str:
        payload = build_companion_runtime_payload(self._storage_dir)
        summary = payload.get("daily_summary", {})
        attention_summary = build_daily_attention_summary(self._storage_dir)
        run_status = load_gmail_dashboard_run_status(self._storage_dir)
        run_status_label = run_status.get("status", "idle")
        inferred_account_id = infer_gmail_account_id(self._storage_dir)
        changed_today = summary.get("changed_today", {})
        selected_unsubscribe_examples = changed_today.get("selected_unsubscribe_examples", [])
        candidate_examples = changed_today.get("candidate_examples", [])
        sections = [
            (
                "Needs Attention",
                "The emails still waiting for a confident decision or explicit follow-up.",
                render_dashboard_email_cards(payload.get("needs_attention_items", []), empty_label="No needs-attention emails in the current snapshot."),
            ),
            (
                "Kept Visible",
                "Emails the agent understood but intentionally left easy to find in the inbox.",
                render_dashboard_email_cards(
                    payload.get("kept_visible_items", []),
                    empty_label="No kept-visible emails in the current snapshot.",
                    allow_attention_feedback=True,
                ),
            ),
            (
                "Auto-Handled",
                "Emails the agent already labeled or removed from inbox under the current bounded rules.",
                render_dashboard_email_cards(payload.get("auto_handled_items", []), empty_label="No auto-handled emails in the current snapshot."),
            ),
            (
                "Recent Queue",
                "The freshest synced emails across the current local snapshot.",
                render_dashboard_email_cards(
                    payload.get("recent_items", []),
                    empty_label="No recent synced emails in the current snapshot.",
                    allow_attention_feedback=True,
                ),
            ),
        ]
        top_labels_html = "".join(
            f'<span class="pill">{escape_html(item.get("label", ""))} · {item.get("count", 0)}</span>'
            for item in summary.get("top_labels", [])
        )
        changed_items_html = render_dashboard_changed_cards(changed_today.get("items", []))
        unsubscribe_html = render_dashboard_unsubscribe_cards(selected_unsubscribe_examples)
        candidate_review_html = render_dashboard_candidate_cards(candidate_examples)
        sections_html = "".join(
            render_dashboard_section(title, description, cards)
            for title, description, cards in sections
        )
        attention_now_html = render_dashboard_attention_cards(
            attention_summary.get("now_items", []),
            empty_label="No attention-now items in the latest Gmail daily report.",
        )
        possible_attention_html = render_dashboard_attention_cards(
            attention_summary.get("possible_items", []),
            empty_label="No possible-attention items in the latest Gmail daily report.",
        )
        hidden_insufficient_context_count = attention_summary.get("hidden_insufficient_context_count", 0)
        hidden_insufficient_context_html = (
            f'<div class="copy">{hidden_insufficient_context_count} lower-risk insufficient-context '
            "item kept out of this daily attention view.</div>"
            if hidden_insufficient_context_count == 1
            else (
                f'<div class="copy">{hidden_insufficient_context_count} lower-risk insufficient-context '
                "items kept out of this daily attention view.</div>"
                if hidden_insufficient_context_count
                else ""
            )
        )
        attention_report_pills = "".join(
            [
                (
                    f'<span class="pill">Latest attention report: {escape_html(attention_summary.get("report_date", ""))}</span>'
                    if attention_summary.get("report_date")
                    else ""
                ),
                f'<span class="pill">Evaluated: {attention_summary.get("evaluated_message_count", 0)}</span>',
                f'<span class="pill">Now: {len(attention_summary.get("now_items", []))}</span>',
                f'<span class="pill">Possible: {len(attention_summary.get("possible_items", []))}</span>',
            ]
        )
        run_result = run_status.get("result") or {}
        run_status_pills = "".join(
            [
                f'<span class="pill">Run status: {escape_html(run_status_label)}</span>',
                (
                    f'<span class="pill">Last batch: {escape_html(run_result.get("batch_id", ""))}</span>'
                    if run_result.get("batch_id")
                    else ""
                ),
                (
                    f'<span class="pill">Error: {escape_html(run_status.get("error", ""))}</span>'
                    if run_status.get("error")
                    else ""
                ),
            ]
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise Daily Dashboard</title>
  <style>
    body {{ margin:0; min-height:100vh; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at 18px 18px, rgba(36,24,18,.05) 2px, transparent 2px) 0 0 / 36px 36px, linear-gradient(135deg,#f7efe0 0%,#fdfaf2 52%,#e7f3ee 100%); color:#241812; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px; display:grid; gap:18px; }}
    .hero,.card {{ background:#fffdf7; border:3px solid #241812; border-radius:18px; padding:18px; box-shadow:5px 5px 0 #241812; }}
    .hero {{ background:#fff7e8; }}
    .hero-heading {{ display:flex; align-items:center; gap:12px; }}
    .brand-mark {{ width:42px; height:42px; border-radius:12px; border:2px solid #241812; box-shadow:3px 3px 0 #241812; flex:0 0 auto; background:#fff8df; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
    .section {{ display:grid; gap:12px; }}
    .eyebrow {{ color:#6b6255; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.14em; font-weight:820; }}
    h1,h2 {{ margin:8px 0 10px; }}
    h1 {{ font-size:2rem; line-height:1.05; }}
    p {{ line-height:1.45; }}
    .pill-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .pill {{ border:2px solid #241812; border-radius:999px; padding:6px 10px; background:#f1eadf; color:#241812; font-size:0.8rem; font-weight:760; box-shadow:2px 2px 0 rgba(36,24,18,.28); }}
    .metric-grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin-top:14px; }}
    .metric {{ border:2px solid #241812; border-radius:11px; background:#fffdf7; padding:12px; box-shadow:2px 2px 0 rgba(36,24,18,.18); }}
    .metric strong {{ display:block; font-size:1.15rem; }}
    .stack {{ display:grid; gap:10px; }}
    .email-card {{ border:2px solid #241812; border-radius:11px; background:#fffdf7; padding:12px; box-shadow:2px 2px 0 rgba(36,24,18,.18); }}
    .attention-card {{ background:#fffaf0; }}
    .email-card h3 {{ margin:0; font-size:0.98rem; line-height:1.3; }}
    .meta {{ margin-top:6px; color:#6b6255; font-size:0.84rem; overflow-wrap:anywhere; }}
    .copy {{ margin-top:8px; color:#1f1a14; line-height:1.45; }}
    .action {{ display:inline-flex; align-items:center; margin-top:10px; border:2px solid #241812; border-radius:11px; background:#2eb67d; color:#241812; padding:9px 12px; text-decoration:none; font-weight:800; box-shadow:3px 3px 0 #241812; }}
    @media (max-width: 820px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-heading">
        <img class="brand-mark" src="/assets/brand/threadwise-app-icon.png" alt="" aria-hidden="true">
        <div>
          <div class="eyebrow">Daily Dashboard</div>
          <h1>What Threadwise did today</h1>
        </div>
      </div>
      <p>This is the fuller secondary view behind the inbox sidebar: what came in, what the agent changed, what still needs attention, and what subscription cleanup is queued.</p>
      <div class="metric-grid">
        <div class="metric"><strong>{summary.get("processed_count", 0)}</strong><span>processed</span></div>
        <div class="metric"><strong>{summary.get("auto_handled_count", 0)}</strong><span>auto-handled</span></div>
        <div class="metric"><strong>{summary.get("needs_attention_count", 0)}</strong><span>need attention</span></div>
        <div class="metric"><strong>{len(payload.get("kept_visible_items", []))}</strong><span>kept visible</span></div>
      </div>
      <div class="pill-row">
        <span class="pill">Source: {escape_html(summary.get("source_label", "stored Gmail snapshot"))}</span>
        {f'<span class="pill">Latest report: {escape_html(summary.get("report_date", ""))}</span>' if summary.get("report_date") else ""}
        <span class="pill">Unsubscribe candidates: {summary.get("unsubscribe_candidate_count", 0)}</span>
      </div>
      {f'<div class="pill-row">{top_labels_html}</div>' if top_labels_html else ""}
    </section>
    <section class="card">
      <div class="eyebrow" id="run-gmail-check">Run Gmail Check</div>
      <h2>Run Gmail check</h2>
      <p>This confirmed run may apply existing safe EA/ labels, remove INBOX only for approved low-value categories, and may call the LLM for attention detection. Attention detection itself does not mutate Gmail.</p>
      <div class="pill-row">{run_status_pills}</div>
      <form method="post" action="/api/gmail-check-run">
        <input type="hidden" name="account_id" value="{escape_html(inferred_account_id)}">
        <input type="hidden" name="batch_size" value="50">
        <label class="copy" style="display:block;">
          <input id="confirm-run-gmail-check" type="checkbox" name="confirmed" value="true" required>
          Confirm this Gmail check may use the existing safe mutation boundaries and small LLM cost.
        </label>
        <button class="action" type="submit" {'disabled' if run_status_label == 'running' else ''}>Run Gmail check</button>
      </form>
    </section>
    <section class="card">
      <div class="eyebrow">Needs Attention</div>
      <h2>Needs attention from latest Gmail report</h2>
      <p>Attention detection is separate from classification and does not mutate Gmail. Strong signals and lower-confidence candidates are split so uncertainty does not swamp the daily view.</p>
      <div class="pill-row">{attention_report_pills}</div>
      {f'<div class="copy">{escape_html(attention_summary.get("empty_reason", ""))}</div>' if attention_summary.get("empty_reason") else ""}
      <div class="grid" style="margin-top:12px;">
        <article class="email-card">
          <div class="eyebrow">Strong Signals</div>
          <h2>Needs Attention Now</h2>
          <div class="stack">{attention_now_html}</div>
        </article>
        <article class="email-card">
          <div class="eyebrow">Lower Confidence</div>
          <h2>Possible Attention</h2>
          <div class="stack">{possible_attention_html}</div>
          {hidden_insufficient_context_html}
        </article>
      </div>
    </section>
    <section class="grid">
      <article class="card">
        <div class="eyebrow">What Changed Today</div>
        <h2>Provider-side changes</h2>
        <div class="metric-grid">
          <div class="metric"><strong>{changed_today.get("label_writes_count", 0)}</strong><span>labels written</span></div>
          <div class="metric"><strong>{changed_today.get("inbox_removed_count", 0)}</strong><span>removed from inbox</span></div>
          <div class="metric"><strong>{changed_today.get("taught_count", 0)}</strong><span>teaching changes</span></div>
          <div class="metric"><strong>{changed_today.get("selected_unsubscribe_count", 0)}</strong><span>unsubscribe queued</span></div>
          <div class="metric"><strong>{changed_today.get("candidate_pending_count", 0)}</strong><span>candidate review</span></div>
        </div>
        <div class="stack" style="margin-top:12px;">{changed_items_html}</div>
        <div class="stack" style="margin-top:12px;">{candidate_review_html}</div>
      </article>
      <article class="card">
        <div class="eyebrow">Subscriptions</div>
        <h2>Queued unsubscribe review</h2>
        <p>The inbox sidebar can queue subscriptions for later review. This page shows the currently queued families.</p>
        <div class="stack">{unsubscribe_html}</div>
        <a class="action" href="/unsubscribe-review" target="_blank" rel="noreferrer">Open unsubscribe review</a>
      </article>
    </section>
    <section class="section">
      {sections_html}
    </section>
  </main>
</body>
</html>"""

    def render_panel(self) -> str:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Threadwise</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3efe4;
      --panel: #fffdf8;
      --ink: #211912;
      --muted: #6b6255;
      --line: rgba(84,68,45,0.2);
      --accent: #0f766e;
      --accent-soft: #d8f3ef;
      --gold: #c88616;
      --warn-soft: #fff4dd;
      --warn-ink: #8a4b00;
      --soft: #f5efe2;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Georgia, 'Times New Roman', serif; background: radial-gradient(circle at top, #fbf6ec 0%, #f4ede0 58%, #efe6d7 100%); color: var(--ink); }
    .shell { width: 100%; min-height: 100vh; padding: 14px; background: radial-gradient(circle at 18px 18px, rgba(36,24,18,.05) 2px, transparent 2px) 0 0 / 36px 36px, linear-gradient(135deg,#f7efe0 0%,#fdfaf2 52%,#e7f3ee 100%); }
    .panel { background: #fff7e8; border: 3px solid #241812; border-radius: 18px; box-shadow: 6px 6px 0 #241812; overflow: hidden; }
    .panel.minimized .content, .panel.minimized .footer { display: none; }
    .panel.minimized { width: 84px; }
    .header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 17px 18px; border-bottom: 3px solid #241812; background: #fff4d7; }
    .header-copy { display: grid; gap: 6px; min-width: 0; }
    .header-top { display: flex; align-items: center; gap: 8px; }
    .dot { width: 10px; height: 10px; border-radius: 999px; background: var(--accent); box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12); }
    .brand-lockup { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .brand-mark { width: 42px; height: 42px; border-radius: 12px; border: 2px solid #241812; box-shadow: 3px 3px 0 #241812; flex: 0 0 auto; background: #fff8df; }
    .brand-kicker { color: #ad6400; font-family: ui-serif, Georgia, "Times New Roman", serif; font-size: 0.58rem; font-weight: 900; letter-spacing: 0.08em; text-transform: uppercase; white-space: nowrap; line-height: 1.05; }
    .title { font-size: 1.35rem; font-weight: 840; letter-spacing: -0.04em; line-height: 1; }
    .subtitle { color: var(--muted); font-size: 0.88rem; line-height: 1.35; }
    .minimize { border: 2px solid #241812; background: #e9efe2; color: var(--ink); border-radius: 11px; padding: 9px 12px; cursor: pointer; font: inherit; font-weight: 760; box-shadow: 2px 2px 0 #241812; }
    .content { padding: 12px; display: grid; gap: 10px; }
    .hero { border: 3px solid #241812; border-radius: 18px; padding: 16px; background: #fffdf7; box-shadow: 2px 2px 0 rgba(36,24,18,.18); }
    .eyebrow { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; }
    .subject { margin-top: 8px; font-size: 1.08rem; font-weight: 700; line-height: 1.2; }
    .sender { margin-top: 6px; color: var(--muted); font-size: 0.88rem; overflow-wrap: anywhere; }
    .pill-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .pill { display: inline-flex; align-items: center; padding: 5px 10px; border-radius: 999px; font-size: 0.82rem; }
    .classification-pill { background: #efe7d4; color: #5f512f; }
    .status-pill { background: var(--accent-soft); color: var(--accent); }
    .warn-pill { background: var(--warn-soft); color: var(--warn-ink); }
    .reason-wrap { margin-top: 14px; border-radius: 10px; background: var(--soft); padding: 12px; }
    .reason-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
    .reason { margin-top: 8px; color: var(--ink); line-height: 1.45; }
    .teach-card { border: 3px solid #241812; border-radius: 18px; background: #ffe1a3; overflow: hidden; box-shadow: 2px 2px 0 rgba(36,24,18,.18); }
    .teach-card > .reason-label { display: flex; align-items: center; min-height: 40px; padding: 0 13px; border-bottom: 3px solid #241812; background: #ffc64a; color: #241812; font-weight: 900; }
    .teach-panel { margin: 12px; display: grid; gap: 12px; }
    .teach-panel .field-stack { margin-top: 0; }
    .secondary-card { border: 3px solid #241812; border-radius: 18px; padding: 16px; background: #e9efe2; box-shadow: 2px 2px 0 rgba(36,24,18,.18); }
    .empty { margin-top: 10px; color: var(--muted); line-height: 1.45; }
    .checklist { margin: 10px 0 0; padding-left: 18px; color: var(--muted); }
    .checklist li + li { margin-top: 6px; }
    .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
    .summary-grid--three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .metric { border-radius: 10px; background: var(--soft); padding: 12px; }
    .metric strong { display: block; font-size: 1.15rem; }
    .metric span { color: var(--muted); font-size: 0.82rem; }
    .label-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .label-chip { border-radius: 999px; padding: 6px 10px; background: #f1eadb; color: #5d5342; font-size: 0.8rem; }
    .footer { padding: 0 14px 14px; }
    .footer-card { border: 1px dashed var(--line); border-radius: 10px; padding: 10px 12px; background: rgba(255,255,255,0.55); color: var(--muted); font-size: 0.84rem; line-height: 1.4; }
    .harness { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 14px; align-items: start; transition: grid-template-columns 160ms ease; }
    .harness.expanded-review { grid-template-columns: minmax(220px,.42fr) minmax(720px,1fr); }
    .list-card { border: 1px solid var(--line); border-radius: 18px; padding: 14px; background: rgba(255,255,255,0.72); }
    .list-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .list-stack { display: grid; gap: 8px; margin-top: 12px; max-height: 68vh; overflow: auto; }
    .list-item { width: 100%; text-align: left; border: 1px solid var(--line); border-radius: 14px; background: #fffdfa; padding: 10px 12px; cursor: pointer; font: inherit; color: var(--ink); }
    .list-item.active { border-color: var(--accent); box-shadow: inset 0 0 0 1px rgba(15,118,110,0.18); background: #f5fbfa; }
    .list-item-subject { font-size: 0.95rem; font-weight: 700; line-height: 1.25; }
    .list-item-meta { margin-top: 4px; color: var(--muted); font-size: 0.82rem; overflow-wrap: anywhere; }
    .list-item-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .metric-button { border: 0; border-radius: 14px; background: var(--soft); padding: 12px; text-align: left; cursor: pointer; font: inherit; color: var(--ink); }
    .metric-button.active { background: #e7f6f4; box-shadow: inset 0 0 0 1px rgba(15,118,110,0.22); }
    .metric-button strong { display:block;font-size:1.15rem;line-height:1; }
    .metric-button span { display:block;margin-top:3px; }
    .detail-list { display: grid; gap: 8px; margin-top: 12px; }
    .field-stack { display: grid; gap: 8px; margin-top: 10px; }
    .select, .textarea { width: 100%; border-radius: 11px; border: 2px solid #241812; background: #fffdf7; color: var(--ink); font: inherit; box-shadow: 2px 2px 0 rgba(36,24,18,.18); }
    .select { padding: 10px 12px; }
    .textarea { min-height: 84px; padding: 10px 12px; resize: vertical; }
    .button-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 2px; }
    .action-button { border: 2px solid #241812; border-radius: 11px; padding: 9px 12px; cursor: pointer; font: inherit; font-weight: 800; box-shadow: 3px 3px 0 #241812; }
    .action-button.primary { background: #2eb67d; color: #241812; }
    .action-button.secondary { background: #ebe4d7; color: var(--ink); }
    .action-button.info { background: #1f6f8b; color: #fff; }
    .action-button.future { background: #7b5d2a; color: #fff; }
    .action-button.quiet { border: 0; background: transparent; color: #5d5342; border-radius: 0; padding: 7px 2px; box-shadow: none; text-decoration: underline; text-underline-offset: 3px; font-weight: 760; }
    .preview-card, .success-card, .error-card, .note { box-sizing: border-box; width: 100%; min-width: 0; max-width: 100%; overflow-wrap: anywhere; word-break: break-word; }
    .preview-card { margin-top: 12px; border-radius: 14px; background: #fff8eb; padding: 12px; color: var(--ink); line-height: 1.45; }
    .success-card { margin-top: 12px; border-radius: 14px; background: var(--accent-soft); padding: 12px; color: var(--accent); line-height: 1.45; }
    .error-card { margin-top: 12px; border-radius: 14px; background: var(--warn-soft); padding: 12px; color: var(--warn-ink); line-height: 1.45; }
    .affected-review { margin-top: 12px; border: 3px solid #241812; border-radius: 14px; background: #fffdf7; overflow: hidden; }
    .affected-review-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; border-bottom: 2px solid #241812; background: #fff4d7; }
    .affected-review-table-wrap { max-height: 52vh; overflow: auto; }
    .affected-review table { width: 100%; border-collapse: collapse; font-size: .84rem; }
    .affected-review th, .affected-review td { padding: 8px 10px; border-bottom: 1px solid rgba(84,68,45,0.18); text-align: left; vertical-align: top; }
    .affected-review th { color: var(--muted); font-size: .68rem; text-transform: uppercase; letter-spacing: .08em; background: #fff8eb; position: sticky; top: 0; z-index: 1; }
    .affected-review td { line-height: 1.3; }
    .affected-review .subject-cell { font-weight: 760; }
    @media (max-width: 980px) { .harness { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="shell">
    <div class="harness" id="harness-shell">
      <section class="list-card">
        <div class="list-header">
          <div>
            <div class="eyebrow">Harness</div>
            <div class="title" style="margin-top:6px;">Synced Inbox Fixtures</div>
          </div>
          <button id="refresh-harness" class="minimize" type="button">Refresh</button>
        </div>
        <div id="harness-filter-pills" class="label-row"></div>
        <div id="harness-list" class="list-stack"></div>
      </section>
      <section id="panel" class="panel">
        <header class="header">
          <div class="header-copy">
            <div class="brand-lockup">
              <img class="brand-mark" src="/assets/brand/threadwise-app-icon.png" alt="" aria-hidden="true">
              <div>
                <div class="title">Threadwise</div>
                <div class="brand-kicker">CLEAR THREADS. BETTER INBOX.</div>
              </div>
            </div>
          </div>
          <button id="minimize" class="minimize" type="button">Minimize</button>
        </header>
        <div class="content">
          <section class="hero">
            <div class="eyebrow">Agent View</div>
            <div id="selected-email"></div>
          </section>
          <section class="teach-card">
            <div class="reason-label">Correct / Teach</div>
            <div id="teach-panel" class="teach-panel"></div>
          </section>
          <section class="secondary-card">
            <div class="eyebrow">Today</div>
            <div id="daily-summary"></div>
          </section>
        </div>
        <div class="footer">
          <div class="footer-card" id="footer-note">Local harness mode is backed by real synced inbox artifacts so the companion can be tested without live Gmail attachment.</div>
        </div>
      </section>
    </div>
  </div>
  <script>
    const panelNode = document.getElementById("panel");
    const selectedEmailNode = document.getElementById("selected-email");
    const harnessShellNode = document.getElementById("harness-shell");
    const teachPanelNode = document.getElementById("teach-panel");
    const dailySummaryNode = document.getElementById("daily-summary");
    const minimizeButton = document.getElementById("minimize");
    const harnessListNode = document.getElementById("harness-list");
    const harnessFilterPillsNode = document.getElementById("harness-filter-pills");
    const refreshHarnessButton = document.getElementById("refresh-harness");
    let currentContext = {};
    let harnessState = null;
    let activeHarnessFilter = "recent_items";
    let teachPreview = null;
    let previousTeachPreview = null;
    let teachResult = "";
    let teachError = "";
    let unsubscribeResult = "";
    let draftLabel = "";
    let draftNote = "";
    let affectedReviewOpen = false;
    let detailsExpanded = false;

    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function nextStepCopy(selectedEmail) {
      if (!selectedEmail || !selectedEmail.found) {
        return {
          title: "What to do now",
          body: "Preview a synced email below, or run a Gmail check from the dashboard to refresh what Threadwise knows.",
        };
      }
      if (selectedEmail.status === "needs-attention") {
        return {
          title: "What to do now",
          body: "This email still needs a decision. Teach the right label below or leave it visible for later.",
        };
      }
      if (selectedEmail.unsubscribe_available) {
        return {
          title: "What to do now",
          body: "The agent already understands this email. If it is recurring, you can queue it for unsubscribe review here.",
        };
      }
      return {
        title: "What to do now",
        body: "The agent has already classified this email. You only need to step in if the label or handling looks wrong.",
      };
    }

    function activeHarnessBucketDescription() {
      return {
        needs_attention_items: "Items still waiting for a confident decision or follow-up.",
        recent_items: "Most recent synced emails across the current local snapshot.",
        auto_handled_items: "Items the agent already handled automatically.",
        kept_visible_items: "Items the agent understood but intentionally left visible.",
      }[activeHarnessFilter] || "Current queue slice.";
    }

    function contextFromItem(item) {
      return {
        provider: "gmail",
        message_id: item?.message_id || "",
        subject: item?.subject || "",
        sender: item?.sender || "",
      };
    }

    function openHarnessItemPreview(item, clearDraft = true) {
      if (!item) {
        return;
      }
      currentContext = contextFromItem(item);
      resetTeachState(clearDraft);
      refreshState();
    }

    function relatedHarnessItemsForContext(context) {
      if (!context || !harnessState) {
        return [];
      }
      const sender = String(context.sender || "").trim().toLowerCase();
      const subject = String(context.subject || "").trim().toLowerCase();
      const seen = new Set();
      const results = [];
      const groups = [
        harnessState.needs_attention_items || [],
        harnessState.recent_items || [],
        harnessState.kept_visible_items || [],
        harnessState.auto_handled_items || [],
      ];
      for (const group of groups) {
        for (const item of group) {
          if (!item || !item.message_id || seen.has(item.message_id)) {
            continue;
          }
          const itemSender = String(item.sender || "").trim().toLowerCase();
          const itemSubject = String(item.subject || "").trim().toLowerCase();
          if ((sender && itemSender === sender) || (subject && itemSubject === subject)) {
            seen.add(item.message_id);
            results.push(item);
          }
        }
      }
      return results;
    }

    function renderSelectedEmail(selectedEmail) {
      const stepCopy = nextStepCopy(selectedEmail);
      const understandingState = String((selectedEmail || {}).understanding_state || "ready");
      const understandingActive = understandingState === "reading" || understandingState === "understanding";
      if (understandingActive) {
        affectedReviewOpen = false;
        syncAffectedReviewLayout();
        selectedEmailNode.innerHTML = `
          <div class="empty">${escapeHtml((selectedEmail && selectedEmail.understanding_message) || "Understanding this email...")}</div>
          <div class="reason-wrap">
            <div class="reason-label">${escapeHtml((selectedEmail && selectedEmail.understanding_label) || "Understanding")}</div>
            <div class="reason">Threadwise is working through the currently selected Gmail email before showing the full judgment.</div>
          </div>
        `;
        teachPanelNode.innerHTML = '<div class="empty">Threadwise is still understanding this email. Teaching controls will appear when the email is ready.</div>';
        return;
      }
      if (!selectedEmail || !selectedEmail.found) {
        affectedReviewOpen = false;
        syncAffectedReviewLayout();
        const hasSnapshotMiss = selectedEmail && selectedEmail.status === "not-in-snapshot";
        const title = hasSnapshotMiss
          ? "Threadwise has not synced this email yet."
          : "Open any email in Gmail and this panel will switch from summary mode into message mode.";
        const reason = hasSnapshotMiss && selectedEmail.reason
          ? `<div style="margin-top:12px;border-radius:14px;background:#fff4dd;padding:12px;color:#8a4b00;line-height:1.45;">${escapeHtml(selectedEmail.reason)}</div>`
          : "";
        const relatedItems = relatedHarnessItemsForContext(currentContext).slice(0, 4);
        const fallbackItems = (((harnessState || {}).needs_attention_items) || []).slice(0, 4);
        const relatedHtml = relatedItems.length
          ? `
            <div class="reason-wrap">
              <div class="reason-label">Closest synced emails</div>
              <div class="empty">These are the best local matches the agent can explain right now.</div>
              <div class="detail-list">${relatedItems.map((item) => `
                <button type="button" class="list-item" data-related-message-id="${escapeHtml(item.message_id)}">
                  <div class="list-item-subject">${escapeHtml(item.subject || "(no subject)")}</div>
                  <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
                </button>
              `).join("")}</div>
            </div>
          `
          : "";
        const fallbackHtml = fallbackItems.length
          ? `
            <div class="reason-wrap">
              <div class="reason-label">Current Queue</div>
              <div class="detail-list">${fallbackItems.map((item) => `
                <button type="button" class="list-item" data-related-message-id="${escapeHtml(item.message_id)}">
                  <div class="list-item-subject">${escapeHtml(item.subject || "(no subject)")}</div>
                  <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
                </button>
              `).join("")}</div>
            </div>
          `
          : "";
        selectedEmailNode.innerHTML = `
          <div class="empty">${title}</div>
          ${reason}
          <div class="reason-wrap">
            <div class="reason-label">${escapeHtml(stepCopy.title)}</div>
            <div class="reason">${escapeHtml(stepCopy.body)}</div>
          </div>
          <div class="empty">Threadwise can explain emails it has already synced. Preview a synced match below, or run a Gmail check from the dashboard to refresh what Threadwise knows.</div>
          <div class="button-row">
            ${relatedItems[0] ? '<button type="button" class="action-button primary" data-action="preview-closest-match">Preview closest synced match</button>' : ""}
            ${fallbackItems[0] ? '<button type="button" class="action-button secondary" data-action="open-needs-attention">Open needs-attention queue</button>' : ""}
          </div>
          ${relatedHtml}
          ${fallbackHtml}
        `;
        teachPanelNode.innerHTML = '<div class="empty">Select a synced email to preview or teach a correction.</div>';
        return;
      }
      const statusClass = selectedEmail.status === "needs-attention" ? "pill status-pill warn-pill" : "pill status-pill";
      const allowedLabels = (((harnessState || {}).sidebar_state || {}).ui_state || {}).allowed_labels || [];
      const labelOptions = allowedLabels.map((option) => {
        const selected = (draftLabel || selectedEmail.internal_label || selectedEmail.suggested_label || "") === option.id ? " selected" : "";
        return `<option value="${escapeHtml(option.id)}"${selected}>${escapeHtml(option.name)}</option>`;
      }).join("");
      const details = selectedEmail.details || {};
      const matchedRuleList = (details.matched_rule_ids || []).length
        ? `<div class="empty">Matched rules: ${escapeHtml((details.matched_rule_ids || []).join(', '))}</div>`
        : "";
      const allClassifications = Array.isArray(selectedEmail.all_classifications) ? selectedEmail.all_classifications : [];
      const allLabelsList = allClassifications.length > 1
        ? `<div class="empty">All labels: ${escapeHtml(allClassifications.join(", "))}</div>`
        : "";
      const unsubscribeReasonList = (details.unsubscribe_reasons || []).length
        ? `<div class="empty">Unsubscribe qualified because: ${escapeHtml((details.unsubscribe_reasons || []).join(', '))}</div>`
        : "";
      const detailsButtonLabel = detailsExpanded ? "Hide details" : "Show details";
      const detailsHtml = detailsExpanded
        ? `
          <div class="empty">Decision source: ${escapeHtml(details.review_action || "n/a")}</div>
          <div class="empty">Label write status: ${escapeHtml(details.write_status || "not written")}</div>
          <div class="empty">Inbox removal status: ${escapeHtml(details.inbox_status || "not removed")}</div>
          <div class="empty">Matched saved rules: ${escapeHtml(String(details.matched_rule_count || 0))}</div>
          ${matchedRuleList}
          ${allLabelsList}
          ${unsubscribeReasonList}
        `
        : '<div class="empty">Open details to inspect decision source, Gmail write status, inbox handling, and matched rules.</div>';
      const unsubscribeLine = selectedEmail.unsubscribe_available
        ? (() => {
      const unsubscribe = selectedEmail.unsubscribe || null;
      const preview = (unsubscribe && unsubscribe.preview) || null;
      const reviewLinkLabel = unsubscribe && unsubscribe.decision_state === "selected"
        ? "Open queued review"
        : "Review all subscriptions";
      const canOpenUnsubscribeUrl = preview
        && preview.url
        && preview.status !== "ready"
        && preview.url.startsWith("mailto:");
      const actions = preview
              ? `
                <div class="button-row" style="margin-top:10px;">
                  ${preview.status === "ready" && !unsubscribeResult ? '<button type="button" class="action-button info" data-action="select-unsubscribe">Queue unsubscribe</button>' : ''}
                  ${canOpenUnsubscribeUrl ? `<a class="action-button quiet" style="display:inline-flex;align-items:center;" href="${escapeHtml(preview.url)}">Open mail unsubscribe</a>` : ''}
                  ${unsubscribe ? `<a class="action-button quiet" style="display:inline-flex;align-items:center;" href="${escapeHtml(unsubscribe.handoff_path || '/unsubscribe-review')}" target="_blank" rel="noreferrer">${escapeHtml(reviewLinkLabel)}</a>` : ''}
                </div>
              `
              : "";
            return `
              <div class="reason-wrap">
                <div class="reason-label">Unsubscribe</div>
                <div class="reason">${escapeHtml((unsubscribe && unsubscribe.display_name) || selectedEmail.sender || "Subscription")}</div>
                <div class="empty">${escapeHtml((preview && preview.notes) || "Unsubscribe available")}</div>
                ${unsubscribeResult ? `<div class="success-card">${escapeHtml(unsubscribeResult)}</div>` : ""}
                ${actions}
              </div>
            `;
          })()
        : "";
      const errorHtml = teachError ? renderTeachError(teachError) : "";
      const resultHtml = teachResult ? `<div class="success-card">${escapeHtml(teachResult)}</div>` : "";
      const feedbackHtml = teachPreview
        ? `${errorHtml}${resultHtml}${renderPreviousTeachPreview(previousTeachPreview)}${renderTeachPreview(teachPreview)}`
        : teachError
          ? errorHtml
          : teachResult
            ? `<div class="success-card">${escapeHtml(teachResult)}</div>`
            : renderPreviousTeachPreview(previousTeachPreview);
      const overviewCard = `
        <div class="reason-wrap">
          <div class="reason-label">Agent view</div>
          <div class="summary-grid" style="margin-top:10px;">
            <div class="metric-button" style="cursor:default;"><strong>${escapeHtml(selectedEmail.classification || "Uncategorized")}</strong><span>category</span></div>
            <div class="metric-button" style="cursor:default;"><strong>${escapeHtml(selectedEmail.status_label || "Unknown")}</strong><span>handling</span></div>
          </div>
        </div>
      `;
      const nextStepCard = `
        <div class="reason-wrap" style="background:${selectedEmail.status === "needs-attention" ? "#fff8eb" : "#eef7f5"};">
          <div class="reason-label">${escapeHtml(stepCopy.title)}</div>
          <div class="reason">${escapeHtml(stepCopy.body)}</div>
        </div>
      `;
      selectedEmailNode.innerHTML = `
        <div class="subject">${escapeHtml(selectedEmail.subject || "(no subject)")}</div>
        <div class="sender">${escapeHtml(selectedEmail.sender || "(unknown sender)")}</div>
        <div class="pill-row">
          <span class="pill classification-pill">${escapeHtml(selectedEmail.classification || "Uncategorized")}</span>
          <span class="${statusClass}">${escapeHtml(selectedEmail.status_label)}</span>
        </div>
        ${overviewCard}
        ${nextStepCard}
        <div class="reason-wrap">
          <div class="reason-label">Why</div>
          <div class="reason">${escapeHtml(selectedEmail.reason || "No short reason is stored yet.")}</div>
        </div>
        <div class="reason-wrap">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <div class="reason-label">Details</div>
            <button type="button" class="action-button secondary" data-action="toggle-details">${escapeHtml(detailsButtonLabel)}</button>
          </div>
          ${detailsHtml}
        </div>
        ${unsubscribeLine}
      `;
      teachPanelNode.innerHTML = `
        <div class="field-stack">
          <textarea id="teach-note" class="textarea" placeholder="What should Threadwise understand?">${escapeHtml(draftNote)}</textarea>
          <details class="empty" style="margin-top:0;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Choose label manually</summary>
            <select id="teach-target-label" class="select" style="margin-top:8px;">${labelOptions}</select>
          </details>
          <div class="button-row">
            <button type="button" class="action-button primary" data-action="preview-teach">Preview</button>
            <button type="button" class="action-button quiet" data-action="clear-teach">Clear draft</button>
          </div>
        </div>
        ${feedbackHtml}
      `;
      const labelNode = document.getElementById("teach-target-label");
      const noteNode = document.getElementById("teach-note");
      if (labelNode) {
        labelNode.addEventListener("change", () => {
          draftLabel = labelNode.value;
        });
      }
      if (noteNode) {
        noteNode.addEventListener("input", () => {
          draftNote = noteNode.value;
        });
      }
    }

    function renderPreviousTeachPreview(previousPreview) {
      if (!previousPreview) {
        return "";
      }
      const impact = previousPreview.impact || {};
      return `
        <div class="note" data-previous-preview="true">
          <div class="reason-label">Previous interpretation</div>
          <div style="margin-top:8px;color:var(--ink);line-height:1.45;font-weight:700;">${escapeHtml(previousPreview.acknowledgment || "Previous preview")}</div>
          <div style="margin-top:6px;color:var(--muted);line-height:1.45;">Matching existing emails: ${impact.matching_existing_count || 0}</div>
        </div>
      `;
    }

    function renderTeachPreview(preview) {
      const impact = preview.impact || {};
      const matchingCount = impact.matching_existing_count || 0;
      const affectedReviewHtml = renderAffectedReview(preview);
      const examples = (impact.matching_existing_examples || []).map((item) =>
        `<li>${escapeHtml(item.subject || "(no subject)")} · ${escapeHtml(item.sender || "(unknown sender)")}</li>`
      ).join("");
      const ruleMeta = `
        <div class="pill-row">
          <span class="pill">${escapeHtml(preview.rule_type_label || "Future rule")}</span>
          <span class="pill ${preview.rule_confidence === "tentative" ? "warn-pill" : "status-pill"}">${escapeHtml(preview.rule_confidence_label || "Future rule")}</span>
        </div>
        ${preview.clarifying_question ? `<div class="empty">${escapeHtml(preview.clarifying_question)}</div>` : ""}
      `;
      return `
        <div class="preview-card">
          <div class="reason-label">This email</div>
          <div style="font-weight:700;margin-top:6px;">${escapeHtml(preview.acknowledgment || "Preview ready.")}</div>
          <div class="empty" style="margin-top:8px;">Fix this email only updates the message you are reviewing.</div>
          <div class="button-row">
            <button type="button" class="action-button primary" data-apply-mode="current-only">Fix this email</button>
          </div>
          <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;">
            <div class="reason-label">Future rule</div>
            <div style="font-weight:700;margin-top:6px;">${escapeHtml(preview.plain_english_rule || "No future rule proposal was generated.")}</div>
            ${ruleMeta}
            <details class="empty" style="margin-top:8px;">
              <summary style="cursor:pointer;font-weight:800;color:#241812;">Structured rule</summary>
              <div style="margin-top:8px;">Hidden until needed.</div>
            </details>
          </div>
          ${renderRuleAmendment(preview.amendment_proposal)}
          <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;">
            <div class="reason-label">Affected existing emails</div>
            <div class="empty" style="margin-top:6px;">Would affect ${matchingCount} matching emails Threadwise has seen.</div>
            ${examples ? `<details style="margin-top:8px;"><summary style="cursor:pointer;font-weight:800;">Show affected emails</summary><ol class="checklist">${examples}</ol></details>` : ""}
            <div class="button-row">
              <button type="button" class="action-button secondary" data-action="open-affected-review" ${matchingCount ? "" : "disabled"}>Review ${matchingCount}</button>
              ${affectedReviewOpen ? '<button type="button" class="action-button info" data-apply-mode="apply-included">Apply to included</button>' : ""}
            </div>
          </div>
          ${affectedReviewHtml}
          <div class="button-row">
            <button type="button" class="action-button future" data-apply-mode="save-future-rule">Teach future rule</button>
            <button type="button" class="action-button secondary" data-action="refine-teach">Keep discussing</button>
          </div>
        </div>
      `;
    }

    function affectedReviewItems(preview) {
      const impact = (preview && preview.impact) || {};
      return impact.matching_existing_items || impact.matching_existing_examples || [];
    }

    function renderRuleAmendment(amendment) {
      if (!amendment || !amendment.status || amendment.status === "accepted" || amendment.status === "rejected") {
        return "";
      }
      const proposedRule = amendment.plain_english_rule || amendment.clarifying_question || "Threadwise needs a clearer boundary before changing the rule.";
      const actions = amendment.status === "proposed"
        ? `
          <div class="button-row" style="margin-top:10px;">
            <button type="button" class="action-button primary" data-amendment-decision="accept">Accept amendment</button>
            <button type="button" class="action-button secondary" data-amendment-decision="reject">Reject</button>
            <button type="button" class="action-button quiet" data-action="refine-teach">Keep reviewing</button>
          </div>
        `
        : "";
      return `
        <div class="reason-wrap" style="background:#eef7f5;">
          <div class="reason-label">Possible rule amendment</div>
          <div class="reason" style="font-weight:800;">${escapeHtml(proposedRule)}</div>
          ${amendment.plain_english_rule && amendment.clarifying_question ? `<div class="empty">${escapeHtml(amendment.clarifying_question)}</div>` : ""}
          <div class="empty">This is only a proposal. Threadwise will not change the rule unless you accept it.</div>
          ${actions}
        </div>
      `;
    }

    function renderAffectedReview(preview) {
      if (!affectedReviewOpen) {
        return "";
      }
      const items = affectedReviewItems(preview);
      const targetLabel = preview && (preview.target_label || preview.proposed_label || draftLabel || "");
      const rows = items.length
        ? items.map((item, index) => `
          <tr>
            <td>${escapeHtml(item.sender || "(unknown sender)")}</td>
            <td class="subject-cell">${escapeHtml(item.subject || "(no subject)")}</td>
            <td>${escapeHtml(item.current_label || item.classification || "Unknown")}</td>
            <td>${escapeHtml(item.proposed_label || targetLabel || "Proposed rule")}</td>
            <td>
              <div style="display:grid;gap:6px;">
                <button type="button" class="action-button quiet" data-affected-open-gmail="${index}">Open in Gmail</button>
                <button type="button" class="action-button secondary" data-affected-exclude="${escapeHtml(item.message_id || "")}">Exclude</button>
                <details class="empty" style="margin:0;">
                  <summary style="cursor:pointer;">Why?</summary>
                  <textarea class="textarea" data-affected-exclusion-reason="${escapeHtml(item.message_id || "")}" placeholder="Optional reason" style="min-height:54px;margin-top:6px;"></textarea>
                </details>
              </div>
            </td>
          </tr>
        `).join("")
        : '<tr><td colspan="5">No exact affected-email examples are available for this preview.</td></tr>';
      return `
        <div class="affected-review" data-affected-review="true">
          <div class="affected-review-header">
            <div>
              <div class="reason-label">Reviewing affected emails</div>
              <div class="empty" style="margin-top:3px;">Exclude saves an exact exception for this rule/email.</div>
            </div>
            <button type="button" class="action-button secondary" data-action="collapse-affected-review">Collapse</button>
          </div>
          <div class="affected-review-table-wrap">
            <table>
              <thead>
                <tr><th>Sender</th><th>Subject</th><th>Current</th><th>Proposed</th><th>Inspect</th></tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>
      `;
    }

    function syncAffectedReviewLayout() {
      if (!harnessShellNode) {
        return;
      }
      harnessShellNode.classList.toggle("expanded-review", affectedReviewOpen);
    }

    function renderTeachError(message) {
      return `
        <div class="error-card">
          <div style="font-weight:800;">Lesson not applied</div>
          <div style="margin-top:8px;">${escapeHtml(message || "Nothing was stored or changed. The preview is still here so you can check the connection and retry without rewriting your note.")}</div>
          <div class="button-row" style="margin-top:12px;">
            <button type="button" class="action-button future" data-action="refresh-state">Check again</button>
            <button type="button" class="action-button primary" data-apply-mode="current-only">Try fix again</button>
          </div>
        </div>
      `;
    }

    function renderDailySummary(summary) {
      const changedToday = summary.changed_today || {};
      const runStatus = (((harnessState || {}).sidebar_state || {}).run_status) || {};
      const selectedUnsubscribeExamples = changedToday.selected_unsubscribe_examples || [];
      const bucketLabel = {
        needs_attention_items: "Needs attention",
        recent_items: "Recent",
        auto_handled_items: "Auto-handled",
        kept_visible_items: "Kept visible",
      }[activeHarnessFilter] || "Queue";
      const topLabels = (summary.top_labels || []).map((label) =>
        `<span class="label-chip">${escapeHtml(label.label)} · ${label.count}</span>`
      ).join("");
      const changedItemsHtml = (changedToday.items || []).length
        ? (changedToday.items || []).map((item) => `
            <button type="button" class="list-item" data-changed-message-id="${escapeHtml(item.message_id || "")}">
              <div class="list-item-subject">${escapeHtml(item.subject || "(no subject)")}</div>
              <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
              <div class="empty">${escapeHtml(item.change_summary || "")}</div>
            </button>
          `).join("")
        : '<div class="empty">No tracked agent changes in this stored batch yet.</div>';
      const queuedSubscriptionsHtml = selectedUnsubscribeExamples.length
        ? `
          <div class="reason-wrap" style="margin-top:12px;background:#fffdfa;">
            <div class="reason-label">Queued subscriptions</div>
            <div class="detail-list">${selectedUnsubscribeExamples.map((item) => `
              <a class="list-item" style="text-decoration:none;" href="${escapeHtml(item.handoff_path || "/unsubscribe-review")}" target="_blank" rel="noreferrer">
                <div class="list-item-subject">${escapeHtml(item.display_name || "(unknown list)")}</div>
                <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
              </a>
            `).join("")}</div>
          </div>
        `
        : "";
      dailySummaryNode.innerHTML = `
        <div class="empty">${summary.run_count > 1 ? `Rolling view across the last ${summary.run_count} Gmail runs` : "Latest run snapshot"}</div>
        <div class="summary-grid">
          <button class="metric-button" data-harness-filter="recent_items"><strong>${summary.processed_count}</strong><span>processed</span></button>
          <button class="metric-button" data-harness-filter="auto_handled_items"><strong>${summary.auto_handled_count}</strong><span>auto-handled</span></button>
          <button class="metric-button" data-harness-filter="needs_attention_items"><strong>${summary.needs_attention_count}</strong><span>need attention</span></button>
          <button class="metric-button" data-harness-filter="kept_visible_items"><strong>${(harnessState && harnessState.kept_visible_items ? harnessState.kept_visible_items.length : summary.unlabeled_count)}</strong><span>kept visible</span></button>
        </div>
        <div class="label-row">
          <span class="label-chip">Unsubscribe candidates · ${summary.unsubscribe_candidate_count || 0}</span>
          <span class="label-chip">Run status · ${escapeHtml(runStatus.status || "idle")}</span>
          ${summary.report_date ? `<span class="label-chip">Latest report · ${escapeHtml(summary.report_date)}</span>` : ""}
        </div>
        <div class="button-row" style="margin-top:12px;">
          <a class="action-button quiet" style="display:inline-flex;align-items:center;" href="${escapeHtml(runStatus.dashboard_path || "/daily-dashboard#run-gmail-check")}" target="_blank" rel="noreferrer">Open daily dashboard</a>
          <a class="action-button quiet" style="display:inline-flex;align-items:center;" href="/unsubscribe-review" target="_blank" rel="noreferrer">Review unsubscribe candidates</a>
        </div>
        <details class="reason-wrap" style="margin-top:12px;">
          <summary style="cursor:pointer;font-weight:800;color:#241812;">Report details</summary>
          <div class="reason-wrap" style="margin-top:12px;background:#eef7f5;">
            <div class="reason-label">Viewing</div>
            <div class="reason"><strong>${escapeHtml(bucketLabel)}</strong> · ${(harnessState && harnessState[activeHarnessFilter] ? harnessState[activeHarnessFilter].length : 0)}</div>
            <div class="empty">${escapeHtml(activeHarnessBucketDescription())}</div>
          </div>
          <div class="reason-wrap" style="margin-top:12px;">
            <div class="reason-label">What Changed Today</div>
            <div class="summary-grid" style="margin-top:10px;">
              <div class="metric-button"><strong>${changedToday.label_writes_count || 0}</strong><span>labels written</span></div>
              <div class="metric-button"><strong>${changedToday.inbox_removed_count || 0}</strong><span>removed from inbox</span></div>
              <div class="metric-button"><strong>${changedToday.taught_count || 0}</strong><span>teaching changes</span></div>
              <div class="metric-button"><strong>${changedToday.selected_unsubscribe_count || 0}</strong><span>unsubscribe queued</span></div>
            </div>
            ${queuedSubscriptionsHtml}
            <div class="detail-list">${changedItemsHtml}</div>
          </div>
          ${(summary.top_labels || []).length ? `<div class="label-row">${topLabels}</div>` : '<p class="empty">No stored label mix yet.</p>'}
          <p class="empty">Source: ${escapeHtml(summary.source_label)}${summary.batch_id ? ` · ${escapeHtml(summary.batch_id)}` : ""}</p>
          <div id="detail-list" class="detail-list"></div>
        </details>
      `;
      renderDetailList();
      wireMetricButtons();
    }

    function renderHarnessList() {
      if (!harnessState || !harnessListNode || !harnessFilterPillsNode) {
        return;
      }
      const filters = [
        ["recent_items", `Recent (${(harnessState.recent_items || []).length})`],
        ["auto_handled_items", `Auto-handled (${(harnessState.auto_handled_items || []).length})`],
        ["kept_visible_items", `Kept visible (${(harnessState.kept_visible_items || []).length})`],
      ];
      if (!filters.some(([key]) => key === activeHarnessFilter)) {
        activeHarnessFilter = "recent_items";
      }
      harnessFilterPillsNode.innerHTML = filters.map(([key, label]) => `
        <button type="button" class="label-chip" data-harness-filter="${key}" style="border:0;cursor:pointer;${key === activeHarnessFilter ? "background:#d8f3ef;color:#0f766e;" : ""}">${escapeHtml(label)}</button>
      `).join("");
      const items = harnessState[activeHarnessFilter] || [];
      if (!items.length) {
        harnessListNode.innerHTML = '<div class="empty">No synced emails in this bucket right now.</div>';
        return;
      }
      harnessListNode.innerHTML = items.map((item) => `
        <button type="button" class="list-item${item.message_id === currentContext.message_id ? " active" : ""}" data-message-id="${escapeHtml(item.message_id)}">
          <div class="list-item-subject">${escapeHtml(item.subject || "(no subject)")}</div>
          <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
          <div class="list-item-pills">
            <span class="label-chip">${escapeHtml(item.classification || "Uncategorized")}</span>
            <span class="label-chip">${escapeHtml(item.status_label || item.status || "")}</span>
          </div>
        </button>
      `).join("");
      harnessListNode.querySelectorAll("[data-message-id]").forEach((button) => {
        button.addEventListener("click", () => {
          const item = items.find((candidate) => candidate.message_id === button.getAttribute("data-message-id"));
          if (!item) {
            return;
          }
          currentContext = {
            provider: "gmail",
            message_id: item.message_id || "",
            subject: item.subject || "",
            sender: item.sender || "",
          };
          resetTeachState(true);
          refreshState();
        });
      });
      harnessFilterPillsNode.querySelectorAll("[data-harness-filter]").forEach((button) => {
        button.addEventListener("click", () => {
          activeHarnessFilter = button.getAttribute("data-harness-filter");
          renderHarnessList();
          renderDetailList();
        });
      });
    }

    function renderDetailList() {
      const node = document.getElementById("detail-list");
      if (!node || !harnessState) {
        return;
      }
      const items = harnessState[activeHarnessFilter] || [];
      if (!items.length) {
        node.innerHTML = "";
        return;
      }
      node.innerHTML = items.slice(0, 6).map((item) => `
        <button type="button" class="list-item${item.message_id === currentContext.message_id ? " active" : ""}" data-message-id="${escapeHtml(item.message_id)}">
          <div class="list-item-subject">${escapeHtml(item.subject || "(no subject)")}</div>
          <div class="list-item-meta">${escapeHtml(item.sender || "(unknown sender)")}</div>
        </button>
      `).join("");
      node.querySelectorAll("[data-message-id]").forEach((button) => {
        button.addEventListener("click", () => {
          const item = items.find((candidate) => candidate.message_id === button.getAttribute("data-message-id"));
          if (!item) {
            return;
          }
          currentContext = {
            provider: "gmail",
            message_id: item.message_id || "",
            subject: item.subject || "",
            sender: item.sender || "",
          };
          resetTeachState(true);
          refreshState();
        });
      });
    }

    function wireMetricButtons() {
      dailySummaryNode.querySelectorAll("[data-harness-filter]").forEach((button) => {
        if (button.getAttribute("data-harness-filter") === activeHarnessFilter) {
          button.classList.add("active");
        }
        button.addEventListener("click", () => {
          activeHarnessFilter = button.getAttribute("data-harness-filter");
          renderHarnessList();
          renderDetailList();
          wireMetricButtons();
        });
      });
    }

    async function refreshState() {
      const query = new URLSearchParams(currentContext);
      const response = await fetch(`/api/harness-state?${query.toString()}`);
      harnessState = await response.json();
      const state = harnessState.sidebar_state;
      currentContext = harnessState.selected_context || currentContext;
      if (state.selected_email && state.selected_email.found && !draftLabel) {
        draftLabel = state.selected_email.internal_label || state.selected_email.suggested_label || "";
      }
      if (!(state.selected_email && state.selected_email.found)) {
        previousTeachPreview = null;
        unsubscribeResult = "";
        detailsExpanded = false;
      }
      renderSelectedEmail(state.selected_email);
      renderDailySummary(state.daily_summary);
      renderHarnessList();
    }

    function resetTeachState(clearDraft) {
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = "";
      teachError = "";
      unsubscribeResult = "";
      affectedReviewOpen = false;
      syncAffectedReviewLayout();
      if (clearDraft) {
        draftLabel = "";
        draftNote = "";
      }
    }

    function selectedEmailFound() {
      return harnessState && harnessState.sidebar_state && harnessState.sidebar_state.selected_email && harnessState.sidebar_state.selected_email.found;
    }

    async function postApi(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return response.json();
    }

    async function previewTeach() {
      if (!selectedEmailFound()) {
        return;
      }
      const labelNode = document.getElementById("teach-target-label");
      const noteNode = document.getElementById("teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      try {
        const payload = await postApi("/api/teach-preview", {
          selected_context: currentContext,
          target_label: draftLabel,
          note: draftNote,
          scope: "sender",
        });
        if (payload.error) {
          teachError = payload.error;
          teachPreview = null;
          teachResult = "";
        } else {
          teachError = "";
          teachResult = "";
          teachPreview = payload;
          affectedReviewOpen = false;
          unsubscribeResult = "";
        }
      } catch (_error) {
        teachError = "Could not preview the lesson.";
        teachPreview = null;
        teachResult = "";
      }
      renderSelectedEmail(harnessState.sidebar_state.selected_email);
    }

    async function applyTeach(mode) {
      if (!selectedEmailFound()) {
        return;
      }
      const labelNode = document.getElementById("teach-target-label");
      const noteNode = document.getElementById("teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      try {
        const payload = await postApi("/api/teach-apply", {
          selected_context: currentContext,
          target_label: draftLabel,
          note: draftNote,
          scope: "sender",
          mode,
        });
        if (payload.error) {
          teachError = payload.error;
          teachResult = "";
          renderSelectedEmail(harnessState.sidebar_state.selected_email);
          return;
        }
        teachPreview = null;
        previousTeachPreview = null;
        affectedReviewOpen = false;
        syncAffectedReviewLayout();
        teachError = "";
        teachResult = payload.acknowledgment || "Lesson applied.";
        unsubscribeResult = "";
        draftLabel = "";
        draftNote = "";
        harnessState.sidebar_state = payload.sidebar_state || harnessState.sidebar_state;
        renderSelectedEmail(harnessState.sidebar_state.selected_email);
        renderDailySummary(harnessState.sidebar_state.daily_summary);
        await refreshState();
      } catch (_error) {
        teachError = "Could not apply the lesson.";
        teachResult = "";
        renderSelectedEmail(harnessState.sidebar_state.selected_email);
      }
    }

    async function excludeAffectedMatch(messageId, reason) {
      if (!selectedEmailFound() || !teachPreview || !messageId) {
        return;
      }
      const labelNode = document.getElementById("teach-target-label");
      const noteNode = document.getElementById("teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      try {
        const payload = await postApi("/api/teach-exclude", {
          selected_context: currentContext,
          target_label: draftLabel,
          note: draftNote,
          scope: "sender",
          excluded_message_id: messageId,
          reason,
        });
        if (payload.error) {
          teachError = payload.error;
          teachResult = "";
        } else {
          teachError = "";
          teachPreview = payload.preview || teachPreview;
          teachResult = "Exception saved. This rule will not apply to this email/pattern later.";
          affectedReviewOpen = true;
        }
      } catch (_error) {
        teachError = "Could not save the exception.";
        teachResult = "";
      }
      renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
    }

    async function decideRuleAmendment(decision) {
      if (!selectedEmailFound() || !teachPreview || !teachPreview.amendment_proposal || !decision) {
        return;
      }
      const labelNode = document.getElementById("teach-target-label");
      const noteNode = document.getElementById("teach-note");
      draftLabel = labelNode ? labelNode.value : draftLabel;
      draftNote = noteNode ? noteNode.value : draftNote;
      try {
        const payload = await postApi("/api/teach-amendment", {
          selected_context: currentContext,
          target_label: draftLabel,
          note: draftNote,
          scope: "sender",
          amendment: teachPreview.amendment_proposal,
          decision,
        });
        if (payload.error) {
          teachError = payload.error;
          teachResult = "";
        } else {
          teachError = "";
          teachPreview = payload.preview || teachPreview;
          draftNote = payload.note || draftNote;
          teachResult = payload.acknowledgment || "Reviewed amendment.";
          affectedReviewOpen = true;
        }
      } catch (_error) {
        teachError = "Could not review the amendment.";
        teachResult = "";
      }
      renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
    }

    minimizeButton.addEventListener("click", () => {
      panelNode.classList.toggle("minimized");
      minimizeButton.textContent = panelNode.classList.contains("minimized") ? "Open" : "Minimize";
    });
    refreshHarnessButton.addEventListener("click", refreshState);
    document.addEventListener("click", (event) => {
      const previewButton = event.target.closest("[data-action='preview-teach']");
      if (previewButton) {
        event.preventDefault();
        previewTeach();
        return;
      }
      const refreshButton = event.target.closest("[data-action='refresh-state']");
      if (refreshButton) {
        event.preventDefault();
        refreshState();
        return;
      }
      const clearButton = event.target.closest("[data-action='clear-teach']");
      if (clearButton) {
        event.preventDefault();
        resetTeachState(true);
        renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
        return;
      }
      const refineButton = event.target.closest("[data-action='refine-teach']");
      if (refineButton) {
        event.preventDefault();
        previousTeachPreview = teachPreview;
        teachPreview = null;
        affectedReviewOpen = false;
        syncAffectedReviewLayout();
        teachError = "";
        teachResult = "";
        renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
        return;
      }
      const openAffectedReviewButton = event.target.closest("[data-action='open-affected-review']");
      if (openAffectedReviewButton) {
        event.preventDefault();
        affectedReviewOpen = true;
        renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
        return;
      }
      const collapseAffectedReviewButton = event.target.closest("[data-action='collapse-affected-review']");
      if (collapseAffectedReviewButton) {
        event.preventDefault();
        affectedReviewOpen = false;
        renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
        return;
      }
      const openAffectedGmailButton = event.target.closest("[data-affected-open-gmail]");
      if (openAffectedGmailButton) {
        event.preventDefault();
        const index = Number(openAffectedGmailButton.getAttribute("data-affected-open-gmail"));
        const item = affectedReviewItems(teachPreview)[index];
        if (item) {
          currentContext = contextFromItem(item);
          refreshState();
        }
        return;
      }
      const excludeAffectedButton = event.target.closest("[data-affected-exclude]");
      if (excludeAffectedButton) {
        event.preventDefault();
        const messageId = excludeAffectedButton.getAttribute("data-affected-exclude") || "";
        const reasonNode = document.querySelector(`[data-affected-exclusion-reason="${CSS.escape(messageId)}"]`);
        excludeAffectedMatch(messageId, reasonNode ? reasonNode.value : "");
        return;
      }
      const amendmentButton = event.target.closest("[data-amendment-decision]");
      if (amendmentButton) {
        event.preventDefault();
        decideRuleAmendment(amendmentButton.getAttribute("data-amendment-decision") || "");
        return;
      }
      const applyButton = event.target.closest("[data-apply-mode]");
      if (applyButton) {
        event.preventDefault();
        applyTeach(applyButton.getAttribute("data-apply-mode"));
        return;
      }
      const unsubscribeButton = event.target.closest("[data-action='select-unsubscribe']");
      if (unsubscribeButton) {
        event.preventDefault();
        unsubscribeSelectCurrent();
        return;
      }
      const detailsButton = event.target.closest("[data-action='toggle-details']");
      if (detailsButton) {
        event.preventDefault();
        detailsExpanded = !detailsExpanded;
        renderSelectedEmail((harnessState || {}).sidebar_state ? harnessState.sidebar_state.selected_email : null);
        return;
      }
      const previewClosestButton = event.target.closest("[data-action='preview-closest-match']");
      if (previewClosestButton) {
        event.preventDefault();
        openHarnessItemPreview(relatedHarnessItemsForContext(currentContext)[0]);
        return;
      }
      const queueButton = event.target.closest("[data-action='open-needs-attention']");
      if (queueButton) {
        event.preventDefault();
        activeHarnessFilter = "needs_attention_items";
        renderHarnessList();
        renderDetailList();
        const firstItem = (((harnessState || {}).needs_attention_items) || [])[0];
        if (firstItem) {
          openHarnessItemPreview(firstItem);
        }
        return;
      }
      const relatedButton = event.target.closest("[data-related-message-id], [data-changed-message-id]");
      if (relatedButton) {
        event.preventDefault();
        const targetId =
          relatedButton.getAttribute("data-related-message-id")
          || relatedButton.getAttribute("data-changed-message-id");
        const item =
          (((harnessState || {}).recent_items) || []).find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).needs_attention_items) || []).find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).auto_handled_items) || []).find((candidate) => candidate.message_id === targetId)
          || (((harnessState || {}).kept_visible_items) || []).find((candidate) => candidate.message_id === targetId);
        openHarnessItemPreview(item);
      }
    });

    refreshState();

    async function unsubscribeSelectCurrent() {
      if (!selectedEmailFound()) {
        return;
      }
      try {
        const payload = await postApi("/api/unsubscribe-select-current", {
          selected_context: currentContext,
        });
        if (payload.error) {
          unsubscribeResult = payload.error;
        } else {
          unsubscribeResult = payload.acknowledgment || "Queued for unsubscribe review.";
        }
        await refreshState();
        renderSelectedEmail(harnessState.sidebar_state.selected_email);
      } catch (_error) {
        unsubscribeResult = "Could not queue the unsubscribe candidate.";
        renderSelectedEmail(harnessState.sidebar_state.selected_email);
      }
    }
  </script>
</body>
</html>"""
