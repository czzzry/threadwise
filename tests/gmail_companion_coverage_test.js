const assert = require("node:assert/strict");
const coverage = require("../extensions/gmail_companion/coverage.js");

function run() {
  assert.equal(Object.isFrozen(coverage), true);
  assert.equal(coverage.model({}).status, "unknown");
  assert.equal(coverage.model({}).action, "Check inbox");
  assert.doesNotMatch(JSON.stringify(coverage.model({})), /Gmail/);
  assert.equal(coverage.model({ status: "checking" }).indicator, "indeterminate");

  const queue = coverage.model({ status: "queue-ready", checked_count: 42, needs_review_count: 6 });
  assert.equal(queue.title, "6 emails need your review");
  assert.equal(queue.action, "Review first");
  assert.equal(
    coverage.model({ status: "queue-ready", checked_count: 15, needs_review_count: 1 }).title,
    "1 email needs your review",
  );

  const clear = coverage.model({ status: "verified-clear", checked_count: 42, checked_at: new Date().toISOString() });
  assert.equal(clear.title, "Review queue clear");
  assert.match(clear.truthNote, /may still contain unread mail/);
  assert.equal(clear.indicator, "none");

  const stale = coverage.model({
    status: "verified-clear",
    checked_at: new Date(Date.now() - coverage.STALE_AFTER_MS - 1).toISOString(),
  });
  assert.equal(stale.status, "stale");
  assert.equal(stale.action, "Check inbox");

  for (const state of ["partial", "failed", "offline"]) {
    const model = coverage.model({ status: state, checked_count: 18, candidate_count: 42, read_failure_count: 24 });
    assert.equal(model.status, state);
    assert.ok(model.action);
    assert.doesNotMatch(model.title, /clear/i);
  }

  for (const state of ["failed", "offline"]) {
    const unavailable = coverage.model({ status: state });
    assert.deepEqual(unavailable.facts, { checked: "—", review: "—", freshness: "Unknown" });
  }

  const failedAfterCheck = coverage.model({
    status: "failed",
    checked_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    checked_count: 18,
    needs_review_count: 4,
  });
  assert.deepEqual(failedAfterCheck.facts, { checked: "18", review: "4", freshness: "2h ago" });
  assert.equal(coverage.freshnessLabel(""), "Unknown");
}

run();
console.log("gmail companion coverage tests passed");
