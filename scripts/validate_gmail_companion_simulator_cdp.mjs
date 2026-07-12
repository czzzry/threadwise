const appUrl = process.argv[2] || "http://127.0.0.1:8031/simulator";
const cdpBase = process.argv[3] || "http://127.0.0.1:9222";

const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
const uncaughtErrors = [];
let nextId = 1;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") {
    uncaughtErrors.push(message.params.exceptionDetails);
  }
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
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"review\"]') !== null"));

  const review = await decisionSnapshot();
  assertWorkspace(review, "review", "selected-email");
  assertEqual(review.suggestion, "Threadwise suggests Work", "production-shaped suggestion display");
  assertEqual(review.primaryActions.join(","), "Accept Work", "review primary action");
  assertEqual(review.hasDailySummary, false, "selected review excludes Today");
  assertEqual(review.hasUnsubscribeJob, false, "selected review excludes unsubscribe job");

  const autoLabeledTruth = await evaluate(`(() => {
    const original = harnessState.sidebar_state.selected_email;
    harnessState.sidebar_state.selected_email = {
      ...original,
      internal_label: 'job-related',
      classification: 'EA/Work',
      status: 'auto-labeled',
      status_label: 'Auto-labeled',
      details: { ...(original.details || {}), write_status: '', inbox_status: '' }
    };
    renderSelectedPanel();
    const result = {
      heading: document.querySelector('[data-ea-auto-handled-heading]')?.textContent.trim() || '',
      receipt: document.querySelector('[data-ea-auto-handled-receipt]')?.textContent.trim() || ''
    };
    harnessState.sidebar_state.selected_email = original;
    renderSelectedPanel();
    return result;
  })()`);
  assertEqual(autoLabeledTruth.heading, "Work · Auto-labeled", "auto-labeled heading is local-only");
  assertEqual(
    autoLabeledTruth.receipt,
    "Threadwise classified this email and kept it visible. Gmail label not confirmed.",
    "auto-labeled receipt does not claim a Gmail write",
  );

  await installTeachApplyInterceptor();
  await evaluate(`(() => {
    window.__twHoldNextHarnessRefresh = true;
    refreshState();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"loading\"]') !== null"));
  const loading = await decisionSnapshot();
  assertWorkspace(loading, "loading", "selected-email");
  assertEqual(loading.primaryActions.length, 0, "loading has no primary action");
  await evaluate("window.__twReleaseHarnessRefresh?.()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"review\"]') !== null"));

  await evaluate(`(() => {
    const button = document.querySelector('[data-action="accept-suggestion"]');
    button.click();
    applyTeach('current-only');
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"applying\"]') !== null"));
  const accepting = await decisionSnapshot();
  const acceptRequests = await capturedRequests();
  assertWorkspace(accepting, "applying", "selected-email");
  assertEqual(acceptRequests.length, 1, "duplicate Accept is blocked");
  assertEqual(acceptRequests[0].mode, "current-only", "Accept uses current-only");
  assertEqual(acceptRequests[0].target_label, "job-related", "Work suggestion maps to internal job-related id");

  await rejectNextApply("Synthetic transport disconnect. Nothing was stored or changed.");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"blocked\"]') !== null"));
  const blockedApply = await decisionSnapshot();
  assertWorkspace(blockedApply, "blocked", "selected-email");
  assertEqual(blockedApply.primaryActions.join(","), "Try fix again", "failed apply offers retry");

  await evaluate("document.querySelector('[data-action=\"edit-current-change\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"change\"]') !== null"));
  const change = await decisionSnapshot();
  assertWorkspace(change, "change", "selected-email");
  assertEqual(change.selectedLabel, "job-related", "Change selects the internal suggested id");
  assertEqual(change.primaryActions.join(","), "Preview change", "Change primary action");

  await evaluate(`(() => {
    const note = document.querySelector('#sim-teach-note');
    note.value = 'This should be Promotions';
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="preview-current-change"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-label-conflict]') !== null"));
  const conflict = await decisionSnapshot();
  assertEqual(
    conflict.conflict,
    "Your note sounds like Promotions, but Work is selected. Choose which one you mean.",
    "label/note conflict",
  );

  await evaluate(`(() => {
    const note = document.querySelector('#sim-teach-note');
    note.value = "This should be Work, not Personal. These messages may look promotional, but they are formal work updates I need to keep visible. Only use ReplyNeeded if a later message explicitly asks me to act by a deadline.";
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="preview-current-change"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"teach-preview\"]') !== null"));
  const negatedAlternative = await decisionSnapshot();
  assertEqual(negatedAlternative.conflict, "", "negated and conditional categories do not create false conflicts");

  await evaluate(`(() => {
    const select = document.querySelector('#sim-target-label');
    select.value = 'promotions';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    document.querySelector('[data-action="preview-current-change"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"preview\"]') !== null"));
  const preview = await decisionSnapshot();
  assertWorkspace(preview, "preview", "selected-email");
  assertEqual(preview.heading, "Change this email to Promotions", "preview heading");
  assertEqual(preview.effect, "This updates the current email only.", "preview effect");

  await evaluate(`(() => {
    const button = document.querySelector('[data-apply-mode="current-only"]');
    button.click();
    applyTeach('current-only');
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"applying\"]') !== null"));
  const applying = await decisionSnapshot();
  const currentRequests = await capturedRequests();
  assertWorkspace(applying, "applying", "selected-email");
  assertEqual(currentRequests.length, 2, "duplicate Apply is blocked");
  assertEqual(currentRequests[1].mode, "current-only", "changed label uses current-only");
  assertEqual(currentRequests[1].target_label, "promotions", "apply payload uses selected internal Promotions id");

  await resolveNextApply(successPayload({ inboxRemoved: 1, inboxFailed: 0 }));
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"receipt\"]') !== null"));
  const receipt = await receiptSnapshot();
  assertWorkspace(receipt, "receipt", "selected-email");
  assertEqual(receipt.heading, "Changed to Promotions", "success receipt heading");
  assertEqual(receipt.outcomes.join(","), "Gmail label updated.,Removed from Inbox.", "success receipt outcomes");
  assertEqual(receipt.followUps.join(","), "Teach Threadwise for future emails", "future learning follows success");

  await evaluate("document.querySelector('[data-action=\"teach-future-after-receipt\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"future-learning\"]') !== null"));
  const future = await decisionSnapshot();
  assertWorkspace(future, "future-learning", "selected-email");
  assertEqual(future.heading, "Teach future emails", "future-learning heading");
  assertEqual(future.primaryActions.join(","), "Save future rule", "future-learning primary action");
  assertEqual(
    await evaluate("document.querySelector('[data-action=\"back-to-current-receipt\"]')?.textContent.trim()"),
    "Not now",
    "future learning can be declined",
  );
  await evaluate("document.querySelector('[data-action=\"back-to-current-receipt\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"receipt\"]') !== null"));

  const firstMessageId = review.messageId;
  await evaluate("document.querySelector('[data-action=\"open-needs-attention\"]').click()");
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null && (selectedEmail()?.message_id || '') !== ${JSON.stringify(firstMessageId)}`));
  const nextReview = await decisionSnapshot();
  assertWorkspace(nextReview, "review", "selected-email");
  assertNotEqual(nextReview.messageId, firstMessageId, "Next email advances the preserved queue");
  assertEqual(nextReview.hasReceipt, false, "receipt state resets across message changes");

  await moveToPromotionsPreview();
  await evaluate("document.querySelector('[data-apply-mode=\"current-only\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"applying\"]') !== null"));
  await resolveNextApply(successPayload({ inboxRemoved: 0, inboxFailed: 1 }));
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"receipt\"]') !== null"));
  const partial = await receiptSnapshot();
  assertEqual(
    partial.outcomes.join(","),
    "Gmail label updated.,Inbox removal needs attention. Open Activity for details.",
    "partial receipt preserves label success",
  );
  assertEqual(partial.primaryActions.length, 0, "partial receipt does not repeat successful work");
  assertEqual(partial.followUps.length, 0, "partial receipt withholds optional learning");
  assertEqual(partial.hasActivityRoute, true, "partial receipt routes to Activity details");

  await evaluate(`(() => {
    const current = selectedEmail()?.message_id || '';
    const target = (harnessState?.needs_attention_items || []).find((item) => item.message_id && item.message_id !== current);
    if (target) setContextFromItem(target);
    return Boolean(target);
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"review\"]') !== null"));
  const afterPartialChange = await decisionSnapshot();
  assertEqual(afterPartialChange.hasReceipt, false, "partial receipt resets on another email");

  await moveToPromotionsPreview();
  await evaluate("document.querySelector('[data-apply-mode=\"current-only\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"applying\"]') !== null"));
  await resolveNextApply(successPayload({ inboxRemoved: 0, inboxFailed: 0 }));
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"receipt\"]') !== null"));
  await evaluate("document.querySelector('[data-action=\"teach-future-after-receipt\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"future-learning\"]') !== null"));
  const futureRequestCount = (await capturedRequests()).length;
  await evaluate(`(() => {
    const note = document.querySelector('#sim-future-note');
    note.value = 'Use Promotions for future messages from this list.';
    const button = document.querySelector('[data-action="save-future-learning"]');
    button.click();
    applyTeach('save-future-rule');
    return true;
  })()`);
  await waitFor(async () => (await capturedRequests()).at(-1)?.mode === "save-future-rule");
  const futureRequests = await capturedRequests();
  assertEqual(futureRequests.length, futureRequestCount + 1, "duplicate future Save is blocked");
  const futureRequest = futureRequests.at(-1);
  assertEqual(futureRequest.mode, "save-future-rule", "future learning uses no-write save-future-rule mode");
  assertEqual(futureRequest.target_label, "promotions", "future rule preserves the selected internal label");
  await resolveNextApply({
    acknowledgment: "Synthetic future rule saved without Gmail mutation.",
    outcome: {
      state: "future-rule-saved",
      scope: "future-rule",
      current_email_changed_locally: false,
      current_email_written_to_gmail: false,
      matching_existing_changed_locally: 0,
      future_rule_saved: true,
      gmail_write_mode: "no-gmail-write-future-rule-only",
      gmail_label_write_failed: 0,
    },
    gmail_write_through: { messages_written: 0, inbox_removed: 0, inbox_remove_failed: 0 },
  });
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"receipt\"]')?.textContent.includes('Future rule saved for review')"));
  const futureSaved = await decisionSnapshot();
  assertWorkspace(futureSaved, "receipt", "selected-email");
  assertEqual(futureSaved.primaryActions.length, 0, "saved future candidate has no repeated primary action");

  const broadRequestCount = (await capturedRequests()).length;
  await evaluate(`(() => {
    teachPreview = {
      plain_english_rule: 'Use Promotions for matching messages.',
      inbox_backfill: { available: true, requires_confirmation: true, estimated_count: 2 }
    };
    selectedDecisionMode = 'teaching';
    teachFlowState = 'scope-confirmation';
    renderSelectedPanel();
    document.querySelector('[data-apply-mode="apply-included"]').click();
    return true;
  })()`);
  assertEqual((await capturedRequests()).length, broadRequestCount, "broad apply waits for explicit confirmation");
  await evaluate(`(() => {
    const button = document.querySelector('[data-action="confirm-inbox-apply"]');
    button.click();
    applyTeach('apply-included');
    return true;
  })()`);
  await waitFor(async () => (await capturedRequests()).length === broadRequestCount + 1);
  const broadRequest = (await capturedRequests()).at(-1);
  assertEqual(broadRequest.mode, "apply-included", "confirmed broad apply uses apply-included");
  await resolveNextApply({ error: "Synthetic broad apply stopped." });
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"blocked\"]') !== null"));

  await evaluate(`(async () => {
    currentContext = { ...currentContext, selected_at: new Date().toISOString() };
    await refreshState();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"understanding\"]') !== null"));
  const understanding = await decisionSnapshot();
  assertWorkspace(understanding, "understanding", "selected-email");
  assertEqual(understanding.primaryActions.length, 0, "understanding has no primary action");

  await evaluate("document.querySelector('#sim-unsynced').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"blocked\"]') !== null"));
  const snapshotMiss = await decisionSnapshot();
  assertWorkspace(snapshotMiss, "blocked", "selected-email");
  assertEqual(snapshotMiss.primaryActions.join(","), "Return to fixture list", "snapshot miss stays fixture-only");

  await evaluate("document.querySelector('#sim-home').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-workspace-body=\"home\"]') !== null"));
  const home = await decisionSnapshot();
  assertWorkspace(home, "home", "home");
  assertEqual(home.hasSelectedEmail, false, "Home excludes selected email");
  assertEqual(home.hasActivityRoute, true, "Home routes Activity separately");
  assertEqual(home.hasSubscriptionRoute, true, "Home routes subscription cleanup separately");

  const overflow = {};
  for (const width of [360, 390, 420]) {
    await send("Emulation.setDeviceMetricsOverride", {
      width,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    overflow[width] = await evaluate(`(() => {
      const panel = document.querySelector('.panel');
      const workspace = document.querySelector('#sim-workspace');
      return Math.max(
        (panel?.scrollWidth || 0) - (panel?.clientWidth || 0),
        (workspace?.scrollWidth || 0) - (workspace?.clientWidth || 0)
      );
    })()`);
    if (overflow[width] > 1) throw new Error(`Simulator overflowed by ${overflow[width]}px at ${width}px`);
  }

  const result = {
    review,
    autoLabeledTruth,
    loading,
    accepting,
    blockedApply,
    change,
    conflict,
    preview,
    applying,
    receipt,
    future,
    nextReview,
    partial,
    futureRequest,
    futureSaved,
    broadRequest,
    understanding,
    snapshotMiss,
    home,
    overflow,
    analyticsHooksPresent: Boolean(await evaluate("globalThis.ThreadwiseAnalytics")),
    uncaughtErrorCount: uncaughtErrors.length,
  };
  console.log(JSON.stringify(result, null, 2));
  if (uncaughtErrors.length) {
    throw new Error(`Simulator emitted ${uncaughtErrors.length} uncaught runtime error(s)`);
  }
  assertEqual(await evaluate("(window.__twProhibitedRequests || []).length"), 0, "simulator never requests live Gmail sync");
} finally {
  socket.close();
  await fetch(`${cdpBase}/json/close/${target.id}`).catch(() => {});
}

async function moveToPromotionsPreview() {
  await evaluate("document.querySelector('[data-action=\"change-suggestion\"]').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"change\"]') !== null"));
  await evaluate(`(() => {
    const select = document.querySelector('#sim-target-label');
    select.value = 'promotions';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    const note = document.querySelector('#sim-teach-note');
    note.value = '';
    note.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector('[data-action="preview-current-change"]').click();
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=\"preview\"]') !== null"));
}

