const assert = require("node:assert/strict");

const messages = [];
let now = 100;
global.chrome = {
  runtime: {
    getManifest: () => ({ version: "0.1.0" }),
    sendMessage: (message) => messages.push(message),
  },
};
global.performance = { now: () => now };

require("../extensions/gmail_companion/analytics.js");

const analytics = global.ThreadwiseAnalytics;
assert.equal(analytics.openExtension(), true);
assert.equal(analytics.showOnboarding("2026-08-09-v1", "selected-email"), true);
assert.equal(analytics.completeOnboarding("2026-08-09-v1", "selected-email"), true);
assert.equal(analytics.dismissOnboarding("2026-08-09-v1", "not-ready"), true);
assert.equal(analytics.openReviewQueue(7), true);
assert.equal(analytics.startEmailReview("local-only-message-key", "needs_attention_queue", 7), true);
now = 1350;
assert.equal(analytics.decideSuggestion("edit"), true);
assert.equal(analytics.confirmRule("included_existing", 3, false), true);
assert.equal(analytics.completeReviewBatch(7), true);

assert.deepEqual(
  messages.map((message) => message.event),
  [
    "extension opened",
    "onboarding shown",
    "onboarding completed",
    "onboarding dismissed",
    "review queue opened",
    "email review started",
    "suggestion decision made",
    "rule confirmed",
    "review batch completed",
  ],
);
assert.equal(messages[1].properties.onboarding_version, "2026-08-09-v1");
assert.equal(messages[1].properties.onboarding_destination, "selected-email");
assert.equal(messages[3].properties.onboarding_destination, "not-ready");
assert.equal(messages[4].properties.queue_size_bucket, "6-10");
assert.equal(messages[6].properties.duration_ms, 1250);
assert.equal(messages[7].properties.affected_count_bucket, "2-5");
assert.equal(messages.some((message) => JSON.stringify(message).includes("local-only-message-key")), false);
for (const message of messages) {
  assert.equal(message.type, "threadwise:analytics");
  assert.equal(message.properties.app_version, "0.1.0");
  assert.equal(message.properties.workflow_version, "gmail-companion-v1");
  assert.equal(message.properties.source, "extension");
  assert.equal(message.properties.provider, "gmail");
}
