import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionRoot = path.join(repoRoot, "extensions", "gmail_companion");
const artifactRoot = path.join(repoRoot, "docs", "gauntlet-evidence", "coverage-2026-08-11");
const tracePath = path.join(artifactRoot, "coverage-trace.json");
const appUrl = "http://127.0.0.1:8891/#inbox/FMcoverage-a";
const viewports = [
  { name: "normal", width: 1280, height: 800 },
  { name: "short", width: 756, height: 469 },
];
const reviewItems = [
  { provider: "gmail", message_id: "coverage-a", thread_id: "thread-coverage", subject: "Quarterly approval", sender: "finance@example.test", suggested_label: "receipt-billing", classification: "EA/Receipts", status: "needs-attention", status_label: "Needs review", reason: "A decision is required." },
  { provider: "gmail", message_id: "coverage-b", thread_id: "thread-coverage", subject: "Travel exception", sender: "travel@example.test", suggested_label: "travel", classification: "EA/Travel", status: "needs-attention", status_label: "Needs review", reason: "A decision is required." },
  { provider: "gmail", message_id: "coverage-c", thread_id: "thread-coverage", subject: "Vendor follow-up", sender: "vendor@example.test", suggested_label: "receipt-billing", classification: "EA/Receipts", status: "needs-attention", status_label: "Needs review", reason: "A decision is required." },
];

const results = { ok: false, tracePath, screenshots: [], states: [], requests: [], forbiddenRequests: [], containment: [] };
let activeStep = "create-target";
let failure = null;
const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const entry = pending.get(message.id);
  pending.delete(message.id);
  message.error ? entry.reject(new Error(message.error.message)) : entry.resolve(message.result);
});
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

try {
  await fs.mkdir(artifactRoot, { recursive: true });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("location.origin === 'http://127.0.0.1:8891'"));
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  activeStep = "install-controlled-gmail";
  await createSyntheticHost();
  await installBridge();
  await injectExtension();
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'coverage-a'"));
  await evaluate("globalThis.__eaTestHooks.setCoverageSyntheticNavigation(true)");
  await evaluate("document.getElementById('ea-brand-toggle')?.click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=review]'))"));

  activeStep = "handled-to-unknown";
  await evaluate("globalThis.__eaTestHooks.showReceipt({ success: true, complete: true, inboxRemoved: false })");
  await evaluate("globalThis.__eaTestHooks.setCoverageState({ status: 'unknown', preserve_surface: true })");
  await waitFor(() => evaluate("document.querySelector('[data-ea-coverage-state=unknown]')?.textContent.includes('This email is handled')"));
  await assertNoReviewProgress("unknown");
  await captureState("handled-unknown");

  activeStep = "click-check-to-queue-ready";
  await evaluate("document.querySelector('[data-ea-action=coverage-check]')?.click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-coverage-state=checking] [data-ea-coverage-indicator=indeterminate]'))"));
  await assertNoReviewProgress("checking");
  await captureState("checking");
  await evaluate(`window.__coverageRespond(${JSON.stringify({
    status: "queue-ready", checked_at: new Date().toISOString(), checked_count: 42,
    candidate_count: 42, needs_review_count: 3, scope: "Current Gmail Inbox messages", review_items: reviewItems,
  })})`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-coverage-state=queue-ready]')?.textContent.includes('3 emails need your review')"));
  assert(await evaluate("document.querySelectorAll('[data-ea-coverage-next]').length === 1"), "queue ready reveals only one next object");
  await captureState("queue-ready");

  activeStep = "review-first-active-variant-c";
  await evaluate("document.querySelector('[data-ea-action=coverage-review]')?.click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]')?.textContent.includes('Quarterly approval')"));
  assert(await evaluate("document.querySelector('[data-ea-review-progress]')?.textContent.trim() === '1 of 3'"), "active review retains 1 of 3");
  assert(await evaluate("Boolean(document.querySelector('[data-ea-review-progress-track]'))"), "active review retains segmented review progress");
  assert(await evaluate("Boolean(document.querySelector('[data-ea-review-facts]'))"), "active review retains Action/Inbox/Scope facts");
  await captureState("review-first");

  activeStep = "coverage-result-states";
  await setAndCapture("verified-clear", { status: "verified-clear", checked_at: new Date().toISOString(), checked_count: 42, candidate_count: 42, needs_review_count: 0, scope: "Current Gmail Inbox messages" });
  await setAndCapture("partial", { status: "partial", checked_at: new Date().toISOString(), checked_count: 31, candidate_count: 42, unchecked_count: 11, needs_review_count: 2, review_items: reviewItems.slice(0, 2), scope: "First 100 current Gmail Inbox messages" });
  await setAndCapture("stale", { status: "verified-clear", checked_at: new Date(Date.now() - 7200000).toISOString(), checked_count: 42, candidate_count: 42, needs_review_count: 0, scope: "Current Gmail Inbox messages" });

  activeStep = "failed-and-offline-transport";
  await evaluate("globalThis.__eaTestHooks.setCoverageState({ status: 'unknown' })");
  await evaluate("document.querySelector('[data-ea-action=coverage-check]')?.click()");
  await evaluate("window.__coverageFail(false)");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-coverage-state=failed]'))"));
  await captureState("failed");
  await evaluate("document.querySelector('[data-ea-action=coverage-check]')?.click()");
  await evaluate("window.__coverageFail(true)");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-coverage-state=offline]'))"));
  await captureState("offline");

  results.requests = await evaluate("JSON.parse(localStorage.getItem('__coverage_requests') || '[]')");
  const allowed = new Set(["email-agent:get-state", "threadwise:analytics", "/api/gmail-coverage-check"]);
  results.forbiddenRequests = results.requests.filter((request) => !allowed.has(request.path || request.type));
  assert(results.forbiddenRequests.length === 0, `forbidden requests: ${results.forbiddenRequests.map((item) => item.path || item.type).join(', ')}`);
  assert(results.requests.filter((request) => request.path === "/api/gmail-coverage-check").length === 3, "only three user-triggered coverage reads ran");
  results.ok = true;
} catch (error) {
  failure = error;
  results.failure = { step: activeStep, message: error.message, stack: error.stack };
} finally {
  await fs.writeFile(tracePath, JSON.stringify(results, null, 2));
  socket.close();
  await fetch(`${cdpBase}/json/close/${target.id}`).catch(() => {});
}

