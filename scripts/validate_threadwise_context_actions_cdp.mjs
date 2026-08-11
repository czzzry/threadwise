import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionRoot = path.join(repoRoot, "extensions", "gmail_companion");
const artifactRoot = "/tmp/threadwise-context-actions";
const tracePath = path.join(artifactRoot, "context-actions-trace.json");
const appUrl = "http://127.0.0.1:8891/#inbox/FMselected-live";
const onboardingStorageKey = "threadwise_onboarding_state";
const requestLogStorageKey = "__tw_context_actions_request_log";
const onboardingVersion = "2026-08-09-v1";
const seededPageScrollY = 180;
const seededContentScrollTop = 72;
const viewports = [
  { name: "1280x800", width: 1280, height: 800 },
  { name: "756x469", width: 756, height: 469 },
  { name: "360x800", width: 360, height: 800 },
];

const queueItems = [
  { provider: "gmail", message_id: "queue-a", subject: "Acme quarterly invoice", sender: "acme@example.test", classification: "EA/Finance", status_label: "Needs attention", status: "needs-attention" },
  { provider: "gmail", message_id: "queue-b", subject: "Project status report", sender: "project@example.test", classification: "EA/Work", status_label: "Needs attention", status: "needs-attention" },
];
const selectedReview = {
  found: true,
  provider: "gmail",
  message_id: "selected-live",
  subject: "Selected synthetic email",
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

  activeStep = "open-review-state";
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'selected-live' && document.querySelector('[data-ea-selected-state=review]')"));
  assert(await evaluate("Boolean(document.querySelector('[data-ea-context-trigger]'))"), "review has one contextual-actions trigger");
  assert(await evaluate("document.querySelectorAll('[data-ea-context-trigger]').length === 1"), "review has exactly one trigger");
  await assertVariantCVisualContract();
  await captureViewportSet("review");

  activeStep = "review-pointer-open-focus-and-scroll";
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 756 && Boolean(document.getElementById('email-agent-companion-root'))"));
  await seedScroll();
  const reviewOpenBefore = await scrollSnapshot();
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.hasAttribute('data-ea-context-item')"));
  const reviewOpenAfter = await scrollSnapshot();
  recordScroll("review-pointer-open", reviewOpenBefore, reviewOpenAfter);
  assertScrollUnchanged(reviewOpenBefore, reviewOpenAfter, "review pointer open");
  assertScrollRangeUnchanged(reviewOpenBefore, reviewOpenAfter, "review pointer open");
  assert((await evaluate("document.activeElement.getAttribute('data-ea-context-item')")) === "change-label", "pointer open focuses the first contextual correction action");
  await recordFocus("review-pointer-open");
  const reviewRoveBefore = await scrollSnapshot();
  await pressKey("ArrowDown");
  const reviewRoveAfter = await scrollSnapshot();
  recordScroll("review-roving", reviewRoveBefore, reviewRoveAfter);
  assertScrollUnchanged(reviewRoveBefore, reviewRoveAfter, "review roving");
  assertScrollRangeUnchanged(reviewRoveBefore, reviewRoveAfter, "review roving");
  assert((await evaluate("document.activeElement.getAttribute('data-ea-context-item')")) === "why", "review correction is keyboard-discoverable before roving to Why");
  const reviewCloseBefore = await scrollSnapshot();
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open"));
  const reviewCloseAfter = await scrollSnapshot();
  recordScroll("review-escape-close", reviewCloseBefore, reviewCloseAfter);
  assertScrollUnchanged(reviewCloseBefore, reviewCloseAfter, "review escape close");
  assertScrollRangeUnchanged(reviewCloseBefore, reviewCloseAfter, "review escape close");
  assert(await evaluate("document.activeElement?.hasAttribute('data-ea-context-trigger')"), "Escape restores review trigger focus");
  activeStep = "review-second-escape-retreats-from-trigger";
  const retreatRequestCount = await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type !== 'email-agent:probe-health').length`);
  const outsideEscape = await evaluate(`(() => {
    const host = document.getElementById('synthetic-gmail-host');
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    const dispatched = host.dispatchEvent(event);
    return { dispatched, defaultPrevented: event.defaultPrevented };
  })()`);
  assert(!outsideEscape.dispatched && outsideEscape.defaultPrevented, "one-shot retreat owns the immediate post-menu Escape even when Gmail receives the key event");
  await waitFor(() => evaluate(`(() => {
    const root = document.getElementById('email-agent-companion-root');
    const content = document.getElementById('ea-content');
    const minimize = document.getElementById('ea-minimize');
    return root?.dataset.eaMinimized === 'true'
      && root.getBoundingClientRect().width <= 71
      && getComputedStyle(content).display === 'none'
      && getComputedStyle(minimize).display === 'none';
  })()`));
  const collapsedLayout = await evaluate(`(() => {
    const root = document.getElementById('email-agent-companion-root');
    const content = document.getElementById('ea-content');
    const workspace = document.getElementById('ea-workspace');
    const minimize = document.getElementById('ea-minimize');
    return {
      minimized: root?.dataset.eaMinimized || '',
      rootWidth: root?.getBoundingClientRect().width || 0,
      contentDisplay: content ? getComputedStyle(content).display : '',
      workspaceWidth: workspace?.getBoundingClientRect().width || 0,
      minimizeDisplay: minimize ? getComputedStyle(minimize).display : '',
    };
  })()`);
  assert(collapsedLayout.minimized === 'true' && collapsedLayout.rootWidth <= 71 && collapsedLayout.contentDisplay === 'none' && collapsedLayout.workspaceWidth === 0 && collapsedLayout.minimizeDisplay === 'none', `outside-root Escape visibly collapses the overlay: ${JSON.stringify(collapsedLayout)}`);
  assert(
    (await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type !== 'email-agent:probe-health').length`)) === retreatRequestCount,
    "Escape retreat from the restored contextual trigger invokes no provider or product request",
  );
  results.steps.push({ step: "review-second-escape-retreats-from-trigger", requestCount: retreatRequestCount, collapsedLayout });
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false' && document.querySelector('[data-ea-selected-state=review]') && document.querySelector('[data-ea-context-trigger]')"));
  const ordinaryGmailEscape = await evaluate(`(() => {
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    const dispatched = document.getElementById('synthetic-gmail-host').dispatchEvent(event);
    return { dispatched, defaultPrevented: event.defaultPrevented };
  })()`);
  assert(ordinaryGmailEscape.dispatched && !ordinaryGmailEscape.defaultPrevented, "an unarmed Gmail Escape remains untouched");
  assert(await evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false'"), "unarmed Gmail Escape does not retreat Threadwise");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open"));
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open"));
  const shiftedThenEscape = await evaluate(`(() => {
    const host = document.getElementById('synthetic-gmail-host');
    const shifted = new KeyboardEvent('keydown', { key: 'Escape', shiftKey: true, bubbles: true, cancelable: true });
    const shiftedDispatched = host.dispatchEvent(shifted);
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    const escapeDispatched = host.dispatchEvent(escape);
    return { shiftedDispatched, shiftedPrevented: shifted.defaultPrevented, escapeDispatched, escapePrevented: escape.defaultPrevented };
  })()`);
  assert(shiftedThenEscape.shiftedDispatched && !shiftedThenEscape.shiftedPrevented, "Shift+Escape is untouched and disarms one-shot retreat");
  assert(shiftedThenEscape.escapeDispatched && !shiftedThenEscape.escapePrevented, "ordinary Gmail Escape remains untouched after Shift+Escape disarms retreat");
  assert(await evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false'"), "Shift+Escape and the following disarmed Escape leave Threadwise open");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open"));
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open"));
  const unrelatedThenEscape = await evaluate(`(() => {
    const host = document.getElementById('synthetic-gmail-host');
    const unrelated = new KeyboardEvent('keydown', { key: 'x', bubbles: true, cancelable: true });
    const unrelatedDispatched = host.dispatchEvent(unrelated);
    const escape = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    const escapeDispatched = host.dispatchEvent(escape);
    return { unrelatedDispatched, unrelatedPrevented: unrelated.defaultPrevented, escapeDispatched, escapePrevented: escape.defaultPrevented };
  })()`);
  assert(unrelatedThenEscape.unrelatedDispatched && !unrelatedThenEscape.unrelatedPrevented, "unrelated Gmail input is untouched and disarms one-shot retreat");
  assert(unrelatedThenEscape.escapeDispatched && !unrelatedThenEscape.escapePrevented, "Gmail Escape remains untouched after unrelated input disarms retreat");
  assert(await evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false'"), "disarmed Gmail Escape leaves Threadwise open");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open"));
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open"));
  const editableEscape = await evaluate(`(() => {
    const input = document.createElement('input');
    document.getElementById('synthetic-gmail-host').appendChild(input);
    const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
    const dispatched = input.dispatchEvent(event);
    input.remove();
    return { dispatched, defaultPrevented: event.defaultPrevented };
  })()`);
  assert(editableEscape.dispatched && !editableEscape.defaultPrevented, "editable Gmail Escape remains untouched and disarms one-shot retreat");
  assert(await evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false'"), "editable Gmail Escape leaves Threadwise open");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.hasAttribute('data-ea-context-item')"));
  await captureViewportSet("review-open");

  activeStep = "root-only-shortcut-and-menu-priority";
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open"));
  await evaluate("document.querySelector('[data-ea-context-trigger]').focus(); document.querySelector('[data-ea-context-trigger]').dispatchEvent(new KeyboardEvent('keydown', { key: '.', bubbles: true, cancelable: true }))");
  assert(!(await evaluate("globalThis.__eaTestHooks.getContextActions().open")), "dot on the native trigger keeps native behavior");
  await evaluate("document.getElementById('email-agent-companion-root').focus(); document.getElementById('email-agent-companion-root').dispatchEvent(new KeyboardEvent('keydown', { key: '.', bubbles: true, cancelable: true }))");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open"));
  await recordFocus("review-keyboard-open");
  await pressKey("j");
  assert((await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId")) === "", "J inside the open menu cannot move the queue");
  assert(await evaluate("globalThis.__eaTestHooks.getContextActions().open"), "J is consumed while the menu is open");
  const menuBefore = await evaluate("globalThis.__eaTestHooks.getContextActions().activeIndex");
  await pressKey("ArrowDown");
  assert((await evaluate("globalThis.__eaTestHooks.getContextActions().activeIndex")) === menuBefore + 1, "Arrow Down roves from Change label to Why");
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.hasAttribute('data-ea-context-trigger')"));
  await recordFocus("review-escape-close");
  await assertNativeShortcutBoundaries();

  activeStep = "queue-preview-contextual-back-and-priority";
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 756 && Boolean(document.getElementById('email-agent-companion-root'))"));
  await evaluate("globalThis.__eaTestHooks.openQueueItem('queue-a')");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId === 'queue-a' && document.querySelector('[data-ea-selected-state=review]')"));
  assert(await evaluate("Boolean(document.querySelector('[data-ea-context-trigger]'))"), "queue preview has a contextual-actions trigger");
  await seedScroll();
  const queueOpenBefore = await scrollSnapshot();
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'change-label,why,open-email,back-to-queue'"));
  const queueOpenAfter = await scrollSnapshot();
  assertScrollUnchanged(queueOpenBefore, queueOpenAfter, "queue pointer open");
  assertScrollRangeUnchanged(queueOpenBefore, queueOpenAfter, "queue pointer open");
  results.steps.push({ step: "queue-preview-policy", policy: await evaluate("globalThis.__eaTestHooks.getContextActionPolicy?.()"), actions: await evaluate("globalThis.__eaTestHooks.getContextActions()") });
  const queueBefore = await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId");
  await pressKey("j");
  assert((await evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId")) === queueBefore, "panel priority prevents J from changing queue item");
  assertScrollUnchanged(queueOpenBefore, await scrollSnapshot(), "queue J consumption");
  assertScrollRangeUnchanged(queueOpenBefore, await scrollSnapshot(), "queue J consumption");
  await captureViewportSet("queue-preview");
  const queueCloseBefore = await scrollSnapshot();
  await pressKey("Escape");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.hasAttribute('data-ea-context-trigger')"));
  assertScrollUnchanged(queueCloseBefore, await scrollSnapshot(), "queue Escape close");
  assertScrollRangeUnchanged(queueCloseBefore, await scrollSnapshot(), "queue Escape close");
  await evaluate("document.querySelector('[data-ea-queue-navigation]').focus()");
  assert(await evaluate("document.activeElement?.matches('[data-ea-queue-navigation]')"), "queue navigation surface receives focus after close");
  await pressKey("j");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId === 'queue-b'"));
  assert(await evaluate("document.activeElement?.matches('[data-ea-queue-navigation]')"), "J restores queue navigation focus");
  await pressKey("k");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId === 'queue-a'"));
  assert(await evaluate("document.activeElement?.matches('[data-ea-queue-navigation]')"), "K restores queue navigation focus");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'change-label,why,open-email,back-to-queue'"));
  await evaluate("document.querySelector('[data-ea-context-item=back-to-queue]').click()");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getQueueSnapshot().currentMessageId === ''"));
  await captureViewportSet("queue-preview-exit");

  activeStep = "handled-receipt-single-fire-and-why";
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 300, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 756 && innerHeight === 300 && Boolean(document.getElementById('email-agent-companion-root'))"));
  await setHostMessage("handled-1", "Handled synthetic email", "handled@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')"));
  await seedScroll();
  const whyOpenBefore = await scrollSnapshot();
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'open-email,why'"));
  const whyOpenAfter = await scrollSnapshot();
  assertScrollUnchanged(whyOpenBefore, whyOpenAfter, "Why pointer open");
  assertScrollRangeUnchanged(whyOpenBefore, whyOpenAfter, "Why pointer open");
  await pressKey("ArrowDown");
  assert((await evaluate("document.activeElement.getAttribute('data-ea-context-item')")) === "why", "roving reaches Why from the active menu item");
  assertScrollUnchanged(whyOpenBefore, await scrollSnapshot(), "Why roving");
  const whyExecutionBefore = await scrollSnapshot();
  await evaluate("document.querySelector('[data-ea-context-item=why]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().detailsExpanded === true && !globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.hasAttribute('data-ea-context-trigger')"));
  const whyExecutionAfter = await scrollSnapshot();
  recordScroll("why-execution", whyExecutionBefore, whyExecutionAfter);
  assertScrollUnchanged(whyExecutionBefore, whyExecutionAfter, "Why execution");
  assert(await evaluate("document.activeElement?.hasAttribute('data-ea-context-trigger')"), "Why rerender restores focus to the current Actions trigger");
  assert((await evaluate("document.querySelectorAll('#ea-handled-why').length")) === 1, "Why executes once and shows one explanation");
  await recordFocus("why-execution");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.getAttribute('data-ea-context-item') === 'open-email'"));
  await pressKey("ArrowDown");
  assert((await evaluate("document.activeElement.getAttribute('data-ea-context-item')")) === "why", "Space activation starts from the active Why item");
  const whySpaceBefore = await scrollSnapshot();
  await pressKey(" ");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().detailsExpanded === false && !globalThis.__eaTestHooks.getContextActions().open && document.activeElement?.hasAttribute('data-ea-context-trigger')"));
  const whySpaceAfter = await scrollSnapshot();
  recordScroll("why-space-activation", whySpaceBefore, whySpaceAfter);
  assertScrollUnchanged(whySpaceBefore, whySpaceAfter, "Space Why activation");
  await captureViewportSet("handled-receipt");

  activeStep = "actionless-blocked";
  await setHostMessage("blocked-1", "Blocked synthetic email", "blocked@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=blocked]')"));
  assert(!(await evaluate("Boolean(document.querySelector('[data-ea-context-trigger]'))")), "blocked state has no invented contextual action");
  await captureViewportSet("blocked");

  activeStep = "teaching-preview-and-scope-invalidation";
  await setHostMessage("selected-live", "Selected synthetic email", "live@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]')"));
  await evaluate("globalThis.__eaTestHooks.showTeachPreview({ target_label: 'work', selected_label_after: ['work'], impact: { matching_existing_count: 1, similar_candidate_count: 0 }, future_rule_allowed: true, human_explanation: 'Synthetic teaching preview' })");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=teach-preview]')"));
  const staleGeneration = await evaluate("globalThis.__eaTestHooks.getContextActions().generation");
  assert(await evaluate("Boolean(document.querySelector('[data-ea-context-trigger]'))"), "teaching preview has a contextual-actions trigger");
  await captureViewportSet("teach-preview");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'open-email,edit-change'"));
  await evaluate("window.__twStaleContextItem = document.querySelector('[data-ea-context-item=edit-change]')");
  await setHostMessage("handled-1", "Handled synthetic email", "handled@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]') && !globalThis.__eaTestHooks.getContextActions().open"));
  const staleRequestCount = await evaluate("JSON.parse(localStorage.getItem('__tw_context_actions_request_log') || '[]').filter((request) => request.type !== 'email-agent:probe-health').length");
  assert((await evaluate("globalThis.__eaTestHooks.getContextActions().generation")) > staleGeneration, "state rerender invalidates the open action set");
  const staleAttempt = await evaluate(`(() => {
    const stale = window.__twStaleContextItem;
    const root = document.getElementById('email-agent-companion-root');
    if (!stale || !root) return { attempted: false };
    const generation = stale.getAttribute('data-ea-context-generation');
    root.appendChild(stale);
    stale.click();
    stale.remove();
    return {
      attempted: true,
      staleGeneration: Number(generation),
      currentGeneration: globalThis.__eaTestHooks.getContextActions().generation,
      state: document.querySelector('[data-ea-selected-state]')?.getAttribute('data-ea-selected-state') || '',
      selectedDecisionMode: globalThis.__eaTestHooks.getApplyState?.().selectedDecisionMode || '',
    };
  })()`);
  assert(staleAttempt.attempted, "stale menu item was retained for rejection");
  assert(staleAttempt.staleGeneration < staleAttempt.currentGeneration, "stale item generation is older than current context");
  assert(staleAttempt.state === "handled-receipt", "stale item cannot change the current selected state");
  assert(staleAttempt.selectedDecisionMode === "review", "stale item cannot revive its old action");
  assert((await evaluate("JSON.parse(localStorage.getItem('__tw_context_actions_request_log') || '[]').filter((request) => request.type !== 'email-agent:probe-health').length")) === staleRequestCount, "stale item causes no request");
  results.steps.push({ step: "stale-action-rejection", staleAttempt, requestCount: staleRequestCount });
  await setHostMessage("selected-live", "Selected synthetic email", "live@example.test");
  await evaluate("globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]')"));
  await evaluate("globalThis.__eaTestHooks.showTeachScope({ target_label: 'work', selected_label_after: ['work'], impact: { matching_existing_count: 1, similar_candidate_count: 0 }, future_rule_allowed: true, human_explanation: 'Synthetic teaching scope' })");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=teach-scope]') && !globalThis.__eaTestHooks.getContextActions().open"));
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'open-email,keep-discussing'"));
  await captureViewportSet("teach-scope");

  activeStep = "keyboard-only-context-action-scroll-and-focus";
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 300, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 756 && innerHeight === 300 && Boolean(document.getElementById('email-agent-companion-root'))"));
  await seedScroll();
  const keyboardActionBefore = await scrollSnapshot();
  await pressKey("ArrowDown");
  assert((await evaluate("document.activeElement.getAttribute('data-ea-context-item')")) === "keep-discussing", "roving focuses the keyboard-only state-changing action");
  await pressKey("Enter");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=change]') && !globalThis.__eaTestHooks.getContextActions().open"));
  const keyboardActionAfter = await scrollSnapshot();
  recordScroll("keyboard-only-state-change", keyboardActionBefore, keyboardActionAfter);
  assertScrollUnchanged(keyboardActionBefore, keyboardActionAfter, "keyboard-only state-changing menu action");
  assert(await evaluate("document.activeElement?.matches('[data-ea-action=preview-current-change]') || document.activeElement?.hasAttribute('data-ea-context-trigger') || document.activeElement?.matches('#ea-workspace')"), "keyboard-only action restores a safe current focus target");
  await recordFocus("keyboard-only-state-change");
  results.steps.push({
    step: "keyboard-only-state-changing-action",
    activationKey: "Enter",
    activeBefore: "keep-discussing",
    activeAfter: await evaluate("document.activeElement?.outerHTML?.slice(0, 220) || ''"),
  });

  activeStep = "receipt-policy-and-single-fire";
  await evaluate("globalThis.__eaTestHooks.showReceipt({ success: true, complete: true })");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=receipt]')"));
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'teach-future,back-home'"));
  await captureViewportSet("receipt");
  await evaluate("document.querySelector('[data-ea-context-item=teach-future]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=future-learning]') && !globalThis.__eaTestHooks.getContextActions().open"));
  assert((await evaluate("document.querySelectorAll('[data-ea-selected-state=future-learning]').length")) === 1, "receipt contextual action fires exactly once");
  await captureViewportSet("receipt-transition");

  activeStep = "viewport-and-scroll-final-check";
  await evaluate("globalThis.__eaTestHooks.showReceipt({ success: true, complete: false })");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=receipt]')"));
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 756 && Boolean(document.getElementById('email-agent-companion-root'))"));
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open"));
  const receiptScrollBefore = await scrollSnapshot();
  await pressKey("ArrowDown");
  await pressKey("Home");
  const receiptScrollAfterRove = await scrollSnapshot();
  recordScroll("receipt-roving", receiptScrollBefore, receiptScrollAfterRove);
  assertScrollUnchanged(receiptScrollBefore, receiptScrollAfterRove, "receipt roving");
  assertScrollRangeUnchanged(receiptScrollBefore, receiptScrollAfterRove, "receipt roving");
  await pressKey("Escape");
  const receiptScrollAfterClose = await scrollSnapshot();
  recordScroll("receipt-close", receiptScrollBefore, receiptScrollAfterClose);
  assert(receiptScrollBefore.pageX === receiptScrollAfterClose.pageX && receiptScrollBefore.pageY === receiptScrollAfterClose.pageY, "receipt close preserves Gmail-page scroll");
  assertScrollRangeUnchanged(receiptScrollBefore, receiptScrollAfterClose, "receipt close");
  assert((await evaluate("document.activeElement?.hasAttribute('data-ea-context-trigger')")), "Escape restores trigger focus");
  await recordFocus("receipt-escape-close");

  activeStep = "reset-to-clean-review-before-recovery";
  await evaluate("window.__twSetConnectionScenario({ kind: 'ready' })");
  await injectContentScript();
  await waitFor(() => evaluate("document.querySelectorAll('#email-agent-companion-root').length === 1 && globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'selected-live'"));
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false'"));
  await send("Emulation.setDeviceMetricsOverride", {
    width: 1280,
    height: 800,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await waitFor(() => evaluate("window.innerWidth === 1280 && window.innerHeight === 800"));
  await evaluate("new Promise((resolve) => setTimeout(resolve, 300))");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getSnapshot().refreshInFlight && !globalThis.__eaTestHooks.getSnapshot().connectionPollInFlight"));

  activeStep = "health-poll-single-flight";
  const singleFlightBefore = await evaluate(`(() => {
    const requests = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]');
    window.__twSetConnectionScenario({ kind: 'ready', delayMs: 300 });
    globalThis.__eaTestHooks.pollConnectionHealth();
    globalThis.__eaTestHooks.forceRefresh();
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    return {
      probes: requests.filter((request) => request.type === 'email-agent:probe-health').length,
      stateReads: requests.filter((request) => request.type === 'email-agent:get-state').length,
      pollInFlight: snapshot.connectionPollInFlight,
      refreshQueued: snapshot.pendingRefreshAfterConnectionPoll,
      refreshInFlight: snapshot.refreshInFlight,
    };
  })()`);
  assert(singleFlightBefore.pollInFlight && singleFlightBefore.refreshQueued && !singleFlightBefore.refreshInFlight, `full refresh waits behind an in-flight health probe: ${JSON.stringify(singleFlightBefore)}`);
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getSnapshot().connectionPollInFlight && !globalThis.__eaTestHooks.getSnapshot().pendingRefreshAfterConnectionPoll && !globalThis.__eaTestHooks.getSnapshot().refreshInFlight"));
  const singleFlightAfter = await evaluate(`(() => {
    const requests = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]');
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    return {
      probes: requests.filter((request) => request.type === 'email-agent:probe-health').length,
      stateReads: requests.filter((request) => request.type === 'email-agent:get-state').length,
      connectionKind: snapshot.connectionKind,
      selectedMessageId: snapshot.selectedEmail?.message_id || '',
    };
  })()`);
  assert(singleFlightAfter.probes - singleFlightBefore.probes === 1 && singleFlightAfter.stateReads - singleFlightBefore.stateReads === 1, `queued refresh runs exactly once after the probe: ${JSON.stringify({ singleFlightBefore, singleFlightAfter })}`);
  assert(singleFlightAfter.connectionKind === "ready" && singleFlightAfter.selectedMessageId === "selected-live", `single-flight refresh preserves the selected review: ${JSON.stringify(singleFlightAfter)}`);
  await evaluate("window.__twSetConnectionScenario({ kind: 'ready' })");
  results.steps.push({ step: "health-poll-single-flight", before: singleFlightBefore, after: singleFlightAfter });
  await injectContentScript();
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getSnapshot()?.connectionKind === 'ready' && globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'selected-live'"));
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false'"));
  await evaluate("new Promise((resolve) => setTimeout(resolve, 300))");
  await waitFor(() => evaluate("!globalThis.__eaTestHooks.getSnapshot().refreshInFlight && !globalThis.__eaTestHooks.getSnapshot().connectionPollInFlight"));

  activeStep = "automatic-ready-outage-detection";
  const automaticOutageBefore = await evaluate(`(() => {
    const requests = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]');
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    return {
      probes: requests.filter((request) => request.type === 'email-agent:probe-health').length,
      stateReads: requests.filter((request) => request.type === 'email-agent:get-state').length,
      messageId: snapshot.selectedEmail?.message_id || '',
      pageUrl: snapshot.lastLiveContext?.page_url || '',
    };
  })()`);
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', error: 'Automatic health probe could not connect.', details: 'The unchanged selected context lost its Threadwise health response.' })");
  const outageStartedAt = Date.now();
  await waitFor(() => evaluate("document.querySelector('[data-ea-recovery-kind=helper-unreachable]') && !globalThis.__eaTestHooks.getSnapshot().connectionPollInFlight"), 6500);
  const automaticOutage = await evaluate(`(() => {
    const requests = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]');
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    const details = document.querySelector('[data-ea-recovery-details]');
    return {
      probes: requests.filter((request) => request.type === 'email-agent:probe-health').length,
      stateReads: requests.filter((request) => request.type === 'email-agent:get-state').length,
      messageId: snapshot.selectedEmail?.message_id || '',
      pageUrl: snapshot.lastLiveContext?.page_url || '',
      connectionKind: snapshot.connectionKind,
      pollInFlight: snapshot.connectionPollInFlight,
      visibleText: document.querySelector('[data-ea-recovery-surface]')?.innerText || '',
      detailsOpen: Boolean(details?.open),
      diagnostics: details?.textContent || '',
    };
  })()`);
  const outageElapsedMs = Date.now() - outageStartedAt;
  assert(automaticOutage.probes - automaticOutageBefore.probes === 1, `unchanged ready context sends exactly one bounded health probe: ${JSON.stringify({ automaticOutageBefore, automaticOutage })}`);
  assert(automaticOutage.stateReads === automaticOutageBefore.stateReads, `ready health polling does not re-render through a full state read: ${JSON.stringify({ automaticOutageBefore, automaticOutage })}`);
  assert(outageElapsedMs <= 6500 && automaticOutage.connectionKind === "helper-unreachable" && !automaticOutage.pollInFlight, `helper outage becomes truthful within one bounded interval: ${JSON.stringify({ outageElapsedMs, automaticOutage })}`);
  assert(automaticOutage.messageId === automaticOutageBefore.messageId && automaticOutage.pageUrl === automaticOutageBefore.pageUrl, `outage detection preserves the unchanged selected context: ${JSON.stringify({ automaticOutageBefore, automaticOutage })}`);
  assert(!automaticOutage.detailsOpen && automaticOutage.diagnostics.includes("lost its Threadwise health response"), `automatic outage retains the exact cause behind closed details: ${JSON.stringify(automaticOutage)}`);
  await captureScreenshot(path.join(artifactRoot, "recovery-automatic-outage-1280x800.png"));
  results.screenshots.push({ state: "recovery-automatic-outage", viewport: "1280x800", path: path.join(artifactRoot, "recovery-automatic-outage-1280x800.png"), containment: await containmentSnapshot() });

  activeStep = "automatic-helper-restoration";
  await evaluate("window.__twSetConnectionScenario({ kind: 'ready' })");
  const restorationStartedAt = Date.now();
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && globalThis.__eaTestHooks.getSnapshot().connectionKind === 'ready' && !globalThis.__eaTestHooks.getSnapshot().connectionPollInFlight"), 6500);
  const automaticRestoration = await evaluate(`(() => {
    const requests = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]');
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    return {
      probes: requests.filter((request) => request.type === 'email-agent:probe-health').length,
      stateReads: requests.filter((request) => request.type === 'email-agent:get-state').length,
      messageId: snapshot.selectedEmail?.message_id || '',
      pageUrl: snapshot.lastLiveContext?.page_url || '',
      feedback: snapshot.connectionRetryFeedback,
    };
  })()`);
  const restorationElapsedMs = Date.now() - restorationStartedAt;
  assert(automaticRestoration.stateReads - automaticOutage.stateReads === 1, `offline recovery performs exactly one bounded full state read: ${JSON.stringify({ automaticOutage, automaticRestoration })}`);
  assert(restorationElapsedMs <= 6500 && automaticRestoration.feedback === "", `restored helper automatically clears recovery state within one interval: ${JSON.stringify({ restorationElapsedMs, automaticRestoration })}`);
  assert(automaticRestoration.messageId === automaticOutageBefore.messageId && automaticRestoration.pageUrl === automaticOutageBefore.pageUrl, `automatic recovery returns to the unchanged selected review: ${JSON.stringify({ automaticOutageBefore, automaticRestoration })}`);
  results.steps.push({ step: "automatic-ready-outage-and-recovery", outageElapsedMs, restorationElapsedMs, before: automaticOutageBefore, outage: automaticOutage, restored: automaticRestoration });

  activeStep = "variant-c-recovery-unreachable";
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', error: 'Failed to fetch synthetic Threadwise state.', details: 'No Threadwise service answered on the configured loopback endpoint.' }); globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-recovery-kind=helper-unreachable]')?.getAttribute('data-ea-retry-state') === 'idle'"));
  await assertRecoveryVisualContract("helper-unreachable");
  await captureViewportSet("recovery-unreachable");

  activeStep = "variant-c-recovery-immediate-failure-feedback";
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false });
  await waitFor(() => evaluate("innerWidth === 1280 && innerHeight === 800"));
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', error: 'Immediate connection refused.', details: 'The configured loopback endpoint refused the connection.' })");
  const immediateFailure = await evaluate(`(() => {
    const getStateCountBefore = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type === 'email-agent:get-state').length;
    document.querySelector('[data-ea-recovery-action]').click();
    const surface = document.querySelector('[data-ea-recovery-surface]');
    const button = surface?.querySelector('[data-ea-recovery-action]');
    const details = surface?.querySelector('[data-ea-recovery-details]');
    const getStateCountAfter = JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type === 'email-agent:get-state').length;
    return {
      getStateDelta: getStateCountAfter - getStateCountBefore,
      inFlight: globalThis.__eaTestHooks.getSnapshot().connectionRetryInFlight,
      feedback: globalThis.__eaTestHooks.getSnapshot().connectionRetryFeedback,
      retryState: surface?.getAttribute('data-ea-retry-state') || '',
      status: surface?.querySelector('[data-ea-recovery-status]')?.textContent.trim() || '',
      buttonText: button?.textContent.trim() || '',
      buttonDisabled: Boolean(button?.disabled),
      detailsOpen: Boolean(details?.open),
      diagnostics: details?.textContent || '',
    };
  })()`);
  assert(immediateFailure.getStateDelta === 1 && !immediateFailure.inFlight && immediateFailure.feedback === "failed", `immediate refusal completes one truthful retry: ${JSON.stringify(immediateFailure)}`);
  assert(immediateFailure.retryState === "checked" && immediateFailure.status === "Still offline \u00b7 checked just now", `immediate refusal leaves persistent visible checked feedback: ${JSON.stringify(immediateFailure)}`);
  assert(!immediateFailure.buttonDisabled && immediateFailure.buttonText === "Check again", `immediate refusal remains retryable without a false checking state: ${JSON.stringify(immediateFailure)}`);
  assert(!immediateFailure.detailsOpen && immediateFailure.diagnostics.includes("connection refused"), `immediate refusal retains the exact cause in collapsed details: ${JSON.stringify(immediateFailure)}`);
  const immediateFailureVisual = await assertRecoveryVisualContract("helper-unreachable");
  assert(immediateFailureVisual.visibleText.includes("Still offline") && !immediateFailureVisual.visibleText.includes("Ready"), `immediate refusal is visibly different and never claims recovery: ${immediateFailureVisual.visibleText}`);
  await captureScreenshot(path.join(artifactRoot, "recovery-checked-1280x800.png"));
  results.screenshots.push({ state: "recovery-checked", viewport: "1280x800", path: path.join(artifactRoot, "recovery-checked-1280x800.png"), containment: await containmentSnapshot() });
  results.steps.push({ step: "recovery-immediate-failure-feedback", evidence: immediateFailure });

  activeStep = "variant-c-recovery-delayed-failure-feedback";
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', delayMs: 300, error: 'Failed to fetch synthetic Threadwise state.', details: 'No Threadwise service answered on the configured loopback endpoint.' })");
  const failedRetryChecking = await evaluate(`(() => {
    document.querySelector('[data-ea-recovery-action]').click();
    const surface = document.querySelector('[data-ea-recovery-surface]');
    const button = surface?.querySelector('[data-ea-recovery-action]');
    return {
      inFlight: globalThis.__eaTestHooks.getSnapshot().connectionRetryInFlight,
      retryState: surface?.getAttribute('data-ea-retry-state') || '',
      busy: surface?.getAttribute('aria-busy') || '',
      buttonText: button?.textContent.trim() || '',
      buttonDisabled: Boolean(button?.disabled),
      status: surface?.querySelector('[data-ea-recovery-status]')?.textContent.trim() || '',
    };
  })()`);
  assert(failedRetryChecking.inFlight && failedRetryChecking.retryState === "checking" && failedRetryChecking.busy === "true", `retry immediately exposes an honest checking state: ${JSON.stringify(failedRetryChecking)}`);
  assert(failedRetryChecking.buttonDisabled && failedRetryChecking.buttonText === "Checking\u2026", `retry immediately disables the Checking action: ${JSON.stringify(failedRetryChecking)}`);
  assert(failedRetryChecking.status.includes("Trying the connection now"), `retry immediately announces progress: ${JSON.stringify(failedRetryChecking)}`);
  await captureScreenshot(path.join(artifactRoot, "recovery-checking-1280x800.png"));
  results.screenshots.push({ state: "recovery-checking", viewport: "1280x800", path: path.join(artifactRoot, "recovery-checking-1280x800.png"), containment: await containmentSnapshot() });
  await waitFor(() => evaluate("document.querySelector('[data-ea-recovery-kind=helper-unreachable]')?.getAttribute('data-ea-retry-state') === 'checked' && !globalThis.__eaTestHooks.getSnapshot().connectionRetryInFlight"));
  const failedRetryTruth = await assertRecoveryVisualContract("helper-unreachable");
  assert(!failedRetryTruth.visibleText.includes("Ready"), `failed retry returns to the truthful error without a recovery claim: ${failedRetryTruth.visibleText}`);
  results.steps.push({ step: "recovery-failed-retry-feedback", checking: failedRetryChecking, returnedKind: failedRetryTruth.kind });

  activeStep = "automatic-offline-read-manual-retry-coalescing";
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', delayMs: 400, error: 'Coalesced connection check stayed offline.', details: 'The single coalesced state read could not reach Threadwise.' })");
  const coalescedRetryChecking = await evaluate(`(() => {
    const countReads = () => JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type === 'email-agent:get-state').length;
    const readsBefore = countReads();
    globalThis.__eaTestHooks.pollConnectionHealth();
    const afterAutomaticStart = globalThis.__eaTestHooks.getSnapshot();
    const readsAfterAutomaticStart = countReads();
    document.querySelector('[data-ea-recovery-action]').click();
    const afterManualClick = globalThis.__eaTestHooks.getSnapshot();
    const surface = document.querySelector('[data-ea-recovery-surface]');
    const button = surface?.querySelector('[data-ea-recovery-action]');
    return {
      readsBefore,
      readsAfterAutomaticStart,
      readsAfterManualClick: countReads(),
      automaticRefreshInFlight: afterAutomaticStart.refreshInFlight,
      manualRefreshInFlight: afterManualClick.refreshInFlight,
      retryInFlight: afterManualClick.connectionRetryInFlight,
      feedback: afterManualClick.connectionRetryFeedback,
      retryState: surface?.getAttribute('data-ea-retry-state') || '',
      buttonText: button?.textContent.trim() || '',
      buttonDisabled: Boolean(button?.disabled),
    };
  })()`);
  assert(coalescedRetryChecking.automaticRefreshInFlight && coalescedRetryChecking.manualRefreshInFlight, `manual retry joins the automatic full read already in flight: ${JSON.stringify(coalescedRetryChecking)}`);
  assert(coalescedRetryChecking.readsAfterAutomaticStart - coalescedRetryChecking.readsBefore === 1 && coalescedRetryChecking.readsAfterManualClick === coalescedRetryChecking.readsAfterAutomaticStart, `automatic and manual recovery coalesce into exactly one full read: ${JSON.stringify(coalescedRetryChecking)}`);
  assert(coalescedRetryChecking.retryInFlight && coalescedRetryChecking.feedback === "checking" && coalescedRetryChecking.retryState === "checking", `coalesced retry remains truthfully checking while the shared read is pending: ${JSON.stringify(coalescedRetryChecking)}`);
  assert(coalescedRetryChecking.buttonDisabled && coalescedRetryChecking.buttonText === "Checking…", `coalesced retry exposes one disabled Checking action: ${JSON.stringify(coalescedRetryChecking)}`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-recovery-kind=helper-unreachable]')?.getAttribute('data-ea-retry-state') === 'checked' && !globalThis.__eaTestHooks.getSnapshot().refreshInFlight && !globalThis.__eaTestHooks.getSnapshot().connectionRetryInFlight"));
  const coalescedRetryFinal = await evaluate(`(() => {
    const surface = document.querySelector('[data-ea-recovery-surface]');
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    return {
      totalReads: JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type === 'email-agent:get-state').length,
      feedback: snapshot.connectionRetryFeedback,
      connectionKind: snapshot.connectionKind,
      visibleText: surface?.innerText || '',
      diagnostics: surface?.querySelector('[data-ea-recovery-details]')?.textContent || '',
    };
  })()`);
  assert(coalescedRetryFinal.totalReads - coalescedRetryChecking.readsBefore === 1, `shared recovery completes with exactly one full read: ${JSON.stringify({ coalescedRetryChecking, coalescedRetryFinal })}`);
  assert(coalescedRetryFinal.feedback === "failed" && coalescedRetryFinal.connectionKind === "helper-unreachable" && coalescedRetryFinal.visibleText.includes("Still offline") && !coalescedRetryFinal.visibleText.includes("Ready"), `shared failed result returns one truthful offline state: ${JSON.stringify(coalescedRetryFinal)}`);
  assert(coalescedRetryFinal.diagnostics.includes("single coalesced state read"), `shared failed result retains the exact cause in diagnostics: ${JSON.stringify(coalescedRetryFinal)}`);
  results.steps.push({ step: "automatic-offline-read-manual-retry-coalescing", checking: coalescedRetryChecking, final: coalescedRetryFinal });

  for (const scenario of [
    { kind: "wrong-service", error: "Unexpected service identity.", details: "Expected threadwise-gmail-companion but received another service." },
    { kind: "health-failed", error: "Threadwise health response was not ready.", details: "Health endpoint returned status starting." },
    { kind: "connecting", error: "Connection is still opening.", details: "Waiting for the Threadwise health response." },
  ]) {
    activeStep = `variant-c-recovery-${scenario.kind}`;
    await evaluate(`window.__twSetConnectionScenario(${JSON.stringify(scenario)}); globalThis.__eaTestHooks.forceRefresh()`);
    await waitFor(() => evaluate(`Boolean(document.querySelector('[data-ea-recovery-kind=${scenario.kind}]')) && !globalThis.__eaTestHooks.getSnapshot().connectionRetryInFlight`));
    await assertRecoveryVisualContract(scenario.kind);
    await captureViewportSet(`recovery-${scenario.kind}`);
  }

  activeStep = "variant-c-recovery-loading";
  await evaluate("window.__twSetConnectionScenario({ kind: 'ready-loading', error: 'Threadwise is connected but the inbox state is still loading.' }); globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-recovery-kind=loading]'))"));
  await assertRecoveryVisualContract("loading");
  await captureViewportSet("recovery-loading");

  activeStep = "variant-c-recovery-successful-retry";
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', error: 'Failed to fetch synthetic Threadwise state.' }); globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-recovery-kind=helper-unreachable]'))"));
  await evaluate("window.__twSetConnectionScenario({ kind: 'ready', delayMs: 300 })");
  const successRetryChecking = await evaluate(`(() => {
    document.querySelector('[data-ea-recovery-action]').click();
    const button = document.querySelector('[data-ea-recovery-action]');
    return { text: button?.textContent.trim() || '', disabled: Boolean(button?.disabled), inFlight: globalThis.__eaTestHooks.getSnapshot().connectionRetryInFlight };
  })()`);
  assert(successRetryChecking.inFlight && successRetryChecking.disabled && successRetryChecking.text === "Checking\u2026", `successful retry begins with the same truthful checking state: ${JSON.stringify(successRetryChecking)}`);
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=review]')) && globalThis.__eaTestHooks.getSnapshot().connectionKind === 'ready' && globalThis.__eaTestHooks.getSnapshot().connectionRetryFeedback === ''"));
  results.steps.push({ step: "recovery-successful-retry", checking: successRetryChecking, returnedState: "review" });

  activeStep = "variant-c-recovery-automatic-five-second-recovery";
  await evaluate("window.__twSetConnectionScenario({ kind: 'helper-unreachable', error: 'Failed to fetch synthetic Threadwise state.' }); globalThis.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-recovery-kind=helper-unreachable]'))"));
  await evaluate("window.__twSetConnectionScenario({ kind: 'ready' })");
  const automaticRecoveryStartedAt = Date.now();
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=review]')) && globalThis.__eaTestHooks.getSnapshot().connectionKind === 'ready' && globalThis.__eaTestHooks.getSnapshot().connectionRetryFeedback === ''"), 8000);
  results.steps.push({ step: "recovery-automatic-five-second-recovery", elapsedMs: Date.now() - automaticRecoveryStartedAt, returnedState: "review" });
  results.ok = true;
} catch (error) {
  failure = error;
  results.error = error.message;
  results.failedStep = activeStep;
    results.failureSnapshot = await evaluate(`(() => ({
      hook: globalThis.__eaTestHooks?.getSnapshot?.(),
      policy: globalThis.__eaTestHooks?.getContextActionPolicy?.(),
      actions: globalThis.__eaTestHooks?.getContextActions?.(),
      menu: (() => { const menu = document.querySelector('#ea-context-menu'); const root = document.querySelector('#email-agent-companion-root')?.getBoundingClientRect(); const rect = menu?.getBoundingClientRect(); return { rect: rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height } : null, root: root ? { left: root.left, top: root.top, right: root.right, bottom: root.bottom } : null, inner: { width: innerWidth, height: innerHeight }, style: menu ? { display: getComputedStyle(menu).display, visibility: getComputedStyle(menu).visibility } : null }; })(),
      reviewPlacement: (() => { const rectOf = (node) => { const rect = node?.getBoundingClientRect?.(); return rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height } : null; }; const change = document.querySelector('[data-ea-action="change-suggestion"]'); const changeRect = rectOf(change); const hit = changeRect ? document.elementFromPoint(changeRect.left + changeRect.width / 2, changeRect.top + changeRect.height / 2) : null; return { accept: rectOf(document.querySelector('[data-ea-action="accept-suggestion"]')), change: changeRect, hit: hit?.outerHTML?.slice(0, 180) || '', hitIsChange: Boolean(hit && change && (hit === change || change.contains(hit))) }; })(),
      workspace: document.querySelector('#ea-workspace')?.innerText || '',
    active: document.activeElement?.outerHTML?.slice(0, 240) || ''
  }))()`).catch(() => null);
} finally {
  try {
    results.requests = await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || "[]")`);
  } catch (_error) {
    results.requests = [];
  }
  results.unexpectedRequests = results.requests.filter((request) => !(
    request?.type === "email-agent:get-state" && request.path === "" && request.method === ""
  ) && !(
    request?.type === "email-agent:probe-health" && request.path === "" && request.method === ""
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
    const append = (request) => { const log = JSON.parse(localStorage.getItem(logKey) || "[]"); log.push({ ...request, at: performance.now() }); localStorage.setItem(logKey, JSON.stringify(log)); };
    const clone = (value) => JSON.parse(JSON.stringify(value));
    let connectionScenario = { kind: "ready", delayMs: 0 };
    window.__twSetConnectionScenario = (scenario) => {
      connectionScenario = { kind: "ready", delayMs: 0, ...(scenario || {}) };
      return clone(connectionScenario);
    };
    const queueItems = ${JSON.stringify(queueItems)};
    const itemById = (id) => queueItems.find((item) => item.message_id === id) || null;
    const stateForContext = (context) => {
      const id = context?.message_id || "";
      const base = ${JSON.stringify(baseState())};
      let selected = clone(${JSON.stringify(selectedReview)});
      if (id === "handled-1") selected = { ...selected, found: true, message_id: id, subject: "Handled synthetic email", sender: "handled@example.test", status: "auto-handled", status_label: "Auto-handled", classification: "EA/Finance", internal_label: "finance", details: { write_status: "applied", inbox_status: "applied" } };
      if (id === "blocked-1") selected = { found: false, provider: "gmail", message_id: id, subject: "Blocked synthetic email", sender: "blocked@example.test", status: "not-in-snapshot", status_label: "Not in snapshot", reason: "Synthetic blocked state" };
      const item = itemById(id);
      if (item) selected = { ...item, found: true, suggested_label: item.classification === "EA/Finance" ? "finance" : "work", internal_label: item.classification === "EA/Finance" ? "finance" : "work", details: {}, understanding_state: "ready", understanding_label: "Ready" };
      base.selected_context = context || {};
      base.sidebar_state.selected_context = context || {};
      base.sidebar_state.selected_email = selected;
      return base;
    };
    window.chrome = { runtime: {
      lastError: null,
      onMessage: { addListener: () => undefined, removeListener: () => undefined },
      getURL: () => ${JSON.stringify(await assetDataUri())},
      getManifest: () => ({ version: "0.3.2" }),
      sendMessage(message, callback) {
        append({ type: message?.type || "unknown", path: message?.path || "", method: message?.method || "" });
        if (message?.type === "email-agent:probe-health") {
          const scenario = clone(connectionScenario);
          const respond = () => {
            if (scenario.kind === "ready" || scenario.kind === "ready-loading") {
              callback?.({ ok: true, connection_state: { kind: "ready", label: "Ready", details: "Synthetic health fixture is ready." } });
              return;
            }
            const labels = {
              "helper-unreachable": "Helper unreachable",
              "wrong-service": "Wrong service on port",
              "health-failed": "Health check failed",
              connecting: "Connecting",
            };
            callback?.({
              ok: false,
              error: scenario.error || "Synthetic health probe failed.",
              connection_state: {
                kind: scenario.kind,
                label: labels[scenario.kind] || "Unavailable",
                details: scenario.details || "Synthetic exact health failure detail.",
              },
            });
          };
          if (scenario.delayMs > 0) window.setTimeout(respond, scenario.delayMs); else respond();
          return true;
        }
        if (message?.type === "email-agent:get-state") {
          const scenario = clone(connectionScenario);
          const respond = () => {
            if (scenario.kind === "ready") {
              callback?.({ ok: true, payload: stateForContext(message.context || {}), connection_state: { kind: "ready", label: "Ready", details: "Synthetic fixture state." } });
              return;
            }
            if (scenario.kind === "ready-loading") {
              callback?.({ ok: false, error: scenario.error || "Threadwise is connected but the inbox state is still loading.", connection_state: { kind: "ready", label: "Ready", details: "Synthetic fixture is loading." } });
              return;
            }
            const labels = {
              "helper-unreachable": "Helper unreachable",
              "wrong-service": "Wrong service on port",
              "health-failed": "Health check failed",
              connecting: "Connecting",
            };
            callback?.({
              ok: false,
              error: scenario.error || "Synthetic " + scenario.kind + " response.",
              connection_state: {
                kind: scenario.kind,
                label: labels[scenario.kind] || "Unavailable",
                details: scenario.details || "Synthetic exact " + scenario.kind + " detail.",
              },
            });
          };
          if (scenario.delayMs > 0) window.setTimeout(respond, scenario.delayMs); else respond();
          return true;
        }
        if (message?.type === "threadwise:analytics") { callback?.({ ok: true }); return true; }
        callback?.({ ok: false, error: "Synthetic context-actions validator rejects " + (message?.path || message?.type || "unknown") + "." });
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
  for (const scriptName of ["provider_adapter.js", "analytics.js", "onboarding.js", "queue_navigation.js", "context_actions.js", "selected_explanation.js", "review_progression.js", "coverage.js", "content.js"]) {
    await evaluate(await fs.readFile(path.join(extensionRoot, scriptName), "utf8"));
  }
}

async function createSyntheticHost() {
  await evaluate(`(() => {
    /*
    document.body.innerHTML = ${JSON.stringify(`<main id="synthetic-gmail-host" style="min-height:1600px;margin:0;padding:32px 36px;background:#f4efe5;color:#241812;font-family:system-ui,sans-serif;"><div style="height:18px;width:240px;background:#e2d8c8;border-radius:4px;"></div><h2 data-thread-perm-id="thread-selected" style="margin-top:96px;font-size:28px;">Selected synthetic email</h2><div data-legacy-message-id="selected-live" data-thread-perm-id="thread-selected" style="display:block;max-width:620px;padding:20px;background:#fffdf8;border:1px solid #ded3c1;"><span email="live@example.test" data-hovercard-id="live@example.test">Live Sender</span><p style="line-height:1.6;">Synthetic Gmail host content for contextual action acceptance.</p></div></main>`)});
    */
    document.body.innerHTML = '<main id="synthetic-gmail-host" style="min-height:1600px;margin:0;padding:32px 36px;background:#f4efe5;color:#241812;font-family:system-ui,sans-serif;"><h2 data-thread-perm-id="thread-selected" style="margin-top:96px;font-size:28px;">Selected synthetic email</h2><div data-legacy-message-id="selected-live" data-thread-perm-id="thread-selected" style="display:block;max-width:620px;padding:20px;background:#fffdf8;border:1px solid #ded3c1;"><span email="live@example.test" data-hovercard-id="live@example.test">Live Sender</span><p>Synthetic Gmail host content for contextual action acceptance.</p></div></main>';
    document.documentElement.style.margin = "0"; document.body.style.margin = "0"; document.documentElement.style.scrollBehavior = "auto"; document.body.style.scrollBehavior = "auto";
    return true;
  })()`);
}

function baseState() {
  const context = { provider: "gmail", message_id: selectedReview.message_id, subject: selectedReview.subject, sender: selectedReview.sender, page_url: appUrl };
  return {
    selected_context: context,
    sidebar_state: { selected_context: context, selected_email: selectedReview, daily_summary: { needs_attention_count: queueItems.length, processed_count: 4, auto_handled_count: 1, kept_visible_count: 1, changed_today: {} }, ui_state: { provider_name: "Gmail", allowed_labels: [{ id: "finance", name: "Finance" }, { id: "work", name: "Work" }], async_follow_up: {} } },
    needs_attention_items: queueItems,
    recent_items: queueItems,
    auto_handled_items: [],
    kept_visible_items: [],
    analytics_status: { state: "disabled" },
  };
}

async function setHostMessage(messageId, subject, sender) {
  await evaluate(`(() => { const host = document.getElementById('synthetic-gmail-host'); const heading = host.querySelector('h2'); const message = host.querySelector('[data-legacy-message-id]'); heading.textContent = ${JSON.stringify(subject)}; message.setAttribute('data-legacy-message-id', ${JSON.stringify(messageId)}); message.querySelector('[email]').setAttribute('email', ${JSON.stringify(sender)}); window.location.hash = ${JSON.stringify(`#inbox/FM${messageId}`)}; return true; })()`);
}

async function assertNativeShortcutBoundaries() {
  await evaluate("document.querySelector('[data-ea-context-trigger]').focus(); document.querySelector('[data-ea-context-trigger]').dispatchEvent(new KeyboardEvent('keydown', { key: '.', bubbles: true, cancelable: true }))");
  assert(!(await evaluate("globalThis.__eaTestHooks.getContextActions().open")), "native button target rejects dot");
  const nativeTargetResults = await evaluate(`(() => {
    const workspace = document.querySelector('#ea-workspace');
    const targets = [
      document.createElement('input'),
      document.createElement('textarea'),
      document.createElement('select'),
      document.createElement('button'),
      document.createElement('a'),
      document.createElement('summary'),
      document.createElement('div'),
    ];
    targets[6].setAttribute('contenteditable', 'true');
    const details = document.createElement('details');
    details.appendChild(targets[5]);
    targets.forEach((target) => workspace.appendChild(target));
    workspace.appendChild(details);
    const results = targets.map((target) => {
      target.focus();
      target.dispatchEvent(new KeyboardEvent('keydown', { key: '.', bubbles: true, cancelable: true }));
      return !globalThis.__eaTestHooks.getContextActions().open;
    });
    targets.forEach((target) => target.remove());
    details.remove();
    return results;
  })()`);
  assert(nativeTargetResults.every(Boolean), "editable and native interactive targets retain dot behavior");
  await evaluate("document.getElementById('synthetic-gmail-host').dispatchEvent(new KeyboardEvent('keydown', { key: '.', bubbles: true, cancelable: true }))");
  assert(!(await evaluate("globalThis.__eaTestHooks.getContextActions().open")), "outside Gmail host target does not open the menu");
}

async function captureViewportSet(stateName) {
  for (const viewport of viewports) {
    await send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: false });
    await waitFor(() => evaluate("Boolean(document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width)"));
    const containment = await containmentSnapshot();
    assert(containment.contained, `${stateName} is contained at ${viewport.name}`);
    await waitFor(() => evaluate(`(() => {
      const menu = document.querySelector('#ea-context-menu');
      const root = document.querySelector('#email-agent-companion-root')?.getBoundingClientRect();
      const rect = menu?.getBoundingClientRect();
      const open = Boolean(globalThis.__eaTestHooks?.getContextActions?.().open);
      return !open || Boolean(menu && root && rect && rect.left >= root.left - 1 && rect.top >= root.top - 1 && rect.right <= root.right + 1 && rect.bottom <= root.bottom + 1 && rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight);
    })()`));
    const openMenu = await evaluate(`(() => {
      const menu = document.querySelector('#ea-context-menu');
      const root = document.querySelector('#email-agent-companion-root')?.getBoundingClientRect();
      const rect = menu?.getBoundingClientRect();
      const style = menu ? getComputedStyle(menu) : null;
      return {
        open: Boolean(globalThis.__eaTestHooks?.getContextActions?.().open),
        visible: Boolean(menu && !menu.hidden && style?.display !== 'none' && style?.visibility !== 'hidden' && rect && rect.width > 0 && rect.height > 0),
        contained: Boolean(menu && root && rect && rect.left >= root.left - 1 && rect.top >= root.top - 1 && rect.right <= root.right + 1 && rect.bottom <= root.bottom + 1 && rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth && rect.bottom <= innerHeight),
        itemCount: menu?.querySelectorAll('[data-ea-context-item]')?.length || 0,
        minTargetHeight: Math.min(...Array.from(menu?.querySelectorAll('[data-ea-context-item]') || []).map((item) => item.getBoundingClientRect().height), Infinity),
      };
    })()`);
    if (openMenu.open) {
      assert(openMenu.visible, `${stateName} menu is visible at ${viewport.name}`);
      assert(openMenu.contained, `${stateName} menu is contained at ${viewport.name}`);
      assert(openMenu.itemCount > 0, `${stateName} menu has items at ${viewport.name}`);
      assert(openMenu.minTargetHeight >= 44, `${stateName} menu keeps 44px targets at ${viewport.name}`);
    }
    if (stateName === "review-open" && (viewport.name === "756x469" || viewport.name === "360x800")) {
      const placement = await evaluate(`(() => {
        const rectOf = (node) => {
          const rect = node?.getBoundingClientRect?.();
          return rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height } : null;
        };
        const intersects = (a, b) => Boolean(a && b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top);
        const menu = document.querySelector('#ea-context-menu');
        const root = document.querySelector('#email-agent-companion-root');
        const accept = document.querySelector('[data-ea-action="accept-suggestion"]');
        const change = document.querySelector('[data-ea-context-item="change-label"]');
        const directChange = document.querySelector('[data-ea-action="change-suggestion"]:not([data-ea-context-item])');
        const menuRect = rectOf(menu);
        const acceptRect = rectOf(accept);
        const changeRect = rectOf(change);
        const rootRect = rectOf(root);
        const hitTarget = changeRect ? document.elementFromPoint(changeRect.left + changeRect.width / 2, changeRect.top + changeRect.height / 2) : null;
        return {
          placement: menu?.dataset.eaContextPlacement || '',
          menu: menuRect,
          root: rootRect,
          accept: acceptRect,
          change: changeRect,
          menuIntersectsAccept: intersects(menuRect, acceptRect),
          controlsVisible: Boolean(
            acceptRect && changeRect
            && acceptRect.width > 0 && acceptRect.height > 0
            && changeRect.width > 0 && changeRect.height > 0
            && acceptRect.left + acceptRect.width / 2 >= 0 && acceptRect.left + acceptRect.width / 2 <= innerWidth
            && acceptRect.top + acceptRect.height / 2 >= 0 && acceptRect.top + acceptRect.height / 2 <= innerHeight
            && getComputedStyle(accept).visibility !== 'hidden'
            && getComputedStyle(change).visibility !== 'hidden'
            && getComputedStyle(change).pointerEvents !== 'none'
            && change.textContent.trim() === 'Change label'
          ),
          directChangeVisible: Boolean(directChange && directChange.getBoundingClientRect().width > 0 && directChange.getBoundingClientRect().height > 0),
          hitTargetIsChange: Boolean(hitTarget && (hitTarget === change || change.contains(hitTarget))),
          hitTarget: hitTarget?.outerHTML?.slice(0, 180) || '',
        };
      })()`);
      assert(!placement.menuIntersectsAccept, `review-open menu does not intersect Accept at ${viewport.name}`);
      assert(placement.controlsVisible, `review-open keeps Accept and contextual Change label readable at ${viewport.name}`);
      assert(!placement.directChangeVisible, `review-open does not restore a second visible Change label action at ${viewport.name}`);
      assert(placement.hitTargetIsChange, `review-open contextual Change label remains hit-testable at ${viewport.name}`);
      const requestCountBeforeChange = await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type !== 'email-agent:probe-health').length`);
      assert(await evaluate("document.activeElement?.getAttribute('data-ea-context-item') === 'change-label'"), `review-open focuses Change label for keyboard discovery at ${viewport.name}`);
      await pressKey("Enter");
      await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=change]') && !globalThis.__eaTestHooks.getContextActions().open"));
      assert((await evaluate("document.querySelectorAll('[data-ea-selected-state=change]').length")) === 1, `Change label enters change state exactly once at ${viewport.name}`);
      assert((await evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]').filter((request) => request.type !== 'email-agent:probe-health').length`)) === requestCountBeforeChange, `keyboard Change label causes no unexpected request at ${viewport.name}`);
      await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
      await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && globalThis.__eaTestHooks.getContextActions().items.map((item) => item.id).join(',') === 'cancel-change'"));
      await evaluate("document.querySelector('[data-ea-context-item=cancel-change]').click()");
      await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]') && !globalThis.__eaTestHooks.getContextActions().open"));
      await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
      await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && document.querySelector('#ea-context-menu')"));
      results.steps.push({ step: `review-open-placement-${viewport.name}`, placement });
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
  const expectedContentScrollTop = Math.min(seededContentScrollTop, Math.max(0, snapshot.contentScrollHeight - snapshot.contentClientHeight));
  assert(snapshot.contentScrollTop === expectedContentScrollTop, `seeded companion scroll matches available overflow: ${snapshot.contentScrollTop} of ${expectedContentScrollTop}`);
  return snapshot;
}

