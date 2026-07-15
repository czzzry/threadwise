import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const analyticsScript = await fs.readFile(path.join(repoRoot, "extensions/gmail_companion/analytics.js"), "utf8");
const contentScript = await fs.readFile(path.join(repoRoot, "extensions/gmail_companion/content.js"), "utf8");
const target = await createTarget("about:blank");
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  message.error ? reject(new Error(message.error.message)) : resolve(message.result);
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

try {
  await send("Runtime.enable");
  await evaluate(`(() => {
    const handled = (id, subject) => ({
      found: true,
      message_id: id,
      subject,
      sender: 'fixture@example.invalid',
      internal_label: 'spam-low-value',
      suggested_label: 'spam-low-value',
      classification: 'EA/LowValue',
      status: 'auto-handled',
      status_label: 'Auto-handled',
      reason: 'Synthetic handled fixture.',
      details: { write_status: 'applied', inbox_status: 'applied' }
    });
    window.__handled = [
      handled('handled-1', 'First handled email'),
      handled('handled-2', 'Second handled email')
    ];
    window.__workspaceState = {
      selected_context: { provider: 'gmail', message_id: 'handled-1', subject: 'First handled email', sender: 'fixture@example.invalid' },
      selected_email: window.__handled[0],
      daily_summary: { processed_count: 2, auto_handled_count: 2, kept_visible_count: 0, needs_attention_count: 0 },
      ui_state: { allowed_labels: [{ id: 'spam-low-value', name: 'EA/LowValue' }] }
    };
    window.__harnessState = {
      sidebar_state: window.__workspaceState,
      needs_attention_items: [],
      recent_items: [],
      auto_handled_items: window.__handled,
      kept_visible_items: []
    };
    window.chrome = { runtime: {
      lastError: null,
      getURL: (value) => value,
      getManifest: () => ({ version: '0.1.0' }),
      onMessage: { addListener: () => undefined, removeListener: () => undefined },
      sendMessage: (message, callback) => {
        if (message?.type === 'threadwise:analytics') {
          throw new Error('Synthetic analytics transport failure');
        }
        if (message?.type === 'email-agent:api' && message?.path === '/api/handled-review-acknowledge') {
          const messageId = message.body?.selected_context?.message_id || '';
          window.__harnessState = {
            ...window.__harnessState,
            recent_items: window.__harnessState.recent_items.filter((item) => item.message_id !== messageId),
            auto_handled_items: window.__harnessState.auto_handled_items.filter((item) => item.message_id !== messageId),
            sidebar_state: {
              ...window.__harnessState.sidebar_state,
              selected_email: { ...window.__harnessState.sidebar_state.selected_email, handled_review_acknowledged: true }
            }
          };
          callback?.({ ok: true, payload: { acknowledged: true, harness_state: window.__harnessState } });
          return;
        }
        if (message?.type === 'email-agent:get-state') {
          const selected = window.__handled.find((item) => item.message_id === message.context?.message_id);
          if (selected) {
            window.__workspaceState = {
              ...window.__workspaceState,
              selected_context: { provider: 'gmail', message_id: selected.message_id, subject: selected.subject, sender: selected.sender },
              selected_email: selected
            };
            window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
          }
        }
        callback?.({ ok: true, payload: window.__harnessState, connection_state: { kind: 'ready', label: 'Ready' } });
      }
    }};
  })()`);
  await evaluate(analyticsScript);
  await evaluate(contentScript);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]')?.textContent.includes('First handled email') || false`));
  await evaluate(`window.__eaTestHooks.selectSummaryFilter('auto_handled_items')`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]')?.textContent.includes('Second handled email') || false`));
  await evaluate(`document.querySelector('[data-ea-action="confirm-handled-and-next"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]')?.textContent.includes('First handled email') || false`));
  await evaluate(`document.querySelector('[data-ea-action="confirm-handled-and-next"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-workspace-body="home"]')?.textContent.includes('Auto-handled complete') || false`));
  console.log(JSON.stringify({ ok: true, selected: "First handled email", completion: "Auto-handled complete" }));
} finally {
  socket.close();
  await fetch(`${cdpBase}/json/close/${target.id}`).catch(() => {});
}

async function createTarget(url) {
  const response = await fetch(`${cdpBase}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) throw new Error(`Could not create CDP target: ${response.status}`);
  return response.json();
}

function send(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "CDP evaluation failed");
  return result.result.value;
}

async function waitFor(check, timeoutMs = 3000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("Timed out waiting for handled-review navigation.");
}
