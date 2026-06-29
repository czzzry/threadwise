import json
import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, unquote, urlparse

from src.label_taxonomy import allowed_gmail_labels
from src.local_artifacts import memory_proposals_path, safety_dispositions_path, teachable_rules_path
from src.local_browser_review_rendering import (
    LocalBrowserReviewRenderingMixin,
    build_summary,
    serialize_item,
)
from src.memory_proposal_store import (
    MemoryProposalStore,
    build_memory_proposal,
    load_storage_items,
)
from src.local_browser_review_runtime import build_live_fetch_batch_fn, build_shadow_eval_fn
from src.review_loop import FixtureReviewLoop
from src.gmail_batch_review_store import GmailBatchReviewStore
from src.operational_readiness import write_operational_readiness_report
from src.safety_disposition_store import SafetyDispositionStore, build_safety_disposition
from src.teachable_rule_memory import TeachableRuleMemory, parse_teaching_instruction, preview_teachable_rule
from src.unified_review_queue import UnifiedReviewQueue
from src.unsubscribe_execution import UnsubscribeExecutor
from src.unsubscribe_inventory_store import UnsubscribeInventoryStore


DEFAULT_STORAGE_DIR = Path("data/gmail_fetch")
DEFAULT_CREDENTIALS_DIR = Path("data/gmail_credentials")
DEFAULT_OUTPUT_STORAGE_DIR = Path("data/classifier_eval")
DEFAULT_PROTONMAIL_STORAGE_DIR = Path("data/protonmail_fetch")
DEFAULT_OUTLOOKMAIL_STORAGE_DIR = Path("data/outlookmail_fetch")


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
    parser.add_argument("--output-storage-dir", type=Path, default=DEFAULT_OUTPUT_STORAGE_DIR)
    parser.add_argument("--protonmail-storage-dir", type=Path, default=DEFAULT_PROTONMAIL_STORAGE_DIR)
    parser.add_argument("--outlookmail-storage-dir", type=Path, default=DEFAULT_OUTLOOKMAIL_STORAGE_DIR)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    return parser