async function assertVariantCVisualContract() {
  const visual = await evaluate(`(() => {
    const root = document.getElementById('email-agent-companion-root');
    const panel = document.getElementById('ea-panel');
    const header = document.getElementById('ea-header');
    const logo = document.getElementById('ea-brand-toggle');
    const primary = document.querySelector('[data-ea-review-dock] [data-tw-primary-action]');
    const contextual = document.querySelector('[data-ea-review-dock] [data-ea-context-trigger]');
    const context = document.querySelector('[data-ea-current-message-context]');
    const facts = document.querySelector('[data-ea-review-facts]');
    const style = (node) => node ? getComputedStyle(node) : null;
    const panelStyle = style(panel);
    const primaryStyle = style(primary);
    return {
      rootWidth: root?.getBoundingClientRect().width || 0,
      panelBackground: panelStyle?.backgroundColor || '',
      panelBorderWidth: panelStyle?.borderTopWidth || '',
      panelBorderColor: panelStyle?.borderTopColor || '',
      panelRadius: panelStyle?.borderTopLeftRadius || '',
      panelShadow: panelStyle?.boxShadow || '',
      headerHeight: header?.getBoundingClientRect().height || 0,
      logoWidth: logo?.getBoundingClientRect().width || 0,
      primaryHeight: primary?.getBoundingClientRect().height || 0,
      primaryBackground: primaryStyle?.backgroundColor || '',
      primaryColor: primaryStyle?.color || '',
      primaryBorderWidth: primaryStyle?.borderTopWidth || '',
      primaryShadow: primaryStyle?.boxShadow || '',
      contextualWidth: contextual?.getBoundingClientRect().width || 0,
      factsVisible: Boolean(facts && facts.getBoundingClientRect().height > 0),
      factsRows: facts?.querySelectorAll('[data-ea-review-fact]').length || 0,
      contextPadding: style(context)?.padding || '',
    };
  })()`);
  assert(Math.abs(visual.rootWidth - 408) <= 1, `Variant C shell is 408px wide: ${visual.rootWidth}`);
  assert(visual.panelBackground === 'rgb(255, 255, 255)', `Variant C shell is white: ${visual.panelBackground}`);
  assert(visual.panelBorderWidth === '1px', `Variant C shell uses a 1px border: ${visual.panelBorderWidth}`);
  assert(visual.panelBorderColor === 'rgb(205, 210, 216)', `Variant C shell uses the strong line token: ${visual.panelBorderColor}`);
  assert(visual.panelRadius === '12px', `Variant C shell uses a 12px radius: ${visual.panelRadius}`);
  assert(visual.panelShadow.includes('rgba(31, 35, 40, 0.12)'), `Variant C shell uses only the soft native shadow: ${visual.panelShadow}`);
  assert(Math.abs(visual.headerHeight - 52) <= 1, `Variant C header is 52px high: ${visual.headerHeight}`);
  assert(Math.abs(visual.logoWidth - 28) <= 1, `Variant C logo is 28px: ${visual.logoWidth}`);
  assert(Math.abs(visual.primaryHeight - 40) <= 1, `Variant C primary action is 40px high: ${visual.primaryHeight}`);
  assert(visual.primaryBackground === 'rgb(99, 91, 255)', `Variant C primary uses #635bff: ${visual.primaryBackground}`);
  assert(visual.primaryColor === 'rgb(255, 255, 255)', `Variant C primary uses white ink: ${visual.primaryColor}`);
  assert(visual.primaryBorderWidth === '0px', `Variant C primary has no heavy border: ${visual.primaryBorderWidth}`);
  assert(visual.primaryShadow === 'none', `Variant C primary has no block shadow: ${visual.primaryShadow}`);
  assert(Math.abs(visual.contextualWidth - 38) <= 1, `Variant C contextual action is 38px wide: ${visual.contextualWidth}`);
  assert(visual.factsVisible && visual.factsRows === 3, `Variant C shows all three exact facts: ${JSON.stringify(visual)}`);
  assert(visual.contextPadding === '15px 16px 13px', `Variant C context density matches the reference: ${visual.contextPadding}`);
  results.steps.push({ step: 'variant-c-visual-contract', visual });
}

