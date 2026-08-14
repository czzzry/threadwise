(() => {
  const VERSION = "2026-08-09-v1";
  const STORAGE_KEY = "threadwise_onboarding_state";
  const ACTIVE_STATUSES = new Set(["active", "completed", "dismissed"]);
  const HANDLED_STATUSES = new Set([
    "auto-handled",
    "auto-labeled",
    "kept-visible",
    "provider-confirmed",
  ]);
  const fallbackData = {};
  const fallbackStorage = {
    async get(key) {
      return { [key]: fallbackData[key] };
    },
    async set(values) {
      Object.assign(fallbackData, values);
    },
  };

  function storageArea(storage) {
    return storage
      || globalThis.chrome?.storage?.local
      || fallbackStorage;
  }

  function unseenState() {
    return { version: VERSION, status: "unseen" };
  }

  function normalizeState(value) {
    if (
      !value
      || value.version !== VERSION
      || (!ACTIVE_STATUSES.has(value.status))
    ) {
      return unseenState();
    }
    return {
      version: VERSION,
      status: value.status,
      ...(value.updated_at ? { updated_at: value.updated_at } : {}),
    };
  }

  async function load(storage) {
    const stored = await storageArea(storage).get(STORAGE_KEY);
    return normalizeState(stored?.[STORAGE_KEY]);
  }

  async function saveStatus(status, storage) {
    if (!ACTIVE_STATUSES.has(status)) {
      throw new Error(`Unsupported onboarding status: ${status}`);
    }
    const next = {
      version: VERSION,
      status,
      updated_at: new Date().toISOString(),
    };
    await storageArea(storage).set({ [STORAGE_KEY]: next });
    return next;
  }

  function markActive(storage) {
    return saveStatus("active", storage);
  }

  function markCompleted(storage) {
    return saveStatus("completed", storage);
  }

  function markDismissed(storage) {
    return saveStatus("dismissed", storage);
  }

  function providerFor(item) {
    return String(item?.provider || item?.source || "").trim().toLowerCase();
  }

  function isReviewableSelected(selected) {
    if (!selected || selected.found !== true) {
      return false;
    }
    return !HANDLED_STATUSES.has(String(selected.status || "").trim().toLowerCase());
  }

  function isProviderQueueItem(item, provider) {
    return Boolean(
      item?.message_id
      && provider
      && providerFor(item) === String(provider).trim().toLowerCase()
      && !HANDLED_STATUSES.has(String(item.status || "").trim().toLowerCase()),
    );
  }

  function resolveTarget({ provider, selectedEmail, needsAttentionItems } = {}) {
    if (isReviewableSelected(selectedEmail)) {
      return {
        kind: "selected-email",
        provider: selectedEmail.provider || provider || "",
        message_id: selectedEmail.message_id || "",
        subject: selectedEmail.subject || "",
        sender: selectedEmail.sender || "",
      };
    }

    const queue = Array.isArray(needsAttentionItems) ? needsAttentionItems : [];
    const next = queue.find((item) => isProviderQueueItem(item, provider));
    if (next) {
      return {
        kind: "needs-attention",
        provider: provider || providerFor(next),
        item: next,
      };
    }

    return { kind: "home", provider: provider || "" };
  }

  const api = Object.freeze({
    VERSION,
    STORAGE_KEY,
    load,
    markActive,
    markCompleted,
    markDismissed,
    normalizeState,
    isReviewableSelected,
    resolveTarget,
  });

  globalThis.ThreadwiseOnboarding = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