def main(argv: list[str] | None = None, stdout=None, server_factory=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    server_factory = server_factory or create_server
    try:
        server = server_factory(
            args.host,
            args.port,
            args.storage_dir,
            args.batch_id,
            args.account_id,
            args.output_storage_dir,
            args.protonmail_storage_dir,
            args.outlookmail_storage_dir,
            args.credentials_dir,
            args.client_secret_path,
            args.fetch_batch_size,
        )
    except TypeError:
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
    output_storage_dir: Path = DEFAULT_OUTPUT_STORAGE_DIR,
    protonmail_storage_dir: Path = DEFAULT_PROTONMAIL_STORAGE_DIR,
    outlookmail_storage_dir: Path = DEFAULT_OUTLOOKMAIL_STORAGE_DIR,
    credentials_dir: Path = DEFAULT_CREDENTIALS_DIR,
    client_secret_path: Path | None = None,
    fetch_batch_size: int = 50,
) -> ThreadingHTTPServer:
    app = LocalBrowserReviewApp(
        storage_dir=storage_dir,
        batch_id=batch_id,
        account_id=account_id,
        output_storage_dir=output_storage_dir,
        provider_storage_dirs=[
            ("gmail", storage_dir),
            ("protonmail", protonmail_storage_dir),
            ("outlookmail", outlookmail_storage_dir),
        ],
        fetch_batch_fn=build_live_fetch_batch_fn(
            storage_dir=storage_dir,
            credentials_dir=credentials_dir,
            client_secret_path=client_secret_path,
            batch_size=fetch_batch_size,
        ),
        run_shadow_eval_fn=build_shadow_eval_fn(storage_dir=storage_dir),
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            app.handle_request(self)

        def do_POST(self) -> None:
            app.handle_request(self)

        def log_message(self, format: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


class LocalBrowserReviewApp(LocalBrowserReviewRenderingMixin):
    def __init__(
        self,
        storage_dir: Path,
        batch_id: str | None,
        fetch_batch_fn=None,
        account_id: str | None = None,
        output_storage_dir: Path | None = None,
        provider_storage_dirs: list[tuple[str, Path]] | None = None,
        run_shadow_eval_fn=None,
    ) -> None:
        self._storage_dir = storage_dir
        self._batch_id = batch_id
        self._store = GmailBatchReviewStore(storage_dir)
        self._unsubscribe_store = UnsubscribeInventoryStore(storage_dir)
        self._unsubscribe_executor = UnsubscribeExecutor(storage_dir)
        self._fetch_batch_fn = fetch_batch_fn
        self._account_id = account_id
        self._run_shadow_eval_fn = run_shadow_eval_fn
        self._batch_item_context_index: dict[tuple[str, str], dict] | None = None
        self._output_storage_dir = output_storage_dir or _infer_output_storage_dir(storage_dir)
        self._provider_storage_dirs = provider_storage_dirs or _infer_provider_storage_dirs(storage_dir)
        self._unified_review_queue = UnifiedReviewQueue(
            self._output_storage_dir,
            self._provider_storage_dirs,
        )

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
                "summary": build_summary(batch["items"]),
                "items": [serialize_item(item) for item in batch["items"]],
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
                "item": serialize_item(updated_item),
                "summary": build_summary(updated_batch["items"]),
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

        if parsed.path == "/api/unified-review-queue" and method == "GET":
            return HTTPStatus.OK, self._load_or_build_unified_review_queue()

        if parsed.path == "/api/unified-review-queue/refresh" and method == "POST":
            return HTTPStatus.OK, self._unified_review_queue.build_queue()

        if parsed.path == "/api/operational-readiness" and method == "GET":
            return HTTPStatus.OK, self._load_operational_readiness()

        if parsed.path == "/api/operational-readiness/refresh" and method == "POST":
            return HTTPStatus.OK, write_operational_readiness_report(self._output_storage_dir)

        requested_queue_item_id = _requested_unified_review_queue_item_id(parsed.path)
        if requested_queue_item_id is not None and method == "POST":
            try:
                return HTTPStatus.OK, self._unified_review_queue.review_item(
                    requested_queue_item_id,
                    action=(body or {}).get("action", ""),
                    notes=(body or {}).get("notes", ""),
                    labels=list((body or {}).get("labels", [])),
                    answer_key=(body or {}).get("answer_key"),
                    response_text=(body or {}).get("response_text"),
                )
            except KeyError as exc:
                return HTTPStatus.NOT_FOUND, {"error": str(exc)}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/teachable-rules/preview" and method == "POST":
            try:
                return HTTPStatus.OK, self._preview_teachable_rule(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown batch id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid teaching payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/teachable-rules" and method == "POST":
            try:
                return HTTPStatus.OK, self._save_teachable_rule(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown batch id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid teaching payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/memory-proposals/preview" and method == "POST":
            try:
                return HTTPStatus.OK, self._preview_memory_proposal(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown batch id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid proposal payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/memory-proposals/approve" and method == "POST":
            try:
                return HTTPStatus.OK, self._approve_memory_proposal(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown proposal id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid proposal payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/memory-proposals/reject" and method == "POST":
            try:
                return HTTPStatus.OK, self._reject_memory_proposal(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown proposal id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid proposal payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/safety-dispositions/preview" and method == "POST":
            try:
                return HTTPStatus.OK, self._preview_safety_disposition(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown batch id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid safety payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/safety-dispositions/approve" and method == "POST":
            try:
                return HTTPStatus.OK, self._approve_safety_disposition(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown disposition id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid safety payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        if parsed.path == "/api/safety-dispositions/reject" and method == "POST":
            try:
                return HTTPStatus.OK, self._reject_safety_disposition(body or {})
            except FileNotFoundError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown disposition id"}
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid safety payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        requested_rule_id = _requested_teachable_rule_disable_id(parsed.path)
        if requested_rule_id is not None and method == "POST":
            try:
                return HTTPStatus.OK, self._disable_teachable_rule(requested_rule_id, body or {})
            except KeyError:
                return HTTPStatus.NOT_FOUND, {"error": "Unknown teachable rule id"}

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

    def _preview_teachable_rule(self, payload: dict) -> dict:
        batch_id = payload["batch_id"]
        instruction = payload["instruction"]
        selected_message_ids = set(payload.get("message_ids", []))
        batch = self._load_batch(batch_id)
        selected_items = _selected_teaching_examples(batch["items"], selected_message_ids)
        rule = parse_teaching_instruction(instruction, source_examples=selected_items)
        return preview_teachable_rule(rule, batch["items"])

    def _save_teachable_rule(self, payload: dict) -> dict:
        batch_id = payload["batch_id"]
        instruction = payload["instruction"]
        selected_message_ids = set(payload.get("message_ids", []))
        batch = self._load_batch(batch_id)
        selected_items = _selected_teaching_examples(batch["items"], selected_message_ids)
        memory = TeachableRuleMemory(teachable_rules_path(self._storage_dir))
        rule = memory.save_instruction(instruction, source_examples=selected_items)
        return {
            "rule": rule.to_dict(),
            "rules_path": str(memory.path),
            "preview": preview_teachable_rule(rule, batch["items"]),
        }

    def _preview_memory_proposal(self, payload: dict) -> dict:
        batch_id = payload["batch_id"]
        scope = payload["scope"]
        label = payload["label"]
        explanation = payload.get("explanation", "")
        selected_message_ids = set(payload.get("message_ids", []))
        batch = self._load_batch(batch_id)
        provider = _batch_provider(batch)
        account_id = _batch_account_id(batch) or self._default_account_id() or ""
        selected_items = _selected_teaching_examples(batch["items"], selected_message_ids)
        storage_items = load_storage_items(self._storage_dir, provider)
        proposal = build_memory_proposal(
            provider=provider,
            account_id=account_id,
            source_batch_id=batch_id,
            selected_items=selected_items,
            scope=scope,
            label=label,
            explanation=explanation,
            storage_items=storage_items,
        )
        store = MemoryProposalStore(memory_proposals_path(self._storage_dir))
        store.save_proposal(proposal)
        return {
            "proposal": proposal.to_dict(),
            "proposal_path": str(memory_proposals_path(self._storage_dir)),
        }

    def _approve_memory_proposal(self, payload: dict) -> dict:
        proposal_id = payload["proposal_id"]
        notes = payload.get("notes", "")
        store = MemoryProposalStore(memory_proposals_path(self._storage_dir))
        memory = TeachableRuleMemory(teachable_rules_path(self._storage_dir))
        approved = store.review_proposal(proposal_id, "approved", rules_memory=memory, review_notes=notes)
        return {
            "proposal": approved.to_dict(),
            "rules_path": str(memory.path),
        }

    def _reject_memory_proposal(self, payload: dict) -> dict:
        proposal_id = payload["proposal_id"]
        notes = payload.get("notes", "")
        store = MemoryProposalStore(memory_proposals_path(self._storage_dir))
        rejected = store.review_proposal(proposal_id, "rejected", review_notes=notes)
        return {"proposal": rejected.to_dict()}

    def _preview_safety_disposition(self, payload: dict) -> dict:
        batch_id = payload["batch_id"]
        scope = payload["scope"]
        disposition = payload["disposition"]
        explanation = payload.get("explanation", "")
        selected_message_ids = set(payload.get("message_ids", []))
        batch = self._load_batch(batch_id)
        provider = _batch_provider(batch)
        account_id = _batch_account_id(batch) or self._default_account_id() or ""
        selected_items = _selected_teaching_examples(batch["items"], selected_message_ids)
        storage_items = load_storage_items(self._storage_dir, provider)
        pending = build_safety_disposition(
            provider=provider,
            account_id=account_id,
            source_batch_id=batch_id,
            selected_items=selected_items,
            scope=scope,
            disposition=disposition,
            explanation=explanation,
            storage_items=storage_items,
        )
        store = SafetyDispositionStore(safety_dispositions_path(self._storage_dir))
        store.save_disposition(pending)
        return {
            "disposition": pending.to_dict(),
            "disposition_path": str(safety_dispositions_path(self._storage_dir)),
        }

    def _approve_safety_disposition(self, payload: dict) -> dict:
        disposition_id = payload["disposition_id"]
        notes = payload.get("notes", "")
        store = SafetyDispositionStore(safety_dispositions_path(self._storage_dir))
        approved = store.review_disposition(disposition_id, "approved", review_notes=notes)
        return {
            "disposition": approved.to_dict(),
            "disposition_path": str(safety_dispositions_path(self._storage_dir)),
        }

    def _reject_safety_disposition(self, payload: dict) -> dict:
        disposition_id = payload["disposition_id"]
        notes = payload.get("notes", "")
        store = SafetyDispositionStore(safety_dispositions_path(self._storage_dir))
        rejected = store.review_disposition(disposition_id, "rejected", review_notes=notes)
        return {
            "disposition": rejected.to_dict(),
            "disposition_path": str(safety_dispositions_path(self._storage_dir)),
        }

    def _disable_teachable_rule(self, rule_id: str, payload: dict) -> dict:
        memory = TeachableRuleMemory(teachable_rules_path(self._storage_dir))
        disabled = memory.disable_rule(rule_id, reason=payload.get("reason", ""))
        return {"rule": disabled.to_dict(), "rules_path": str(memory.path)}

    def _load_or_build_unified_review_queue(self) -> dict:
        if self._unified_review_queue.path.exists():
            return self._unified_review_queue.load_queue()
        return self._unified_review_queue.build_queue()

    def _load_operational_readiness(self) -> dict:
        reports_dir = self._output_storage_dir / "operational_readiness_reports"
        if reports_dir.exists():
            matches = sorted(reports_dir.glob("*.json"))
            if matches:
                payload = json.loads(matches[-1].read_text())
                payload["report_path"] = str(matches[-1])
                return payload
        return write_operational_readiness_report(self._output_storage_dir)

    def _require_known_batch_id(self, requested_batch_id: str) -> None:
        if self._batch_id is None:
            return
        if requested_batch_id != self._batch_id:
            raise FileNotFoundError(requested_batch_id)

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


def _requested_teachable_rule_disable_id(path: str) -> str | None:
    prefix = "/api/teachable-rules/"
    suffix = "/disable"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    remainder = path[len(prefix):-len(suffix)]
    if not remainder or "/" in remainder:
        return None
    return remainder


def _requested_unified_review_queue_item_id(path: str) -> str | None:
    prefix = "/api/unified-review-queue/items/"
    suffix = "/actions"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    remainder = path[len(prefix):-len(suffix)]
    if not remainder:
        return None
    return unquote(remainder)


def _selected_teaching_examples(items: list[dict], selected_message_ids: set[str]) -> list[dict]:
    if not selected_message_ids:
        raise ValueError("Select at least one email before teaching a rule.")
    selected_items = [item for item in items if item["message_id"] in selected_message_ids]
    if not selected_items:
        raise ValueError("Selected emails were not found in this batch.")
    return [
        {
            "message_id": item["message_id"],
            "sender": item.get("sender"),
            "subject": item.get("subject"),
            "date": item.get("date"),
            "snippet": item.get("snippet", ""),
            "body": item.get("body", ""),
            "applied_labels": item.get("applied_labels", []),
        }
        for item in selected_items
    ]


def _batch_provider(batch: dict) -> str:
    provider = batch.get("provider")
    if provider:
        return provider
    for item in batch.get("items", []):
        source = item.get("source")
        if source:
            return source
    return "gmail"


def _batch_account_id(batch: dict) -> str:
    item_account_ids = {
        item.get("account_id")
        for item in batch.get("items", [])
        if item.get("account_id")
    }
    if len(item_account_ids) == 1:
        return next(iter(item_account_ids))
    account_id = batch.get("account_id")
    if account_id:
        return account_id
    for item_account_id in item_account_ids:
        return item_account_id
    return ""


def _infer_output_storage_dir(storage_dir: Path) -> Path:
    if storage_dir.name in {"gmail_fetch", "protonmail_fetch", "outlookmail_fetch"}:
        return storage_dir.parent / "classifier_eval"
    return storage_dir / "classifier_eval"


def _infer_provider_storage_dirs(storage_dir: Path) -> list[tuple[str, Path]]:
    if storage_dir.name in {"gmail_fetch", "protonmail_fetch", "outlookmail_fetch"}:
        base_dir = storage_dir.parent
        return [
            ("gmail", base_dir / "gmail_fetch"),
            ("protonmail", base_dir / "protonmail_fetch"),
            ("outlookmail", base_dir / "outlookmail_fetch"),
        ]
    return [
        ("gmail", storage_dir),
        ("protonmail", storage_dir),
        ("outlookmail", storage_dir),
    ]