async function assertRecoveryVisualContract(expectedKind) {
  const visual = await evaluate(`(() => {
    const root = document.getElementById('email-agent-companion-root');
    const panel = document.getElementById('ea-panel');
    const surface = document.querySelector('[data-ea-recovery-surface]');
    const primary = surface?.querySelector('[data-tw-primary-action]');
    const details = surface?.querySelector('[data-ea-recovery-details]');
    const panelStyle = panel ? getComputedStyle(panel) : null;
    const surfaceStyle = surface ? getComputedStyle(surface) : null;
    const primaryStyle = primary ? getComputedStyle(primary) : null;
    return {
      kind: surface?.getAttribute('data-ea-recovery-kind') || '',
      retryState: surface?.getAttribute('data-ea-retry-state') || '',
      visibleText: surface?.innerText || '',
      diagnostics: details?.textContent || '',
      detailsOpen: Boolean(details?.open),
      viewportWidth: innerWidth,
      rootWidth: root?.getBoundingClientRect().width || 0,
      panelBackground: panelStyle?.backgroundColor || '',
      panelBorderWidth: panelStyle?.borderTopWidth || '',
      panelBorderColor: panelStyle?.borderTopColor || '',
      panelShadow: panelStyle?.boxShadow || '',
      surfaceBackground: surfaceStyle?.backgroundColor || '',
      surfaceFont: surfaceStyle?.fontFamily || '',
      primaryCount: surface?.querySelectorAll('[data-tw-primary-action]').length || 0,
      progressVisible: Boolean(surface?.querySelector('[data-ea-recovery-progress]')?.getBoundingClientRect().height),
      primaryBackground: primaryStyle?.backgroundColor || '',
      primaryColor: primaryStyle?.color || '',
      primaryBorderWidth: primaryStyle?.borderTopWidth || '',
      primaryShadow: primaryStyle?.boxShadow || '',
      primaryHeight: primary?.getBoundingClientRect().height || 0,
    };
  })()`);
  assert(visual.kind === expectedKind, `recovery exposes truthful ${expectedKind} kind: ${JSON.stringify(visual)}`);
  if (visual.viewportWidth > 480) {
    assert(Math.abs(visual.rootWidth - 408) <= 1, `recovery keeps the 408px Variant C shell: ${visual.rootWidth}`);
  } else {
    assert(visual.rootWidth >= 300 && visual.rootWidth <= visual.viewportWidth - 16, `recovery keeps the responsive Variant C shell at narrow width: ${JSON.stringify(visual)}`);
  }
  assert(visual.panelBackground === 'rgb(255, 255, 255)', `recovery panel is white: ${visual.panelBackground}`);
  assert(visual.panelBorderWidth === '1px' && visual.panelBorderColor === 'rgb(205, 210, 216)', `recovery panel uses the neutral 1px border: ${JSON.stringify(visual)}`);
  assert(visual.panelShadow.includes('rgba(31, 35, 40, 0.12)'), `recovery panel uses only the soft native shadow: ${visual.panelShadow}`);
  assert(visual.surfaceBackground === 'rgba(0, 0, 0, 0)', `recovery surface has no cream card fill: ${visual.surfaceBackground}`);
  assert(!visual.visibleText.toLowerCase().includes('local companion') && !visual.visibleText.toLowerCase().includes('startup helper'), `visible recovery copy hides implementation terms: ${visual.visibleText}`);
  if (expectedKind !== 'loading') {
    assert(!visual.detailsOpen && visual.diagnostics.toLowerCase().includes(expectedKind === 'helper-unreachable' ? 'unreachable' : expectedKind.replace('-', ' ')), `collapsed diagnostics retain the exact reason: ${visual.diagnostics}`);
  }
  if (expectedKind === 'loading') {
    assert(visual.primaryCount === 0 && visual.progressVisible, `loading uses quiet progress without a false recovery action: ${JSON.stringify(visual)}`);
    results.steps.push({ step: `recovery-visual-${expectedKind}`, visual });
    return visual;
  }
  assert(visual.primaryCount === 1 && Math.abs(visual.primaryHeight - 40) <= 1, `recovery has one 40px primary action: ${JSON.stringify(visual)}`);
  assert(visual.primaryBackground === 'rgb(99, 91, 255)' && visual.primaryColor === 'rgb(255, 255, 255)', `recovery primary uses Variant C purple: ${JSON.stringify(visual)}`);
  assert(visual.primaryBorderWidth === '0px' && visual.primaryShadow === 'none', `recovery primary has no heavy border or block shadow: ${JSON.stringify(visual)}`);
  results.steps.push({ step: `recovery-visual-${expectedKind}`, visual });
  return visual;
}

