import argparse
import json
import sys
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from src.fixture_classifier import FixtureBatchClassifier
from src.label_taxonomy import gmail_label_name
from src.teachable_rule_memory import TeachableRuleMemory, matching_rules_for_message


DEFAULT_FIXTURES_DIR = Path("examples/prototype_teachable_workbench")
DEFAULT_RULES_PATH = Path("data/prototype_teachable_rules.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve a local prototype workbench for teaching EmailAgent classification rules."
    )
    parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES_DIR)
    parser.add_argument("--rules-path", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None, stdout=None, server_factory=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output = stdout or sys.stdout
    server_factory = server_factory or create_server
    server = server_factory(args.host, args.port, args.fixtures_dir, args.rules_path)
    try:
        output.write(f"Serving teachable rules prototype at http://{args.host}:{server.server_port}\n")
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        output.write("Stopped teachable rules prototype.\n")
        return 0
    finally:
        server.server_close()


def create_server(host: str, port: int, fixtures_dir: Path, rules_path: Path) -> ThreadingHTTPServer:
    app = TeachableRulesWorkbenchApp(fixtures_dir=fixtures_dir, rules_path=rules_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            app.handle_request(self)

        def do_POST(self) -> None:
            app.handle_request(self)

        def log_message(self, format: str, *args) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


class TeachableRulesWorkbenchApp:
    def __init__(self, fixtures_dir: Path, rules_path: Path) -> None:
        self._fixtures_dir = fixtures_dir
        self._rules = TeachableRuleMemory(rules_path)

    def handle_request(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if handler.command == "GET" and parsed.path == "/":
            encoded = self.render_page().encode("utf-8")
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "text/html; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            handler.end_headers()
            handler.wfile.write(encoded)
            return

        status_code, payload = self.handle_api_request(handler.command, parsed.path, self._read_json_body(handler))
        encoded = json.dumps(payload).encode("utf-8")
        handler.send_response(status_code)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)

    def handle_api_request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        if method == "GET" and path == "/api/state":
            return HTTPStatus.OK, self.state()

        if method == "POST" and path == "/api/instructions":
            try:
                rule = self._rules.save_instruction((body or {})["instruction"])
            except (KeyError, TypeError) as exc:
                return HTTPStatus.BAD_REQUEST, {"error": f"Invalid instruction payload: {exc}"}
            except ValueError as exc:
                return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
            return HTTPStatus.OK, {"rule": rule.to_dict(), **self.state()}

        if method == "POST" and path == "/api/rerun":
            return HTTPStatus.OK, self.state()

        return HTTPStatus.NOT_FOUND, {"error": "Not found"}

    def state(self) -> dict:
        messages = self._load_messages()
        rules = self._rules.list_rules()
        return {
            "rules_path": str(self._rules.path),
            "rules": [rule.to_dict() for rule in rules],
            "items": classify_with_teachable_rules(self._fixtures_dir, messages, rules),
        }

    def render_page(self) -> str:
        state = self.state()
        state_json = json.dumps(state)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EmailAgent Teaching Prototype</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f4;
      --panel: #ffffff;
      --ink: #1d2320;
      --muted: #5f6a64;
      --line: #d9ded8;
      --accent: #146c5f;
      --accent-soft: #dff3ee;
      --warn: #8a4b00;
      --warn-soft: #fff3d8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px 18px 48px; }}
    header {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 18px; align-items: end; margin-bottom: 18px; }}
    h1 {{ margin: 0 0 6px; font-size: 1.7rem; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 1.05rem; letter-spacing: 0; }}
    p {{ margin: 0; }}
    .meta {{ color: var(--muted); font-size: 0.94rem; line-height: 1.45; }}
    .status {{ min-height: 22px; color: var(--accent); font-weight: 650; }}
    .layout {{ display: grid; grid-template-columns: minmax(300px, 380px) minmax(0, 1fr); gap: 16px; align-items: start; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    textarea {{ width: 100%; min-height: 126px; resize: vertical; border: 1px solid var(--line); border-radius: 8px; padding: 12px; font: inherit; line-height: 1.4; }}
    button {{ border: 0; border-radius: 8px; padding: 10px 12px; background: var(--ink); color: white; cursor: pointer; font-weight: 650; }}
    button.secondary {{ background: #e8ece8; color: var(--ink); }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .rules {{ display: grid; gap: 8px; margin-top: 12px; }}
    .rule {{ border: 1px solid var(--line); background: #fbfcfb; border-radius: 8px; padding: 10px; }}
    .rule strong {{ display: block; font-size: 0.9rem; }}
    .rule code {{ overflow-wrap: anywhere; }}
    .items {{ display: grid; gap: 12px; }}
    .item {{ border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 14px; }}
    .item.changed {{ border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-soft); }}
    .item-header {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: start; }}
    .subject {{ font-weight: 750; overflow-wrap: anywhere; }}
    .sender {{ margin-top: 3px; color: var(--muted); overflow-wrap: anywhere; }}
    .labels {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }}
    .pill {{ display: inline-flex; align-items: center; min-height: 26px; border-radius: 999px; padding: 4px 8px; background: #edf0ed; font-size: 0.84rem; }}
    .pill.rule-match {{ background: var(--accent-soft); color: var(--accent); border: 1px solid #9dd8ca; }}
    .pill.warn {{ background: var(--warn-soft); color: var(--warn); }}
    .body {{ margin-top: 10px; color: #34413a; line-height: 1.45; }}
    .empty {{ color: var(--muted); border: 1px dashed var(--line); border-radius: 8px; padding: 10px; }}
    @media (max-width: 820px) {{
      header, .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>EmailAgent Teaching Prototype</h1>
        <p class="meta">Local fixture-only workbench. Save an instruction, rerun classification, and inspect which saved rule changed each result.</p>
      </div>
      <p id="status" class="status"></p>
    </header>
    <section class="layout">
      <aside class="panel">
        <h2>Teach a Rule</h2>
        <textarea id="instruction" aria-label="Teaching instruction">anything from recruiters, Ashby, Greenhouse, or Lever should be job-related and kept visible</textarea>
        <div class="actions">
          <button id="save-instruction">Save instruction</button>
          <button id="rerun" class="secondary">Rerun classification</button>
        </div>
        <p class="meta" style="margin-top: 12px;">Saved to <code id="rules-path"></code></p>
        <div id="rules" class="rules"></div>
      </aside>
      <section>
        <div class="items" id="items"></div>
      </section>
    </section>
  </main>
  <script>
    let state = {state_json};
    const statusNode = document.getElementById("status");
    const rulesPathNode = document.getElementById("rules-path");
    const rulesNode = document.getElementById("rules");
    const itemsNode = document.getElementById("items");
    const instructionNode = document.getElementById("instruction");

    function render() {{
      rulesPathNode.textContent = state.rules_path;
      rulesNode.innerHTML = state.rules.length
        ? state.rules.map((rule) => `
          <article class="rule">
            <strong>${{escapeHtml(rule.label)}} · ${{escapeHtml(rule.id)}}</strong>
            <p class="meta">${{escapeHtml(rule.instruction)}}</p>
            <p class="meta">Terms: <code>${{escapeHtml(rule.terms.join(", "))}}</code></p>
          </article>
        `).join("")
        : '<p class="empty">No saved teaching rules yet.</p>';

      itemsNode.innerHTML = state.items.map((item) => `
        <article class="item ${{item.matched_rules.length ? "changed" : ""}}">
          <div class="item-header">
            <div>
              <div class="subject">${{escapeHtml(item.subject)}}</div>
              <div class="sender">${{escapeHtml(item.sender)}}</div>
            </div>
            <span class="pill ${{item.matched_rules.length ? "rule-match" : ""}}">${{item.matched_rules.length ? "Rule matched" : "Heuristic only"}}</span>
          </div>
          <div class="labels">
            ${{item.applied_labels.length ? item.applied_labels.map((label) => `<span class="pill">${{escapeHtml(label)}}</span>`).join("") : '<span class="pill warn">unlabeled</span>'}}
          </div>
          ${{item.matched_rules.length ? `<div class="labels">${{item.matched_rules.map((rule) => `<span class="pill rule-match">matched ${{escapeHtml(rule.id)}}: ${{escapeHtml(rule.terms.join(", "))}}</span>`).join("")}}</div>` : ""}}
          <p class="body">${{escapeHtml(item.body)}}</p>
          <p class="meta" style="margin-top: 10px;">${{escapeHtml(item.interpretation)}}</p>
        </article>
      `).join("");
    }}

    async function saveInstruction() {{
      statusNode.textContent = "Saving instruction...";
      const response = await fetch("/api/instructions", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ instruction: instructionNode.value }})
      }});
      const payload = await response.json();
      if (!response.ok) {{
        statusNode.textContent = payload.error || "Could not save instruction.";
        return;
      }}
      state = payload;
      statusNode.textContent = `Saved ${{payload.rule.id}} and reran classification.`;
      render();
    }}

    async function rerunClassification() {{
      statusNode.textContent = "Rerunning classification...";
      const response = await fetch("/api/rerun", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: "{{}}" }});
      state = await response.json();
      statusNode.textContent = "Classification rerun from saved rules.";
      render();
    }}

    function escapeHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[char]));
    }}

    document.getElementById("save-instruction").addEventListener("click", saveInstruction);
    document.getElementById("rerun").addEventListener("click", rerunClassification);
    render();
  </script>
</body>
</html>"""

    def _load_messages(self) -> list[dict]:
        batch_path = self._fixtures_dir / "teachable-samples.json"
        return json.loads(batch_path.read_text())["messages"]

    def _read_json_body(self, handler: BaseHTTPRequestHandler) -> dict | None:
        content_length = int(handler.headers.get("Content-Length", "0"))
        if content_length == 0:
            return None
        return json.loads(handler.rfile.read(content_length).decode("utf-8"))


def classify_with_teachable_rules(fixtures_dir: Path, messages: list[dict], rules: list) -> list[dict]:
    base = FixtureBatchClassifier(fixtures_dir=fixtures_dir).classify_messages("teachable-samples", messages)
    by_message_id = {message["message_id"]: message for message in messages}
    items = []
    for item in base["items"]:
        message = by_message_id[item["message_id"]]
        matched_rules = matching_rules_for_message(message, rules)
        applied_labels = list(item["applied_labels"])
        for rule in matched_rules:
            if rule.label not in applied_labels:
                applied_labels.append(rule.label)
        rendered_item = dict(item)
        rendered_item["applied_labels"] = [gmail_label_name(label) for label in applied_labels]
        rendered_item["matched_rules"] = [rule.to_dict() for rule in matched_rules]
        if matched_rules:
            rendered_item["confidence_band"] = "medium"
            rendered_item["interpretation"] = "Matched saved teaching rule: " + "; ".join(
                f"{rule.id} -> {rule.label}" for rule in matched_rules
            )
        items.append(rendered_item)
    return items
