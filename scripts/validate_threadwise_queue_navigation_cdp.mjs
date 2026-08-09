import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionRoot = path.join(repoRoot, "extensions", "gmail_companion");
const screenshotCompact = "/tmp/threadwise-queue-navigation-compact.png";
const screenshotShort = "/tmp/threadwise-queue-navigation-short.png";
const screenshotNarrow = "/tmp/threadwise-queue-navigation-narrow.png";
const tracePath = "/tmp/threadwise-queue-navigation-forbidden-requests.json";
const appUrl = "http://127.0.0.1:8891/#inbox/FMqueueA";
const onboardingStorageKey = "threadwise_onboarding_state";
const baseStateStorageKey = "__tw_queue_navigation_base_state";
const requestLogStorageKey = "__tw_queue_navigation_request_log";
const onboardingVersion = "2026-08-09-v1";
const seededPageScrollY = 180;
const seededContentScrollTop = 72;
const scrollOffsetKeys = Object.freeze([
  "pageX",
  "pageY",
  "documentScrollLeft",
  "documentScrollTop",
  "bodyScrollLeft",
  "bodyScrollTop",
  "contentScrollLeft",
  "contentScrollTop",
]);

const queueItems = [
  {
    provider: "gmail",
    message_id: "gmail-a",
    subject: "Acme quarterly invoice",
    sender: "acme@example.test",
    classification: "EA/Finance",
    status_label: "Needs attention",
    status: "needs-attention",
  },
  {
    provider: "protonmail",
    message_id: "proton-a",
    subject: "Proton finance notice",
    sender: "proton@example.test",
    classification: "EA/Finance",
    status_label: "Needs attention",
    status: "needs-attention",
  },
  {
    provider: "gmail",
    message_id: "gmail-b",
    subject: "Project status report",
    sender: "project@example.test",
    classification: "EA/Work",
    status_label: "Needs attention",
    status: "needs-attention",
  },
  {
    message_id: "gmail-c",
    subject: "Finance planning note",
    sender: "planning@example.test",
    classification: "EA/Finance",
    status_label: "Needs attention",
    status: "needs-attention",
  },
  ...["gmail-d", "gmail-e", "gmail-f", "gmail-g"].map((message_id, index) => ({
    provider: "gmail",
    message_id,
    subject: `Other review item ${index + 1}`,
    sender: `other-${index + 1}@example.test`,
    classification: "EA/Work",
    status_label: "Needs attention",
    status: "needs-attention",
  })),
];

const selectedLive = {
  found: true,
  provider: "gmail",
  message_id: "selected-live",
  subject: "Selected live synthetic email",
  sender: "live@example.test",
  status: "needs-attention",
  status_label: "Needs attention",
  classification: "EA/Work",
  suggested_label: "work",
  internal_label: "work",
  details: {},
  understanding_state: "ready",
  understanding_label: "Ready",
};

