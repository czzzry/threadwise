import assert from "node:assert/strict";
import test from "node:test";

import {
  applyTeachingToMatches,
  confirmMessage,
  createDemoState,
  folderCounts,
  matchingMessages,
  matchingMessagesNeedingUpdate,
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
  assert.equal(state.lastRuleAdded, true);
});

test("reapplying the lesson reports no inbox or rule delta", () => {
  const state = createDemoState();
  applyTeachingToMatches(state, "rolescout-current");
  const countsBeforeReplay = folderCounts(state);

  const affectedIds = applyTeachingToMatches(state, "rolescout-current");

  assert.deepEqual(affectedIds, []);
  assert.deepEqual(matchingMessagesNeedingUpdate(state, "rolescout-current"), []);
  assert.deepEqual(folderCounts(state), countsBeforeReplay);
  assert.equal(state.futureRules.length, 1);
  assert.equal(state.lastRuleAdded, false);
  assert.equal(state.mailboxStatus, "0 emails moved to EA/Work · future rule already saved");
});

test("future-only saves a visible rule without changing existing inbox labels", () => {
  const state = createDemoState();
  const before = state.messages.map(({ id, label }) => ({ id, label }));
  const countsBefore = folderCounts(state);

  const saved = saveTeachingForFuture(state, "rolescout-current");

  assert.equal(saved, true);
  assert.deepEqual(state.messages.map(({ id, label }) => ({ id, label })), before);
  assert.deepEqual(folderCounts(state), countsBefore);
  assert.equal(state.futureRules.length, 1);
  assert.equal(state.mailboxStatus, "Future rule saved · existing inbox unchanged");
});

test("saving an existing future lesson reports no new rule", () => {
  const state = createDemoState();
  saveTeachingForFuture(state, "rolescout-current");

  const saved = saveTeachingForFuture(state, "rolescout-current");

  assert.equal(saved, false);
  assert.equal(state.futureRules.length, 1);
  assert.equal(state.lastRuleAdded, false);
  assert.equal(state.mailboxStatus, "Future rule already saved · existing inbox unchanged");
});

test("confirming a decision marks the row without changing its label", () => {
  const state = createDemoState();
  const message = state.messages.find(({ id }) => id === "project-partner");
  const initialLabel = message.label;

  const confirmed = confirmMessage(state, message.id);

  assert.equal(confirmed, true);
  assert.equal(message.label, initialLabel);
  assert.equal(message.confirmed, true);
  assert.equal(state.mailboxStatus, "Decision confirmed · inbox labels unchanged");
});

test("confirming an existing decision reports no new confirmation", () => {
  const state = createDemoState();
  confirmMessage(state, "project-partner");

  const confirmed = confirmMessage(state, "project-partner");

  assert.equal(confirmed, false);
  assert.equal(state.lastConfirmationAdded, false);
  assert.equal(state.mailboxStatus, "Decision already confirmed · inbox labels unchanged");
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
  assert.equal(resetState.lastRuleAdded, false);
  assert.equal(resetState.lastConfirmationAdded, false);
  assert.equal(resetState.mailboxStatus, "No demo changes yet");
});
