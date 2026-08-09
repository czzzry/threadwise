import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionRoot = path.join(repoRoot, "extensions", "gmail_companion");
const artifactRoot = "/tmp/threadwise-selected-explanation";
const tracePath = path.join(artifactRoot, "selected-explanation-trace.json");
const appUrl = "http://127.0.0.1:8891/#inbox/FMhigh-review";
const onboardingStorageKey = "threadwise_onboarding_state";
const requestLogStorageKey = "__tw_selected_explanation_request_log";
const onboardingVersion = "2026-08-09-v1";
const seededPageScrollY = 180;
const seededContentScrollTop = 72;
const viewports = [
  { name: "1280x800", width: 1280, height: 800 },
  { name: "756x469", width: 756, height: 469 },
  { name: "360x800", width: 360, height: 800 },
];

const selectedStates = {
  "high-review": {
    found: true,
    provider: "gmail",
    message_id: "high-review",
    subject: "Approval needed today",
    sender: "manager@example.test",
    status: "needs-attention",
    status_label: "Needs attention",
    classification: "EA/Work",
    suggested_label: "job-related",
    internal_label: "job-related",
    reason: "A manager asks for a same-day approval.",
    rationale: "A manager asks for a same-day approval.",
    details: {
      confidence_band: "high",
      near_misses: ["travel", "promotions", "travel"],
      matched_rule_count: 2,
      matched_rule_ids: ["opaque-rule-1", "opaque-rule-2"],
    },
    understanding_state: "ready",
    understanding_label: "Ready",
  },
  "low-no-label": {
    found: true,
    provider: "gmail",
    message_id: "low-no-label",
    subject: "Unclear monthly update",
    sender: "updates@example.test",
    status: "needs-attention",
    status_label: "Needs attention",
    classification: "Uncategorized",
    suggested_label: "",
    internal_label: "",
    reason: "",
    rationale: "",
    details: {
      confidence_band: "low",
      near_misses: ["promotions"],
      matched_rule_count: 0,
    },
    understanding_state: "ready",
    understanding_label: "Ready",
  },
  "missing-evidence": {
    found: true,
    provider: "gmail",
    message_id: "missing-evidence",
    subject: "Stored result without explanation",
    sender: "unknown@example.test",
    status: "needs-attention",
    status_label: "Needs attention",
    classification: "Uncategorized",
    suggested_label: "",
    internal_label: "",
    reason: "",
    rationale: "",
    details: {},
    understanding_state: "ready",
    understanding_label: "Ready",
  },
  "write-unconfirmed": {
    found: true,
    provider: "gmail",
    message_id: "write-unconfirmed",
    subject: "Account confirmation pending",
    sender: "accounts@example.test",
    status: "write-unconfirmed",
    status_label: "Gmail update needs confirmation",
    classification: "EA/Finance",
    suggested_label: "financial-account",
    internal_label: "financial-account",
    reason: "A routine account notice.",
    rationale: "A routine account notice.",
    details: {
      confidence_band: "high",
      near_misses: ["travel"],
      matched_rule_count: 0,
      write_status: "",
      inbox_status: "applied",
    },
    understanding_state: "ready",
    understanding_label: "Ready",
  },
  "handled-why": {
    found: true,
    provider: "gmail",
    message_id: "handled-why",
    subject: "Order receipt",
    sender: "shop@example.test",
    status: "auto-handled",
    status_label: "Auto-handled",
    classification: "EA/Finance",
    suggested_label: "financial-account",
    internal_label: "financial-account",
    reason: "A completed purchase receipt.",
    rationale: "A completed purchase receipt.",
    details: {
      confidence_band: "medium",
      near_misses: ["shopping-order"],
      matched_rule_count: 1,
      write_status: "applied",
      inbox_status: "applied",
    },
    understanding_state: "ready",
    understanding_label: "Ready",
  },
};

const queueItems = [
  { provider: "gmail", message_id: "high-review", subject: "Approval needed today", sender: "manager@example.test", classification: "EA/Work", status_label: "Needs attention", status: "needs-attention" },
  { provider: "gmail", message_id: "low-no-label", subject: "Unclear monthly update", sender: "updates@example.test", classification: "Uncategorized", status_label: "Needs attention", status: "needs-attention" },
];