const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;
let activeStep = "create-target";
const results = {
  screenshots: { compact: screenshotCompact, short: screenshotShort, narrow: screenshotNarrow },
  tracePath,
  viewportChecks: [],
  keyboardTrace: [],
  focusHandoff: [],
  scrollEvidence: [],
  queueExitTrace: [],
  requests: [],
  forbiddenRequests: [],
};
let failure = null;

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
  activeStep = "load-synthetic-companion";
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

  const initial = await evaluate(`(() => {
    const root = document.getElementById("email-agent-companion-root");
    return { minimized: root?.dataset.eaMinimized === "true", contentHidden: document.getElementById("ea-content")?.style.display === "none", onboarding: Boolean(document.querySelector("[data-ea-onboarding]")) };
  })()`);
  assert(initial.minimized, "fresh mount remains minimized");
  assert(initial.contentHidden, "fresh mount hides content");
  assert(!initial.onboarding, "dismissed synthetic onboarding stays out of the queue acceptance path");

  activeStep = "open-selected-email-view";
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'selected-live' && !globalThis.__eaTestHooks?.getSnapshot()?.manualPreviewContext"));
  assert(!(await evaluate("Boolean(document.querySelector('[data-ea-action=\\\"open-queue-finder\\\"]'))")), "selected-email first view has no queue finder");

  activeStep = "open-home";
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"));
  assert(await evaluate("Boolean(document.querySelector('[data-ea-action=\\\"open-queue-finder\\\"]'))"), "Home exposes the queue finder disclosure");
  await evaluate("document.querySelector('[data-ea-action=\\\"open-queue-finder\\\"]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('#ea-queue-query'))"));

  activeStep = "filter-finance";
  await setQuery("finance");
  const finance = await queueSnapshot();
  assert(finance.count === "2 of 7", "active Gmail queue count includes only provider-safe finance matches");
  assert(finance.resultIds.join(",") === "gmail-a,gmail-c", "provider filtering excludes Proton and preserves source order");
  assert(!finance.resultText.includes("Proton finance notice"), "Proton item never appears in Gmail queue results");

  await setQuery("project@example.test");
  assert((await queueSnapshot()).resultIds.join(",") === "gmail-b", "sender matching uses the loaded queue");
  await setQuery("quarterly invoice");
  assert((await queueSnapshot()).resultIds.join(",") === "gmail-a", "subject matching uses the loaded queue");
  await setQuery("ea/finance");
  assert((await queueSnapshot()).resultIds.join(",") === "gmail-a,gmail-c", "displayed classification matching uses the loaded queue");
  await setQuery("needs attention");
  assert((await queueSnapshot()).count === "7 of 7", "displayed status matching stays provider scoped");

  activeStep = "filter-miss-and-clear";
  await setQuery("not-loaded");
  const miss = await queueSnapshot();
  assert(miss.noResults, "filter miss has an explicit no-results state");
  assert(miss.text.includes("No loaded review emails match this filter."), "filter miss names loaded review emails");
  assert(!/Inbox zero|queue complete|stale|unavailable|unsynced/i.test(miss.text), "filter miss does not imply another queue state");

  await evaluate("document.querySelector('[data-ea-action=\\\"clear-queue-filter\\\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-queue-query]')?.value === ''"));
  const cleared = await queueSnapshot();
  assert(cleared.count === "7 of 7", "clearing restores the active provider queue order");
  assert(cleared.resultIds.slice(0, 3).join(",") === "gmail-a,gmail-b,gmail-c", "clearing restores source order without Proton");
  assert(cleared.capNotice, "render cap is disclosed");
  await evaluate("document.querySelector('[data-ea-action=\"toggle-queue-help\"]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-queue-help]'))"));
  await dispatchPanelKey("Escape", "[data-ea-queue-finder]");
  await waitFor(() => evaluate("!document.querySelector('[data-ea-queue-help]')"));
  assert((await queueSnapshot()).count === "7 of 7", "Escape closes help before changing the queue filter");

  activeStep = "filtered-pointer-and-jk-navigation";
  await setQuery("finance");
  const scrollSetupBefore = await scrollSnapshot();
  await seedShortViewportScroll();
  const scrollSetupAfter = await scrollSnapshot();
  results.scrollEvidence.push({
    step: "seed-short-viewport-scroll",
    before: scrollSetupBefore,
    after: scrollSetupAfter,
    expected: { pageY: seededPageScrollY, contentScrollTop: seededContentScrollTop },
  });
  assert(scrollSetupAfter.pageY === seededPageScrollY, "synthetic Gmail page has the known nonzero short-viewport scroll offset");
  assert(scrollSetupAfter.contentScrollTop === seededContentScrollTop, "Threadwise content has the known nonzero short-viewport scroll offset");
  assertNonzeroScroll(scrollSetupAfter, "seeded short-viewport scroll");

  const pointerEntryFocusBefore = await activeFocusSnapshot();
  const pointerEntryScrollBefore = await scrollSnapshot();
  assertNonzeroScroll(pointerEntryScrollBefore, "pointer queue entry before click");
  await evaluate("document.querySelector('[data-ea-queue-item=\\\"gmail-a\\\"]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-queue-navigation]')) && document.activeElement === document.querySelector('[data-ea-queue-navigation]')"));
  const pointerEntryScrollAfter = await scrollSnapshot();
  const pointerEntryFocusAfter = await activeFocusSnapshot();
  results.focusHandoff.push({
    step: "pointer-entry",
    focusBefore: pointerEntryFocusBefore,
    focusAfter: pointerEntryFocusAfter,
    before: pointerEntryScrollBefore,
    after: pointerEntryScrollAfter,
  });
  results.scrollEvidence.push({ step: "pointer-entry", before: pointerEntryScrollBefore, after: pointerEntryScrollAfter });
  assertScrollUnchanged(pointerEntryScrollBefore, pointerEntryScrollAfter, "pointer queue entry");
  assertNonzeroScroll(pointerEntryScrollAfter, "pointer queue entry after click");
  assert(await evaluate("document.activeElement === document.querySelector('[data-ea-queue-navigation]')"), "pointer result entry focuses the fresh queue-navigation surface");
  assert((await evaluate("document.querySelector('[data-ea-queue-position]')?.innerText")) === "1 of 2", "queue preview shows filtered position");
  assert((await evaluate("document.querySelector('#ea-workspace')?.innerText"))?.includes("Acme quarterly invoice"), "result click enters the existing manual preview context");

  const pointerNextScrollBefore = await scrollSnapshot();
  const pointerNextFocusBefore = await activeFocusSnapshot();
  assertNonzeroScroll(pointerNextScrollBefore, "pointer Next before rerender");
  await evaluate("document.querySelector('[data-ea-queue-nav=next]').click()");
  await waitFor(() => evaluate("document.querySelector('#ea-workspace')?.innerText.includes('Finance planning note') && document.activeElement === document.querySelector('[data-ea-queue-navigation]')"));
  const pointerNextScrollAfter = await scrollSnapshot();
  const pointerNextFocusAfter = await activeFocusSnapshot();
  results.focusHandoff.push({ step: "pointer-next", focusBefore: pointerNextFocusBefore, focusAfter: pointerNextFocusAfter, before: pointerNextScrollBefore, after: pointerNextScrollAfter });
  results.scrollEvidence.push({ step: "pointer-next-rerender", before: pointerNextScrollBefore, after: pointerNextScrollAfter });
  assertScrollUnchanged(pointerNextScrollBefore, pointerNextScrollAfter, "pointer Next rerender");
  assertNonzeroScroll(pointerNextScrollAfter, "pointer Next after rerender");
  assert(await evaluate("document.activeElement === document.querySelector('[data-ea-queue-navigation]')"), "pointer queue traversal refocuses the fresh queue-navigation surface");
  assert((await evaluate("document.querySelector('[data-ea-queue-position]')?.innerText")) === "2 of 2", "Next moves to the next filtered item");

  assert(await evaluate("document.activeElement === document.querySelector('[data-ea-queue-navigation]')"), "real CDP J starts on the fresh queue-navigation surface");
  const jScrollBefore = await scrollSnapshot();
  assertNonzeroScroll(jScrollBefore, "CDP J before rerender");
  await pressPanelKey("j");
  await waitFor(() => evaluate("document.querySelector('#ea-workspace')?.innerText.includes('Finance planning note') && document.activeElement === document.querySelector('[data-ea-queue-navigation]')"));
  const jScrollAfter = await scrollSnapshot();
  results.scrollEvidence.push({ step: "cdp-j-rerender", before: jScrollBefore, after: jScrollAfter });
  assertScrollUnchanged(jScrollBefore, jScrollAfter, "CDP J rerender");
  assertNonzeroScroll(jScrollAfter, "CDP J after rerender");
  assert(await evaluate("document.activeElement === document.querySelector('[data-ea-queue-navigation]')"), "J keeps focus on the queue-navigation surface at the filtered boundary");
  assert((await evaluate("document.querySelector('#ea-workspace')?.innerText"))?.includes("Finance planning note"), "J does not wrap at the end of the filtered queue");

  assert(await evaluate("document.activeElement === document.querySelector('[data-ea-queue-navigation]')"), "real CDP K starts on the fresh queue-navigation surface");
  const kScrollBefore = await scrollSnapshot();
  assertNonzeroScroll(kScrollBefore, "CDP K before rerender");
  await pressPanelKey("k");
  await waitFor(() => evaluate("document.querySelector('#ea-workspace')?.innerText.includes('Acme quarterly invoice') && document.activeElement === document.querySelector('[data-ea-queue-navigation]')"));
  const kScrollAfter = await scrollSnapshot();
  results.scrollEvidence.push({ step: "cdp-k-rerender", before: kScrollBefore, after: kScrollAfter });
  assertScrollUnchanged(kScrollBefore, kScrollAfter, "CDP K rerender");
  assertNonzeroScroll(kScrollAfter, "CDP K after rerender");
  assert(await evaluate("document.activeElement === document.querySelector('[data-ea-queue-navigation]')"), "K refocuses the new queue-navigation surface after rerender");

  const scrollResetBefore = await scrollSnapshot();
  await resetShortViewportScroll();
  const scrollResetAfter = await scrollSnapshot();
  results.scrollEvidence.push({ step: "restore-scroll-before-viewport-checks", before: scrollResetBefore, after: scrollResetAfter });
  assert(scrollResetAfter.pageY === 0, "synthetic Gmail page scroll is reset before viewport screenshots");
  assert(scrollResetAfter.contentScrollTop === 0, "Threadwise content scroll is reset before viewport screenshots");

  activeStep = "escape-retreat";
  await dispatchPanelKey("Escape", "[data-ea-queue-navigation]");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getQueueSnapshot().query === '' && globalThis.__eaTestHooks.getQueueSnapshot().previewActive"));
  assert(await evaluate("Boolean(document.querySelector('[data-ea-queue-navigation]'))"), "Escape clears the active query before leaving its queue preview");
  await dispatchPanelKey("Escape", "[data-ea-queue-navigation]");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"));
  assert(await evaluate("Boolean(document.querySelector('[data-ea-queue-finder]'))"), "Escape returns to Home with the finder preserved");

  await setQuery("project");
  await dispatchPanelKey("Escape", "[data-ea-queue-finder]");
  await waitFor(() => evaluate("document.querySelector('[data-ea-queue-query]')?.value === ''"));
  assert(await evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"), "Escape first clears a non-empty query");

  activeStep = "mapped-enter";
  await dispatchPanelKey("Enter", "[data-ea-queue-finder]");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-queue-navigation]'))"));
  assert((await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId")) === "gmail-a", "Enter activates exactly one visible primary Home action");

  activeStep = "editable-and-host-isolation";
  await dispatchPanelKey("Escape", "[data-ea-queue-navigation]");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"));
  await evaluate("document.querySelector('#ea-queue-query').focus()");
  const beforeEditable = await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().previewActive");
  await dispatchPanelKey("j", "#ea-queue-query");
  assert((await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().previewActive")) === beforeEditable, "Gmail/Threadwise editable typing does not navigate");
  await dispatchPanelKey("j", "document.body");
  assert((await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().previewActive")) === beforeEditable, "events outside the root do not navigate");

  activeStep = "viewport-containment";
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width > 0"));
  results.compact = await containmentSnapshot();
  assert(results.compact.contained, "compact desktop companion stays contained");
  await captureScreenshot(screenshotCompact);
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width > 0"));
  results.short = await containmentSnapshot();
  assert(results.short.contained, "short desktop companion stays contained");
  await captureScreenshot(screenshotShort);
  await send("Emulation.setDeviceMetricsOverride", { width: 360, height: 800, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width > 0"));
  results.narrow = await containmentSnapshot();
  assert(results.narrow.contained, "narrow companion stays contained without host displacement");
  await captureScreenshot(screenshotNarrow);
  results.viewportChecks.push(results.compact, results.short, results.narrow);
  activeStep = "explicit-queue-exit-and-selected-reopen";
  await setQuery("finance");
  await evaluate("document.querySelector('[data-ea-action=\"toggle-queue-help\"]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-queue-help]'))"));
  await evaluate("document.querySelector('[data-ea-queue-item=\"gmail-a\"]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-queue-navigation]'))"));
  const staleQueue = await evaluate("globalThis.__eaTestHooks.getQueueSnapshot()");
  assert(staleQueue.query === "finance", "exit trace starts with a nonempty queue filter");
  assert(staleQueue.finderOpen && staleQueue.helpOpen && staleQueue.previewActive, "exit trace starts with finder, help, and preview state active");
  results.queueExitTrace.push({ step: "stale-queue-before-explicit-exit", queue: staleQueue });

  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"));
  const afterExplicitExit = await evaluate("globalThis.__eaTestHooks.getQueueSnapshot()");
  assert(afterExplicitExit.query === "" && !afterExplicitExit.finderOpen && !afterExplicitExit.helpOpen && !afterExplicitExit.previewActive, "explicit Home exit resets every queue state field");
  assert(!afterExplicitExit.pendingFocus, "explicit Home exit clears the pending queue focus handoff through reset");
  results.queueExitTrace.push({ step: "explicit-home-exit", queue: afterExplicitExit, finderVisible: Boolean(await evaluate("document.querySelector('[data-ea-action=\\\"open-queue-finder\\\"]')")) });

  await dispatchPanelKey("Escape", "[data-ea-selected-state=home]");
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'true'"));
  results.queueExitTrace.push({ step: "minimized-after-explicit-exit", minimized: true });

  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'selected-live' && !globalThis.__eaTestHooks?.getSnapshot()?.manualPreviewContext"));
  const reopenedSelected = await evaluate("globalThis.__eaTestHooks.getQueueSnapshot()");
  assert(reopenedSelected.query === "" && !reopenedSelected.finderOpen && !reopenedSelected.helpOpen && !reopenedSelected.previewActive, "selected-email reopen starts with clean queue state");
  assert(!reopenedSelected.pendingFocus, "selected-email reopen has no pending queue focus handoff");
  assert(!(await evaluate("Boolean(document.querySelector('[data-ea-action=\\\"open-queue-finder\\\"]'))")), "selected-email reopen keeps the queue finder absent");
  results.queueExitTrace.push({ step: "selected-email-reopen", queue: reopenedSelected, finderVisible: false });

  activeStep = "clean-selected-context-escape";
  await dispatchPanelKey("Escape", "#ea-workspace");
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'true'"));
  const afterSelectedEscape = await evaluate("globalThis.__eaTestHooks.getQueueSnapshot()");
  assert(afterSelectedEscape.query === "" && !afterSelectedEscape.finderOpen && !afterSelectedEscape.helpOpen && !afterSelectedEscape.previewActive, "one Escape minimizes immediately without consuming stale queue state");
  assert(!(await evaluate("Boolean(document.querySelector('[data-ea-action=\\\"open-queue-finder\\\"]'))")), "one Escape leaves the selected-email context minimized without a queue finder");
  results.queueExitTrace.push({ step: "single-escape-minimized", queue: afterSelectedEscape, minimized: true });
  results.ok = true;
} catch (error) {
  failure = error;
  results.error = error.message;
  results.failedStep = activeStep;
  results.failureSnapshot = await evaluate(`(() => ({
    hook: globalThis.__eaTestHooks?.getSnapshot?.(),
    queue: globalThis.__eaTestHooks?.getQueueSnapshot?.(),
    navigationVisible: Boolean(document.querySelector('[data-ea-queue-navigation]')),
    homeVisible: Boolean(document.querySelector('[data-ea-selected-state=home]')),
    workspaceText: document.querySelector('#ea-workspace')?.innerText || ''
  }))()`).catch(() => null);
} finally {
  try {
    results.requests = await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || "[]")`);
  } catch (_error) {
    results.requests = [];
  }
  results.forbiddenRequests = results.requests.filter((request) => (
    request.type === "email-agent:api"
    || /provider-sync|gmail-check|teach-preview|teach-apply|safety-(preview|apply)|unsubscribe|handled|write|reply|send|sync/i.test(request.path || "")
  ));
  await fs.writeFile(tracePath, JSON.stringify({ requests: results.requests, forbiddenRequests: results.forbiddenRequests }, null, 2));
  socket.close();
}

console.log(JSON.stringify(results, null, 2));
if (failure || results.forbiddenRequests.length) {
  process.exitCode = 1;
}

async function installBridge() {
  const stateLiteral = JSON.stringify(baseState());
  await evaluate(`(() => {
    const requestLogKey = ${JSON.stringify(requestLogStorageKey)};
    localStorage.setItem(${JSON.stringify(onboardingStorageKey)}, JSON.stringify({ version: ${JSON.stringify(onboardingVersion)}, status: "dismissed" }));
    localStorage.setItem(${JSON.stringify(baseStateStorageKey)}, ${JSON.stringify(stateLiteral)});
    localStorage.setItem(requestLogKey, "[]");
    const appendRequest = (request) => {
      const requests = JSON.parse(localStorage.getItem(requestLogKey) || "[]");
      requests.push(request);
      localStorage.setItem(requestLogKey, JSON.stringify(requests));
    };
    const clone = (value) => JSON.parse(JSON.stringify(value));
    const stateForContext = (context) => {
      const base = clone(JSON.parse(localStorage.getItem(${JSON.stringify(baseStateStorageKey)})));
      const selectedQueueItem = (base.needs_attention_items || []).find((item) => item.message_id === context?.message_id && (!item.provider || item.provider === "gmail"));
      if (selectedQueueItem) {
        base.sidebar_state.selected_email = {
          ...selectedQueueItem,
          found: true,
          status: "needs-attention",
          status_label: "Needs attention",
          suggested_label: selectedQueueItem.classification === "EA/Finance" ? "finance" : "work",
          internal_label: selectedQueueItem.classification === "EA/Finance" ? "finance" : "work",
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
      async get(key) { const raw = localStorage.getItem(key); return { [key]: raw ? JSON.parse(raw) : undefined }; },
      async set(values) { Object.entries(values).forEach(([key, value]) => localStorage.setItem(key, JSON.stringify(value))); },
    };
    window.chrome = {
      runtime: {
        lastError: null,
        onMessage: { addListener: () => undefined, removeListener: () => undefined },
        getURL: () => ${JSON.stringify(await assetDataUri())},
        getManifest: () => ({ version: "0.3.2" }),
        sendMessage(message, callback) {
          appendRequest({ type: message?.type || "unknown", path: message?.path || "", method: message?.method || "" });
          if (message?.type === "email-agent:get-state") {
            callback?.({ ok: true, payload: stateForContext(message.context || {}), connection_state: { kind: "ready", label: "Ready", details: "Synthetic fixture state." } });
            return true;
          }
          if (message?.type === "threadwise:analytics") { callback?.({ ok: true }); return true; }
          callback?.({ ok: false, error: "Synthetic queue validator rejects " + (message?.path || message?.type || "unknown") + "." });
          return true;
        },
      },
      storage: { local: storage },
    };
    return true;
  })()`);
}

async function injectContentScript() {
  for (const scriptName of ["provider_adapter.js", "analytics.js", "onboarding.js", "queue_navigation.js", "content.js"]) {
    await evaluate(await fs.readFile(path.join(extensionRoot, scriptName), "utf8"));
  }
}

async function createSyntheticHost() {
  await evaluate(`(() => {
    document.body.innerHTML = ${JSON.stringify(`<main id="synthetic-gmail-host" style="min-height:100vh;margin:0;padding:32px 36px;background:#f4efe5;color:#241812;font-family:system-ui,sans-serif;"><div style="height:18px;width:240px;background:#e2d8c8;border-radius:4px;"></div><h2 data-thread-perm-id="thread-selected" style="margin-top:96px;font-size:28px;">Selected live synthetic email</h2><div data-legacy-message-id="selected-live" data-thread-perm-id="thread-selected" style="display:block;max-width:620px;padding:20px;background:#fffdf8;border:1px solid #ded3c1;"><span email="live@example.test" data-hovercard-id="live@example.test">Live Sender</span><p style="line-height:1.6;">Synthetic Gmail host content for queue navigation acceptance.</p></div></main>`)};
    document.documentElement.style.margin = "0"; document.body.style.margin = "0";
    document.getElementById("synthetic-gmail-host").style.minHeight = "1400px";
    return true;
  })()`);
}

function baseState() {
  const context = { provider: "gmail", message_id: selectedLive.message_id, subject: selectedLive.subject, sender: selectedLive.sender, page_url: appUrl };
  return {
    selected_context: context,
    sidebar_state: { selected_context: context, selected_email: selectedLive, daily_summary: { needs_attention_count: 7, processed_count: 9, auto_handled_count: 1, kept_visible_count: 1, changed_today: {} }, ui_state: { provider_name: "Gmail", allowed_labels: [{ id: "finance", name: "Finance" }, { id: "work", name: "Work" }], async_follow_up: {} } },
    needs_attention_items: queueItems,
    recent_items: queueItems,
    auto_handled_items: [],
    kept_visible_items: [],
    analytics_status: { state: "disabled" },
  };
}

async function queueSnapshot() {
  return evaluate(`(() => ({
    count: document.querySelector('[data-ea-queue-count]')?.innerText || "",
    resultIds: Array.from(document.querySelectorAll('[data-ea-queue-item]')).map((node) => node.getAttribute('data-ea-queue-item')),
    resultText: document.querySelector('[data-ea-queue-results]')?.innerText || "",
    noResults: Boolean(document.querySelector('[data-ea-queue-no-results]')),
    capNotice: Boolean(document.querySelector('[data-ea-queue-cap]')),
    text: document.querySelector('[data-ea-queue-finder]')?.innerText || "",
  }))()`);
}

async function setQuery(value) {
  await evaluate(`(() => { const input = document.querySelector('#ea-queue-query'); input.value = ${JSON.stringify(value)}; input.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  await waitFor(() => evaluate(`document.querySelector('#ea-queue-query')?.value === ${JSON.stringify(value)}`));
}

async function dispatchPanelKey(key, targetSelector) {
  const snapshot = await evaluate(`(() => {
    const target = ${targetSelector === "document.body" ? "document.body" : `document.querySelector(${JSON.stringify(targetSelector)})`};
    if (!target) return { ok: false };
    target.focus?.({ preventScroll: true });
    const event = new KeyboardEvent("keydown", { key: ${JSON.stringify(key)}, bubbles: true, cancelable: true });
    const dispatched = target.dispatchEvent(event);
    return { ok: true, defaultPrevented: event.defaultPrevented, dispatched, active: document.activeElement?.id || document.activeElement?.getAttribute?.("data-ea-queue-navigation") || "" };
  })()`);
  results.keyboardTrace.push({ key, target: targetSelector, ...snapshot, queue: await evaluate("globalThis.__eaTestHooks.getQueueSnapshot()") });
}

async function pressPanelKey(key) {
  const before = await activeFocusSnapshot();
  await pressKey(key);
  const after = await activeFocusSnapshot();
  results.keyboardTrace.push({ key, target: "activeElement", before, after, queue: await evaluate("globalThis.__eaTestHooks.getQueueSnapshot()") });
}

async function activeFocusSnapshot() {
  return evaluate(`(() => {
    const active = document.activeElement;
    const root = document.getElementById("email-agent-companion-root");
    const navigation = document.querySelector("[data-ea-queue-navigation]");
    return {
      tag: active?.tagName || "",
      id: active?.id || "",
      insideThreadwise: Boolean(active && root?.contains(active)),
      queueNavigation: active === navigation,
    };
  })()`);
}

async function scrollSnapshot() {
  return evaluate(`(() => ({
    pageX: window.scrollX,
    pageY: window.scrollY,
    documentScrollLeft: document.documentElement.scrollLeft,
    documentScrollTop: document.documentElement.scrollTop,
    bodyScrollLeft: document.body.scrollLeft,
    bodyScrollTop: document.body.scrollTop,
    pageScrollHeight: document.documentElement.scrollHeight,
    pageClientHeight: document.documentElement.clientHeight,
    contentScrollLeft: document.getElementById("ea-content")?.scrollLeft || 0,
    contentScrollTop: document.getElementById("ea-content")?.scrollTop || 0,
    contentScrollHeight: document.getElementById("ea-content")?.scrollHeight || 0,
    contentClientHeight: document.getElementById("ea-content")?.clientHeight || 0,
  }))()`);
}

async function seedShortViewportScroll() {
  await evaluate(`(() => {
    const content = document.getElementById("ea-content");
    if (!content) throw new Error("Threadwise content scroller is missing before scroll setup.");
    document.documentElement.style.scrollBehavior = "auto";
    document.body.style.scrollBehavior = "auto";
    window.scrollTo(0, 0);
    content.scrollTop = 0;
    window.scrollTo(0, ${seededPageScrollY});
    content.scrollTop = ${seededContentScrollTop};
    return true;
  })()`);
}

async function resetShortViewportScroll() {
  await evaluate(`(() => {
    const content = document.getElementById("ea-content");
    const host = document.getElementById("synthetic-gmail-host");
    if (host) host.style.minHeight = "100vh";
    return new Promise((resolve) => requestAnimationFrame(() => {
      window.scrollTo(0, 0);
      if (content) content.scrollTop = 0;
      resolve(true);
    }));
  })()`);
}

function assertNonzeroScroll(snapshot, step) {
  assert(snapshot.pageY > 0, `${step} keeps the synthetic Gmail page genuinely scrolled`);
  assert(snapshot.contentScrollTop > 0, `${step} keeps the Threadwise content genuinely scrolled`);
  assert(snapshot.pageScrollHeight > snapshot.pageClientHeight, `${step} has a scrollable synthetic Gmail page`);
  assert(snapshot.contentScrollHeight > snapshot.contentClientHeight, `${step} has a scrollable Threadwise content region`);
}

function assertScrollUnchanged(before, after, step) {
  for (const key of scrollOffsetKeys) {
    assert(after[key] === before[key], `${step} preserves ${key} exactly (${before[key]} -> ${after[key]})`);
  }
}

async function pressKey(key) {
  const code = /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : key;
  await send("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key,
    code,
    windowsVirtualKeyCode: /^[a-z]$/i.test(key) ? key.toUpperCase().charCodeAt(0) : 0,
  });
  await send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key,
    code,
    windowsVirtualKeyCode: /^[a-z]$/i.test(key) ? key.toUpperCase().charCodeAt(0) : 0,
  });
}

async function containmentSnapshot() {
  return evaluate(`(() => {
    const root = document.getElementById("email-agent-companion-root")?.getBoundingClientRect();
    const host = document.getElementById("synthetic-gmail-host")?.getBoundingClientRect();
    return { contained: Boolean(root && root.left >= 0 && root.top >= 0 && root.right <= innerWidth + 1 && root.bottom <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth && host?.left === 0), viewport: { width: innerWidth, height: innerHeight }, root: root ? { left: root.left, top: root.top, right: root.right, bottom: root.bottom, width: root.width } : null, documentWidth: document.documentElement.scrollWidth };
  })()`);
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
  throw new Error(`Timed out waiting for browser state: ${await evaluate("document.body.innerText.slice(0, 1200)").catch(() => "unavailable")}`);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
