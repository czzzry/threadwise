(() => {
  const CANONICAL_LABELS = new Set([
    "travel",
    "receipt-billing",
    "shopping-order",
    "financial-account",
    "newsletter",
    "promotions",
    "account-security",
    "calendar-event",
    "personal",
    "job-related",
    "spam-low-value",
    "reply-needed",
    "suspicious",
  ]);
  const CONFIDENCE_TEXT = Object.freeze({
    high: "High confidence",
    medium: "Medium confidence",
    low: "Low confidence",
  });
  const VISIBLE_MODES = new Set(["review", "handled-receipt"]);

  function text(value) {
    return String(value ?? "").trim();
  }

  function normalizeConfidenceBand(value) {
    const band = text(value).toLowerCase();
    return Object.prototype.hasOwnProperty.call(CONFIDENCE_TEXT, band) ? band : "";
  }

  function normalizeNearMisses(values) {
    if (!Array.isArray(values)) {
      return [];
    }
    const result = [];
    for (const value of values) {
      const label = text(value).toLowerCase();
      if (CANONICAL_LABELS.has(label) && !result.includes(label)) {
        result.push(label);
      }
    }
    return result;
  }

  function providerStatusText(value, fallback) {
    const status = text(value).toLowerCase();
    return {
      applied: "Confirmed",
      pending: "Pending",
      failed: "Failed",
      skipped: "Skipped",
    }[status] || fallback;
  }

  function initialDecisionText(value) {
    const provenance = value && typeof value === "object" ? value : {};
    const source = text(provenance.decision_source).toLowerCase();
    const model = text(provenance.llm_model);
    const modelSuffix = model ? ` · ${model}` : "";
    if (provenance.llm_failed || source === "model-failure") {
      return `Model unavailable${modelSuffix}`;
    }
    if (provenance.llm_abstained) {
      return `Model abstained${modelSuffix}`;
    }
    if (provenance.llm_used || source === "model") {
      return `Model${modelSuffix}`;
    }
    if (source === "rules") {
      return "Rules";
    }
    return "";
  }

  function derive(input = {}) {
    const workspaceMode = text(input.workspaceMode);
    const visible = VISIBLE_MODES.has(workspaceMode);
    const selectedStatus = text(input.selectedStatus).toLowerCase();
    const providerName = text(input.providerName) || "The provider";
    const suggestionLabel = text(input.suggestedLabel);
    const details = input.details && typeof input.details === "object" ? input.details : {};
    const confidenceBand = normalizeConfidenceBand(details.confidence_band);
    const rationale = text(input.storedReason) || "No classification rationale was stored for this email";
    const nearMisses = normalizeNearMisses(details.near_misses);
    const matchedRuleCount = Number(details.matched_rule_count);
    const evidenceRows = [];
    const initialDecision = initialDecisionText(details.decision_provenance);

    if (initialDecision) {
      evidenceRows.push({
        key: "decision-source",
        label: "Initial decision",
        values: [initialDecision],
      });
    }

    if (nearMisses.length) {
      evidenceRows.push({
        key: "near-misses",
        label: "Also considered",
        values: nearMisses,
      });
    }
    if (Number.isInteger(matchedRuleCount) && matchedRuleCount > 0) {
      evidenceRows.push({
        key: "matched-rules",
        label: "Saved rules matched",
        values: [String(matchedRuleCount)],
      });
    }
    if (selectedStatus === "write-unconfirmed") {
      evidenceRows.push({
        key: "provider-write",
        label: "Provider label update",
        values: [providerStatusText(details.write_status, "Not confirmed")],
      });
      if (text(details.inbox_status)) {
        evidenceRows.push({
          key: "inbox",
          label: "Inbox handling",
          values: [providerStatusText(details.inbox_status, "Not recorded")],
        });
      }
    }

    const suggestionText = suggestionLabel
      ? `Threadwise suggests ${suggestionLabel}`
      : "Threadwise needs your label";
    const queueReason = selectedStatus === "write-unconfirmed"
      ? `${providerName} has not confirmed this label update`
      : selectedStatus === "needs-attention"
        ? (suggestionLabel ? "Waiting for your review" : "Threadwise needs your label")
        : selectedStatus === "auto-handled" || selectedStatus === "kept-visible" || selectedStatus === "auto-labeled"
          ? "Handled by Threadwise"
          : (suggestionLabel ? "Waiting for your review" : "Threadwise needs your label");

    return {
      workspaceMode,
      visible,
      suggestionLabel,
      suggestionText,
      queueReason,
      confidenceBand,
      confidenceText: CONFIDENCE_TEXT[confidenceBand] || "Confidence not recorded",
      rationale,
      evidenceRows,
      hasEvidence: evidenceRows.length > 0,
    };
  }

  const api = Object.freeze({
    derive,
    build: derive,
    normalizeConfidenceBand,
    normalizeNearMisses,
    initialDecisionText,
  });

  globalThis.ThreadwiseSelectedExplanation = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
