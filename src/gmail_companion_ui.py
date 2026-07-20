import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
from src.gmail_safety_action import GmailSafetyAction
from src.gmail_message_normalizer import normalize_gmail_message
from src.handled_review_store import HandledReviewStore
from src.label_taxonomy import CANONICAL_LABEL_ORDER, gmail_label_name
from src.live_gmail_client import GMAIL_MODIFY_SCOPE, GMAIL_SAFETY_SCOPE
from src.live_protonmail_client import LiveProtonMailClient, SetupError as ProtonSetupError
from src.local_artifacts import write_json_artifact
from src.proton_review_console import ProtonReviewConsole, render_proton_review_page
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
    render_daily_dashboard_page as render_daily_dashboard_page_html,
    render_install_page as render_install_page_html,
    render_panel as render_panel_html,
    render_simulator as render_simulator_html,
    render_unsubscribe_review_page as render_unsubscribe_review_page_html,
    script_safe_json,
    server_origin,
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
from src.companion_teaching_workflow import CompanionTeachingWorkflow, TeachingWriteRequest
from src.teaching_loop import (
    load_items_for_gmail_write_through,
)
from src.semantic_rule_matching import semantic_gmail_search_clauses, semantic_rule_matches_message, semantic_search_keywords


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")
DEFAULT_PROTON_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_PROTON_CREDENTIALS_DIR = Path("data/protonmail_credentials")
DEFAULT_PROTON_ACCOUNT_ID = "founder-proton"
THREADWISE_APP_ICON_PATH = Path("docs/assets/brand/threadwise-app-icon.png")
HEALTH_STATUS_SCHEMA_VERSION = 1
HEALTH_STATUS_PATH = "/api/health"
HEALTH_STATUS_SERVICE_ID = "threadwise-gmail-companion"
HEALTH_STATUS_SERVICE_NAME = "Threadwise Gmail Companion"
HARNESS_STATE_CACHE_SECONDS = 120.0
HEALTH_STATUS_CACHE_SECONDS = 5.0
COMPANION_DATA_CACHE_SECONDS = 120.0
LIVE_INBOX_RECONCILIATION_CACHE_SECONDS = 30.0
LIVE_INBOX_RECONCILIATION_MAX_MESSAGES = 10_000
INBOX_BACKFILL_CONFIRM_THRESHOLD = 200
INBOX_BACKFILL_ESTIMATE_CAP = 25
THREADWISE_APP_VERSION = "0.1.0"


def infer_gmail_account_id(storage_dir: Path) -> str:
    latest_report = load_latest_report(storage_dir)
    if latest_report and latest_report.get("account_id"):
        return latest_report["account_id"]
    latest_batch = load_latest_batch(storage_dir)
    if latest_batch and latest_batch.get("account_id"):
        return latest_batch["account_id"]
    return ""