await fs.mkdir(artifactRoot, { recursive: true });
const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;
let activeStep = "create-target";
let failure = null;
const results = {
  ok: false,
  screenshots: [],
  tracePath,
  requests: [],
  unexpectedRequests: [],
  steps: [],
  focusTrace: [],
  scrollTrace: [],
};

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
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  await createSyntheticHost();
  await installBridge();
  await injectContentScript();
  await waitFor(() => evaluate("Boolean(document.getElementById('email-agent-companion-root'))"));
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getOnboardingState()?.status !== 'loading'"));

  activeStep = "high-confidence-review";
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && document.querySelector('[data-ea-selected-explanation]')"));
  assert(await evaluate("document.querySelector('[data-ea-explanation-confidence]').textContent.trim() === 'High confidence'"), "high-confidence review shows the stored confidence band");
  assert(await evaluate("document.querySelector('[data-ea-explanation-queue-reason]').textContent.trim() === 'Waiting for your review'"), "review shows the pending queue reason");
  assert(await evaluate("document.querySelector('[data-ea-explanation-rationale]').textContent.includes('same-day approval')"), "review shows the stored rationale");
  assert(await evaluate("document.querySelector('[data-ea-action=change-suggestion]')?.textContent.trim() === 'Change label'"), "review keeps one-click Change label visible");
  await captureViewportSet("high-confidence-review");

  activeStep = "evidence-pointer-focus-and-scroll";
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 756 && innerHeight === 469"));
  await seedScroll();
  const evidenceBeforeRequests = await requestCount();
  const evidenceBeforeScroll = await scrollSnapshot();
  await evaluate("document.querySelector('[data-ea-explanation-disclosure]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-explanation-evidence]') && document.querySelector('[data-ea-explanation-disclosure]').getAttribute('aria-expanded') === 'true'"));
  const evidenceAfterScroll = await scrollSnapshot();
  assertScrollUnchanged(evidenceBeforeScroll, evidenceAfterScroll, "evidence pointer open");
  assert((await requestCount()) === evidenceBeforeRequests, "opening evidence makes no request");
  assert(await evaluate("document.activeElement?.hasAttribute('data-ea-explanation-disclosure')"), "evidence pointer open restores disclosure focus");
  assert(await evaluate("document.querySelector('[data-ea-explanation-evidence]').textContent.includes('Also considered')"), "evidence shows canonical near misses");
  assert(await evaluate("document.querySelector('[data-ea-explanation-evidence]').textContent.includes('Saved rules matched')"), "evidence shows matched-rule count");
  assert(await evaluate("!document.querySelector('[data-ea-explanation-evidence]').textContent.includes('opaque-rule-1')"), "evidence does not expose raw rule IDs");
  results.focusTrace.push({ step: "evidence-pointer-open", active: await activeElementSnapshot() });
  results.scrollTrace.push({ step: "evidence-pointer-open", before: evidenceBeforeScroll, after: evidenceAfterScroll });
  await evaluate("document.querySelector('[data-ea-explanation-disclosure]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-explanation-disclosure]').getAttribute('aria-expanded') === 'false'"));
  assert(await evaluate("document.activeElement?.hasAttribute('data-ea-explanation-disclosure')"), "evidence pointer close restores disclosure focus");

  activeStep = "low-confidence-no-label-review";
  await setHostMessage("low-no-label", "Unclear monthly update", "updates@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'low-no-label'"));
  assert(await evaluate("document.querySelector('[data-ea-explanation-confidence]').textContent.trim() === 'Low confidence'"), "low-confidence review shows Low confidence");
  assert(await evaluate("document.querySelector('[data-ea-explanation-queue-reason]').textContent.trim() === 'Threadwise needs your label'"), "no-label review names the label decision");
  assert(await evaluate("document.querySelector('[data-ea-explanation-rationale]').textContent.trim() === 'No classification rationale was stored for this email'"), "missing rationale uses the explicit fallback");
  assert(await evaluate("document.querySelector('[data-ea-action=change-suggestion]')?.textContent.trim() === 'Change label'"), "no-label review keeps Change label directly hit-testable");
  await captureViewportSet("low-confidence-no-label-review");

  activeStep = "missing-evidence-review";
  await setHostMessage("missing-evidence", "Stored result without explanation", "unknown@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'missing-evidence'"));
  assert(await evaluate("document.querySelector('[data-ea-explanation-confidence]').textContent.trim() === 'Confidence not recorded'"), "missing confidence is not promoted to a band");
  assert(await evaluate("!document.querySelector('[data-ea-explanation-disclosure]')"), "missing evidence has no empty disclosure");
  await captureViewportSet("missing-evidence-review");

  activeStep = "write-unconfirmed-recovery-state";
  await setHostMessage("write-unconfirmed", "Account confirmation pending", "accounts@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'write-unconfirmed'"));
  assert(await evaluate("document.querySelector('[data-ea-explanation-queue-reason]').textContent.trim() === 'Gmail has not confirmed this label update'"), "write-unconfirmed names provider recovery");
  assert(await evaluate("document.querySelector('[data-ea-explanation-confidence]').textContent.trim() === 'High confidence'"), "provider recovery does not rewrite model confidence");
  await evaluate("document.querySelector('[data-ea-explanation-disclosure]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-explanation-evidence]')"));
  assert(await evaluate("document.querySelector('[data-ea-explanation-evidence]').textContent.includes('Provider label update') && document.querySelector('[data-ea-explanation-evidence]').textContent.includes('Not confirmed')"), "provider recovery evidence is explicit");
  await evaluate("document.querySelector('[data-ea-explanation-disclosure]').click()");
  await captureViewportSet("write-unconfirmed-recovery");

  activeStep = "queue-preview-context-replacement";
  await evaluate("globalThis.__eaTestHooks.openQueueItem('high-review')");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().queuePreviewActive && globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'high-review'"));
  await evaluate("document.querySelector('[data-ea-explanation-disclosure]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-explanation-evidence]')"));
  await evaluate("globalThis.__eaTestHooks.openQueueItem('low-no-label')");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'low-no-label' && document.querySelector('[data-ea-selected-state=review]')"));
  assert(await evaluate("!document.querySelector('[data-ea-explanation-evidence]')"), "selected-message change closes old evidence");
  assert(await evaluate("document.querySelector('[data-ea-explanation-confidence]').textContent.trim() === 'Low confidence'"), "selected-message change replaces confidence");
  assert(await evaluate("!document.querySelector('[data-ea-explanation-rationale]').textContent.includes('same-day approval')"), "selected-message change removes stale rationale");
  await captureViewportSet("queue-preview");

  activeStep = "handled-why-keyboard";
  await evaluate("globalThis.__eaTestHooks.returnToLive()");
  await setHostMessage("handled-why", "Order receipt", "shop@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')"));
  const whyBeforeRequests = await requestCount();
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'open-email,why'"));
  await pressKey("ArrowDown");
  assert(await evaluate("document.activeElement?.getAttribute('data-ea-context-item') === 'why'"), "handled Why is keyboard reachable");
  await pressKey("Enter");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().detailsExpanded === true && document.querySelector('#ea-handled-why [data-ea-selected-explanation]') && !globalThis.__eaTestHooks.getContextActions().open"));
  assert((await requestCount()) === whyBeforeRequests, "handled Why makes no request");
  assert(await evaluate("document.querySelector('#ea-handled-why [data-ea-explanation-confidence]').textContent.trim() === 'Medium confidence'"), "handled Why reuses stored confidence");
  assert(await evaluate("document.querySelector('#ea-handled-why [data-ea-explanation-rationale]').textContent.includes('completed purchase')"), "handled Why reuses the stored rationale");
  assert(await evaluate("document.querySelector('[data-ea-action=change-auto-handled]')?.textContent.trim() === 'Change'"), "handled receipt keeps one-click Change visible");
  await captureViewportSet("handled-why");

  results.ok = true;
} catch (error) {
  failure = error;
  results.failure = { step: activeStep, message: error.message, stack: error.stack };
} finally {
  try {
    results.requests = await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || "[]")`);
  } catch (_error) {
    results.requests = [];
  }
  results.unexpectedRequests = results.requests.filter((request) => !(
    request?.type === "email-agent:get-state" && request.path === "" && request.method === ""
  ) && !(
    request?.type === "threadwise:analytics" && request.path === "" && request.method === ""
  ));
  await fs.writeFile(tracePath, JSON.stringify(results, null, 2));
  socket.close();
}

console.log(JSON.stringify(results, null, 2));
if (failure || results.unexpectedRequests.length) process.exitCode = 1;

async function installBridge() {
  await evaluate(`(() => {
    const logKey = ${JSON.stringify(requestLogStorageKey)};
    localStorage.setItem(${JSON.stringify(onboardingStorageKey)}, JSON.stringify({ version: ${JSON.stringify(onboardingVersion)}, status: "dismissed" }));
    localStorage.setItem(logKey, "[]");
    const append = (request) => { const log = JSON.parse(localStorage.getItem(logKey) || "[]"); log.push(request); localStorage.setItem(logKey, JSON.stringify(log)); };
    const clone = (value) => JSON.parse(JSON.stringify(value));
    const states = ${JSON.stringify(selectedStates)};
    const queueItems = ${JSON.stringify(queueItems)};
    const allowedLabels = [
      ["travel", "Travel"], ["receipt-billing", "Receipts"], ["shopping-order", "Orders"], ["financial-account", "Finance"],
      ["newsletter", "Newsletter"], ["promotions", "Promotions"], ["account-security", "Account"], ["calendar-event", "Calendar"],
      ["personal", "Personal"], ["job-related", "Work"], ["spam-low-value", "LowValue"], ["reply-needed", "NeedsAction"], ["suspicious", "Suspicious"],
    ].map(([id, name]) => ({ id, name: "EA/" + name }));
    const stateForContext = (context) => {
      const id = context?.message_id || "high-review";
      const baseState = {
        selected_context: context || {},
        sidebar_state: {
          selected_context: context || {},
          selected_email: clone(states[id] || states["high-review"]),
          daily_summary: { needs_attention_count: queueItems.length, processed_count: 5, auto_handled_count: 1, kept_visible_count: 1, changed_today: {} },
          ui_state: { provider_name: "Gmail", allowed_labels: allowedLabels, async_follow_up: {} },
        },
        needs_attention_items: queueItems,
        recent_items: queueItems,
        auto_handled_items: [],
        kept_visible_items: [],
        analytics_status: { state: "disabled" },
      };
      baseState.sidebar_state.selected_email.provider = "gmail";
      baseState.sidebar_state.selected_email.message_id = id;
      return baseState;
    };
    window.chrome = { runtime: {
      lastError: null,
      onMessage: { addListener: () => undefined, removeListener: () => undefined },
      getURL: () => ${JSON.stringify(await assetDataUri())},
      getManifest: () => ({ version: "0.3.2" }),
      sendMessage(message, callback) {
        append({ type: message?.type || "unknown", path: message?.path || "", method: message?.method || "" });
        if (message?.type === "email-agent:get-state") { callback?.({ ok: true, payload: stateForContext(message.context || {}), connection_state: { kind: "ready", label: "Ready", details: "Synthetic fixture state." } }); return true; }
        if (message?.type === "threadwise:analytics") { callback?.({ ok: true }); return true; }
        callback?.({ ok: false, error: "Selected-explanation validator rejects " + (message?.path || message?.type || "unknown") + "." });
        return true;
      },
    }, storage: { local: {
      async get(key) { const raw = localStorage.getItem(key); return { [key]: raw ? JSON.parse(raw) : undefined }; },
      async set(values) { Object.entries(values).forEach(([key, value]) => localStorage.setItem(key, JSON.stringify(value))); },
    } } };
    return true;
  })()`);
}

async function injectContentScript() {
  for (const scriptName of ["provider_adapter.js", "analytics.js", "onboarding.js", "queue_navigation.js", "context_actions.js", "selected_explanation.js", "review_progression.js", "content.js"]) {
    await evaluate(await fs.readFile(path.join(extensionRoot, scriptName), "utf8"));
  }
}

async function createSyntheticHost() {
  await evaluate(`(() => {
    document.body.innerHTML = '<main id="synthetic-gmail-host" style="min-height:1600px;margin:0;padding:32px 36px;background:#f4efe5;color:#241812;font-family:system-ui,sans-serif;"><h2 data-thread-perm-id="thread-selected" style="margin-top:96px;font-size:28px;">Approval needed today</h2><div data-legacy-message-id="high-review" data-thread-perm-id="thread-selected" style="display:block;max-width:620px;padding:20px;background:#fffdf8;border:1px solid #ded3c1;"><span email="manager@example.test" data-hovercard-id="manager@example.test">Manager</span><p>Synthetic Gmail host content for explanation acceptance.</p></div></main>';
    document.documentElement.style.margin = "0"; document.body.style.margin = "0"; document.documentElement.style.scrollBehavior = "auto"; document.body.style.scrollBehavior = "auto";
    return true;
  })()`);
}

async function setHostMessage(messageId, subject, sender) {
  await evaluate(`(() => { const host = document.getElementById('synthetic-gmail-host'); const heading = host.querySelector('h2'); const message = host.querySelector('[data-legacy-message-id]'); heading.textContent = ${JSON.stringify(subject)}; message.setAttribute('data-legacy-message-id', ${JSON.stringify(messageId)}); message.querySelector('[email]').setAttribute('email', ${JSON.stringify(sender)}); window.location.hash = ${JSON.stringify(`#inbox/FM${messageId}`)}; return true; })()`);
}

async function captureViewportSet(stateName) {
  for (const viewport of viewports) {
    await send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: false });
    await waitFor(() => evaluate("Boolean(document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width)"));
    const containment = await containmentSnapshot();
    assert(containment.contained, `${stateName} is contained at ${viewport.name}`);
    if (["high-confidence-review", "low-confidence-no-label-review", "write-unconfirmed-recovery"].includes(stateName)) {
      const controls = await evaluate(`(() => { const node = document.querySelector('[data-ea-action="change-suggestion"]'); const rect = node?.getBoundingClientRect(); return { visible: Boolean(rect && rect.width > 0 && rect.height > 0), height: rect?.height || 0, text: node?.textContent.trim() || "" }; })()`);
      assert(controls.visible && controls.height >= 44 && controls.text === "Change label", `${stateName} keeps a 44px Change label at ${viewport.name}`);
    }
    const outputPath = path.join(artifactRoot, `${stateName}-${viewport.name}.png`);
    await captureScreenshot(outputPath);
    results.screenshots.push({ state: stateName, viewport: viewport.name, path: outputPath, containment });
  }
}

async function seedScroll() {
  await evaluate(`(() => { const content = document.getElementById('ea-content'); window.scrollTo(0, ${seededPageScrollY}); content.scrollTop = ${seededContentScrollTop}; return true; })()`);
  const snapshot = await scrollSnapshot();
  assert(snapshot.pageY === seededPageScrollY, `seeded Gmail-page scroll is ${seededPageScrollY}`);
  assert(snapshot.contentScrollTop > 0, `seeded companion scroll is nonzero: ${snapshot.contentScrollTop}`);
  return snapshot;
}

async function scrollSnapshot() {
  return evaluate("(() => ({ pageX: window.scrollX, pageY: window.scrollY, contentScrollTop: document.getElementById('ea-content')?.scrollTop || 0, contentScrollLeft: document.getElementById('ea-content')?.scrollLeft || 0, contentScrollHeight: document.getElementById('ea-content')?.scrollHeight || 0, contentClientHeight: document.getElementById('ea-content')?.clientHeight || 0 }))()");
}

function assertScrollUnchanged(before, after, step) {
  for (const key of ["pageX", "pageY", "contentScrollTop", "contentScrollLeft"]) {
    assert(before[key] === after[key], `${step} preserves ${key}: ${before[key]} -> ${after[key]}`);
  }
}

async function containmentSnapshot() {
  return evaluate("(() => { const root = document.getElementById('email-agent-companion-root')?.getBoundingClientRect(); const host = document.getElementById('synthetic-gmail-host')?.getBoundingClientRect(); return { contained: Boolean(root && root.left >= 0 && root.top >= 0 && root.right <= innerWidth + 1 && root.bottom <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth && host?.left === 0), root: root ? { left: root.left, top: root.top, right: root.right, bottom: root.bottom, width: root.width } : null, viewport: { width: innerWidth, height: innerHeight } }; })()");
}

async function activeElementSnapshot() {
  return evaluate("document.activeElement ? { tag: document.activeElement.tagName, action: document.activeElement.getAttribute('data-ea-action') || '', disclosure: document.activeElement.hasAttribute('data-ea-explanation-disclosure'), contextItem: document.activeElement.getAttribute('data-ea-context-item') || '' } : null");
}

async function requestCount() {
  return evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || "[]").length`);
}

async function captureScreenshot(outputPath) {
  const result = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  await fs.writeFile(outputPath, Buffer.from(result.data, "base64"));
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
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Evaluation failed");
  return result.result.value;
}

async function waitFor(fn, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out at ${activeStep}: ${await evaluate("document.body.innerText.slice(0, 1200)").catch(() => "unavailable")}`);
}

async function pressKey(key) {
  await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key, code: /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : key, windowsVirtualKeyCode: /^[a-z]$/i.test(key) ? key.toUpperCase().charCodeAt(0) : 0 });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key, code: /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : key, windowsVirtualKeyCode: /^[a-z]$/i.test(key) ? key.toUpperCase().charCodeAt(0) : 0 });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
