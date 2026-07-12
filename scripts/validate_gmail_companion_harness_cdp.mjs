const appUrl = process.argv[2] || "http://127.0.0.1:8031/";
const cdpBase = process.argv[3] || "http://127.0.0.1:9222";

const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
let nextId = 1;
const pending = new Map();
const uncaughtErrors = [];

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") {
    uncaughtErrors.push(message.params.exceptionDetails);
  }
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
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  await waitFor(() => evaluate("document.querySelectorAll('#harness-list [data-message-id]').length > 0"));

  const state = await evaluate(`({
    fixtureCount: document.querySelectorAll('#harness-list [data-message-id]').length,
    selectedEmail: document.querySelector('#selected-email')?.innerText || '',
    today: document.querySelector('#daily-summary')?.innerText || ''
  })`);

  console.log(JSON.stringify({ ...state, uncaughtErrorCount: uncaughtErrors.length }, null, 2));
  if (!state.fixtureCount || !state.selectedEmail || !state.today || uncaughtErrors.length) {
    process.exitCode = 1;
  }
} finally {
  socket.close();
  await fetch(`${cdpBase}/json/close/${target.id}`).catch(() => {});
}

async function createTarget(url) {
  const response = await fetch(`${cdpBase}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) throw new Error(`Could not create Chrome target: ${response.status}`);
  return response.json();
}

function send(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Evaluation failed");
  }
  return result.result.value;
}

async function waitFor(fn, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Timed out waiting for the companion harness to render.");
}
