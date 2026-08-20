(() => {
  const STALE_AFTER_MS = 15 * 60 * 1000;
  const STATES = Object.freeze([
    "unknown", "checking", "queue-ready", "verified-clear", "partial", "failed", "offline", "stale",
  ]);

  function normalize(value, now = Date.now()) {
    const state = value && typeof value === "object" ? { ...value } : {};
    let status = STATES.includes(state.status) ? state.status : "unknown";
    const checkedAt = Date.parse(state.checked_at || "");
    if (["queue-ready", "verified-clear"].includes(status)
      && Number.isFinite(checkedAt)
      && now - checkedAt > STALE_AFTER_MS) {
      status = "stale";
    }
    return {
      status,
      checked_at: state.checked_at || "",
      checked_count: Math.max(0, Number(state.checked_count || 0)),
      candidate_count: Math.max(0, Number(state.candidate_count || 0)),
      needs_review_count: Math.max(0, Number(state.needs_review_count || 0)),
      read_failure_count: Math.max(0, Number(state.read_failure_count || 0)),
      unchecked_count: Math.max(0, Number(state.unchecked_count || 0)),
      requires_sync_count: Math.max(0, Number(state.requires_sync_count || 0)),
      scope: state.scope || "Inbox coverage not checked",
      review_items: Array.isArray(state.review_items) ? state.review_items : [],
      error: state.error || "",
      previous_status: state.previous_status || "",
    };
  }

  function freshnessLabel(checkedAt, now = Date.now()) {
    const checked = Date.parse(checkedAt || "");
    if (!Number.isFinite(checked)) return "Unknown";
    const ageMs = Math.max(0, now - checked);
    if (ageMs < 60 * 1000) return "Just now";
    if (ageMs < 60 * 60 * 1000) return `${Math.floor(ageMs / (60 * 1000))}m ago`;
    if (ageMs < 24 * 60 * 60 * 1000) return `${Math.floor(ageMs / (60 * 60 * 1000))}h ago`;
    return `${Math.floor(ageMs / (24 * 60 * 60 * 1000))}d ago`;
  }

  function model(value, now = Date.now()) {
    const state = normalize(value, now);
    const hasCompletedCheck = Boolean(state.checked_at);
    const unavailable = ["unknown", "failed", "offline"].includes(state.status) && !hasCompletedCheck;
    const facts = {
      checked: unavailable ? "—" : String(state.checked_count),
      review: unavailable ? "—" : String(state.needs_review_count),
      freshness: state.status === "checking"
        ? "In progress"
        : state.status === "stale"
          ? "Out of date"
          : freshnessLabel(state.checked_at, now),
    };
    const shared = {
      ...state,
      facts,
      truthNote: "Unread mail stays in your inbox. Only checked messages needing your judgment enter this queue.",
      indicator: "none",
      secondary: "",
    };
    if (state.status === "checking") return { ...shared, shell: "Checking inbox…", title: "Checking new and changed mail…", action: "Checking…", disabled: true, indicator: "indeterminate" };
    if (state.status === "queue-ready") {
      const plural = state.needs_review_count !== 1;
      return {
        ...shared,
        shell: `${state.needs_review_count} need review`,
        title: `${state.needs_review_count} email${plural ? "s" : ""} ${plural ? "need" : "needs"} your review`,
        action: "Review first",
        secondary: "Check again",
      };
    }
    if (state.status === "verified-clear") return { ...shared, shell: "Queue clear · just now", title: "Review queue clear", action: "Back to inbox", secondary: "Check again", truthNote: "Your inbox may still contain unread mail. Clear means no checked messages need review." };
    if (state.status === "partial") return { ...shared, shell: "Check incomplete", title: state.requires_sync_count ? `${state.requires_sync_count} message${state.requires_sync_count === 1 ? "" : "s"} need Threadwise` : `${state.unchecked_count || state.read_failure_count || Math.max(1, state.candidate_count - state.checked_count)} messages weren’t checked`, action: state.requires_sync_count ? "Update inbox" : "Finish check", secondary: state.needs_review_count ? `Review ${state.needs_review_count}` : "", indicator: "determinate" };
    if (state.status === "failed") return { ...shared, shell: "Check failed", title: "Inbox check failed", action: "Try again", secondary: state.needs_review_count ? `Review ${state.needs_review_count}` : "" };
    if (state.status === "offline") return { ...shared, shell: "Offline", title: "Can’t check inbox", action: "Try again", secondary: "Details", truthNote: "This email is handled. The wider review queue is unverified while coverage is unavailable." };
    if (state.status === "stale") return { ...shared, shell: "Coverage out of date", title: "Queue status is out of date", action: "Check inbox", truthNote: "Your inbox changed since the last check. Threadwise makes no clear claim until it is checked again." };
    return { ...shared, shell: "Coverage not checked", title: "Inbox not checked", action: "Check inbox" };
  }

  const api = Object.freeze({ STATES, STALE_AFTER_MS, freshnessLabel, normalize, model });
  globalThis.ThreadwiseCoverage = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