async function scrollSnapshot() {
  return evaluate(`(() => ({ pageX: window.scrollX, pageY: window.scrollY, contentScrollTop: document.getElementById('ea-content')?.scrollTop || 0, contentScrollLeft: document.getElementById('ea-content')?.scrollLeft || 0, pageScrollHeight: document.documentElement.scrollHeight, pageClientHeight: document.documentElement.clientHeight, contentScrollHeight: document.getElementById('ea-content')?.scrollHeight || 0, contentClientHeight: document.getElementById('ea-content')?.clientHeight || 0 }))()`);
}

async function recordFocus(step) {
  results.focusTrace.push({
    step,
    active: await evaluate("document.activeElement ? { tag: document.activeElement.tagName, action: document.activeElement.getAttribute('data-ea-action') || '', contextItem: document.activeElement.getAttribute('data-ea-context-item') || '', trigger: document.activeElement.hasAttribute('data-ea-context-trigger') } : null"),
  });
}

function recordScroll(step, before, after) {
  results.scrollTrace.push({ step, before, after });
}

function assertScrollUnchanged(before, after, step) {
  for (const key of ["pageX", "pageY", "contentScrollTop", "contentScrollLeft"]) {
    assert(before[key] === after[key], `${step} preserves ${key}: ${before[key]} -> ${after[key]}`);
  }
}

