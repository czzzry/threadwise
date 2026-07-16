(() => {
  const WORKFLOW_VERSION = "gmail-companion-v1";
  const COMMON_KEYS = ["app_version", "workflow_version", "source"];
  const EVENT_KEYS = Object.freeze({
    "extension opened": ["surface"],
    "review queue opened": ["queue_size_bucket"],
    "email review started": ["queue_size_bucket", "review_origin"],
    "suggestion decision made": ["decision_type", "duration_ms"],
    "rule confirmed": ["rule_scope", "affected_count_bucket", "dry_run"],
    "review batch completed": ["reviewed_count_bucket", "duration_ms"],
  });
  const SENSITIVE_VALUE = /[^\s@]+@[^\s@]+\.[^\s@]+|\bbearer\s+|\bya29\./i;
  let reviewStartedAt = null;
  let currentReviewKey = "";

  /** @typedef {'approve'|'edit'|'reject'} SuggestionDecision */
  /** @typedef {'current_email'|'included_existing'|'future_email'} RuleScope */

  function bucketCount(rawCount) {
    const count = Math.max(0, Number(rawCount) || 0);
    if (count === 0) return "0";
    if (count === 1) return "1";
    if (count <= 5) return "2-5";
    if (count <= 10) return "6-10";
    if (count <= 25) return "11-25";
    if (count <= 50) return "26-50";
    return "51+";
  }

  function capture(event, eventProperties = {}) {
    const eventKeys = EVENT_KEYS[event];
    if (!eventKeys) return false;
    try {
      const properties = {
        app_version: chrome.runtime.getManifest().version,
        workflow_version: WORKFLOW_VERSION,
        source: "extension",
        ...eventProperties,
      };
      const expectedKeys = new Set([...COMMON_KEYS, ...eventKeys]);
      if (Object.keys(properties).some((key) => !expectedKeys.has(key))) return false;
      if ([...expectedKeys].some((key) => properties[key] === undefined)) return false;
      if (Object.values(properties).some((value) => typeof value === "string" && SENSITIVE_VALUE.test(value))) {
        return false;
      }
      chrome.runtime.sendMessage({
        type: "threadwise:analytics",
        event,
        properties,
      });
      return true;
    } catch (_error) {
      // Analytics is an observer and must never block the user workflow.
      return false;
    }
  }

  function openExtension() {
    return capture("extension opened", { surface: "gmail_companion" });
  }

  function openReviewQueue(queueSize) {
    return capture("review queue opened", { queue_size_bucket: bucketCount(queueSize) });
  }

  function startEmailReview(reviewKey, origin, queueSize) {
    if (!reviewKey || reviewKey === currentReviewKey) return false;
    currentReviewKey = reviewKey;
    reviewStartedAt = performance.now();
    return capture("email review started", {
      queue_size_bucket: bucketCount(queueSize),
      review_origin: origin,
    });
  }

  /** @param {SuggestionDecision} decisionType */
  function decideSuggestion(decisionType) {
    const durationMs = reviewStartedAt === null ? 0 : Math.max(0, Math.round(performance.now() - reviewStartedAt));
    return capture("suggestion decision made", {
      decision_type: decisionType,
      duration_ms: durationMs,
    });
  }

  /** @param {RuleScope} ruleScope */
  function confirmRule(ruleScope, affectedCount, dryRun = false) {
    return capture("rule confirmed", {
      rule_scope: ruleScope,
      affected_count_bucket: bucketCount(affectedCount),
      dry_run: Boolean(dryRun),
    });
  }

  function completeReviewBatch(reviewedCount) {
    const durationMs = reviewStartedAt === null ? 0 : Math.max(0, Math.round(performance.now() - reviewStartedAt));
    return capture("review batch completed", {
      reviewed_count_bucket: bucketCount(reviewedCount),
      duration_ms: durationMs,
    });
  }

  globalThis.ThreadwiseAnalytics = Object.freeze({
    bucketCount,
    openExtension,
    openReviewQueue,
    startEmailReview,
    decideSuggestion,
    confirmRule,
    completeReviewBatch,
  });
})();
