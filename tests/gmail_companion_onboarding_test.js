const assert = require("node:assert/strict");
const onboarding = require("../extensions/gmail_companion/onboarding.js");

class MemoryStorage {
  constructor() {
    this.values = {};
  }

  async get(key) {
    return { [key]: this.values[key] };
  }

  async set(values) {
    Object.assign(this.values, values);
  }
}

function selected(overrides = {}) {
  return {
    found: true,
    provider: "gmail",
    message_id: "selected-1",
    subject: "Selected message",
    sender: "sender@example.test",
    status: "needs-attention",
    ...overrides,
  };
}

function queueItem(provider, messageId) {
  return {
    provider,
    message_id: messageId,
    subject: `${provider} queue item`,
    sender: `${provider}@example.test`,
    status: "needs-attention",
  };
}

async function run() {
  const storage = new MemoryStorage();

  assert.deepEqual(await onboarding.load(storage), {
    version: onboarding.VERSION,
    status: "unseen",
  }, "missing state is fresh for the current onboarding version");

  await onboarding.markCompleted(storage);
  assert.equal((await onboarding.load(storage)).status, "completed");
  await onboarding.markDismissed(storage);
  assert.equal((await onboarding.load(storage)).status, "dismissed");
  await onboarding.markActive(storage);
  assert.equal((await onboarding.load(storage)).status, "active");

  storage.values[onboarding.STORAGE_KEY] = {
    version: "old-version",
    status: "completed",
  };
  assert.deepEqual(await onboarding.load(storage), {
    version: onboarding.VERSION,
    status: "unseen",
  }, "old onboarding versions are unseen again");

  const gmailQueue = queueItem("gmail", "gmail-queue-1");
  const protonQueue = queueItem("protonmail", "proton-queue-1");
  assert.deepEqual(
    onboarding.resolveTarget({
      provider: "gmail",
      selectedEmail: selected(),
      needsAttentionItems: [protonQueue, gmailQueue],
    }),
    {
      kind: "selected-email",
      provider: "gmail",
      message_id: "selected-1",
      subject: "Selected message",
      sender: "sender@example.test",
    },
    "a reviewable selected email wins over the queue");

  assert.deepEqual(
    onboarding.resolveTarget({
      provider: "gmail",
      selectedEmail: selected({ status: "auto-handled" }),
      needsAttentionItems: [protonQueue, gmailQueue],
    }),
    {
      kind: "needs-attention",
      provider: "gmail",
      item: gmailQueue,
    },
    "the next item is provider-scoped when the selection is already handled");

  assert.deepEqual(
    onboarding.resolveTarget({
      provider: "gmail",
      selectedEmail: { found: false, status: "not-in-snapshot" },
      needsAttentionItems: [protonQueue],
    }),
    { kind: "home", provider: "gmail" },
    "Home is the honest fallback when no provider-scoped review exists");

  assert.equal(onboarding.isReviewableSelected(selected({ status: "kept-visible" })), false);
  assert.equal(onboarding.isReviewableSelected(selected({ status: "write-unconfirmed" })), true);
  console.log("gmail companion onboarding tests passed");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
