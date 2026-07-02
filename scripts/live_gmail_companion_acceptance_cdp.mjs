const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const localOrigin = process.argv[3] || "http://127.0.0.1:8021";

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

  const initial = await sidebarSnapshot();
  const listInfo = await evaluate(`(() => {
    const rows = Array.from(document.querySelectorAll('tr[role="row"]'));
    return {
      rowCount: rows.length,
      hash: window.location.hash || "",
      title: document.title,
      url: window.location.href,
    };
  })()`);

  let openedThread = false;
  if (!initial.context.message_id) {
    openedThread = await evaluate(`(() => {
      const candidates = Array.from(document.querySelectorAll('tr[role="row"]')).filter((row) => {
        const subject = row.querySelector('span[data-thread-id], span[data-legacy-thread-id], span.bog, span.y2');
        return !!subject;
      });
      const row = candidates[0];
      if (!row) {
        return false;
      }
      row.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      return true;
    })()`);
    if (openedThread) {
      await waitFor(async () => {
        const snapshot = await sidebarSnapshot();
        return Boolean(snapshot.context.message_id || snapshot.selected.subject);
      }, 20000);
    }
  }

  const afterOpen = await sidebarSnapshot();
  const queueSelection = await selectQueueItem();
  const afterQueueSelection = await sidebarSnapshot();
  const filterNavigation = await verifySummaryFilterNavigation();
  const draftPersistence = await verifyDraftPersistence();
  const teachPreview = queueSelection
    ? await runTeachPreview()
    : { attempted: false };

  const result = {
    target: {
      id: target.id,
      title: target.title,
      url: target.url,
    },
    initial,
    listInfo,
    openedThread,
    afterOpen,
    queueSelection,
    afterQueueSelection,
    filterNavigation,
    draftPersistence,
    teachPreview,
  };

  result.checks = buildChecks(result);
  result.ok = Object.values(result.checks).every(Boolean);

  if (!result.ok) {
    console.error(JSON.stringify(result, null, 2));
    process.exitCode = 1;
  } else {
    console.log(JSON.stringify(result, null, 2));
  }
} finally {
  socket.close();
}

