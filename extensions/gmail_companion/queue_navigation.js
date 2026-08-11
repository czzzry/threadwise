(() => {
  const SEARCH_FIELDS = Object.freeze([
    "sender",
    "from",
    "subject",
    "classification",
    "classification_label",
    "displayed_classification",
    "displayedClassification",
    "label",
    "labels",
    "suggested_label",
    "suggestedLabel",
    "displayed_label",
    "displayedLabel",
    "displayed_labels",
    "displayedLabels",
    "internal_label",
    "internalLabel",
    "applied_label",
    "appliedLabel",
    "applied_labels",
    "appliedLabels",
    "provider_label",
    "providerLabel",
    "provider_labels",
    "providerLabels",
    "gmail_labels",
    "status_label",
    "statusLabel",
    "status",
  ]);

  const NATIVE_INTERACTIVE_TAGS = new Set([
    "A",
    "AREA",
    "BUTTON",
    "INPUT",
    "OPTION",
    "SELECT",
    "SUMMARY",
    "TEXTAREA",
  ]);

  function normalizeQuery(value) {
    let text = String(value ?? "");
    if (typeof text.normalize === "function") {
      text = text.normalize("NFKC");
    }
    return text.trim().replace(/\s+/g, " ").toLowerCase();
  }

  function valueText(value) {
    if (value == null) return "";
    if (Array.isArray(value)) {
      return value.map(valueText).filter(Boolean).join(" ");
    }
    if (typeof value === "object") {
      return ["label", "name", "value", "title", "text", "email", "address"]
        .map((field) => valueText(value[field]))
        .filter(Boolean)
        .join(" ");
    }
    return String(value);
  }

  function buildSearchableText(item) {
    if (!item || typeof item !== "object") return "";
    return normalizeQuery(
      SEARCH_FIELDS.map((field) => valueText(item[field]))
        .filter(Boolean)
        .join(" "),
    );
  }

  function normalizeProvider(value) {
    return normalizeQuery(value);
  }

  function itemProvider(item) {
    if (!item || typeof item !== "object") return "";
    return normalizeProvider(item.provider || "");
  }

  function isActiveProviderItem(item, activeProvider) {
    const provider = normalizeProvider(activeProvider);
    if (!provider || !item || typeof item !== "object") return false;
    const itemProviderValue = itemProvider(item);
    return !itemProviderValue || itemProviderValue === provider;
  }

  function filterQueueItems(items, activeProviderOrOptions, query) {
    let activeProvider = activeProviderOrOptions;
    let normalizedQuery = query;
    if (
      activeProviderOrOptions
      && typeof activeProviderOrOptions === "object"
      && !Array.isArray(activeProviderOrOptions)
    ) {
      activeProvider = activeProviderOrOptions.activeProvider
        ?? activeProviderOrOptions.provider;
      normalizedQuery = activeProviderOrOptions.query;
    }

    const provider = normalizeProvider(activeProvider);
    if (!Array.isArray(items) || !provider) return [];
    const queryText = normalizeQuery(normalizedQuery);
    return items.filter((item) => (
      isActiveProviderItem(item, provider)
      && (!queryText || buildSearchableText(item).includes(queryText))
    ));
  }

  function filterQueue(items, query, activeProvider) {
    if (
      query
      && typeof query === "object"
      && !Array.isArray(query)
    ) {
      return filterQueueItems(items, query);
    }
    return filterQueueItems(items, activeProvider, query);
  }

  function stableMessageId(value) {
    if (value == null) return null;
    const messageId = String(value);
    return messageId.trim() ? messageId : null;
  }

  function queueEntries(items) {
    return Array.isArray(items)
      ? items.filter((item) => stableMessageId(item?.message_id) !== null)
      : [];
  }

  function findQueueIndex(items, messageId) {
    const wanted = stableMessageId(messageId);
    if (wanted === null) return -1;
    return queueEntries(items).findIndex((item) => (
      stableMessageId(item.message_id) === wanted
    ));
  }

  function findCurrentItem(items, messageId) {
    const index = findQueueIndex(items, messageId);
    return index < 0 ? null : queueEntries(items)[index];
  }

  function findAdjacentItem(items, messageId, direction) {
    const entries = queueEntries(items);
    const index = findQueueIndex(entries, messageId);
    if (index < 0) return null;
    const offset = direction === "next" || direction === 1
      ? 1
      : direction === "previous" || direction === -1
        ? -1
        : 0;
    if (!offset) return null;
    const adjacentIndex = index + offset;
    return adjacentIndex < 0 || adjacentIndex >= entries.length
      ? null
      : entries[adjacentIndex];
  }

  function findNextItem(items, messageId) {
    return findAdjacentItem(items, messageId, "next");
  }

  function findPreviousItem(items, messageId) {
    return findAdjacentItem(items, messageId, "previous");
  }

  function queueNeighbors(items, messageId) {
    return {
      current: findCurrentItem(items, messageId),
      previous: findPreviousItem(items, messageId),
      next: findNextItem(items, messageId),
    };
  }

  function parentOf(node) {
    return node?.parentElement || node?.parentNode || null;
  }

  function attribute(node, name) {
    if (!node || typeof node.getAttribute !== "function") return null;
    try {
      return node.getAttribute(name);
    } catch (_error) {
      return null;
    }
  }

  function contentEditableValue(node) {
    if (!node) return null;
    if (node.isContentEditable === true) return true;
    if (typeof node.contentEditable === "string") {
      const property = normalizeQuery(node.contentEditable);
      if (property === "true" || property === "plaintext-only") return true;
      if (property === "false") return false;
    }
    const rawAttribute = attribute(node, "contenteditable");
    if (rawAttribute === null) return null;
    const value = normalizeQuery(rawAttribute);
    return value !== "false";
  }

  function tagName(node) {
    return String(node?.tagName || node?.nodeName || "").toUpperCase();
  }

  function role(node) {
    return normalizeQuery(attribute(node, "role") || node?.role || "");
  }

  function eachAncestor(target, callback) {
    const seen = new Set();
    let node = target;
    while (node && !seen.has(node)) {
      seen.add(node);
      if (callback(node) === true) return true;
      node = parentOf(node);
    }
    return false;
  }

  function isEditableTarget(target) {
    return eachAncestor(target, (node) => {
      const name = tagName(node);
      return name === "INPUT"
        || name === "SELECT"
        || name === "TEXTAREA"
        || contentEditableValue(node) === true;
    });
  }

  function isNativeInteractiveTarget(target) {
    return eachAncestor(target, (node) => (
      NATIVE_INTERACTIVE_TAGS.has(tagName(node))
      || role(node) === "button"
      || role(node) === "link"
    ));
  }

  function isInteractiveTarget(target) {
    return isEditableTarget(target) || isNativeInteractiveTarget(target);
  }

  function isWithinRoot(target, root) {
    if (!target || !root) return false;
    if (target === root) return true;
    if (typeof root.contains === "function") {
      try {
        if (root.contains(target)) return true;
      } catch (_error) {
        // Fall through to the dependency-free parent walk.
      }
    }
    return eachAncestor(target, (node) => node === root);
  }

  function hasModifier(event) {
    return Boolean(event?.altKey || event?.ctrlKey || event?.metaKey || event?.shiftKey);
  }

  function classifyPanelKey(event, root) {
    if (!event || typeof event !== "object") return null;
    const panelRoot = root || event.currentTarget;
    const target = event.target || panelRoot;
    if (!isWithinRoot(target, panelRoot) || hasModifier(event)) {
      return null;
    }

    if (event.key === "Escape" || event.key === "Esc") {
      return isEditableTarget(target) ? null : "escape";
    }
    if (isInteractiveTarget(target)) return null;

    switch (event.key) {
      case "Enter":
        return "primary-action";
      case "j":
      case "J":
        return "next";
      case "k":
      case "K":
        return "previous";
      default:
        return null;
    }
  }

  const api = Object.freeze({
    normalizeQuery,
    buildSearchableText,
    searchableText: buildSearchableText,
    normalizeProvider,
    itemProvider,
    isActiveProviderItem,
    filterQueueItems,
    filterProviderQueue: filterQueueItems,
    filterQueue,
    filterByQuery: filterQueue,
    findQueueIndex,
    findCurrentItem,
    findCurrent: findCurrentItem,
    findQueueItemByMessageId: findCurrentItem,
    findAdjacentItem,
    findNextItem,
    findNext: findNextItem,
    findPreviousItem,
    findPrevious: findPreviousItem,
    queueNeighbors,
    getQueueNeighbors: queueNeighbors,
    isEditableTarget,
    isNativeInteractiveTarget,
    isInteractiveTarget,
    isWithinRoot,
    classifyPanelKey,
    classifyKey: classifyPanelKey,
  });

  globalThis.ThreadwiseQueueNavigation = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
