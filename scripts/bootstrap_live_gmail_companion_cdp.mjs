import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const localOrigin = process.argv[3] || "http://127.0.0.1:8021";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const contentScriptPath = path.join(repoRoot, "extensions", "gmail_companion", "content.js");

const target = await findGmailTarget();
const socket = new WebSocket(target.webSocketDebuggerUrl);
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

  const before = await evaluate(`({
    hasRoot: !!document.getElementById('email-agent-companion-root'),
    title: document.title,
    url: window.location.href
  })`);

  await evaluate(`(() => {
    const bridge = {};
    bridge.lastError = null;
    bridge.onMessage = { addListener: () => undefined };
    window.__eaPendingMessages = [];
    window.__eaMessageCallbacks = {};
    window.__eaMessageSeq = 0;
    window.__eaDeliverResponse = (id, response, errorMessage) => {
      const callback = window.__eaMessageCallbacks[id];
      delete window.__eaMessageCallbacks[id];
      bridge.lastError = errorMessage ? { message: errorMessage } : null;
      if (typeof callback === 'function') {
        callback(response);
      }
      bridge.lastError = null;
      return true;
    };
    bridge.sendMessage = (message, callback) => {
      const id = ++window.__eaMessageSeq;
      if (typeof callback === 'function') {
        window.__eaMessageCallbacks[id] = callback;
      }
      window.__eaPendingMessages.push({ id, message });
      return true;
    };

    window.chrome = window.chrome || {};
    window.chrome.runtime = bridge;
    return true;
  })()`);

  const contentScript = await fs.readFile(contentScriptPath, "utf8");
  await evaluate(contentScript);

  await waitFor(async () => {
    await pumpBridge();
    const rootReady = await evaluate(`!!document.getElementById('email-agent-companion-root')`);
    return rootReady;
  }, 15000);

  await waitFor(async () => {
    await pumpBridge();
    const snapshot = await evaluate(`({
      subtitle: document.getElementById('ea-subtitle')?.innerText || '',
      selectedText: document.getElementById('ea-selected-email')?.innerText || '',
      summaryText: document.getElementById('ea-daily-summary')?.innerText || ''
    })`);
    return (
      snapshot.subtitle !== "Connecting to local companion server" &&
      (snapshot.selectedText.length > 0 || snapshot.summaryText.length > 0)
    );
  }, 15000);

  const after = await evaluate(`({
    hasRoot: !!document.getElementById('email-agent-companion-root'),
    subtitle: document.getElementById('ea-subtitle')?.innerText || '',
    selectedText: document.getElementById('ea-selected-email')?.innerText.slice(0, 1200) || '',
    summaryText: document.getElementById('ea-daily-summary')?.innerText.slice(0, 1200) || ''
  })`);

  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, before, after }, null, 2));
} finally {
  socket.close();
}

async function findGmailTarget() {
  const response = await fetch(`${cdpBase}/json/list`);
  if (!response.ok) {
    throw new Error(`Could not list Chrome targets: ${response.status}`);
  }
  const targets = await response.json();
  const pageTarget = targets.find(
    (entry) =>
      entry.type === "page" &&
      typeof entry.url === "string" &&
      entry.url.startsWith("https://mail.google.com/mail/")
  );
  if (!pageTarget) {
    throw new Error("No live Gmail page target found.");
  }
  return pageTarget;
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
  throw new Error("Timed out waiting for injected Gmail companion state.");
}

async function pumpBridge() {
  let processed = 0;
  while (processed < 20) {
    const pendingMessage = await evaluate(`(() => {
      const queue = window.__eaPendingMessages || [];
      return queue.length ? queue.shift() : null;
    })()`);
    if (!pendingMessage) {
      return;
    }
    processed += 1;
    const response = await fulfillMessage(pendingMessage.message);
    const responseLiteral = JSON.stringify(response.payload ?? null);
    const errorLiteral = JSON.stringify(response.error ?? null);
    await evaluate(`window.__eaDeliverResponse(${JSON.stringify(pendingMessage.id)}, ${responseLiteral}, ${errorLiteral})`);
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
      return { payload: { ok: false, payload }, error: payload?.error || `HTTP ${response.status}` };
    }
    return { payload: { ok: true, payload }, error: null };
  } catch (error) {
    return { payload: { ok: false }, error: String(error) };
  }
}
