const assert = require("node:assert/strict");
const navigation = require("../extensions/gmail_companion/queue_navigation.js");

function item(messageId, overrides = {}) {
  return {
    provider: "gmail",
    message_id: messageId,
    sender: "sender@example.test",
    subject: "A queue message",
    classification: "needs review",
    status_label: "Needs attention",
    status: "pending",
    ...overrides,
  };
}

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

function run() {
  assert.equal(Object.isFrozen(navigation), true, "the public API is frozen");
  assert.equal(globalThis.ThreadwiseQueueNavigation, navigation);

  assert.equal(navigation.normalizeQuery("  Needs   ATTENTION  "), "needs attention");
  assert.equal(navigation.normalizeQuery(null), "");
  assert.equal(navigation.normalizeQuery(42), "42");

  const searchable = navigation.buildSearchableText(item("gmail-1", {
    sender: "Acme Updates <updates@example.test>",
    subject: "Your quarterly invoice",
    classification: "Finance",
    suggested_label: "billing",
    applied_labels: ["EA/finance", "important"],
    status_label: "Needs attention",
    status: "write-unconfirmed",
  }));
  assert.match(searchable, /acme updates/);
  assert.match(searchable, /quarterly invoice/);
  assert.match(searchable, /finance/);
  assert.match(searchable, /billing/);
  assert.match(searchable, /ea\/finance/);
  assert.match(searchable, /needs attention/);
  assert.match(searchable, /write-unconfirmed/);
  assert.equal(navigation.searchableText(item("gmail-2", { subject: "Same" })),
    navigation.buildSearchableText(item("gmail-2", { subject: "Same" })));

  const providerless = item("gmail-c", {
    sender: "Delta <delta@example.test>",
    subject: "Project planning",
    source: "latest stored run",
  });
  delete providerless.provider;

  const source = [
    item("gmail-a", {
      sender: "Alpha <alpha@example.test>",
      subject: "Project planning",
      status: "pending",
    }),
    item("proton-a", {
      provider: "protonmail",
      sender: "Beta <beta@example.test>",
      subject: "Project planning",
    }),
    item("gmail-b", {
      sender: "Gamma <gamma@example.test>",
      subject: "Receipt",
      status_label: "Needs review",
      status: "write-unconfirmed",
      suggested_label: "finance",
    }),
    providerless,
  ];

  assert.deepEqual(
    navigation.filterQueueItems(source, "gmail", "project"),
    [source[0], source[3]],
    "matching is local, provider-safe, and source-order preserving",
  );
  assert.deepEqual(
    navigation.filterQueueItems(source, "gmail", "FINANCE"),
    [source[2]],
    "classification/label and status fields are searchable",
  );
  assert.deepEqual(
    navigation.filterQueueItems(source, "gmail", ""),
    [source[0], source[2], source[3]],
    "an empty query restores order without mistaking source metadata for a provider",
  );
  assert.deepEqual(
    navigation.filterQueueItems(source, "protonmail", ""),
    [source[1], source[3]],
    "providerless items inherit the already-scoped active queue",
  );
  assert.deepEqual(navigation.filterQueueItems(source, "gmail", "not loaded"), []);
  assert.deepEqual(navigation.filterQueueItems(null, "gmail", "anything"), []);
  assert.deepEqual(
    navigation.filterQueue(source, "project", "gmail"),
    [source[0], source[3]],
    "the query-first convenience form uses the same safe filter",
  );

  const queue = [item("message-a"), item("message-b"), item("message-c")];
  assert.equal(navigation.findCurrentItem(queue, "message-b"), queue[1]);
  assert.equal(navigation.findCurrentItem(queue, "missing"), null);
  assert.equal(navigation.findNextItem(queue, "message-b"), queue[2]);
  assert.equal(navigation.findPreviousItem(queue, "message-b"), queue[0]);
  assert.equal(navigation.findPreviousItem(queue, "message-a"), null);
  assert.equal(navigation.findNextItem(queue, "message-c"), null);
  assert.equal(navigation.findNextItem(queue, "missing"), null);
  assert.deepEqual(navigation.queueNeighbors(queue, "message-b"), {
    current: queue[1],
    previous: queue[0],
    next: queue[2],
  });
  assert.deepEqual(navigation.queueNeighbors(queue, "missing"), {
    current: null,
    previous: null,
    next: null,
  });

  const input = node("INPUT");
  const button = node("BUTTON");
  const buttonChild = node("SPAN", {}, button);
  const editable = node("DIV", { contenteditable: "true" });
  const nonEditable = node("DIV", { contenteditable: "false" });
  const summary = node("SUMMARY");
  const link = node("A");
  assert.equal(navigation.isEditableTarget(input), true);
  assert.equal(navigation.isEditableTarget(editable), true);
  assert.equal(navigation.isEditableTarget(nonEditable), false);
  assert.equal(navigation.isNativeInteractiveTarget(button), true);
  assert.equal(navigation.isNativeInteractiveTarget(buttonChild), true);
  assert.equal(navigation.isNativeInteractiveTarget(summary), true);
  assert.equal(navigation.isNativeInteractiveTarget(link), true);
  assert.equal(navigation.isInteractiveTarget(input), true);
  assert.equal(navigation.isInteractiveTarget(buttonChild), true);

  const root = node("ASIDE");
  const panelChild = node("DIV", {}, root);
  const contextualTrigger = node("BUTTON", {}, root);
  const outside = node("DIV");
  assert.equal(navigation.classifyPanelKey({ key: "j", target: panelChild }, root), "next");
  assert.equal(navigation.classifyPanelKey({ key: "K", target: panelChild }, root), "previous");
  assert.equal(navigation.classifyPanelKey({ key: "Enter", target: root }, root), "primary-action");
  assert.equal(navigation.classifyPanelKey({ key: "Escape", target: panelChild }, root), "escape");
  assert.equal(
    navigation.classifyPanelKey({ key: "Escape", target: contextualTrigger }, root),
    "escape",
    "Escape retreats after a contextual menu restores focus to its interactive trigger",
  );
  assert.equal(navigation.classifyPanelKey({ key: "j", target: outside }, root), null);
  assert.equal(navigation.classifyPanelKey({ key: "Enter", target: buttonChild }, root), null);
  assert.equal(navigation.classifyPanelKey({ key: "Escape", target: input }, root), null);
  assert.equal(navigation.classifyPanelKey({ key: "Escape", target: contextualTrigger, shiftKey: true }, root), null);
  assert.equal(navigation.classifyPanelKey({ key: "j", target: panelChild, ctrlKey: true }, root), null);
  assert.equal(navigation.classifyPanelKey({ key: "x", target: panelChild }, root), null);
  assert.equal(navigation.classifyPanelKey({ key: "j", target: panelChild }), null);

  console.log("gmail companion queue navigation tests passed");
}

try {
  run();
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
