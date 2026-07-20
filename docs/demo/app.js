const messages = [
  {
    id: "rolescout",
    sender: "RoleScout Jobs",
    address: "jobs@example.test",
    subject: "Senior AI product roles this week",
    preview: "New recommendations based on your saved search.",
    time: "9:42 AM",
    label: "Promotions",
    reason: "A recurring recommendation email with a promotional format. Threadwise kept it visible because the sender also matches your job-search context.",
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
};

const messageList = document.querySelector("#message-list");
const companion = document.querySelector("#companion-content");

function selectedMessage() {
  return messages.find((message) => message.id === state.selectedId);
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
    <p class="flow-hint">${message.id === "rolescout" && !state.corrected ? "Try the flow: this job alert belongs with Work, not Promotions." : "Choose another synthetic email, or inspect how this decision was made."}</p>
    <div class="button-row">
      <button class="action primary" type="button" data-action="correct">Correct / teach</button>
      <button class="action quiet" type="button" data-action="looks-right">Looks right</button>
    </div>
  `;
}

function renderTeach(message) {
  companion.innerHTML = `
    ${panelHeading(message)}
    <form class="teach-form" data-form="teach">
      <label for="teaching-note">What should Threadwise understand?</label>
      <textarea id="teaching-note" name="teaching-note">${message.id === "rolescout" ? "Job recommendations from RoleScout belong in Work, not Promotions." : `Messages like this from ${message.sender} should use a different label.`}</textarea>
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
  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill">${message.label}</span>
      <span class="pill success">→ EA/Work</span>
    </div>
    <div class="impact">
      <strong>I found 4 matching emails before changing anything.</strong>
      The current email will move to EA/Work. Three earlier RoleScout recommendations match the same proposed rule.
    </div>
    <p class="flow-hint">Choose the scope explicitly. The hosted demo changes only this synthetic page.</p>
    <div class="button-row">
      <button class="action confirm" type="button" data-action="apply-matches">Apply to 4</button>
      <button class="action" type="button" data-action="future-only">Use for future only</button>
      <button class="action quiet" type="button" data-action="cancel">Keep discussing</button>
    </div>
  `;
}

function renderReceipt(message) {
  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill success">EA/Work</span>
      <span class="pill success">Kept visible</span>
    </div>
    <div class="receipt">
      <strong>Updated in the synthetic inbox.</strong>
      Threadwise changed the four matching demo messages to EA/Work and saved the lesson for future RoleScout recommendations.
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
  if (action === "correct") state.mode = "teach";
  if (action === "preview") state.mode = "preview";
  if (action === "cancel" || action === "looks-right") state.mode = "current";
  if (action === "future-only") state.mode = "receipt";
  if (action === "apply-matches") {
    const message = selectedMessage();
    message.label = "EA/Work";
    message.reason = "A recurring job recommendation that supports the active search workflow. The user confirmed that RoleScout belongs with Work.";
    state.corrected = true;
    state.mode = "receipt";
  }
  if (action === "restart") {
    const message = messages.find((item) => item.id === "rolescout");
    message.label = "Promotions";
    message.reason = "A recurring recommendation email with a promotional format. Threadwise kept it visible because the sender also matches your job-search context.";
    state.selectedId = message.id;
    state.corrected = false;
    state.mode = "current";
  }

  renderMessages();
  renderPanel();
});

renderMessages();
renderPanel();