console.log(JSON.stringify(results, null, 2));
if (failure) process.exitCode = 1;

async function setAndCapture(name, fixture) {
  await evaluate(`globalThis.__eaTestHooks.setCoverageState(${JSON.stringify(fixture)})`);
  const expected = name === "stale" ? "stale" : name;
  await waitFor(() => evaluate(`Boolean(document.querySelector('[data-ea-coverage-state=${expected}]'))`));
  await assertNoReviewProgress(expected);
  await captureState(name);
}

async function assertNoReviewProgress(label) {
  assert(!(await evaluate("Boolean(document.querySelector('[data-ea-review-progress-track]'))")), `${label} has no segmented review bar`);
}

async function captureState(name) {
  const state = await evaluate("globalThis.__eaTestHooks.getCoverageState()");
  const rendered = await evaluate(`(() => ({
    header: document.getElementById('ea-status')?.textContent?.trim() || '',
    coverageDisplayed: Boolean(document.querySelector('[data-ea-coverage-state]')),
    facts: Array.from(document.querySelectorAll('[data-ea-coverage-facts] strong')).map((node) => node.textContent.trim()),
  }))()`);
  if (rendered.coverageDisplayed) {
    assert(rendered.header === state.shell, `${name} header projects coverage shell: ${rendered.header} !== ${state.shell}`);
    const checkedFact = state.status === "partial" && state.candidate_count
      ? `${state.checked_count} of ${state.candidate_count}`
      : state.facts.checked;
    assert(rendered.facts.join('|') === [checkedFact, state.facts.review, state.facts.freshness].join('|'), `${name} rendered facts match coverage policy`);
  }
  if (["failed", "offline"].includes(state.status) && !state.checked_at) {
    assert(rendered.facts.join('|') === "—|—|Unknown", `${name} never invents zero/Just now without a completed check`);
  }
  results.states.push({ name, state, rendered });
  for (const viewport of viewports) {
    await send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: false });
    await evaluate("(() => { const content = document.getElementById('ea-content'); if (content) content.scrollTop = 0; window.scrollTo(0, 0); return true; })()");
    const containment = await evaluate(`(() => { const root = document.getElementById('email-agent-companion-root')?.getBoundingClientRect(); return { state: ${JSON.stringify(name)}, viewport: ${JSON.stringify(viewport.name)}, contained: Boolean(root && root.left >= 0 && root.top >= 0 && root.right <= innerWidth + 1 && root.bottom <= innerHeight + 1), root: root ? { left: root.left, top: root.top, right: root.right, bottom: root.bottom, width: root.width, height: root.height } : null }; })()`);
    results.containment.push(containment);
    assert(containment.contained, `${name} is contained at ${viewport.name}`);
    const output = path.join(artifactRoot, `${name}-${viewport.name}.png`);
    const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
    await fs.writeFile(output, Buffer.from(shot.data, "base64"));
    results.screenshots.push(output);
  }
}