function assertScrollRangeUnchanged(before, after, step) {
  for (const key of ["contentScrollHeight", "contentClientHeight"]) {
    assert(before[key] === after[key], `${step} preserves ${key}: ${before[key]} -> ${after[key]}`);
  }
}

async function containmentSnapshot() {
  return evaluate(`(() => { const root = document.getElementById('email-agent-companion-root')?.getBoundingClientRect(); const host = document.getElementById('synthetic-gmail-host')?.getBoundingClientRect(); return { contained: Boolean(root && root.left >= 0 && root.top >= 0 && root.right <= innerWidth + 1 && root.bottom <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth && host?.left === 0), root: root ? { left: root.left, top: root.top, right: root.right, bottom: root.bottom, width: root.width } : null, viewport: { width: innerWidth, height: innerHeight } }; })()`);
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
  throw new Error(`Timed out at ${activeStep}: ${await evaluate("document.body.innerText.slice(0, 1000)").catch(() => "unavailable")}`);
}

async function pressKey(key) {
  await send("Input.dispatchKeyEvent", { type: "rawKeyDown", key, code: /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : key, windowsVirtualKeyCode: /^[a-z]$/i.test(key) ? key.toUpperCase().charCodeAt(0) : 0 });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key, code: /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : key, windowsVirtualKeyCode: /^[a-z]$/i.test(key) ? key.toUpperCase().charCodeAt(0) : 0 });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
