export const roleScoutTeaching = Object.freeze({
  initialLabel: "EA/Promotions",
  initialReason: "A recurring recommendation email with a promotional format. Threadwise kept it visible because the sender also matches your job-search context.",
  targetLabel: "EA/Work",
  defaultNote: "Job recommendations from RoleScout belong in Work, not Promotions.",
  matchKey: "rolescout-jobs",
  appliedReason: "A recurring job recommendation that supports the active search workflow. You confirmed that RoleScout belongs with Work.",
});

const messageDefinitions = Object.freeze([
  {
    id: "rolescout-current",
    sender: "RoleScout Jobs",
    address: "jobs@example.test",
    subject: "Senior AI product roles this week",
    preview: "New recommendations based on your saved search.",
    time: "9:42 AM",
    label: roleScoutTeaching.initialLabel,
    reason: roleScoutTeaching.initialReason,
    matchKey: roleScoutTeaching.matchKey,
    teaching: roleScoutTeaching,
  },
  {
    id: "rolescout-berlin",
    sender: "RoleScout Jobs",
    address: "jobs@example.test",
    subject: "Product engineer openings near Berlin",
    preview: "Six new roles match your saved search.",
    time: "9:18 AM",
    label: roleScoutTeaching.initialLabel,
    reason: roleScoutTeaching.initialReason,
    matchKey: roleScoutTeaching.matchKey,
  },
  {
    id: "rolescout-ai-pm",
    sender: "RoleScout Jobs",
    address: "jobs@example.test",
    subject: "AI product manager roles hiring now",
    preview: "Hiring teams are reviewing candidates this week.",
    time: "8:56 AM",
    label: roleScoutTeaching.initialLabel,
    reason: roleScoutTeaching.initialReason,
    matchKey: roleScoutTeaching.matchKey,
  },
  {
    id: "rolescout-startups",
    sender: "RoleScout Jobs",
    address: "jobs@example.test",
    subject: "Startup product roles you may like",
    preview: "New roles from early-stage teams.",
    time: "8:32 AM",
    label: roleScoutTeaching.initialLabel,
    reason: roleScoutTeaching.initialReason,
    matchKey: roleScoutTeaching.matchKey,
  },
  {
    id: "project-partner",
    sender: "Project Partner",
    address: "partner@example.test",
    subject: "Can you approve the demo copy?",
    preview: "Please confirm the final wording before release.",
    time: "8:14 AM",
    label: "EA/Work",
    reason: "A direct request from a known collaborator with a clear decision needed.",
  },
  {
    id: "repo-security",
    sender: "Repo Security",
    address: "alerts@example.test",
    subject: "Dependency alert resolved",
    preview: "The patched version is now on the default branch.",
    time: "7:51 AM",
    label: "EA/Work",
    reason: "A project notification that confirms a security-sensitive task has been resolved.",
  },
  {
    id: "northstar",
    sender: "Northstar Weekly",
    address: "digest@example.test",
    subject: "Five useful essays worth reading",
    preview: "A concise roundup from a sender you usually keep.",
    time: "7:28 AM",
    label: "Updates",
    reason: "A recurring editorial digest. It is useful, but no immediate action is required.",
  },
  {
    id: "daily-deals",
    sender: "Daily Deals Outlet",
    address: "offers@example.test",
    subject: "Final hours: workspace gear sale",
    preview: "The offer ends tonight.",
    time: "7:05 AM",
    label: "EA/LowValue",
    reason: "A time-limited retail promotion from a high-volume sender with no prior engagement.",
  },
  {
    id: "saas-webinar",
    sender: "SaaS Webinar Club",
    address: "events@example.test",
    subject: "Tomorrow: automate your inbox workshop",
    preview: "Reserve your place for the live session.",
    time: "6:47 AM",
    label: "EA/Promotions",
    reason: "A promotional event invitation that does not need an immediate response.",
  },
  {
    id: "city-rail",
    sender: "City Rail",
    address: "tickets@example.test",
    subject: "Your trip receipt",
    preview: "Booking confirmation and travel details.",
    time: "6:31 AM",
    label: "Receipts",
    reason: "A transactional message containing a purchase receipt and travel record.",
  },
  {
    id: "cloud-billing",
    sender: "Cloud Billing",
    address: "billing@example.test",
    subject: "Monthly invoice available",
    preview: "Your account statement is ready to view.",
    time: "6:16 AM",
    label: "Receipts",
    reason: "A transactional billing message kept for reference.",
  },
  {
    id: "calendar-bot",
    sender: "Calendar Bot",
    address: "calendar@example.test",
    subject: "Coffee chat confirmed for Thursday",
    preview: "Calendar invitation details are attached.",
    time: "5:58 AM",
    label: "Needs attention",
    reason: "A calendar confirmation that may need a quick schedule check.",
  },
]);