function successPayload({ inboxRemoved, inboxFailed }) {
  return {
    acknowledgment: "Synthetic current-email outcome.",
    outcome: {
      state: "changed",
      scope: "current-email",
      current_email_changed_locally: true,
      current_email_written_to_gmail: true,
      matching_existing_changed_locally: 0,
      future_rule_saved: false,
      gmail_write_mode: inboxFailed ? "partial" : "applied",
      gmail_label_write_failed: 0,
    },
    gmail_write_through: {
      messages_written: 1,
      inbox_removed: inboxRemoved,
      inbox_remove_failed: inboxFailed,
    },
  };
}

async function installTeachApplyInterceptor() {
  await evaluate(`(() => {
    window.__twOriginalFetch = window.fetch.bind(window);
    window.__twCapturedRequests = [];
    window.__twPendingResponses = [];
    window.__twProhibitedRequests = [];
    window.fetch = (input, init = {}) => {
      const url = String(input || '');
      if (url.includes('/api/gmail-check-run')) {
        window.__twProhibitedRequests.push(url);
        return Promise.reject(new Error('Simulator attempted a prohibited Gmail sync request.'));
      }
      if (url.includes('/api/harness-state') && window.__twHoldNextHarnessRefresh) {
        window.__twHoldNextHarnessRefresh = false;
        return new Promise((resolve) => {
          window.__twReleaseHarnessRefresh = () => {
            window.__twReleaseHarnessRefresh = null;
            window.__twOriginalFetch(input, init).then(resolve);
          };
        });
      }
      if (!url.includes('/api/teach-apply')) return window.__twOriginalFetch(input, init);
      let body = {};
      try { body = JSON.parse(init.body || '{}'); } catch (_error) { body = {}; }
      window.__twCapturedRequests.push(body);
      return new Promise((resolve, reject) => {
        window.__twPendingResponses.push({
          resolve: (payload) => resolve(new Response(JSON.stringify(payload), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          })),
          reject,
        });
      });
    };
    return true;
  })()`);
}

