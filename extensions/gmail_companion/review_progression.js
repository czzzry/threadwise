(() => {
  const COMPLETE = "verified-complete";
  const FILTERED_EMPTY = "filtered-empty";
  const NEXT_AVAILABLE = "next-available";
  const CHECKING = "checking";
  const RETRY = "retry";
  const DEFAULT_PROVIDER = "gmail";

  function text(value) {
    return String(value ?? "").trim();
  }

  function normalizeProvider(value) {
    return text(value).toLowerCase();
  }

  function normalizeIdentity(input = {}) {
    const source = input && typeof input === "object" ? input : {};
    return {
      provider: normalizeProvider(source.provider || source.provider_id || source.activeProvider),
      messageId: text(source.message_id || source.messageId || source.id),
      threadId: text(source.thread_id || source.threadId),
    };
  }

  function identityKey(input = {}) {
    const identity = normalizeIdentity(input);
    if (!identity.provider || !identity.messageId) {
      return "";
    }
    return `${identity.provider}:${identity.messageId}`;
  }

  function itemIdentity(item, activeProvider = "") {
    const source = item && typeof item === "object" ? item : {};
    return normalizeIdentity({
      ...source,
      provider: source.provider || activeProvider,
    });
  }

  function identitiesCompatible(expected, current) {
    const wanted = normalizeIdentity(expected);
    const actual = normalizeIdentity(current);
    if (!wanted.provider || !wanted.messageId || !actual.provider || !actual.messageId) {
      return false;
    }
    if (wanted.provider !== actual.provider || wanted.messageId !== actual.messageId) {
      return false;
    }
    return !wanted.threadId || !actual.threadId || wanted.threadId === actual.threadId;
  }

  function normalizedCommittedKeys(values, activeProvider = "") {
    if (!Array.isArray(values)) {
      return new Set();
    }
    const keys = new Set();
    for (const value of values) {
      const key = typeof value === "string"
        ? value.trim().toLowerCase()
        : identityKey(itemIdentity(value, activeProvider));
      if (key) {
        keys.add(key);
      }
    }
    return keys;
  }

  function providerMatches(item, activeProvider) {
    const provider = normalizeProvider(activeProvider);
    if (!provider || !item || typeof item !== "object") {
      return false;
    }
    const itemProvider = normalizeProvider(item.provider);
    return !itemProvider || itemProvider === provider;
  }

  function eligibleItems({
    items = [],
    activeProvider = DEFAULT_PROVIDER,
    committedIdentities = [],
  } = {}) {
    const committed = normalizedCommittedKeys(committedIdentities, activeProvider);
    if (!Array.isArray(items)) {
      return [];
    }
    const seen = new Set();
    return items.filter((item) => {
      if (!providerMatches(item, activeProvider)) {
        return false;
      }
      const key = identityKey(itemIdentity(item, activeProvider));
      if (!key || committed.has(key) || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }

  function itemIndex(items, identity, activeProvider = DEFAULT_PROVIDER) {
    const wanted = identityKey(itemIdentity(identity, activeProvider));
    if (!wanted || !Array.isArray(items)) {
      return -1;
    }
    return items.findIndex((item) => identityKey(itemIdentity(item, activeProvider)) === wanted);
  }

  function nextEligibleItem({
    items = [],
    currentIdentity = {},
    activeProvider = DEFAULT_PROVIDER,
    committedIdentities = [],
  } = {}) {
    const candidates = eligibleItems({ items, activeProvider, committedIdentities });
    if (!candidates.length) {
      return null;
    }
    const currentKey = identityKey(itemIdentity(currentIdentity, activeProvider));
    const currentIndex = itemIndex(items, currentIdentity, activeProvider);
    if (currentIndex < 0) {
      return candidates[0];
    }
    for (const candidate of candidates) {
      const candidateIndex = itemIndex(items, candidate, activeProvider);
      if (candidateIndex > currentIndex) {
        return candidate;
      }
    }
    if (!currentKey) {
      return candidates[0];
    }
    return null;
  }

  function labelChangeRequiresCurrentOnly(change = {}) {
    if (!change || typeof change !== "object") {
      return false;
    }
    const operation = text(change.operation).toLowerCase();
    const labelsAfter = Array.isArray(change.labels_after) ? change.labels_after.filter((label) => text(label)) : [];
    const legacySingleLabel = text(change.compatibility) === "legacy-single-label"
      && operation === "only"
      && labelsAfter.length === 1;
    return Boolean(operation) && !legacySingleLabel;
  }

  function hasApprovedLabelChange(change = {}) {
    return Boolean(
      change && typeof change === "object"
      && text(change.operation)
      && Array.isArray(change.labels_after)
      && change.labels_after.some((label) => text(label)),
    );
  }

  function sameLabelSet(left, right) {
    if (!Array.isArray(left) || !Array.isArray(right)) {
      return false;
    }
    const normalizedLeft = [...new Set(left.map(text).filter(Boolean))].sort();
    const normalizedRight = [...new Set(right.map(text).filter(Boolean))].sort();
    return normalizedLeft.length === normalizedRight.length
      && normalizedLeft.every((label, index) => label === normalizedRight[index]);
  }

  function recoveryConfirmation({
    responseOk = false,
    sameMessage = false,
    selected = {},
    expectedLabels = [],
    requestId = "",
  } = {}) {
    const details = selected?.details || {};
    const receipt = details.provider_write_receipt || {};
    const receiptStatus = text(receipt.status).toLowerCase();
    const localAccepted = Boolean(
      responseOk
      && sameMessage
      && text(requestId)
      && text(receipt.request_id) === text(requestId)
      && ["applied", "failed"].includes(receiptStatus)
      && sameLabelSet(receipt.final_labels, expectedLabels)
      && sameLabelSet(selected.all_labels, expectedLabels)
    );
    const confirmed = Boolean(
      localAccepted
      && receiptStatus === "applied"
      && text(details.write_status).toLowerCase() === "applied"
      && text(details.inbox_status).toLowerCase() !== "failed"
    );
    return Object.freeze({
      localAccepted,
      confirmed,
      providerFailed: localAccepted && !confirmed,
      inboxRemoved: confirmed && text(details.inbox_status).toLowerCase() === "applied",
    });
  }

  function handledAcknowledgementAction({
    items = [],
    currentIdentity = {},
    activeProvider = DEFAULT_PROVIDER,
    committedIdentities = [],
  } = {}) {
    const next = nextEligibleItem({ items, currentIdentity, activeProvider, committedIdentities });
    return Object.freeze({
      hasNext: Boolean(next),
      label: next ? "Looks right · Next" : "Looks right · Check queue",
      item: next || null,
    });
  }

  function decisionMayAdvance({
    localAccepted = false,
    responseReceived = false,
    responseAccepted = null,
  } = {}) {
    return Boolean(localAccepted && responseReceived && responseAccepted === true);
  }

  function createRequestToken({
    generation = 0,
    kind = "decision",
    identity = {},
    attemptId = "",
  } = {}) {
    const normalized = normalizeIdentity(identity);
    const key = identityKey(normalized);
    const numericGeneration = Number.isFinite(Number(generation)) ? Number(generation) : 0;
    const baseToken = `${text(kind) || "decision"}:${numericGeneration}:${key}`;
    const normalizedAttemptId = text(attemptId);
    return Object.freeze({
      kind: text(kind) || "decision",
      generation: numericGeneration,
      identity: Object.freeze(normalized),
      identityKey: key,
      token: normalizedAttemptId ? `${baseToken}:${normalizedAttemptId}` : baseToken,
    });
  }

  function matchesRequestToken(token, {
    generation,
    identity,
    kind,
    requireThreadMatch = false,
  } = {}) {
    if (!token || typeof token !== "object" || !token.identityKey) {
      return false;
    }
    if (kind && text(token.kind) !== text(kind)) {
      return false;
    }
    if (generation != null && Number(token.generation) !== Number(generation)) {
      return false;
    }
    if (requireThreadMatch) {
      const expected = normalizeIdentity(token.identity);
      const actual = normalizeIdentity(identity);
      if (expected.threadId && expected.threadId !== actual.threadId) {
        return false;
      }
    }
    return identitiesCompatible(token.identity, identity);
  }

  function responseMatchesToken(token, current = {}) {
    return matchesRequestToken(token, { ...current, requireThreadMatch: true });
  }

  function dailyCountFor(freshState, queueKind) {
    const sidebar = freshState?.sidebar_state || freshState || {};
    const summary = sidebar.daily_summary || {};
    if (queueKind === "auto_handled_items") {
      return summary.auto_handled_count;
    }
    return summary.needs_attention_count;
  }

  function isExplicitFiniteNumericZero(value) {
    return typeof value === "number" && Number.isFinite(value) && value === 0;
  }

  function queueItemsFor(freshState, queueKind) {
    const source = freshState && typeof freshState === "object" ? freshState : {};
    return Array.isArray(source[queueKind]) ? source[queueKind] : null;
  }

  function completionPresentation({
    query = "",
    loadedItems = [],
    freshState = null,
    activeProvider = DEFAULT_PROVIDER,
    committedIdentities = [],
    queueKind = "needs_attention_items",
    requireDailyCount = queueKind === "needs_attention_items",
    refreshGeneration = null,
    expectedGeneration = null,
    followUpState = "",
    error = "",
  } = {}) {
    const normalizedQuery = text(query);
    const hasFreshState = Boolean(freshState && typeof freshState === "object");
    const freshItems = hasFreshState ? queueItemsFor(freshState, queueKind) : null;
    if (hasFreshState && !freshItems) {
      return {
        kind: RETRY,
        title: "Review queue check needs a retry",
        message: "Threadwise could not verify the provider-scoped review queue.",
        item: null,
      };
    }
    const localEligible = eligibleItems({
      items: loadedItems,
      activeProvider,
      committedIdentities,
    });
    if (normalizedQuery && localEligible.length === 0) {
      return {
        kind: FILTERED_EMPTY,
        title: "No loaded review emails match",
        message: "Clear the filter to continue reviewing the active provider queue.",
        item: null,
      };
    }
    if (error) {
      return {
        kind: RETRY,
        title: "Review queue check needs a retry",
        message: text(error),
        item: null,
      };
    }
    if (expectedGeneration != null && refreshGeneration != null
      && Number(expectedGeneration) !== Number(refreshGeneration)) {
      return {
        kind: CHECKING,
        title: "Checking review queue…",
        message: "Threadwise is waiting for the newest provider-scoped queue read.",
        item: null,
      };
    }
    if (!freshState || typeof freshState !== "object") {
      return {
        kind: CHECKING,
        title: "Checking review queue…",
        message: "Threadwise is verifying the current provider-scoped review queue.",
        item: null,
      };
    }
    if (["working", "pending"].includes(text(followUpState).toLowerCase())) {
      return {
        kind: CHECKING,
        title: "Checking review queue…",
        message: "Threadwise is waiting for the background queue refresh to settle.",
        item: null,
      };
    }
    const freshEligible = eligibleItems({
      items: freshItems,
      activeProvider,
      committedIdentities,
    });
    if (freshEligible.length) {
      return {
        kind: NEXT_AVAILABLE,
        title: "Next review email ready",
        message: "Threadwise found another eligible email in the refreshed queue.",
        item: freshEligible[0],
      };
    }
    const dailyCount = dailyCountFor(freshState, queueKind);
    const countVerified = !requireDailyCount || isExplicitFiniteNumericZero(dailyCount);
    if (countVerified) {
      return {
        kind: COMPLETE,
        title: queueKind === "needs_attention_items" ? "Review queue complete" : "Auto-handled complete",
        message: queueKind === "needs_attention_items"
          ? "The fresh provider-scoped state has no reviewable emails remaining."
          : "The fresh provider-scoped handled queue has no emails remaining.",
        item: null,
      };
    }
    return {
      kind: CHECKING,
      title: "Checking review queue…",
      message: "Threadwise is waiting for a fresh provider count before calling this queue complete.",
      item: null,
    };
  }

  function previousDecisionStatus({
    localAccepted = false,
    providerWriteState = "",
    providerName = "the provider",
    responseReceived = true,
    responseAccepted = true,
    decisionKind = "",
  } = {}) {
    if (!localAccepted) {
      return Object.freeze({ visible: false, state: "hidden", label: "", message: "" });
    }
    if (!responseReceived) {
      return Object.freeze({
        visible: true,
        state: "working",
        label: "Previous decision sent",
        message: "Waiting for Threadwise to confirm the local save",
      });
    }
    if (responseAccepted === false) {
      return Object.freeze({
        visible: true,
        state: "retry",
        label: "Previous decision needs attention",
        message: text(decisionKind) === "handled-review-acknowledge"
          ? "Threadwise did not confirm the review acknowledgement; try again"
          : "Threadwise did not confirm the local save; check Activity",
      });
    }
    const state = text(providerWriteState).toLowerCase();
    if (["retry", "error", "failed"].includes(state)) {
      return Object.freeze({
        visible: true,
        state: "retry",
        label: "Previous decision saved",
        message: `Background ${providerName} activity needs a retry`,
      });
    }
    if (["done", "complete", "completed"].includes(state)) {
      return Object.freeze({
        visible: true,
        state: "done",
        label: "Previous decision saved",
        message: `Background ${providerName} activity is complete; this is not a per-message provider confirmation`,
      });
    }
    return Object.freeze({
      visible: true,
      state: "working",
      label: "Previous decision saved",
      message: `Updating ${providerName} in the background`,
    });
  }

  function cloneSerializable(value) {
    if (value == null || typeof value !== "object") {
      return value;
    }
    if (Array.isArray(value)) {
      return value.map(cloneSerializable);
    }
    const result = {};
    for (const [key, entry] of Object.entries(value)) {
      if (typeof entry !== "function") {
        result[key] = cloneSerializable(entry);
      }
    }
    return result;
  }

  const api = Object.freeze({
    COMPLETE,
    FILTERED_EMPTY,
    NEXT_AVAILABLE,
    CHECKING,
    RETRY,
    normalizeIdentity,
    identityKey,
    itemIdentity,
    identitiesCompatible,
    eligibleItems,
    filterEligibleItems: eligibleItems,
    nextEligibleItem,
    chooseNextItem: nextEligibleItem,
    labelChangeRequiresCurrentOnly,
    hasApprovedLabelChange,
    sameLabelSet,
    recoveryConfirmation,
    handledAcknowledgementAction,
    decisionMayAdvance,
    createRequestToken,
    makeRequestToken: createRequestToken,
    matchesRequestToken,
    responseMatchesToken,
    isExplicitFiniteNumericZero,
    completionPresentation,
    getCompletionPresentation: completionPresentation,
    previousDecisionStatus,
    derivePreviousDecisionStatus: previousDecisionStatus,
    cloneSerializable,
  });

  globalThis.ThreadwiseReviewProgression = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
