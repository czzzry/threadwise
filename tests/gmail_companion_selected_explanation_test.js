const assert = require("node:assert/strict");
const explanation = require("../extensions/gmail_companion/selected_explanation.js");

function run() {
  assert.equal(Object.isFrozen(explanation), true);
  assert.equal(globalThis.ThreadwiseSelectedExplanation, explanation);

  const review = explanation.derive({
    workspaceMode: "review",
    selectedStatus: "needs-attention",
    providerName: "Gmail",
    suggestedLabel: "EA/Work",
    storedReason: "A manager asks for a same-day approval.",
    details: {
      confidence_band: "HIGH",
      near_misses: ["promotions", "promotions", "not-a-label", "travel"],
      matched_rule_count: 2,
      write_status: "",
      inbox_status: "",
    },
  });
  assert.deepEqual(review, {
    workspaceMode: "review",
    visible: true,
    suggestionLabel: "EA/Work",
    suggestionText: "Threadwise suggests EA/Work",
    queueReason: "Waiting for your review",
    confidenceBand: "high",
    confidenceText: "High confidence",
    rationale: "A manager asks for a same-day approval.",
    evidenceRows: [
      { key: "near-misses", label: "Also considered", values: ["promotions", "travel"] },
      { key: "matched-rules", label: "Saved rules matched", values: ["2"] },
    ],
    hasEvidence: true,
  });

  const noEvidence = explanation.derive({
    workspaceMode: "review",
    selectedStatus: "needs-attention",
    providerName: "Gmail",
    suggestedLabel: "",
    storedReason: "",
    details: { confidence_band: "not-a-band", near_misses: [], matched_rule_count: 0 },
  });
  assert.equal(noEvidence.suggestionText, "Threadwise needs your label");
  assert.equal(noEvidence.queueReason, "Threadwise needs your label");
  assert.equal(noEvidence.confidenceBand, "");
  assert.equal(noEvidence.confidenceText, "Confidence not recorded");
  assert.equal(noEvidence.rationale, "No classification rationale was stored for this email");
  assert.equal(noEvidence.hasEvidence, false);

  const recovery = explanation.derive({
    workspaceMode: "review",
    selectedStatus: "write-unconfirmed",
    providerName: "Gmail",
    suggestedLabel: "EA/Finance",
    storedReason: "A routine account notice.",
    details: {
      confidence_band: "low",
      near_misses: ["travel"],
      matched_rule_count: 0,
      write_status: "",
      inbox_status: "applied",
    },
  });
  assert.equal(recovery.queueReason, "Gmail has not confirmed this label update");
  assert.equal(recovery.confidenceText, "Low confidence");
  assert.deepEqual(recovery.evidenceRows, [
    { key: "near-misses", label: "Also considered", values: ["travel"] },
    { key: "provider-write", label: "Provider label update", values: ["Not confirmed"] },
    { key: "inbox", label: "Inbox handling", values: ["Confirmed"] },
  ]);

  const handled = explanation.derive({
    workspaceMode: "handled-receipt",
    selectedStatus: "auto-handled",
    providerName: "Gmail",
    suggestedLabel: "EA/Promotions",
    storedReason: "Promotional mail from a recurring sender.",
    details: { confidence_band: "medium", near_misses: [], matched_rule_count: 0 },
  });
  assert.equal(handled.visible, true);
  assert.equal(handled.queueReason, "Handled by Threadwise");
  assert.equal(handled.confidenceText, "Medium confidence");

  assert.equal(explanation.derive({ workspaceMode: "home" }).visible, false);
  console.log("gmail companion selected explanation tests passed");
}

try {
  run();
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
