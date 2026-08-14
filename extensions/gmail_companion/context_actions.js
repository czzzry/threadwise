(() => {
  const MAX_ACTIONS = 4;

  const ACTIONS = [
    { id: "change-label", label: "Change label", dataAction: "change-suggestion" },
    { id: "open-email", label: "Open email", dataAction: "open-selected-gmail" },
    { id: "back-to-queue", label: "Back to queue", dataAction: "return-queue-home" },
    { id: "why", label: "Why", dataAction: "toggle-details" },
    { id: "not-now", label: "Not now", dataAction: "back-to-current-receipt" },
    { id: "edit-current-apply", label: "Edit", dataAction: "edit-current-apply" },
    { id: "teach-future", label: "Teach future emails", dataAction: "teach-future-after-receipt" },
    { id: "back-home", label: "Back to Home", dataAction: "return-home-after-receipt" },
    { id: "open-activity", label: "Open Activity", linkKind: "activity" },
    { id: "cancel-change", label: "Cancel", dataAction: "cancel-current-change" },
    { id: "edit-change", label: "Edit", dataAction: "edit-current-change" },
    { id: "keep-discussing", label: "Keep discussing", dataAction: "refine-teach" },
    { id: "back", label: "Back", dataAction: "edit-current-change" },
  ].map((action) => Object.freeze(action));
  const ALLOWLIST = Object.freeze(ACTIONS);
  const ACTION_BY_ID = new Map(ACTIONS.map((action) => [action.id, action]));

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

  function normalize(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  function attribute(node, name) {
    if (!node || typeof node.getAttribute !== "function") return null;
    try {
      return node.getAttribute(name);
    } catch (_error) {
      return null;
    }
  }

  function tagName(node) {
    return String(node?.tagName || node?.nodeName || "").toUpperCase();
  }

  function role(node) {
    return normalize(attribute(node, "role") || node?.role || "");
  }

  function contentEditableValue(node) {
    if (!node) return null;
    if (node.isContentEditable === true) return true;
    if (typeof node.contentEditable === "string") {
      const value = normalize(node.contentEditable);
      if (value === "true" || value === "plaintext-only") return true;
      if (value === "false") return false;
    }
    const raw = attribute(node, "contenteditable");
    if (raw === null) return null;
    return normalize(raw) !== "false";
  }

  function parentOf(node) {
    return node?.parentElement || node?.parentNode || null;
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
    return eachAncestor(target, (node) => (
      ["INPUT", "SELECT", "TEXTAREA"].includes(tagName(node))
      || contentEditableValue(node) === true
    ));
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
        // Use the dependency-free parent walk below.
      }
    }
    return eachAncestor(target, (node) => node === root);
  }

  function isRootShortcutTarget(target, root) {
    return isWithinRoot(target, root) && !isInteractiveTarget(target);
  }

  function hasModifier(event) {
    return Boolean(event?.altKey || event?.ctrlKey || event?.metaKey || event?.shiftKey);
  }

  function classifyMenuKey(event, root, menuOpen = false) {
    if (!event || typeof event !== "object") return null;
    const panelRoot = root || event.currentTarget;
    const target = event.target || panelRoot;
    if (!isWithinRoot(target, panelRoot) || hasModifier(event)) return null;

    if (!menuOpen) {
      return event.key === "." && isRootShortcutTarget(target, panelRoot)
        ? "open"
        : null;
    }

    const key = event.key;
    if (key === "j" || key === "J" || key === "k" || key === "K") {
      return "consume";
    }
    const menuItem = typeof target.closest === "function"
      ? target.closest("[data-ea-context-item]")
      : null;
    if (!menuItem && isEditableTarget(target)) return null;
    switch (key) {
      case "ArrowDown":
        return "next";
      case "ArrowUp":
        return "previous";
      case "Home":
        return "first";
      case "End":
        return "last";
      case "Enter":
      case " ":
      case "Spacebar":
        return "activate";
      case "Escape":
      case "Esc":
        return "close";
      default:
        return null;
    }
  }

  function nextIndex(currentIndex, direction, length) {
    const count = Number(length);
    if (!Number.isInteger(count) || count <= 0) return -1;
    const current = Math.min(Math.max(Number(currentIndex) || 0, 0), count - 1);
    if (direction === "first" || direction === "home") return 0;
    if (direction === "last" || direction === "end") return count - 1;
    if (direction === "next" || direction === 1) return Math.min(current + 1, count - 1);
    if (direction === "previous" || direction === -1) return Math.max(current - 1, 0);
    return current;
  }

  function bool(value) {
    return value === true;
  }

  function actionEnabled(input, actionId) {
    const enabledActions = input?.enabledActions;
    if (enabledActions && Object.prototype.hasOwnProperty.call(enabledActions, actionId)) {
      return Boolean(enabledActions[actionId]);
    }
    const disabled = input?.disabledActionIds;
    return !(Array.isArray(disabled) && disabled.includes(actionId));
  }

  function addAction(result, actionId, input) {
    const action = ACTION_BY_ID.get(actionId);
    if (!action || !actionEnabled(input, actionId) || result.some((item) => item.id === actionId)) {
      return;
    }
    result.push(action);
  }

  function deriveActions(input = {}) {
    const mode = normalize(input.workspaceMode || input.mode);
    const result = [];
    switch (mode) {
      case "review":
        if (bool(input.hasSuggestedLabel)) addAction(result, "change-label", input);
        if (input.canExplain !== false) addAction(result, "why", input);
        if (input.canOpenEmail !== false) addAction(result, "open-email", input);
        if (bool(input.queuePreviewActive)) addAction(result, "back-to-queue", input);
        break;
      case "handled-receipt":
        if (input.canOpenEmail !== false) addAction(result, "open-email", input);
        if (input.canExplain !== false) addAction(result, "why", input);
        break;
      case "future-learning":
        addAction(result, "not-now", input);
        break;
      case "current-apply-error":
        addAction(result, "edit-current-apply", input);
        break;
      case "current-receipt":
      case "partial-receipt":
        if (bool(input.providerChangeSucceeded)) addAction(result, "teach-future", input);
        if (bool(input.queueComplete) && bool(input.providerChangeSucceeded)) addAction(result, "back-home", input);
        if (bool(input.receiptFailed)) addAction(result, "open-activity", input);
        break;
      case "change":
        addAction(result, "cancel-change", input);
        break;
      case "preview":
        addAction(result, "edit-change", input);
        break;
      case "teach-preview":
        if (input.canOpenEmail !== false) addAction(result, "open-email", input);
        if (input.canEdit !== false) addAction(result, "edit-change", input);
        break;
      case "teach-scope":
        if (input.canOpenEmail !== false) addAction(result, "open-email", input);
        if (input.canKeepDiscussing !== false) addAction(result, "keep-discussing", input);
        break;
      default:
        break;
    }
    return Object.freeze(result.slice(0, MAX_ACTIONS));
  }

  const api = Object.freeze({
    MAX_ACTIONS,
    ALLOWLIST,
    ACTIONS: ALLOWLIST,
    isEditableTarget,
    isNativeInteractiveTarget,
    isInteractiveTarget,
    isWithinRoot,
    isRootShortcutTarget,
    classifyMenuKey,
    classifyKey: classifyMenuKey,
    nextIndex,
    getNextIndex: nextIndex,
    deriveActions,
    actionsForState: deriveActions,
    getActions: deriveActions,
  });

  globalThis.ThreadwiseContextActions = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