function buildChecks(result) {
  const queueText = result.queueSelection?.panelText || "";
  const teachText = result.teachPreview?.finalText || result.teachPreview?.selected || "";
  const summaryText = result.initial?.summary?.text || result.afterOpen?.summary?.text || "";
  return {
    sidebarLoaded: Boolean(result.afterOpen?.hasRoot && result.afterOpen?.subtitle),
    queuePreviewReached: Boolean(result.queueSelection?.ok && queueText.includes("QUEUE PREVIEW")),
    unsubscribeActionVisible: queueText.includes("Queue unsubscribe review"),
    summaryFilterNavigation: Boolean(result.filterNavigation?.attempted && result.filterNavigation?.ok),
    draftPersistsAcrossRefresh: Boolean(result.draftPersistence?.attempted && result.draftPersistence?.ok),
    teachPreviewReached: Boolean(result.teachPreview?.attempted && result.teachPreview?.hasPreview),
    impactWarningVisible: teachText.includes("Would affect"),
    explicitChoiceCopyVisible: teachText.includes("Fix this email") && teachText.includes("Also apply broader rule"),
    keepDiscussingVisible: teachText.includes("Keep discussing"),
    dailySummaryVisible: summaryText.includes("WHAT CHANGED TODAY") || summaryText.includes("What Changed Today"),
  };
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
    await pumpBridge();
    if (await fn()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error("Timed out waiting for live Gmail state.");
}

async function sidebarSnapshot() {
  return evaluate(`(() => {
    const root = document.getElementById('email-agent-companion-root');
    const selected = document.getElementById('ea-selected-email');
    const summary = document.getElementById('ea-daily-summary');
    const subtitle = document.getElementById('ea-subtitle');
    const messageNode =
      document.querySelector('[data-legacy-message-id]') ||
      document.querySelector('[data-message-id]');
    const senderNode =
      document.querySelector('[email][data-hovercard-id]') ||
      document.querySelector('span[email]');
    const subjectNode =
      document.querySelector('h2[data-thread-perm-id]') ||
      document.querySelector('h2.hP') ||
      document.querySelector("h2[role='heading']");

    return {
      hasRoot: !!root,
      subtitle: subtitle ? subtitle.innerText : "",
      selected: {
        text: selected ? selected.innerText.slice(0, 4000) : "",
        subject: subjectNode ? subjectNode.innerText.trim() : "",
        sender: senderNode ? (senderNode.getAttribute('email') || senderNode.innerText || '').trim() : "",
      },
      summary: {
        text: summary ? summary.innerText.slice(0, 4000) : "",
      },
      context: {
        message_id: messageNode ? (messageNode.getAttribute('data-legacy-message-id') || messageNode.getAttribute('data-message-id') || '') : "",
        thread_id: messageNode ? (messageNode.getAttribute('data-thread-perm-id') || '') : "",
        hash: window.location.hash || "",
        url: window.location.href,
        title: document.title,
      },
    };
  })()`);
}

async function selectQueueItem() {
  await evaluate(`(() => {
    if (!globalThis.__eaTestHooks || typeof globalThis.__eaTestHooks.selectSummaryFilter !== 'function') {
      return { ok: false, error: 'missing-filter-hook' };
    }
    return globalThis.__eaTestHooks.selectSummaryFilter('needs_attention_items');
  })()`);
  await waitFor(async () => {
    const snapshot = await evaluate(`globalThis.__eaTestHooks.getSnapshot()`);
    return snapshot.activeSummaryFilter === "needs_attention_items";
  }, 10000);
  const selected = await evaluate(`(() => {
    const preferred = Array.from(document.querySelectorAll('[data-ea-summary-item]')).find((node) =>
      node.innerText.toLowerCase().includes('linkedin')
    );
    const fallback = document.querySelector('[data-ea-summary-item]');
    const target = preferred || fallback;
    if (!target) {
      return null;
    }
    const messageId = target.getAttribute('data-ea-summary-item') || '';
    const text = target.innerText || '';
    if (!globalThis.__eaTestHooks || typeof globalThis.__eaTestHooks.selectSummaryItem !== 'function') {
      return { ok: false, error: 'missing-test-hooks', messageId, text };
    }
    const result = globalThis.__eaTestHooks.selectSummaryItem(messageId);
    return { ...result, messageId, text };
  })()`);
  if (!selected) {
    return null;
  }
  const finalText = await settlePanel((text) => {
    const normalized = text.toLowerCase();
    return normalized.includes('queue preview') || normalized.includes('correct / teach');
  }, 10000);
  return {
    ...selected,
    panelText: finalText,
  };
}

async function runTeachPreview() {
  const before = await evaluate(`(() => {
    const selected = document.getElementById('ea-selected-email')?.innerText || '';
    if (!globalThis.__eaTestHooks || typeof globalThis.__eaTestHooks.previewTeach !== 'function') {
      return { attempted: false, reason: 'preview-hook-missing', selected };
    }
    const result = globalThis.__eaTestHooks.previewTeach(
      'job-related',
      'Acceptance harness: LinkedIn job alerts should be work-related and kept visible.',
    );
    return { attempted: true, selected, result };
  })()`);
  if (!before.attempted) {
    return before;
  }
  const finalText = await settlePanel((text) => {
    return text.includes('Would affect') || text.includes('Could not preview the lesson.');
  }, 10000);
  return evaluate(`(() => {
    const liveText = document.getElementById('ea-selected-email')?.innerText || '';
    return {
      attempted: true,
      selected: liveText,
      hasPreview: liveText.includes('Would affect'),
      hasError: liveText.includes('Could not preview the lesson.'),
      finalText: ${JSON.stringify(finalText)},
    };
  })()`);
}

async function verifySummaryFilterNavigation() {
  const result = await evaluate(`(() => {
    if (!globalThis.__eaTestHooks || typeof globalThis.__eaTestHooks.selectSummaryFilter !== 'function') {
      return { attempted: false, reason: 'filter-hook-missing' };
    }
    return { attempted: true, action: globalThis.__eaTestHooks.selectSummaryFilter('auto_handled_items') };
  })()`);
  if (!result.attempted) {
    return result;
  }
  await waitFor(async () => {
    const snapshot = await evaluate(`globalThis.__eaTestHooks.getSnapshot()`);
    return snapshot.activeSummaryFilter === "auto_handled_items" && Boolean(snapshot.selectedEmail);
  }, 10000);
  const snapshot = await evaluate(`globalThis.__eaTestHooks.getSnapshot()`);
  const panelText = await evaluate(`document.getElementById('ea-selected-email')?.innerText || ''`);
  return {
    attempted: true,
    ok: snapshot.activeSummaryFilter === "auto_handled_items" && panelText.length > 0,
    activeSummaryFilter: snapshot.activeSummaryFilter,
    selectedMessageId: snapshot.selectedEmail?.message_id || "",
    panelText: panelText.slice(0, 2000),
  };
}

async function verifyDraftPersistence() {
  const result = await evaluate(`(() => {
    if (!globalThis.__eaTestHooks || typeof globalThis.__eaTestHooks.setDraft !== 'function' || typeof globalThis.__eaTestHooks.forceRefresh !== 'function') {
      return { attempted: false, reason: 'draft-hooks-missing' };
    }
    const draft = globalThis.__eaTestHooks.setDraft(
      'personal',
      'Acceptance harness draft should survive a refresh.',
    );
    const refreshed = globalThis.__eaTestHooks.forceRefresh();
    return { attempted: true, draft, refreshed };
  })()`);
  if (!result.attempted) {
    return result;
  }
  await waitFor(async () => {
    const draft = await evaluate(`globalThis.__eaTestHooks.getDraft()`);
    return draft.targetLabel === 'personal' && draft.note === 'Acceptance harness draft should survive a refresh.';
  }, 10000);
  const after = await evaluate(`(() => {
    const draft = globalThis.__eaTestHooks.getDraft();
    return {
      draft,
      domLabel: document.getElementById('ea-target-label')?.value || '',
      domNote: document.getElementById('ea-teach-note')?.value || '',
    };
  })()`);
  const ok =
    after.draft?.targetLabel === "personal" &&
    after.draft?.note === "Acceptance harness draft should survive a refresh." &&
    after.domLabel === "personal" &&
    after.domNote === "Acceptance harness draft should survive a refresh.";
  return {
    attempted: true,
    ok,
    ...after,
  };
}

async function settlePanel(predicate, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastText = "";
  while (Date.now() < deadline) {
    await pumpBridge();
    lastText = await evaluate(`document.getElementById('ea-selected-email')?.innerText || ''`);
    if (await predicate(lastText)) {
      return lastText;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(`Timed out waiting for live Gmail state. Last panel text:\\n${lastText.slice(0, 2000)}`);
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
