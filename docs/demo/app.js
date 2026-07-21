import {
  applyTeachingToMatches,
  confirmMessage,
  createDemoState,
  folderCounts,
  matchingMessages,
  matchingMessagesNeedingUpdate,
  saveTeachingForFuture,
} from "./model.mjs";

let state = createDemoState();

const messageList = document.querySelector("#message-list");
const companion = document.querySelector("#companion-content");
const mailboxStatus = document.querySelector("#mailbox-status");
const mailCount = document.querySelector("#mail-count");

function selectedMessage() {
  return state.messages.find((message) => message.id === state.selectedId);
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

function normalizeTeachingNote(value) {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function beginTeaching(message) {
  if (!message.teaching) return;
  state.teachingNote = message.teaching.defaultNote;
  state.teachingError = "";
  state.receiptAction = null;
  state.mode = "teach";
  state.mailboxStatus = "Drafting a correction · inbox unchanged";
}

function renderMessages() {
  messageList.innerHTML = state.messages
    .map(
      (message) => `
        <button class="message-row" type="button" data-message-id="${message.id}" aria-pressed="${message.id === state.selectedId}">
          <strong>${escapeHtml(message.sender)}</strong>
          <span class="message-content">
            <span class="subject">${escapeHtml(message.subject)} <span aria-hidden="true">-</span> <span class="preview">${escapeHtml(message.preview)}</span></span>
            <span class="row-tags">
              <span class="message-label" data-message-label>${escapeHtml(message.label)}</span>
              <span class="confirmed-badge" data-confirmed hidden>✓ Confirmed</span>
            </span>
          </span>
          <time>${escapeHtml(message.time)}</time>
        </button>
      `,
    )
    .join("");
}

function updateMessageSelection() {
  messageList.querySelectorAll("[data-message-id]").forEach((row) => {
    row.setAttribute("aria-pressed", String(row.dataset.messageId === state.selectedId));
  });
}

function updateInboxVisualState() {
  const counts = folderCounts(state);
  mailCount.textContent = `${counts.inbox} messages`;
  mailboxStatus.textContent = state.mailboxStatus;

  document.querySelectorAll("[data-folder-count]").forEach((count) => {
    count.textContent = counts[count.dataset.folderCount];
  });

  messageList.querySelectorAll("[data-message-id]").forEach((row) => {
    const message = state.messages.find((item) => item.id === row.dataset.messageId);
    row.querySelector("[data-message-label]").textContent = message.label;
    row.querySelector("[data-confirmed]").hidden = !message.confirmed;
    row.classList.toggle("is-updated", state.lastAffectedIds.includes(message.id));
  });
}

function focusCompanion(selector) {
  const target = companion.querySelector(selector);
  if (target) target.focus();
}

function panelHeading(message) {
  return `
    <div>
      <p class="section-label">Selected email</p>
      <h2 class="email-title">${escapeHtml(message.subject)}</h2>
      <p class="sender">${escapeHtml(message.sender)} &lt;${escapeHtml(message.address)}&gt;</p>
    </div>
  `;
}

function renderCurrent(message) {
  const teachingHint = message.teaching
    ? state.corrected
      ? "The four matching messages now show their new labels in the inbox. You can restart or inspect another email."
      : "Try the flow: this job alert belongs with Work, not Promotions."
    : "This message is available for inspection. The guided teaching scenario uses the first RoleScout job alert.";
  const teachingAction = message.teaching
    ? '<button class="action primary" type="button" data-action="correct">Correct / teach</button>'
    : '<button class="action primary" type="button" data-action="open-guided-teaching">Try RoleScout correction</button>';
  const looksRightAction = !message.teaching || state.corrected
    ? '<button class="action quiet" type="button" data-action="looks-right">Looks right</button>'
    : "";
  const notice = state.mailboxStatus !== "No demo changes yet"
    ? `<div class="inline-status" role="status">${escapeHtml(state.mailboxStatus)}</div>`
    : "";

  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill ${state.lastAffectedIds.includes(message.id) ? "success" : ""}">${escapeHtml(message.label)}</span>
      <span class="pill success">Kept visible</span>
      ${message.confirmed ? '<span class="pill confirmed">✓ Confirmed</span>' : ""}
    </div>
    <div class="reason">
      <p class="section-label">Why</p>
      ${escapeHtml(message.reason)}
    </div>
    ${notice}
    <p class="flow-hint">${teachingHint}</p>
    <div class="button-row">
      ${teachingAction}
      ${looksRightAction}
    </div>
  `;
}

function renderTeach(message) {
  if (!message.teaching) {
    renderCurrent(message);
    return;
  }

  const error = state.teachingError
    ? `<p id="teaching-error" class="form-error" role="alert">${escapeHtml(state.teachingError)}</p>`
    : "";
  const restoreAction = state.teachingError
    ? '<button class="action" type="button" data-action="restore-note">Restore example</button>'
    : "";

  companion.innerHTML = `
    ${panelHeading(message)}
    <form class="teach-form" data-form="teach">
      <label for="teaching-note">What should Threadwise understand?</label>
      <textarea id="teaching-note" name="teaching-note" aria-invalid="${Boolean(state.teachingError)}" aria-describedby="teaching-guidance${state.teachingError ? " teaching-error" : ""}">${escapeHtml(state.teachingNote)}</textarea>
    </form>
    <div class="reason">
      <p class="section-label">Nothing has changed yet</p>
      <span id="teaching-guidance">This deterministic demo recognizes the example RoleScout lesson, then shows its fixed impact preview. Other wording is not interpreted.</span>
    </div>
    ${error}
    <div class="button-row">
      <button class="action primary" type="button" data-action="preview">Preview change</button>
      ${restoreAction}
      <button class="action quiet" type="button" data-action="cancel">Cancel</button>
    </div>
  `;
}

function renderPreview(message) {
  if (!message.teaching) {
    renderCurrent(message);
    return;
  }

  const matchCount = matchingMessages(state, message.id).length;
  const affectedCount = matchingMessagesNeedingUpdate(state, message.id).length;
  const impactCopy = affectedCount > 0
    ? `${affectedCount} of them will move to ${escapeHtml(message.teaching.targetLabel)}. The future lesson will also be ${state.futureRules.some((rule) => rule.matchKey === message.teaching.matchKey) ? "kept" : "saved"}.`
    : `All ${matchCount} already show ${escapeHtml(message.teaching.targetLabel)}. Applying again will leave the inbox labels and folder counts unchanged.`;
  const applyLabel = affectedCount > 0 ? `Apply to ${affectedCount}` : "Confirm no inbox changes";
  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill">${escapeHtml(message.label)}</span>
      <span class="pill success">→ ${escapeHtml(message.teaching.targetLabel)}</span>
    </div>
    <div class="impact">
      <strong>I found ${matchCount} matching emails before changing anything.</strong>
      ${impactCopy}
    </div>
    <p class="flow-hint">Choose the scope explicitly. The hosted demo changes only this synthetic page.</p>
    <div class="button-row">
      <button class="action confirm" type="button" data-action="apply-matches">${applyLabel}</button>
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
  const affectedCount = state.lastAffectedIds.length;
  let receiptHeading;
  let receiptBody;
  if (futureOnly) {
    receiptHeading = state.lastRuleAdded ? "Future lesson saved." : "Future lesson already saved.";
    receiptBody = state.lastRuleAdded
      ? `Future ${escapeHtml(message.sender)} recommendations will go to ${escapeHtml(message.teaching.targetLabel)}. Existing demo messages remain unchanged, as shown by the inbox labels and folder counts.`
      : `The existing future lesson remains active for ${escapeHtml(message.sender)} recommendations. Existing demo messages and folder counts stayed unchanged.`;
  } else if (affectedCount > 0) {
    receiptHeading = "Updated in the synthetic inbox.";
    receiptBody = `${affectedCount} matching demo messages now show ${escapeHtml(message.teaching.targetLabel)} in the inbox. The folder count increased by ${affectedCount}, and the future lesson was ${state.lastRuleAdded ? "saved" : "already saved"}.`;
  } else {
    receiptHeading = state.lastRuleAdded ? "Future lesson saved." : "No additional changes needed.";
    receiptBody = `All ${matchingMessages(state, message.id).length} matching demo messages already show ${escapeHtml(message.teaching.targetLabel)}. Folder counts stayed unchanged, and the future lesson was ${state.lastRuleAdded ? "saved" : "already saved"}.`;
  }

  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill ${futureOnly ? "" : "success"}">${escapeHtml(message.label)}</span>
      <span class="pill success">Kept visible</span>
    </div>
    <div class="receipt" role="status">
      <strong>${receiptHeading}</strong>
      ${receiptBody}
    </div>
    <p class="flow-hint">In the real product this receipt appears only after provider-side verification. No provider exists on this page.</p>
    <div class="button-row">
      <button class="action primary" type="button" data-action="restart">Run the demo again</button>
    </div>
  `;
}

function renderAcknowledged(message) {
  const receiptHeading = state.lastConfirmationAdded ? "Decision confirmed." : "Decision already confirmed.";
  const receiptBody = state.lastConfirmationAdded
    ? `Threadwise kept the existing ${escapeHtml(message.label)} decision. The inbox row now shows Confirmed; no label or provider data changed.`
    : `The inbox row already showed Confirmed for this ${escapeHtml(message.label)} decision, so no inbox or provider data changed.`;
  companion.innerHTML = `
    ${panelHeading(message)}
    <div class="pill-row">
      <span class="pill">${escapeHtml(message.label)}</span>
      <span class="pill success">Kept visible</span>
      <span class="pill confirmed">✓ Confirmed</span>
    </div>
    <div class="receipt" role="status">
      <strong>${receiptHeading}</strong>
      ${receiptBody}
    </div>
    <p class="flow-hint">Continue inspecting this message or choose another synthetic email.</p>
    <div class="button-row">
      <button class="action primary" type="button" data-action="continue-inspecting">Continue inspecting</button>
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
  } else if (state.mode === "acknowledged") {
    renderAcknowledged(message);
  } else {
    renderCurrent(message);
  }
}

messageList.addEventListener("click", (event) => {
  const row = event.target.closest("[data-message-id]");
  if (!row) return;
  state.selectedId = row.dataset.messageId;
  state.mode = "current";
  state.teachingError = "";
  updateMessageSelection();
  renderPanel();
});

companion.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;

  const action = button.dataset.action;
  const message = selectedMessage();
  let focusSelector = null;
  let selectionChanged = false;

  if (action === "correct" && message.teaching) {
    beginTeaching(message);
    focusSelector = "#teaching-note";
  } else if (action === "open-guided-teaching") {
    const guidedMessage = state.messages.find((item) => item.teaching);
    state.selectedId = guidedMessage.id;
    beginTeaching(guidedMessage);
    selectionChanged = true;
    focusSelector = "#teaching-note";
  } else if (action === "preview" && message.teaching) {
    const note = companion.querySelector("[name='teaching-note']");
    state.teachingNote = note.value;
    if (normalizeTeachingNote(state.teachingNote) === normalizeTeachingNote(message.teaching.defaultNote)) {
      state.teachingError = "";
      state.mode = "preview";
      state.mailboxStatus = `Previewing ${matchingMessagesNeedingUpdate(state, message.id).length} inbox changes · inbox unchanged`;
      focusSelector = "[data-action='apply-matches']";
    } else {
      state.teachingError = state.teachingNote.trim()
        ? "This deterministic demo can preview only the example RoleScout lesson. Restore the example wording to continue."
        : "Enter the example RoleScout lesson to preview the change.";
      state.mode = "teach";
      state.mailboxStatus = "Lesson needs the example wording · inbox unchanged";
      focusSelector = "#teaching-note";
    }
  } else if (action === "restore-note" && message.teaching) {
    state.teachingNote = message.teaching.defaultNote;
    state.teachingError = "";
    state.mode = "teach";
    state.mailboxStatus = "Drafting a correction · inbox unchanged";
    focusSelector = "#teaching-note";
  } else if (action === "keep-discussing" && message.teaching) {
    state.mode = "teach";
    state.mailboxStatus = "Refining the lesson · inbox unchanged";
    focusSelector = "#teaching-note";
  } else if (action === "cancel") {
    state.teachingError = "";
    state.mode = "current";
    state.mailboxStatus = "Correction canceled · inbox unchanged";
    focusSelector = "[data-action='correct'], [data-action='open-guided-teaching']";
  } else if (action === "looks-right") {
    confirmMessage(state, message.id);
    state.mode = "acknowledged";
    focusSelector = "[data-action='continue-inspecting']";
  } else if (action === "continue-inspecting") {
    state.mode = "current";
    focusSelector = "[data-action='correct'], [data-action='open-guided-teaching']";
  } else if (action === "future-only" && message.teaching) {
    saveTeachingForFuture(state, message.id);
    state.receiptAction = "future-only";
    state.mode = "receipt";
    focusSelector = "[data-action='restart']";
  } else if (action === "apply-matches" && message.teaching) {
    applyTeachingToMatches(state, message.id);
    state.receiptAction = "apply-matches";
    state.mode = "receipt";
    focusSelector = "[data-action='restart']";
  } else if (action === "restart") {
    state = createDemoState();
    selectionChanged = true;
    focusSelector = "[data-action='correct']";
  } else {
    return;
  }

  if (selectionChanged) updateMessageSelection();
  updateInboxVisualState();
  renderPanel();
  if (focusSelector) focusCompanion(focusSelector);
});

renderMessages();
updateInboxVisualState();
renderPanel();
