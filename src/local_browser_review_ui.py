import json
import argparse
from collections import Counter
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

from src.gmail_fetcher import GmailBatchFetcher
from src.label_taxonomy import allowed_gmail_labels, gmail_label_name
from src.live_gmail_client import LiveGmailClient, SetupError
from src.local_batch_summary import load_batch, summarize_batch
from src.review_loop import FixtureReviewLoop
from src.shadow_label_eval import OpenAIShadowLabelClient, ShadowLabelEvaluator
from src.stored_batch_review_store import StoredBatchReviewStore
from src.trusted_sender_store import TrustedSenderStore
from src.unsubscribe_execution import UnsubscribeExecutor
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve a local browser review UI for stored Gmail batches without Gmail writes."
    )
    parser.add_argument("--batch-id")
    parser.add_argument("--storage-dir", type=Path, default=DEFAULT_STORAGE_DIR)
    parser.add_argument("--account-id")
    parser.add_argument("--credentials-dir", type=Path, default=DEFAULT_CREDENTIALS_DIR)
    parser.add_argument("--client-secret-path", type=Path)
    parser.add_argument("--fetch-batch-size", type=int, default=50)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
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
        args.batch_id,
        args.account_id,
        args.credentials_dir,
        args.client_secret_path,
        args.fetch_batch_size,
    )
    try:
        if args.batch_id:
            output.write(
                f"Serving stored batch review UI for {args.batch_id} at "
                f"http://{args.host}:{server.server_port}\n"
            )
        else:
            output.write(
                f"Serving stored batch review UI workbench at "
                f"http://{args.host}:{server.server_port}\n"
            )
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        output.write("Stopped local browser review UI.\n")
        return 0
    finally:
        server.server_close()


