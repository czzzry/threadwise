const assert = require("node:assert/strict");
const recovery = require("../extensions/gmail_companion/teaching_recovery.js");

function run() {
  assert.equal(Object.isFrozen(recovery), true);
  assert.equal(globalThis.ThreadwiseTeachingRecovery, recovery);

  assert.deepEqual(
    recovery.describe({
      operation: "preview",
      error: "Extension context invalidated.",
      providerName: "Proton Mail",
    }),
    {
      kind: "preview-error",
      category: "stale-extension",
      state_label: "Nothing changed",
      title: "Refresh Proton Mail to continue",
      message: "Threadwise was updated while this Proton Mail tab was open. Your instruction was not applied and no labels changed. Refresh Proton Mail, then enter the instruction again.",
      actions: [
        { action: "reload-provider-tab", label: "Refresh Proton Mail", primary: true },
      ],
    },
  );

  assert.deepEqual(
    recovery.describe({
      operation: "preview",
      response: {
        ok: false,
        status: 500,
        error: "Unexpected preview failure",
        connection_state: { kind: "ready" },
      },
      providerName: "Proton Mail",
    }),
    {
      kind: "preview-error",
      category: "preview-failed",
      state_label: "Nothing changed",
      title: "Could not interpret this instruction",
      message: "Threadwise is connected, but it could not prepare the AI interpretation. Your instruction was not applied and no labels changed.",
      actions: [
        { action: "retry-preview-teach", label: "Try AI preview again", primary: true },
      ],
    },
    "a healthy companion must never be described as unavailable",
  );

  const offline = recovery.describe({
    operation: "preview",
    response: {
      ok: false,
      error: "TypeError: Failed to fetch",
      connection_state: { kind: "helper-unreachable" },
    },
    providerName: "Gmail",
  });
  assert.equal(offline.category, "companion-offline");
  assert.equal(offline.title, "Threadwise is stopped");
  assert.match(offline.message, /instruction was not applied and no labels changed/i);
  assert.deepEqual(offline.actions, [
    { action: "force-refresh", label: "Check connection", primary: true },
  ]);

  const aiUnavailable = recovery.describe({
    operation: "preview",
    response: {
      ok: false,
      status: 503,
      error: "LLM review was unavailable.",
      connection_state: { kind: "ready" },
    },
    providerName: "Gmail",
  });
  assert.equal(aiUnavailable.category, "ai-unavailable");
  assert.equal(aiUnavailable.title, "AI review could not finish");
  assert.equal(aiUnavailable.actions[0].label, "Try AI preview again");

  const quotaExceeded = recovery.describe({
    operation: "preview",
    response: {
      ok: false,
      status: 402,
      payload: {
        error: "The connected OpenAI account has no available API quota.",
        error_code: "quota_exceeded",
        provider: "openai",
        provider_code: "insufficient_quota",
        retryable: false,
      },
      connection_state: { kind: "ready" },
    },
    providerName: "Proton Mail",
  });
  assert.equal(quotaExceeded.category, "ai-quota-exceeded");
  assert.equal(quotaExceeded.title, "OpenAI API credits or usage limit reached");
  assert.match(quotaExceeded.message, /instruction was not applied and no labels changed/i);
  assert.match(quotaExceeded.message, /add API credits or raise the project's usage limit/i);

  const rejectedKey = recovery.describe({
    operation: "preview",
    response: {
      ok: false,
      status: 401,
      payload: { error_code: "authentication_failed", provider: "openai" },
      connection_state: { kind: "ready" },
    },
    providerName: "Gmail",
  });
  assert.equal(rejectedKey.category, "ai-authentication-failed");
  assert.equal(rejectedKey.title, "OpenAI API key was rejected");

  const rateLimited = recovery.describe({
    operation: "preview",
    response: {
      ok: false,
      status: 429,
      payload: { error_code: "rate_limited", provider: "openai", retryable: true },
      connection_state: { kind: "ready" },
    },
    providerName: "Gmail",
  });
  assert.equal(rateLimited.category, "ai-rate-limited");
  assert.equal(rateLimited.title, "OpenAI is temporarily rate-limited");

  const applyFailure = recovery.describe({
    operation: "apply",
    response: {
      ok: false,
      status: 500,
      error: "Unexpected write failure",
      connection_state: { kind: "ready" },
    },
    providerName: "Proton Mail",
  });
  assert.equal(applyFailure.title, "Could not confirm this change");
  assert.equal(applyFailure.state_label, "Status unconfirmed");
  assert.doesNotMatch(applyFailure.message, /nothing changed/i);
  assert.match(applyFailure.message, /Threadwise will check whether anything changed before retrying/i);
  assert.deepEqual(applyFailure.actions, [
    { action: "retry-apply-teach", label: "Check and retry", primary: true },
  ]);
}

run();
