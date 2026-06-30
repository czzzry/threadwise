(() => {
  const SINGLETON_KEY = "__eaCompanionSingleton";
  if (globalThis[SINGLETON_KEY] && typeof globalThis[SINGLETON_KEY].teardown === "function") {
    globalThis[SINGLETON_KEY].teardown();
  }
  const ROOT_ID = "email-agent-companion-root";
  const LOCAL_ORIGIN = "http://127.0.0.1:8021";
  const PANEL_WIDTH = "392px";
  const PANEL_WIDTH_MINIMIZED = "84px";
  let minimized = false;
  let previousPayload = "";
  let lastHarnessState = null;
  let lastSidebarState = null;
  let teachPreview = null;
  let previousTeachPreview = null;
  let teachResult = "";
  let unsubscribeResult = "";
  let activeSummaryFilter = "needs_attention_items";
  let detailsExpanded = false;
  let teachDraft = {
    targetLabel: "",
    note: "",
  };
  let manualPreviewContext = null;
  let lastLiveContext = null;
  let trustedHtmlPolicy = null;
  let refreshIntervalId = null;
  let hashChangeListener = null;
  let documentClickListener = null;
  let runtimeMessageListener = null;

  function boot() {
    ensureRoot();
    installTestHooks();
    refreshSelection();
    refreshIntervalId = window.setInterval(refreshSelection, 1200);
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
      <div id="ea-panel" style="background:rgba(255,253,248,0.98);border:1px solid rgba(215,207,191,0.95);border-radius:22px;box-shadow:0 20px 60px rgba(31,26,20,0.16);overflow:hidden;font-family:Georgia,'Times New Roman',serif;color:#1f1a14;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:16px 16px 14px;border-bottom:1px solid #d7cfbf;background:linear-gradient(180deg,#fff8eb 0%,#f6eedf 100%);">
          <div style="display:grid;gap:6px;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="width:10px;height:10px;border-radius:999px;background:#0f766e;box-shadow:0 0 0 4px rgba(15,118,110,0.12);"></span>
              <div style="font-size:1.08rem;font-weight:700;">Threadwise</div>
            </div>
            <div id="ea-subtitle" style="color:#6b6255;font-size:0.88rem;line-height:1.35;">Connecting to local companion server</div>
          </div>
          <button id="ea-minimize" type="button" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:8px 12px;cursor:pointer;font:inherit;">Minimize</button>
        </div>
        <div id="ea-content" style="padding:14px;display:grid;gap:12px;">
          <section style="border:1px solid #d7cfbf;border-radius:18px;padding:14px;background:linear-gradient(180deg,#fffdfa 0%,#faf5ea 100%);">
            <div style="color:#6b6255;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;">Selected Email</div>
            <div id="ea-selected-email"></div>
          </section>
          <section style="border:1px solid #d7cfbf;border-radius:16px;padding:14px;background:#fffdfa;">
            <div style="color:#6b6255;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;">Today</div>
            <div id="ea-daily-summary"></div>
          </section>
        </div>
        <div id="ea-footer" style="padding:0 14px 14px;">
          <div style="border:1px dashed #d7cfbf;border-radius:16px;padding:12px 14px;background:rgba(255,255,255,0.55);color:#6b6255;font-size:0.84rem;line-height:1.4;">
            Live Gmail sidebar mode is using the same stored inbox snapshot and queue buckets as the local harness.
          </div>
        </div>
      </div>
    `);
    document.body.appendChild(root);

    root.querySelector("#ea-minimize").addEventListener("click", () => {
      minimized = !minimized;
      renderMinimized();
    });
    root.addEventListener("click", handlePanelClick);
    root.addEventListener("input", handlePanelInput);
    root.addEventListener("change", handlePanelInput);
    renderMinimized();
  }

  function renderMinimized() {
    const root = document.getElementById(ROOT_ID);
    if (!root) {
      return;
    }
    const content = root.querySelector("#ea-content");
    const footer = root.querySelector("#ea-footer");
    const button = root.querySelector("#ea-minimize");
    if (!content || !footer || !button) {
      return;
    }
    content.style.display = minimized ? "none" : "grid";
    footer.style.display = minimized ? "none" : "block";
    root.style.width = minimized ? PANEL_WIDTH_MINIMIZED : PANEL_WIDTH;
    button.textContent = minimized ? "Open" : "Minimize";
  }

  function selectedContext() {
    const messageNode = selectedMessageNode();
    const senderNode = selectedSenderNode(messageNode);
    return {
      provider: "gmail",
      message_id: messageNode
        ? messageNode.getAttribute("data-legacy-message-id") ||
          messageNode.getAttribute("data-message-id") ||
          ""
        : "",
      thread_id: messageNode ? messageNode.getAttribute("data-thread-perm-id") || "" : "",
      subject: firstText(["h2[data-thread-perm-id]", "h2.hP", "h2[role='heading']"]),
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
    teachResult = "";
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
    previousPayload = payload;
    chrome.runtime.sendMessage({ type: "email-agent:get-state", context }, (response) => {
      if (chrome.runtime.lastError) {
        renderError(chrome.runtime.lastError.message || "Could not reach extension background.");
        return;
      }
      if (!response || !response.ok) {
        renderError((response && response.error) || "Could not reach local companion server.");
        return;
      }
      renderState(response.payload);
    });
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
    return Boolean(context && (context.message_id || context.subject || context.sender));
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

  function renderError(message) {
    const subtitle = document.getElementById("ea-subtitle");
    const selectedEmailNode = document.getElementById("ea-selected-email");
    const dailySummaryNode = document.getElementById("ea-daily-summary");
    if (subtitle) {
      subtitle.textContent = "Connection failed";
    }
    if (selectedEmailNode) {
      setHtml(selectedEmailNode, `<div style="margin-top:10px;color:#8a4b00;line-height:1.45;">${escapeHtml(message)}</div>`);
    }
    if (dailySummaryNode) {
      setHtml(dailySummaryNode, `<div style="margin-top:10px;color:#6b6255;line-height:1.45;">Make sure the local companion server is running on 127.0.0.1:8021.</div>`);
    }
  }

  function renderState(state) {
    lastHarnessState = normalizeHarnessState(state);
    lastSidebarState = lastHarnessState.sidebar_state;
    const subtitle = document.getElementById("ea-subtitle");
    const selectedEmailNode = document.getElementById("ea-selected-email");
    const dailySummaryNode = document.getElementById("ea-daily-summary");
    if (!subtitle || !selectedEmailNode || !dailySummaryNode) {
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

    subtitle.textContent = showingQueuePreview
      ? "Queue preview loaded"
      : selected && selected.found
        ? "Selected email loaded"
        : "Compact daily summary";
    if (!selected || !selected.found) {
      const hasSnapshotMiss = selected && selected.status === "not-in-snapshot";
      const title = hasSnapshotMiss
        ? "This email is not in the current local sync."
        : "Open any email in Gmail and this panel will switch from summary mode into message mode.";
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
        <div style="margin-top:12px;color:#6b6255;line-height:1.45;">The agent can only explain and teach from the latest stored sync, so use a queue item below for now or rerun the Gmail sync.</div>
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
      const previewHtml = teachPreview
        ? `${renderPreviousTeachPreviewHtml(previousTeachPreview)}${renderTeachPreviewHtml(teachPreview)}`
        : teachResult
          ? `<div style="margin-top:12px;border-radius:14px;background:#d8f3ef;padding:12px;color:#0f766e;line-height:1.45;">
              <div style="font-weight:700;">Lesson applied</div>
              <div style="margin-top:8px;">${escapeHtml(teachResult)}</div>
            </div>`
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
      const detailsButtonLabel = detailsExpanded ? "Hide details" : "Show details";
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
      const unsubscribeLine = unsubscribe
        ? `
          <div style="margin-top:14px;border-radius:14px;background:#f5efe2;padding:12px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Unsubscribe</div>
            <div style="margin-top:8px;color:#1f1a14;line-height:1.45;font-weight:700;">${escapeHtml(unsubscribe.display_name || selected.sender || "Subscription")}</div>
            <div style="margin-top:6px;color:#6b6255;line-height:1.45;">${escapeHtml((unsubscribePreview && unsubscribePreview.notes) || "Unsubscribe available")}</div>
            ${unsubscribeResult ? `<div style="margin-top:12px;border-radius:14px;background:#d8f3ef;padding:12px;color:#0f766e;line-height:1.45;">${escapeHtml(unsubscribeResult)}</div>` : ""}
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
              ${unsubscribePreview && unsubscribePreview.status === "ready" ? '<button type="button" data-ea-action="select-unsubscribe" style="border:0;background:#1f6f8b;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Queue unsubscribe review</button>' : ""}
              ${unsubscribePreview && unsubscribePreview.url ? `<a href="${escapeHtml(unsubscribePreview.url)}"${unsubscribePreview.url.startsWith("http") ? ' target="_blank" rel="noreferrer"' : ''} style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;display:inline-flex;align-items:center;text-decoration:none;font:inherit;">${unsubscribePreview.url.startsWith("http") ? "Open unsubscribe" : "Open mail unsubscribe"}</a>` : ""}
              <a href="${escapeHtml(`${LOCAL_ORIGIN}${unsubscribe.handoff_path || "/unsubscribe-review"}`)}" target="_blank" rel="noreferrer" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;display:inline-flex;align-items:center;text-decoration:none;font:inherit;">${reviewLinkLabel}</a>
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
              <button type="button" data-ea-action="return-to-live" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Back to inbox email</button>
            </div>
          </div>
        `
        : "";
      const overviewCard = `
        <div style="margin-top:14px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Agent view</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
            <div style="border-radius:12px;background:#fffdfa;padding:10px 12px;">
              <div style="font-size:0.72rem;color:#6b6255;text-transform:uppercase;letter-spacing:0.08em;">Category</div>
              <div style="margin-top:6px;font-weight:700;line-height:1.3;">${escapeHtml(selected.classification || "Uncategorized")}</div>
            </div>
            <div style="border-radius:12px;background:#fffdfa;padding:10px 12px;">
              <div style="font-size:0.72rem;color:#6b6255;text-transform:uppercase;letter-spacing:0.08em;">Handling</div>
              <div style="margin-top:6px;font-weight:700;line-height:1.3;">${escapeHtml(selected.status_label || "Unknown")}</div>
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
        <div style="margin-top:8px;font-size:1.08rem;font-weight:700;line-height:1.2;">${escapeHtml(selected.subject || "(no subject)")}</div>
        <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.sender || "(unknown sender)")}</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#efe7d4;color:#5f512f;font-size:0.82rem;">${escapeHtml(selected.classification || "Uncategorized")}</span>
          <span style="${statusStyle}">${escapeHtml(selected.status_label)}</span>
        </div>
        ${previewModeBanner}
        ${overviewCard}
        ${nextStepCard}
        <div style="margin-top:14px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Why</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(selected.reason || "No short reason is stored yet.")}</div>
        </div>
        <div style="margin-top:14px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Details</div>
            <button type="button" data-ea-action="toggle-details" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:7px 10px;cursor:pointer;font:inherit;">${detailsButtonLabel}</button>
          </div>
          ${detailsHtml}
        </div>
        ${unsubscribeLine}
        <div style="margin-top:14px;border-top:1px solid #e5dccb;padding-top:14px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Correct / Teach</div>
          <div style="display:grid;gap:8px;margin-top:10px;">
            <select id="ea-target-label" style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid #d7cfbf;background:#fffdfa;color:#1f1a14;font:inherit;">
              ${labelOptions}
            </select>
            <textarea id="ea-teach-note" rows="3" placeholder="Tell the agent what it got wrong or what it should learn." style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid #d7cfbf;background:#fffdfa;color:#1f1a14;font:inherit;resize:vertical;">${escapeHtml(teachDraft.note)}</textarea>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <button type="button" data-ea-action="preview-teach" style="border:0;background:#0f766e;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Preview lesson</button>
              <button type="button" data-ea-action="clear-teach" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Clear</button>
            </div>
          </div>
          ${previewHtml}
        </div>
      `);
    }

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
      `border:0;border-radius:14px;background:${activeSummaryFilter === key ? "#e7f6f4" : "#f5efe2"};box-shadow:${activeSummaryFilter === key ? "inset 0 0 0 1px rgba(15,118,110,0.22)" : "none"};padding:12px;text-align:left;cursor:pointer;font:inherit;color:#1f1a14;`;
    const keptVisibleCount = summary.kept_visible_count ?? countForFilter("kept_visible_items");
    setHtml(dailySummaryNode, `
      <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${summary.run_count > 1 ? `Rolling view across the last ${summary.run_count} Gmail runs` : "Latest run snapshot"}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;">
        <button type="button" data-ea-summary-filter="recent_items" style="${metricButtonStyle("recent_items")}"><strong style="display:block;font-size:1.15rem;">${summary.processed_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">processed</span></button>
        <button type="button" data-ea-summary-filter="auto_handled_items" style="${metricButtonStyle("auto_handled_items")}"><strong style="display:block;font-size:1.15rem;">${summary.auto_handled_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">auto-handled</span></button>
        <button type="button" data-ea-summary-filter="needs_attention_items" style="${metricButtonStyle("needs_attention_items")}"><strong style="display:block;font-size:1.15rem;">${summary.needs_attention_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">need attention</span></button>
        <button type="button" data-ea-summary-filter="kept_visible_items" style="${metricButtonStyle("kept_visible_items")}"><strong style="display:block;font-size:1.15rem;">${keptVisibleCount || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">kept visible</span></button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
        <span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">Unsubscribe candidates - ${summary.unsubscribe_candidate_count || 0}</span>
        ${summary.report_date ? `<span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">Latest report - ${escapeHtml(summary.report_date)}</span>` : ""}
      </div>
      <div style="margin-top:12px;border-radius:14px;background:#eef7f5;padding:12px;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Viewing</div>
        <div style="margin-top:8px;font-weight:700;line-height:1.35;">${escapeHtml(focus.label)} · ${focus.count}</div>
        <div style="margin-top:6px;color:#1f1a14;line-height:1.45;">${escapeHtml(focus.description)}</div>
      </div>
      <div style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">What Changed Today</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
          <div style="border-radius:14px;background:#fffdfa;padding:12px;"><strong style="display:block;font-size:1.15rem;">${changedToday.label_writes_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">labels written</span></div>
          <div style="border-radius:14px;background:#fffdfa;padding:12px;"><strong style="display:block;font-size:1.15rem;">${changedToday.inbox_removed_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">removed from inbox</span></div>
          <div style="border-radius:14px;background:#fffdfa;padding:12px;"><strong style="display:block;font-size:1.15rem;">${changedToday.taught_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">teaching changes</span></div>
          <div style="border-radius:14px;background:#fffdfa;padding:12px;"><strong style="display:block;font-size:1.15rem;">${changedToday.selected_unsubscribe_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">unsubscribe queued</span></div>
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
        <div style="margin-top:12px;display:grid;gap:8px;">${
          (changedToday.items || []).length
            ? (changedToday.items || []).map((item) => `
              <button type="button" data-ea-changed-item="${escapeHtml(item.message_id || "")}" style="width:100%;text-align:left;border:1px solid #d7cfbf;border-radius:14px;background:#fffdfa;padding:10px 12px;color:#1f1a14;cursor:pointer;font:inherit;">
                <div style="font-size:0.95rem;font-weight:700;line-height:1.25;">${escapeHtml(item.subject || "(no subject)")}</div>
                <div style="margin-top:4px;color:#6b6255;font-size:0.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</div>
                <div style="margin-top:6px;color:#6b6255;line-height:1.45;">${escapeHtml(item.change_summary || "")}</div>
              </button>
            `).join("")
            : '<div style="color:#6b6255;line-height:1.45;">No tracked agent changes in this stored batch yet.</div>'
        }</div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
        <a href="${LOCAL_ORIGIN}/daily-dashboard" target="_blank" rel="noreferrer" style="border:0;background:#0f766e;color:#fff;border-radius:999px;padding:9px 12px;display:inline-flex;align-items:center;text-decoration:none;font:inherit;">Open daily dashboard</a>
        <a href="${LOCAL_ORIGIN}/unsubscribe-review" target="_blank" rel="noreferrer" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;display:inline-flex;align-items:center;text-decoration:none;font:inherit;">Review unsubscribe candidates</a>
      </div>
      ${
        (summary.top_labels || []).length
          ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">${topLabels}</div>`
          : '<p style="margin-top:12px;color:#6b6255;line-height:1.45;">No stored label mix yet.</p>'
      }
      <p style="color:#6b6255;font-size:0.85rem;margin-top:12px;">Source: ${escapeHtml(summary.source_label || "stored Gmail snapshot")}${summary.batch_id ? ` - ${escapeHtml(summary.batch_id)}` : ""}</p>
      <div style="margin-top:12px;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(bucketLabelForFilter(activeSummaryFilter))}</div>
      <div style="margin-top:10px;display:grid;gap:8px;">${renderSummaryItemCards(summaryItemsForFilter(activeSummaryFilter))}</div>
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
          </button>
        `;
      })
      .join("");
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

  function renderTeachPreviewHtml(preview) {
    const impact = preview.impact || {};
    const matchingCount = impact.matching_existing_count || 0;
    const severityTone = matchingCount >= 50
      ? { bg: "#fff4dd", fg: "#8a4b00", label: "Large existing-email change" }
      : matchingCount > 0
        ? { bg: "#eef7f5", fg: "#0f766e", label: "Existing-email change to confirm" }
        : { bg: "#eef7f5", fg: "#0f766e", label: "Future-facing lesson" };
    const targetLabelName = humanLabelNameFromId((preview.selected_label_after || [])[0] || "");
    const examples = (impact.matching_existing_examples || [])
      .map(
        (item) =>
          `<li>${escapeHtml(item.subject || "(no subject)")} - ${escapeHtml(item.sender || "(unknown sender)")}</li>`,
      )
      .join("");
    return `
      <div style="margin-top:12px;border-radius:14px;background:#fff8eb;padding:12px;color:#1f1a14;line-height:1.45;">
        <div style="font-weight:700;">${escapeHtml(preview.acknowledgment || "Preview ready.")}</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:${severityTone.bg};color:${severityTone.fg};font-size:0.82rem;">${escapeHtml(severityTone.label)}</span>
          <span style="display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#f1eadb;color:#5d5342;font-size:0.82rem;">Current email -> ${escapeHtml(targetLabelName)}</span>
          <span style="display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#f1eadb;color:#5d5342;font-size:0.82rem;">Matching existing emails: ${matchingCount}</span>
        </div>
        <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${escapeHtml(previewChoiceExplainer(matchingCount))}</div>
        <div style="margin-top:10px;border-radius:12px;background:#fffdfa;padding:10px 12px;color:#6b6255;line-height:1.45;">
          <div><strong style="color:#1f1a14;">Apply only to this email</strong> changes the current message only.</div>
          <div style="margin-top:6px;"><strong style="color:#1f1a14;">Apply to current + ${matchingCount} matching emails</strong> rewrites those existing stored emails too.</div>
          <div style="margin-top:6px;"><strong style="color:#1f1a14;">Apply to current + future emails only</strong> saves the lesson without rewriting other stored emails today.</div>
        </div>
        ${
          examples
            ? `<ol style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${examples}</ol>`
            : ""
        }
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-apply="current-only" style="border:0;background:#0f766e;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Apply only to this email</button>
          <button type="button" data-ea-apply="matching-existing" style="border:0;background:#1f6f8b;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Apply to current + ${matchingCount} matching emails</button>
          <button type="button" data-ea-apply="future-only" style="border:0;background:#7b5d2a;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Apply to current + future emails only</button>
          <button type="button" data-ea-action="refine-teach" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Keep discussing</button>
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
      <div data-ea-previous-preview="true" style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;color:#1f1a14;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Previous interpretation</div>
        <div style="margin-top:8px;font-weight:700;">${escapeHtml(previousPreview.acknowledgment || "Previous preview")}</div>
        <div style="margin-top:6px;color:#6b6255;">Would relabel to ${escapeHtml(targetLabelName)} and change ${impact.matching_existing_count || 0} existing emails.</div>
        <div style="margin-top:6px;color:#6b6255;">Use this to compare the old understanding against the current one before you confirm anything broader.</div>
      </div>
    `;
  }

  function previewChoiceExplainer(matchingCount) {
    if (matchingCount > 0) {
      return "Nothing beyond the current email changes unless you explicitly approve it. Use the broader apply option only if this lesson really should rewrite those stored emails too.";
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
    const summaryFilterButton = event.target.closest("[data-ea-summary-filter]");
    if (summaryFilterButton) {
      event.preventDefault();
      activeSummaryFilter = summaryFilterButton.getAttribute("data-ea-summary-filter") || "needs_attention_items";
      openFirstSummaryItemIfHelpful(activeSummaryFilter);
      return;
    }
    const summaryItemButton = event.target.closest("[data-ea-summary-item]");
    if (summaryItemButton) {
      event.preventDefault();
      const item = findSummaryItem(summaryItemButton.getAttribute("data-ea-summary-item") || "");
      openItemPreview(item);
      return;
    }
    const changedItemButton = event.target.closest("[data-ea-changed-item]");
    if (changedItemButton) {
      event.preventDefault();
      const item = findSummaryItem(changedItemButton.getAttribute("data-ea-changed-item") || "");
      openItemPreview(item);
      return;
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
    const clearButton = event.target.closest("[data-ea-action='clear-teach']");
    if (clearButton) {
      event.preventDefault();
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = "";
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
      teachResult = "";
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
      teachResult = "";
      unsubscribeResult = "";
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
        teachResult = chrome.runtime.lastError.message || "Could not preview the lesson.";
        teachPreview = null;
      } else if (!response || !response.ok) {
        teachResult = (response && (response.payload?.error || response.error)) || "Could not preview the lesson.";
        teachPreview = null;
      } else {
        teachResult = "";
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
        teachResult = chrome.runtime.lastError.message || "Could not apply the lesson.";
        teachPreview = null;
        renderState(lastSidebarState);
        return;
      }
      if (!response || !response.ok) {
        teachResult = (response && (response.payload?.error || response.error)) || "Could not apply the lesson.";
        teachPreview = null;
        renderState(lastSidebarState);
        return;
      }
      const payload = response.payload || {};
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = payload.acknowledgment || "Lesson applied.";
      unsubscribeResult = "";
      teachDraft = { targetLabel: "", note: "" };
      renderState(payload.sidebar_state || lastSidebarState);
      refreshSelection(true);
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
    return teachDraft.targetLabel || selected.internal_label || "";
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
        teachResult = "";
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