def create_server(
    host: str,
    port: int,
    storage_dir: Path,
    batch_id: str | None,
    account_id: str | None = None,
    credentials_dir: Path = DEFAULT_CREDENTIALS_DIR,
    client_secret_path: Path | None = None,
    fetch_batch_size: int = 50,
) -> ThreadingHTTPServer:
    app = LocalBrowserReviewApp(
        storage_dir=storage_dir,
        batch_id=batch_id,
        account_id=account_id,
        fetch_batch_fn=_build_live_fetch_batch_fn(
            storage_dir=storage_dir,
            credentials_dir=credentials_dir,
            client_secret_path=client_secret_path,
            batch_size=fetch_batch_size,
        ),
        run_shadow_eval_fn=_build_shadow_eval_fn(storage_dir=storage_dir),
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            app.handle_request(self)

        def do_POST(self) -> None:
            app.handle_request(self)

        def log_message(self, format: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


class LocalBrowserReviewApp:
    def __init__(
        self,
        storage_dir: Path,
        batch_id: str | None,
        fetch_batch_fn=None,
        account_id: str | None = None,
        run_shadow_eval_fn=None,
    ) -> None:
        self._storage_dir = storage_dir
        self._batch_id = batch_id
        self._store = StoredBatchReviewStore(storage_dir)
        self._unsubscribe_store = UnsubscribeInventoryStore(storage_dir)
        self._unsubscribe_executor = UnsubscribeExecutor(storage_dir)
        self._fetch_batch_fn = fetch_batch_fn
        self._account_id = account_id
        self._run_shadow_eval_fn = run_shadow_eval_fn
        self._batch_item_context_index: dict[tuple[str, str], dict] | None = None

    def handle_request(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if handler.command == "GET" and parsed.path == "/":
            selected_batch_id = parse_qs(parsed.query).get("batch_id", [self._batch_id])[0]
            selected_evaluation_id = parse_qs(parsed.query).get("evaluation_id", [None])[0]
            encoded = self.render_page(selected_batch_id, selected_evaluation_id).encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        status_code, payload = self.handle_api_request(handler.command, handler.path, self._read_json_body(handler))
        encoded = json.dumps(payload).encode("utf-8")
        handler.send_response(status_code)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)

    def render_page(self, selected_batch_id: str | None = None, selected_evaluation_id: str | None = None) -> str:
        if selected_evaluation_id:
            heading = f"Shadow evaluation {selected_evaluation_id}"
            subheading = (
                "Compare the current reviewed labels against OpenAI shadow suggestions. "
                "Only disagreements are shown here."
            )
            batch_id = ""
            try:
                body_html = self._render_shadow_evaluation(selected_evaluation_id)
            except Exception as exc:
                message = str(exc)
                if isinstance(exc, FileNotFoundError):
                    message = f"Unknown evaluation id: {selected_evaluation_id}"
                body_html = (
                    '<section class="panel error-panel"><h2>Could not load shadow evaluation.</h2>'
                    f'<p class="meta">{escape(message)}</p></section>'
                )
            return self._render_document(heading, subheading, batch_id, body_html)

        active_batch_id = selected_batch_id if selected_batch_id is not None else self._batch_id
        if active_batch_id is None:
            body_html = self._render_workbench()
            heading = "Stored batch workbench"
            subheading = (
                "Local-only review workbench. Open stored batches here. "
                "No Gmail fetches or writes happen in this surface."
            )
            batch_id = ""
        else:
            heading = f"Review stored batch {active_batch_id}"
            subheading = (
                "Local-only review surface. Decisions are saved to the stored batch. "
                "No Gmail fetches or writes happen here."
            )
            batch_id = active_batch_id
            try:
                batch = self._load_batch(active_batch_id)
                items = batch["items"]
                pending_items = [item for item in items if item.get("review_state") != "reviewed"]
                body_html = self._render_summary(_build_summary(items))
                if pending_items:
                    body_html += self._render_pending_items(active_batch_id, pending_items)
                else:
                    body_html += (
                        '<section class="panel"><h2>No pending items remain for this batch.</h2>'
                        '<p class="meta">All review decisions are already saved locally. '
                        'Reviewed items remain frozen by the existing review contract.</p></section>'
                    )
            except Exception as exc:
                message = str(exc)
                if isinstance(exc, FileNotFoundError):
                    message = f"Unknown batch id: {active_batch_id}"
                body_html = (
                    '<section class="panel error-panel"><h2>Could not load stored batch.</h2>'
                    f'<p class="meta">{escape(message)}</p></section>'
                )
        return self._render_document(heading, subheading, batch_id, body_html)

    def _render_document(self, heading: str, subheading: str, batch_id: str, body_html: str) -> str:
        return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stored Batch Review</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3efe4;
      --panel: #fffdf8;
      --ink: #1f1a14;
      --muted: #6b6255;
      --line: #d7cfbf;
      --accent: #0f766e;
      --accent-soft: #d8f3ef;
      --error: #9f1239;
    }
    body { margin: 0; font-family: Georgia, "Times New Roman", serif; background: linear-gradient(180deg, #f7f1e7 0%, var(--bg) 100%); color: var(--ink); }
    main { max-width: 1100px; margin: 0 auto; padding: 32px 20px 60px; }
    h1 { margin-bottom: 8px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 10px 30px rgba(31, 26, 20, 0.06); margin-bottom: 20px; }
    .error-panel { border-color: #f0b7c5; background: #fff5f7; color: var(--error); }
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
    .metric { background: #f8f5ed; border-radius: 12px; padding: 12px; }
    .items { display: grid; gap: 16px; }
    .item { border: 1px solid var(--line); border-radius: 14px; padding: 16px; background: #fffdfa; }
    .taxonomy { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .taxonomy-option { border: 1px solid var(--line); background: white; border-radius: 999px; padding: 8px 12px; cursor: pointer; }
    .taxonomy-option.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
    .actionability { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .actionability-option { border: 1px solid var(--line); background: white; border-radius: 999px; padding: 8px 12px; cursor: pointer; }
    .actionability-option.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
    .actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
    .action { border: 0; border-radius: 999px; padding: 10px 14px; cursor: pointer; background: var(--ink); color: white; }
    .secondary { background: #ebe4d7; color: var(--ink); }
    .danger { background: #7f1d1d; color: white; }
    .meta { color: var(--muted); font-size: 0.95rem; }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #f0eadf; margin-right: 6px; margin-top: 6px; }
    .field { margin: 6px 0; }
    .field strong { display: inline-block; min-width: 92px; }
    details.context-panel { margin-top: 12px; padding: 12px; border: 1px dashed var(--line); border-radius: 12px; background: #fcf8f0; }
    details.context-panel summary { cursor: pointer; font-weight: 600; }
    .context-copy { margin-top: 10px; white-space: pre-wrap; overflow-wrap: anywhere; }
    .compare-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 12px; }
    .compare-card { border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: #f8f5ed; }
    .compare-card h3 { margin-top: 0; margin-bottom: 10px; font-size: 1rem; }
    .unsubscribe-row { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; }
    .checkbox { margin-top: 6px; width: 18px; height: 18px; }
    #fetch-status { position: sticky; top: 0; z-index: 5; }
    .status-banner { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; border-radius: 12px; padding: 12px 14px; margin: 12px 0 20px; }
  </style>
</head>
<body>
  <main>
    <h1>__HEADING__</h1>
    <p class="meta">__SUBHEADING__</p>
    <div id="fetch-status" class="meta"></div>
    __BODY_HTML__
  </main>
  <script>
    const labelMap = {
      "EA/Travel": "travel",
      "EA/Receipts": "receipt-billing",
      "EA/Orders": "shopping-order",
      "EA/Finance": "financial-account",
      "EA/Newsletter": "newsletter",
      "EA/Promotions": "promotions",
      "EA/Account": "account-security",
      "EA/Calendar": "calendar-event",
      "EA/Personal": "personal",
      "EA/Work": "job-related",
      "EA/LowValue": "spam-low-value",
      "EA/ReplyNeeded": "reply-needed"
    };
    function selectedLabels(card) {
      return [...card.querySelectorAll(".taxonomy-option.active")].map((button) => labelMap[button.dataset.label]);
    }
    function selectedActionability(card) {
      const active = card.querySelector(".actionability-option.active");
      return active ? active.dataset.actionability : null;
    }
    async function saveDecision(card, decision) {
      const payload = {
        message_id: card.dataset.messageId,
        decision,
        final_labels: decision === "edit" ? selectedLabels(card) : [],
        actionability: selectedActionability(card)
      };
      const response = await fetch("/api/batches/__BATCH_ID__/decisions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const errorPayload = await response.json();
        window.alert(errorPayload.error || "Failed to save review decision.");
        return;
      }
      window.location.reload();
    }
    async function fetchAnotherBatch() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Fetching another batch...";
      }
      const response = await fetch("/api/fetch-batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not fetch another batch.";
        }
        return;
      }
      if (!payload.batch_id) {
        if (statusNode) {
          statusNode.textContent = "No new messages found.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Fetched ${payload.fetched_count} new messages into ${payload.batch_id}.`;
      }
      window.location.href = `/?batch_id=${encodeURIComponent(payload.batch_id)}`;
    }
    async function savePreference(card, preference) {
      const payload = {
        item_key: card.dataset.itemKey,
        preference
      };
      const response = await fetch(`/api/evaluations/${encodeURIComponent(card.dataset.evaluationId)}/preferences`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const errorPayload = await response.json();
        window.alert(errorPayload.error || "Failed to save evaluation preference.");
        return;
      }
      window.location.reload();
    }
    async function runShadowEvaluation() {
      const statusNode = document.getElementById("fetch-status");
      if (statusNode) {
        statusNode.textContent = "Running OpenAI comparison over 100 reviewed messages...";
      }
      const response = await fetch("/api/evaluations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not run OpenAI comparison.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved ${payload.evaluation_id} with ${payload.comparison_count} disagreements to review.`;
      }
      window.location.href = `/?evaluation_id=${encodeURIComponent(payload.evaluation_id)}`;
    }
    async function saveUnsubscribeSelections() {
      const statusNode = document.getElementById("fetch-status");
      const candidateCheckboxes = [...document.querySelectorAll(".unsubscribe-checkbox")];
      const payload = {
        candidate_keys: candidateCheckboxes.map((checkbox) => checkbox.dataset.candidateKey),
        selected_candidate_keys: candidateCheckboxes
          .filter((checkbox) => checkbox.checked)
          .map((checkbox) => checkbox.dataset.candidateKey)
      };
      const response = await fetch("/api/unsubscribe-candidates/selections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const responsePayload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = responsePayload.error || "Could not save unsubscribe selections.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Saved ${responsePayload.saved_count} unsubscribe selections locally.`;
      }
      window.alert(`Saved ${responsePayload.saved_count} unsubscribe selections locally.`);
      window.location.reload();
    }
    async function previewUnsubscribeExecution() {
      const statusNode = document.getElementById("fetch-status");
      const response = await fetch("/api/unsubscribe-executions/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not preview unsubscribe execution.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Preview: ${payload.ready_count} ready, ${payload.unsupported_count} unsupported.`;
      }
      window.alert(`Execution preview:\nReady now: ${payload.ready_count}\nManual follow-up: ${payload.unsupported_count}`);
    }
    async function executeUnsubscribes() {
      const confirmation = window.prompt("Type UNSUBSCRIBE to execute supported selected unsubscribes.");
      if (confirmation === null) {
        return;
      }
      const statusNode = document.getElementById("fetch-status");
      const response = await fetch("/api/unsubscribe-executions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation })
      });
      const payload = await response.json();
      if (!response.ok) {
        if (statusNode) {
          statusNode.textContent = payload.error || "Could not execute unsubscribes.";
        }
        return;
      }
      if (statusNode) {
        statusNode.textContent = `Executed ${payload.executed_count} selected unsubscribes. ${payload.unsupported_count} require manual follow-up.`;
      }
      window.alert(`Execution complete:\nExecuted: ${payload.executed_count}\nManual follow-up: ${payload.unsupported_count}\nFailed: ${payload.failed_count}`);
      window.location.reload();
    }
    const fetchBatchButton = document.getElementById("fetch-batch");
    if (fetchBatchButton) {
      fetchBatchButton.addEventListener("click", fetchAnotherBatch);
    }
    const runShadowEvalButton = document.getElementById("run-shadow-eval");
    if (runShadowEvalButton) {
      runShadowEvalButton.addEventListener("click", runShadowEvaluation);
    }
    const saveUnsubscribeButton = document.getElementById("save-unsubscribe-selections");
    if (saveUnsubscribeButton) {
      saveUnsubscribeButton.addEventListener("click", saveUnsubscribeSelections);
    }
    const previewUnsubscribeButton = document.getElementById("preview-unsubscribe-execution");
    if (previewUnsubscribeButton) {
      previewUnsubscribeButton.addEventListener("click", previewUnsubscribeExecution);
    }
    const executeUnsubscribeButton = document.getElementById("execute-unsubscribes");
    if (executeUnsubscribeButton) {
      executeUnsubscribeButton.addEventListener("click", executeUnsubscribes);
    }
    for (const button of document.querySelectorAll(".taxonomy-option")) {
      button.addEventListener("click", () => button.classList.toggle("active"));
    }
    for (const card of document.querySelectorAll(".item")) {
      const actionabilityButtons = card.querySelectorAll(".actionability-option");
      for (const button of actionabilityButtons) {
        button.addEventListener("click", () => {
          for (const option of actionabilityButtons) {
            option.classList.remove("active");
          }
          button.classList.add("active");
        });
      }
    }
    for (const card of document.querySelectorAll(".item")) {
      const approveButton = card.querySelector(".approve");
      const saveButton = card.querySelector(".save");
      const unlabeledButton = card.querySelector(".unlabeled");
      const rejectButton = card.querySelector(".reject");
      if (!approveButton || !saveButton || !unlabeledButton || !rejectButton) {
        continue;
      }
      approveButton.addEventListener("click", () => saveDecision(card, "approve"));
      saveButton.addEventListener("click", () => saveDecision(card, "edit"));
      unlabeledButton.addEventListener("click", () => {
        for (const option of card.querySelectorAll(".taxonomy-option")) {
          option.classList.remove("active");
        }
        saveDecision(card, "edit");
      });
      rejectButton.addEventListener("click", () => saveDecision(card, "reject"));
    }
    for (const card of document.querySelectorAll(".comparison-item")) {
      const reviewedButton = card.querySelector(".prefer-reviewed");
      const openaiButton = card.querySelector(".prefer-openai");
      if (!reviewedButton || !openaiButton) {
        continue;
      }
      reviewedButton.addEventListener("click", () => savePreference(card, "reviewed"));
      openaiButton.addEventListener("click", () => savePreference(card, "openai"));
    }
  </script>
</body>
</html>""".replace("__BATCH_ID__", escape(batch_id)).replace("__HEADING__", escape(heading)).replace(
            "__SUBHEADING__", escape(subheading)
        ).replace("__BODY_HTML__", body_html)

    def handle_api_request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        parsed = urlparse(path)
        requested_batch_id = _requested_batch_id(parsed.path)
        if requested_batch_id is not None and method == "GET":
            try:
                batch = self._load_batch(requested_batch_id)
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown batch id"}

            return HTTPStatus.OK, {
                "batch_id": batch["batch_id"],
                "allowed_labels": allowed_gmail_labels(),
                "summary": _build_summary(batch["items"]),
                "items": [_serialize_item(item) for item in batch["items"]],
            }

        requested_batch_id = _requested_decision_batch_id(parsed.path)
        if requested_batch_id is not None and method == "POST":
            try:
                updated_batch, updated_item = self._apply_decision(requested_batch_id, body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown batch id"}
            except ValueError as exc:
                return HTTPStatus.CONFLICT, {"error": str(exc)}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid review payload: {exc}"}
            except Exception as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not save review decision: {exc}"}

            return HTTPStatus.OK, {
                "item": _serialize_item(updated_item),
                "summary": _build_summary(updated_batch["items"]),
            }

        if parsed.path == "/api/fetch-batches" and method == "POST":
            if self._fetch_batch_fn is None:
                return HTTPStatus.CONFLICT, {"error": "Browser fetch is not configured."}
            account_id = self._default_account_id()
            if account_id is None:
                return HTTPStatus.CONFLICT, {"error": "No stored account is available for fetch."}
            try:
                review_queue = self._fetch_batch_fn(account_id)
            except Exception as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not fetch a new batch: {exc}"}
            if review_queue is None:
                return HTTPStatus.OK, {"batch_id": None, "fetched_count": 0}
            return HTTPStatus.OK, {
                "batch_id": review_queue["batch_id"],
                "fetched_count": len(review_queue["items"]),
                "fetch_failure_count": len(review_queue.get("fetch_failures", [])),
            }

        if parsed.path == "/api/evaluations" and method == "POST":
            if self._run_shadow_eval_fn is None:
                return HTTPStatus.CONFLICT, {"error": "OpenAI comparison is not configured."}
            try:
                evaluation = self._run_shadow_eval_fn(100)
            except Exception as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not run OpenAI comparison: {exc}"}
            return HTTPStatus.OK, evaluation

        if parsed.path == "/api/unsubscribe-candidates" and method == "GET":
            return HTTPStatus.OK, {"candidates": self._unsubscribe_store.list_candidates()}

        if parsed.path == "/api/unsubscribe-candidates/selections" and method == "POST":
            try:
                saved_candidates = self._unsubscribe_store.save_selection_states(
                    body.get("candidate_keys", []),
                    body.get("selected_candidate_keys", []),
                )
            except Exception as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not save unsubscribe selections: {exc}"}
            return HTTPStatus.OK, {"saved_count": len(saved_candidates), "candidates": saved_candidates}

        if parsed.path == "/api/unsubscribe-executions/preview" and method == "POST":
            return HTTPStatus.OK, self._unsubscribe_executor.preview_selected_candidates()

        if parsed.path == "/api/unsubscribe-executions" and method == "POST":
            if (body or {}).get("confirmation") != "UNSUBSCRIBE":
                return HTTPStatus.CONFLICT, {
                    "error": "Execution requires explicit confirmation. Type UNSUBSCRIBE to continue."
                }
            try:
                return HTTPStatus.OK, self._unsubscribe_executor.execute_selected_candidates()
            except Exception as exc:
                return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Could not execute unsubscribes: {exc}"}

        requested_evaluation_id = _requested_evaluation_id(parsed.path)
        if requested_evaluation_id is not None and method == "GET":
            try:
                evaluation = self._load_evaluation(requested_evaluation_id)
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown evaluation id"}
            return HTTPStatus.OK, evaluation

        requested_evaluation_preference_id = _requested_evaluation_preference_id(parsed.path)
        if requested_evaluation_preference_id is not None and method == "POST":
            try:
                evaluation = self._save_evaluation_preference(requested_evaluation_preference_id, body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown evaluation id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid evaluation payload: {exc}"}
            return HTTPStatus.OK, evaluation

        return HTTPStatus.NOT_FOUND, {"error": "Not found"}

    def _read_json_body(self, handler: BaseHTTPRequestHandler) -> dict | None:
        content_length = int(handler.headers.get("Content-Length", "0"))
        if content_length == 0:
            return None
        return json.loads(handler.rfile.read(content_length).decode("utf-8"))

    def _load_batch(self, requested_batch_id: str) -> dict:
        self._require_known_batch_id(requested_batch_id)
        stored_batch = self._store.load_batch(requested_batch_id)
        review_queue = self._store.to_review_queue(stored_batch)
        review_loop = FixtureReviewLoop(fixtures_dir=self._storage_dir)
        review_loop.load_review_queue(review_queue)
        return review_loop.load_fixture_batch(requested_batch_id)

    def _apply_decision(self, requested_batch_id: str, payload: dict) -> tuple[dict, dict]:
        self._require_known_batch_id(requested_batch_id)
        stored_batch = self._store.load_batch(requested_batch_id)
        review_queue = self._store.to_review_queue(stored_batch)
        review_loop = FixtureReviewLoop(fixtures_dir=self._storage_dir)
        review_loop.load_review_queue(review_queue)

        updated_item = review_loop.review_message(
            requested_batch_id,
            payload["message_id"],
            {
                "type": payload["decision"],
                "final_labels": payload.get("final_labels", []),
                "actionability": payload.get("actionability"),
            },
        )
        updated_batch = review_loop.load_fixture_batch(requested_batch_id)
        self._store.persist_reviewed_items(requested_batch_id, updated_batch["items"])
        return updated_batch, updated_item

    def _require_known_batch_id(self, requested_batch_id: str) -> None:
        if self._batch_id is None:
            return
        if requested_batch_id != self._batch_id:
            raise FileNotFoundError(requested_batch_id)

    def _render_workbench(self) -> str:
        reminder_html = self._render_threshold_reminders()
        trusted_sender_html = self._render_trusted_sender_summary()
        unsubscribe_inventory_html = self._render_unsubscribe_inventory()
        shadow_eval_html = self._render_shadow_eval_summary()
        batch_cards = "".join(self._render_batch_card(summary) for summary in self._list_batch_summaries())
        if not batch_cards:
            batch_cards = '<div class="meta">No stored batches found yet.</div>'
        return (
            '<section class="panel"><h2>Workbench actions</h2>'
            '<div class="actions">'
            '<button type="button" class="action" id="fetch-batch">Fetch another batch</button>'
            '<button type="button" class="action secondary" id="run-shadow-eval">Run OpenAI comparison for 100 reviewed messages</button>'
            '</div>'
            '<p class="meta">The OpenAI comparison sends stored reviewed message content to OpenAI only when you trigger it explicitly.</p>'
            '</section>'
            +
            reminder_html
            +
            trusted_sender_html
            +
            unsubscribe_inventory_html
            +
            shadow_eval_html
            +
            '<section class="panel">'
            '<h2>Stored batches</h2>'
            '<div class="items">'
            f"{batch_cards}"
            "</div>"
            "</section>"
        )

    def _list_batch_summaries(self) -> list[dict]:
        batch_paths = sorted((self._storage_dir / "batches").glob("*.json"))
        return [summarize_batch(self._storage_dir, load_batch(batch_path)) for batch_path in batch_paths]

    def _render_batch_card(self, summary: dict) -> str:
        if summary["review_states"].get("pending", 0) > 0:
            status = "Pending review"
        elif summary["review_states"].get("reviewed", 0) == summary["item_count"]:
            status = "Reviewed"
        else:
            status = "Not started"
        return (
            '<article class="item">'
            f'<div class="field"><strong>Batch:</strong> {escape(summary["batch_id"])}</div>'
            f'<div class="field"><strong>Status:</strong> {escape(status)}</div>'
            f'<div class="field"><strong>Items:</strong> {summary["item_count"]}</div>'
            f'<div class="field"><strong>Reviewed:</strong> {summary["review_states"].get("reviewed", 0)}</div>'
            f'<div class="field"><strong>Remaining:</strong> {summary["review_states"].get("pending", 0)}</div>'
            f'<div class="field"><a href="/?batch_id={escape(summary["batch_id"])}">Open batch</a></div>'
            "</article>"
        )

    def _render_threshold_reminders(self) -> str:
        reviewed_count = self._cumulative_reviewed_count()
        sections = []
        if reviewed_count >= 50:
            sections.append(f"<p>{escape(f'{reviewed_count} reviewed messages reached. 50-message checkpoint is ready.')}</p>")
        if reviewed_count >= 100:
            sections.append(self._render_low_value_gate_summary(reviewed_count))
        if reviewed_count >= 200:
            sections.append("<p>200-message confidence checkpoint reached.</p>")
        if not sections:
            return ""
        reminder_items = "".join(sections)
        return f'<section class="panel"><h2>Review checkpoints</h2>{reminder_items}</section>'

    def _render_trusted_sender_summary(self) -> str:
        store = TrustedSenderStore(self._storage_dir)
        entries = store.load_entries_or_rebuild()
        path = self._storage_dir / "trusted_personal_senders.json"
        if not entries:
            body = (
                '<p class="meta">No trusted personal senders are seeded yet.</p>'
                '<p class="meta">The file is kept at '
                f'{escape(str(path))}'
                ' and will populate automatically from repeated reviewed personal mail or future manual approvals.</p>'
            )
        else:
            rows = "".join(
                '<article class="item">'
                f'<div class="field"><strong>Address:</strong> {escape(entry["address"])}</div>'
                f'<div class="field"><strong>Source:</strong> {escape(entry.get("source", "unknown"))}</div>'
                f'<div class="field"><strong>Kind:</strong> {escape(entry.get("kind", "direct"))}</div>'
                f'<div class="field"><strong>Notes:</strong> {escape(entry.get("notes", ""))}</div>'
                '</article>'
                for entry in entries
            )
            body = (
                f'<p class="meta">Allowlist file: {escape(str(path))}</p>'
                '<div class="items">'
                f'{rows}'
                '</div>'
            )
        return f'<section class="panel"><h2>Trusted Personal Senders</h2>{body}</section>'

    def _render_shadow_eval_summary(self) -> str:
        evaluation_paths = sorted(
            [
                path
                for path in (self._storage_dir / "evaluations").glob("shadow-label-eval-*.json")
                if not path.stem.endswith("-preferences")
            ],
            reverse=True,
        )
        if not evaluation_paths:
            return (
                '<section class="panel"><h2>Shadow Evaluations</h2>'
                '<p class="meta">No shadow evaluation reports found yet.</p></section>'
            )

        cards = []
        for path in evaluation_paths[:5]:
            report = json.loads(path.read_text())
            eval_id = path.stem
            comparison_count = len(report.get("comparison_candidates", []))
            cards.append(
                '<article class="item">'
                f'<div class="field"><strong>Evaluation:</strong> {escape(eval_id)}</div>'
                f'<div class="field"><strong>Reviewed:</strong> {report["overall"]["reviewed_count"]}</div>'
                f'<div class="field"><strong>Heuristic exact-match:</strong> {report["overall"]["heuristic"]["exact_match_rate"]}%</div>'
                f'<div class="field"><strong>OpenAI vs your final result:</strong> {comparison_count}</div>'
                f'<div class="field"><a href="/?evaluation_id={escape(eval_id)}">Open evaluation</a></div>'
                '</article>'
            )
        return (
            '<section class="panel"><h2>Shadow Evaluations</h2>'
            '<div class="items">'
            f'{"".join(cards)}'
            '</div></section>'
        )

    def _render_unsubscribe_inventory(self) -> str:
        candidates = self._unsubscribe_store.list_candidates()
        if not candidates:
            return (
                '<section class="panel"><h2>Unsubscribe inventory</h2>'
                '<p class="meta">No unsubscribe candidates have been detected in stored batches yet.</p>'
                '</section>'
            )

        selected_count = sum(1 for candidate in candidates if candidate.get("decision_state") == "selected")
        execution_preview = self._unsubscribe_executor.preview_selected_candidates()
        cards = "".join(self._render_unsubscribe_candidate_card(candidate) for candidate in candidates)
        return (
            '<section class="panel"><h2>Unsubscribe inventory</h2>'
            '<p class="meta">Review mailing-list candidates from stored batches only. '
            'Selections are saved locally for a later execution slice. No unsubscribe actions run here.</p>'
            f'<p class="meta">Selected for later unsubscribe: {selected_count} of {len(candidates)}</p>'
            '<section class="panel">'
            '<h3>Execution preview</h3>'
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{execution_preview["ready_count"]}</strong><div class="meta">Ready now</div></div>'
            f'<div class="metric"><strong>{execution_preview["unsupported_count"]}</strong><div class="meta">Manual follow-up</div></div>'
            f'<div class="metric"><strong>{execution_preview["selected_count"]}</strong><div class="meta">Selected total</div></div>'
            '</div>'
            '</section>'
            '<div class="actions">'
            '<button type="button" class="action secondary" id="save-unsubscribe-selections">Save unsubscribe selections</button>'
            '<button type="button" class="action secondary" id="preview-unsubscribe-execution">Preview execution</button>'
            '<button type="button" class="action" id="execute-unsubscribes">Execute supported unsubscribes</button>'
            '</div>'
            '<div class="items">'
            f'{cards}'
            '</div></section>'
        )

    def _render_unsubscribe_candidate_card(self, candidate: dict) -> str:
        checked = " checked" if candidate.get("decision_state") == "selected" else ""
        reason_text = ", ".join(candidate.get("qualification_reasons") or []) or "(missing)"
        execution_preview = self._unsubscribe_executor._build_preview_item(candidate)
        state_label = {
            "selected": "Selected for later unsubscribe",
            "not_selected": "Kept off the unsubscribe list",
            "undecided": "Undecided",
        }.get(candidate.get("decision_state"), "Undecided")
        latest_execution = candidate.get("latest_execution")
        latest_execution_html = ""
        if latest_execution:
            latest_execution_html = (
                f'<div class="field"><strong>Latest unsubscribe:</strong> '
                f'{escape(latest_execution.get("status") or "(missing)")} via '
                f'{escape(latest_execution.get("method") or "(missing)")}</div>'
                f'<div class="field"><strong>Notes:</strong> {escape(latest_execution.get("notes") or "(none)")}</div>'
            )
        manual_action_html = _render_manual_unsubscribe_action(execution_preview)
        return (
            '<article class="item unsubscribe-row">'
            f'<input type="checkbox" class="checkbox unsubscribe-checkbox" data-candidate-key="{escape(candidate["list_key"])}"{checked}>'
            '<div>'
            f'<div class="field"><strong>List:</strong> {escape(candidate.get("display_name") or "(missing)")}</div>'
            f'<div class="field"><strong>Sender:</strong> {escape(candidate.get("sender") or "(missing)")}</div>'
            f'<div class="field"><strong>Provider:</strong> {escape(candidate.get("provider") or "(missing)")}</div>'
            f'<div class="field"><strong>Evidence:</strong> {candidate.get("evidence_count", 0)} messages</div>'
            f'<div class="field"><strong>Most recent:</strong> {escape(candidate.get("latest_message_date") or "(missing)")}</div>'
            f'<div class="field"><strong>Qualified because:</strong> {escape(reason_text)}</div>'
            f'<div class="field"><strong>State:</strong> {escape(state_label)}</div>'
            f'{latest_execution_html}'
            f'{manual_action_html}'
            '</div>'
            '</article>'
        )

    def _render_shadow_evaluation(self, evaluation_id: str) -> str:
        evaluation = self._load_evaluation(evaluation_id)
        items = evaluation.get("comparison_candidates", [])
        if not items:
            return (
                '<section class="panel"><h2>No OpenAI differences found.</h2>'
                '<p class="meta">This evaluation has no cases where OpenAI differed from your final reviewed result.</p></section>'
            )

        preference_counts = Counter(item.get("preference") for item in items if item.get("preference"))
        summary = (
            '<section class="panel"><h2>OpenAI vs Your Final Review</h2>'
            f'<p class="meta">You are choosing between your final reviewed result and the OpenAI shadow suggestion on {len(items)} differing messages.</p>'
            f'<p class="meta">Prefer your final reviewed result: {preference_counts.get("reviewed", 0)} | '
            f'Prefer OpenAI: {preference_counts.get("openai", 0)}</p>'
            '<p class="meta">Current system suggestion is shown only as background context. It is not one of the two choices.</p>'
            '</section>'
        )
        cards = "".join(self._render_shadow_eval_card(evaluation_id, item, index, len(items)) for index, item in enumerate(items, start=1))
        return summary + f'<section class="panel"><div class="items">{cards}</div></section>'

    def _render_shadow_eval_card(self, evaluation_id: str, item: dict, index: int, total_items: int) -> str:
        preview = _preview_text(item)
        message_context = _render_message_context(item)
        reviewed_labels = ", ".join(gmail_label_name(label) for label in item.get("ground_truth", [])) or "(unlabeled)"
        heuristic_labels = ", ".join(gmail_label_name(label) for label in item.get("heuristic_labels", [])) or "(unlabeled)"
        openai_labels = ", ".join(gmail_label_name(label) for label in item.get("model_labels", [])) or "(unlabeled)"
        item_key = f'{item["batch_id"]}:{item["message_id"]}'
        preference = item.get("preference")
        reviewed_class = " secondary" if preference == "reviewed" else ""
        openai_class = " secondary" if preference == "openai" else ""
        return (
            f'<article class="item comparison-item" data-evaluation-id="{escape(evaluation_id)}" data-item-key="{escape(item_key)}">'
            f'<div class="meta">Disagreement {index} of {total_items}</div>'
            f'<div class="field"><strong>Batch:</strong> {escape(item["batch_id"])}</div>'
            f'<div class="field"><strong>Message ID:</strong> {escape(item["message_id"])}</div>'
            f'<div class="field"><strong>From:</strong> {escape(item.get("sender") or "(missing)")}</div>'
            f'<div class="field"><strong>Subject:</strong> {escape(item.get("subject") or "(missing)")}</div>'
            f'<div class="field"><strong>Date:</strong> {escape(item.get("date") or "(missing)")}</div>'
            f'<div class="field"><strong>Preview:</strong> {escape(preview)}</div>'
            f"{message_context}"
            '<div class="compare-grid">'
            '<div class="compare-card">'
            '<h3>Current system suggestion (background only)</h3>'
            f'<div class="field"><strong>Labels:</strong> {escape(heuristic_labels)}</div>'
            '</div>'
            '<div class="compare-card">'
            '<h3>Your final reviewed result</h3>'
            f'<div class="field"><strong>Labels:</strong> {escape(reviewed_labels)}</div>'
            '</div>'
            '<div class="compare-card">'
            '<h3>OpenAI shadow suggestion</h3>'
            f'<div class="field"><strong>Labels:</strong> {escape(openai_labels)}</div>'
            f'<div class="field"><strong>Why:</strong> {escape(item.get("model_reason") or "(missing)")}</div>'
            '</div>'
            '</div>'
            '<p class="meta">Pick between your final reviewed result and OpenAI. The current system suggestion is shown only to help you understand the original miss.</p>'
            '<div class="actions">'
            f'<button type="button" class="action prefer-reviewed{reviewed_class}">Prefer your final reviewed result</button>'
            f'<button type="button" class="action prefer-openai{openai_class}">Prefer OpenAI</button>'
            '</div>'
            '</article>'
        )

    def _load_evaluation(self, evaluation_id: str) -> dict:
        report_path = self._storage_dir / "evaluations" / f"{evaluation_id}.json"
        if not report_path.exists():
            raise FileNotFoundError(evaluation_id)
        report = json.loads(report_path.read_text())
        preferences = self._load_evaluation_preferences(evaluation_id)
        for item in report.get("comparison_candidates", []):
            self._hydrate_evaluation_item(item, preferences)
        for item in report.get("disagreements", {}).get("model_better_than_heuristic", []):
            self._hydrate_evaluation_item(item, preferences)
        for item in report.get("disagreements", {}).get("heuristic_better_than_model", []):
            self._hydrate_evaluation_item(item, preferences)
        return report

    def _hydrate_evaluation_item(self, item: dict, preferences: dict[str, str]) -> None:
        item.update(self._lookup_batch_item_context(item["batch_id"], item["message_id"]))
        item_key = f'{item["batch_id"]}:{item["message_id"]}'
        item["preference"] = _migrate_legacy_preference(preferences.get(item_key))

    def _lookup_batch_item_context(self, batch_id: str, message_id: str) -> dict:
        if self._batch_item_context_index is None:
            self._batch_item_context_index = self._build_batch_item_context_index()
        return self._batch_item_context_index.get((batch_id, message_id), {})

    def _build_batch_item_context_index(self) -> dict[tuple[str, str], dict]:
        index: dict[tuple[str, str], dict] = {}
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            batch_id = batch.get("batch_id")
            if not batch_id:
                continue
            for item in batch.get("items", []):
                message_id = item.get("message_id")
                if not message_id:
                    continue
                index[(batch_id, message_id)] = {
                    "date": item.get("date"),
                    "snippet": item.get("snippet"),
                    "body": item.get("body"),
                    "interpretation": item.get("interpretation"),
                }
        return index

    def _load_evaluation_preferences(self, evaluation_id: str) -> dict[str, str]:
        path = self._evaluation_preference_path(evaluation_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def _save_evaluation_preference(self, evaluation_id: str, payload: dict) -> dict:
        report_path = self._storage_dir / "evaluations" / f"{evaluation_id}.json"
        if not report_path.exists():
            raise FileNotFoundError(evaluation_id)
        preferences = self._load_evaluation_preferences(evaluation_id)
        preferences[payload["item_key"]] = payload["preference"]
        self._evaluation_preference_path(evaluation_id).write_text(json.dumps(preferences, indent=2))
        return {"preferences": preferences}

    def _evaluation_preference_path(self, evaluation_id: str) -> Path:
        return self._storage_dir / "evaluations" / f"{evaluation_id}-preferences.json"

    def _cumulative_reviewed_count(self) -> int:
        reviewed_count = 0
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            reviewed_count += sum(1 for item in batch["items"] if item.get("review_state") == "reviewed")
        return reviewed_count

    def _render_low_value_gate_summary(self, reviewed_count: int) -> str:
        gate_stats = self._low_value_gate_stats()
        explicit_count = gate_stats["explicit_count"]
        safe_count = gate_stats["safe_count"]
        precision = round((safe_count / explicit_count) * 100) if explicit_count else 0
        return (
            f"<p>{reviewed_count}-message automation gate is ready for founder review.</p>"
            f"<p>Low-value actionability precision: {precision}%</p>"
            f"<p>{safe_count} of {explicit_count} explicitly reviewed low-value candidates marked safe to remove.</p>"
        )

    def _low_value_gate_stats(self) -> dict[str, int]:
        explicit_count = 0
        safe_count = 0
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            for item in batch["items"]:
                if item.get("review_state") != "reviewed":
                    continue
                if item.get("actionability") not in {"safe-to-remove-from-inbox", "keep-in-inbox"}:
                    continue
                final_labels = set(item.get("final_labels") or [])
                if not final_labels.intersection({"promotions", "spam-low-value"}):
                    continue
                explicit_count += 1
                if item.get("actionability") == "safe-to-remove-from-inbox":
                    safe_count += 1
        return {"explicit_count": explicit_count, "safe_count": safe_count}

    def _render_summary(self, summary: dict) -> str:
        label_pills = "".join(
            f'<span class="pill">{escape(label)}: {count}</span>'
            for label, count in summary["label_counts"].items()
        ) or '<span class="meta">No reviewed labels yet.</span>'
        return (
            '<section class="panel">'
            '<h2>Feedback summary</h2>'
            '<div class="summary-grid">'
            f'<div class="metric"><strong>{summary["total_items"]}</strong><div class="meta">Total items</div></div>'
            f'<div class="metric"><strong>{summary["reviewed_items"]}</strong><div class="meta">Reviewed</div></div>'
            f'<div class="metric"><strong>{summary["remaining_items"]}</strong><div class="meta">Remaining</div></div>'
            '</div>'
            f'<div style="margin-top: 12px;">{label_pills}</div>'
            '</section>'
        )

    def _render_pending_items(self, batch_id: str, pending_items: list[dict]) -> str:
        cards = "".join(
            self._render_pending_item_card(batch_id, index, len(pending_items), item)
            for index, item in enumerate(pending_items, start=1)
        )
        return f'<section class="panel"><div class="items">{cards}</div></section>'

    def _render_pending_item_card(self, batch_id: str, index: int, total_items: int, item: dict) -> str:
        preview = _preview_text(item)
        active_labels = item.get("final_labels") or item.get("applied_labels") or []
        taxonomy_buttons = "".join(
            _render_taxonomy_button(label_name, label_name in [gmail_label_name(label) for label in active_labels])
            for label_name in allowed_gmail_labels()
        )
        suggested = ", ".join(gmail_label_name(label) for label in item.get("applied_labels", [])) or "(none)"
        actionability_controls = _render_actionability_controls(item)
        message_context = _render_message_context(item)
        return (
            f'<article class="item" data-message-id="{escape(item["message_id"])}">'
            f'<div class="meta">Item {index} of {total_items}</div>'
            f'<div class="field"><strong>Batch:</strong> {escape(batch_id)}</div>'
            f'<div class="field"><strong>Message ID:</strong> {escape(item["message_id"])}</div>'
            f'<div class="field"><strong>From:</strong> {escape(item.get("sender") or "(missing)")}</div>'
            f'<div class="field"><strong>Subject:</strong> {escape(item.get("subject") or "(missing)")}</div>'
            f'<div class="field"><strong>Date:</strong> {escape(item.get("date") or "(missing)")}</div>'
            f'<div class="field"><strong>Preview:</strong> {escape(preview)}</div>'
            f'<div class="field"><strong>Suggested labels:</strong> {escape(suggested)}</div>'
            f'<div class="field"><strong>Why:</strong> {escape(item.get("interpretation") or "(missing)")}</div>'
            f"{message_context}"
            f'<div class="taxonomy">{taxonomy_buttons}</div>'
            '<p class="meta">Use Approve suggested to keep the original suggestion. '
            'Use Save selected labels after changing labels.</p>'
            f"{actionability_controls}"
            '<div class="actions">'
            '<button type="button" class="action approve">Approve suggested</button>'
            '<button type="button" class="action save secondary">Save selected labels</button>'
            '<button type="button" class="action unlabeled secondary">Mark unlabeled</button>'
            '<button type="button" class="action reject danger">Reject</button>'
            '</div>'
            '</article>'
        )

    def _default_account_id(self) -> str | None:
        if self._account_id:
            return self._account_id
        for batch_path in sorted((self._storage_dir / "batches").glob("*.json")):
            batch = load_batch(batch_path)
            account_id = batch.get("account_id")
            if account_id:
                return account_id
        return None


def _build_live_fetch_batch_fn(
    storage_dir: Path,
    credentials_dir: Path,
    client_secret_path: Path | None,
    batch_size: int,
):
    def fetch_batch(account_id: str) -> dict | None:
        try:
            gmail_client = LiveGmailClient.from_local_oauth(
                account_id,
                credentials_dir,
                client_secret_path=client_secret_path,
            )
            fetcher = GmailBatchFetcher(gmail_client=gmail_client, storage_dir=storage_dir)
            review_queue = fetcher.fetch_gmail_batch(account_id, batch_size)
        except SetupError as exc:
            raise RuntimeError(str(exc)) from exc

        if review_queue is None:
            return None

        batch = load_batch(storage_dir / "batches" / f"{review_queue['batch_id']}.json")
        review_queue["fetch_failures"] = batch.get("fetch_failures", [])
        return review_queue

    return fetch_batch


def _build_shadow_eval_fn(storage_dir: Path):
    def run_shadow_eval(limit: int) -> dict:
        evaluator = ShadowLabelEvaluator(
            storage_dir=storage_dir,
            model_client=OpenAIShadowLabelClient.from_env("gpt-4.1-mini"),
        )
        report = evaluator.run(limit=limit, disagreement_limit=limit)
        report_path = Path(report["report_path"])
        return {
            "evaluation_id": report_path.stem,
            "reviewed_count": report["overall"]["reviewed_count"],
            "comparison_count": len(report.get("comparison_candidates", [])),
            "report_path": report["report_path"],
        }

    return run_shadow_eval

def _serialize_item(item: dict) -> dict:
    return {
        "message_id": item["message_id"],
        "sender": item["sender"],
        "subject": item["subject"],
        "date": item["date"],
        "preview": _preview_text(item),
        "snippet": item.get("snippet"),
        "body": item.get("body"),
        "interpretation": item["interpretation"],
        "suggested_labels": [gmail_label_name(label) for label in item.get("applied_labels", [])],
        "review_state": item["review_state"],
        "review_action": item["review_action"],
        "final_labels": [gmail_label_name(label) for label in item.get("final_labels") or []],
        "actionability": item.get("actionability"),
    }


def _build_summary(items: list[dict]) -> dict:
    reviewed_items = [item for item in items if item.get("review_state") == "reviewed"]
    label_counts = Counter(
        gmail_label_name(label)
        for item in reviewed_items
        for label in item.get("final_labels") or []
    )
    return {
        "total_items": len(items),
        "reviewed_items": len(reviewed_items),
        "remaining_items": len(items) - len(reviewed_items),
        "label_counts": dict(sorted(label_counts.items())),
    }


def _preview_text(item: dict) -> str:
    return item.get("snippet") or item.get("subject") or item.get("body") or "(missing)"


def _render_message_context(item: dict) -> str:
    snippet = item.get("snippet")
    body = item.get("body")
    if not snippet and not body:
        return ""

    parts = []
    if snippet:
        parts.append(f'<div class="context-copy"><strong>Snippet:</strong> {escape(snippet)}</div>')
    if body:
        parts.append(f'<div class="context-copy"><strong>Body:</strong> {escape(body)}</div>')

    return '<details class="context-panel"><summary>More context</summary>' + "".join(parts) + "</details>"


def _render_taxonomy_button(label_name: str, is_active: bool) -> str:
    active_class = " active" if is_active else ""
    return (
        f'<button type="button" class="taxonomy-option{active_class}" '
        f'data-label="{escape(label_name)}">{escape(label_name)}</button>'
    )


def _render_manual_unsubscribe_action(preview_item: dict) -> str:
    if preview_item.get("status") == "ready":
        return ""

    url = preview_item.get("url")
    if not url:
        return ""

    if url.startswith("mailto:"):
        return (
            '<div class="field"><strong>Manual action:</strong> '
            f'<a href="{escape(url)}">Manual mail unsubscribe</a></div>'
        )

    if url.startswith("https://") or url.startswith("http://"):
        return (
            '<div class="field"><strong>Manual action:</strong> '
            f'<a href="{escape(url)}" target="_blank" rel="noreferrer">Open unsubscribe link manually</a></div>'
        )

    return ""


def _migrate_legacy_preference(preference: str | None) -> str | None:
    if preference == "current":
        return "reviewed"
    return preference


def _render_actionability_controls(item: dict) -> str:
    if not _is_plausible_inbox_removal_candidate(item):
        return ""
    selected_value = item.get("actionability") or "safe-to-remove-from-inbox"
    safe_active = " active" if selected_value == "safe-to-remove-from-inbox" else ""
    keep_active = " active" if selected_value == "keep-in-inbox" else ""
    return (
        '<div class="field"><strong>Actionability:</strong></div>'
        '<div class="actionability">'
        f'<button type="button" class="actionability-option{safe_active}" '
        'data-actionability="safe-to-remove-from-inbox">Safe to remove from inbox</button>'
        f'<button type="button" class="actionability-option{keep_active}" '
        'data-actionability="keep-in-inbox">Keep in inbox</button>'
        "</div>"
    )


def _is_plausible_inbox_removal_candidate(item: dict) -> bool:
    labels = set(item.get("final_labels") or item.get("applied_labels") or [])
    return bool(labels.intersection({"promotions", "spam-low-value", "newsletter", "shopping-order", "receipt-billing"}))


def _requested_batch_id(path: str) -> str | None:
    prefix = "/api/batches/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix):]
    if not remainder or "/" in remainder:
        return None
    return remainder


def _requested_decision_batch_id(path: str) -> str | None:
    prefix = "/api/batches/"
    suffix = "/decisions"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    remainder = path[len(prefix):-len(suffix)]
    if not remainder or "/" in remainder:
        return None
    return remainder


def _requested_evaluation_id(path: str) -> str | None:
    prefix = "/api/evaluations/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix):]
    if not remainder or "/" in remainder:
        return None
    return remainder


def _requested_evaluation_preference_id(path: str) -> str | None:
    prefix = "/api/evaluations/"
    suffix = "/preferences"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    remainder = path[len(prefix):-len(suffix)]
    if not remainder or "/" in remainder:
        return None
    return remainder