async function capturedRequests() {
  return evaluate("window.__twCapturedRequests || []");
}

async function resolveNextApply(payload) {
  const resolved = await evaluate(`(() => {
    const pending = (window.__twPendingResponses || []).shift();
    if (!pending) return false;
    pending.resolve(${JSON.stringify(payload)});
    return true;
  })()`);
  if (!resolved) throw new Error("No intercepted teach-apply request was pending");
}

async function rejectNextApply(message) {
  const rejected = await evaluate(`(() => {
    const pending = (window.__twPendingResponses || []).shift();
    if (!pending) return false;
    pending.reject(new Error(${JSON.stringify(message)}));
    return true;
  })()`);
  if (!rejected) throw new Error("No intercepted teach-apply request was pending");
}

async function decisionSnapshot() {
  return evaluate(`(() => {
    const workspace = document.querySelector('#sim-workspace');
    const state = workspace?.querySelector('[data-ea-selected-state]');
    const visiblePrimaries = [...(workspace?.querySelectorAll('[data-tw-primary-action]') || [])]
      .filter((node) => getComputedStyle(node).display !== 'none' && getComputedStyle(node).visibility !== 'hidden');
    return {
      mode: workspace?.dataset.eaWorkspaceMode || '',
      bodyCount: workspace?.querySelectorAll(':scope > [data-ea-workspace-body]').length || 0,
      state: state?.dataset.eaSelectedState || workspace?.dataset.eaSelectedState || '',
      messageId: selectedEmail()?.message_id || '',
      suggestion: state?.querySelector('[data-ea-review-suggestion]')?.textContent?.trim() || '',
      heading: state?.querySelector('[data-ea-preview-heading]')?.textContent?.trim() || '',
      effect: state?.querySelector('[data-ea-preview-effect]')?.textContent?.trim() || '',
      conflict: state?.querySelector('[data-ea-label-conflict]')?.textContent?.trim() || '',
      selectedLabel: state?.querySelector('#sim-target-label')?.value || '',
      primaryActions: visiblePrimaries.map((node) => node.textContent.trim()),
      hasDailySummary: !!workspace?.querySelector('#sim-daily-summary'),
      hasUnsubscribeJob: !!workspace?.querySelector('[data-action="select-unsubscribe"], a[href^="/unsubscribe-review"]'),
      hasSelectedEmail: !!workspace?.querySelector('#sim-selected-email'),
      hasReceipt: !!workspace?.querySelector('[data-ea-selected-state="receipt"]'),
      hasActivityRoute: !!workspace?.querySelector('a[href="/daily-dashboard"]'),
      hasSubscriptionRoute: !!workspace?.querySelector('a[href="/unsubscribe-review"]'),
    };
  })()`);
}