async function createSyntheticHost() {
  await evaluate(`(() => {
    document.body.innerHTML = '<main id="synthetic-gmail-host" style="min-height:1300px;padding:30px;background:#f6f8fc;font-family:Arial,sans-serif;"><nav style="height:54px;background:#fff;border-bottom:1px solid #dadce0;">Gmail</nav><h2 data-thread-perm-id="thread-coverage" style="margin:70px 24px 0;">Quarterly approval</h2><div data-legacy-message-id="coverage-a" data-thread-perm-id="thread-coverage" style="margin:18px 24px;padding:18px;background:#fff;"><span email="finance@example.test" data-hovercard-id="finance@example.test">Finance</span><p>Controlled synthetic Gmail message.</p></div></main>';
    document.documentElement.style.margin = '0'; document.body.style.margin = '0';
    return true;
  })()`);
}

async function installBridge() {
  await evaluate(`(() => {
    const items = ${JSON.stringify(reviewItems)};
    const selectedById = Object.fromEntries(items.map((item) => [item.message_id, { found: true, ...item, understanding_state: 'ready', understanding_label: 'Ready', rationale: item.reason, details: {} }]));
    const requests = [];
    const pendingCoverage = [];
    const stateFor = (context = {}) => ({
      selected_context: context,
      sidebar_state: {
        selected_context: context,
        selected_email: selectedById[context.message_id] || selectedById['coverage-a'],
        daily_summary: { processed_count: 3, auto_handled_count: 0, kept_visible_count: 0, needs_attention_count: items.length },
        ui_state: { provider_name: 'Gmail', allowed_labels: [{ id: 'job-related', name: 'EA/Work' }, { id: 'travel', name: 'EA/Travel' }, { id: 'receipt-billing', name: 'EA/Receipts' }], activity_feed: [] },
      },
      needs_attention_items: items,
      recent_items: items,
      auto_handled_items: [], kept_visible_items: [], analytics_status: { state: 'disabled' },
    });
    window.__coverageRespond = (payload) => { const callback = pendingCoverage.shift(); callback?.({ ok: true, payload, connection_state: { kind: 'ready' } }); return Boolean(callback); };
    window.__coverageFail = (offline) => { const callback = pendingCoverage.shift(); callback?.({ ok: false, payload: { error: offline ? 'Offline' : 'Synthetic read failed' }, connection_state: { kind: offline ? 'helper-unreachable' : 'ready' } }); return Boolean(callback); };
    window.chrome = { runtime: {
      lastError: null,
      onMessage: { addListener() {}, removeListener() {} },
      getURL: () => ${JSON.stringify(await assetDataUri())},
      getManifest: () => ({ version: '0.3.2' }),
      sendMessage(message, callback) {
        const request = { type: message?.type || '', path: message?.path || '', method: message?.method || '' };
        requests.push(request); localStorage.setItem('__coverage_requests', JSON.stringify(requests));
        if (message?.type === 'email-agent:get-state') { callback?.({ ok: true, payload: stateFor(message.context || {}), connection_state: { kind: 'ready' } }); return true; }
        if (message?.type === 'threadwise:analytics') { callback?.({ ok: true }); return true; }
        if (message?.type === 'email-agent:api' && message.path === '/api/gmail-coverage-check') { pendingCoverage.push(callback); return true; }
        callback?.({ ok: false, error: 'Forbidden synthetic route.' }); return true;
      },
    }, storage: { local: {
      async get(key) { const value = localStorage.getItem(key); return { [key]: value ? JSON.parse(value) : undefined }; },
      async set(values) { for (const [key, value] of Object.entries(values)) localStorage.setItem(key, JSON.stringify(value)); },
    } } };
    localStorage.setItem('threadwise_onboarding_state', JSON.stringify({ version: '2026-08-09-v1', status: 'dismissed' }));
    localStorage.setItem('__coverage_requests', '[]');
    return true;
  })()`);
}

async function injectExtension() {
  for (const scriptName of ["provider_adapter.js", "analytics.js", "onboarding.js", "queue_navigation.js", "context_actions.js", "selected_explanation.js", "review_progression.js", "coverage.js", "content.js"]) {
    await evaluate(await fs.readFile(path.join(extensionRoot, scriptName), "utf8"));
  }
}

async function assetDataUri() {
  const bytes = await fs.readFile(path.join(extensionRoot, "assets", "brand", "threadwise-app-icon.png"));
  return `data:image/png;base64,${bytes.toString("base64")}#assets/brand/threadwise-app-icon.png`;
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

async function waitFor(check, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 75));
  }
  throw new Error(`Timed out at ${activeStep}: ${await evaluate("document.body.innerText.slice(0, 800)")}`);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