def default_proton_client_factory(account_id: str, credentials_dir: Path) -> LiveProtonMailClient:
    return LiveProtonMailClient.from_bridge_config(account_id, credentials_dir)


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
        live_inbox_reconciliation_enabled=gmail_check_enabled,
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
        live_inbox_reconciliation_enabled: bool = False,
        gmail_run_runner=None,
        attention_model_client: object | None = None,
        analytics: ProductAnalytics | None = None,
        proton_storage_dir: Path = DEFAULT_PROTON_STORAGE_DIR,
        proton_credentials_dir: Path = DEFAULT_PROTON_CREDENTIALS_DIR,
        proton_account_id: str = DEFAULT_PROTON_ACCOUNT_ID,
        proton_client_factory=None,
        proton_review_console: object | None = None,
    ) -> None:
        self._storage_dir = storage_dir
        self._credentials_dir = credentials_dir
        self._client_secret_path = client_secret_path
        self._gmail_client_factory = gmail_client_factory or default_gmail_client_factory
        self._gmail_write_through_enabled = gmail_write_through_enabled
        self._gmail_check_enabled = gmail_check_enabled
        self._live_inbox_reconciliation_enabled = live_inbox_reconciliation_enabled
        self._gmail_run_runner = gmail_run_runner
        self._attention_model_client = attention_model_client
        self._analytics = analytics or ProductAnalytics.from_environment()
        self._proton_storage_dir = proton_storage_dir
        self._proton_credentials_dir = proton_credentials_dir
        self._proton_account_id = proton_account_id
        self._proton_client_factory = proton_client_factory or default_proton_client_factory
        self._proton_review_console_instance = proton_review_console
        self._proton_review_console_lock = threading.Lock()
        self._analytics_distinct_ids = AnonymousDistinctIdStore(storage_dir)
        self._unsubscribe_store = UnsubscribeInventoryStore(storage_dir)
        self._handled_review_store = HandledReviewStore(storage_dir)
        self._harness_state_cache: dict[str, tuple[float, dict]] = {}
        self._harness_state_lock = threading.Lock()
        self._health_storage_cache: tuple[float, dict] | None = None
        self._health_storage_lock = threading.Lock()
        self._runtime_payload_cache: tuple[float, dict] | None = None
        self._live_inbox_ids_cache: tuple[float, set[str]] | None = None
        self._daily_summary_cache: tuple[float, dict] | None = None
        self._unsubscribe_candidates_cache: tuple[float, list[dict]] | None = None
        self._companion_data_lock = threading.Lock()
        self._async_follow_up_state: dict | None = None
        self._async_follow_up_lock = threading.Lock()
        self._teaching_workflow = CompanionTeachingWorkflow(
            storage_dir,
            write_through=lambda request: self._write_teaching_request_to_gmail(request),
        )

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
            self._capture_workflow_event(
                handler,
                "unsubscribe review opened",
                {"surface": "gmail_companion"},
            )
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

        if handler.command == "GET" and parsed.path == "/proton-review":
            try:
                state = self.proton_review_state()
                self._capture_workflow_event(
                    handler,
                    "proton review opened",
                    {
                        "surface": "proton_review",
                        "queue_size_bucket": bucket_count(state.get("remaining_count", 0)),
                    },
                )
                encoded = render_proton_review_page(state).encode("utf-8")
            except (OSError, ValueError, RuntimeError, ProtonSetupError) as exc:
                self._capture_workflow_event(
                    handler,
                    "proton review failed",
                    {
                        "surface": "proton_review",
                        "decision_type": "open",
                        "error_category": "provider_write_error",
                    },
                )
                encoded = render_proton_review_page({
                    "remaining_count": 0,
                    "reviewed_count": 0,
                    "current": None,
                    "allowed_labels": [],
                }).replace(
                    "Nothing else needs a double check",
                    "Proton review is not available",
                ).replace(
                    "Threadwise will not re-offer the messages you reviewed in this console.",
                    escape_html(str(exc)),
                ).encode("utf-8")
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
                response = self.teach_preview_initial(
                    payload,
                    analytics_distinct_id=self._analytics_distinct_id_from_request(handler),
                )
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                self._capture_workflow_event(
                    handler,
                    "teach/fix failed",
                    {"surface": "gmail_companion", "error_category": "invalid_request"},
                )
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/teach-preview-impact":
            try:
                payload = self._read_json_body(handler)
                response = self.teach_preview_impact(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, HTTPException) as exc:
                self._capture_workflow_event(
                    handler,
                    "teach/fix failed",
                    {"surface": "gmail_companion", "error_category": "teaching_model_error"},
                )
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
                self._capture_workflow_event(
                    handler,
                    "teach/fix failed",
                    {"surface": "gmail_companion", "error_category": "provider_write_error"},
                )
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/safety-preview":
            try:
                return self._write_json(handler, HTTPStatus.OK, self.safety_preview(self._read_json_body(handler)))
            except (KeyError, ValueError, HTTPException) as exc:
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/safety-apply":
            try:
                return self._write_json(handler, HTTPStatus.OK, self.safety_apply(self._read_json_body(handler)))
            except (KeyError, ValueError, HTTPException, RuntimeError) as exc:
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

        if handler.command == "POST" and parsed.path == "/api/handled-review-acknowledge":
            try:
                payload = self._read_json_body(handler)
                response = self.acknowledge_handled_review(payload)
                return self._write_json(handler, HTTPStatus.OK, response)
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

        if handler.command == "POST" and parsed.path == "/api/unsubscribe-candidates/selections":
            try:
                payload = self._read_json_body(handler)
                response = self.save_unsubscribe_selections(
                    payload,
                    analytics_distinct_id=self._analytics_distinct_id_from_request(handler),
                )
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

        if handler.command == "POST" and parsed.path == "/api/proton-review/acknowledge":
            try:
                payload = self._read_json_body(handler)
                response = self._proton_console().acknowledge(str(payload.get("message_id") or ""))
                self._capture_workflow_event(
                    handler,
                    "proton review completed",
                    {
                        "surface": "proton_review",
                        "decision_type": "looks_right",
                        "queue_size_bucket": bucket_count(response.get("remaining_count", 0)),
                        "provider_verified": False,
                    },
                )
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, RuntimeError, ProtonSetupError) as exc:
                self._capture_workflow_event(
                    handler,
                    "proton review failed",
                    {
                        "surface": "proton_review",
                        "decision_type": "looks_right",
                        "error_category": "invalid_request" if isinstance(exc, (KeyError, ValueError)) else "provider_write_error",
                    },
                )
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if handler.command == "POST" and parsed.path == "/api/proton-review/apply-label":
            try:
                payload = self._read_json_body(handler)
                response = self._proton_console().apply_label(
                    str(payload.get("message_id") or ""),
                    str(payload.get("internal_label") or ""),
                )
                self._capture_workflow_event(
                    handler,
                    "proton review completed",
                    {
                        "surface": "proton_review",
                        "decision_type": "add_label",
                        "queue_size_bucket": bucket_count(response.get("remaining_count", 0)),
                        "provider_verified": True,
                    },
                )
                return self._write_json(handler, HTTPStatus.OK, response)
            except (KeyError, ValueError, RuntimeError, ProtonSetupError) as exc:
                self._capture_workflow_event(
                    handler,
                    "proton review failed",
                    {
                        "surface": "proton_review",
                        "decision_type": "add_label",
                        "error_category": "invalid_request" if isinstance(exc, (KeyError, ValueError)) else "provider_write_error",
                    },
                )
                return self._write_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        self._write_json(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def _read_json_body(self, handler: BaseHTTPRequestHandler) -> dict:
        content_length = int(handler.headers.get("Content-Length", "0") or "0")
        raw = handler.rfile.read(content_length) if content_length else b"{}"
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _proton_console(self):
        with self._proton_review_console_lock:
            if self._proton_review_console_instance is None:
                proton_client = self._proton_client_factory(
                    self._proton_account_id,
                    self._proton_credentials_dir,
                )
                self._proton_review_console_instance = ProtonReviewConsole(
                    proton_client=proton_client,
                    classification_ledger_path=self._proton_storage_dir / "live_manual_review_ledger.json",
                    review_state_path=self._proton_storage_dir / "review_console_state.json",
                )
            return self._proton_review_console_instance

    def proton_review_state(self) -> dict:
        return self._proton_console().state()

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

    def _capture_workflow_event(
        self,
        handler: BaseHTTPRequestHandler | None,
        event: str,
        properties: dict[str, object],
        distinct_id: str | None = None,
    ) -> None:
        """Capture coarse workflow telemetry without allowing analytics to break the product."""
        try:
            distinct_id = distinct_id or (
                self._analytics_distinct_id_from_request(handler)
                if handler is not None
                else self._analytics_distinct_ids.get_or_create()
            )
            self._analytics.capture(
                distinct_id=distinct_id,
                event=event,
                properties={
                    "app_version": THREADWISE_APP_VERSION,
                    "workflow_version": ANALYTICS_WORKFLOW_VERSION,
                    "source": "companion_service",
                    **properties,
                },
            )
        except Exception:
            return

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
            "analytics_enabled": self._analytics.enabled,
            "analytics": self._analytics.delivery_status(),
            "storage_summary": self._cached_storage_summary(),
            "capabilities": [
                "sidebar-state",
                "daily-dashboard",
                "gmail-check",
                "attention-feedback",
                "unsubscribe-review",
                "proton-review",
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
            payload = build_companion_runtime_payload(
                self._storage_dir,
                allowed_review_message_ids=self._cached_live_inbox_message_ids(),
            )
            self._runtime_payload_cache = (time.monotonic(), payload)
            return payload

    def _cached_live_inbox_message_ids(self) -> set[str] | None:
        if not self._live_inbox_reconciliation_enabled:
            return None
        now = time.monotonic()
        if self._live_inbox_ids_cache is not None:
            created_at, message_ids = self._live_inbox_ids_cache
            if now - created_at <= LIVE_INBOX_RECONCILIATION_CACHE_SECONDS:
                return message_ids
        latest_batch = load_latest_batch(self._storage_dir) or {}
        account_id = str(latest_batch.get("account_id") or "")
        if not account_id:
            return None
        try:
            gmail_client = self._gmail_client_factory(
                account_id,
                self._credentials_dir,
                self._client_secret_path,
                GMAIL_MODIFY_SCOPE,
            )
            message_ids = {
                str(message_id)
                for message_id in gmail_client.search_message_ids(
                    "in:inbox",
                    LIVE_INBOX_RECONCILIATION_MAX_MESSAGES,
                )
                if message_id
            }
        except Exception:
            return None
        self._live_inbox_ids_cache = (time.monotonic(), message_ids)
        return message_ids

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
            self._live_inbox_ids_cache = None
            self._daily_summary_cache = None
            self._unsubscribe_candidates_cache = None
        with self._harness_state_lock:
            self._harness_state_cache.clear()

    def _run_teach_apply_follow_up_refresh(self, selected_context: dict) -> None:
        try:
            self._invalidate_companion_caches()
            self.sidebar_state(selected_context)
            self._set_async_follow_up_state(
                {
                    "kind": "teach-apply-refresh",
                    "state": "done",
                    "label": "Background refresh done",
                    "message": "Queue summary and follow-up context are ready.",
                }
            )
            cache_key = json.dumps(selected_context or {}, sort_keys=True)
            payload = self._build_harness_state(selected_context)
            with self._harness_state_lock:
                self._harness_state_cache[cache_key] = (time.monotonic(), payload)
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
        unacknowledged_items = [item for item in items if not self._handled_review_store.is_acknowledged(item)]
        selected_context = selected_context or {}
        sidebar_state = self.sidebar_state(selected_context)
        sidebar_state["daily_summary"] = runtime.get("daily_summary") or sidebar_state.get("daily_summary") or {}
        selected_email = dict(sidebar_state.get("selected_email") or {})
        selected_message_id = str(selected_context.get("message_id") or "")
        runtime_selected = next(
            (
                item
                for item in [
                    *(runtime.get("needs_attention_items") or []),
                    *(runtime.get("items") or []),
                ]
                if str(item.get("message_id") or "") == selected_message_id
            ),
            None,
        )
        if runtime_selected is not None:
            for field in (
                "internal_label",
                "suggested_label",
                "classification",
                "status",
                "status_label",
                "action_reason",
                "reason",
            ):
                if runtime_selected.get(field) is not None:
                    selected_email[field] = runtime_selected[field]
        selected_email["handled_review_acknowledged"] = self._handled_review_store.is_acknowledged(selected_email)
        sidebar_state["selected_email"] = selected_email
        return {
            "selected_context": selected_context,
            "sidebar_state": sidebar_state,
            "recent_items": unacknowledged_items[:24],
            "needs_attention_items": list(runtime.get("needs_attention_items") or [])[:12],
            "auto_handled_items": [item for item in unacknowledged_items if item.get("status") == "auto-handled"][:12],
            "kept_visible_items": [item for item in unacknowledged_items if item.get("status") in {"kept-visible", "auto-labeled"}][:12],
            "analytics_status": self._analytics.delivery_status(),
        }

    def acknowledge_handled_review(self, payload: dict) -> dict:
        selected_context = dict(payload.get("selected_context") or {})
        selected_email = self.sidebar_state(selected_context).get("selected_email") or {}
        if not selected_email.get("found"):
            raise ValueError("Selected email is not available for handled review.")
        if selected_email.get("status") not in {"auto-handled", "kept-visible", "auto-labeled"}:
            raise ValueError("Selected email is not a completed handled item.")
        decision = self._handled_review_store.acknowledge(
            provider=selected_email.get("provider") or selected_context.get("provider") or "gmail",
            account_id=selected_email.get("account_id") or selected_context.get("account_id") or "",
            message_id=selected_email.get("message_id") or selected_context.get("message_id") or "",
            batch_id=selected_email.get("batch_id") or "",
        )
        self._invalidate_companion_caches()
        return {
            "acknowledged": True,
            "decision": decision,
            "harness_state": self.harness_state(selected_context),
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
        return self._finish_teach_preview_impact(self._build_teach_preview(payload))

    def teach_preview_initial(
        self,
        payload: dict,
        *,
        analytics_distinct_id: str | None = None,
    ) -> dict:
        self._capture_workflow_event(
            None,
            "teach/fix flow started",
            {"surface": "gmail_companion"},
            distinct_id=analytics_distinct_id,
        )
        preview = self._build_teach_preview(payload, include_existing_impact=False)
        preview["inbox_backfill"] = {
            "state": "working",
            "available": None,
            "estimated_count": 0,
            "is_capped": False,
            "requires_confirmation": False,
            "query": "",
            "matches": [],
        }
        self._capture_workflow_event(
            None,
            "teach/fix preview shown",
            {"surface": "gmail_companion", "preview_outcome": "ready"},
            distinct_id=analytics_distinct_id,
        )
        return preview

    def teach_preview_impact(self, payload: dict) -> dict:
        completed = self._teaching_workflow.finish_preview_impact(payload.get("preview"))
        completed = self._finish_teach_preview_impact(completed)
        completed["inbox_backfill"]["state"] = "ready"
        return completed

    def _build_teach_preview(self, payload: dict, *, include_existing_impact: bool = True) -> dict:
        return self._teaching_workflow.build_preview(
            payload,
            include_existing_impact=include_existing_impact,
        )

    def _finish_teach_preview_impact(self, preview: dict) -> dict:
        preview["inbox_backfill"] = self._build_inbox_backfill_preview(preview)
        remote_matches = list(preview["inbox_backfill"].get("matches") or [])
        existing_items = list(preview.get("impact", {}).get("matching_existing_items") or [])
        if preview["inbox_backfill"].get("available"):
            # Gmail is authoritative for actionable backfill. Local snapshots are
            # retained as learning history, but may contain messages since deleted
            # from the mailbox and must not inflate the preview or be mutated.
            existing_items = []
        combined_by_id = {
            str(item.get("message_id") or ""): item
            for item in [*existing_items, *remote_matches]
            if item.get("message_id")
        }
        combined_items = list(combined_by_id.values())
        combined_was_capped = len(combined_items) > INBOX_BACKFILL_ESTIMATE_CAP
        reviewed_items = combined_items[:INBOX_BACKFILL_ESTIMATE_CAP]
        preview["impact"]["matching_existing_items"] = reviewed_items
        preview["impact"]["matching_existing_examples"] = reviewed_items[:5]
        preview["impact"]["matching_existing_count"] = len(reviewed_items)
        preview["structured_rule"]["applies_to_existing_count"] = len(reviewed_items)
        preview["inbox_backfill"]["is_capped"] = bool(
            preview["inbox_backfill"].get("is_capped") or combined_was_capped
        )
        preview["inbox_backfill"]["requires_confirmation"] = bool(
            preview["inbox_backfill"].get("requires_confirmation") or combined_was_capped
        )
        return preview

    def teach_apply(self, payload: dict, *, analytics_distinct_id: str | None = None) -> dict:
        retry_count = payload.get("retry_count", 0)
        if isinstance(retry_count, int) and retry_count > 0:
            self._capture_workflow_event(
                None,
                "teach/fix retry clicked",
                {"surface": "gmail_companion", "retry_count": min(retry_count, 100)},
                distinct_id=analytics_distinct_id,
            )
        workflow_result = self._teaching_workflow.apply(payload)
        self._capture_label_write_outcomes(
            analytics_distinct_id or self._analytics_distinct_ids.get_or_create(),
            workflow_result.response["mode"],
            workflow_result.write_summary,
        )
        self._start_teach_apply_follow_up_refresh(workflow_result.selected_context)
        self._capture_workflow_event(
            None,
            "teach/fix completed",
            {"surface": "gmail_companion", "flow_outcome": "completed"},
            distinct_id=analytics_distinct_id,
        )
        refreshed = self._fast_sidebar_state(workflow_result.selected_context)
        return {
            **workflow_result.response,
            "sidebar_state": refreshed,
        }

    def safety_preview(self, payload: dict) -> dict:
        selected = self._selected_gmail_message_for_safety(payload)
        return GmailSafetyAction(None, self._storage_dir).preview(
            message_id=selected["message_id"],
            sender=selected["sender"],
            scope=payload.get("scope") or "sender",
        )

    def safety_apply(self, payload: dict) -> dict:
        if not self._gmail_write_through_enabled:
            raise ValueError("Gmail safety actions are disabled for this server.")
        selected = self._selected_gmail_message_for_safety(payload)
        gmail_client = self._gmail_client_factory(
            selected["account_id"],
            self._credentials_dir,
            self._client_secret_path,
            GMAIL_SAFETY_SCOPE,
        )
        result = GmailSafetyAction(gmail_client, self._storage_dir).apply(
            account_id=selected["account_id"],
            message_id=selected["message_id"],
            sender=selected["sender"],
            scope=payload.get("scope") or "sender",
            confirmed=payload.get("confirmed") is True,
        )
        self._invalidate_companion_caches()
        return result

    def _selected_gmail_message_for_safety(self, payload: dict) -> dict:
        selected_context = payload.get("selected_context") or {}
        if selected_context.get("provider") != "gmail" or not selected_context.get("message_id"):
            raise ValueError("Select a Gmail message before applying a suspicious-email action.")
        selected = build_selected_email_state(
            self._storage_dir,
            self._cached_unsubscribe_candidates(),
            selected_context,
        )
        if not selected or selected.get("message_id") != selected_context["message_id"]:
            raise ValueError("The selected Gmail message is no longer available.")
        sender = selected.get("sender") or ""
        if not sender:
            raise ValueError("The selected Gmail message has no usable sender.")
        return {
            "account_id": selected.get("account_id") or infer_gmail_account_id(self._storage_dir),
            "message_id": selected["message_id"],
            "sender": sender,
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
        return {
            **self._teaching_workflow.exclude_match(payload),
            "sidebar_state": self.sidebar_state(selected_context),
        }

    def teach_amendment(self, payload: dict) -> dict:
        selected_context = payload.get("selected_context") or {}
        return {
            **self._teaching_workflow.decide_amendment(payload),
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

    def save_unsubscribe_selections(
        self,
        payload: dict,
        *,
        analytics_distinct_id: str | None = None,
    ) -> dict:
        candidate_keys = payload.get("candidate_keys")
        selected_candidate_keys = payload.get("selected_candidate_keys")
        if not isinstance(candidate_keys, list) or not isinstance(selected_candidate_keys, list):
            raise ValueError("candidate_keys and selected_candidate_keys must be lists.")
        if any(not isinstance(key, str) or not key.strip() for key in candidate_keys):
            raise ValueError("candidate_keys must contain non-empty strings.")
        if any(not isinstance(key, str) or not key.strip() for key in selected_candidate_keys):
            raise ValueError("selected_candidate_keys must contain non-empty strings.")
        candidate_keys = list(dict.fromkeys(key.strip() for key in candidate_keys))
        selected_candidate_keys = list(dict.fromkeys(key.strip() for key in selected_candidate_keys))
        if not set(selected_candidate_keys).issubset(candidate_keys):
            raise ValueError("selected_candidate_keys must be a subset of candidate_keys.")
        known_keys = {
            candidate.get("list_key")
            for candidate in self._unsubscribe_store.list_candidates()
            if candidate.get("list_key")
        }
        unknown_keys = set(candidate_keys).difference(known_keys)
        if unknown_keys:
            raise ValueError("candidate_keys contains an unknown unsubscribe candidate.")

        saved = self._unsubscribe_store.save_selection_states(candidate_keys, selected_candidate_keys)
        self._invalidate_companion_caches()
        selected_count = sum(1 for candidate in saved if candidate.get("decision_state") == "selected")
        self._capture_workflow_event(
            None,
            "unsubscribe review completed",
            {
                "surface": "gmail_companion",
                "reviewed_count_bucket": bucket_count(len(candidate_keys)),
                "review_outcome": "saved" if selected_count else "cleared",
            },
            distinct_id=analytics_distinct_id,
        )
        return {
            "acknowledgment": (
                f"Saved {selected_count} queued selection{'s' if selected_count != 1 else ''}. "
                "Nothing was unsubscribed."
            ),
            "candidate_count": len(saved),
            "selected_count": selected_count,
            "selected_candidate_keys": selected_candidate_keys,
            "gmail_mutation": "none",
            "execution": "none",
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
        response = trigger_dashboard_gmail_check(self._storage_dir, payload, runner)
        self._invalidate_companion_caches()
        return response

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
        included_message_ids: set[str] | None = None,
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
                included_message_ids=included_message_ids or set(),
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

    def _write_teaching_request_to_gmail(self, request: TeachingWriteRequest) -> dict:
        return self._write_teach_result_to_gmail(
            request.account_id,
            request.current_message_id,
            request.mode,
            request.preview_matches,
            semantic_rule=request.semantic_rule,
            current_subject=request.current_subject,
            current_sender=request.current_sender,
            included_message_ids=set(request.included_message_ids),
        )

    def _build_inbox_backfill_preview(self, preview: dict) -> dict:
        if not self._gmail_write_through_enabled:
            return {
                "available": False,
                "estimated_count": 0,
                "requires_confirmation": False,
                "query": "",
                "matches": [],
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
                "matches": [],
            }
        try:
            gmail_client = self._gmail_client_factory(
                account_id,
                self._credentials_dir,
                self._client_secret_path,
                GMAIL_MODIFY_SCOPE,
            )
            candidate_ids = gmail_client.search_message_ids(query, INBOX_BACKFILL_ESTIMATE_CAP + 1)
        except Exception:
            return {
                "available": False,
                "estimated_count": 0,
                "requires_confirmation": False,
                "query": query,
                "matches": [],
            }
        if not hasattr(gmail_client, "get_message"):
            return {
                "available": False,
                "estimated_count": 0,
                "is_capped": len(candidate_ids) > INBOX_BACKFILL_ESTIMATE_CAP,
                "requires_confirmation": False,
                "query": query,
                "matches": [],
            }
        semantic_rule = preview.get("semantic_rule") or {}
        selected_id = str(preview.get("selected_message_id") or "")
        seen: set[str] = set()
        inspect_ids: list[str] = []
        for message_id in candidate_ids[:INBOX_BACKFILL_ESTIMATE_CAP]:
            if not message_id or message_id == selected_id or message_id in seen:
                continue
            seen.add(message_id)
            inspect_ids.append(message_id)

        def inspect_message(message_id: str) -> dict | None:
            try:
                normalized = normalize_gmail_message(account_id, gmail_client.get_message(message_id))
            except Exception:
                return None
            if not semantic_rule_matches_message(semantic_rule, normalized):
                return None
            return {
                **normalized,
                "labels_before": [],
                "labels_after": [preview.get("semantic_rule", {}).get("target_label") or (preview.get("selected_label_after") or [""])[0]],
                "source": "gmail-live-preview",
            }

        inspected_matches: list[dict] = []
        if inspect_ids:
            worker_count = min(16, len(inspect_ids))
            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="threadwise-preview") as executor:
                inspected_matches = [match for match in executor.map(inspect_message, inspect_ids) if match]
        estimated_count = len(inspected_matches)
        capped = len(candidate_ids) > INBOX_BACKFILL_ESTIMATE_CAP
        return {
            "available": True,
            "estimated_count": estimated_count,
            "is_capped": capped,
            "requires_confirmation": estimated_count > INBOX_BACKFILL_CONFIRM_THRESHOLD or capped,
            "query": query,
            "matches": inspected_matches,
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
        included_message_ids: set[str],
    ) -> dict:
        filtered_ids = sorted(
            message_id
            for message_id in included_message_ids
            if message_id and message_id not in excluded_message_ids
        )
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
        sender_domain = str((semantic_rule or {}).get("sender_domain") or "").strip().lower().lstrip("@")
        semantic_pattern = (semantic_rule or {}).get("semantic_pattern") or ""
        rule_type = (semantic_rule or {}).get("rule_type") or ""
        if rule_type == "sender-domain" and sender_domain:
            return f"from:{sender_domain}"
        include_clauses, exclude_clauses = semantic_gmail_search_clauses(semantic_rule)
        subject_keywords = semantic_search_keywords(semantic_rule) or self._query_keywords_for_semantic_pattern(semantic_pattern, current_subject)
        parts: list[str] = []
        if sender and "@" in sender and rule_type != "cross-sender-semantic":
            parts.append(f"from:{sender}")
        if include_clauses:
            if len(include_clauses) == 1:
                parts.append(include_clauses[0])
            else:
                parts.append("{" + " ".join(include_clauses) + "}")
            parts.extend(exclude_clauses)
        elif subject_keywords:
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

    def render_simulator(self) -> str:
        return render_simulator_html()

    def render_install_page(self, host_header: str) -> str:
        return render_install_page_html(
            origin=server_origin(host_header),
            extension_path=str((Path.cwd() / "extensions" / "gmail_companion").resolve()),
        )

    def render_unsubscribe_review_page(self, query: dict[str, list[str]] | None = None) -> str:
        query = query or {}
        focus_list_key = first_query_value(query, "list_key")
        details = [
            build_unsubscribe_detail(candidate, self._storage_dir)
            for candidate in self._unsubscribe_store.list_candidates()
        ]
        return render_unsubscribe_review_page_html(
            details,
            focus_list_key=focus_list_key,
        )

    def render_daily_dashboard_page(self) -> str:
        return render_daily_dashboard_page_html(
            payload=self._cached_runtime_payload(),
            attention_summary=build_daily_attention_summary(self._storage_dir),
            run_status=load_gmail_dashboard_run_status(self._storage_dir),
            inferred_account_id=infer_gmail_account_id(self._storage_dir),
            gmail_check_enabled=self._gmail_check_enabled,
        )

    def render_panel(self) -> str:
        return render_panel_html()
