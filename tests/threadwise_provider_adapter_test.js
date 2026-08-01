const assert = require("node:assert/strict");

const { createProviderPageAdapter } = require("../extensions/gmail_companion/provider_adapter.js");

function node(text = "", attributes = {}) {
  return {
    textContent: text,
    getAttribute: (name) => attributes[name] || "",
    getBoundingClientRect: () => ({ width: 120, height: 30 }),
    closest: () => null,
    querySelector: () => null,
  };
}

function documentFixture({ one = {}, all = {} }) {
  return {
    querySelector: (selector) => one[selector] || null,
    querySelectorAll: (selector) => all[selector] || [],
  };
}

{
  const message = node("", {
    "data-legacy-message-id": "abcdef123456",
    "data-thread-perm-id": "gmail-thread-1",
  });
  const sender = node("Founder", { email: "founder@example.test" });
  message.closest = () => ({ querySelector: () => sender });
  const gmailDocument = documentFixture({
    one: { "h2.hP": node("A Gmail subject") },
    all: {
      "[data-legacy-message-id], [data-message-id]": [message],
      '[aria-label^="Search for all messages with label EA/"]': [node("EA/Work")],
    },
  });
  const gmailWindow = {
    location: {
      hostname: "mail.google.com",
      href: "https://mail.google.com/mail/u/0/#inbox/abcdef123456",
      hash: "#inbox/abcdef123456",
      pathname: "/mail/u/0/",
    },
    getComputedStyle: () => ({ display: "block", visibility: "visible" }),
  };
  const adapter = createProviderPageAdapter(gmailWindow, gmailDocument);

  assert.equal(adapter.id, "gmail");
  assert.equal(adapter.name, "Gmail");
  assert.equal(adapter.canRunManualSync, true);
  assert.equal(adapter.hasOpenMessage(), true);
  const context = adapter.selectedContext();
  assert.deepEqual(context, {
    provider: "gmail",
    message_id: "abcdef123456",
    thread_id: "gmail-thread-1",
    subject: "A Gmail subject",
    sender: "founder@example.test",
    gmail_labels: "EA/Work",
    page_url: gmailWindow.location.href,
    selected_at: context.selected_at,
  });
  assert.equal(
    adapter.messageUrl({ message_id: "abcdef123456" }),
    "https://mail.google.com/mail/u/0/#all/abcdef123456",
  );
}

{
  const protonDocument = documentFixture({
    one: {
      '[data-testid="conversation-header:subject"]': node("A Proton subject"),
      '[data-testid="message-header:sender-address"]': node("Founder", {
        title: "founder@proton.test",
      }),
    },
    all: {
      '[data-testid*="label"], [class*="label"]': [node("EA/Personal"), node("Inbox")],
    },
  });
  const protonWindow = {
    location: {
      hostname: "mail.proton.me",
      href: "https://mail.proton.me/u/0/inbox/proton-ref-1",
      hash: "",
      pathname: "/u/0/inbox/proton-ref-1",
    },
    getComputedStyle: () => ({ display: "block", visibility: "visible" }),
  };
  const adapter = createProviderPageAdapter(protonWindow, protonDocument);

  assert.equal(adapter.id, "protonmail");
  assert.equal(adapter.name, "Proton Mail");
  assert.equal(adapter.canRunManualSync, false);
  assert.equal(adapter.hasOpenMessage(), true);
  const context = adapter.selectedContext();
  assert.equal(context.subject, "A Proton subject");
  assert.equal(context.sender, "Founder <founder@proton.test>");
  assert.equal(context.provider_labels, "EA/Personal");
  assert.equal(context.provider_ref, "proton-ref-1");
  assert.match(
    adapter.messageUrl({ subject: "A Proton subject", sender: "Founder <founder@proton.test>" }),
    /^https:\/\/mail\.proton\.me\/u\/0\/all-mail#keyword=/,
  );
}
