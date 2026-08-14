const assert = require("node:assert/strict");
const progression = require("../extensions/gmail_companion/review_progression.js");

function item(messageId, overrides = {}) {
  return {
    provider: "gmail",
    message_id: messageId,
    subject: `Synthetic ${messageId}`,
    status: "needs-attention",
    ...overrides,
  };
}

function run() {
  assert.equal(Object.isFrozen(progression), true);
  assert.equal(globalThis.ThreadwiseReviewProgression, progression);

  const queue = [item("a"), item("proton", { provider: "protonmail" }), item("b"), item("c")];
  assert.deepEqual(
    progression.eligibleItems({
      items: queue,
      activeProvider: "gmail",
      committedIdentities: [{ provider: "gmail", message_id: "a" }],
    }).map((candidate) => candidate.message_id),
    ["b", "c"],
    "provider and committed-identity filtering preserves source order",
  );
  assert.equal(
    progression.nextEligibleItem({
      items: queue,
      activeProvider: "gmail",
      currentIdentity: { provider: "gmail", message_id: "a" },
      committedIdentities: ["gmail:a"],
    }).message_id,
    "b",
  );
  assert.equal(
    progression.nextEligibleItem({
      items: [item("a"), item("b"), item("c")],
      activeProvider: "gmail",
      currentIdentity: { provider: "gmail", message_id: "b" },
      committedIdentities: ["gmail:b"],
    }).message_id,
    "c",
    "the current cursor is located before committed identities are excluded",
  );
  assert.equal(
    progression.nextEligibleItem({
      items: [item("a"), item("b"), item("c")],
      activeProvider: "gmail",
      currentIdentity: { provider: "gmail", message_id: "c" },
      committedIdentities: ["gmail:c"],
    }),
    null,
    "a committed final middle-queue cursor never wraps back to A",
  );
  assert.equal(
    progression.nextEligibleItem({
      items: queue,
      activeProvider: "gmail",
      currentIdentity: { provider: "gmail", message_id: "c" },
      committedIdentities: ["gmail:c"],
    }),
    null,
    "the policy never wraps after the final eligible item",
  );

  assert.equal(progression.labelChangeRequiresCurrentOnly({
    operation: "only",
    labels_after: ["personal"],
    compatibility: "legacy-single-label",
  }), false, "legacy one-label corrections keep broader teaching scopes");
  assert.equal(progression.labelChangeRequiresCurrentOnly({
    operation: "only",
    labels_after: ["personal"],
  }), true, "explicit only corrections remain bounded to the selected email");
  assert.equal(progression.labelChangeRequiresCurrentOnly({
    operation: "only",
    labels_after: ["shopping-order", "receipt-billing"],
  }), true);
  assert.equal(progression.labelChangeRequiresCurrentOnly({
    operation: "add",
    labels_after: ["shopping-order", "receipt-billing"],
  }), true);
  assert.equal(progression.hasApprovedLabelChange({
    operation: "only",
    labels_after: ["personal"],
  }), true);

  assert.deepEqual(progression.handledAcknowledgementAction({
    items: [item("a"), item("b")],
    currentIdentity: { provider: "gmail", message_id: "a" },
    activeProvider: "gmail",
  }), {
    hasNext: true,
    label: "Looks right · Next",
    item: item("b"),
  });
  assert.deepEqual(progression.handledAcknowledgementAction({
    items: [item("a")],
    currentIdentity: { provider: "gmail", message_id: "a" },
    activeProvider: "gmail",
  }), {
    hasNext: false,
    label: "Looks right · Check queue",
    item: null,
  });
  assert.equal(progression.decisionMayAdvance({
    localAccepted: false,
    responseReceived: false,
    responseAccepted: null,
  }), false, "a decision cannot advance before local acceptance");
  assert.equal(progression.decisionMayAdvance({
    localAccepted: false,
    responseReceived: true,
    responseAccepted: false,
  }), false, "a rejected response cannot advance review");
  assert.equal(progression.decisionMayAdvance({
    localAccepted: true,
    responseReceived: true,
    responseAccepted: true,
  }), true, "an accepted local response can advance while provider work continues");

  const token = progression.createRequestToken({
    generation: 7,
    kind: "teach-apply",
    identity: { provider: "gmail", message_id: "a" },
  });
  assert.equal(Object.isFrozen(token), true);
  assert.equal(token.token, "teach-apply:7:gmail:a");
  const firstAttempt = progression.createRequestToken({
    generation: 7,
    kind: "teach-apply",
    identity: { provider: "gmail", message_id: "a" },
    attemptId: "attempt-a",
  });
  const secondAttempt = progression.createRequestToken({
    generation: 7,
    kind: "teach-apply",
    identity: { provider: "gmail", message_id: "a" },
    attemptId: "attempt-b",
  });
  assert.notEqual(firstAttempt.token, secondAttempt.token, "provider receipts are bound to one apply attempt");
  assert.equal(progression.matchesRequestToken(token, {
    generation: 7,
    identity: { provider: "gmail", message_id: "a" },
  }), true);
  assert.equal(progression.matchesRequestToken(token, {
    generation: 7,
    identity: { provider: "protonmail", message_id: "a" },
  }), false);
  assert.equal(progression.matchesRequestToken(token, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a" },
  }), false);
  const threadedToken = progression.createRequestToken({
    generation: 8,
    kind: "teach-apply",
    identity: { provider: "gmail", message_id: "a", thread_id: "thread-a" },
  });
  assert.equal(progression.matchesRequestToken(threadedToken, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a", thread_id: "thread-a" },
  }), true);
  assert.equal(progression.matchesRequestToken(threadedToken, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a", thread_id: "thread-b" },
  }), false, "a response from another thread cannot match the flight");
  assert.equal(progression.matchesRequestToken(threadedToken, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a" },
  }), true, "display matching may tolerate a queue item without a thread id");
  assert.equal(progression.responseMatchesToken(threadedToken, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a" },
  }), false, "a response omitting a known thread id cannot authorize item UI");
  assert.equal(progression.responseMatchesToken(threadedToken, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a", thread_id: "thread-b" },
  }), false, "a response changing a known thread id cannot authorize item UI");
  assert.equal(progression.responseMatchesToken(threadedToken, {
    generation: 8,
    identity: { provider: "gmail", message_id: "a", thread_id: "thread-a" },
  }), true, "a response with the known thread id authorizes the item UI");

  const recoverySelected = {
    all_labels: ["shopping-order", "receipt-billing"],
    details: {
      write_status: "applied",
      inbox_status: "ineligible",
      provider_write_receipt: {
        request_id: token.token,
        status: "applied",
        final_labels: ["shopping-order", "receipt-billing"],
      },
    },
  };
  assert.deepEqual(progression.recoveryConfirmation({
    responseOk: true,
    sameMessage: true,
    selected: recoverySelected,
    expectedLabels: ["shopping-order", "receipt-billing"],
    requestId: token.token,
  }), {
    localAccepted: true,
    confirmed: true,
    providerFailed: false,
    inboxRemoved: false,
  });
  assert.equal(progression.recoveryConfirmation({
    responseOk: true,
    sameMessage: true,
    selected: recoverySelected,
    expectedLabels: ["shopping-order"],
    requestId: token.token,
  }).confirmed, false, "the old primary label cannot confirm a missing secondary label");
  assert.equal(progression.recoveryConfirmation({
    responseOk: true,
    sameMessage: true,
    selected: recoverySelected,
    expectedLabels: ["shopping-order", "receipt-billing"],
    requestId: "teach-apply:8:gmail:a",
  }).confirmed, false, "a stale provider receipt cannot confirm a newer attempt");
  assert.deepEqual(progression.recoveryConfirmation({
    responseOk: true,
    sameMessage: true,
    selected: {
      ...recoverySelected,
      details: {
        ...recoverySelected.details,
        write_status: "failed",
        provider_write_receipt: {
          ...recoverySelected.details.provider_write_receipt,
          status: "failed",
        },
      },
    },
    expectedLabels: ["shopping-order", "receipt-billing"],
    requestId: token.token,
  }), {
    localAccepted: true,
    confirmed: false,
    providerFailed: true,
    inboxRemoved: false,
  }, "a failed exact attempt proves only local acceptance and remains retryable");

  const filteredEmpty = progression.completionPresentation({
    query: "not-loaded",
    loadedItems: [],
    activeProvider: "gmail",
    committedIdentities: [],
  });
  assert.equal(filteredEmpty.kind, progression.FILTERED_EMPTY);
  assert.match(filteredEmpty.title, /No loaded review emails match/);

  const checking = progression.completionPresentation({
    loadedItems: [item("a")],
    activeProvider: "gmail",
    committedIdentities: ["gmail:a"],
    refreshGeneration: 2,
    expectedGeneration: 2,
  });
  assert.equal(checking.kind, progression.CHECKING);

  const next = progression.completionPresentation({
    loadedItems: [item("a")],
    freshState: {
      needs_attention_items: [item("a"), item("b")],
      sidebar_state: { daily_summary: { needs_attention_count: 1 } },
    },
    activeProvider: "gmail",
    committedIdentities: ["gmail:a"],
    refreshGeneration: 2,
    expectedGeneration: 2,
  });
  assert.equal(next.kind, progression.NEXT_AVAILABLE);
  assert.equal(next.item.message_id, "b");

  const complete = progression.completionPresentation({
    loadedItems: [item("a")],
    freshState: {
      needs_attention_items: [],
      sidebar_state: { daily_summary: { needs_attention_count: 0 } },
    },
    activeProvider: "gmail",
    committedIdentities: ["gmail:a"],
    refreshGeneration: 3,
    expectedGeneration: 3,
  });
  assert.equal(complete.kind, progression.COMPLETE);
  assert.equal(complete.title, "Review queue complete");

  for (const invalidZero of [null, undefined, "", "0", Number.NaN, Number.POSITIVE_INFINITY]) {
    const notComplete = progression.completionPresentation({
      loadedItems: [item("a")],
      freshState: {
        needs_attention_items: [],
        sidebar_state: { daily_summary: { needs_attention_count: invalidZero } },
      },
      activeProvider: "gmail",
      committedIdentities: ["gmail:a"],
      refreshGeneration: 3,
      expectedGeneration: 3,
    });
    assert.notEqual(notComplete.kind, progression.COMPLETE, `non-numeric count ${String(invalidZero)} cannot verify zero`);
  }
  assert.equal(progression.isExplicitFiniteNumericZero(0), true);
  assert.equal(progression.isExplicitFiniteNumericZero(null), false);
  assert.equal(progression.isExplicitFiniteNumericZero("0"), false);

  const retry = progression.completionPresentation({
    loadedItems: [item("a")],
    freshState: { needs_attention_items: [] },
    activeProvider: "gmail",
    committedIdentities: ["gmail:a"],
    refreshGeneration: 3,
    expectedGeneration: 3,
  });
  assert.equal(retry.kind, progression.CHECKING);
  const explicitRetry = progression.completionPresentation({
    loadedItems: [item("a")],
    activeProvider: "gmail",
    committedIdentities: ["gmail:a"],
    error: "Synthetic state read failed.",
  });
  assert.equal(explicitRetry.kind, progression.RETRY);
  const missingFreshQueue = progression.completionPresentation({
    loadedItems: [item("a")],
    freshState: {
      sidebar_state: { daily_summary: { needs_attention_count: 0 } },
    },
    activeProvider: "gmail",
    committedIdentities: ["gmail:a"],
    refreshGeneration: 4,
    expectedGeneration: 4,
  });
  assert.equal(missingFreshQueue.kind, progression.RETRY, "missing fresh queue fields cannot fall back to stale local arrays");

  assert.deepEqual(progression.previousDecisionStatus({ localAccepted: false }), {
    visible: false,
    state: "hidden",
    label: "",
    message: "",
  });
  assert.equal(
    progression.previousDecisionStatus({ localAccepted: true, providerName: "Gmail" }).message,
    "Updating Gmail in the background",
  );
  assert.deepEqual(
    progression.previousDecisionStatus({
      localAccepted: true,
      providerName: "Gmail",
      responseReceived: false,
    }),
    {
      visible: true,
      state: "working",
      label: "Previous decision sent",
      message: "Waiting for Threadwise to confirm the local save",
    },
  );
  assert.match(
    progression.previousDecisionStatus({
      localAccepted: true,
      providerName: "Gmail",
      responseReceived: true,
      responseAccepted: false,
    }).message,
    /did not confirm the local save/,
  );
  assert.match(
    progression.previousDecisionStatus({
      localAccepted: true,
      providerName: "Gmail",
      responseReceived: true,
      responseAccepted: false,
      decisionKind: "handled-review-acknowledge",
    }).message,
    /review acknowledgement/,
  );
  assert.match(
    progression.previousDecisionStatus({ localAccepted: true, providerWriteState: "retry", providerName: "Gmail" }).message,
    /needs a retry/,
  );
  assert.match(
    progression.previousDecisionStatus({ localAccepted: true, providerWriteState: "done", providerName: "Gmail" }).message,
    /not a per-message provider confirmation/,
  );

  console.log("gmail companion review progression tests passed");
}

try {
  run();
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