async function receiptSnapshot() {
  const base = await decisionSnapshot();
  const details = await evaluate(`(() => {
    const state = document.querySelector('[data-ea-selected-state="receipt"]');
    return {
      heading: state?.querySelector('[data-ea-receipt-heading]')?.textContent?.trim() || '',
      outcomes: [...(state?.querySelectorAll('[data-ea-receipt-outcome]') || [])].map((node) => node.textContent.trim()),
      followUps: [...(state?.querySelectorAll('[data-action="teach-future-after-receipt"]') || [])].map((node) => node.textContent.trim()),
    };
  })()`);
  return { ...base, ...details };
}

function assertWorkspace(snapshot, expectedState, expectedMode) {
  assertEqual(snapshot.bodyCount, 1, `${expectedState} has one workspace body`);
  assertEqual(snapshot.mode, expectedMode, `${expectedState} workspace mode`);
  assertEqual(snapshot.state, expectedState, `${expectedState} state marker`);
  if (snapshot.primaryActions.length > 1) {
    throw new Error(`${expectedState} exposed ${snapshot.primaryActions.length} primary actions`);
  }
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

function assertNotEqual(actual, unexpected, label) {
  if (actual === unexpected) {
    throw new Error(`${label}: did not expect ${JSON.stringify(unexpected)}`);
  }
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
  const result = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(
      result.exceptionDetails.exception?.description ||
      result.exceptionDetails.exception?.value ||
      result.exceptionDetails.text ||
      "Evaluation failed",
    );
  }
  return result.result.value;
}

async function waitFor(fn, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const pageState = await evaluate("document.body.innerText.slice(0, 2000)").catch(() => "<unavailable>");
  throw new Error(`Timed out waiting for browser state. Snapshot:\n${pageState}`);
}
