(() => {
  const SINGLETON_KEY = "__eaCompanionSingleton";
  if (globalThis[SINGLETON_KEY] && typeof globalThis[SINGLETON_KEY].teardown === "function") {
    globalThis[SINGLETON_KEY].teardown();
  }
  const ROOT_ID = "email-agent-companion-root";
  const LOCAL_ORIGIN = "http://127.0.0.1:8021";
  const HEALTH_PATH = "/api/health";
  const HEALTH_SERVICE_ID = "threadwise-gmail-companion";
  const BRAND_ICON_URL = chrome.runtime.getURL("assets/brand/threadwise-app-icon.png");
  const PANEL_WIDTH = "420px";
  const PANEL_WIDTH_MINIMIZED = "70px";
  const REFRESH_INTERVAL_MS = 5000;
  let minimized = true;
  let previousPayload = "";
  let lastHarnessState = null;
  let lastSidebarState = null;
  let lastConnectionState = {
    kind: "connecting",
    label: "Connecting",
    details: "Checking the local companion.",
  };
  let teachPreview = null;
  let previousTeachPreview = null;
  let teachResult = null;
  let unsubscribeResult = "";
  let feedbackOpen = false;
  let feedbackDraft = "";
  let feedbackResult = "";
  let activeSummaryFilter = "recent_items";
  let detailsExpanded = false;
  let teachDraft = {
    targetLabel: "",
    note: "",
  };
  let manualPreviewContext = null;
  let lastLiveContext = null;
  let trustedHtmlPolicy = null;
  let refreshIntervalId = null;
  let refreshInFlight = false;
  let hashChangeListener = null;
  let documentClickListener = null;
  let runtimeMessageListener = null;

  function boot() {
    ensureRoot();
    installTestHooks();
    refreshSelection();
    refreshIntervalId = window.setInterval(refreshSelection, REFRESH_INTERVAL_MS);
    hashChangeListener = () => refreshSelection();
    window.addEventListener("hashchange", hashChangeListener);
    documentClickListener = () => window.setTimeout(refreshSelection, 150);
    document.addEventListener("click", documentClickListener);
    runtimeMessageListener = (message) => {
      if (!message || message.type !== "email-agent:toggle") {
        return;
      }
      minimized = !minimized;
      renderMinimized();
    };
    chrome.runtime.onMessage.addListener(runtimeMessageListener);
    globalThis[SINGLETON_KEY] = {
      teardown,
    };
  }

  function ensureRoot() {
    if (document.getElementById(ROOT_ID)) {
      return;
    }

    const root = document.createElement("div");
    root.id = ROOT_ID;
    Object.assign(root.style, {
      position: "fixed",
      top: "14px",
      right: "14px",
      width: PANEL_WIDTH,
      maxWidth: "calc(100vw - 28px)",
      maxHeight: "calc(100vh - 28px)",
      zIndex: "2147483647",
      pointerEvents: "auto",
    });
    setHtml(root, `
      <div id="ea-panel" style="background:#fff7e8;border:3px solid #241812;border-radius:18px;box-shadow:6px 6px 0 #241812;overflow:hidden;font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#241812;display:flex;flex-direction:column;max-height:calc(100vh - 28px);">
        <div id="ea-header" style="display:grid;grid-template-columns:52px 1fr auto;align-items:center;gap:12px;padding:17px 18px;border-bottom:3px solid #241812;background:#fff4d7;">
          <div style="display:flex;align-items:center;gap:10px;min-width:0;">
            <button id="ea-brand-toggle" type="button" title="Open Threadwise" style="position:relative;width:42px;height:42px;border-radius:12px;border:2px solid #241812;box-shadow:3px 3px 0 #241812;flex:0 0 auto;background:#fff8df;padding:0;cursor:pointer;overflow:hidden;">
              <img src="${BRAND_ICON_URL}" alt="" aria-hidden="true" data-ea-brand-img="true" style="width:100%;height:100%;display:block;object-fit:cover;background:#fff8df;">
              <span aria-hidden="true" style="display:none;place-items:center;width:100%;height:100%;font-weight:900;font-size:0.82rem;color:#241812;background:#ffc64a;">TW</span>
            </button>
          </div>
          <div style="display:flex;align-items:center;gap:10px;min-width:0;">
            <div style="display:grid;gap:3px;min-width:0;">
              <div style="font-size:1.35rem;font-weight:840;letter-spacing:-0.04em;line-height:1;">Threadwise</div>
              <div id="ea-status" style="display:inline-flex;align-items:center;gap:6px;width:max-content;border:2px solid #241812;border-radius:999px;padding:4px 8px;background:#d8f3ef;color:#0f766e;font-size:0.72rem;font-weight:800;line-height:1;">Connecting</div>
              <div style="color:#ad6400;font-family:ui-serif,Georgia,'Times New Roman',serif;font-size:0.58rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;line-height:1.05;white-space:nowrap;">CLEAR THREADS. BETTER INBOX.</div>
            </div>
          </div>
          <button id="ea-minimize" type="button" style="border:2px solid #241812;background:#e9efe2;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:760;box-shadow:2px 2px 0 #241812;">Minimize</button>
        </div>
        <div id="ea-content" style="padding:14px;display:grid;gap:13px;overflow-y:auto;min-height:0;">
          <section style="border:3px solid #241812;border-radius:18px;padding:16px;background:#fffdf7;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
            <div style="color:#6b6255;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.14em;font-weight:820;">Agent View</div>
            <div id="ea-selected-email"></div>
            <div style="margin-top:14px;border:3px solid #241812;border-radius:18px;background:#ffe1a3;overflow:hidden;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
              <div style="min-height:40px;display:flex;align-items:center;padding:0 13px;border-bottom:3px solid #241812;background:#ffc64a;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.14em;color:#241812;font-weight:900;">Correct / Teach</div>
              <div id="ea-teach-panel" style="display:grid;gap:12px;margin:12px;"></div>
            </div>
            <div id="ea-selected-email-secondary"></div>
          </section>
          <section style="border:3px solid #241812;border-radius:18px;padding:16px;background:#e9efe2;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
            <div style="color:#6b6255;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.14em;font-weight:820;">Today</div>
            <div id="ea-daily-summary"></div>
          </section>
        </div>
        <div id="ea-footer" style="display:none;flex:0 0 auto;"></div>
        <div id="ea-feedback-shell" style="border-top:3px solid #241812;background:#fffdf7;padding:10px 12px;flex:0 0 auto;">
          <button id="ea-feedback-open" type="button" data-ea-action="open-feedback" style="width:100%;border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:840;box-shadow:2px 2px 0 #241812;">Note</button>
          <div id="ea-feedback-panel" style="display:none;margin-top:10px;"></div>
        </div>
      </div>
    `);
    document.body.appendChild(root);

    root.querySelector("#ea-minimize").addEventListener("click", () => {
      minimized = !minimized;
      renderMinimized();
    });
    root.querySelector("#ea-brand-toggle").addEventListener("click", () => {
      minimized = !minimized;
      renderMinimized();
    });
    root.querySelector("[data-ea-brand-img]")?.addEventListener("error", (event) => {
      event.target.style.display = "none";
      if (event.target.nextElementSibling) {
        event.target.nextElementSibling.style.display = "grid";
      }
    });
    root.addEventListener("click", handlePanelClick);
    root.addEventListener("input", handlePanelInput);
    root.addEventListener("change", handlePanelInput);
    renderMinimized();
    renderFeedbackPanel();
  }

  function renderMinimized() {
    const root = document.getElementById(ROOT_ID);
    if (!root) {
      return;
    }
    const content = root.querySelector("#ea-content");
    const footer = root.querySelector("#ea-footer");
    const feedbackShell = root.querySelector("#ea-feedback-shell");
    const button = root.querySelector("#ea-minimize");
    const status = root.querySelector("#ea-status");
    const title = root.querySelector("#ea-status")?.previousElementSibling;
    const header = root.querySelector("#ea-header");
    const headerCopy = title?.parentElement?.parentElement;
    const brandButton = root.querySelector("#ea-brand-toggle");
    if (!content || !footer || !button || !header || !brandButton) {
      return;
    }
    const statusCopy = connectionStatusCopy();
    content.style.display = minimized ? "none" : "grid";
    footer.style.display = "none";
    if (feedbackShell) {
      feedbackShell.style.display = minimized ? "none" : "block";
    }
    root.style.width = minimized ? PANEL_WIDTH_MINIMIZED : PANEL_WIDTH;
    header.style.gridTemplateColumns = minimized ? "1fr" : "52px 1fr auto";
    header.style.padding = minimized ? "10px" : "17px 18px";
    header.style.borderBottom = minimized ? "0" : "3px solid #241812";
    button.style.display = minimized ? "none" : "block";
    if (headerCopy) {
      headerCopy.style.display = minimized ? "none" : "flex";
    }
    brandButton.title = minimized ? `${statusCopy.label} - open Threadwise` : "Minimize Threadwise";
    button.textContent = "Minimize";
    button.title = statusCopy.label;
    if (status) {
      status.textContent = statusCopy.label;
      status.style.background = statusCopy.background;
      status.style.color = statusCopy.foreground;
    }
    if (title) {
      title.style.fontSize = minimized ? "1.12rem" : "1.35rem";
    }
    const subtitle = root.querySelector("#ea-status")?.nextElementSibling;
    if (subtitle) {
      subtitle.style.display = minimized ? "none" : "block";
    }
  }

  function selectedContext() {
    const subject = firstText(["h2[data-thread-perm-id]", "h2.hP", "h2[role='heading']"]);
    const messageNode = subject ? selectedMessageNode() : null;
    const senderNode = selectedSenderNode(messageNode);
    return {
      provider: "gmail",
      message_id: messageNode
        ? messageNode.getAttribute("data-legacy-message-id") ||
          messageNode.getAttribute("data-message-id") ||
          ""
        : "",
      thread_id: messageNode ? messageNode.getAttribute("data-thread-perm-id") || "" : "",
      subject,
      sender: senderNode
        ? (senderNode.getAttribute("email") || senderNode.textContent || "").trim()
        : "",
      page_url: window.location.href,
      selected_at: new Date().toISOString(),
    };
  }

  function selectedMessageNode() {
    const visibleCandidates = Array.from(
      document.querySelectorAll("[data-legacy-message-id], [data-message-id]"),
    ).filter(isVisibleNode);
    if (visibleCandidates.length) {
      return visibleCandidates[visibleCandidates.length - 1];
    }
    return (
      document.querySelector("[data-legacy-message-id]") ||
      document.querySelector("[data-message-id]")
    );
  }

  function selectedSenderNode(messageNode) {
    const scopedRoot =
      messageNode?.closest("[role='listitem'], .adn, .ii, .h7, [data-thread-perm-id]") ||
      document;
    return (
      scopedRoot.querySelector?.("[email][data-hovercard-id]") ||
      scopedRoot.querySelector?.("span[email]") ||
      document.querySelector("[email][data-hovercard-id]") ||
      document.querySelector("span[email]")
    );
  }

  function isVisibleNode(node) {
    if (!node || typeof node.getBoundingClientRect !== "function") {
      return false;
    }
    const style = window.getComputedStyle(node);
    if (!style || style.display === "none" || style.visibility === "hidden") {
      return false;
    }
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function contextFromItem(item) {
    return {
      provider: "gmail",
      message_id: item?.message_id || "",
      subject: item?.subject || "",
      sender: item?.sender || "",
    };
  }

  function openItemPreview(item, options = {}) {
    if (!item) {
      return false;
    }
    manualPreviewContext = contextFromItem(item);
    teachPreview = null;
    previousTeachPreview = null;
    teachResult = null;
    unsubscribeResult = "";
    if (options.clearDraft !== false) {
      teachDraft = { targetLabel: "", note: "" };
    }
    refreshSelection(true);
    return true;
  }

  function firstText(selectors) {
    for (const selector of selectors) {
      const node = document.querySelector(selector);
      if (node && node.textContent && node.textContent.trim()) {
        return node.textContent.trim();
      }
    }
    return "";
  }

  function refreshSelection(force = false) {
    lastLiveContext = stabilizedLiveContext(selectedContext());
    const context = chooseRefreshContext();
    const payload = JSON.stringify({
      provider: context.provider || "",
      message_id: context.message_id || "",
      thread_id: context.thread_id || "",
      subject: context.subject || "",
      sender: context.sender || "",
      page_url: context.page_url || "",
    });
    if (!force && payload === previousPayload) {
      return;
    }
    if (refreshInFlight && !force) {
      return;
    }
    refreshInFlight = true;
    chrome.runtime.sendMessage({ type: "email-agent:get-state", context }, (response) => {
      refreshInFlight = false;
      if (chrome.runtime.lastError) {
        previousPayload = "";
        renderError(chrome.runtime.lastError.message || "Could not reach extension background.", {
          kind: "helper-unreachable",
          label: "Helper unreachable",
          details: chrome.runtime.lastError.message || "Could not reach extension background.",
        });
        return;
      }
      if (!response || !response.ok) {
        previousPayload = "";
        const connectionState = normalizeConnectionState(response && response.connection_state);
        if (connectionState.kind === "ready") {
          renderLoadingState((response && response.error) || "Threadwise is connected but the inbox state is still loading.");
          return;
        }
        renderError((response && response.error) || "Could not reach local companion server.", connectionState);
        return;
      }
      previousPayload = payload;
      lastConnectionState = normalizeConnectionState(response.connection_state || {
        kind: "ready",
        label: "Ready",
        details: "Threadwise is connected.",
      });
      renderState(response.payload);
    });
  }

  function renderLoadingState(message) {
    const selectedEmailNode = document.getElementById("ea-selected-email");
    const selectedEmailSecondaryNode = document.getElementById("ea-selected-email-secondary");
    const teachPanelNode = document.getElementById("ea-teach-panel");
    const dailySummaryNode = document.getElementById("ea-daily-summary");
    lastConnectionState = normalizeConnectionState({
      kind: "ready",
      label: "Ready",
      details: "Threadwise is responding at the local companion server.",
    });
    if (selectedEmailNode) {
      setHtml(selectedEmailNode, `
        <div style="margin-top:10px;color:#0f766e;line-height:1.45;">${escapeHtml(message)}</div>
        <div style="margin-top:10px;border-radius:14px;background:#d8f3ef;padding:12px;color:#0f766e;line-height:1.45;">
          The helper is up. Threadwise is loading the inbox snapshot and queue state.
        </div>
      `);
    }
    if (teachPanelNode) {
      setHtml(teachPanelNode, `<div style="color:#6b6255;line-height:1.45;">Loading the current inbox state before teaching corrections.</div>`);
    }
    if (selectedEmailSecondaryNode) {
      setHtml(selectedEmailSecondaryNode, "");
    }
    if (dailySummaryNode) {
      setHtml(dailySummaryNode, `<div style="margin-top:10px;color:#6b6255;line-height:1.45;">The local companion is reachable. Waiting for the inbox state payload.</div>`);
    }
    renderMinimized();
  }

  function chooseRefreshContext() {
    if (manualPreviewContext) {
      return manualPreviewContext;
    }
    if (shouldHoldSelectedContext()) {
      return (lastSidebarState && lastSidebarState.selected_context) || lastLiveContext;
    }
    return lastLiveContext;
  }

  function stabilizedLiveContext(nextContext) {
    const previous = lastLiveContext || {};
    if (!isMeaningfulContext(nextContext)) {
      return previous;
    }
    if (shouldPreferPreviousContext(nextContext, previous)) {
      return previous;
    }
    return nextContext;
  }

  function shouldPreferPreviousContext(nextContext, previousContext) {
    if (!isMeaningfulContext(previousContext)) {
      return false;
    }
    if (contextsMatch(nextContext, previousContext)) {
      return contextStrength(nextContext) < contextStrength(previousContext);
    }
    return hasTeachDraftChanges() && contextStrength(nextContext) < contextStrength(previousContext);
  }

  function shouldHoldSelectedContext() {
    const selectedContext = (lastSidebarState && lastSidebarState.selected_context) || {};
    if (!hasTeachDraftChanges() || !isMeaningfulContext(selectedContext)) {
      return false;
    }
    return (
      contextsMatch(lastLiveContext, selectedContext) ||
      contextStrength(lastLiveContext) < contextStrength(selectedContext)
    );
  }

  function hasTeachDraftChanges() {
    return Boolean((teachDraft.targetLabel || "").trim() || (teachDraft.note || "").trim());
  }

  function isMeaningfulContext(context) {
    return Boolean(context && (context.message_id || context.subject));
  }

  function contextStrength(context) {
    if (!context) {
      return 0;
    }
    let strength = 0;
    if (context.message_id) {
      strength += 4;
    }
    if (context.subject) {
      strength += 2;
    }
    if (context.sender) {
      strength += 1;
    }
    return strength;
  }

  function contextsMatch(left, right) {
    if (!left || !right) {
      return false;
    }
    if (left.message_id && right.message_id) {
      return left.message_id === right.message_id;
    }
    const leftSender = normalizedSender(left.sender || "");
    const rightSender = normalizedSender(right.sender || "");
    const leftSubject = normalizedSubject(left.subject || "");
    const rightSubject = normalizedSubject(right.subject || "");
    return Boolean(leftSender && rightSender && leftSubject && rightSubject && leftSender === rightSender && leftSubject === rightSubject);
  }

  function normalizedSender(value) {
    return String(value || "").trim().toLowerCase();
  }

  function normalizedSubject(value) {
    return String(value || "").trim().toLowerCase();
  }

  function normalizeConnectionState(state) {
    const kind = state && state.kind ? state.kind : "helper-unreachable";
    if (kind === "ready") {
      return {
        kind,
        label: state.label || "Ready",
        details: state.details || "Threadwise is connected.",
      };
    }
    if (kind === "wrong-service") {
      return {
        kind,
        label: state.label || "Wrong service on port",
        details: state.details || `Something else is responding at ${LOCAL_ORIGIN}.`,
      };
    }
    if (kind === "health-failed") {
      return {
        kind,
        label: state.label || "Health check failed",
        details: state.details || "Threadwise did not report a ready status.",
      };
    }
    if (kind === "connecting") {
      return {
        kind,
        label: state.label || "Connecting",
        details: state.details || "Checking the local companion.",
      };
    }
    return {
      kind: "helper-unreachable",
      label: state.label || "Helper unreachable",
      details: state.details || "Could not reach the local companion.",
    };
  }

  function connectionStatusCopy() {
    const state = normalizeConnectionState(lastConnectionState);
    const needsAttentionCount = ((lastSidebarState && lastSidebarState.needs_attention_items) || []).length;
    if (state.kind !== "ready") {
      if (state.kind === "wrong-service") {
        return {
          label: "Wrong service",
          background: "#fff4dd",
          foreground: "#8a4b00",
        };
      }
      if (state.kind === "health-failed") {
        return {
          label: "Needs setup",
          background: "#fff4dd",
          foreground: "#8a4b00",
        };
      }
      return {
        label: "Offline",
        background: "#f7e2e2",
        foreground: "#8a1f1f",
      };
    }
    if (needsAttentionCount > 0) {
      return {
        label: `Needs attention ${needsAttentionCount}`,
        background: "#fff4dd",
        foreground: "#8a4b00",
      };
    }
    return {
      label: "Ready",
      background: "#d8f3ef",
      foreground: "#0f766e",
    };
  }

  function connectionRemediationCopy(state) {
    if (state.kind === "wrong-service") {
      return [
        "Confirm no other app is using the Threadwise port.",
        "Start the Threadwise startup helper again.",
      ];
    }
    if (state.kind === "health-failed") {
      return [
        "Check the local companion logs.",
        "Restart the personal startup helper.",
      ];
    }
    if (state.kind === "connecting") {
      return ["Waiting for the local companion to answer."];
    }
    return [
      "Open the Threadwise startup helper.",
      "Check again after the helper says Threadwise is running.",
    ];
  }

  function renderError(message, connectionState) {
    lastConnectionState = normalizeConnectionState(connectionState || lastConnectionState);
    const selectedEmailNode = document.getElementById("ea-selected-email");
    const selectedEmailSecondaryNode = document.getElementById("ea-selected-email-secondary");
    const teachPanelNode = document.getElementById("ea-teach-panel");
    const dailySummaryNode = document.getElementById("ea-daily-summary");
    const statusCopy = connectionStatusCopy();
    const remediation = connectionRemediationCopy(lastConnectionState);
    const errorTitle = errorTitleForConnection(lastConnectionState);
    const friendlyMessage = friendlyErrorMessage(message);
    if (selectedEmailNode) {
      setHtml(selectedEmailNode, `
        <div style="margin-top:10px;border:2px solid #241812;border-radius:14px;background:#fff4dd;padding:12px;color:#8a4b00;line-height:1.45;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#8a4b00;font-weight:900;">${escapeHtml(statusCopy.label)}</div>
          <div style="margin-top:8px;font-size:1.05rem;font-weight:840;color:#241812;">${escapeHtml(errorTitle)}</div>
          <div style="margin-top:8px;">${escapeHtml(friendlyMessage)}</div>
          <details style="margin-top:8px;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Technical detail</summary>
            <div style="margin-top:6px;overflow-wrap:anywhere;">${escapeHtml(message)}</div>
          </details>
        </div>
        <div style="margin-top:10px;border-radius:14px;background:#fffdf7;padding:12px;color:#8a4b00;line-height:1.45;">
          <div style="font-weight:700;">What to do</div>
          <ul style="margin:8px 0 0;padding-left:18px;">
            ${remediation.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
          <button type="button" data-ea-action="force-refresh" style="margin-top:12px;border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Check again</button>
        </div>
      `);
    }
    if (teachPanelNode) {
      setHtml(teachPanelNode, `<div style="color:#8a4b00;line-height:1.45;">Reconnect Threadwise before teaching corrections.</div>`);
    }
    if (selectedEmailSecondaryNode) {
      setHtml(selectedEmailSecondaryNode, "");
    }
    if (dailySummaryNode) {
      setHtml(dailySummaryNode, `
        <details style="margin-top:10px;color:#6b6255;line-height:1.45;">
          <summary style="cursor:pointer;font-weight:800;color:#241812;">Connection details</summary>
          <div style="margin-top:8px;overflow-wrap:anywhere;">${escapeHtml(lastConnectionState.details || "Threadwise did not provide a connection detail.")}</div>
        </details>
      `);
    }
    renderMinimized();
  }

  function errorTitleForConnection(state) {
    if (state.kind === "wrong-service") {
      return "Something else is using the Threadwise port.";
    }
    if (state.kind === "health-failed") {
      return "Threadwise answered, but it is not ready.";
    }
    if (state.kind === "connecting") {
      return "Threadwise is still connecting.";
    }
    return "Threadwise is not connected.";
  }

  function friendlyErrorMessage(message) {
    const normalized = String(message || "").toLowerCase();
    if (normalized.includes("aborterror") || normalized.includes("signal is aborted")) {
      return "The last connection attempt was interrupted. This usually clears after checking again or reopening Gmail.";
    }
    if (normalized.includes("failed to fetch") || normalized.includes("could not reach")) {
      return "The Gmail extension cannot reach the local Threadwise companion yet.";
    }
    return "Threadwise could not load the local companion state.";
  }

  function feedbackContext() {
    const sidebarState = lastSidebarState || {};
    return {
      surface: "gmail_companion_extension",
      page_url: window.location.href,
      connection_kind: normalizeConnectionState(lastConnectionState).kind,
      active_summary_filter: activeSummaryFilter,
      selected_context: sidebarState.selected_context || lastLiveContext || {},
      selected_email: sidebarState.selected_email || {},
    };
  }

  function renderFeedbackPanel() {
    const root = document.getElementById(ROOT_ID);
    const panel = document.getElementById("ea-feedback-panel");
    const openButton = document.getElementById("ea-feedback-open");
    if (!panel || !openButton) {
      return;
    }
    if (root) {
      root.style.width = feedbackOpen ? PANEL_WIDTH : (minimized ? PANEL_WIDTH_MINIMIZED : PANEL_WIDTH);
    }
    openButton.textContent = feedbackOpen ? "Close note" : (feedbackResult ? "Note saved" : "Note");
    panel.style.display = feedbackOpen ? "block" : "none";
    if (!feedbackOpen) {
      return;
    }
    const context = feedbackContext();
    const selectedContext = context.selected_context || {};
    const contextLine = selectedContext.subject || selectedContext.sender
      ? `${selectedContext.subject || "(no subject)"} - ${selectedContext.sender || "(unknown sender)"}`
      : "Current Threadwise view";
    setHtml(panel, `
      <div style="display:grid;gap:8px;">
        <textarea id="ea-feedback-note" rows="4" placeholder="What should Threadwise do better here?" style="box-sizing:border-box;width:100%;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:#fffdf7;color:#1f1a14;font:inherit;resize:vertical;box-shadow:2px 2px 0 rgba(36,24,18,.18);">${escapeHtml(feedbackDraft)}</textarea>
        <div style="color:#6b6255;font-size:0.78rem;line-height:1.35;overflow-wrap:anywhere;">Context: ${escapeHtml(contextLine)}</div>
        ${feedbackResult ? `<div style="border-radius:11px;background:#d8f3ef;color:#0f766e;padding:9px 10px;font-size:0.84rem;line-height:1.35;">${escapeHtml(feedbackResult)}</div>` : ""}
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button type="button" data-ea-action="submit-feedback" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Save note</button>
          <button type="button" data-ea-action="clear-feedback" style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Clear</button>
        </div>
      </div>
    `);
  }

  function submitFounderFeedback() {
    feedbackDraft = (document.getElementById("ea-feedback-note")?.value || feedbackDraft || "").trim();
    if (!feedbackDraft) {
      feedbackResult = "Write a note first.";
      renderFeedbackPanel();
      return;
    }
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/founder-feedback",
      method: "POST",
      body: {
        source: "gmail_companion_extension",
        note: feedbackDraft,
        context: feedbackContext(),
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        feedbackResult = chrome.runtime.lastError.message || "Could not save note.";
      } else if (!response || !response.ok) {
        feedbackResult = (response && (response.payload?.error || response.error)) || "Could not save note.";
      } else {
        feedbackDraft = "";
        feedbackResult = "Saved locally for review.";
        feedbackOpen = false;
      }
      renderFeedbackPanel();
    });
  }

  function renderState(state) {
    lastHarnessState = normalizeHarnessState(state);
    lastSidebarState = lastHarnessState.sidebar_state;
    const selectedEmailNode = document.getElementById("ea-selected-email");
    const selectedEmailSecondaryNode = document.getElementById("ea-selected-email-secondary");
    const teachPanelNode = document.getElementById("ea-teach-panel");
    const dailySummaryNode = document.getElementById("ea-daily-summary");
    if (!selectedEmailNode || !selectedEmailSecondaryNode || !teachPanelNode || !dailySummaryNode) {
      return;
    }

    const selected = lastSidebarState.selected_email || null;
    const summary = lastSidebarState.daily_summary || {};
    const showingQueuePreview = !!manualPreviewContext;
    const stepCopy = nextStepCopy(selected, showingQueuePreview);
    if (!(selected && selected.found)) {
      previousTeachPreview = null;
      unsubscribeResult = "";
      detailsExpanded = false;
    }

    if (!selected || !selected.found) {
      const hasSnapshotMiss = selected && selected.status === "not-in-snapshot";
      const title = hasSnapshotMiss
        ? "Threadwise has not synced this email yet."
        : "Open an email to inspect or teach Threadwise.";
      const reason = hasSnapshotMiss && selected.reason
        ? `<div style="margin-top:12px;border-radius:14px;background:#fff4dd;padding:12px;color:#8a4b00;line-height:1.45;">${escapeHtml(selected.reason)}</div>`
        : "";
      const relatedItems = relatedSummaryItemsForContext(lastLiveContext).slice(0, 4);
      const primaryRelatedItem = relatedItems[0] || null;
      const relatedHtml = relatedItems.length
        ? `
          <div style="margin-top:14px;border-top:1px solid #e5dccb;padding-top:14px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Closest synced emails</div>
            <div style="margin-top:8px;color:#6b6255;line-height:1.45;">These are the best local matches the agent can explain right now.</div>
            <div style="display:grid;gap:8px;margin-top:10px;">${renderSummaryItemCards(relatedItems)}</div>
          </div>
        `
        : "";
      const fallbackItems = summaryItemsForFilter("needs_attention_items").slice(0, 4);
      const primaryFallbackItem = fallbackItems[0] || null;
      const fallbackHtml = fallbackItems.length
        ? `
          <div style="margin-top:14px;border-top:1px solid #e5dccb;padding-top:14px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Current Queue</div>
            <div style="display:grid;gap:8px;margin-top:10px;">${renderSummaryItemCards(fallbackItems)}</div>
          </div>
        `
        : "";
      const liveEmailCard = hasSnapshotMiss && lastLiveContext && (lastLiveContext.subject || lastLiveContext.sender)
        ? `
          <div style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Viewing in Gmail now</div>
            <div style="margin-top:8px;font-weight:700;line-height:1.35;">${escapeHtml(lastLiveContext.subject || "(no subject)")}</div>
            <div style="margin-top:6px;color:#6b6255;line-height:1.45;overflow-wrap:anywhere;">${escapeHtml(lastLiveContext.sender || "(unknown sender)")}</div>
          </div>
        `
        : "";
      setHtml(selectedEmailNode, `
        <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${title}</div>
        ${reason}
        ${liveEmailCard}
        <div style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(stepCopy.title)}</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(stepCopy.body)}</div>
        </div>
        <div style="margin-top:12px;color:#6b6255;line-height:1.45;">Threadwise can explain emails it has already synced. Preview a synced match below, or run a Gmail check from the dashboard to refresh what Threadwise knows.</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          ${
            primaryRelatedItem
              ? `<button type="button" data-ea-related-item="${escapeHtml(primaryRelatedItem.message_id || "")}" style="border:0;background:#0f766e;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Preview closest synced match</button>`
              : ""
          }
          ${
            primaryFallbackItem
              ? '<button type="button" data-ea-action="open-needs-attention" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Open needs-attention queue</button>'
              : ""
          }
        </div>
        ${relatedHtml}
        ${fallbackHtml}
      `);
      setHtml(teachPanelNode, `<div style="color:#6b6255;line-height:1.45;">Select a synced email to preview or teach a correction.</div>`);
      setHtml(selectedEmailSecondaryNode, "");
    } else {
      const statusStyle =
        selected.status === "needs-attention"
          ? "display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#fff4dd;color:#8a4b00;font-size:0.82rem;"
          : "display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#d8f3ef;color:#0f766e;font-size:0.82rem;";
      const labelOptions = (((lastSidebarState.ui_state || {}).allowed_labels) || [])
        .map(
          (option) =>
            `<option value="${escapeHtml(option.id)}"${
              option.id === currentDraftTargetLabel(selected) ? " selected" : ""
            }>${escapeHtml(option.name)}</option>`,
        )
        .join("");
      const resultHtml = teachResult ? renderTeachResultHtml(teachResult) : "";
      const previewHtml = teachPreview
        ? `${resultHtml}${renderPreviousTeachPreviewHtml(previousTeachPreview)}${renderTeachPreviewHtml(teachPreview)}`
        : teachResult
          ? resultHtml
          : renderPreviousTeachPreviewHtml(previousTeachPreview);
      const details = selected.details || {};
      const decisionSource = humanDecisionSource(details.review_action || "");
      const writeStatusLabel = humanWriteStatus(details.write_status || "");
      const inboxStatusLabel = humanInboxStatus(details.inbox_status || "");
      const matchedRuleList = (details.matched_rule_ids || []).length
        ? `<div style="margin-top:6px;color:#6b6255;line-height:1.45;">Matched rules: ${escapeHtml((details.matched_rule_ids || []).join(", "))}</div>`
        : "";
      const unsubscribeReasonList = (details.unsubscribe_reasons || []).length
        ? `<div style="margin-top:6px;color:#6b6255;line-height:1.45;">Unsubscribe qualified because: ${escapeHtml((details.unsubscribe_reasons || []).join(", "))}</div>`
        : "";
      const detailsButtonLabel = detailsExpanded ? "Hide technical details" : "Show technical details";
      const detailsHtml = detailsExpanded
        ? `
          <div style="margin-top:10px;color:#6b6255;line-height:1.45;">Decision source: ${escapeHtml(decisionSource)}</div>
          <div style="margin-top:6px;color:#6b6255;line-height:1.45;">Label write status: ${escapeHtml(writeStatusLabel)}</div>
          <div style="margin-top:6px;color:#6b6255;line-height:1.45;">Inbox handling: ${escapeHtml(inboxStatusLabel)}</div>
          <div style="margin-top:6px;color:#6b6255;line-height:1.45;">Matched saved rules: ${escapeHtml(String(details.matched_rule_count || 0))}</div>
          ${matchedRuleList}
          ${unsubscribeReasonList}
        `
        : `<div style="margin-top:8px;color:#6b6255;line-height:1.45;">Open details to inspect decision source, Gmail write status, inbox handling, and matched rules.</div>`;
      const unsubscribe = selected.unsubscribe || null;
      const unsubscribePreview = (unsubscribe && unsubscribe.preview) || null;
      const reviewLinkLabel = unsubscribe && unsubscribe.decision_state === "selected"
        ? "Open queued review"
        : "Review all subscriptions";
      const canOpenUnsubscribeUrl = unsubscribePreview
        && unsubscribePreview.url
        && unsubscribePreview.status !== "ready"
        && unsubscribePreview.url.startsWith("mailto:");
      const unsubscribeLine = unsubscribe
        ? `
          <div data-ea-unsubscribe-card="true" style="margin-top:14px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;box-shadow:3px 3px 0 rgba(36,24,18,.22);">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Unsubscribe</div>
            <div style="margin-top:8px;color:#1f1a14;line-height:1.45;font-weight:700;">${escapeHtml(unsubscribe.display_name || selected.sender || "Subscription")}</div>
            <div style="margin-top:6px;color:#6b6255;line-height:1.45;">${escapeHtml((unsubscribePreview && unsubscribePreview.notes) || "Unsubscribe available")}</div>
            ${unsubscribeResult ? `<div style="margin-top:12px;border-radius:14px;background:#d8f3ef;padding:12px;color:#0f766e;line-height:1.45;">${escapeHtml(unsubscribeResult)}</div>` : ""}
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
              ${unsubscribePreview && unsubscribePreview.status === "ready" && !unsubscribeResult ? '<button type="button" data-ea-action="select-unsubscribe" data-ea-unsubscribe-action="queue" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Queue unsubscribe review</button>' : ""}
              ${canOpenUnsubscribeUrl ? `<a href="${escapeHtml(unsubscribePreview.url)}" data-ea-unsubscribe-action="open-mail" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px;font:inherit;font-weight:760;box-shadow:none;">Open mail unsubscribe</a>` : ""}
              <a href="${escapeHtml(`${LOCAL_ORIGIN}${unsubscribe.handoff_path || "/unsubscribe-review"}`)}" target="_blank" rel="noreferrer" data-ea-unsubscribe-action="review" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px;font:inherit;font-weight:760;box-shadow:none;">${reviewLinkLabel}</a>
            </div>
          </div>
        `
        : "";
      const previewModeBanner = showingQueuePreview
        ? `
          <div style="margin-top:14px;border-radius:14px;background:#fff8eb;padding:12px;color:#1f1a14;line-height:1.45;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Queue preview</div>
            <div style="margin-top:8px;">You are previewing a stored queue email from the local snapshot.</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
              <button type="button" data-ea-action="return-to-live" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Close preview</button>
            </div>
          </div>
        `
        : "";
      const overviewCard = `
        <div style="margin-top:14px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Agent view</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
            <div style="border-radius:12px;background:#fffdfa;padding:10px 12px;">
              <div style="font-size:0.72rem;color:#6b6255;text-transform:uppercase;letter-spacing:0.08em;">Gmail label</div>
              <div style="margin-top:6px;font-weight:700;line-height:1.3;">${escapeHtml(selected.classification || "Uncategorized")}</div>
            </div>
            <div style="border-radius:12px;background:#fffdfa;padding:10px 12px;">
              <div style="font-size:0.72rem;color:#6b6255;text-transform:uppercase;letter-spacing:0.08em;">Human meaning</div>
              <div style="margin-top:6px;font-weight:700;line-height:1.3;">${escapeHtml(humanMeaningForSelected(selected))}</div>
            </div>
          </div>
        </div>
      `;
      const nextStepCard = `
        <div style="margin-top:14px;border-radius:14px;background:${selected.status === "needs-attention" ? "#fff8eb" : "#eef7f5"};padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(stepCopy.title)}</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(stepCopy.body)}</div>
        </div>
      `;
      setHtml(selectedEmailNode, `
        <div style="margin-top:7px;font-size:1.45rem;font-weight:840;letter-spacing:-0.015em;line-height:1.04;">${escapeHtml(selected.subject || "(no subject)")}</div>
        <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.sender || "(unknown sender)")}</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">${escapeHtml(selected.classification || "Uncategorized")}</span>
          <span style="${statusStyle};border:2px solid #241812;box-shadow:2px 2px 0 rgba(36,24,18,.28);font-weight:760;">${escapeHtml(selected.status_label)}</span>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-action="open-selected-gmail" style="border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Open this email in Gmail</button>
        </div>
        ${previewModeBanner}
        ${overviewCard}
        ${nextStepCard}
        <div style="margin-top:14px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Likely why</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(likelyReasonForSelected(selected))}</div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, `
        <div style="margin-top:14px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Technical details</div>
            <button type="button" data-ea-action="toggle-details" style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:11px;padding:7px 10px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">${detailsButtonLabel}</button>
          </div>
          ${detailsHtml}
        </div>
        ${unsubscribeLine}
      `);
      setHtml(teachPanelNode, `
        <div style="display:grid;gap:8px;">
          <textarea id="ea-teach-note" rows="3" placeholder="What should Threadwise understand?" style="box-sizing:border-box;width:100%;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:#fffdf7;color:#1f1a14;font:inherit;resize:vertical;box-shadow:2px 2px 0 rgba(36,24,18,.18);">${escapeHtml(teachDraft.note)}</textarea>
          <details style="color:#6b6255;line-height:1.35;font-size:0.82rem;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Choose label manually</summary>
            <select id="ea-target-label" style="box-sizing:border-box;width:100%;margin-top:8px;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:#fffdf7;color:#1f1a14;font:inherit;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
              <option value="">Infer from note</option>
              ${labelOptions}
            </select>
          </details>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button type="button" data-ea-action="preview-teach" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Preview</button>
            <button type="button" data-ea-action="clear-teach" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;cursor:pointer;font:inherit;font-weight:760;text-decoration:underline;text-underline-offset:3px;box-shadow:none;">Clear draft</button>
          </div>
        </div>
        ${previewHtml}
      `);
    }
    renderMinimized();

    const changedToday = summary.changed_today || {};
    const selectedUnsubscribeExamples = changedToday.selected_unsubscribe_examples || [];
    const focus = summaryFocusCopy(activeSummaryFilter);
    const topLabels = (summary.top_labels || [])
      .map(
        (item) =>
          `<span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">${escapeHtml(item.label)} - ${item.count}</span>`,
      )
      .join("");
      const metricButtonStyle = (key) =>
      `border:2px solid #241812;border-radius:11px;background:${activeSummaryFilter === key ? "#dff8ed" : "#fffdf7"};box-shadow:2px 2px 0 rgba(36,24,18,.18);padding:12px;text-align:left;cursor:pointer;font:inherit;color:#241812;`;
    const keptVisibleCount = summary.kept_visible_count ?? countForFilter("kept_visible_items");
    setHtml(dailySummaryNode, `
      <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${summary.run_count > 1 ? `Rolling view across the last ${summary.run_count} Gmail runs` : "Latest run snapshot"}</div>
      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px;">
        <button type="button" data-ea-summary-filter="recent_items" style="${metricButtonStyle("recent_items")}"><strong style="display:block;font-size:1.15rem;">${summary.processed_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">processed</span></button>
        <button type="button" data-ea-summary-filter="auto_handled_items" style="${metricButtonStyle("auto_handled_items")}"><strong style="display:block;font-size:1.15rem;">${summary.auto_handled_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">auto-handled</span></button>
        <button type="button" data-ea-summary-filter="kept_visible_items" style="${metricButtonStyle("kept_visible_items")}"><strong style="display:block;font-size:1.15rem;">${keptVisibleCount || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">kept visible</span></button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
        <span style="border:2px solid #241812;border-radius:999px;padding:6px 10px;background:#f1eadf;color:#241812;font-size:0.8rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Unsubscribe candidates - ${summary.unsubscribe_candidate_count || 0}</span>
        ${summary.report_date ? `<span style="border:2px solid #241812;border-radius:999px;padding:6px 10px;background:#f1eadf;color:#241812;font-size:0.8rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Latest report - ${escapeHtml(summary.report_date)}</span>` : ""}
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
        <a href="${LOCAL_ORIGIN}/daily-dashboard" target="_blank" rel="noreferrer" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px;font:inherit;font-weight:760;box-shadow:none;">Open daily dashboard</a>
        <a href="${LOCAL_ORIGIN}/unsubscribe-review" target="_blank" rel="noreferrer" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px;font:inherit;font-weight:760;box-shadow:none;">Review unsubscribe candidates</a>
      </div>
      <details style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:10px 12px;">
        <summary style="cursor:pointer;font-weight:800;color:#241812;">Report details</summary>
        <div style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#dff8ed;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Viewing</div>
          <div style="margin-top:8px;font-weight:700;line-height:1.35;">${escapeHtml(focus.label)} · ${focus.count}</div>
          <div style="margin-top:6px;color:#1f1a14;line-height:1.45;">${escapeHtml(focus.description)}</div>
        </div>
        <div style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">What Changed Today</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.label_writes_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">labels written</span></div>
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.inbox_removed_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">removed from inbox</span></div>
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.taught_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">teaching changes</span></div>
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.selected_unsubscribe_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">unsubscribe queued</span></div>
          </div>
          ${
            selectedUnsubscribeExamples.length
              ? `<div style="margin-top:12px;border-radius:12px;background:#fffdfa;padding:12px;">
                  <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Queued subscriptions</div>
                  <div style="display:grid;gap:8px;margin-top:10px;">
                    ${selectedUnsubscribeExamples.map((item) => `
                      <a href="${escapeHtml(`${LOCAL_ORIGIN}${item.handoff_path}`)}" target="_blank" rel="noreferrer" style="text-decoration:none;border:1px solid #d7cfbf;border-radius:14px;background:#fffdfa;padding:10px 12px;color:#1f1a14;">
                        <div style="font-size:0.95rem;font-weight:700;line-height:1.25;">${escapeHtml(item.display_name || "(unknown list)")}</div>
                        <div style="margin-top:4px;color:#6b6255;font-size:0.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</div>
                      </a>
                    `).join("")}
                  </div>
                </div>`
              : ""
          }
          <div style="margin-top:12px;display:grid;gap:10px;">${renderChangedTodayGroups(changedToday)}</div>
        </div>
        ${
          (summary.top_labels || []).length
            ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">${topLabels}</div>`
            : '<p style="margin-top:12px;color:#6b6255;line-height:1.45;">No stored label mix yet.</p>'
        }
        <p style="color:#6b6255;font-size:0.85rem;margin-top:12px;">Source: ${escapeHtml(summary.source_label || "stored Gmail snapshot")}${summary.batch_id ? ` - ${escapeHtml(summary.batch_id)}` : ""}</p>
        <div style="margin-top:12px;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(bucketLabelForFilter(activeSummaryFilter))}</div>
        <div style="margin-top:10px;display:grid;gap:8px;">${renderSummaryItemCards(summaryItemsForFilter(activeSummaryFilter))}</div>
      </details>
    `);
  }

  function setHtml(node, html) {
    if (!node) {
      return;
    }
    node.innerHTML = toTrustedHtml(html);
  }

  function toTrustedHtml(html) {
    if (!globalThis.trustedTypes || typeof globalThis.trustedTypes.createPolicy !== "function") {
      return html;
    }
    if (!trustedHtmlPolicy) {
      try {
        trustedHtmlPolicy = globalThis.trustedTypes.createPolicy("email-agent-gmail-companion", {
          createHTML(value) {
            return value;
          },
        });
      } catch (_error) {
        trustedHtmlPolicy = {
          createHTML(value) {
            return value;
          },
        };
      }
    }
    return trustedHtmlPolicy.createHTML(html);
  }

  function normalizeHarnessState(state) {
    if (state && state.sidebar_state) {
      return state;
    }
    return {
      selected_context: state?.selected_context || {},
      sidebar_state: state || {},
      recent_items: [],
      needs_attention_items: [],
      auto_handled_items: [],
      kept_visible_items: [],
    };
  }

  function summaryItemsForFilter(filter) {
    if (!lastHarnessState) {
      return [];
    }
    return Array.isArray(lastHarnessState[filter]) ? lastHarnessState[filter] : [];
  }

  function bucketLabelForFilter(filter) {
    return {
      recent_items: "Recent queue",
      auto_handled_items: "Auto-handled",
      needs_attention_items: "Needs attention",
      kept_visible_items: "Kept visible",
    }[filter] || "Queue";
  }

  function countForFilter(filter) {
    return summaryItemsForFilter(filter).length;
  }

  function nextStepCopy(selected, showingQueuePreview) {
    if (!selected || !selected.found) {
      return {
        title: "What to do now",
        body: "Open one of the synced queue items below if you want to review or teach the agent before the next Gmail sync finishes.",
      };
    }
    if (showingQueuePreview) {
      return {
        title: "What to do now",
        body: "Review this stored queue email, teach the agent if needed, or jump back to the live inbox email when you are done.",
      };
    }
    if (selected.status === "needs-attention") {
      return {
        title: "What to do now",
        body: "This email still needs a decision. Either teach the right label below or leave it visible for later.",
      };
    }
    if (selected.unsubscribe_available) {
      return {
        title: "What to do now",
        body: "The agent already understands this email. If it is a recurring subscription, you can queue it for unsubscribe review here.",
      };
    }
    return {
      title: "What to do now",
      body: "The agent has already classified this email. You only need to step in if the label or handling looks wrong.",
    };
  }

  function likelyReasonForSelected(selected) {
    const reason = (selected && selected.reason ? selected.reason : "").trim();
    if (reason) {
      return `Likely because: ${reason}`;
    }
    return "Likely because this matched the stored classification signals for the current label. Threadwise did not store a more specific reason for this decision yet.";
  }

  function humanMeaningForSelected(selected) {
    if (!selected) {
      return "Unknown";
    }
    const status = selected.status_label || "";
    const label = selected.classification || "";
    if (status && label) {
      return `${status} · ${label.replace(/^EA\//, "")}`;
    }
    return status || label.replace(/^EA\//, "") || "Unknown";
  }

  function summaryFocusCopy(filter) {
    const count = countForFilter(filter);
    const label = bucketLabelForFilter(filter);
    const descriptions = {
      recent_items: "Most recent synced emails across the current local snapshot.",
      auto_handled_items: "Items the agent already handled automatically.",
      needs_attention_items: "Items still waiting for a confident decision or follow-up.",
      kept_visible_items: "Items the agent understood but intentionally left in the inbox view.",
    };
    return {
      label,
      count,
      description: descriptions[filter] || "Current queue slice.",
    };
  }

  function renderSummaryItemCards(items) {
    if (!items.length) {
      return '<div style="color:#6b6255;line-height:1.45;">No synced emails in this bucket right now.</div>';
    }
    return items.slice(0, 6)
      .map((item) => {
        return `
          <button type="button" data-ea-summary-item="${escapeHtml(item.message_id || "")}" style="width:100%;text-align:left;border:1px solid ${item.message_id === ((lastSidebarState || {}).selected_email || {}).message_id ? "#0f766e" : "#d7cfbf"};border-radius:14px;background:${item.message_id === ((lastSidebarState || {}).selected_email || {}).message_id ? "#f5fbfa" : "#fffdfa"};padding:10px 12px;color:#1f1a14;cursor:pointer;font:inherit;">
            <div style="font-size:0.95rem;font-weight:700;line-height:1.25;">${escapeHtml(item.subject || "(no subject)")}</div>
            <div style="margin-top:4px;color:#6b6255;font-size:0.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
              <span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">${escapeHtml(item.classification || "Uncategorized")}</span>
              <span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">${escapeHtml(item.status_label || item.status || "")}</span>
            </div>
            <a href="${escapeHtml(gmailSearchUrl(item))}" target="_blank" rel="noreferrer" data-ea-open-gmail="true" style="display:inline-flex;width:max-content;margin-top:8px;border:1px solid #d7cfbf;border-radius:999px;background:#f5efe2;color:#241812;padding:6px 10px;text-decoration:none;font-size:0.78rem;font-weight:800;">Open in Gmail</a>
          </button>
        `;
      })
      .join("");
  }

  function gmailSearchUrl(item) {
    const subject = String(item?.subject || "").replace(/\s+/g, " ").trim().slice(0, 80);
    let sender = String(item?.sender || "").trim();
    if (sender.includes("<") && sender.includes(">")) {
      sender = sender.split("<", 2)[1].split(">", 1)[0].trim();
    }
    const parts = [];
    if (sender) {
      parts.push(`from:${sender}`);
    }
    if (subject) {
      parts.push(`"${subject}"`);
    }
    const query = parts.join(" ") || String(item?.message_id || "");
    return `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(query)}`;
  }

  function renderChangedTodayGroups(changedToday) {
    const groups = changedToday.groups || [];
    if (groups.length) {
      return groups.map((group) => `
        <div style="display:grid;gap:8px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(group.label || "Changes")}</div>
          ${(group.items || []).map(renderChangedTodayItem).join("")}
        </div>
      `).join("");
    }
    const items = changedToday.items || [];
    if (items.length) {
      return items.map(renderChangedTodayItem).join("");
    }
    return '<div style="color:#6b6255;line-height:1.45;">No tracked agent changes in this stored batch yet.</div>';
  }

  function renderChangedTodayItem(item) {
    return `
      <div style="width:100%;text-align:left;border:1px solid #d7cfbf;border-radius:14px;background:#fffdfa;padding:10px 12px;color:#1f1a14;box-sizing:border-box;">
        <div style="font-size:0.95rem;font-weight:700;line-height:1.25;">${escapeHtml(item.subject || "(no subject)")}</div>
        <div style="margin-top:4px;color:#6b6255;font-size:0.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</div>
        <div style="margin-top:6px;color:#6b6255;line-height:1.45;">${escapeHtml(item.change_summary || "")}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
          <button type="button" data-ea-changed-item="${escapeHtml(item.message_id || "")}" style="border:1px solid #d7cfbf;border-radius:999px;background:#f5efe2;color:#241812;padding:6px 10px;cursor:pointer;font:inherit;font-size:0.78rem;font-weight:800;">Preview in Threadwise</button>
          <button type="button" data-ea-open-changed-gmail="${escapeHtml(item.message_id || "")}" style="border:1px solid #d7cfbf;border-radius:999px;background:#ffc64a;color:#241812;padding:6px 10px;cursor:pointer;font:inherit;font-size:0.78rem;font-weight:800;">Open in Gmail</button>
        </div>
      </div>
    `;
  }

  function relatedSummaryItemsForContext(context) {
    if (!context) {
      return [];
    }
    const sender = normalizedSender(context.sender || "");
    const subject = normalizedSubject(context.subject || "");
    const seen = new Set();
    const results = [];
    const groups = [
      summaryItemsForFilter("needs_attention_items"),
      summaryItemsForFilter("recent_items"),
      summaryItemsForFilter("kept_visible_items"),
      summaryItemsForFilter("auto_handled_items"),
    ];
    for (const group of groups) {
      for (const item of group) {
        if (!item || !item.message_id || seen.has(item.message_id)) {
          continue;
        }
        const itemSender = normalizedSender(item.sender || "");
        const itemSubject = normalizedSubject(item.subject || "");
        const senderMatch = sender && itemSender && sender === itemSender;
        const subjectMatch = subject && itemSubject && subject === itemSubject;
        if (!senderMatch && !subjectMatch) {
          continue;
        }
        seen.add(item.message_id);
        results.push(item);
      }
    }
    return results;
  }

  function findSummaryItem(messageId) {
    if (!lastHarnessState || !messageId) {
      return null;
    }
    const groups = [
      lastHarnessState.recent_items || [],
      lastHarnessState.needs_attention_items || [],
      lastHarnessState.auto_handled_items || [],
      lastHarnessState.kept_visible_items || [],
    ];
    for (const group of groups) {
      const match = group.find((item) => item.message_id === messageId);
      if (match) {
        return match;
      }
    }
    return null;
  }

  function findChangedTodayItem(messageId) {
    if (!messageId) {
      return null;
    }
    const changedToday = (((lastSidebarState || {}).daily_summary || {}).changed_today) || {};
    for (const group of (changedToday.groups || [])) {
      const match = (group.items || []).find((item) => item.message_id === messageId);
      if (match) {
        return match;
      }
    }
    return (changedToday.items || []).find((item) => item.message_id === messageId) || null;
  }

  function selectedEmailAsItem() {
    const selected = ((lastSidebarState || {}).selected_email) || {};
    return {
      message_id: selected.message_id || "",
      subject: selected.subject || "",
      sender: selected.sender || "",
    };
  }

  function openSelectedEmailInGmail() {
    return openGmailItem(selectedEmailAsItem());
  }

  function openGmailItem(item) {
    if (!item || !(item.subject || item.sender || item.message_id)) {
      return;
    }
    window.location.href = gmailSearchUrl(item);
  }

  function teachErrorResult(operation, rawMessage) {
    const operationLabel = operation === "preview" ? "preview" : "apply";
    const retryCopy = operation === "preview"
      ? "Nothing was changed. Check the local companion connection and try Preview again."
      : "Nothing was stored or changed. The preview is still here so you can check the connection and retry without rewriting your note.";
    return {
      kind: `${operation}-error`,
      title: operation === "preview" ? "Preview failed" : "Lesson not applied",
      message: `${friendlyErrorMessage(rawMessage || `Could not ${operationLabel} the lesson.`)} ${retryCopy}`,
    };
  }

  function renderTeachResultHtml(result) {
    const isError = String(result.kind || "").endsWith("-error");
    const tone = isError
      ? { background: "#fff4dd", color: "#8a4b00" }
      : { background: "#d8f3ef", color: "#0f766e" };
    const recoveryActions = isError
      ? `
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-action="force-refresh" style="border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Check again</button>
          ${
            result.kind === "apply-error"
              ? '<button type="button" data-ea-action="retry-apply-teach" data-ea-apply="current-only" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Try fix again</button>'
              : '<button type="button" data-ea-action="retry-preview-teach" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Try preview again</button>'
          }
        </div>
      `
      : "";
    return `
      <div style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border-radius:14px;background:${tone.background};padding:12px;color:${tone.color};line-height:1.45;">
        <div style="font-weight:700;">${escapeHtml(result.title || (isError ? "Lesson failed" : "Lesson applied"))}</div>
        <div style="margin-top:8px;">${escapeHtml(result.message || "")}</div>
        ${recoveryActions}
      </div>
    `;
  }

  function renderTeachPreviewHtml(preview) {
    const impact = preview.impact || {};
    const matchingCount = impact.matching_existing_count || 0;
    const similarCount = impact.similar_candidate_count || 0;
    const similarGroups = impact.similar_candidate_groups || [];
    const broaderRules = impact.broader_rule_candidates || [];
    const severityTone = matchingCount >= 50
      ? { bg: "#fff4dd", fg: "#8a4b00", label: "Large existing-email change" }
      : matchingCount > 0
        ? { bg: "#eef7f5", fg: "#0f766e", label: "Existing-email change to confirm" }
        : similarCount > 0
          ? { bg: "#fff4dd", fg: "#8a4b00", label: "Similar emails found" }
          : { bg: "#eef7f5", fg: "#0f766e", label: "Future-facing lesson" };
    const targetLabelName = humanLabelNameFromId((preview.selected_label_after || [])[0] || "");
    const examples = (impact.matching_existing_examples || [])
      .map(
        (item) =>
          `<li>${escapeHtml(item.subject || "(no subject)")} - ${escapeHtml(item.sender || "(unknown sender)")}</li>`,
      )
      .join("");
    const structuredRule = preview.structured_rule || {};
    const ruleMeta = `
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;">
        <span style="display:inline-flex;align-items:center;padding:6px 9px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.76rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.22);">${escapeHtml(preview.rule_type_label || "Future rule")}</span>
        <span style="display:inline-flex;align-items:center;padding:6px 9px;border:2px solid #241812;border-radius:999px;background:${preview.rule_confidence === "tentative" ? "#fff4dd" : "#eef7f5"};color:${preview.rule_confidence === "tentative" ? "#8a4b00" : "#0f766e"};font-size:0.76rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.22);">${escapeHtml(preview.rule_confidence_label || "Future rule")}</span>
      </div>
      ${
        preview.clarifying_question
          ? `<div style="margin-top:8px;color:#6b6255;line-height:1.45;">${escapeHtml(preview.clarifying_question)}</div>`
          : ""
      }
    `;
    const structuredRuleRows = Object.keys(structuredRule).length
      ? Object.entries(structuredRule)
          .map(([key, value]) => `<div><strong>${escapeHtml(key.replaceAll("_", " "))}:</strong> ${escapeHtml(Array.isArray(value) ? value.join(", ") : String(value))}</div>`)
          .join("")
      : '<div>No structured rule details are available yet.</div>';
    const similarGroupsHtml = similarGroups.length
      ? `
        <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fff8eb;padding:10px 12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Similar emails found</div>
          <div style="margin-top:6px;color:#6b6255;">These are broader candidates. Threadwise is showing them for review, not applying them automatically.</div>
          <div style="display:grid;gap:8px;margin-top:10px;">
            ${similarGroups.map((group) => `
              <div style="border:1px solid #d7cfbf;border-radius:11px;background:#fffdfa;padding:9px 10px;">
                <div style="font-weight:800;">${escapeHtml(group.label || "Similar group")} · ${escapeHtml(String(group.count || 0))}</div>
                <div style="margin-top:4px;color:#6b6255;">${escapeHtml(group.reason || "")}</div>
                ${
                  (group.examples || []).length
                    ? `<ol style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${(group.examples || []).slice(0, 3).map((item) => `<li>${escapeHtml(item.subject || "(no subject)")} - ${escapeHtml(item.sender || "(unknown sender)")}</li>`).join("")}</ol>`
                    : ""
                }
              </div>
            `).join("")}
          </div>
          ${
            broaderRules.length
              ? `<div style="display:grid;gap:6px;margin-top:10px;">${broaderRules.map((rule) => `<div style="color:#6b6255;"><strong style="color:#1f1a14;">Broader rule candidate:</strong> ${escapeHtml(rule.plain_english_rule || "")}</div>`).join("")}</div>`
              : ""
          }
        </div>
      `
      : "";
    return `
      <div style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:#241812;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">This email</div>
        <div style="margin-top:6px;font-weight:700;">${escapeHtml(preview.acknowledgment || "Preview ready.")}</div>
        <div style="margin-top:8px;color:#6b6255;line-height:1.45;">Fix this email only updates the message you are reviewing.</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-apply="current-only" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Fix this email</button>
        </div>
        <div style="margin-top:10px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Future rule</div>
          <div style="margin-top:6px;font-weight:700;">${escapeHtml(preview.plain_english_rule || "No future rule proposal was generated.")}</div>
          ${ruleMeta}
          <details style="margin-top:8px;color:#6b6255;">
            <summary style="cursor:pointer;font-weight:700;color:#241812;">Structured rule</summary>
            <div style="display:grid;gap:4px;margin-top:8px;">${structuredRuleRows}</div>
          </details>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:${severityTone.bg};color:${severityTone.fg};font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">${escapeHtml(severityTone.label)}</span>
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Current email -> ${escapeHtml(targetLabelName)}</span>
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Exact sender matches: ${matchingCount}</span>
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Similar candidates: ${similarCount}</span>
        </div>
        <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${escapeHtml(previewChoiceExplainer(matchingCount, similarCount))}</div>
        <div style="margin-top:10px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;color:#6b6255;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Affected existing emails</div>
          <div style="margin-top:6px;">Would affect <strong style="color:#1f1a14;">${matchingCount}</strong> matching emails Threadwise has seen.</div>
          <details style="margin-top:8px;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Show affected emails</summary>
            ${
              examples
                ? `<ol style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${examples}</ol>`
                : '<div style="margin-top:8px;color:#6b6255;">No matching existing emails to show.</div>'
            }
          </details>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
            <button type="button" data-ea-apply="matching-existing" style="border:2px solid #241812;background:#3d6df2;color:#fff;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Apply to matching emails too</button>
          </div>
        </div>
        ${similarGroupsHtml}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-apply="save-future-rule" style="border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Teach future rule</button>
          <button type="button" data-ea-action="refine-teach" style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Keep discussing</button>
        </div>
      </div>
    `;
  }

  function renderPreviousTeachPreviewHtml(previousPreview) {
    if (!previousPreview) {
      return "";
    }
    const impact = previousPreview.impact || {};
    const targetLabelName = humanLabelNameFromId((previousPreview.selected_label_after || [])[0] || "");
    return `
      <div data-ea-previous-preview="true" style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:#241812;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Previous interpretation</div>
        <div style="margin-top:8px;font-weight:700;">${escapeHtml(previousPreview.acknowledgment || "Previous preview")}</div>
        <div style="margin-top:6px;color:#6b6255;">Would relabel to ${escapeHtml(targetLabelName)} and change ${impact.matching_existing_count || 0} existing emails.</div>
        <div style="margin-top:6px;color:#6b6255;">Use this to compare the old understanding against the current one before you confirm anything broader.</div>
      </div>
    `;
  }

  function previewChoiceExplainer(matchingCount, similarCount) {
    if (matchingCount > 0) {
      return "Nothing beyond the current email changes unless you explicitly approve it. Use the broader apply option only if this lesson really should rewrite those stored emails too.";
    }
    if (similarCount > 0) {
      return "No exact-sender matches were found, but Threadwise found similar candidates. Those broader candidates are visible for review and need a separate confirmation path before they can be applied.";
    }
    return "This lesson only changes the current email now and teaches future behavior. There are no other stored emails waiting on this exact rule today.";
  }

  function humanLabelNameFromId(labelId) {
    if (!labelId) {
      return "Uncategorized";
    }
    const allowedLabels = ((((lastSidebarState || {}).ui_state || {}).allowed_labels) || []);
    const match = allowedLabels.find((item) => item.id === labelId);
    return match ? match.name : labelId;
  }

  async function handlePanelClick(event) {
    const openFeedbackButton = event.target.closest("[data-ea-action='open-feedback']");
    if (openFeedbackButton) {
      event.preventDefault();
      feedbackOpen = !feedbackOpen;
      feedbackResult = "";
      renderFeedbackPanel();
      return;
    }
    const submitFeedbackButton = event.target.closest("[data-ea-action='submit-feedback']");
    if (submitFeedbackButton) {
      event.preventDefault();
      return submitFounderFeedback();
    }
    const clearFeedbackButton = event.target.closest("[data-ea-action='clear-feedback']");
    if (clearFeedbackButton) {
      event.preventDefault();
      feedbackDraft = "";
      feedbackResult = "";
      renderFeedbackPanel();
      return;
    }
    const forceRefreshButton = event.target.closest("[data-ea-action='force-refresh']");
    if (forceRefreshButton) {
      event.preventDefault();
      previousPayload = "";
      refreshSelection(true);
      return;
    }
    const summaryFilterButton = event.target.closest("[data-ea-summary-filter]");
    if (summaryFilterButton) {
      event.preventDefault();
      activeSummaryFilter = summaryFilterButton.getAttribute("data-ea-summary-filter") || "needs_attention_items";
      openFirstSummaryItemIfHelpful(activeSummaryFilter);
      return;
    }
    const summaryItemButton = event.target.closest("[data-ea-summary-item]");
    if (summaryItemButton) {
      if (event.target.closest("[data-ea-open-gmail]")) {
        return;
      }
      event.preventDefault();
      const item = findSummaryItem(summaryItemButton.getAttribute("data-ea-summary-item") || "");
      openItemPreview(item);
      return;
    }
    const changedItemButton = event.target.closest("[data-ea-changed-item]");
    if (changedItemButton) {
      event.preventDefault();
      const messageId = changedItemButton.getAttribute("data-ea-changed-item") || "";
      const item = findSummaryItem(messageId) || findChangedTodayItem(messageId);
      openItemPreview(item);
      return;
    }
    const openSelectedGmailButton = event.target.closest("[data-ea-action='open-selected-gmail']");
    if (openSelectedGmailButton) {
      event.preventDefault();
      return openSelectedEmailInGmail();
    }
    const openChangedGmailButton = event.target.closest("[data-ea-open-changed-gmail]");
    if (openChangedGmailButton) {
      event.preventDefault();
      const messageId = openChangedGmailButton.getAttribute("data-ea-open-changed-gmail") || "";
      return openGmailItem(findSummaryItem(messageId) || findChangedTodayItem(messageId));
    }
    const relatedItemButton = event.target.closest("[data-ea-related-item]");
    if (relatedItemButton) {
      event.preventDefault();
      const item = findSummaryItem(relatedItemButton.getAttribute("data-ea-related-item") || "");
      openItemPreview(item);
      return;
    }
    const queueButton = event.target.closest("[data-ea-action='open-needs-attention']");
    if (queueButton) {
      event.preventDefault();
      activeSummaryFilter = "needs_attention_items";
      openFirstSummaryItemIfHelpful(activeSummaryFilter);
      return;
    }
    const previewButton = event.target.closest("[data-ea-action='preview-teach']");
    if (previewButton) {
      event.preventDefault();
      return previewTeach();
    }
    const retryPreviewButton = event.target.closest("[data-ea-action='retry-preview-teach']");
    if (retryPreviewButton) {
      event.preventDefault();
      return previewTeach();
    }
    const clearButton = event.target.closest("[data-ea-action='clear-teach']");
    if (clearButton) {
      event.preventDefault();
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = null;
      unsubscribeResult = "";
      teachDraft = { targetLabel: "", note: "" };
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const refineButton = event.target.closest("[data-ea-action='refine-teach']");
    if (refineButton) {
      event.preventDefault();
      previousTeachPreview = teachPreview;
      teachPreview = null;
      teachResult = null;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const applyButton = event.target.closest("[data-ea-apply]");
    if (applyButton) {
      event.preventDefault();
      return applyTeach(applyButton.getAttribute("data-ea-apply"));
    }
    const detailsButton = event.target.closest("[data-ea-action='toggle-details']");
    if (detailsButton) {
      event.preventDefault();
      detailsExpanded = !detailsExpanded;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const unsubscribeButton = event.target.closest("[data-ea-action='select-unsubscribe']");
    if (unsubscribeButton) {
      event.preventDefault();
      return selectUnsubscribeCurrent();
    }
    const returnButton = event.target.closest("[data-ea-action='return-to-live']");
    if (returnButton) {
      event.preventDefault();
      manualPreviewContext = null;
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = null;
      unsubscribeResult = "";
      previousPayload = "";
      if (lastHarnessState) {
        lastSidebarState = lastHarnessState.sidebar_state || lastSidebarState;
        renderState(lastHarnessState);
      }
      refreshSelection(true);
    }
  }

  function openFirstSummaryItemIfHelpful(filter) {
    const items = summaryItemsForFilter(filter);
    if (!items.length) {
      if (lastHarnessState) {
        renderState(lastHarnessState);
      }
      return;
    }
    const currentMessageId = ((lastSidebarState || {}).selected_email || {}).message_id || "";
    if (manualPreviewContext && currentMessageId && items.some((item) => item.message_id === currentMessageId)) {
      if (lastHarnessState) {
        renderState(lastHarnessState);
      }
      return;
    }
    const firstItem = items[0];
    openItemPreview(firstItem);
  }

  function handlePanelInput(event) {
    if (
      event.target?.id === "ea-target-label" ||
      event.target?.id === "ea-teach-note"
    ) {
      syncTeachDraftFromDom();
    }
    if (event.target?.id === "ea-feedback-note") {
      feedbackDraft = event.target.value || "";
    }
  }

  async function previewTeach() {
    if (!lastSidebarState || !lastSidebarState.selected_email || !lastSidebarState.selected_email.found) {
      return;
    }
    syncTeachDraftFromDom();
    const targetLabel = teachDraft.targetLabel;
    const note = teachDraft.note;
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-preview",
      method: "POST",
      body: {
        selected_context: lastSidebarState.selected_context || {},
        target_label: targetLabel,
        note,
        scope: "sender",
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        teachResult = teachErrorResult("preview", chrome.runtime.lastError.message || "Could not preview the lesson.");
        teachPreview = null;
      } else if (!response || !response.ok) {
        teachResult = teachErrorResult("preview", (response && (response.payload?.error || response.error)) || "Could not preview the lesson.");
        teachPreview = null;
      } else {
        teachResult = null;
        teachPreview = response.payload;
        unsubscribeResult = "";
      }
      renderState(lastSidebarState);
    });
  }

  async function applyTeach(mode) {
    if (!lastSidebarState || !lastSidebarState.selected_email || !lastSidebarState.selected_email.found) {
      return;
    }
    syncTeachDraftFromDom();
    const targetLabel = teachDraft.targetLabel;
    const note = teachDraft.note;
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-apply",
      method: "POST",
      body: {
        selected_context: lastSidebarState.selected_context || {},
        target_label: targetLabel,
        note,
        scope: "sender",
        mode,
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        teachResult = teachErrorResult("apply", chrome.runtime.lastError.message || "Could not apply the lesson.");
        renderState(lastSidebarState);
        return;
      }
      if (!response || !response.ok) {
        teachResult = teachErrorResult("apply", (response && (response.payload?.error || response.error)) || "Could not apply the lesson.");
        renderState(lastSidebarState);
        return;
      }
      const payload = response.payload || {};
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = {
        kind: "apply-success",
        title: "Lesson applied",
        message: payload.acknowledgment || "Lesson applied.",
      };
      unsubscribeResult = "";
      teachDraft = { targetLabel: "", note: "" };
      renderState(payload.sidebar_state || lastSidebarState);
    });
  }

  async function selectUnsubscribeCurrent() {
    if (!lastSidebarState || !lastSidebarState.selected_email || !lastSidebarState.selected_email.found) {
      return;
    }
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/unsubscribe-select-current",
      method: "POST",
      body: {
        selected_context: lastSidebarState.selected_context || {},
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        unsubscribeResult = chrome.runtime.lastError.message || "Could not queue the unsubscribe candidate.";
        renderState(lastSidebarState);
        return;
      }
      if (!response || !response.ok) {
        unsubscribeResult = (response && (response.payload?.error || response.error)) || "Could not queue the unsubscribe candidate.";
        renderState(lastSidebarState);
        return;
      }
      const payload = response.payload || {};
      unsubscribeResult = payload.acknowledgment || "Queued for unsubscribe review.";
      renderState(payload.sidebar_state || lastSidebarState);
      refreshSelection(true);
    });
  }

  function currentDraftTargetLabel(selected) {
    return teachDraft.targetLabel || "";
  }

  function syncTeachDraftFromDom() {
    const selectNode = document.getElementById("ea-target-label");
    const noteNode = document.getElementById("ea-teach-note");
    teachDraft = {
      targetLabel: selectNode?.value || teachDraft.targetLabel || "",
      note: noteNode?.value || "",
    };
  }

  function humanDecisionSource(reviewAction) {
    if (!reviewAction) {
      return "No prior decision recorded";
    }
    return {
      "auto-approve": "Auto-approved by current rules",
      approve: "Previously reviewed locally",
      "sidebar-current-only": "Taught on this email only",
      "sidebar-matching-existing": "Taught and rewrote matching stored emails",
      "sidebar-future-only": "Saved as a future lesson",
    }[reviewAction] || reviewAction.replaceAll("-", " ");
  }

  function humanWriteStatus(writeStatus) {
    if (!writeStatus) {
      return "Not written to Gmail";
    }
    return {
      applied: "Written to Gmail",
      skipped: "Skipped Gmail write",
      failed: "Gmail write failed",
    }[writeStatus] || writeStatus;
  }

  function humanInboxStatus(inboxStatus) {
    if (!inboxStatus) {
      return "Inbox unchanged";
    }
    return {
      applied: "Removed from inbox",
      skipped: "Left in inbox",
      failed: "Inbox update failed",
    }[inboxStatus] || inboxStatus;
  }

  function installTestHooks() {
    globalThis.__eaTestHooks = {
      getSnapshot() {
        return {
          previousPayload,
          activeSummaryFilter,
        manualPreviewContext,
        detailsExpanded,
        lastLiveContext,
        selectedContext: lastSidebarState?.selected_context || {},
        selectedEmail: lastSidebarState?.selected_email || null,
          recentCount: (lastHarnessState?.recent_items || []).length,
          needsAttentionCount: (lastHarnessState?.needs_attention_items || []).length,
        };
      },
      selectSummaryItem(messageId) {
        const item = findSummaryItem(messageId);
        if (!item) {
          return { ok: false, error: "item-not-found" };
        }
        openItemPreview(item);
        return { ok: true, messageId: item.message_id || "", subject: item.subject || "" };
      },
      selectSummaryFilter(filter) {
        if (!filter) {
          return { ok: false, error: "missing-filter" };
        }
        activeSummaryFilter = filter;
        openFirstSummaryItemIfHelpful(filter);
        return { ok: true, filter };
      },
      setDraft(targetLabel, note) {
        if (typeof targetLabel === "string" && targetLabel) {
          teachDraft.targetLabel = targetLabel;
        }
        if (typeof note === "string") {
          teachDraft.note = note;
        }
        const selectNode = document.getElementById("ea-target-label");
        const noteNode = document.getElementById("ea-teach-note");
        if (selectNode && teachDraft.targetLabel) {
          selectNode.value = teachDraft.targetLabel;
        }
        if (noteNode) {
          noteNode.value = teachDraft.note;
        }
        return { ok: true, draft: { ...teachDraft } };
      },
      getDraft() {
        syncTeachDraftFromDom();
        return { ...teachDraft };
      },
      forceRefresh() {
        syncTeachDraftFromDom();
        refreshSelection(true);
        return { ok: true };
      },
      previewTeach(targetLabel, note) {
        if (!lastSidebarState || !lastSidebarState.selected_email || !lastSidebarState.selected_email.found) {
          return { ok: false, error: "selected-email-not-found" };
        }
        teachDraft = {
          targetLabel: targetLabel || teachDraft.targetLabel || "",
          note: note || "",
        };
        const selectNode = document.getElementById("ea-target-label");
        const noteNode = document.getElementById("ea-teach-note");
        if (selectNode && targetLabel) {
          selectNode.value = targetLabel;
        }
        if (noteNode) {
          noteNode.value = note || "";
        }
        previewTeach();
        return {
          ok: true,
          targetLabel: teachDraft.targetLabel,
          note: teachDraft.note,
        };
      },
      returnToLive() {
        manualPreviewContext = null;
        teachPreview = null;
        previousTeachPreview = null;
        teachResult = null;
        unsubscribeResult = "";
        refreshSelection(true);
        return { ok: true };
      },
    };
  }

  function teardown() {
    if (refreshIntervalId !== null) {
      window.clearInterval(refreshIntervalId);
      refreshIntervalId = null;
    }
    if (hashChangeListener) {
      window.removeEventListener("hashchange", hashChangeListener);
      hashChangeListener = null;
    }
    if (documentClickListener) {
      document.removeEventListener("click", documentClickListener);
      documentClickListener = null;
    }
    if (
      runtimeMessageListener &&
      chrome?.runtime?.onMessage &&
      typeof chrome.runtime.onMessage.removeListener === "function"
    ) {
      chrome.runtime.onMessage.removeListener(runtimeMessageListener);
    }
    runtimeMessageListener = null;
    const root = document.getElementById(ROOT_ID);
    if (root) {
      root.remove();
    }
    delete globalThis.__eaTestHooks;
    delete globalThis[SINGLETON_KEY];
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  boot();
})();
