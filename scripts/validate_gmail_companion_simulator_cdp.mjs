const appUrl = process.argv[2] || "http://127.0.0.1:8031/simulator";
const cdpBase = process.argv[3] || "http://127.0.0.1:9222";
const applyMode = process.argv[4] || "future-only";

const target = await createTarget(appUrl);
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
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"), 15000);
  await waitFor(() => evaluate("document.querySelectorAll('#sim-list [data-queue-message-id]').length > 0"), 15000);

  const initialState = await evaluate(`({
    title: document.querySelector('h1').innerText,
    subtitle: document.querySelector('#sim-subtitle').innerText,
    listCount: document.querySelectorAll('#sim-list [data-queue-message-id]').length,
    selectedSubject: document.querySelector('#sim-message .message-title')?.innerText || '',
    minimizeLabel: document.querySelector('#sim-minimize')?.innerText || ''
  })`);

  await evaluate(`(() => { document.querySelector('#sim-minimize').click(); return true; })()`);
  await waitFor(() => evaluate("document.querySelector('.panel').classList.contains('minimized')"));
  await evaluate(`(() => { document.querySelector('#sim-minimize').click(); return true; })()`);
  await waitFor(() => evaluate("!document.querySelector('.panel').classList.contains('minimized')"));

  await evaluate(`(() => {
    const button = document.querySelector('#sim-filter-pills [data-filter="kept_visible_items"]');
    if (button) button.click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-filter-pills [data-filter=\"kept_visible_items\"]').classList.contains('active')"));
  const keptVisibleCount = await evaluate("document.querySelectorAll('#sim-list [data-queue-message-id]').length");

  await evaluate(`(() => {
    const button = document.querySelector('#sim-filter-pills [data-filter="recent_items"]');
    if (button) button.click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-filter-pills [data-filter=\"recent_items\"]').classList.contains('active')"));
  await evaluate(`(async () => {
    const target = (harnessState?.recent_items || []).find((item) => item.unsubscribe_available);
    if (!target) {
      return false;
    }
    currentContext = {
      provider: "gmail",
      message_id: target.message_id || "",
      subject: target.subject || "",
      sender: target.sender || "",
    };
    resetTeachState(true);
    await refreshState();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-selected-email a[href=\"/unsubscribe-review\"]') !== null"));
  const unsubscribeState = await evaluate(`(() => {
    const quick = document.querySelector('[data-action="select-unsubscribe"]');
    const handoff = document.querySelector('#sim-selected-email a[href="/unsubscribe-review"]');
    const external = Array.from(document.querySelectorAll('#sim-selected-email a')).find((node) => node.getAttribute('href') !== '/unsubscribe-review');
    return {
      title: document.querySelector('#sim-selected-email .reason-wrap .reason')?.innerText || '',
      quickActionVisible: !!quick,
      handoffVisible: !!handoff,
      externalLabel: external?.innerText || ''
    };
  })()`);
  if (await evaluate("document.querySelector('[data-action=\"select-unsubscribe\"]') !== null")) {
    await evaluate(`(() => {
      document.querySelector('[data-action="select-unsubscribe"]').click();
      return true;
    })()`);
    await waitFor(() => evaluate("document.querySelector('#sim-selected-email').innerText.includes('Queued')"));
  }
  const unsubscribeAfterQueue = await evaluate(`({
    queueAckPresent: document.querySelector('#sim-selected-email').innerText.includes('Queued'),
    reviewLinkPresent: !!document.querySelector('#sim-selected-email a[href="/unsubscribe-review"]')
  })`);

  await evaluate(`(() => {
    const button = document.querySelector('#sim-filter-pills [data-filter="needs_attention_items"]');
    if (button) button.click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-filter-pills [data-filter=\"needs_attention_items\"]').classList.contains('active')"));

  await evaluate(`(() => {
    const target = Array.from(document.querySelectorAll('#sim-list [data-queue-message-id]'))
      .find((node) => node.innerText.toLowerCase().includes('linkedin job alerts'));
    if (target) target.click();
    return true;
  })()`);
  await waitFor(() => evaluate("(document.querySelector('#sim-selected-email .sender')?.innerText || '').toLowerCase().includes('linkedin')"));

  const selectedBefore = await evaluate(`({
    selectedSubject: document.querySelector('#sim-selected-email .subject')?.innerText || '',
    classification: document.querySelector('#sim-selected-email .classification-pill')?.innerText || '',
    status: document.querySelector('#sim-selected-email .warn-pill, #sim-selected-email .status-pill')?.innerText || ''
  })`);

  await evaluate(`(() => {
    document.querySelector('#sim-target-label').value = 'job-related';
    document.querySelector('#sim-target-label').dispatchEvent(new Event('change', { bubbles: true }));
    const note = document.querySelector('#sim-teach-note');
    note.value = 'Simulator teaching pass: LinkedIn job alerts should be work-related and kept visible.';
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="preview-teach"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.body.innerText.includes('Matching existing emails:')"));

  const previewState = await evaluate(`({
    previewVisible: !!document.querySelector('.preview-card'),
    previewText: document.querySelector('.preview-card')?.innerText || '',
    previewExamples: Array.from(document.querySelectorAll('.preview-card li')).map((node) => node.innerText)
  })`);

  await evaluate(`(() => {
    document.querySelector('[data-action="refine-teach"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-previous-preview=\"true\"]') !== null"));

  const refineState = await evaluate(`({
    previewVisible: !!document.querySelector('.preview-card'),
    previousVisible: !!document.querySelector('[data-previous-preview="true"]'),
    previousText: document.querySelector('[data-previous-preview="true"]')?.innerText || ''
  })`);

  await evaluate(`(() => {
    const note = document.querySelector('#sim-teach-note');
    note.value = 'Revised simulator teaching pass: recurring LinkedIn job alerts should be EA/Work unless they are direct person-to-person messages.';
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="preview-teach"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelectorAll('[data-previous-preview=\"true\"]').length === 1 && document.querySelector('.preview-card') !== null"));

  const compareState = await evaluate(`({
    previousVisible: !!document.querySelector('[data-previous-preview="true"]'),
    previousText: document.querySelector('[data-previous-preview="true"]')?.innerText || '',
    revisedText: document.querySelector('.preview-card')?.innerText || ''
  })`);

  await evaluate(`(() => {
    const note = document.querySelector('#sim-teach-note');
    note.value = 'Temporary draft that should clear cleanly.';
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="clear-teach"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-teach-note') && document.querySelector('#sim-teach-note').value === ''"));

  const clearState = await evaluate(`({
    draftNote: document.querySelector('#sim-teach-note')?.value || '',
    previousVisible: !!document.querySelector('[data-previous-preview="true"]'),
    previewVisible: !!document.querySelector('.preview-card')
  })`);

  await evaluate(`(() => {
    document.querySelector('#sim-target-label').value = 'job-related';
    document.querySelector('#sim-target-label').dispatchEvent(new Event('change', { bubbles: true }));
    const note = document.querySelector('#sim-teach-note');
    note.value = 'Final simulator teaching pass before apply: LinkedIn job alerts should be work-related and kept visible.';
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="preview-teach"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('.preview-card') !== null"));

  await evaluate(`(() => {
    document.querySelector('[data-apply-mode="${applyMode}"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('.success-card') !== null"));

  const afterApply = await evaluate(`({
    successText: document.querySelector('.success-card')?.innerText || '',
    selectedSubject: document.querySelector('#sim-selected-email .subject')?.innerText || '',
    simulatorModeText: document.body.innerText.includes('disables Gmail write-through'),
    needsAttentionSummary: document.querySelector('#sim-daily-summary')?.innerText || '',
    draftNote: document.querySelector('#sim-teach-note')?.value || '',
    previousVisible: !!document.querySelector('[data-previous-preview="true"]')
  })`);

  await evaluate(`(() => { document.querySelector('#sim-unsynced').click(); return true; })()`);
  await waitFor(() => evaluate("document.body.innerText.includes('Fresh message not in local sync yet')"));

  const unsyncedState = await evaluate(`({
    readingPaneTitle: document.querySelector('#sim-message .message-title')?.innerText || '',
    panelNoticePresent: document.body.innerText.includes('This email is not in the current local sync.'),
    queueVisible: document.body.innerText.toLowerCase().includes('current queue')
  })`);

  await evaluate(`(() => {
    const firstQueueItem = document.querySelector('#sim-selected-email [data-queue-message-id]');
    if (firstQueueItem) {
      firstQueueItem.click();
      return true;
    }
    return false;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-selected-email .subject') !== null"));

  const queueRecoveryState = await evaluate(`({
    selectedSubject: document.querySelector('#sim-selected-email .subject')?.innerText || '',
    queuePreviewed: !document.body.innerText.includes('This email is not in the current local sync.')
  })`);

  await evaluate(`(() => {
    const button = document.querySelector('#sim-daily-summary [data-filter="recent_items"]');
    if (button) {
      button.click();
      return true;
    }
    return false;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-daily-summary [data-filter=\"recent_items\"]')?.classList.contains('active') === true"));
  await evaluate(`(() => {
    const firstQueueItem = document.querySelector('#sim-daily-summary [data-queue-message-id]');
    if (firstQueueItem) {
      firstQueueItem.click();
      return true;
    }
    return false;
  })()`);
  await waitFor(() => evaluate("document.querySelector('#sim-selected-email .subject') !== null"));

  const summaryNavigationState = await evaluate(`({
    recentFilterActive: !!document.querySelector('#sim-daily-summary [data-filter="recent_items"].active'),
    selectedSubject: document.querySelector('#sim-selected-email .subject')?.innerText || ''
  })`);

  const result = {
    initialState,
    keptVisibleCount,
    unsubscribeState,
    unsubscribeAfterQueue,
    selectedBefore,
    previewState,
    refineState,
    compareState,
    clearState,
    afterApply,
    unsyncedState,
    queueRecoveryState,
    summaryNavigationState,
  };

  console.log(JSON.stringify(result, null, 2));

  if (
    initialState.title !== "Email Agent Inbox Simulator" ||
    initialState.listCount < 1 ||
    initialState.minimizeLabel !== "Minimize" ||
    keptVisibleCount < 1 ||
    !unsubscribeState.handoffVisible ||
    (unsubscribeState.quickActionVisible === false && unsubscribeState.externalLabel === "") ||
    !unsubscribeAfterQueue.reviewLinkPresent ||
    !selectedBefore.selectedSubject ||
    !previewState.previewText.includes("EA/Work") ||
    !previewState.previewVisible ||
    !previewState.previewText.includes("Matching existing emails: 24") ||
    previewState.previewExamples.some((line) => line.includes("spam-low-value")) ||
    refineState.previewVisible ||
    !refineState.previousVisible ||
    !refineState.previousText.toLowerCase().includes("previous interpretation") ||
    !compareState.previousVisible ||
    !compareState.previousText.toLowerCase().includes("previous interpretation") ||
    !compareState.revisedText.includes("Matching existing emails: 24") ||
    clearState.draftNote !== "" ||
    clearState.previousVisible ||
    clearState.previewVisible ||
    !(applyMode === "future-only"
      ? afterApply.successText.includes("future mail")
      : afterApply.successText.includes("rewrote")) ||
    !afterApply.simulatorModeText ||
    afterApply.draftNote !== "" ||
    afterApply.previousVisible ||
    !unsyncedState.panelNoticePresent ||
    !unsyncedState.queueVisible ||
    !queueRecoveryState.queuePreviewed ||
    queueRecoveryState.selectedSubject === "" ||
    !summaryNavigationState.recentFilterActive ||
    summaryNavigationState.selectedSubject === ""
  ) {
    process.exitCode = 1;
  }
} finally {
  socket.close();
}

async function createTarget(url) {
  const response = await fetch(`${cdpBase}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) {
    throw new Error(`Could not create Chrome target: ${response.status}`);
  }
  return response.json();
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
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  let pageState = "";
  try {
    pageState = await evaluate("document.body.innerText.slice(0, 2000)");
  } catch (_error) {
    pageState = "<page-state-unavailable>";
  }
  throw new Error(`Timed out waiting for browser state. Snapshot:\\n${pageState}`);
}
