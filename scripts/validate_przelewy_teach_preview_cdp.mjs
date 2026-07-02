import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const localOrigin = process.argv[3] || "http://127.0.0.1:8021";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const contentScriptPath = path.join(repoRoot, "extensions", "gmail_companion", "content.js");

const page = await createPage();
const socket = new WebSocket(page.webSocketDebuggerUrl);
let nextId = 1;
const pending = new Map();

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message));
    } else {
      resolve(message.result);
    }
  }
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

try {
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: gmailFixtureDataUrl() });
  await waitFor(async () => {
    const readyState = await evaluate("document.readyState");
    return readyState === "complete";
  }, 10000);

  await installChromeRuntimeBridge();
  const contentScript = await fs.readFile(contentScriptPath, "utf8");
  await evaluate(contentScript);

  await waitFor(async () => {
    await pumpBridge();
    return await evaluate("!!document.getElementById('email-agent-companion-root')");
  }, 15000);

  await pumpUntil(async () => {
    const text = await selectedText();
    const teachText = await teachPanelText();
    return text.includes("Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)") && teachText.includes("Preview");
  }, 15000);

  await evaluate(`document.getElementById("ea-brand-toggle")?.click()`);
  await pumpBridge();
  const previewStart = await evaluate(`globalThis.__eaTestHooks.previewTeach("", "this is phishing. I never want emails like this again")`);
  await pumpUntil(async () => {
    const text = await teachPanelText();
    return text.includes("I can relabel this email to EA/LowValue");
  }, 15000);

  const result = {
    ok: true,
    previewStart,
    selectedText: await selectedText(),
    teachPanelText: await teachPanelText(),
    requests: await evaluate("globalThis.__eaFulfilledMessages || []"),
  };

  const checks = {
    selectedEmailVisible: result.selectedText.includes("Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)"),
    lowValueSuggestionVisible: result.teachPanelText.includes("I can relabel this email to EA/LowValue"),
    noConnectionError: !result.teachPanelText.includes("cannot reach"),
    previewOptionsVisible: result.teachPanelText.includes("Fix this email"),
    exactSenderCountVisible: result.teachPanelText.includes("Exact sender matches: 0"),
    similarCandidateVisible: result.teachPanelText.includes("Similar candidates: 1"),
    broaderCandidateVisible: result.teachPanelText.includes("Broader rule candidate:"),
  };
  result.checks = checks;
  result.ok = Object.values(checks).every(Boolean);

  console.log(JSON.stringify(result, null, 2));
  if (!result.ok) {
    process.exitCode = 1;
  }
} finally {
  socket.close();
}

async function createPage() {
  const response = await fetch(`${cdpBase}/json/new?about:blank`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`Could not create Chrome page: ${response.status}`);
  }
  return response.json();
}

function gmailFixtureDataUrl() {
  const html = `<!doctype html>
    <html>
      <head><title>Gmail fixture</title></head>
      <body>
        <main role="main">
          <h2 class="hP" data-thread-perm-id="19e2103b25f08452">Nowa transakcja płatnicza (P24-Y6A-Y4M-T1W)</h2>
          <section class="adn" data-legacy-message-id="19e2103b25f08452" data-message-id="19e2103b25f08452" data-thread-perm-id="19e2103b25f08452">
            <span email="no-reply@przelewy24.pl" data-hovercard-id="no-reply@przelewy24.pl">"Przelewy24.pl" &lt;no-reply@przelewy24.pl&gt;</span>
            <p>Informacja o transakcji P24-Y6A-Y4M-T1W.</p>
          </section>
        </main>
      </body>
    </html>`;
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
}

function send(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
  });
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    const details = result.exceptionDetails;
    const exceptionText =
      details.exception?.description ||
      details.exception?.value ||
      details.text ||
      "Evaluation failed";
    throw new Error(exceptionText);
  }
  return result.result.value;
}

async function waitFor(fn, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error("Timed out waiting for condition.");
}

async function pumpUntil(fn, timeoutMs = 15000) {
  return waitFor(async () => {
    await pumpBridge();
    return fn();
  }, timeoutMs);
}

async function installChromeRuntimeBridge() {
  await evaluate(`(() => {
    const bridge = {};
    bridge.lastError = null;
    bridge.getURL = (assetPath) => "http://127.0.0.1:8021/" + String(assetPath || "").replace(/^assets\\/brand\\//, "assets/brand/");
    bridge.onMessage = { addListener: () => undefined, removeListener: () => undefined };
    window.__eaPendingMessages = [];
    window.__eaMessageCallbacks = {};
    window.__eaFulfilledMessages = [];
    window.__eaMessageSeq = 0;
    window.__eaDeliverResponse = (id, response, errorMessage) => {
      const callback = window.__eaMessageCallbacks[id];
      delete window.__eaMessageCallbacks[id];
      bridge.lastError = errorMessage ? { message: errorMessage } : null;
      if (typeof callback === "function") {
        callback(response);
      }
      bridge.lastError = null;
      return true;
    };
    bridge.sendMessage = (message, callback) => {
      const id = ++window.__eaMessageSeq;
      if (typeof callback === "function") {
        window.__eaMessageCallbacks[id] = callback;
      }
      window.__eaPendingMessages.push({ id, message });
      return true;
    };
    window.chrome = window.chrome || {};
    window.chrome.runtime = bridge;
    return true;
  })()`);
}

async function pumpBridge() {
  let processed = 0;
  while (processed < 25) {
    const pendingMessage = await evaluate(`(() => {
      const queue = window.__eaPendingMessages || [];
      return queue.length ? queue.shift() : null;
    })()`);
    if (!pendingMessage) {
      return;
    }
    processed += 1;
    const response = await fulfillMessage(pendingMessage.message);
    await evaluate(`(() => {
      window.__eaFulfilledMessages = window.__eaFulfilledMessages || [];
      window.__eaFulfilledMessages.push(${JSON.stringify({
        type: pendingMessage.message?.type || "",
        path: pendingMessage.message?.path || "",
        ok: response.payload?.ok ?? false,
        error: response.error || "",
      })});
      return window.__eaDeliverResponse(${JSON.stringify(pendingMessage.id)}, ${JSON.stringify(response.payload ?? null)}, ${JSON.stringify(response.error ?? null)});
    })()`);
  }
}

async function fulfillMessage(message) {
  if (!message) {
    return { payload: { ok: false }, error: "Missing message." };
  }
  if (message.type === "email-agent:get-state") {
    const query = new URLSearchParams(message.context || {});
    return fetchJson(`${localOrigin}/api/harness-state?${query.toString()}`);
  }
  if (message.type === "email-agent:api") {
    return fetchJson(`${localOrigin}${message.path}`, {
      method: message.method || "GET",
      headers: { "Content-Type": "application/json" },
      body: message.body ? JSON.stringify(message.body) : undefined,
    });
  }
  return { payload: { ok: false }, error: `Unsupported message type: ${message.type || "unknown"}` };
}

async function fetchJson(url, init) {
  try {
    const response = await fetch(url, init);
    const payload = await response.json();
    if (!response.ok) {
      return {
        payload: { ok: false, payload, error: payload?.error || `HTTP ${response.status}` },
        error: payload?.error || `HTTP ${response.status}`,
      };
    }
    return { payload: { ok: true, payload }, error: null };
  } catch (error) {
    return { payload: { ok: false }, error: String(error) };
  }
}

async function selectedText() {
  return evaluate(`document.getElementById("ea-selected-email")?.innerText || ""`);
}

async function teachPanelText() {
  return evaluate(`document.getElementById("ea-teach-panel")?.innerText || ""`);
}
