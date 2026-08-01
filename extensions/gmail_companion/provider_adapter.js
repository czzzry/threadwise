(() => {
  function createProviderPageAdapter(browserWindow, browserDocument) {
    if (!browserWindow?.location || !browserDocument) {
      throw new Error("Threadwise provider adapter requires a browser window and document.");
    }
    return browserWindow.location.hostname === "mail.proton.me"
      ? protonAdapter(browserWindow, browserDocument)
      : gmailAdapter(browserWindow, browserDocument);
  }

  function gmailAdapter(browserWindow, browserDocument) {
    function routeHasOpenMessage() {
      const hash = browserWindow.location.hash || "";
      if (!hash || hash === "#inbox") return false;
      const parts = hash.replace(/^#/, "").split("/").filter(Boolean);
      if (parts.length < 2) return false;
      const lastPart = decodeURIComponent(parts[parts.length - 1] || "");
      return Boolean(lastPart && /^(FM|msg|thread|[a-f0-9]{8,})/i.test(lastPart));
    }

    function selectedContext() {
      if (!routeHasOpenMessage()) return emptyContext("gmail", browserWindow.location.href);
      const subject = firstText(browserDocument, [
        "h2[data-thread-perm-id]",
        "h2.hP",
        "h2[role='heading']",
      ]);
      const messageNode = subject
        ? selectedGmailMessageNode(browserWindow, browserDocument)
        : null;
      const senderNode = selectedGmailSenderNode(browserDocument, messageNode);
      const gmailLabels = Array.from(
        browserDocument.querySelectorAll('[aria-label^="Search for all messages with label EA/"]'),
      )
        .map((node) => (node.textContent || "").trim())
        .filter(Boolean);
      return {
        provider: "gmail",
        message_id: messageNode
          ? messageNode.getAttribute("data-legacy-message-id")
            || messageNode.getAttribute("data-message-id")
            || ""
          : "",
        thread_id: messageNode?.getAttribute("data-thread-perm-id") || "",
        subject,
        sender: senderNode
          ? (senderNode.getAttribute("email") || senderNode.textContent || "").trim()
          : "",
        gmail_labels: [...new Set(gmailLabels)].join(","),
        page_url: browserWindow.location.href,
        selected_at: new Date().toISOString(),
      };
    }

    return Object.freeze({
      id: "gmail",
      name: "Gmail",
      canRunManualSync: true,
      hasOpenMessage: routeHasOpenMessage,
      selectedContext,
      messageUrl: gmailMessageUrl,
    });
  }

  function protonAdapter(browserWindow, browserDocument) {
    function messageReference() {
      const parts = browserWindow.location.pathname.split("/").filter(Boolean);
      const mailboxIndex = parts.findIndex((part) => [
        "inbox", "all-mail", "archive", "sent", "drafts", "trash", "spam", "starred",
      ].includes(part));
      if (mailboxIndex < 0 || parts.length <= mailboxIndex + 1) return "";
      return decodeURIComponent(parts[mailboxIndex + 1] || "");
    }

    function selectedContext() {
      const providerRef = messageReference();
      if (!providerRef) return emptyContext("protonmail", browserWindow.location.href, {
        provider_labels: "",
      });
      const subject = firstText(browserDocument, [
        '[data-testid="conversation-header:subject"]',
        '[data-testid="message-view:subject"]',
        '[data-testid*="conversation-header"] h1',
        "main h1",
        "main h2",
      ]);
      const providerLabels = Array.from(
        browserDocument.querySelectorAll('[data-testid*="label"], [class*="label"]'),
      )
        .map((node) => (node.textContent || "").trim())
        .filter((value) => value.startsWith("EA/"));
      return {
        provider: "protonmail",
        message_id: "",
        thread_id: "",
        subject,
        sender: protonSenderText(browserDocument),
        provider_labels: [...new Set(providerLabels)].join(","),
        provider_ref: providerRef,
        page_url: browserWindow.location.href,
        selected_at: new Date().toISOString(),
      };
    }

    return Object.freeze({
      id: "protonmail",
      name: "Proton Mail",
      canRunManualSync: false,
      hasOpenMessage: () => Boolean(messageReference()),
      selectedContext,
      messageUrl: protonMessageUrl,
    });
  }

  function emptyContext(provider, pageUrl, extra = {}) {
    return {
      provider,
      message_id: "",
      thread_id: "",
      subject: "",
      sender: "",
      ...extra,
      page_url: pageUrl,
      selected_at: new Date().toISOString(),
    };
  }

  function firstText(browserDocument, selectors) {
    for (const selector of selectors) {
      const text = (browserDocument.querySelector(selector)?.textContent || "").trim();
      if (text) return text;
    }
    return "";
  }

  function selectedGmailMessageNode(browserWindow, browserDocument) {
    const visibleCandidates = Array.from(
      browserDocument.querySelectorAll("[data-legacy-message-id], [data-message-id]"),
    ).filter((node) => isVisibleNode(browserWindow, node));
    return visibleCandidates[visibleCandidates.length - 1]
      || browserDocument.querySelector("[data-legacy-message-id]")
      || browserDocument.querySelector("[data-message-id]");
  }

  function selectedGmailSenderNode(browserDocument, messageNode) {
    const root = messageNode?.closest?.(
      "[role='listitem'], .adn, .ii, .h7, [data-thread-perm-id]",
    ) || browserDocument;
    return root.querySelector?.("[email][data-hovercard-id]")
      || root.querySelector?.("span[email]")
      || browserDocument.querySelector("[email][data-hovercard-id]")
      || browserDocument.querySelector("span[email]");
  }

  function isVisibleNode(browserWindow, node) {
    if (!node || typeof node.getBoundingClientRect !== "function") return false;
    const style = browserWindow.getComputedStyle(node);
    if (!style || style.display === "none" || style.visibility === "hidden") return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function protonSenderText(browserDocument) {
    const selectors = [
      '[data-testid="message-header:sender-address"]',
      '[data-testid="message-header:sender"]',
      '[data-testid*="message-header"] [title*="@"]',
      '[data-testid*="sender"] [title*="@"]',
      '[data-testid*="sender"]',
    ];
    for (const selector of selectors) {
      const node = browserDocument.querySelector(selector);
      if (!node) continue;
      const address = node.getAttribute("title") || node.getAttribute("data-email") || "";
      const name = (node.textContent || "").trim();
      if (address.includes("@") && name && name !== address) return `${name} <${address}>`;
      if (address.includes("@")) return address;
      if (name) return name;
    }
    return "";
  }

  function normalizedSender(value) {
    const text = String(value || "").trim();
    if (text.includes("<") && text.includes(">")) {
      return text.split("<", 2)[1].split(">", 1)[0].trim();
    }
    return text;
  }

  function gmailMessageUrl(item) {
    const messageId = String(item?.message_id || "").trim();
    if (messageId) {
      return `https://mail.google.com/mail/u/0/#all/${encodeURIComponent(messageId)}`;
    }
    const subject = String(item?.subject || "").replace(/\s+/g, " ").trim().slice(0, 80);
    const sender = normalizedSender(item?.sender || "");
    const query = [sender ? `from:${sender}` : "", subject ? `"${subject}"` : ""]
      .filter(Boolean)
      .join(" ") || messageId;
    return `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(query)}`;
  }

  function protonMessageUrl(item) {
    const subject = String(item?.subject || "").replace(/\s+/g, " ").trim().slice(0, 120);
    const sender = normalizedSender(item?.sender || "");
    return `https://mail.proton.me/u/0/all-mail#keyword=${encodeURIComponent(
      [sender, subject].filter(Boolean).join(" "),
    )}`;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { createProviderPageAdapter };
  }
  if (globalThis.window && globalThis.document) {
    globalThis.ThreadwiseProvider = createProviderPageAdapter(globalThis.window, globalThis.document);
  }
})();