function addFutureRule(state, teaching) {
  if (state.futureRules.some((rule) => rule.matchKey === teaching.matchKey)) return false;

  state.futureRules.push({
    matchKey: teaching.matchKey,
    sender: "RoleScout Jobs",
    targetLabel: teaching.targetLabel,
  });
  return true;
}

export function createDemoState() {
  return {
    messages: messageDefinitions.map((message) => ({ ...message, confirmed: false })),
    selectedId: messageDefinitions[0].id,
    mode: "current",
    corrected: false,
    teachingNote: "",
    teachingError: "",
    receiptAction: null,
    futureRules: [],
    lastAffectedIds: [],
    lastRuleAdded: false,
    lastConfirmationAdded: false,
    mailboxStatus: "No demo changes yet",
  };
}

export function matchingMessages(state, messageId) {
  const source = state.messages.find((message) => message.id === messageId);
  if (!source?.teaching) return [];
  return state.messages.filter((message) => message.matchKey === source.teaching.matchKey);
}

export function matchingMessagesNeedingUpdate(state, messageId) {
  const source = state.messages.find((message) => message.id === messageId);
  if (!source?.teaching) return [];
  return matchingMessages(state, messageId).filter((message) => message.label !== source.teaching.targetLabel);
}

export function folderCounts(state) {
  return {
    inbox: state.messages.length,
    "EA/Work": state.messages.filter((message) => message.label === "EA/Work").length,
    "EA/Promotions": state.messages.filter((message) => message.label === "EA/Promotions").length,
    "EA/LowValue": state.messages.filter((message) => message.label === "EA/LowValue").length,
  };
}

export function applyTeachingToMatches(state, messageId) {
  const source = state.messages.find((message) => message.id === messageId);
  if (!source?.teaching) return [];

  const affectedMessages = matchingMessagesNeedingUpdate(state, messageId);
  affectedMessages.forEach((message) => {
    message.label = source.teaching.targetLabel;
    message.reason = source.teaching.appliedReason;
  });
  state.lastRuleAdded = addFutureRule(state, source.teaching);
  state.lastAffectedIds = affectedMessages.map((message) => message.id);
  state.corrected = true;
  const ruleStatus = state.lastRuleAdded ? "future rule saved" : "future rule already saved";
  state.mailboxStatus = `${affectedMessages.length} emails moved to ${source.teaching.targetLabel} · ${ruleStatus}`;
  return [...state.lastAffectedIds];
}

export function saveTeachingForFuture(state, messageId) {
  const source = state.messages.find((message) => message.id === messageId);
  if (!source?.teaching) return false;

  state.lastRuleAdded = addFutureRule(state, source.teaching);
  state.lastAffectedIds = [];
  state.mailboxStatus = state.lastRuleAdded
    ? "Future rule saved · existing inbox unchanged"
    : "Future rule already saved · existing inbox unchanged";
  return state.lastRuleAdded;
}

export function confirmMessage(state, messageId) {
  const message = state.messages.find((item) => item.id === messageId);
  if (!message) return false;

  state.lastConfirmationAdded = !message.confirmed;
  message.confirmed = true;
  state.lastAffectedIds = [];
  state.mailboxStatus = state.lastConfirmationAdded
    ? "Decision confirmed · inbox labels unchanged"
    : "Decision already confirmed · inbox labels unchanged";
  return state.lastConfirmationAdded;
}
