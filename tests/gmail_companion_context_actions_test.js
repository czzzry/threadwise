const assert = require("node:assert/strict");
const contextActions = require("../extensions/gmail_companion/context_actions.js");

function node(tagName, attributes = {}, parentElement = null) {
  return {
    tagName,
    parentElement,
    isContentEditable: attributes.isContentEditable,
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(attributes, name)
        ? attributes[name]
        : null;
    },
  };
}

function ids(actions) {
  return actions.map((action) => action.id);
}

function run() {
  assert.equal(Object.isFrozen(contextActions), true, "the public API is frozen");
  assert.equal(globalThis.ThreadwiseContextActions, contextActions);
  assert.equal(Object.isFrozen(contextActions.ALLOWLIST), true);
  assert.ok(contextActions.ALLOWLIST.length >= 10);
  assert.ok(contextActions.ALLOWLIST.every((action) => Object.isFrozen(action)));
  assert.ok(contextActions.ALLOWLIST.every((action) => (
    action.id && action.label && (action.dataAction || action.linkKind)
  )));

  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "review", hasSuggestedLabel: true })),
    ["change-label", "why", "open-email"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "review", hasSuggestedLabel: true, queuePreviewActive: true })),
    ["change-label", "why", "open-email", "back-to-queue"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "handled-receipt", detailsExpanded: false })),
    ["open-email", "why"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "handled-receipt", detailsExpanded: true })),
    ["open-email", "why"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "future-learning" })),
    ["not-now"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "current-apply-error" })),
    ["edit-current-apply"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "change" })),
    ["cancel-change"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "preview" })),
    ["edit-change"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "teach-preview" })),
    ["open-email", "edit-change"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "teach-scope" })),
    ["open-email", "keep-discussing"],
  );
  assert.deepEqual(ids(contextActions.deriveActions({ workspaceMode: "safety-preview" })), []);
  assert.deepEqual(ids(contextActions.deriveActions({ workspaceMode: "safety-error" })), []);
  assert.deepEqual(
    ids(contextActions.deriveActions({
      workspaceMode: "current-receipt",
      providerChangeSucceeded: true,
      queueComplete: false,
      receiptFailed: false,
    })),
    ["teach-future"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({
      workspaceMode: "current-receipt",
      providerChangeSucceeded: true,
      queueComplete: true,
      receiptFailed: false,
    })),
    ["teach-future", "back-home"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({
      workspaceMode: "partial-receipt",
      providerChangeSucceeded: false,
      queueComplete: true,
      receiptFailed: true,
    })),
    ["open-activity"],
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "blocked" })),
    [],
    "blocked has no invented handoff action",
  );
  assert.deepEqual(
    ids(contextActions.deriveActions({ workspaceMode: "home" })),
    [],
  );

  const capped = contextActions.deriveActions({
    workspaceMode: "current-receipt",
    providerChangeSucceeded: true,
    queueComplete: true,
    receiptFailed: true,
    enabledActions: {
      "teach-future": true,
      "back-home": true,
      "open-activity": true,
      "open-email": true,
      "back": true,
    },
  });
  assert.ok(capped.length <= 4);
  assert.equal(new Set(ids(capped)).size, capped.length);

  const root = node("ASIDE");
  const child = node("DIV", {}, root);
  const input = node("INPUT", {}, child);
  const button = node("BUTTON", {}, child);
  const link = node("A", {}, child);
  const summary = node("SUMMARY", {}, child);
  const editable = node("DIV", { contenteditable: "true" }, child);
  assert.equal(contextActions.isWithinRoot(child, root), true);
  assert.equal(contextActions.isWithinRoot(node("DIV"), root), false);
  assert.equal(contextActions.isEditableTarget(input), true);
  assert.equal(contextActions.isEditableTarget(editable), true);
  assert.equal(contextActions.isNativeInteractiveTarget(button), true);
  assert.equal(contextActions.isNativeInteractiveTarget(link), true);
  assert.equal(contextActions.isNativeInteractiveTarget(summary), true);
  assert.equal(contextActions.isRootShortcutTarget(child, root), true);
  assert.equal(contextActions.isRootShortcutTarget(input, root), false);
  assert.equal(contextActions.isRootShortcutTarget(button, root), false);
  assert.equal(contextActions.isRootShortcutTarget(node("DIV"), root), false);

  assert.equal(contextActions.classifyMenuKey({ key: ".", target: child }, root, false), "open");
  assert.equal(contextActions.classifyMenuKey({ key: ".", target: input }, root, false), null);
  assert.equal(contextActions.classifyMenuKey({ key: ".", target: button }, root, false), null);
  assert.equal(contextActions.classifyMenuKey({ key: ".", target: node("DIV") }, root, false), null);
  assert.equal(contextActions.classifyMenuKey({ key: "ArrowDown", target: button }, root, true), "next");
  assert.equal(contextActions.classifyMenuKey({ key: "ArrowUp", target: button }, root, true), "previous");
  assert.equal(contextActions.classifyMenuKey({ key: "Home", target: button }, root, true), "first");
  assert.equal(contextActions.classifyMenuKey({ key: "End", target: button }, root, true), "last");
  assert.equal(contextActions.classifyMenuKey({ key: "Enter", target: button }, root, true), "activate");
  assert.equal(contextActions.classifyMenuKey({ key: " ", target: button }, root, true), "activate");
  assert.equal(contextActions.classifyMenuKey({ key: "Escape", target: button }, root, true), "close");
  assert.equal(contextActions.classifyMenuKey({ key: "j", target: button }, root, true), "consume");
  assert.equal(contextActions.classifyMenuKey({ key: "j", target: child }, root, false), null);
  assert.equal(contextActions.classifyMenuKey({ key: "ArrowDown", target: button, ctrlKey: true }, root, true), null);

  assert.equal(contextActions.nextIndex(0, "next", 3), 1);
  assert.equal(contextActions.nextIndex(2, "next", 3), 2);
  assert.equal(contextActions.nextIndex(0, "previous", 3), 0);
  assert.equal(contextActions.nextIndex(1, "first", 3), 0);
  assert.equal(contextActions.nextIndex(1, "last", 3), 2);
  assert.equal(contextActions.nextIndex(2, "next", 0), -1);
  assert.equal(contextActions.nextIndex(99, "previous", 3), 1);

  console.log("gmail companion context actions tests passed");
}

try {
  run();
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
