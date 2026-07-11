import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const contentScript = await fs.readFile(path.join(repoRoot, "extensions/gmail_companion/content.js"), "utf8");
const target = await createTarget("about:blank");
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
const uncaughtErrors = [];
let nextId = 1;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") uncaughtErrors.push(message.params.exceptionDetails);
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
    window.__workspaceState = {
      selected_context: {},
      selected_email: {
        found: true,
        message_id: "synthetic-1",
        subject: "Synthetic review email",
        sender: "fixture@example.invalid",
        classification: "EA/Work",
        status: "needs-attention",
        status_label: "Needs attention",
        reason: "Synthetic acceptance fixture",
        details: {}
      },
      daily_summary: { processed_count: 12, auto_handled_count: 2, kept_visible_count: 7 },
      ui_state: { allowed_labels: [
        { id: "EA/Work", name: "Work" },
        { id: "EA/Promotions", name: "Promotions" }
      ] }
    };
    const listeners = [];
    window.chrome = { runtime: {
      lastError: null,
      getURL: (value) => value,
      onMessage: { addListener: (listener) => listeners.push(listener), removeListener: () => undefined },
      sendMessage: (_message, callback) => callback({ ok: true, payload: window.__workspaceState })
    }};
    return true;
  })()`);
  await evaluate(contentScript);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-workspace-body="selected-email"]') !== null`));
  const selected = await workspaceSnapshot();
  const review = await decisionSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="change-suggestion"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  const change = await decisionSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="cancel-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null`));
  const reviewAfterCancel = await decisionSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_email: {
        found: true,
        message_id: "synthetic-auto-1",
        subject: "Synthetic handled email",
        sender: "fixture@example.invalid",
        classification: "EA/Newsletter",
        status: "auto-handled",
        status_label: "Auto-handled",
        reason: "Matched the newsletter signals.",
        details: { inbox_status: "kept" }
      }
    };
    window.__eaTestHooks.forceRefresh();
    return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="auto-handled"]') !== null`));
  const autoHandled = await autoHandledSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="toggle-details"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('#ea-selected-email-secondary')?.textContent.includes('Matched the newsletter signals.')`));
  const autoHandledWhy = await evaluate(`document.querySelector('#ea-selected-email-secondary')?.textContent.trim() || ''`);
  await evaluate(`document.querySelector('[data-ea-action="change-auto-handled"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('#ea-teach-note') !== null`));
  const autoHandledChangeOpened = await evaluate(`document.querySelector('#ea-teach-note') !== null`);

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_email: {
        ...window.__workspaceState.selected_email,
        message_id: "synthetic-auto-2",
        details: { inbox_status: "applied" }
      }
    };
    window.__eaTestHooks.forceRefresh();
    return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-auto-handled-receipt]')?.textContent.includes('removed it from Inbox')`));
  const autoHandledRemovedReceipt = await evaluate(`document.querySelector('[data-ea-auto-handled-receipt]')?.textContent.trim() || ''`);

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_email: { found: false },
      daily_summary: { processed_count: 12, auto_handled_count: 2, kept_visible_count: 7 }
    };
    window.__eaTestHooks.forceRefresh();
    return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-workspace-body="home"]') !== null`));
  const home = await workspaceSnapshot();

  const result = { selected, review, change, reviewAfterCancel, autoHandled, autoHandledWhy, autoHandledChangeOpened, autoHandledRemovedReceipt, home, uncaughtErrorCount: uncaughtErrors.length };
  console.log(JSON.stringify(result, null, 2));
  if (
    selected.bodyCount !== 1 || selected.mode !== "selected-email" || selected.hasHome || selected.hasDailySummary ||
    review.state !== "review" || review.primaryActions.join(",") !== "Accept Work" ||
    review.suggestion !== "Threadwise suggests Work" || review.hasLabelPicker || review.hasNote ||
    change.state !== "change" || change.primaryActions.join(",") !== "Preview change" ||
    change.selectedLabel !== "EA/Work" || !change.hasLabelPicker || !change.hasNote ||
    reviewAfterCancel.state !== "review" || reviewAfterCancel.primaryActions.length !== 1 ||
    autoHandled.heading !== "Newsletter · Auto-handled" ||
    autoHandled.receipt !== "Threadwise applied Newsletter and kept this email in Inbox." ||
    autoHandled.hasCorrectionForm || autoHandled.actions.join(",") !== "Change,Why" ||
    !autoHandledWhy.includes("Matched the newsletter signals.") || !autoHandledChangeOpened ||
    autoHandledRemovedReceipt !== "Threadwise applied Newsletter and removed it from Inbox." ||
    home.bodyCount !== 1 || home.mode !== "home" || home.hasSelectedEmail || !home.hasDailySummary ||
    uncaughtErrors.length
  ) process.exitCode = 1;
} finally {
  socket.close();
  await fetch(`${cdpBase}/json/close/${target.id}`).catch(() => {});
}

async function decisionSnapshot() {
  return evaluate(`(() => {
    const state = document.querySelector('[data-ea-selected-state]');
    return {
      state: state?.dataset.eaSelectedState || '',
      suggestion: state?.querySelector('[data-ea-review-suggestion]')?.textContent?.trim() || '',
      primaryActions: [...(state?.querySelectorAll('[data-tw-primary-action]') || [])].map((node) => node.textContent.trim()),
      hasLabelPicker: !!state?.querySelector('#ea-target-label'),
      selectedLabel: state?.querySelector('#ea-target-label')?.value || '',
      hasNote: !!state?.querySelector('#ea-teach-note')
    };
  })()`);
}

async function autoHandledSnapshot() {
  return evaluate(`(() => {
    const state = document.querySelector('[data-ea-selected-state="auto-handled"]');
    return {
      heading: state?.querySelector('[data-ea-auto-handled-heading]')?.textContent?.trim() || '',
      receipt: state?.querySelector('[data-ea-auto-handled-receipt]')?.textContent?.trim() || '',
      hasCorrectionForm: !!document.querySelector('#ea-teach-note, #ea-target-label'),
      actions: [...(state?.querySelectorAll('button') || [])].map((node) => node.textContent.trim())
    };
  })()`);
}

async function workspaceSnapshot() {
  return evaluate(`(() => {
    const workspace = document.querySelector('#ea-workspace');
    return {
      mode: workspace?.dataset.eaWorkspaceMode || '',
      bodyCount: workspace?.querySelectorAll(':scope > [data-ea-workspace-body]').length || 0,
      hasHome: !!workspace?.querySelector('[data-ea-workspace-body="home"]'),
      hasSelectedEmail: !!workspace?.querySelector('#ea-selected-email'),
      hasDailySummary: !!workspace?.querySelector('#ea-daily-summary')
    };
  })()`);
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
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}

async function waitFor(fn, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Timed out waiting for workspace state.");
}
