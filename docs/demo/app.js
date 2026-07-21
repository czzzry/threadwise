const roleScoutTeaching = Object.freeze({
  initialLabel: "Promotions",
  initialReason: "A recurring recommendation email with a promotional format. Threadwise kept it visible because the sender also matches your job-search context.",
  targetLabel: "EA/Work",
  defaultNote: "Job recommendations from RoleScout belong in Work, not Promotions.",
  matchCount: 4,
  appliedReason: "A recurring job recommendation that supports the active search workflow. The user confirmed that RoleScout belongs with Work.",
});

const messages = [
  {
    id: "rolescout",
    sender: "RoleScout Jobs",
    address: "jobs@example.test",
    subject: "Senior AI product roles this week",
    preview: "New recommendations based on your saved search.",
    time: "9:42 AM",
    label: roleScoutTeaching.initialLabel,
    reason: roleScoutTeaching.initialReason,
    teaching: roleScoutTeaching,
  },
  {
    id: "project-partner",
    sender: "Project Partner",
    address: "partner@example.test",
    subject: "Can you approve the demo copy?",
    preview: "Please confirm the final wording before release.",
    time: "9:31 AM",
    label: "EA/Work",
    reason: "A direct request from a known collaborator with a clear decision needed.",
  },
  {
    id: "northstar",
    sender: "Northstar Weekly",
    address: "digest@example.test",
    subject: "Five useful essays worth reading",
    preview: "A concise roundup from a sender you usually keep.",
    time: "8:21 AM",
    label: "Updates",
    reason: "A recurring editorial digest. It is useful, but no immediate action is required.",
  },
  {
    id: "daily-deals",
    sender: "Daily Deals Outlet",
    address: "offers@example.test",
    subject: "Final hours: workspace gear sale",
    preview: "The offer ends tonight.",
    time: "7:55 AM",
    label: "EA/LowValue",
    reason: "A time-limited retail promotion from a high-volume sender with no prior engagement.",
  },
  {
    id: "repo-security",
    sender: "Repo Security",
    address: "alerts@example.test",
    subject: "Dependency alert resolved",
    preview: "The patched version is now on the default branch.",
    time: "7:18 AM",
    label: "EA/Work",
    reason: "A project notification that confirms a security-sensitive task has been resolved.",
  },
  {
    id: "city-rail",
    sender: "City Rail",
    address: "tickets@example.test",
    subject: "Your trip receipt",
    preview: "Booking confirmation and travel details.",
    time: "6:44 AM",
    label: "Receipts",
    reason: "A transactional message containing a purchase receipt and travel record.",
  },
];

const state = {
  selectedId: messages[0].id,
  mode: "current",
  corrected: false,
  teachingNote: "",
  receiptAction: null,
};

const messageList = document.querySelector("#message-list");
const companion = document.querySelector("#companion-content");

function selectedMessage() {
  return messages.find((message) => message.id === state.selectedId);
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}

function beginTeaching(message) {
  if (!message.teaching) return;
  state.teachingNote = message.teaching.defaultNote;
  state.receiptAction = null;
  state.mode = "teach";
}

function renderMessages() {
  messageList.innerHTML = messages
    .map(
      (message) => `
        <button class="message-row" type="button" data-message-id="${message.id}" aria-pressed="${message.id === state.selectedId}">
          <strong>${message.sender}</strong>
          <span class="subject">${message.subject} <span aria-hidden="true">-</span> ${message.preview}</span>
          <time>${message.time}</time>
        </button>
      `,
    )
    .join("");
}

function panelHeading(message) {
  return `
    <div>
      <p class="section-label">Selected email</p>
      <h2 class="email-title">${message.subject}</h2>
      <p class="sender">${message.sender} &lt;${message.address}&gt;</p>
    </div>
  `;
}

