import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionRoot = path.join(repoRoot, "extensions", "gmail_companion");
const screenshotDesktop = "/tmp/threadwise-onboarding-candidate-desktop.png";
const screenshotNarrow = "/tmp/threadwise-onboarding-candidate-narrow.png";
const onboardingStorageKey = "threadwise_onboarding_state";
const baseStateStorageKey = "__tw_onboarding_base_state";
const connectionStateStorageKey = "__tw_onboarding_connection_state";
const requestLogStorageKey = "__tw_onboarding_request_log";
const assetBytes = await fs.readFile(path.join(extensionRoot, "assets", "brand", "threadwise-app-icon.png"));
const assetDataUri = `data:image/png;base64,${assetBytes.toString("base64")}#assets/brand/threadwise-app-icon.png`;

const selectedItem = {
  found: true,
  provider: "gmail",
  message_id: "selected-1",
  subject: "Selected synthetic message",
  sender: "selected@example.test",
  status: "needs-attention",
};
const queueItem = {
  provider: "gmail",
  message_id: "queue-1",
  subject: "Next synthetic message",
  sender: "queue@example.test",
  status: "needs-attention",
};

const appUrl = "http://127.0.0.1:8891/#inbox/FMselected1";
const target = await createTarget(appUrl);
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

const results = {
  screenshots: { desktop: screenshotDesktop, narrow: screenshotNarrow },
  requests: [],
};

