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
    window.__responseMode = 'error';
    window.isVisible = (node) => {
      if (!node) return false;
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    };
    window.__workspaceState = {
      selected_context: { provider: 'gmail', message_id: 'synthetic-1', subject: 'Synthetic review email', sender: 'fixture@example.invalid' },
      selected_email: {
        found: true,
        message_id: "synthetic-1",
        subject: "Synthetic review email",
        sender: "fixture@example.invalid",
        internal_label: null,
        suggested_label: "job-related",
        classification: "Uncategorized",
        status: "needs-attention",
        status_label: "Needs attention",
        reason: "Synthetic acceptance fixture",
        details: {}
      },
      daily_summary: { processed_count: 12, auto_handled_count: 2, kept_visible_count: 7, needs_attention_count: 2 },
      ui_state: { allowed_labels: [
        { id: "job-related", name: "EA/Work" },
        { id: "promotions", name: "EA/Promotions" },
        { id: "newsletter", name: "EA/Newsletter" }
      ] }
    };
    window.__nextReview = {
      found: true,
      message_id: 'synthetic-2',
      subject: 'Second review email',
      sender: 'second@example.invalid',
      internal_label: null,
      suggested_label: 'promotions',
      classification: 'Uncategorized',
      status: 'needs-attention',
      status_label: 'Needs attention',
      reason: 'Synthetic second fixture',
      details: {}
    };
    window.__harnessState = {
      sidebar_state: window.__workspaceState,
      needs_attention_items: [
        { message_id: 'synthetic-1', subject: 'Synthetic review email', sender: 'fixture@example.invalid', status: 'needs-attention' },
        { message_id: 'synthetic-2', subject: 'Second review email', sender: 'second@example.invalid', status: 'needs-attention' }
      ],
      recent_items: [], auto_handled_items: [], kept_visible_items: []
    };
    window.__applyRequests = [];
    window.__applyCallbacks = [];
    window.__analyticsCalls = [];
    window.ThreadwiseAnalytics = {
      openExtension: () => window.__analyticsCalls.push({ type: 'open' }),
      openReviewQueue: (size) => window.__analyticsCalls.push({ type: 'queue', size }),
      startEmailReview: (id, origin, size) => window.__analyticsCalls.push({ type: 'start', id, origin, size }),
      decideSuggestion: (decision) => window.__analyticsCalls.push({ type: 'decision', decision }),
      confirmRule: (scope, affected, dryRun) => window.__analyticsCalls.push({ type: 'confirm', scope, affected, dryRun }),
      completeReviewBatch: (count) => window.__analyticsCalls.push({ type: 'complete', count })
    };
    const listeners = [];
    window.chrome = { runtime: {
      lastError: null,
      getURL: (value) => value,
      onMessage: { addListener: (listener) => listeners.push(listener), removeListener: () => undefined },
      sendMessage: (message, callback) => {
        if (message?.path === '/api/teach-apply') {
          window.__applyRequests.push(structuredClone(message.body));
          window.__applyCallbacks.push(callback);
          return;
        }
        if (window.__responseMode === 'error') {
          callback({
            ok: false,
            error: 'Synthetic helper outage.',
            connection_state: { kind: 'helper-unreachable', label: 'Offline', details: 'Synthetic helper outage.' }
          });
          return;
        }
        if (message?.type === 'email-agent:get-state' && message?.context?.message_id === 'synthetic-2') {
          const sidebar = {
            ...window.__workspaceState,
            selected_context: { provider: 'gmail', message_id: 'synthetic-2', subject: 'Second review email', sender: 'second@example.invalid' },
            selected_email: window.__nextReview
          };
          window.__workspaceState = sidebar;
          window.__harnessState = { ...window.__harnessState, sidebar_state: sidebar };
        }
        callback({ ok: true, payload: window.__harnessState });
      }
    }};
    return true;
  })()`);
  await evaluate(contentScript);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-workspace-body="error"]') !== null`));
  await evaluate(`document.querySelector('#ea-brand-toggle').click()`);
  await waitFor(() => evaluate(`isVisible(document.querySelector('[data-ea-workspace-body="error"]'))`));
  const initialError = await workspaceSnapshot();
  await evaluate(`window.__responseMode = 'state'; document.querySelector('[data-ea-action="force-refresh"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-workspace-body="review"]') !== null`));
  const selected = await workspaceSnapshot();
  const review = await decisionSnapshot();
  const reviewWidthAudits = await captureWidthAudits("review");
  await evaluate(`document.querySelector('[data-ea-action="change-suggestion"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  const change = await decisionSnapshot();
  const changeWidthAudits = await captureWidthAudits("change");
  await evaluate(`document.querySelector('#ea-teach-note').value = 'This is promotions'; document.querySelector('[data-ea-action="preview-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-label-conflict]') !== null`));
  const conflict = await decisionSnapshot();
  await evaluate(`document.querySelector('#ea-target-label').value = 'promotions'; document.querySelector('#ea-target-label').dispatchEvent(new Event('change', { bubbles: true })); document.querySelector('[data-ea-action="preview-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="preview"]') !== null`));
  const preview = await decisionSnapshot();
  const previewWidthAudits = await captureWidthAudits("preview");
  await evaluate(`document.querySelector('[data-ea-action="edit-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  const changeAfterEdit = await decisionSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="cancel-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null`));
  const reviewAfterCancel = await decisionSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="change-suggestion"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  await evaluate(`document.querySelector('[data-ea-action="cancel-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null`));
  const initialMessageId = await evaluate(`window.__workspaceState.selected_email.message_id`);
  await evaluate(`(() => {
    const button = document.querySelector('[data-ea-action="accept-suggestion"]');
    button.click();
    button.click();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  const applying = await decisionSnapshot();
  const applyingWidthAudits = await captureWidthAudits("applying");
  const teachApplyRequestCount = await evaluate(`window.__applyRequests.length`);
  const acceptRequest = await evaluate(`window.__applyRequests[0]`);
  const acceptAnalytics = await evaluate(`window.__analyticsCalls.filter((item) => item.type === 'decision' && item.decision === 'approve').length`);
  const editAnalytics = await evaluate(`window.__analyticsCalls.filter((item) => item.type === 'decision' && item.decision === 'edit').length`);
  await evaluate(`window.__applyCallbacks.shift()?.({ ok: false, error: 'Synthetic current apply failure.' })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="current-apply-error"]') !== null`));
  const currentApplyError = await decisionSnapshot();
  const currentApplyErrorWidthAudits = await captureWidthAudits("current-apply-error");
  await evaluate(`document.querySelector('[data-ea-action="retry-current-apply"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  const currentApplyRetryRequestCount = await evaluate(`window.__applyRequests.length`);
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Synthetic current-email change applied.',
      outcome: {
        state: 'changed',
        scope: 'current-email',
        current_email_changed_locally: true,
        current_email_written_to_gmail: true,
        matching_existing_changed_locally: 0,
        future_rule_saved: false,
        gmail_write_mode: 'applied',
        gmail_label_write_failed: 0
      },
      gmail_write_through: { messages_written: 1, inbox_removed: 1, inbox_remove_failed: 0 },
      sidebar_state: window.__workspaceState
    }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="receipt"]') !== null`));
  const receipt = await receiptSnapshot();
  const receiptWidthAudits = await captureWidthAudits("receipt");
  await evaluate(`document.querySelector('[data-ea-action="teach-future-after-receipt"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="future-learning"]') !== null`));
  const futureLearning = await decisionSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="back-to-current-receipt"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="receipt"]') !== null`));
  const receiptAfterFutureLearning = await receiptSnapshot();

  await evaluate(`document.querySelector('[data-ea-action="open-needs-attention"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]')?.textContent.includes('Second review email')`));
  const nextEmail = await decisionSnapshot();
  const nextEmailSubject = await evaluate(`document.querySelector('[data-ea-selected-state="review"]')?.textContent.includes('Second review email') || false`);
  const nextEmailMessageId = await evaluate(`window.__workspaceState.selected_email.message_id`);

  await evaluate(`document.querySelector('[data-ea-action="change-suggestion"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  await evaluate(`document.querySelector('#ea-target-label').value = 'promotions'; document.querySelector('#ea-target-label').dispatchEvent(new Event('change', { bubbles: true })); document.querySelector('#ea-teach-note').value = 'Treat recurring offers as promotions'; document.querySelector('[data-ea-action="preview-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="preview"]') !== null`));
  await evaluate(`document.querySelector('[data-ea-apply="current-only"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Synthetic second change applied.',
      outcome: {
        state: 'changed', scope: 'current-email', current_email_changed_locally: true,
        current_email_written_to_gmail: true, matching_existing_changed_locally: 0,
        future_rule_saved: false, gmail_write_mode: 'applied', gmail_label_write_failed: 0
      },
      gmail_write_through: { messages_written: 1, inbox_removed: 0, inbox_remove_failed: 0 },
      sidebar_state: window.__workspaceState
    }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="receipt"]') !== null`));
  await evaluate(`document.querySelector('[data-ea-action="teach-future-after-receipt"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="future-learning"]') !== null`));
  await evaluate(`document.querySelector('#ea-future-note').value = 'Treat recurring offer emails as promotions'; document.querySelector('#ea-future-note').dispatchEvent(new Event('input', { bubbles: true })); document.querySelector('[data-ea-action="save-future-rule"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="future-learning-applying"]') !== null`));
  const futureRequest = await evaluate(`window.__applyRequests.at(-1)`);
  const futureConfirmAnalytics = await evaluate(`window.__analyticsCalls.filter((item) => item.type === 'confirm' && item.scope === 'future_email').at(-1)`);
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Future rule saved.',
      outcome: {
        state: 'future-rule-saved', scope: 'future-rule', current_email_changed_locally: false,
        current_email_written_to_gmail: false, matching_existing_changed_locally: 0,
        future_rule_saved: true, gmail_write_mode: 'no-gmail-write-future-rule-only', gmail_label_write_failed: 0
      },
      gmail_write_through: { messages_written: 0, inbox_removed: 0, inbox_remove_failed: 0, mode: 'no-gmail-write-future-rule-only' },
      sidebar_state: window.__workspaceState
    }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="future-learning-receipt"]') !== null`));
  const futureReceipt = await receiptSnapshot('future-learning-receipt');

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-partial-1', subject: 'Partial review email', sender: 'partial@example.invalid' },
      selected_email: {
        ...window.__nextReview,
        message_id: 'synthetic-partial-1', subject: 'Partial review email', sender: 'partial@example.invalid', suggested_label: 'job-related'
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.returnToLive();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null`));
  const staleStateReset = await evaluate(`window.__eaTestHooks.getDraft()`);
  await evaluate(`document.querySelector('[data-ea-action="change-suggestion"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  await evaluate(`document.querySelector('#ea-target-label').value = 'promotions'; document.querySelector('#ea-target-label').dispatchEvent(new Event('change', { bubbles: true })); document.querySelector('[data-ea-action="preview-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="preview"]') !== null`));
  await evaluate(`document.querySelector('[data-ea-apply="current-only"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  const partialEditAnalytics = await evaluate(`window.__analyticsCalls.filter((item) => item.type === 'decision' && item.decision === 'edit').length`);
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Synthetic label applied with Inbox cleanup pending.',
      outcome: {
        state: 'changed', scope: 'current-email', current_email_changed_locally: true,
        current_email_written_to_gmail: true, matching_existing_changed_locally: 0,
        future_rule_saved: false, gmail_write_mode: 'partial', gmail_label_write_failed: 0
      },
      gmail_write_through: { messages_written: 1, inbox_removed: 0, inbox_remove_failed: 1 },
      sidebar_state: window.__workspaceState
    }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="receipt"]') !== null`));
  const partialReceipt = await receiptSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-label-failed', subject: 'Label write failed email', sender: 'label-failed@example.invalid' },
      selected_email: {
        ...window.__nextReview,
        message_id: 'synthetic-label-failed', subject: 'Label write failed email', sender: 'label-failed@example.invalid', suggested_label: 'promotions'
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.returnToLive();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null`));
  await evaluate(`(() => {
    const button = document.querySelector('[data-ea-action="accept-suggestion"]');
    button.click();
    button.click();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Saved locally; Gmail label write failed.',
      outcome: {
        state: 'changed-locally', scope: 'current-email', current_email_changed_locally: true,
        current_email_written_to_gmail: false, matching_existing_changed_locally: 0,
        future_rule_saved: false, gmail_write_mode: 'partial', gmail_label_write_failed: 1
      },
      gmail_write_through: { messages_written: 0, label_write_failed: 1, inbox_removed: 0, inbox_remove_failed: 0 },
      sidebar_state: window.__workspaceState
    }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="receipt"]') !== null`));
  const labelFailureReceipt = await receiptSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-auto-1', subject: 'Synthetic handled email', sender: 'fixture@example.invalid' },
      selected_email: {
        found: true,
        message_id: "synthetic-auto-1",
        subject: "Synthetic handled email",
        sender: "fixture@example.invalid",
        internal_label: "newsletter",
        suggested_label: "newsletter",
        classification: "EA/Newsletter",
        status: "auto-handled",
        status_label: "Auto-handled",
        reason: "Matched the newsletter signals.",
        details: { write_status: "applied", inbox_status: "applied" }
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
    return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]') !== null`));
  const autoHandled = await autoHandledSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="toggle-details"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('#ea-selected-email-secondary')?.textContent.includes('Matched the newsletter signals.')`));
  const autoHandledWhy = await evaluate(`document.querySelector('#ea-selected-email-secondary')?.textContent.trim() || ''`);
  const autoHandledDecisionCountBefore = await evaluate(`window.__analyticsCalls.filter((item) => item.type === 'decision').length`);
  await evaluate(`document.querySelector('[data-ea-action="change-auto-handled"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="change"]') !== null`));
  const autoHandledChangeOpened = await decisionSnapshot();
  await evaluate(`document.querySelector('[data-ea-action="preview-current-change"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="preview"]') !== null`));
  await evaluate(`document.querySelector('[data-ea-apply="current-only"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  const autoHandledSuggestionAnalytics = await evaluate(`window.__analyticsCalls.filter((item) => item.type === 'decision').length - ${autoHandledDecisionCountBefore}`);
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Synthetic handled correction applied.',
      outcome: {
        state: 'changed', scope: 'current-email', current_email_changed_locally: true,
        current_email_written_to_gmail: true, matching_existing_changed_locally: 0,
        future_rule_saved: false, gmail_write_mode: 'applied', gmail_label_write_failed: 0
      },
      gmail_write_through: { messages_written: 1, inbox_removed: 0, inbox_remove_failed: 0 },
      sidebar_state: window.__workspaceState
    }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="receipt"]') !== null`));

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-auto-unconfirmed', subject: 'Synthetic unconfirmed handled email', sender: 'unconfirmed@example.invalid' },
      selected_email: {
        ...window.__workspaceState.selected_email,
        message_id: 'synthetic-auto-unconfirmed', subject: 'Synthetic unconfirmed handled email', sender: 'unconfirmed@example.invalid',
        status: 'auto-handled', status_label: 'Auto-handled', details: { write_status: 'skipped', inbox_status: 'applied' }
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]') !== null`));
  const autoHandledUnconfirmed = await autoHandledSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-kept-1', subject: 'Synthetic kept email', sender: 'kept@example.invalid' },
      selected_email: {
        ...window.__workspaceState.selected_email,
        message_id: "synthetic-kept-1",
        subject: "Synthetic kept email",
        status: "kept-visible",
        status_label: "Kept visible",
        details: { write_status: "applied", inbox_status: "skipped" }
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
    return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]') !== null`));
  const keptVisible = await autoHandledSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-labeled-1', subject: 'Synthetic labeled email', sender: 'labeled@example.invalid' },
      selected_email: {
        ...window.__workspaceState.selected_email,
        message_id: 'synthetic-labeled-1', subject: 'Synthetic labeled email', status: 'auto-labeled', status_label: 'Auto-labeled',
        details: { write_status: 'applied', inbox_status: '' }
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="handled-receipt"]') !== null`));
  const autoLabeled = await autoHandledSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-failed-1', subject: 'Synthetic failed email', sender: 'failed@example.invalid' },
      selected_email: {
        ...window.__workspaceState.selected_email,
        message_id: 'synthetic-failed-1', subject: 'Synthetic failed email', status: 'kept-visible', status_label: 'Kept visible',
        details: { write_status: 'applied', inbox_status: 'failed' }
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="blocked"]') !== null`));
  const failedHandling = await decisionSnapshot();

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: { provider: 'gmail', message_id: 'synthetic-no-suggestion', subject: 'No suggestion email', sender: 'none@example.invalid' },
      selected_email: {
        ...window.__nextReview,
        message_id: 'synthetic-no-suggestion', subject: 'No suggestion email', sender: 'none@example.invalid',
        suggested_label: null, internal_label: null, classification: 'Uncategorized'
      }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="review"]') !== null`));
  const noSuggestion = await decisionSnapshot();
  const noSuggestionHasAccept = await evaluate(`!!document.querySelector('[data-ea-action="accept-suggestion"]')`);

  await evaluate(`window.__eaTestHooks.setDraft('promotions', 'Guard broader apply'); window.__eaTestHooks.showTeachScope({
    plain_english_rule: 'Treat matching offer emails as Promotions',
    selected_label_after: ['promotions'],
    impact: { matching_existing_count: 2 },
    inbox_backfill: { available: true, estimated_count: 2, requires_confirmation: true }
  })`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="teach-scope"] [data-ea-apply="apply-included"]') !== null`));
  const broadOptionVisible = await evaluate(`isVisible(document.querySelector('[data-ea-apply="apply-included"]'))`);
  const applyCountBeforeGuard = await evaluate(`window.__applyRequests.length`);
  await evaluate(`document.querySelector('[data-ea-apply="apply-included"]').click()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-action="confirm-inbox-apply"]') !== null`));
  const broadConfirmationVisible = await evaluate(`isVisible(document.querySelector('[data-ea-action="confirm-inbox-apply"]'))`);
  await evaluate(`(() => {
    const button = document.querySelector('[data-ea-action="confirm-inbox-apply"]');
    button.click();
    button.click();
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-selected-state="applying"]') !== null`));
  const applyIncludedGuardCount = await evaluate(`window.__applyRequests.length - ${applyCountBeforeGuard}`);
  const applyIncludedRequest = await evaluate(`window.__applyRequests.at(-1)`);
  await evaluate(`window.__applyCallbacks.shift()?.({
    ok: true,
    payload: {
      acknowledgment: 'Included apply complete.',
      outcome: {
        state: 'changed', scope: 'included-existing', current_email_changed_locally: true,
        current_email_written_to_gmail: true, matching_existing_changed_locally: 0,
        future_rule_saved: true, gmail_write_mode: 'applied', gmail_label_write_failed: 0
      },
      gmail_write_through: { messages_written: 1, inbox_removed: 0, inbox_remove_failed: 0 },
      sidebar_state: window.__workspaceState
    }
  })`);

  await evaluate(`(() => {
    window.__workspaceState = {
      ...window.__workspaceState,
      selected_context: {},
      selected_email: { found: false, status: 'idle' },
      daily_summary: { processed_count: 12, auto_handled_count: 2, kept_visible_count: 7 }
    };
    window.__harnessState = { ...window.__harnessState, sidebar_state: window.__workspaceState };
    window.__eaTestHooks.forceRefresh();
    return true;
  })()`);
  await waitFor(() => evaluate(`document.querySelector('[data-ea-workspace-body="home"]') !== null`));
  const home = await workspaceSnapshot();
  const widthAudits = [...reviewWidthAudits, ...changeWidthAudits, ...previewWidthAudits, ...applyingWidthAudits, ...currentApplyErrorWidthAudits, ...receiptWidthAudits];

  const result = { initialError, selected, review, change, conflict, preview, applying, currentApplyError, receipt, futureLearning, receiptAfterFutureLearning, initialMessageId, nextEmail, nextEmailSubject, nextEmailMessageId, futureReceipt, partialReceipt, partialEditAnalytics, labelFailureReceipt, teachApplyRequestCount, currentApplyRetryRequestCount, acceptRequest, acceptAnalytics, editAnalytics, futureRequest, futureConfirmAnalytics, staleStateReset, changeAfterEdit, reviewAfterCancel, autoHandled, autoHandledWhy, autoHandledChangeOpened, autoHandledSuggestionAnalytics, autoHandledUnconfirmed, keptVisible, autoLabeled, failedHandling, noSuggestion, noSuggestionHasAccept, broadOptionVisible, broadConfirmationVisible, applyIncludedGuardCount, applyIncludedRequest, home, widthAudits, uncaughtErrorCount: uncaughtErrors.length };
  console.log(JSON.stringify(result, null, 2));
  if (
    initialError.bodyCount !== 1 || initialError.mode !== "error" || !initialError.visible ||
    selected.bodyCount !== 1 || selected.mode !== "review" || selected.hasHome || selected.hasDailySummary ||
    review.state !== "review" || review.primaryActions.join(",") !== "Accept Work" ||
    review.suggestion !== "Threadwise suggests Work" || review.hasLabelPicker || review.hasNote ||
    change.state !== "change" || change.primaryActions.join(",") !== "Preview change" ||
    change.selectedLabel !== "job-related" || !change.hasLabelPicker || !change.hasNote ||
    conflict.state !== "change" || conflict.selectedLabel !== "job-related" ||
    conflict.conflict !== "Your note sounds like Promotions, but Work is selected. Choose which one you mean." ||
    preview.state !== "preview" || preview.primaryActions.join(",") !== "Apply change" ||
    preview.heading !== "Change this email to Promotions" || preview.effect !== "This updates the current email only." ||
    preview.hasLabelPicker || preview.hasNote ||
    applying.state !== "applying" || applying.primaryActions.length !== 0 ||
    applying.heading !== "Applying Work" || applying.effect !== "Updating the current email only…" ||
    applying.hasLabelPicker || applying.hasNote || teachApplyRequestCount !== 1 ||
    currentApplyError.state !== "current-apply-error" || currentApplyError.heading !== "Couldn’t apply Work" ||
    currentApplyError.primaryActions.join(",") !== "Retry" || currentApplyError.actions.join(",") !== "Retry,Edit" ||
    !currentApplyError.effect.includes("Threadwise did not confirm that the change completed.") || currentApplyRetryRequestCount !== 2 ||
    acceptRequest?.mode !== "current-only" || acceptRequest?.target_label !== "job-related" || acceptRequest?.note !== "" || acceptRequest?.scope !== "sender" ||
    acceptAnalytics !== 1 || editAnalytics !== 0 ||
    receipt.state !== "receipt" || receipt.heading !== "Changed to Work" ||
    receipt.outcomes.join(",") !== "Gmail label updated.,Removed from Inbox." ||
    receipt.primaryActions.join(",") !== "Next email" || receipt.hasLabelPicker || receipt.hasNote ||
    receipt.followUps.join(",") !== "Teach Threadwise for future emails" ||
    futureLearning.state !== "future-learning" || futureLearning.primaryActions.join(",") !== "Save future rule" ||
    futureLearning.heading !== "Teach future emails" || !futureLearning.hasFutureNote ||
    receiptAfterFutureLearning.followUps.join(",") !== "Teach Threadwise for future emails" ||
    !nextEmailSubject || nextEmail.state !== "review" || nextEmail.suggestion !== "Threadwise suggests Promotions" ||
    initialMessageId !== "synthetic-1" || nextEmailMessageId !== "synthetic-2" || nextEmailMessageId === initialMessageId ||
    futureRequest?.mode !== "save-future-rule" || futureRequest?.target_label !== "promotions" ||
    futureRequest?.note !== "Treat recurring offer emails as promotions" || futureRequest?.scope !== "sender" ||
    futureConfirmAnalytics?.scope !== "future_email" || futureConfirmAnalytics?.affected !== 0 ||
    futureReceipt.state !== "future-learning-receipt" || futureReceipt.heading !== "Future rule saved" ||
    futureReceipt.outcomes.join(",") !== "Threadwise saved the lesson for future emails. No Gmail message was changed." ||
    partialReceipt.state !== "receipt" || partialReceipt.heading !== "Changed to Promotions" ||
    partialReceipt.outcomes.join(",") !== "Gmail label updated.,Couldn’t remove from Inbox. Open Activity to review the failed step." ||
    partialReceipt.primaryActions.length !== 0 || partialReceipt.followUps.length !== 0 || partialReceipt.hasLabelPicker || partialReceipt.hasNote ||
    partialEditAnalytics !== 1 ||
    labelFailureReceipt.state !== "receipt" || labelFailureReceipt.heading !== "Saved locally as Promotions" ||
    labelFailureReceipt.outcomes.join(",") !== "Saved locally in Threadwise.,Gmail label not confirmed. Open Activity to review recovery." ||
    labelFailureReceipt.primaryActions.length !== 0 || labelFailureReceipt.followUps.length !== 0 || labelFailureReceipt.activityLinks.join(",") !== "Open Activity" ||
    staleStateReset.targetLabel !== "" || staleStateReset.note !== "" ||
    changeAfterEdit.state !== "change" || changeAfterEdit.selectedLabel !== "promotions" ||
    reviewAfterCancel.state !== "review" || reviewAfterCancel.primaryActions.length !== 1 ||
    autoHandled.heading !== "Newsletter · Auto-handled" ||
    autoHandled.receipt !== "Threadwise applied the Newsletter Gmail label and removed this email from Inbox." ||
    autoHandled.hasCorrectionForm || autoHandled.actions.join(",") !== "Change,Why" ||
    !autoHandledWhy.includes("Matched the newsletter signals.") || autoHandledChangeOpened.state !== "change" || autoHandledChangeOpened.selectedLabel !== "newsletter" ||
    autoHandledSuggestionAnalytics !== 0 ||
    autoHandledUnconfirmed.heading !== "Newsletter · Auto-handled" || autoHandledUnconfirmed.receipt !== "Threadwise classified this email as Newsletter and kept it visible. Gmail label write is not confirmed." ||
    keptVisible.heading !== "Newsletter · Kept visible" || keptVisible.receipt !== "Threadwise applied the Newsletter Gmail label and kept this email in Inbox." ||
    autoLabeled.heading !== "Newsletter · Auto-labeled" || autoLabeled.receipt !== "Threadwise classified this email as Newsletter and kept it visible. Gmail label write is not confirmed." ||
    failedHandling.state !== "blocked" || noSuggestionHasAccept || noSuggestion.primaryActions.join(",") !== "Change label" ||
    !broadOptionVisible || !broadConfirmationVisible || applyIncludedGuardCount !== 1 || applyIncludedRequest?.mode !== "apply-included" ||
    home.bodyCount !== 1 || home.mode !== "home" || home.hasSelectedEmail || !home.hasDailySummary ||
    widthAudits.length !== 18 || [...new Set(widthAudits.map((audit) => audit.state))].sort().join(",") !== "applying,change,current-apply-error,preview,receipt,review" ||
    widthAudits.some((audit) => audit.visibleBodyCount !== 1 || audit.visiblePrimaryCount > 1 || audit.horizontalOverflow > 1 || audit.rootRightOverflow > 1) ||
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
      hasNote: !!state?.querySelector('#ea-teach-note'),
      heading: state?.querySelector('[data-ea-preview-heading]')?.textContent?.trim() || '',
      effect: state?.querySelector('[data-ea-preview-effect]')?.textContent?.trim() || '',
      conflict: state?.querySelector('[data-ea-label-conflict]')?.textContent?.trim() || '',
      hasFutureNote: !!state?.querySelector('#ea-future-note'),
      actions: [...(state?.querySelectorAll('button') || [])].map((node) => node.textContent.trim()),
      followUps: [...(state?.querySelectorAll('[data-ea-action="teach-future-after-receipt"]') || [])].map((node) => node.textContent.trim())
    };
  })()`);
}

async function autoHandledSnapshot() {
  return evaluate(`(() => {
    const state = document.querySelector('[data-ea-selected-state="handled-receipt"]');
    return {
      heading: state?.querySelector('[data-ea-auto-handled-heading]')?.textContent?.trim() || '',
      receipt: state?.querySelector('[data-ea-auto-handled-receipt]')?.textContent?.trim() || '',
      hasCorrectionForm: !!document.querySelector('#ea-teach-note, #ea-target-label'),
      actions: [...(state?.querySelectorAll('button') || [])].map((node) => node.textContent.trim())
    };
  })()`);
}

async function receiptSnapshot(stateName = "receipt") {
  return evaluate(`(() => {
    const state = document.querySelector('[data-ea-selected-state="${stateName}"]');
    return {
      state: state?.dataset.eaSelectedState || '',
      heading: state?.querySelector('[data-ea-receipt-heading]')?.textContent?.trim() || '',
      outcomes: [...(state?.querySelectorAll('[data-ea-receipt-outcome]') || [])].map((node) => node.textContent.trim()),
      primaryActions: [...(state?.querySelectorAll('[data-tw-primary-action]') || [])].map((node) => node.textContent.trim()),
      followUps: [...(state?.querySelectorAll('[data-ea-action="teach-future-after-receipt"]') || [])].map((node) => node.textContent.trim()),
      activityLinks: [...(state?.querySelectorAll('a') || [])].map((node) => node.textContent.trim()),
      hasLabelPicker: !!state?.querySelector('#ea-target-label'),
      hasNote: !!state?.querySelector('#ea-teach-note')
    };
  })()`);
}

async function workspaceSnapshot() {
  return evaluate(`(() => {
    const workspace = document.querySelector('#ea-workspace');
    const body = workspace?.querySelector(':scope > [data-ea-workspace-body]');
    return {
      mode: workspace?.dataset.eaWorkspaceMode || '',
      bodyCount: workspace?.querySelectorAll(':scope > [data-ea-workspace-body]').length || 0,
      visible: isVisible(body),
      hasHome: !!workspace?.querySelector('[data-ea-workspace-body="home"]'),
      hasSelectedEmail: !!workspace?.querySelector('#ea-selected-email'),
      hasDailySummary: !!workspace?.querySelector('#ea-daily-summary')
    };
  })()`);
}

async function layoutAudit(width) {
  return evaluate(`(() => {
    const root = document.querySelector('#email-agent-companion-root');
    const content = document.querySelector('#ea-content');
    const bodies = [...document.querySelectorAll('#ea-workspace > [data-ea-workspace-body]')].filter(isVisible);
    const primaries = [...document.querySelectorAll('#ea-workspace [data-tw-primary-action]')].filter(isVisible);
    return {
      width: ${width},
      visibleBodyCount: bodies.length,
      visiblePrimaryCount: primaries.length,
      horizontalOverflow: Math.max(0, (content?.scrollWidth || 0) - (content?.clientWidth || 0)),
      rootRightOverflow: Math.max(0, (root?.getBoundingClientRect().right || 0) - innerWidth)
    };
  })()`);
}

async function captureWidthAudits(state) {
  const audits = [];
  for (const width of [360, 390, 420]) {
    await send("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
    audits.push({ state, ...await layoutAudit(width) });
  }
  await send("Emulation.setDeviceMetricsOverride", { width: 420, height: 900, deviceScaleFactor: 1, mobile: false });
  return audits;
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