function renderCurrent(message) {
  const teachingHint = message.teaching
    ? state.corrected
      ? "The guided correction is complete. You can run it again or inspect another synthetic email."
      : "Try the flow: this job alert belongs with Work, not Promotions."
    : "This message is available for inspection. The guided teaching scenario uses the RoleScout job alert.";
  const teachingAction = message.teaching
    ? '<button class="action primary" type="button" data-action="correct">Correct / teach</button>'
    : '<button class="action primary" type="button" data-action="open-guided-teaching">Try RoleScout correction</button>';

  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill ${state.corrected && message.id === "rolescout" ? "success" : ""}">${message.label}</span>
      <span class="pill success">Kept visible</span>
    </div>
    <div class="reason">
      <p class="section-label">Why</p>
      ${message.reason}
    </div>
    <p class="flow-hint">${teachingHint}</p>
    <div class="button-row">
      ${teachingAction}
      <button class="action quiet" type="button" data-action="looks-right">Looks right</button>
    </div>
  `;
}

function renderTeach(message) {
  if (!message.teaching) {
    renderCurrent(message);
    return;
  }

  companion.innerHTML = `
    ${panelHeading(message)}
    <form class="teach-form" data-form="teach">
      <label for="teaching-note">What should Threadwise understand?</label>
      <textarea id="teaching-note" name="teaching-note">${escapeHtml(state.teachingNote)}</textarea>
    </form>
    <div class="reason">
      <p class="section-label">Nothing has changed yet</p>
      Threadwise will first turn your note into a proposed rule and check how many other messages it would affect.
    </div>
    <div class="button-row">
      <button class="action primary" type="button" data-action="preview">Preview change</button>
      <button class="action quiet" type="button" data-action="cancel">Cancel</button>
    </div>
  `;
}

function renderPreview(message) {
  if (!message.teaching) {
    renderCurrent(message);
    return;
  }

  const earlierMatches = message.teaching.matchCount - 1;
  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill">${message.label}</span>
      <span class="pill success">→ ${message.teaching.targetLabel}</span>
    </div>
    <div class="impact">
      <strong>I found ${message.teaching.matchCount} matching emails before changing anything.</strong>
      The current email will move to ${message.teaching.targetLabel}. ${earlierMatches} earlier ${message.sender} recommendations match the same proposed rule.
    </div>
    <p class="flow-hint">Choose the scope explicitly. The hosted demo changes only this synthetic page.</p>
    <div class="button-row">
      <button class="action confirm" type="button" data-action="apply-matches">Apply to ${message.teaching.matchCount}</button>
      <button class="action" type="button" data-action="future-only">Use for future only</button>
      <button class="action quiet" type="button" data-action="keep-discussing">Keep discussing</button>
    </div>
  `;
}

function renderReceipt(message) {
  if (!message.teaching) {
    renderCurrent(message);
    return;
  }

  const futureOnly = state.receiptAction === "future-only";
  const receiptHeading = futureOnly ? "Future lesson saved." : "Updated in the synthetic inbox.";
  const receiptBody = futureOnly
    ? `Threadwise saved the lesson for future ${message.sender} recommendations. The current email and all other existing demo messages were unchanged.`
    : `Threadwise changed the ${message.teaching.matchCount} matching demo messages to ${message.teaching.targetLabel} and saved the lesson for future ${message.sender} recommendations.`;

  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill ${futureOnly ? "" : "success"}">${message.label}</span>
      <span class="pill success">Kept visible</span>
    </div>
    <div class="receipt">
      <strong>${receiptHeading}</strong>
      ${receiptBody}
    </div>
    <p class="flow-hint">In the real product this receipt appears only after provider-side verification. No provider exists on this page.</p>
    <div class="button-row">
      <button class="action primary" type="button" data-action="restart">Run the demo again</button>
    </div>
  `;
}

function renderPanel() {
  const message = selectedMessage();
  if (state.mode === "teach") {
    renderTeach(message);
  } else if (state.mode === "preview") {
    renderPreview(message);
  } else if (state.mode === "receipt") {
    renderReceipt(message);
  } else {
    renderCurrent(message);
  }
}

messageList.addEventListener("click", (event) => {
  const row = event.target.closest("[data-message-id]");
  if (!row) return;
  state.selectedId = row.dataset.messageId;
  state.mode = "current";
  renderMessages();
  renderPanel();
});

companion.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;

  const action = button.dataset.action;
  const message = selectedMessage();
  if (action === "correct") {
    beginTeaching(message);
  } else if (action === "open-guided-teaching") {
    const guidedMessage = messages.find((item) => item.teaching);
    state.selectedId = guidedMessage.id;
    beginTeaching(guidedMessage);
  } else if (action === "preview" && message.teaching) {
    const note = companion.querySelector("[name='teaching-note']");
    state.teachingNote = note.value;
    state.mode = "preview";
  } else if (action === "keep-discussing" && message.teaching) {
    state.mode = "teach";
  } else if (action === "cancel" || action === "looks-right") {
    state.mode = "current";
  } else if (action === "future-only" && message.teaching) {
    state.receiptAction = "future-only";
    state.mode = "receipt";
  } else if (action === "apply-matches" && message.teaching) {
    message.label = message.teaching.targetLabel;
    message.reason = message.teaching.appliedReason;
    state.corrected = true;
    state.receiptAction = "apply-matches";
    state.mode = "receipt";
  } else if (action === "restart") {
    const message = messages.find((item) => item.id === "rolescout");
    message.label = message.teaching.initialLabel;
    message.reason = message.teaching.initialReason;
    state.selectedId = message.id;
    state.corrected = false;
    state.teachingNote = "";
    state.receiptAction = null;
    state.mode = "current";
  }

  renderMessages();
  renderPanel();
});

renderMessages();
renderPanel();