try {
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: 756,
    height: 469,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  await createSyntheticHost();

  await installBridge(baseState("selected"));
  await injectContentScript();
  await waitFor(() => evaluate("!!document.getElementById('email-agent-companion-root')"));
  await waitFor(() => evaluate("!!globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail"));

  results.initial = await evaluate(`(() => {
    const root = document.getElementById("email-agent-companion-root");
    return {
      minimized: root?.dataset.eaMinimized === "true",
      contentHidden: document.getElementById("ea-content")?.style.display === "none",
      onboardingVisible: Boolean(root?.querySelector("[data-ea-onboarding]")),
      rootWidth: root?.getBoundingClientRect().width || 0,
    };
  })()`);
  assert(results.initial.minimized, "fresh mount remains minimized");
  assert(results.initial.contentHidden, "fresh mount keeps panel content hidden");
  assert(!results.initial.onboardingVisible, "fresh mount does not auto-expand onboarding");

  await openPanel();
  results.onboarding = await onboardingSnapshot();
  assert(results.onboarding.visible, "explicit open reveals onboarding");
  assert(results.onboarding.logoSrc.includes("threadwise-app-icon.png"), "onboarding uses the approved icon asset");
  assert(results.onboarding.text.includes("classifies and labels"), "onboarding explains classification and labels");
  assert(results.onboarding.text.includes("explains why"), "onboarding explains explanations");
  assert(results.onboarding.text.includes("lets you correct"), "onboarding explains correction");
  assert(results.onboarding.text.includes("Broader changes are previewed"), "onboarding explains previewed broader changes");
  assert(results.onboarding.text.includes("never writes or sends replies"), "onboarding states the reply boundary");
  assert(!results.onboarding.text.includes("Choose Gmail"), "onboarding has no provider chooser");
  assert(!results.onboarding.text.includes("TW"), "onboarding has no substitute text mark");
  assert(results.onboarding.focusedPrimary, "onboarding focuses its contextual primary action");
  assert(results.onboarding.targetKind === "selected-email", "selected email is the first handoff target");

  results.desktopLayout = await onboardingLayoutSnapshot();
  assert(results.desktopLayout.viewport.width === 756 && results.desktopLayout.viewport.height === 469, "desktop acceptance uses a 756x469 viewport");
  assert(results.desktopLayout.contentScrollTop <= 1, "desktop onboarding focus does not scroll the content container");
  assert(results.desktopLayout.allRequiredVisible, "desktop identity, headline, explanation, status, and primary action are visible together");
  assert(results.desktopLayout.primaryFocused, "desktop primary action remains focused while the required content is visible");

  await captureScreenshot(screenshotDesktop);
  results.desktopContainment = await containmentSnapshot();
  assert(results.desktopContainment.contained, "desktop companion is contained");

  await send("Emulation.setDeviceMetricsOverride", {
    width: 360,
    height: 800,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width > 0"));
  results.narrowContainment = await containmentSnapshot();
  assert(results.narrowContainment.contained, "narrow companion is contained without host displacement");
  results.narrowLayout = await onboardingLayoutSnapshot();
  assert(results.narrowLayout.allRequiredVisible, "narrow onboarding keeps required content and the primary action usable");
  assert(results.narrowLayout.primaryUsable, "narrow primary action has a usable target size");
  await captureScreenshot(screenshotNarrow);

  await send("Page.bringToFront");
  const keyboardFocusReady = await evaluate(`(() => {
    const action = document.querySelector('[data-ea-action="onboarding-continue"]');
    action?.focus({ preventScroll: true });
    return document.activeElement === action;
  })()`);
  assert(keyboardFocusReady, "primary action is focused before keyboard activation");
  await pressKey("Enter");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"review\"]') !== null"));
  results.continueHandoff = await evaluate(`({
    state: globalThis.__eaTestHooks.getOnboardingState(),
    review: Boolean(document.querySelector('[data-ea-selected-state="review"]')),
    onboardingVisible: Boolean(document.querySelector('[data-ea-onboarding]')),
  })`);
  assert(results.continueHandoff.state.status === "completed", "Continue persists completed onboarding state");
  assert(results.continueHandoff.review, "Continue enters selected-email review");
  assert(!results.continueHandoff.onboardingVisible, "Continue removes onboarding after handoff");

  await reloadAndInject();
  results.afterContinueReload = await reloadPersistenceCheck("completed");
  assert(results.afterContinueReload.minimized, "reload returns the companion to minimized state");
  assert(!results.afterContinueReload.onboardingVisible, "completed onboarding stays out of the way after reload");

  await clearOnboardingAndSetBase("queue");
  await reloadAndInject();
  await openPanel();
  const queueOnboarding = await onboardingSnapshot();
  assert(queueOnboarding.targetKind === "needs-attention", "queue handoff selects the active provider queue");
  await clickPrimary();
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"review\"]') !== null"));
  results.queueHandoff = await evaluate(`({
    subject: document.querySelector('[data-ea-selected-state="review"]')?.innerText || "",
    target: globalThis.__eaTestHooks.getOnboardingState().target,
  })`);
  assert(results.queueHandoff.subject.includes("Next synthetic message"), "queue Continue opens the next real review item");

  await clearOnboardingAndSetBase("home");
  await reloadAndInject();
  await openPanel();
  const homeOnboarding = await onboardingSnapshot();
  assert(homeOnboarding.targetKind === "home", "Home is the honest final handoff target");
  await clickPrimary();
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"home\"]') !== null"));
  results.homeHandoff = await evaluate(`({
    home: Boolean(document.querySelector('[data-ea-selected-state="home"]')),
    onboardingVisible: Boolean(document.querySelector('[data-ea-onboarding]')),
  })`);
  assert(results.homeHandoff.home, "Home handoff enters the existing Home destination");
  assert(!results.homeHandoff.onboardingVisible, "Home handoff removes onboarding");

  await clearOnboardingAndSetBase("offline");
  await reloadAndInject();
  await openPanel();
  const offlineOnboarding = await onboardingSnapshot();
  assert(offlineOnboarding.targetKind === "not-ready", "offline onboarding does not invent a ready destination");
  assert(offlineOnboarding.text.includes("Start the local companion and check again."), "offline onboarding gives truthful remediation");
  assert(!offlineOnboarding.text.includes("Using Gmail from this tab"), "offline onboarding does not claim a ready connection");
  assert(await evaluate(`Boolean(document.querySelector('[data-ea-action="onboarding-retry"]'))`), "offline onboarding offers Check again");
  await clickPrimary();
  await waitFor(() => evaluate("document.querySelector('[data-ea-action=\"onboarding-retry\"]') !== null"));
  results.offline = await evaluate(`({
    state: globalThis.__eaTestHooks.getOnboardingState(),
    onboardingVisible: Boolean(document.querySelector('[data-ea-onboarding]')),
    retryVisible: Boolean(document.querySelector('[data-ea-action="onboarding-retry"]')),
  })`);
  assert(results.offline.state.status === "active", "offline retry does not falsely complete onboarding");
  assert(results.offline.onboardingVisible && results.offline.retryVisible, "offline retry remains truthful and actionable");

  await clearOnboardingAndSetBase("selected");
  await reloadAndInject();
  await openPanel();
  await evaluate(`document.querySelector('[data-ea-action="onboarding-skip"]').focus()`);
  await evaluate("document.activeElement?.click()");
  await waitFor(() => evaluate("!document.querySelector('[data-ea-onboarding]')"));
  results.skip = await evaluate(`({
    state: globalThis.__eaTestHooks.getOnboardingState(),
    review: Boolean(document.querySelector('[data-ea-selected-state="review"]')),
  })`);
  assert(results.skip.state.status === "dismissed", "Skip persists dismissed onboarding state");
  assert(results.skip.review, "Skip still enters the existing selected review destination");

  await reloadAndInject();
  results.afterSkipReload = await reloadPersistenceCheck("dismissed");
  assert(!results.afterSkipReload.onboardingVisible, "dismissed onboarding stays out of the way after reload");

  results.requests = await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || "[]")`);
  const forbidden = results.requests.filter((request) =>
    request.type === "email-agent:api"
    || /provider-sync|gmail-check|teach-apply|safety-(preview|apply)|unsubscribe|write|reply|send/i.test(request.path || ""),
  );
  results.forbiddenRequests = forbidden;
  assert(forbidden.length === 0, "onboarding triggers no provider sync, teaching, safety, unsubscribe, or write request");
  results.ok = true;
  console.log(JSON.stringify(results, null, 2));
} finally {
  socket.close();
}

async function installBridge(state) {
  const stateLiteral = JSON.stringify(state);
  await evaluate(`(() => {
    const initialState = ${stateLiteral};
    if (initialState !== null) {
      localStorage.removeItem(${JSON.stringify(onboardingStorageKey)});
      localStorage.removeItem(${JSON.stringify(requestLogStorageKey)});
      localStorage.setItem(${JSON.stringify(baseStateStorageKey)}, JSON.stringify(initialState));
      localStorage.setItem(${JSON.stringify(connectionStateStorageKey)}, JSON.stringify({
        kind: "ready",
        label: "Ready",
        details: "Threadwise is connected.",
      }));
    }
    const requestLogKey = ${JSON.stringify(requestLogStorageKey)};
    const appendRequest = (request) => {
      const requests = JSON.parse(localStorage.getItem(requestLogKey) || "[]");
      requests.push(request);
      localStorage.setItem(requestLogKey, JSON.stringify(requests));
    };
    const clone = (value) => JSON.parse(JSON.stringify(value));
    const stateForContext = (context) => {
      const base = clone(JSON.parse(localStorage.getItem(${JSON.stringify(baseStateStorageKey)})));
      const selectedQueueItem = (base.needs_attention_items || []).find((item) =>
        item.message_id && item.message_id === context?.message_id
      );
      if (selectedQueueItem) {
        base.sidebar_state.selected_email = {
          found: true,
          provider: selectedQueueItem.provider,
          message_id: selectedQueueItem.message_id,
          subject: selectedQueueItem.subject,
          sender: selectedQueueItem.sender,
          status: "needs-attention",
          status_label: "Needs attention",
          classification: "EA/Work",
          suggested_label: "work",
          internal_label: "work",
          details: {},
          understanding_state: "ready",
          understanding_label: "Ready",
        };
      }
      base.sidebar_state.selected_context = context || {};
      base.selected_context = context || {};
      return base;
    };
    const storage = {
      async get(key) {
        const raw = localStorage.getItem(key);
        return { [key]: raw ? JSON.parse(raw) : undefined };
      },
      async set(values) {
        Object.entries(values).forEach(([key, value]) => localStorage.setItem(key, JSON.stringify(value)));
      },
    };
    const bridge = {
      lastError: null,
      onMessage: { addListener: () => undefined, removeListener: () => undefined },
      getURL: () => ${JSON.stringify(assetDataUri)},
      getManifest: () => ({ version: "0.3.2" }),
      sendMessage(message, callback) {
        appendRequest({ type: message?.type || "unknown", path: message?.path || "", method: message?.method || "" });
        if (message?.type === "email-agent:get-state") {
          const connectionState = JSON.parse(localStorage.getItem(${JSON.stringify(connectionStateStorageKey)}) || "null") || {
            kind: "ready",
            label: "Ready",
            details: "Threadwise is connected.",
          };
          callback?.({
            ok: true,
            payload: stateForContext(message.context || {}),
            connection_state: connectionState,
          });
          return true;
        }
        if (message?.type === "threadwise:analytics") {
          callback?.({ ok: true });
          return true;
        }
        callback?.({ ok: false, error: "Synthetic onboarding bridge rejects " + (message?.path || message?.type || "unknown") + "." });
        return true;
      },
    };
    window.chrome = { runtime: bridge, storage: { local: storage } };
    window.__twOnboardingSyntheticBridge = true;
    return true;
  })()`);
}

async function injectContentScript() {
  const scripts = ["provider_adapter.js", "analytics.js", "onboarding.js", "content.js"];
  for (const scriptName of scripts) {
    const script = await fs.readFile(path.join(extensionRoot, scriptName), "utf8");
    await evaluate(script);
  }
}

async function reloadAndInject() {
  await send("Page.reload", { ignoreCache: true });
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  await createSyntheticHost();
  await installBridge(nullStateFromStorage());
  await injectContentScript();
  await waitFor(() => evaluate("!!document.getElementById('email-agent-companion-root')"));
  await waitFor(() => evaluate("!!globalThis.__eaTestHooks?.getSnapshot()"));
}

function nullStateFromStorage() {
  return null;
}

async function openPanel() {
  await waitFor(() => evaluate("document.querySelector('#ea-brand-toggle') !== null"));
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-onboarding]') !== null"));
}

async function createSyntheticHost() {
  await evaluate(`(() => {
    document.body.innerHTML = ${JSON.stringify(`
      <main id="synthetic-gmail-host" style="min-height:100vh;margin:0;padding:32px 36px;background:#f4efe5;color:#241812;font-family:system-ui,sans-serif;">
        <div style="height:18px;width:240px;background:#e2d8c8;border-radius:4px;"></div>
        <h2 data-thread-perm-id="thread-selected" style="margin-top:96px;font-size:28px;">Selected synthetic message</h2>
        <div data-legacy-message-id="selected-1" data-thread-perm-id="thread-selected" style="display:block;max-width:620px;padding:20px;background:#fffdf8;border:1px solid #ded3c1;">
          <span email="selected@example.test" data-hovercard-id="selected@example.test">Selected Sender</span>
          <p style="line-height:1.6;">Synthetic Gmail host content for Threadwise onboarding acceptance.</p>
        </div>
      </main>
    `)};
    document.documentElement.style.margin = "0";
    document.body.style.margin = "0";
    return true;
  })()`);
}

async function clickPrimary() {
  await evaluate(`document.querySelector('[data-ea-action="onboarding-continue"], [data-ea-action="onboarding-retry"]')?.click()`);
}

async function onboardingSnapshot() {
  return evaluate(`(() => {
    const root = document.getElementById("email-agent-companion-root");
    const onboarding = root?.querySelector("[data-ea-onboarding]");
    const action = onboarding?.querySelector('[data-ea-action="onboarding-continue"], [data-ea-action="onboarding-retry"]');
    return {
      visible: Boolean(onboarding),
      text: onboarding?.innerText || "",
      logoSrc: onboarding?.querySelector('[data-ea-onboarding-logo]')?.getAttribute("src") || "",
      focusedPrimary: document.activeElement === action,
      targetKind: globalThis.__eaTestHooks.getOnboardingState().target.kind,
    };
  })()`);
}

async function onboardingLayoutSnapshot() {
  return evaluate(`(() => {
    const content = document.getElementById("ea-content");
    const viewport = content?.getBoundingClientRect();
    const selectors = {
      identity: "[data-ea-onboarding-identity]",
      headline: "[data-ea-onboarding-title]",
      explanation: "[data-ea-onboarding-description]",
      status: "[data-ea-onboarding-status]",
      primary: '[data-ea-action="onboarding-continue"]',
    };
    const visibleInContent = (selector) => {
      const node = document.querySelector(selector);
      const rect = node?.getBoundingClientRect();
      return Boolean(
        rect
        && viewport
        && rect.left >= viewport.left - 1
        && rect.right <= viewport.right + 1
        && rect.top >= viewport.top - 1
        && rect.bottom <= viewport.bottom + 1,
      );
    };
    const requiredVisible = Object.fromEntries(
      Object.entries(selectors).map(([name, selector]) => [name, visibleInContent(selector)]),
    );
    const primary = document.querySelector(selectors.primary)?.getBoundingClientRect();
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      contentScrollTop: content?.scrollTop || 0,
      contentScrollHeight: content?.scrollHeight || 0,
      contentClientHeight: content?.clientHeight || 0,
      rootScrollTop: document.getElementById("email-agent-companion-root")?.scrollTop || 0,
      requiredVisible,
      allRequiredVisible: Object.values(requiredVisible).every(Boolean),
      primaryFocused: document.activeElement === document.querySelector(selectors.primary),
      primaryUsable: Boolean(primary && primary.width >= 40 && primary.height >= 40),
    };
  })()`);
}

async function containmentSnapshot() {
  return evaluate(`(() => {
    const root = document.getElementById("email-agent-companion-root");
    const rect = root?.getBoundingClientRect();
    const host = document.getElementById("synthetic-gmail-host")?.getBoundingClientRect();
    return {
      contained: Boolean(
        rect
        && rect.left >= 0
        && rect.top >= 0
        && rect.right <= window.innerWidth + 1
        && rect.bottom <= window.innerHeight + 1
        && document.documentElement.scrollWidth <= window.innerWidth
        && document.body.scrollWidth <= window.innerWidth
        && host?.left === 0,
      ),
      viewport: { width: window.innerWidth, height: window.innerHeight },
      root: rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width } : null,
      documentWidth: document.documentElement.scrollWidth,
    };
  })()`);
}

async function reloadPersistenceCheck(expectedStatus) {
  return evaluate(`({
    minimized: document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'true',
    onboardingVisible: Boolean(document.querySelector('[data-ea-onboarding]')),
    status: globalThis.__eaTestHooks.getOnboardingState().status,
    expected: ${JSON.stringify(expectedStatus)},
  })`);
}

async function clearOnboardingAndSetBase(scenario) {
  const state = baseState(scenario);
  const connectionState = scenario === "offline"
    ? {
      kind: "backend_unavailable",
      label: "Unavailable",
      details: "Start the local companion and check again.",
    }
    : { kind: "ready", label: "Ready", details: "Threadwise is connected." };
  await evaluate(`localStorage.removeItem(${JSON.stringify(onboardingStorageKey)})`);
  await evaluate(`localStorage.setItem(${JSON.stringify(baseStateStorageKey)}, ${JSON.stringify(JSON.stringify(state))})`);
  await evaluate(`localStorage.setItem(${JSON.stringify(connectionStateStorageKey)}, ${JSON.stringify(JSON.stringify(connectionState))})`);
}

function baseState(scenario) {
  const selected = scenario === "selected" ? selectedItem : {
    found: false,
    provider: "gmail",
    message_id: "",
    subject: "",
    sender: "",
    status: "idle",
    status_label: "Waiting for message selection",
    details: {},
  };
  const queue = ["queue", "selected"].includes(scenario) ? [queueItem] : [];
  const context = scenario === "selected"
    ? { provider: "gmail", message_id: selectedItem.message_id, subject: selectedItem.subject, sender: selectedItem.sender, page_url: appUrl }
    : { provider: "gmail", page_url: appUrl };
  return {
    selected_context: context,
    sidebar_state: {
      selected_context: context,
      selected_email: selected,
      daily_summary: { needs_attention_count: queue.length, processed_count: queue.length + 1, auto_handled_count: 0, kept_visible_count: 0, changed_today: {} },
      ui_state: { provider_name: "Gmail", allowed_labels: [], async_follow_up: {} },
    },
    needs_attention_items: queue,
    recent_items: queue,
    auto_handled_items: [],
    kept_visible_items: [],
    analytics_status: { state: "disabled" },
  };
}

async function captureScreenshot(outputPath) {
  const result = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  await fs.writeFile(outputPath, Buffer.from(result.data, "base64"));
}

async function pressKey(key) {
  const windowsVirtualKeyCode = key === "Enter" ? 13 : 0;
  const text = key === "Enter" ? "\r" : "";
  await send("Input.dispatchKeyEvent", {
    type: text ? "keyDown" : "rawKeyDown",
    key,
    code: key,
    windowsVirtualKeyCode,
    text,
    unmodifiedText: text,
  });
  await send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code: key,
    windowsVirtualKeyCode,
  });
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

async function waitFor(fn, timeoutMs = 12000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for browser state: ${await evaluate("document.body.innerText.slice(0, 1200)").catch(() => "unavailable")}`);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
