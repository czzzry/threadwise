import assert from "node:assert/strict";
import test from "node:test";

import {
  applyTeachingToMatches,
  confirmMessage,
  createDemoState,
  folderCounts,
  matchingMessages,
  saveTeachingForFuture,
} from "../docs/demo/model.mjs";

test("the synthetic inbox contains four real RoleScout matches", () => {
  const state = createDemoState();
  const matches = matchingMessages(state, "rolescout-current");

  assert.equal(state.messages.length, 12);
  assert.equal(matches.length, 4);
  assert.deepEqual(
    matches.map((message) => message.id),
    ["rolescout-current", "rolescout-berlin", "rolescout-ai-pm", "rolescout-startups"],
  );
});

test("applying the lesson changes exactly four rows and the derived folder counts", () => {
  const state = createDemoState();

  assert.deepEqual(folderCounts(state), {
    inbox: 12,
    "EA/Work": 2,
    "EA/Promotions": 5,
    "EA/LowValue": 1,
  });

  const affectedIds = applyTeachingToMatches(state, "rolescout-current");

  assert.equal(affectedIds.length, 4);
  assert.deepEqual(folderCounts(state), {
    inbox: 12,
    "EA/Work": 6,
    "EA/Promotions": 1,
    "EA/LowValue": 1,
  });
  assert.ok(affectedIds.every((id) => state.messages.find((message) => message.id === id).label === "EA/Work"));
  assert.equal(state.futureRules.length, 1);
});

test("future-only saves a visible rule without changing existing inbox labels", () => {
  const state = createDemoState();
  const before = state.messages.map(({ id, label }) => ({ id, label }));
  const countsBefore = folderCounts(state);

  saveTeachingForFuture(state, "rolescout-current");

  assert.deepEqual(state.messages.map(({ id, label }) => ({ id, label })), before);
  assert.deepEqual(folderCounts(state), countsBefore);
  assert.equal(state.futureRules.length, 1);
  assert.equal(state.mailboxStatus, "Future rule saved · existing inbox unchanged");
});

test("confirming a decision marks the row without changing its label", () => {
  const state = createDemoState();
  const message = state.messages.find(({ id }) => id === "project-partner");
  const initialLabel = message.label;

  confirmMessage(state, message.id);

  assert.equal(message.label, initialLabel);
  assert.equal(message.confirmed, true);
  assert.equal(state.mailboxStatus, "Decision confirmed · inbox labels unchanged");
});

test("a fresh demo state restores every visible mutation", () => {
  const state = createDemoState();
  applyTeachingToMatches(state, "rolescout-current");
  confirmMessage(state, "project-partner");

  const resetState = createDemoState();

  assert.deepEqual(folderCounts(resetState), {
    inbox: 12,
    "EA/Work": 2,
    "EA/Promotions": 5,
    "EA/LowValue": 1,
  });
  assert.equal(resetState.futureRules.length, 0);
  assert.equal(resetState.messages.some((message) => message.confirmed), false);
  assert.equal(resetState.lastAffectedIds.length, 0);
  assert.equal(resetState.mailboxStatus, "No demo changes yet");
});
