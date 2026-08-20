(() => {
  const SINGLETON_KEY = "__eaCompanionSingleton";
  if (globalThis[SINGLETON_KEY] && typeof globalThis[SINGLETON_KEY].teardown === "function") {
    globalThis[SINGLETON_KEY].teardown();
  }
  const ROOT_ID = "email-agent-companion-root";
  const LOCAL_ORIGIN = "http://127.0.0.1:8021";
  const HEALTH_PATH = "/api/health";
  const HEALTH_SERVICE_ID = "threadwise-gmail-companion";
  const TEACHING_RECOVERY = globalThis.ThreadwiseTeachingRecovery;
  const ANALYTICS = globalThis.ThreadwiseAnalytics;
  const PROVIDER = globalThis.ThreadwiseProvider;
  const ONBOARDING = globalThis.ThreadwiseOnboarding;
  const QUEUE_NAVIGATION = globalThis.ThreadwiseQueueNavigation;
  const CONTEXT_ACTIONS = globalThis.ThreadwiseContextActions;
  const SELECTED_EXPLANATION = globalThis.ThreadwiseSelectedExplanation;
  const REVIEW_PROGRESSION = globalThis.ThreadwiseReviewProgression;
  const COVERAGE = globalThis.ThreadwiseCoverage;
  if (!PROVIDER) {
    throw new Error("Threadwise provider adapter did not load.");
  }
  if (!TEACHING_RECOVERY) {
    throw new Error("Threadwise teaching recovery module did not load.");
  }
  if (!ONBOARDING) {
    throw new Error("Threadwise onboarding module did not load.");
  }
  if (!QUEUE_NAVIGATION) {
    throw new Error("Threadwise queue navigation module did not load.");
  }
  if (!CONTEXT_ACTIONS) {
    throw new Error("Threadwise contextual actions module did not load.");
  }
  if (!SELECTED_EXPLANATION) {
    throw new Error("Threadwise selected explanation module did not load.");
  }
  if (!REVIEW_PROGRESSION) {
    throw new Error("Threadwise review progression module did not load.");
  }
  if (!COVERAGE) {
    throw new Error("Threadwise coverage module did not load.");
  }
  const BRAND_ICON_URL = chrome.runtime.getURL("assets/brand/threadwise-app-mark.png");
  const ACTIVE_PROVIDER = PROVIDER.id;
  const PANEL_WIDTH = "408px";
  const PANEL_WIDTH_EXPANDED = "min(920px, calc(100vw - 84px))";
  const PANEL_WIDTH_MINIMIZED = "40px";
  const REFRESH_INTERVAL_MS = 5000;
  const PROGRESSION_REFRESH_INTERVAL_MS = 1000;
  const UNDERSTANDING_REFRESH_INTERVAL_MS = 400;
  const QUEUE_RENDER_CAP = 6;
  let minimized = true;
  let previousPayload = "";
  let lastHarnessState = null;
  let lastSidebarState = null;
  let lastConnectionState = {
    kind: "connecting",
    label: "Connecting",
    details: "Checking the local companion.",
  };
  let teachPreview = null;
  let teachPreviewRequestId = 0;
  let forceLlmReviewRequested = false;
  let previousTeachPreview = null;
  let teachResult = null;
  let teachFlowState = "teaching";
  let inboxApplyConfirmOpen = false;
  let teachOutcome = null;
  let teachWriteThrough = null;
  let feedbackOpen = false;
  let founderFeedbackVisible = false;
  let feedbackDraft = "";
  let feedbackResult = "";
  let activeSummaryFilter = "recent_items";
  let detailsExpanded = false;
  let autoHandledChangeOpen = false;
  let selectedDecisionMode = "review";
  let selectedDecisionConflict = "";
  let futureLearningError = "";
  let currentApplyError = "";
  let handledAdvanceError = "";
  let applyInFlight = false;
  let activeTeachApplyMode = "";
  let recordedSuggestionDecisions = { approve: false, edit: false };
  let lastSelectedMessageId = "";
  let affectedReviewOpen = false;
  let selectedTeachScope = "current-only";
  let gmailCheckPending = false;
  let gmailCheckResult = null;
  let forcedHome = false;
  let forcedHomeLiveContext = null;
  let teachDraft = {
    targetLabel: "",
    targetLabelExplicit: false,
    note: "",
  };
  let manualPreviewContext = null;
  let manualPreviewOriginContext = null;
  let lastLiveContext = null;
  let trustedHtmlPolicy = null;
  let refreshIntervalId = null;
  let understandingRefreshTimeoutId = null;
  let refreshInFlight = false;
  let connectionPollInFlight = false;
  let pendingRefreshAfterConnectionPoll = null;
  let connectionRetryInFlight = false;
  let connectionRetryFeedback = "";
  let lastRecoveryMessage = "";
  let hashChangeListener = null;
  let popStateListener = null;
  let documentClickListener = null;
  let hostContextMutationObserver = null;
  let hostContextInvalidationMicrotaskPending = false;
  let companionLifecycleActive = false;
  let runtimeMessageListener = null;
  let onboardingState = { version: ONBOARDING.VERSION, status: "loading" };
  let onboardingReady = Promise.resolve(onboardingState);
  let onboardingVisible = false;
  let onboardingActionInFlight = false;
  let onboardingMessage = "";
  let queueQuery = "";
  let queueFinderOpen = false;
  let queueHelpOpen = false;
  let queuePreviewActive = false;
  let queueProvider = ACTIVE_PROVIDER;
  let pendingQueueNavigationFocus = null;
  let keyboardListener = null;
  let documentKeydownListener = null;
  let contextMenuResizeListener = null;
  let contextMenuResizeObserver = null;
  let contextActionFocusPending = false;
  let contextActionFocusTimer = null;
  let contextActionsOpen = false;
  let contextActionsActiveIndex = 0;
  let contextActionsGeneration = 0;
  let contextEscapeRetreatArmed = false;
  let contextEscapeRetreatTimer = null;
  let explanationFocusPending = false;
  let reviewProgressionGeneration = 0;
  let stateReadGeneration = 0;
  let latestStateReadGeneration = 0;
  let optimisticDecision = null;
  let committedReviewIdentities = [];
  let progressionCheck = null;
  let progressionRefreshTimeoutId = null;
  let handledProgressionFlight = null;
  let coverageState = COVERAGE.normalize({ status: "unknown" });
  let coverageCheckInFlight = false;
  let coverageDetailsOpen = false;
  let coverageSyntheticNavigation = false;

  function boot() {
    companionLifecycleActive = true;
    ensureRoot();
    installHostContextMutationObserver();
    installTestHooks();
    onboardingReady = ONBOARDING.load()
      .then((state) => {
        onboardingState = state;
        return state;
      })
      .catch((error) => {
        onboardingState = { version: ONBOARDING.VERSION, status: "unseen" };
        onboardingMessage = `Threadwise could not save onboarding state: ${error.message || error}`;
        return onboardingState;
      });
    refreshSelection();
    refreshIntervalId = window.setInterval(pollConnectionHealth, REFRESH_INTERVAL_MS);
    hashChangeListener = () => {
      if (!invalidateProgressionForHostNavigation()) {
        refreshSelection();
      }
    };
    window.addEventListener("hashchange", hashChangeListener);
    popStateListener = () => {
      if (!invalidateProgressionForHostNavigation()) {
        refreshSelection();
      }
    };
    window.addEventListener("popstate", popStateListener);
    contextMenuResizeListener = () => {
      positionContextMenu();
      window.requestAnimationFrame?.(() => positionContextMenu());
      window.setTimeout(() => positionContextMenu(), 0);
    };
    window.addEventListener("resize", contextMenuResizeListener);
    documentClickListener = (event) => {
      disarmContextEscapeRetreat();
      if (pendingQueueNavigationFocus && !isQueueFocusHandoffTrigger(event)) {
        clearPendingQueueNavigationFocus();
      }
      releaseCompletedQueuePreviewOnGmailClick(event);
      scheduleProgressionHostResample();
      window.setTimeout(refreshSelection, 150);
    };
    document.addEventListener("click", documentClickListener, true);
    documentKeydownListener = handleDocumentKeydown;
    document.addEventListener("keydown", documentKeydownListener, true);
    runtimeMessageListener = (message) => {
      if (!message || message.type !== "email-agent:toggle") {
        return;
      }
      minimized = !minimized;
      renderMinimized();
    };
    chrome.runtime.onMessage.addListener(runtimeMessageListener);
    globalThis[SINGLETON_KEY] = {
      teardown,
    };
  }

  function ensureRoot() {
    if (document.getElementById(ROOT_ID)) {
      return;
    }

    const root = document.createElement("div");
    root.id = ROOT_ID;
    root.tabIndex = 0;
    root.setAttribute("aria-label", "Threadwise Companion");
    Object.assign(root.style, {
      position: "fixed",
      top: "14px",
      right: "14px",
      width: PANEL_WIDTH,
      maxWidth: "calc(100vw - 28px)",
      maxHeight: "calc(100vh - 28px)",
      boxSizing: "border-box",
      minWidth: "0",
      overflowX: "hidden",
      zIndex: "2147483647",
      pointerEvents: "auto",
    });
    setHtml(root, `
      <style id="ea-editorial-utility-styles">
        #${ROOT_ID} {
          --tw-ink: #1f2328;
          --tw-muted: #60666f;
          --tw-faint: #8a9099;
          --tw-surface: #fff;
          --tw-subtle: #f6f7f9;
          --tw-hover: #f0f2f5;
          --tw-line: #e2e5e9;
          --tw-line-strong: #cdd2d8;
          --tw-accent: #635bff;
          --tw-accent-hover: #554df0;
          --tw-success: #16815d;
          --tw-warning: #946200;
          --tw-danger: #b42318;
          --tw-focus: #1a73e8;
          color: var(--tw-ink);
          font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          box-sizing: border-box;
          min-width: 0;
          overflow-x: hidden;
        }
        #${ROOT_ID} #ea-panel {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          max-width: 100%;
          overflow-x: hidden;
          border: 1px solid var(--tw-line-strong) !important;
          border-radius: 12px !important;
          background: var(--tw-surface) !important;
          color: var(--tw-ink) !important;
          box-shadow: 0 4px 8px rgba(31, 35, 40, .12) !important;
        }
        #${ROOT_ID} #ea-panel * {
          box-sizing: border-box;
          box-shadow: none !important;
        }
        #${ROOT_ID} #ea-header {
          box-sizing: border-box;
          height: 52px !important;
          flex: 0 0 52px;
          grid-template-columns: 28px minmax(0, 1fr) 30px !important;
          gap: 10px !important;
          padding: 0 14px !important;
          border-bottom: 1px solid var(--tw-line) !important;
          background: rgba(255,255,255,.98) !important;
        }
        #${ROOT_ID} #ea-brand-toggle {
          width: 28px !important;
          height: 28px !important;
          border: 0 !important;
          border-radius: 7px !important;
          background: transparent !important;
        }
        #${ROOT_ID} #ea-header > div:first-child {
          width: 28px;
        }
        #${ROOT_ID} #ea-header > div:nth-child(2) > div {
          display: flex !important;
          align-items: center;
          gap: 9px !important;
        }
        #${ROOT_ID} #ea-title {
          color: var(--tw-ink) !important;
          font-size: 14px !important;
          font-weight: 720 !important;
          letter-spacing: -.02em !important;
          line-height: 1.2 !important;
        }
        #${ROOT_ID} #ea-header-tagline {
          display: none !important;
        }
        #${ROOT_ID} #ea-status {
          min-width: 0;
          max-width: 100%;
          padding: 0 !important;
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          color: var(--tw-muted) !important;
          font-size: 12px !important;
          font-weight: 500 !important;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        #${ROOT_ID} #ea-minimize {
          width: 30px;
          height: 30px;
          display: grid !important;
          place-items: center;
          padding: 0 !important;
          border: 0 !important;
          border-radius: 7px !important;
          background: transparent !important;
          color: var(--tw-muted) !important;
          font-size: 18px !important;
          font-weight: 500 !important;
          line-height: 1 !important;
        }
        #${ROOT_ID} #ea-minimize:hover,
        #${ROOT_ID} #ea-brand-toggle:hover {
          background: var(--tw-hover) !important;
        }
        #${ROOT_ID} #ea-content {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          max-width: 100%;
          overflow-x: hidden;
          padding: 12px !important;
          gap: 0 !important;
          background: var(--tw-surface) !important;
        }
        #${ROOT_ID} #ea-content[data-ea-workspace-mode="review"] {
          padding: 0 !important;
        }
        #${ROOT_ID} #ea-workspace,
        #${ROOT_ID} #ea-workspace > [data-ea-workspace-body],
        #${ROOT_ID} [data-ea-current-message-context],
        #${ROOT_ID} [data-ea-selected-state] {
          box-sizing: border-box;
          width: 100%;
          min-width: 0;
          max-width: 100%;
        }
        #${ROOT_ID} #ea-workspace,
        #${ROOT_ID} #ea-workspace > [data-ea-workspace-body] {
          overflow-x: hidden;
        }
        #${ROOT_ID} #ea-workspace > [data-ea-workspace-body] > *,
        #${ROOT_ID} [data-ea-current-message-context] > * {
          min-width: 0;
          max-width: 100%;
        }
        #${ROOT_ID} #ea-workspace > [data-ea-workspace-body] {
          border: 0 !important;
          border-radius: 0 !important;
          background: var(--tw-surface) !important;
          color: var(--tw-ink) !important;
          box-shadow: none !important;
        }
        #${ROOT_ID} #ea-workspace > [data-ea-workspace-body="review"] {
          padding: 0 !important;
          overflow: hidden;
          background: var(--tw-surface) !important;
        }
        #${ROOT_ID} [data-ea-current-message-context] {
          padding: 15px 16px 13px;
          border-bottom: 1px solid var(--tw-line);
        }
        #${ROOT_ID} [data-ea-current-message-context] > div:first-child > div:first-child > div:first-child {
          color: var(--tw-ink) !important;
          font-size: 14px !important;
          font-weight: 650 !important;
        }
        #${ROOT_ID} [data-ea-current-message-context] [style*="color:#6b6255"],
        #${ROOT_ID} [data-ea-review-progress] {
          color: var(--tw-muted) !important;
        }
        #${ROOT_ID} [data-ea-review-progress-track] {
          height: 3px;
          margin-top: 12px;
          overflow: hidden;
          border-radius: 2px;
          background: var(--tw-line);
        }
        #${ROOT_ID} [data-ea-review-progress-fill] {
          height: 100%;
          border-radius: inherit;
          background: var(--tw-accent);
        }
        #${ROOT_ID} [data-ea-review-judgment] {
          padding: 18px 16px 0;
          color: var(--tw-ink) !important;
        }
        #${ROOT_ID} [data-ea-explanation-suggestion] {
          color: var(--tw-ink) !important;
          font-size: 19px !important;
          font-weight: 700 !important;
          letter-spacing: -.025em !important;
          line-height: 1.2 !important;
        }
        #${ROOT_ID} [data-ea-explanation-confidence] {
          color: var(--tw-success) !important;
          padding: 2px 0 !important;
          font-size: 11px !important;
          font-weight: 650 !important;
        }
        #${ROOT_ID} [data-ea-explanation-rationale] {
          max-width: 38ch;
          margin-top: 8px !important;
          color: var(--tw-muted) !important;
          font-size: 13px;
          line-height: 1.5;
        }
        #${ROOT_ID} [data-ea-explanation-queue-reason] {
          display: flex;
          align-items: center;
          gap: 7px;
          margin-top: 16px !important;
          color: var(--tw-muted) !important;
          font-size: 12px !important;
          font-weight: 500 !important;
        }
        #${ROOT_ID} [data-ea-explanation-queue-reason]::before {
          width: 7px;
          height: 7px;
          flex: 0 0 auto;
          border-radius: 50%;
          background: var(--tw-success);
          content: "";
        }
        #${ROOT_ID} [data-ea-review-facts] {
          margin: 18px 16px 0;
          border-top: 1px solid var(--tw-line);
        }
        #${ROOT_ID} [data-ea-review-fact] {
          display:flex;
          justify-content:space-between;
          gap:18px;
          padding:10px 0;
          border-bottom:1px solid var(--tw-line);
          color:var(--tw-ink);
          font-size:12px;
        }
        #${ROOT_ID} [data-ea-review-fact] > span {
          color: var(--tw-muted) !important;
        }
        #${ROOT_ID} [data-ea-review-fact] > strong {
          font-weight: 620 !important;
        }
        #${ROOT_ID} [data-ea-review-dock] {
          display:grid;
          grid-template-columns:minmax(0,1fr) 38px;
          gap:8px;
          padding:12px 14px;
          margin-top: 18px;
          border-top: 1px solid var(--tw-line);
          background: var(--tw-surface);
        }
        #${ROOT_ID} [data-ea-review-dock] #ea-context-actions {
          min-width:0;
        }
        #${ROOT_ID} [data-ea-review-dock] [data-ea-context-actions-surface] {
          margin-top:0 !important;
          height:100%;
        }
        #${ROOT_ID} [data-ea-review-dock] [data-ea-context-trigger] {
          width:38px !important;
          min-height:40px !important;
          height:40px !important;
          padding:0 !important;
          border: 1px solid var(--tw-line-strong) !important;
          border-radius: 8px !important;
          background: var(--tw-surface) !important;
          color: var(--tw-ink) !important;
          font-size:18px !important;
        }
        #${ROOT_ID} #ea-workspace [data-ea-selected-state],
        #${ROOT_ID} #ea-workspace [data-ea-selected-state] * {
          box-shadow: none !important;
        }
        #${ROOT_ID} #ea-panel button:not([data-tw-primary-action]),
        #${ROOT_ID} #ea-panel a:not([data-tw-primary-action]) {
          box-shadow: none !important;
        }
        #${ROOT_ID} #ea-panel button:not([data-tw-primary-action])[style*="background:#2eb67d"],
        #${ROOT_ID} #ea-panel button:not([data-tw-primary-action])[style*="background:#3d6df2"],
        #${ROOT_ID} #ea-panel button:not([data-tw-primary-action])[style*="background:#ffc64a"] {
          background: var(--tw-surface) !important;
          color: var(--tw-ink) !important;
        }
        #${ROOT_ID} #ea-panel [data-tw-primary-action] {
          border: 0 !important;
          border-radius: 8px !important;
          background:var(--tw-accent) !important;
          color:#fff !important;
          box-shadow: none !important;
        }
        #${ROOT_ID} #ea-panel [data-tw-primary-action]:hover {
          background: var(--tw-accent-hover) !important;
        }
        #${ROOT_ID} [data-ea-review-dock] [data-tw-primary-action] {
          min-height: 40px !important;
          height: 40px;
          padding: 0 12px !important;
          font-size: 14px !important;
          font-weight: 680 !important;
        }
        #${ROOT_ID} :where(button, a, input, select, textarea, summary, [tabindex]):focus-visible {
          outline: 2px solid var(--tw-focus) !important;
          outline-offset: 2px !important;
        }
        #${ROOT_ID} #ea-panel [data-tw-primary-action]:focus-visible {
          box-shadow: none !important;
        }
        #${ROOT_ID} [data-ea-recovery-surface] {
          display: grid;
          gap: 0;
          padding: 18px 16px 16px;
          color: var(--tw-ink);
        }
        #${ROOT_ID} [data-ea-recovery-eyebrow] {
          display: flex;
          align-items: center;
          gap: 7px;
          color: var(--tw-muted);
          font-size: 12px;
          font-weight: 600;
          line-height: 1.3;
        }
        #${ROOT_ID} [data-ea-recovery-eyebrow]::before {
          width: 7px;
          height: 7px;
          flex: 0 0 auto;
          border-radius: 50%;
          background: var(--tw-danger);
          content: "";
        }
        #${ROOT_ID} [data-ea-recovery-surface][data-ea-retry-state="checking"] [data-ea-recovery-eyebrow]::before,
        #${ROOT_ID} [data-ea-recovery-surface][data-ea-recovery-kind="connecting"] [data-ea-recovery-eyebrow]::before,
        #${ROOT_ID} [data-ea-recovery-surface][data-ea-recovery-kind="loading"] [data-ea-recovery-eyebrow]::before {
          background: var(--tw-accent);
        }
        #${ROOT_ID} [data-ea-recovery-title] {
          margin: 10px 0 0;
          color: var(--tw-ink);
          font-size: 19px;
          font-weight: 700;
          letter-spacing: -.025em;
          line-height: 1.25;
        }
        #${ROOT_ID} [data-ea-recovery-copy] {
          max-width: 38ch;
          margin: 8px 0 0;
          color: var(--tw-muted);
          font-size: 13px;
          line-height: 1.5;
        }
        #${ROOT_ID} [data-ea-recovery-action] {
          width: 100%;
          min-height: 40px !important;
          margin-top: 18px;
          padding: 0 12px !important;
          font-size: 14px;
          font-weight: 680 !important;
        }
        #${ROOT_ID} [data-ea-recovery-action][disabled] {
          background: #ebeafd !important;
          color: #7771c8 !important;
          cursor: wait !important;
        }
        #${ROOT_ID} [data-ea-recovery-status] {
          min-height: 18px;
          margin-top: 8px;
          color: var(--tw-muted);
          font-size: 12px;
          line-height: 1.45;
        }
        #${ROOT_ID} [data-ea-recovery-details] {
          margin-top: 15px;
          padding-top: 11px;
          border-top: 1px solid var(--tw-line);
          color: var(--tw-muted);
          font-size: 12px;
          line-height: 1.45;
        }
        #${ROOT_ID} [data-ea-recovery-details] summary {
          width: max-content;
          cursor: pointer;
          color: var(--tw-muted) !important;
          font-weight: 600 !important;
        }
        #${ROOT_ID} [data-ea-recovery-diagnostic] {
          display: grid;
          gap: 8px;
          margin-top: 10px;
          padding: 10px;
          border: 1px solid var(--tw-line);
          border-radius: 8px;
          background: var(--tw-subtle);
          overflow-wrap: anywhere;
        }
        #${ROOT_ID} [data-ea-recovery-diagnostic] strong {
          color: var(--tw-ink);
          font-weight: 620;
        }
        #${ROOT_ID} [data-ea-recovery-progress] {
          height: 3px;
          margin-top: 18px;
          overflow: hidden;
          border-radius: 2px;
          background: var(--tw-line);
        }
        #${ROOT_ID} [data-ea-recovery-progress] > span {
          display: block;
          width: 42%;
          height: 100%;
          border-radius: inherit;
          background: var(--tw-accent);
          animation: ea-recovery-progress 1.2s ease-in-out infinite alternate;
        }
        @keyframes ea-recovery-progress {
          from { transform: translateX(-15%); }
          to { transform: translateX(150%); }
        }
        @media (prefers-reduced-motion: reduce) {
          #${ROOT_ID} [data-ea-recovery-progress] > span {
            animation: none;
            transform: none;
          }
        }
        #${ROOT_ID} #ea-workspace [data-ea-selected-state] [style*="background:#fff4dd"],
        #${ROOT_ID} #ea-workspace [data-ea-selected-state] [style*="background:#fff8eb"],
        #${ROOT_ID} #ea-workspace [data-ea-selected-state] [style*="background:#f5efe2"] {
          background: var(--tw-subtle) !important;
          color: var(--tw-ink) !important;
        }
        #${ROOT_ID}[data-ea-minimized="true"] #ea-panel {
          width: 40px !important;
          min-width: 40px !important;
          max-width: 40px !important;
          height: 40px !important;
          flex: 0 0 40px !important;
          overflow: visible !important;
          border-color: transparent !important;
          background: transparent !important;
          box-shadow: none !important;
        }
        #${ROOT_ID}[data-ea-minimized="true"] {
          min-width: 40px !important;
          max-width: 40px !important;
          overflow: visible !important;
        }
        #${ROOT_ID}[data-ea-minimized="true"] #ea-header {
          width: 40px !important;
          height: 40px !important;
          min-height: 40px !important;
          flex: 0 0 40px !important;
          grid-template-columns: 40px !important;
          justify-content: center;
          padding: 0 !important;
          border: 0 !important;
          border-radius: 10px !important;
          background: transparent !important;
          box-shadow: none !important;
        }
        #${ROOT_ID}[data-ea-minimized="true"] #ea-header > div:first-child,
        #${ROOT_ID}[data-ea-minimized="true"] #ea-brand-toggle {
          width: 40px !important;
          height: 40px !important;
        }
        #${ROOT_ID}[data-ea-minimized="true"] #ea-brand-toggle {
          border-radius: 10px !important;
        }
        #${ROOT_ID}[data-ea-minimized="true"] #ea-brand-toggle:hover {
          background: transparent !important;
        }
        @media (min-width: 481px) and (max-height: 520px) {
          #${ROOT_ID}:not([data-ea-minimized="true"]) {
            max-height: calc(100vh - 14px) !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) #ea-panel {
            max-height: calc(100vh - 14px) !important;
          }
          #${ROOT_ID} [data-ea-review-facts] {
            margin-top: 14px;
          }
          #${ROOT_ID} [data-ea-review-fact] {
            padding: 9px 0;
          }
          #${ROOT_ID} [data-ea-review-dock] {
            padding: 10px 14px;
          }
          #${ROOT_ID} [data-ea-recovery-surface] {
            padding: 14px;
          }
          #${ROOT_ID} [data-ea-recovery-action] {
            margin-top: 14px;
          }
          #${ROOT_ID} [data-ea-recovery-details] {
            margin-top: 11px;
            padding-top: 9px;
          }
          #${ROOT_ID} #ea-workspace:has([data-ea-explanation-disclosure]) [data-ea-review-judgment] {
            padding-top: 14px;
          }
          #${ROOT_ID} #ea-workspace:has([data-ea-explanation-disclosure]) [data-ea-explanation-queue-reason] {
            margin-top: 10px !important;
          }
          #${ROOT_ID} #ea-workspace:has([data-ea-explanation-disclosure]) [data-ea-explanation-disclosure] {
            margin-top: 6px !important;
            padding: 3px 2px !important;
          }
        }
        @media (max-width: 480px) {
          #${ROOT_ID}:not([data-ea-minimized="true"]) {
            top: 8px !important;
            left: 8px !important;
            right: 8px !important;
            width: auto !important;
            max-width: none !important;
            max-height: calc(100vh - 16px) !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) #ea-panel {
            max-height: calc(100vh - 16px) !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) #ea-header {
            grid-template-columns: 28px minmax(0, 1fr) 30px !important;
          }
          #${ROOT_ID} #ea-brand-toggle {
            width: 28px !important;
            height: 28px !important;
            border-radius: 7px !important;
          }
          #${ROOT_ID} #ea-title {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 1.08rem !important;
          }
          #${ROOT_ID} #ea-status {
            padding: 3px 6px !important;
            font-size: .66rem !important;
          }
          #${ROOT_ID} #ea-minimize {
            width: 30px;
            height: 30px;
          }
          #${ROOT_ID} #ea-content {
            padding: 10px !important;
          }
          #${ROOT_ID} #ea-workspace > [data-ea-workspace-body="review"] {
            padding: 0 !important;
          }
        }
        @media (min-width: 481px) and (max-height: 520px) {
          #${ROOT_ID}:not([data-ea-minimized="true"]) #ea-content {
            padding: 8px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) #ea-workspace > [data-ea-workspace-body="onboarding"] {
            padding: 10px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding] {
            gap: 6px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-identity] {
            gap: 6px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-logo] {
            width: 28px !important;
            height: 28px !important;
            border-radius: 8px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-identity] > div {
            line-height: 1.15 !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-title] {
            font-size: 1.12rem !important;
            line-height: 1.02 !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-description],
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-boundary] {
            margin-top: 4px !important;
            font-size: .88rem !important;
            line-height: 1.24 !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-status] {
            padding: 6px 0 !important;
            font-size: .84rem !important;
            line-height: 1.24 !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-status] > div + div {
            margin-top: 4px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-actions] {
            gap: 4px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-actions] [data-tw-primary-action] {
            min-height: 44px !important;
            padding: 6px 10px !important;
          }
          #${ROOT_ID}:not([data-ea-minimized="true"]) [data-ea-onboarding-skip] {
            padding: 2px !important;
          }
        }
      </style>
      <div id="ea-panel" style="background:#fff;border:1px solid #cdd2d8;border-radius:12px;box-shadow:0 4px 8px rgba(31,35,40,.12);overflow:hidden;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1f2328;display:flex;flex-direction:column;max-height:calc(100vh - 28px);">
        <div id="ea-header" style="height:52px;display:grid;grid-template-columns:28px minmax(0,1fr) 30px;align-items:center;gap:10px;padding:0 14px;border-bottom:1px solid #e2e5e9;background:#fff;">
          <div style="display:flex;align-items:center;gap:10px;min-width:0;">
            <button id="ea-brand-toggle" type="button" aria-label="Open Threadwise Home" title="Open Threadwise" style="position:relative;width:28px;height:28px;border-radius:7px;border:0;flex:0 0 auto;background:transparent;padding:0;cursor:pointer;overflow:hidden;">
              <img src="${BRAND_ICON_URL}" alt="" aria-hidden="true" data-ea-brand-img="true" style="width:100%;height:100%;display:block;object-fit:contain;background:transparent;">
            </button>
          </div>
          <div style="display:flex;align-items:center;gap:10px;min-width:0;">
            <div style="display:flex;align-items:center;gap:9px;min-width:0;">
              <div id="ea-title" style="font-size:14px;font-weight:720;letter-spacing:-0.02em;line-height:1.2;">Threadwise</div>
              <div id="ea-status" style="display:inline-flex;align-items:center;gap:6px;width:max-content;border:0;padding:0;background:transparent;color:#60666f;font-size:12px;font-weight:500;line-height:1.2;">Connecting</div>
              <div id="ea-header-tagline" style="color:#ad6400;font-family:ui-serif,Georgia,'Times New Roman',serif;font-size:0.58rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;line-height:1.05;white-space:nowrap;">CLEAR THREADS. BETTER INBOX.</div>
            </div>
          </div>
          <button id="ea-minimize" type="button" aria-label="Minimize Threadwise" title="Minimize Threadwise" style="width:30px;height:30px;border:0;background:transparent;color:#60666f;border-radius:7px;padding:0;cursor:pointer;font:inherit;font-size:18px;line-height:1;">−</button>
        </div>
        <div id="ea-content" style="padding:14px;display:grid;gap:13px;overflow-y:auto;min-height:0;">
          <main id="ea-workspace"></main>
        </div>
        <div id="ea-footer" style="display:none;flex:0 0 auto;"></div>
        <div id="ea-feedback-shell" style="display:none;border-top:1px solid rgba(36,24,18,.28);background:#fffdf7;padding:10px 12px;flex:0 0 auto;">
          <button id="ea-feedback-open" type="button" data-ea-action="open-feedback" style="width:100%;border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:840;box-shadow:2px 2px 0 #241812;">Note</button>
          <div id="ea-feedback-panel" style="display:none;margin-top:10px;"></div>
        </div>
      </div>
    `);
    document.body.appendChild(root);
    if (typeof globalThis.ResizeObserver === "function") {
      contextMenuResizeObserver = new ResizeObserver(() => positionContextMenu());
      contextMenuResizeObserver.observe(document.documentElement);
      contextMenuResizeObserver.observe(document.body);
      contextMenuResizeObserver.observe(root);
    }

    root.querySelector("#ea-minimize").addEventListener("click", () => {
      minimized = !minimized;
      renderMinimized();
    });
    root.querySelector("#ea-brand-toggle").addEventListener("click", handleBrandToggle);
    root.addEventListener("click", handlePanelClick);
    root.addEventListener("input", handlePanelInput);
    root.addEventListener("change", handlePanelInput);
    keyboardListener = handlePanelKeydown;
    root.addEventListener("keydown", keyboardListener);
    renderMinimized();
    renderFeedbackPanel();
  }

  function renderMinimized() {
    const root = document.getElementById(ROOT_ID);
    if (!root) {
      return;
    }
    if (minimized) {
      invalidateContextActions();
    }
    const content = root.querySelector("#ea-content");
    const footer = root.querySelector("#ea-footer");
    const feedbackShell = root.querySelector("#ea-feedback-shell");
    const button = root.querySelector("#ea-minimize");
    const status = root.querySelector("#ea-status");
    const title = root.querySelector("#ea-status")?.previousElementSibling;
    const header = root.querySelector("#ea-header");
    const headerCopy = title?.parentElement?.parentElement;
    const brandButton = root.querySelector("#ea-brand-toggle");
    if (!content || !footer || !button || !header || !brandButton) {
      return;
    }
    const wasMinimized = root.dataset.eaMinimized === "true";
    const statusCopy = connectionStatusCopy();
    content.style.display = minimized ? "none" : "grid";
    footer.style.display = "none";
    if (feedbackShell) {
      feedbackShell.style.display = !minimized && founderFeedbackVisible ? "block" : "none";
      root.dataset.eaFounderTools = founderFeedbackVisible ? "true" : "false";
    }
    root.style.width = minimized ? PANEL_WIDTH_MINIMIZED : (affectedReviewOpen ? PANEL_WIDTH_EXPANDED : PANEL_WIDTH);
    header.style.gridTemplateColumns = minimized ? "1fr" : "28px minmax(0, 1fr) 30px";
    header.style.padding = minimized ? "0" : "0 14px";
    header.style.borderBottom = minimized ? "0" : "1px solid #e2e5e9";
    button.style.setProperty("display", minimized ? "none" : "grid", "important");
    if (headerCopy) {
      headerCopy.style.display = minimized ? "none" : "flex";
    }
    brandButton.title = minimized ? `${statusCopy.label} - open Threadwise Home` : "Threadwise Home";
    brandButton.setAttribute("aria-label", minimized ? "Open Threadwise Home" : "Threadwise Home");
    button.textContent = "−";
    button.title = "Minimize Threadwise";
    button.setAttribute("aria-label", "Minimize Threadwise");
    if (status) {
      status.textContent = statusCopy.label;
      status.style.background = statusCopy.background;
      status.style.color = statusCopy.foreground;
    }
    if (title) {
      title.style.fontSize = "14px";
    }
    const subtitle = root.querySelector("#ea-status")?.nextElementSibling;
    if (subtitle) {
      subtitle.style.display = minimized ? "none" : "block";
    }
    root.dataset.eaMinimized = minimized ? "true" : "false";
    if (!minimized && wasMinimized) {
      ANALYTICS?.openExtension();
    }
  }

  function selectedContext() {
    return PROVIDER.selectedContext();
  }

  function currentHostRoute() {
    return `${window.location.pathname || ""}${window.location.search || ""}${window.location.hash || ""}`;
  }

  function sampleActualProgressionHostContext() {
    let sampled = null;
    try {
      sampled = PROVIDER.selectedContext();
    } catch (_error) {
      sampled = null;
    }
    const source = sampled && typeof sampled === "object" ? sampled : {};
    return {
      ...source,
      provider: String(source.provider || ACTIVE_PROVIDER).trim().toLowerCase(),
      page_url: window.location.href,
      selected_at: source.selected_at || new Date().toISOString(),
    };
  }

  function providerName(provider = ACTIVE_PROVIDER) {
    return provider === "protonmail" ? "Proton Mail" : "Gmail";
  }

  function activeProviderName() {
    return lastSidebarState?.ui_state?.provider_name || PROVIDER.name || providerName();
  }

  function contextFromItem(item) {
    return {
      provider: item?.provider || ACTIVE_PROVIDER,
      message_id: item?.message_id || "",
      thread_id: item?.thread_id || "",
      subject: item?.subject || "",
      sender: item?.sender || "",
    };
  }

  function progressionIdentity(sidebarState = lastSidebarState, selected = sidebarState?.selected_email) {
    const context = sidebarState?.selected_context || {};
    return REVIEW_PROGRESSION.normalizeIdentity({
      provider: selected?.provider || context.provider || ACTIVE_PROVIDER,
      message_id: selected?.message_id || context.message_id || "",
      thread_id: selected?.thread_id || context.thread_id || "",
    });
  }

  function progressionIdentityKey(identity) {
    return REVIEW_PROGRESSION.identityKey(identity);
  }

  function progressionIdentityFromContext(context) {
    return REVIEW_PROGRESSION.normalizeIdentity({
      provider: context?.provider || ACTIVE_PROVIDER,
      message_id: context?.message_id || context?.messageId || "",
      thread_id: context?.thread_id || context?.threadId || "",
    });
  }

  function displayedProgressionIdentities() {
    const identities = [progressionIdentity()];
    if (manualPreviewContext?.message_id) {
      identities.push(progressionIdentityFromContext(manualPreviewContext));
    } else {
      const liveContext = stabilizedLiveContext(selectedContext());
      if (liveContext?.message_id) {
        identities.push(progressionIdentityFromContext(liveContext));
      }
    }
    return identities;
  }

  function progressionContextAnchorPart(context, overrides = {}) {
    const source = context && typeof context === "object" ? context : {};
    const identity = REVIEW_PROGRESSION.normalizeIdentity({
      provider: source.provider || ACTIVE_PROVIDER,
      message_id: source.message_id || source.messageId || "",
      thread_id: source.thread_id || source.threadId || "",
    });
    return Object.freeze({
      ...identity,
      pageUrl: String(overrides.pageUrl || source.page_url || source.pageUrl || ""),
      route: String(overrides.route || source.page_route || source.route || ""),
    });
  }

  function progressionDisplayIdentity(anchorPart) {
    return [
      anchorPart?.provider || "",
      anchorPart?.messageId || "",
      anchorPart?.threadId || "",
    ].join("|");
  }

  function progressionAnchorPartMatches(expected, actual) {
    return (
      expected?.provider === actual?.provider
      && expected?.messageId === actual?.messageId
      && expected?.threadId === actual?.threadId
      && expected?.pageUrl === actual?.pageUrl
      && expected?.route === actual?.route
    );
  }

  function currentProgressionHostAnchor(actualHostContext = null) {
    const sampledHostContext = actualHostContext || sampleActualProgressionHostContext();
    return progressionContextAnchorPart(sampledHostContext, {
      pageUrl: window.location.href,
      route: currentHostRoute(),
    });
  }

  function progressionHostAnchorMatches(expectedHost, actualHostContext = null) {
    const currentHost = currentProgressionHostAnchor(actualHostContext);
    return Boolean(
      expectedHost
      && currentHost.provider
      && currentHost.provider === String(ACTIVE_PROVIDER || "").trim().toLowerCase()
      && currentHost.pageUrl === window.location.href
      && currentHost.route === currentHostRoute()
      && progressionAnchorPartMatches(expectedHost, currentHost)
    );
  }

  function currentProgressionDisplayContext() {
    if (manualPreviewContext?.message_id) {
      return manualPreviewContext;
    }
    const sidebarContext = lastSidebarState?.selected_context;
    if (sidebarContext && (sidebarContext.message_id || sidebarContext.thread_id || sidebarContext.subject || sidebarContext.sender)) {
      return sidebarContext;
    }
    if (progressionCheck?.anchor?.display) {
      return {
        provider: progressionCheck.anchor.display.provider,
        message_id: progressionCheck.anchor.display.messageId,
        thread_id: progressionCheck.anchor.display.threadId,
      };
    }
    return sidebarContext
      || (forcedHome && lastLiveContext?.message_id ? lastLiveContext : null)
      || lastLiveContext
      || selectedContext();
  }

  function progressionContextAnchor(generation) {
    const host = currentProgressionHostAnchor();
    const display = progressionContextAnchorPart(currentProgressionDisplayContext(), {
      pageUrl: host.pageUrl,
      route: host.route,
    });
    return Object.freeze({
      generation,
      provider: String(ACTIVE_PROVIDER || "").trim().toLowerCase(),
      host,
      display,
      displayIdentity: progressionDisplayIdentity(display),
    });
  }

  function progressionContextAnchorMatches(check, actualHostContext = null) {
    const anchor = check?.anchor;
    if (!anchor || Number(anchor.generation) !== Number(check.generation)) {
      return false;
    }
    const sampledHostContext = actualHostContext || sampleActualProgressionHostContext();
    const currentHost = currentProgressionHostAnchor(sampledHostContext);
    const currentDisplay = progressionContextAnchorPart(currentProgressionDisplayContext(), {
      pageUrl: currentHost.pageUrl,
      route: currentHost.route,
    });
    const displayMatches = progressionAnchorPartMatches(anchor.display, currentDisplay)
      && anchor.displayIdentity === progressionDisplayIdentity(currentDisplay);
    return (
      anchor.provider === String(ACTIVE_PROVIDER || "").trim().toLowerCase()
      && progressionHostAnchorMatches(anchor.host, sampledHostContext)
      && displayMatches
    );
  }

  function invalidateProgressionForHostNavigation(actualHostContext = null) {
    if (!progressionCheck) {
      return false;
    }
    const sampledHostContext = actualHostContext || sampleActualProgressionHostContext();
    if (progressionContextAnchorMatches(progressionCheck, sampledHostContext)) {
      return false;
    }
    return supersedeProgressionCheckForContextChange({
      actualHostContext: sampledHostContext,
      refreshCurrentContext: true,
    });
  }

  function progressionResponseContextIsCurrent(generation) {
    if (!progressionCheck || progressionCheck.generation !== generation || progressionCheck.status !== "checking") {
      return false;
    }
    return progressionContextAnchorMatches(progressionCheck);
  }

  function scheduleProgressionHostResample() {
    if (hostContextInvalidationMicrotaskPending) {
      return;
    }
    hostContextInvalidationMicrotaskPending = true;
    const resample = () => {
      hostContextInvalidationMicrotaskPending = false;
      if (companionLifecycleActive) {
        invalidateProgressionForHostNavigation();
      }
    };
    if (typeof window.queueMicrotask === "function") {
      window.queueMicrotask(resample);
    } else {
      Promise.resolve().then(resample);
    }
  }

  function installHostContextMutationObserver() {
    if (typeof window.MutationObserver !== "function" || !document.body) {
      return;
    }
    hostContextMutationObserver = new window.MutationObserver((records) => {
      const root = document.getElementById(ROOT_ID);
      const touchesHost = records.some((record) => {
        if (!root || !root.contains(record.target)) {
          return true;
        }
        return Array.from(record.addedNodes || [])
          .concat(Array.from(record.removedNodes || []))
          .some((node) => node !== root && !root.contains(node));
      });
      if (touchesHost) {
        scheduleProgressionHostResample();
      }
    });
    hostContextMutationObserver.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: [
        "data-legacy-message-id",
        "data-message-id",
        "data-thread-perm-id",
        "email",
        "aria-label",
      ],
    });
  }

  function progressionFlightIsCurrent(token) {
    if (!token) {
      return true;
    }
    const flight = token.kind === "handled-review-acknowledge"
      ? handledProgressionFlight
      : optimisticDecision;
    return Boolean(
      flight?.token?.token === token.token
      && flight.token.generation === token.generation
      && flight.token.kind === token.kind,
    );
  }

  function progressionFlightHostIsCurrent(token) {
    if (!token || !progressionFlightIsCurrent(token)) {
      return false;
    }
    const flight = token.kind === "handled-review-acknowledge"
      ? handledProgressionFlight
      : optimisticDecision;
    return progressionHostAnchorMatches(flight?.hostAnchor);
  }

  function releaseStaleProgressionFlight(token) {
    if (!token || !progressionFlightIsCurrent(token)) {
      return false;
    }
    if (token.kind === "handled-review-acknowledge") {
      handledProgressionFlight = null;
    } else if (optimisticDecision?.token?.token === token.token) {
      optimisticDecision.flightActive = false;
      applyInFlight = false;
    }
    return true;
  }

  function progressionResponseCanRender(token, responseState = null) {
    if (!token || !progressionFlightIsCurrent(token)) {
      return !token;
    }
    const displayed = displayedProgressionIdentities();
    if (!displayed.length || !displayed.every((identity) => REVIEW_PROGRESSION.matchesRequestToken(token, {
      generation: token.generation,
      identity,
      kind: token.kind,
    }))) {
      return false;
    }
    if (!responseState) {
      return !token.identity?.threadId;
    }
    const responseIdentity = progressionIdentity(responseState, responseState.selected_email);
    return REVIEW_PROGRESSION.responseMatchesToken(token, {
      generation: token.generation,
      identity: responseIdentity,
      kind: token.kind,
    });
  }

  function progressionResponseIdentity(responseState = null) {
    const source = responseState?.sidebar_state || responseState || {};
    const selected = source.selected_email || {};
    const context = responseState?.selected_context || source.selected_context || {};
    return REVIEW_PROGRESSION.normalizeIdentity({
      provider: selected.provider || context.provider || "",
      message_id: selected.message_id || context.message_id || "",
      thread_id: selected.thread_id || context.thread_id || "",
    });
  }

  function progressionResponseIsAuthoritative(token, responseState = null) {
    if (!token || !responseState) {
      return false;
    }
    const expected = REVIEW_PROGRESSION.normalizeIdentity(token.identity);
    const actual = progressionResponseIdentity(responseState);
    return (
      Boolean(actual.provider && actual.messageId)
      && actual.provider === expected.provider
      && actual.messageId === expected.messageId
      && (!expected.threadId || actual.threadId === expected.threadId)
    );
  }

  function rejectProgressionResponse(token) {
    if (!token) {
      return false;
    }
    forgetCommittedIdentity(token.identity);
    const existing = optimisticDecision?.token?.token === token.token ? optimisticDecision : null;
    optimisticDecision = {
      ...(existing || {
        token,
        identity: token.identity,
        localAccepted: false,
        decisionKind: token.kind,
        advanceDone: false,
      }),
      token,
      identity: token.identity,
      localAccepted: false,
      decisionKind: token.kind,
      providerWriteState: "retry",
      retryStateLocked: true,
      flightActive: false,
      responseReceived: true,
      responseAccepted: false,
    };
    applyInFlight = false;
    handledProgressionFlight = null;
    handledAdvanceError = "";
    teachFlowState = "teaching";
    selectedDecisionMode = "review";
    return true;
  }

  function progressionDisplayCanRender(token) {
    if (!token || !progressionFlightIsCurrent(token)) {
      return !token;
    }
    const displayed = displayedProgressionIdentities();
    return Boolean(displayed.length) && displayed.every((identity) => REVIEW_PROGRESSION.matchesRequestToken(token, {
      generation: token.generation,
      identity,
      kind: token.kind,
    }));
  }

  function displayedStateIsSettled() {
    const providerIdentity = progressionIdentity();
    if (!providerIdentity.messageId) {
      return false;
    }
    const displayedContext = manualPreviewContext || stabilizedLiveContext(selectedContext());
    if (!displayedContext?.message_id) {
      return true;
    }
    return REVIEW_PROGRESSION.identitiesCompatible(providerIdentity, progressionIdentityFromContext(displayedContext));
  }

  function captureFocusedCompanionTarget() {
    const root = document.getElementById(ROOT_ID);
    const active = document.activeElement;
    if (!root || !active || active === document.body || !root.contains(active)) {
      return null;
    }
    return {
      id: active.id || "",
      action: active.getAttribute("data-ea-action") || "",
      queue: active.hasAttribute("data-ea-queue-navigation"),
      queueNav: active.getAttribute("data-ea-queue-nav") || "",
      contextItem: active.getAttribute("data-ea-context-item") || "",
    };
  }

  function restoreFocusedCompanionTarget(target) {
    if (!target) {
      return;
    }
    const root = document.getElementById(ROOT_ID);
    if (!root) {
      return;
    }
    let node = target.id ? document.getElementById(target.id) : null;
    if (!node && target.queue) {
      node = root.querySelector("[data-ea-queue-navigation]");
    }
    if (!node && target.queueNav) {
      node = Array.from(root.querySelectorAll("[data-ea-queue-nav]"))
        .find((candidate) => candidate.getAttribute("data-ea-queue-nav") === target.queueNav);
    }
    if (!node && target.contextItem) {
      node = Array.from(root.querySelectorAll("[data-ea-context-item]"))
        .find((candidate) => candidate.getAttribute("data-ea-context-item") === target.contextItem);
    }
    if (!node && target.action) {
      node = Array.from(root.querySelectorAll("[data-ea-action]"))
        .find((candidate) => candidate.getAttribute("data-ea-action") === target.action);
    }
    node?.focus?.({ preventScroll: true });
  }

  function renderCurrentStatePreservingFocus(state) {
    const focused = captureFocusedCompanionTarget();
    renderState(state);
    restoreFocusedCompanionTarget(focused);
  }

  function committedIdentityKeys() {
    return committedReviewIdentities
      .map((identity) => progressionIdentityKey(identity))
      .filter(Boolean);
  }

  function rememberCommittedIdentity(identity) {
    const normalized = REVIEW_PROGRESSION.normalizeIdentity(identity);
    const key = progressionIdentityKey(normalized);
    if (!key) {
      return;
    }
    committedReviewIdentities = [
      ...committedReviewIdentities.filter((candidate) => progressionIdentityKey(candidate) !== key),
      normalized,
    ].slice(-32);
  }

  function forgetCommittedIdentity(identity) {
    const key = progressionIdentityKey(identity);
    if (!key) {
      return;
    }
    committedReviewIdentities = committedReviewIdentities.filter(
      (candidate) => progressionIdentityKey(candidate) !== key,
    );
  }

  function clearOptimisticDecisionStatus({ preserveHandledFlight = false } = {}) {
    optimisticDecision = null;
    if (!preserveHandledFlight) {
      handledProgressionFlight = null;
    }
  }

  function providerActivityState(sidebarState) {
    const uiState = sidebarState?.ui_state || {};
    const followUp = uiState.async_follow_up || {};
    if (followUp.kind === "teach-apply-refresh" && followUp.state) {
      return String(followUp.state).toLowerCase();
    }
    const activity = Array.isArray(uiState.activity_feed) ? uiState.activity_feed : [];
    const relevant = activity.find((item) => (
      item && ["working", "pending", "done", "complete", "completed", "retry", "error", "failed"]
        .includes(String(item.state || "").toLowerCase())
    ));
    return String(relevant?.state || "").toLowerCase();
  }

  function updateOptimisticDecisionLifecycle(sidebarState, state = "") {
    if (!optimisticDecision) {
      return;
    }
    const aggregateState = String(state || providerActivityState(sidebarState) || "").toLowerCase();
    if (["retry", "error", "failed"].includes(aggregateState)) {
      optimisticDecision.providerWriteState = aggregateState;
      optimisticDecision.retryStateLocked = true;
      return;
    }
    if (optimisticDecision.retryStateLocked) {
      return;
    }
    if (aggregateState) {
      optimisticDecision.providerWriteState = aggregateState;
    }
  }

  function renderPreviousDecisionStatusHtml() {
    if (!optimisticDecision?.localAccepted) {
      return "";
    }
    const model = REVIEW_PROGRESSION.previousDecisionStatus({
      localAccepted: true,
      providerWriteState: optimisticDecision.providerWriteState || "working",
      providerName: activeProviderName(),
      responseReceived: Boolean(optimisticDecision.responseReceived),
      responseAccepted: optimisticDecision.responseAccepted,
      decisionKind: optimisticDecision.decisionKind || "",
    });
    if (!model.visible) {
      return "";
    }
    const tone = model.state === "retry"
      ? { background: "#fff4dd", color: "#8a4b00" }
      : model.state === "done"
        ? { background: "#eef7f5", color: "#0f766e" }
        : { background: "#eef3ff", color: "#2146b7" };
    return `
      <div data-ea-previous-decision-status="${escapeHtml(model.state)}" role="status" aria-live="polite" style="border-radius:11px;background:${tone.background};padding:9px 11px;color:${tone.color};line-height:1.4;font-size:.84rem;">
        <strong>${escapeHtml(model.label)}</strong>
        <span style="margin-left:4px;">· ${escapeHtml(model.message)}</span>
      </div>
    `;
  }

  function reconcileCommittedIdentitiesFromState(state) {
    const items = state && Array.isArray(state.needs_attention_items)
      ? state.needs_attention_items
      : null;
    if (!items) {
      return;
    }
    const activeKeys = new Set(items
      .map((item) => progressionIdentityKey(REVIEW_PROGRESSION.itemIdentity(item, ACTIVE_PROVIDER)))
      .filter(Boolean));
    const dailyCount = state.sidebar_state?.daily_summary?.needs_attention_count;
    if (REVIEW_PROGRESSION.isExplicitFiniteNumericZero(dailyCount)) {
      committedReviewIdentities = [];
      return;
    }
    committedReviewIdentities = committedReviewIdentities.filter(
      (identity) => activeKeys.has(progressionIdentityKey(identity)),
    );
  }

  function localProgressionActivityItem() {
    if (!optimisticDecision?.localAccepted || !forcedHome) {
      return null;
    }
    const status = REVIEW_PROGRESSION.previousDecisionStatus({
      localAccepted: true,
      providerWriteState: optimisticDecision.providerWriteState || "working",
      providerName: activeProviderName(),
      responseReceived: Boolean(optimisticDecision.responseReceived),
      responseAccepted: optimisticDecision.responseAccepted,
      decisionKind: optimisticDecision.decisionKind || "",
    });
    if (!status.visible) {
      return null;
    }
    return {
      id: `review-progression-${optimisticDecision.token?.token || "latest"}`,
      kind: "review-progression",
      state: status.state,
      label: status.label,
      message: status.message,
      action: status.state === "retry" ? "force-refresh" : "",
      action_label: status.state === "retry" ? "Check queue again" : "",
    };
  }

  function progressionItemsForFilter(filter, { includeCommitted = false } = {}) {
    const source = filter === "needs_attention_items"
      ? filteredQueueItems(queueQuery, { excludeCommitted: false })
      : summaryItemsForFilter(filter);
    return REVIEW_PROGRESSION.eligibleItems({
      items: source,
      activeProvider: ACTIVE_PROVIDER,
      committedIdentities: includeCommitted ? [] : committedReviewIdentities,
    });
  }

  function nextProgressionItem(filter, currentIdentity) {
    return REVIEW_PROGRESSION.nextEligibleItem({
      items: progressionItemsForFilter(filter, { includeCommitted: true }),
      activeProvider: ACTIVE_PROVIDER,
      currentIdentity,
      committedIdentities: committedReviewIdentities,
    });
  }

  function openItemPreview(item, options = {}) {
    if (!item) {
      return false;
    }
    if (options.queueContext && !findQueueItem(item.message_id)) {
      return false;
    }
    if (!options.preserveProgressionStatus) {
      clearOptimisticDecisionStatus({ preserveHandledFlight: Boolean(handledProgressionFlight) });
    }
    forcedHome = false;
    manualPreviewContext = contextFromItem(item);
    manualPreviewOriginContext = lastLiveContext ? { ...lastLiveContext } : null;
    queuePreviewActive = Boolean(options.queueContext);
    if (queuePreviewActive) {
      requestQueueNavigationFocus();
    } else {
      clearPendingQueueNavigationFocus();
    }
    teachPreview = null;
    previousTeachPreview = null;
    teachResult = null;
    teachFlowState = "teaching";
    inboxApplyConfirmOpen = false;
    teachOutcome = null;
    teachWriteThrough = null;
    affectedReviewOpen = false;
    if (options.clearDraft !== false) {
      teachDraft = { targetLabel: "", note: "" };
    }
    ANALYTICS?.startEmailReview(
      item.message_id || "",
      "needs_attention_queue",
      Number((lastSidebarState?.daily_summary || {}).needs_attention_count || 0),
    );
    refreshSelection(true);
    return true;
  }

  function pollConnectionHealth() {
    if (
      !companionLifecycleActive || refreshInFlight || connectionPollInFlight || progressionCheck
      || applyInFlight
      || optimisticDecision?.flightActive
    ) {
      return latestStateReadGeneration;
    }
    if (lastConnectionState.kind !== "ready") {
      return refreshSelection();
    }
    connectionPollInFlight = true;
    chrome.runtime.sendMessage({ type: "email-agent:probe-health" }, (response) => {
      const runtimeError = chrome.runtime.lastError?.message || "";
      if (releaseConnectionPoll()) {
        return;
      }
      if (!companionLifecycleActive) {
        return;
      }
      if (applyInFlight || optimisticDecision?.flightActive) {
        return;
      }
      if (runtimeError) {
        previousPayload = "";
        renderError(runtimeError || "Could not reach extension background.", {
          kind: "helper-unreachable",
          label: "Helper unreachable",
          details: runtimeError || "Could not reach extension background.",
        });
        return;
      }
      const connectionState = normalizeConnectionState(response && response.connection_state);
      if (response?.ok && connectionState.kind === "ready") {
        connectionRetryFeedback = "";
        lastConnectionState = connectionState;
        renderMinimized();
        return;
      }
      previousPayload = "";
      renderError((response && response.error) || "Could not reach local companion server.", connectionState);
    });
    return latestStateReadGeneration;
  }

  function releaseConnectionPoll() {
    connectionPollInFlight = false;
    const pendingRefresh = pendingRefreshAfterConnectionPoll;
    pendingRefreshAfterConnectionPoll = null;
    if (!companionLifecycleActive || !pendingRefresh) {
      return false;
    }
    refreshSelection(pendingRefresh.force, pendingRefresh.options);
    return true;
  }

  function refreshSelection(force = false) {
    const options = arguments[1] || {};
    if (connectionPollInFlight) {
      const pendingRefresh = pendingRefreshAfterConnectionPoll;
      if (force || !pendingRefresh || !pendingRefresh.force) {
        pendingRefreshAfterConnectionPoll = {
          force: Boolean(force || pendingRefresh?.force),
          options,
        };
      }
      return latestStateReadGeneration;
    }
    const sampledHostContext = options.actualHostContext || sampleActualProgressionHostContext();
    const nextLiveContext = options.contextInvalidation
      ? sampledHostContext
      : stabilizedLiveContext(sampledHostContext);
    lastLiveContext = nextLiveContext;
    if (progressionCheck && options.progressionGeneration == null && !progressionContextAnchorMatches(progressionCheck)) {
      return supersedeProgressionCheckForContextChange({
        actualHostContext: sampledHostContext,
        refreshCurrentContext: true,
      });
    }
    if (progressionCheck && options.progressionGeneration == null) {
      return latestStateReadGeneration;
    }
    if (
      forcedHome
      && forcedHomeLiveContext?.page_url
      && lastLiveContext?.page_url
      && lastLiveContext.page_url !== forcedHomeLiveContext.page_url
    ) {
      forcedHome = false;
      forcedHomeLiveContext = null;
    }
    const context = chooseRefreshContext();
    const payload = JSON.stringify({
      provider: context.provider || "",
      message_id: context.message_id || "",
      thread_id: context.thread_id || "",
      subject: context.subject || "",
      sender: context.sender || "",
      gmail_labels: context.gmail_labels || "",
      provider_labels: context.provider_labels || "",
      provider_ref: context.provider_ref || "",
      page_url: context.page_url || "",
    });
    if (!force && payload === previousPayload && !asyncFollowUpIsWorking()) {
      return latestStateReadGeneration;
    }
    if (refreshInFlight && !force) {
      return latestStateReadGeneration;
    }
    const readGeneration = ++stateReadGeneration;
    latestStateReadGeneration = readGeneration;
    const renderedContext = (lastSidebarState && lastSidebarState.selected_context) || {};
    if (
      !forcedHome
      && !manualPreviewContext
      && isMeaningfulContext(context)
      && !contextsMatch(context, renderedContext)
      && !options.suppressTransition
    ) {
      renderSelectedEmailTransition(context);
    }
    refreshInFlight = true;
    chrome.runtime.sendMessage({ type: "email-agent:get-state", context }, (response) => {
      if (readGeneration !== latestStateReadGeneration) {
        return;
      }
      refreshInFlight = false;
      const manualConnectionRetry = connectionRetryInFlight;
      connectionRetryInFlight = false;
      if (chrome.runtime.lastError) {
        if (manualConnectionRetry) {
          connectionRetryFeedback = "failed";
        }
        previousPayload = "";
        if (options.progressionGeneration != null) {
          if (!progressionResponseContextIsCurrent(options.progressionGeneration)) {
            return;
          }
          finishProgressionCheckWithError(options.progressionGeneration, chrome.runtime.lastError.message || "Could not verify the review queue.");
          return;
        }
        renderError(chrome.runtime.lastError.message || "Could not reach extension background.", {
          kind: "helper-unreachable",
          label: "Helper unreachable",
          details: chrome.runtime.lastError.message || "Could not reach extension background.",
        });
        return;
      }
      if (!response || !response.ok) {
        previousPayload = "";
        if (options.progressionGeneration != null) {
          if (!progressionResponseContextIsCurrent(options.progressionGeneration)) {
            return;
          }
          finishProgressionCheckWithError(
            options.progressionGeneration,
            (response && (response.payload?.error || response.error)) || "Could not verify the review queue.",
          );
          return;
        }
        const connectionState = normalizeConnectionState(response && response.connection_state);
        if (connectionState.kind === "ready") {
          connectionRetryFeedback = "";
          renderLoadingState((response && response.error) || "Threadwise is connected but the inbox state is still loading.");
          return;
        }
        if (manualConnectionRetry) {
          connectionRetryFeedback = "failed";
        }
        renderError((response && response.error) || "Could not reach local companion server.", connectionState);
        return;
      }
      if (options.progressionGeneration != null) {
        if (handleProgressionStateResponse(options.progressionGeneration, response.payload, response.connection_state)) {
          previousPayload = payload;
        }
        return;
      }
      connectionRetryFeedback = "";
      previousPayload = payload;
      lastConnectionState = normalizeConnectionState(response.connection_state || {
        kind: "ready",
        label: "Ready",
        details: "Threadwise is connected.",
      });
      renderState(response.payload);
    });
    return readGeneration;
  }

  function requestProgressionRefresh(generation) {
    clearProgressionRefreshTimer();
    return refreshSelection(true, { progressionGeneration: generation });
  }

  function clearProgressionRefreshTimer() {
    if (progressionRefreshTimeoutId !== null) {
      window.clearTimeout(progressionRefreshTimeoutId);
      progressionRefreshTimeoutId = null;
    }
  }

  function scheduleProgressionRefresh(generation) {
    clearProgressionRefreshTimer();
    progressionRefreshTimeoutId = window.setTimeout(() => {
      progressionRefreshTimeoutId = null;
      if (progressionCheck?.generation !== generation || progressionCheck.status !== "checking") {
        return;
      }
      requestProgressionRefresh(generation);
    }, PROGRESSION_REFRESH_INTERVAL_MS);
  }

  function clearProgressionCheck() {
    clearProgressionRefreshTimer();
    progressionCheck = null;
  }

  function removeProgressionPresentation() {
    const node = document.querySelector(`#${ROOT_ID} [data-ea-review-progression]`);
    if (!node || node.contains(document.activeElement)) {
      return;
    }
    node.remove();
  }

  function supersedeProgressionCheckForContextChange({ actualHostContext = null, refreshCurrentContext = true } = {}) {
    if (!progressionCheck) {
      return false;
    }
    clearProgressionCheck();
    reviewProgressionGeneration += 1;
    refreshInFlight = false;
    latestStateReadGeneration = ++stateReadGeneration;
    previousPayload = "";
    gmailCheckResult = null;
    removeProgressionPresentation();
    if (forcedHome) {
      forcedHome = false;
      forcedHomeLiveContext = null;
    }
    if (refreshCurrentContext && companionLifecycleActive) {
      refreshSelection(true, {
        actualHostContext: actualHostContext || sampleActualProgressionHostContext(),
        contextInvalidation: true,
        suppressTransition: true,
      });
    }
    return true;
  }

  function finishProgressionCheckWithError(generation, message) {
    if (!progressionCheck || progressionCheck.generation !== generation || progressionCheck.status !== "checking") {
      return;
    }
    clearProgressionRefreshTimer();
    progressionCheck.status = "retry";
    gmailCheckResult = {
      kind: "review-progression-retry",
      title: "Review queue status unverified",
      message: `This check needs a retry. ${message || "Threadwise could not verify the provider-scoped review queue."}`,
    };
    renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
  }

  function supersedeProgressionCheckWithDecisionFailure(generation, message) {
    if (!progressionCheck || progressionCheck.generation !== generation) {
      return;
    }
    clearProgressionRefreshTimer();
    progressionCheck.status = "retry";
    progressionCheck.readGeneration = null;
    refreshInFlight = false;
    latestStateReadGeneration = ++stateReadGeneration;
    gmailCheckResult = {
      kind: "review-progression-retry",
      title: "Review queue status unverified",
      message: `This check needs a retry. ${message || "The last decision was not confirmed. Threadwise kept this email eligible and needs a fresh queue check."}`,
    };
    renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
  }

  function handleProgressionStateResponse(generation, payload, connectionState = null) {
    if (!progressionCheck || progressionCheck.generation !== generation || progressionCheck.status !== "checking") {
      return false;
    }
    const check = progressionCheck;
    const actualHostContext = sampleActualProgressionHostContext();
    const contextMatches = progressionContextAnchorMatches(check, actualHostContext);
    if (!contextMatches) {
      supersedeProgressionCheckForContextChange({
        actualHostContext,
        refreshCurrentContext: true,
      });
      return false;
    }
    lastConnectionState = normalizeConnectionState(connectionState || {
      kind: "ready",
      label: "Ready",
      details: "Threadwise is connected.",
    });
    const freshState = normalizeHarnessState(payload, { preserveMissingQueues: true });
    const filter = check.filter || "needs_attention_items";
    const queueKind = filter;
    const presentation = REVIEW_PROGRESSION.completionPresentation({
      query: check.query || "",
      loadedItems: freshState[queueKind] || [],
      freshState,
      activeProvider: ACTIVE_PROVIDER,
      committedIdentities: committedReviewIdentities,
      queueKind,
      requireDailyCount: queueKind === "needs_attention_items",
      refreshGeneration: generation,
      expectedGeneration: generation,
      followUpState: providerActivityState(freshState.sidebar_state),
    });
    updateOptimisticDecisionLifecycle(freshState.sidebar_state);
    if (presentation.kind === REVIEW_PROGRESSION.NEXT_AVAILABLE && presentation.item) {
      clearProgressionCheck();
      gmailCheckResult = null;
      reconcileCommittedIdentitiesFromState(freshState);
      forcedHome = false;
      forcedHomeLiveContext = null;
      renderState(freshState);
      openItemPreview(presentation.item, {
        queueContext: queueKind === "needs_attention_items",
        preserveProgressionStatus: true,
      });
      return true;
    }
    if (presentation.kind === REVIEW_PROGRESSION.COMPLETE) {
      clearProgressionCheck();
      const completionResult = {
        title: filter === "needs_attention_items" ? "Review queue complete" : `${bucketLabelForFilter(filter)} complete`,
        message: presentation.message,
      };
      gmailCheckResult = {
        kind: "review-progression-complete",
        ...completionResult,
      };
      reconcileCommittedIdentitiesFromState(freshState);
      forcedHome = true;
      forcedHomeLiveContext = lastLiveContext ? { ...lastLiveContext } : null;
      renderState(freshState);
      return true;
    }
    if (presentation.kind === REVIEW_PROGRESSION.RETRY) {
      finishProgressionCheckWithError(generation, presentation.message);
      return true;
    }
    progressionCheck.status = "checking";
    gmailCheckResult = {
      kind: "review-progression-checking",
      title: presentation.title,
      message: presentation.message,
    };
    renderState(freshState);
    scheduleProgressionRefresh(generation);
    return true;
  }

  function asyncFollowUpIsWorking() {
    return String((((lastSidebarState || {}).ui_state || {}).async_follow_up || {}).state || "") === "working";
  }

  function renderLoadingState(message) {
    lastConnectionState = normalizeConnectionState({
      kind: "ready",
      label: "Ready",
      details: "Threadwise is responding at the local companion server.",
    });
    if (onboardingVisible) {
      renderOnboarding();
      return;
    }
    renderStandaloneWorkspace("loading", `
      <div data-ea-selected-state="loading" data-ea-recovery-surface data-ea-recovery-kind="loading" role="status" aria-live="polite" aria-busy="true">
        <div data-ea-recovery-eyebrow>Getting ready</div>
        <h2 data-ea-recovery-title>Loading Threadwise\u2026</h2>
        <p data-ea-recovery-copy>${escapeHtml(message)}</p>
        <div data-ea-recovery-progress aria-hidden="true"><span></span></div>
      </div>
    `);
  }

  function renderSelectedEmailTransition(context) {
    lastConnectionState = normalizeConnectionState({
      kind: "ready",
      label: "Ready",
      details: `Threadwise is reading the selected ${activeProviderName()} message.`,
    });
    renderStandaloneWorkspace("understanding", `
      <div data-ea-selected-state="reading" role="status" aria-live="polite" aria-busy="true" style="display:grid;gap:12px;">
        <div style="font-size:1.3rem;font-weight:840;line-height:1.2;">${escapeHtml(context.subject || "Selected email")}</div>
        <div style="color:#6b6255;overflow-wrap:anywhere;">${escapeHtml(context.sender || "")}</div>
        <div style="border-radius:14px;background:#fff8eb;padding:12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Reading progress</div>
          <div style="margin-top:8px;">Reading this email…</div>
          <div style="margin-top:6px;color:#6b6255;">Threadwise is updating the selected-email view.</div>
        </div>
      </div>
    `);
  }

  function chooseRefreshContext() {
    if (forcedHome) {
      return {
        provider: ACTIVE_PROVIDER,
        message_id: "",
        thread_id: "",
        subject: "",
        sender: "",
        page_url: window.location.href,
      };
    }
    if (manualPreviewContext) {
      return manualPreviewContext;
    }
    if (shouldHoldSelectedContext()) {
      return (lastSidebarState && lastSidebarState.selected_context) || lastLiveContext;
    }
    return lastLiveContext;
  }

  function releaseCompletedQueuePreviewOnGmailClick(event) {
    if (event?.target?.closest?.(`#${ROOT_ID}`)) {
      return;
    }
    const completedReceipt = document.querySelector(
      `#${ROOT_ID} [data-ea-selected-state="receipt"], `
      + `#${ROOT_ID} [data-ea-selected-state="teach-result-receipt"], `
      + `#${ROOT_ID} [data-ea-selected-state="future-learning-receipt"]`,
    );
    if (!completedReceipt) {
      return;
    }
    manualPreviewContext = null;
    manualPreviewOriginContext = null;
    clearPendingQueueNavigationFocus();
    previousPayload = "";
    resetPerEmailInteraction();
  }

  function isQueueFocusHandoffTrigger(event) {
    return Boolean(event?.target?.closest?.(
      `#${ROOT_ID} [data-ea-queue-item], #${ROOT_ID} [data-ea-queue-nav], #${ROOT_ID} [data-ea-action='open-needs-attention']`,
    ));
  }

  function requestQueueNavigationFocus() {
    pendingQueueNavigationFocus = {
      origin: document.activeElement,
    };
  }

  function clearPendingQueueNavigationFocus() {
    pendingQueueNavigationFocus = null;
  }

  function restorePendingQueueNavigationFocus() {
    const pending = pendingQueueNavigationFocus;
    if (!pending) {
      return;
    }
    if (!queuePreviewActive || !manualPreviewContext) {
      clearPendingQueueNavigationFocus();
      return;
    }
    const root = document.getElementById(ROOT_ID);
    const navigation = root?.querySelector?.("[data-ea-queue-navigation]");
    if (!navigation) {
      return;
    }
    const activeElement = document.activeElement;
    if (
      activeElement
      && activeElement !== document.body
      && activeElement !== pending.origin
    ) {
      clearPendingQueueNavigationFocus();
      return;
    }
    navigation.focus({ preventScroll: true });
    clearPendingQueueNavigationFocus();
  }

  function stabilizedLiveContext(nextContext) {
    if (!PROVIDER.hasOpenMessage()) {
      return nextContext || {};
    }
    const previous = lastLiveContext || {};
    if (!isMeaningfulContext(nextContext)) {
      return previous;
    }
    if (contextsMatch(nextContext, previous)) {
      return {
        ...nextContext,
        selected_at: previous.selected_at || nextContext.selected_at,
      };
    }
    if (shouldPreferPreviousContext(nextContext, previous)) {
      return previous;
    }
    return nextContext;
  }

  function shouldPreferPreviousContext(nextContext, previousContext) {
    if (!isMeaningfulContext(previousContext)) {
      return false;
    }
    if (contextsMatch(nextContext, previousContext)) {
      return contextStrength(nextContext) < contextStrength(previousContext);
    }
    return hasTeachDraftChanges() && contextStrength(nextContext) < contextStrength(previousContext);
  }

  function shouldHoldSelectedContext() {
    const selectedContext = (lastSidebarState && lastSidebarState.selected_context) || {};
    const correctionInProgress = ["change", "teach-preview", "teach-scope"].includes(selectedDecisionMode)
      || ["previewing", "applying", "scope-confirmation"].includes(teachFlowState);
    if ((!correctionInProgress && !affectedReviewOpen) || !isMeaningfulContext(selectedContext)) {
      return false;
    }
    return (
      contextsMatch(lastLiveContext, selectedContext) ||
      contextStrength(lastLiveContext) < contextStrength(selectedContext)
    );
  }

  function hasTeachDraftChanges() {
    return Boolean((teachDraft.targetLabel || "").trim() || (teachDraft.note || "").trim());
  }

  function isMeaningfulContext(context) {
    return Boolean(context && (context.message_id || context.subject));
  }

  function contextStrength(context) {
    if (!context) {
      return 0;
    }
    let strength = 0;
    if (context.message_id) {
      strength += 4;
    }
    if (context.subject) {
      strength += 2;
    }
    if (context.sender) {
      strength += 1;
    }
    return strength;
  }

  function contextsMatch(left, right) {
    if (!left || !right) {
      return false;
    }
    if (left.message_id && right.message_id) {
      return left.message_id === right.message_id;
    }
    const leftSender = normalizedSender(left.sender || "");
    const rightSender = normalizedSender(right.sender || "");
    const leftSubject = normalizedSubject(left.subject || "");
    const rightSubject = normalizedSubject(right.subject || "");
    return Boolean(leftSender && rightSender && leftSubject && rightSubject && leftSender === rightSender && leftSubject === rightSubject);
  }

  function normalizedSender(value) {
    return String(value || "").trim().toLowerCase();
  }

  function normalizedSubject(value) {
    return String(value || "").trim().toLowerCase();
  }

  function normalizeConnectionState(state) {
    const kind = state && state.kind ? state.kind : "helper-unreachable";
    if (kind === "ready") {
      return {
        kind,
        label: state.label || "Ready",
        details: state.details || "Threadwise is connected.",
      };
    }
    if (kind === "wrong-service") {
      return {
        kind,
        label: state.label || "Wrong service on port",
        details: state.details || `Something else is responding at ${LOCAL_ORIGIN}.`,
      };
    }
    if (kind === "health-failed") {
      return {
        kind,
        label: state.label || "Health check failed",
        details: state.details || "Threadwise did not report a ready status.",
      };
    }
    if (kind === "connecting") {
      return {
        kind,
        label: state.label || "Connecting",
        details: state.details || "Checking the local companion.",
      };
    }
    return {
      kind: "helper-unreachable",
      label: state.label || "Helper unreachable",
      details: state.details || "Could not reach the local companion.",
    };
  }

  function connectionStatusCopy() {
    const state = normalizeConnectionState(lastConnectionState);
    const needsAttentionCount = ((lastSidebarState && lastSidebarState.needs_attention_items) || []).length;
    if (document.querySelector("[data-ea-coverage-state]")) {
      const coverage = COVERAGE.model(coverageState);
      return {
        label: coverage.shell,
        background: "transparent",
        foreground: coverage.status === "failed" || coverage.status === "offline" ? "#b42318" : "#60666f",
      };
    }
    if (connectionRetryInFlight) {
      return {
        label: "Checking\u2026",
        background: "transparent",
        foreground: "#60666f",
      };
    }
    if (state.kind !== "ready") {
      if (state.kind === "wrong-service") {
        return {
          label: "Wrong service",
          background: "#fff4dd",
          foreground: "#8a4b00",
        };
      }
      if (state.kind === "health-failed") {
        return {
          label: "Needs setup",
          background: "#fff4dd",
          foreground: "#8a4b00",
        };
      }
      return {
        label: "Offline",
        background: "#f7e2e2",
        foreground: "#8a1f1f",
      };
    }
    if (needsAttentionCount > 0) {
      return {
        label: `Needs attention ${needsAttentionCount}`,
        background: "#fff4dd",
        foreground: "#8a4b00",
      };
    }
    return {
      label: "Ready",
      background: "#d8f3ef",
      foreground: "#0f766e",
    };
  }

  function connectionRemediationCopy(state) {
    if (state.kind === "wrong-service") {
      return [
        "Confirm no other app is using the Threadwise port.",
        "Start the Threadwise startup helper again.",
      ];
    }
    if (state.kind === "health-failed") {
      return [
        "Check the local companion logs.",
        "Restart the personal startup helper.",
      ];
    }
    if (state.kind === "connecting") {
      return ["Waiting for the local companion to answer."];
    }
    return [
      "Open the Threadwise startup helper.",
      "Check again after the helper says Threadwise is running.",
    ];
  }

  function renderError(message, connectionState) {
    lastConnectionState = normalizeConnectionState(connectionState || lastConnectionState);
    lastRecoveryMessage = String(message || lastRecoveryMessage || "Threadwise did not return a response.");
    if (onboardingVisible) {
      renderOnboarding();
      return;
    }
    const statusCopy = connectionStatusCopy();
    const errorTitle = errorTitleForConnection(lastConnectionState);
    const friendlyMessage = recoveryFriendlyMessage(lastConnectionState, lastRecoveryMessage);
    const recoveryKind = lastConnectionState.kind;
    const retryLabel = connectionRetryInFlight ? "Checking\u2026" : "Check again";
    const recoveryStatus = connectionRetryInFlight
      ? "Trying the connection now\u2026"
      : connectionRetryFeedback === "failed"
        ? recoveryCheckedCopy(lastConnectionState)
        : "Threadwise will keep checking automatically.";
    renderStandaloneWorkspace("error", `
      <div
        data-ea-selected-state="error"
        data-ea-recovery-surface
        data-ea-recovery-kind="${escapeHtml(recoveryKind)}"
        data-ea-retry-state="${connectionRetryInFlight ? "checking" : connectionRetryFeedback === "failed" ? "checked" : "idle"}"
        role="${connectionRetryInFlight ? "status" : "alert"}"
        aria-live="polite"
        aria-busy="${connectionRetryInFlight ? "true" : "false"}"
      >
        <div data-ea-recovery-eyebrow>${escapeHtml(connectionRetryInFlight ? "Checking\u2026" : statusCopy.label)}</div>
        <h2 data-ea-recovery-title>${escapeHtml(errorTitle)}</h2>
        <p data-ea-recovery-copy>${escapeHtml(friendlyMessage)}</p>
        <button
          type="button"
          data-ea-action="force-refresh"
          data-ea-recovery-action
          data-tw-primary-action
          ${connectionRetryInFlight ? "disabled" : ""}
          aria-busy="${connectionRetryInFlight ? "true" : "false"}"
        >${escapeHtml(retryLabel)}</button>
        <div data-ea-recovery-status role="status">${escapeHtml(recoveryStatus)}</div>
        <details data-ea-recovery-details>
          <summary>Details</summary>
          <div data-ea-recovery-diagnostic>
            <div><strong>Reason:</strong> ${escapeHtml(recoveryReasonLabel(lastConnectionState))}</div>
            <div><strong>Status:</strong> ${escapeHtml(lastConnectionState.details || "No status detail was returned.")}</div>
            <div><strong>Last response:</strong> ${escapeHtml(lastRecoveryMessage)}</div>
          </div>
        </details>
      </div>
    `);
  }

  function recoveryReasonLabel(state) {
    return {
      "helper-unreachable": "unreachable",
      "wrong-service": "wrong service",
      "health-failed": "health failed",
      connecting: "connecting",
    }[state.kind] || state.kind || "unavailable";
  }

  function recoveryCheckedCopy(state) {
    if (state.kind === "helper-unreachable") {
      return "Still offline \u00b7 checked just now";
    }
    if (state.kind === "connecting") {
      return "Still connecting \u00b7 checked just now";
    }
    return "Still unavailable \u00b7 checked just now";
  }

  function errorTitleForConnection(state) {
    if (state.kind === "wrong-service") {
      return "Threadwise can't connect.";
    }
    if (state.kind === "health-failed") {
      return "Threadwise isn't ready yet.";
    }
    if (state.kind === "connecting") {
      return "Connecting to Threadwise\u2026";
    }
    return "Threadwise isn't available.";
  }

  function recoveryFriendlyMessage(state, message) {
    const normalized = String(message || "").toLowerCase();
    if (state.kind === "wrong-service") {
      return "Another app is using the connection Threadwise needs. Gmail is unchanged.";
    }
    if (state.kind === "health-failed") {
      return "Threadwise responded, but it is not ready to review this email. Gmail is unchanged.";
    }
    if (state.kind === "connecting") {
      return "This usually takes a few seconds. You can keep using Gmail while Threadwise connects.";
    }
    if (normalized.includes("aborterror") || normalized.includes("signal is aborted")) {
      return "The last check was interrupted. Threadwise will try again automatically.";
    }
    return "Your review is safe. You can keep using Gmail while Threadwise reconnects.";
  }

  function friendlyErrorMessage(message) {
    const normalized = String(message || "").toLowerCase();
    if (normalized.includes("llm review is not configured")) {
      return "LLM review is unavailable because the Threadwise companion has no OpenAI key configured.";
    }
    if (normalized.includes("llm review was unavailable")) {
      return "LLM review could not complete. Nothing was changed; you can retry without losing your note.";
    }
    if (normalized.includes("aborterror") || normalized.includes("signal is aborted")) {
      return `The last connection attempt was interrupted. This usually clears after checking again or reopening ${activeProviderName()}.`;
    }
    if (normalized.includes("failed to fetch") || normalized.includes("could not reach")) {
      return `The Threadwise extension cannot reach the local companion from ${activeProviderName()} yet.`;
    }
    return "Threadwise could not load the local companion state.";
  }

  function feedbackContext() {
    const sidebarState = lastSidebarState || {};
    return {
      surface: "gmail_companion_extension",
      page_url: window.location.href,
      connection_kind: normalizeConnectionState(lastConnectionState).kind,
      active_summary_filter: activeSummaryFilter,
      selected_context: sidebarState.selected_context || lastLiveContext || {},
      selected_email: sidebarState.selected_email || {},
    };
  }

  function renderFeedbackPanel() {
    const root = document.getElementById(ROOT_ID);
    const panel = document.getElementById("ea-feedback-panel");
    const openButton = document.getElementById("ea-feedback-open");
    if (!panel || !openButton) {
      return;
    }
    if (root) {
      root.style.width = feedbackOpen ? PANEL_WIDTH : (minimized ? PANEL_WIDTH_MINIMIZED : PANEL_WIDTH);
    }
    openButton.textContent = feedbackOpen ? "Close note" : (feedbackResult ? "Note saved" : "Note");
    panel.style.display = feedbackOpen ? "block" : "none";
    if (!feedbackOpen) {
      return;
    }
    const context = feedbackContext();
    const selectedContext = context.selected_context || {};
    const contextLine = selectedContext.subject || selectedContext.sender
      ? `${selectedContext.subject || "(no subject)"} - ${selectedContext.sender || "(unknown sender)"}`
      : "Current Threadwise view";
    setHtml(panel, `
      <div style="display:grid;gap:8px;">
        <textarea id="ea-feedback-note" rows="4" placeholder="What should Threadwise do better here?" style="box-sizing:border-box;width:100%;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:#fffdf7;color:#1f1a14;font:inherit;resize:vertical;box-shadow:2px 2px 0 rgba(36,24,18,.18);">${escapeHtml(feedbackDraft)}</textarea>
        <div style="color:#6b6255;font-size:0.78rem;line-height:1.35;overflow-wrap:anywhere;">Context: ${escapeHtml(contextLine)}</div>
        ${feedbackResult ? `<div style="border-radius:11px;background:#d8f3ef;color:#0f766e;padding:9px 10px;font-size:0.84rem;line-height:1.35;">${escapeHtml(feedbackResult)}</div>` : ""}
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button type="button" data-ea-action="submit-feedback" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Save note</button>
          <button type="button" data-ea-action="clear-feedback" style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Clear</button>
        </div>
      </div>
    `);
  }

  function submitFounderFeedback() {
    feedbackDraft = (document.getElementById("ea-feedback-note")?.value || feedbackDraft || "").trim();
    if (!feedbackDraft) {
      feedbackResult = "Write a note first.";
      renderFeedbackPanel();
      return;
    }
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/founder-feedback",
      method: "POST",
      body: {
        source: "gmail_companion_extension",
        note: feedbackDraft,
        context: feedbackContext(),
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        feedbackResult = chrome.runtime.lastError.message || "Could not save note.";
      } else if (!response || !response.ok) {
        feedbackResult = (response && (response.payload?.error || response.error)) || "Could not save note.";
      } else {
        feedbackDraft = "";
        feedbackResult = "Saved locally for review.";
        feedbackOpen = false;
      }
      renderFeedbackPanel();
    });
  }

  function selectedMessageIdentity(sidebarState, selected) {
    const context = (sidebarState && sidebarState.selected_context) || lastLiveContext || {};
    const provider = selected?.provider || context.provider || "gmail";
    const messageId = selected?.message_id || context.message_id || "";
    if (messageId) {
      return `${provider}:${messageId}`;
    }
    const subject = selected?.subject || context.subject || "";
    const sender = selected?.sender || context.sender || "";
    if (subject && sender) {
      return `${provider}:${normalizedSender(sender)}:${normalizedSubject(subject)}`;
    }
    return selected?.status === "idle" || !selected ? "home" : "";
  }

  function invalidateContextActions() {
    disarmContextEscapeRetreat();
    contextActionsOpen = false;
    contextActionsActiveIndex = 0;
    contextActionsGeneration += 1;
    const menu = document.getElementById("ea-context-menu");
    if (menu?.parentNode) {
      menu.parentNode.removeChild(menu);
    }
    const host = document.getElementById("ea-context-actions");
    if (!host) {
      return;
    }
    const trigger = host.querySelector("[data-ea-context-trigger]");
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
    }
  }

  function resetPerEmailInteraction({ preserveProgressionStatus = false } = {}) {
    invalidateContextActions();
    teachPreviewRequestId += 1;
    teachPreview = null;
    previousTeachPreview = null;
    teachResult = null;
    teachFlowState = "teaching";
    inboxApplyConfirmOpen = false;
    teachOutcome = null;
    teachWriteThrough = null;
    detailsExpanded = false;
    autoHandledChangeOpen = false;
    selectedDecisionMode = "review";
    selectedDecisionConflict = "";
    futureLearningError = "";
    currentApplyError = "";
    handledAdvanceError = "";
    activeTeachApplyMode = "";
    recordedSuggestionDecisions = { approve: false, edit: false };
    affectedReviewOpen = false;
    selectedTeachScope = "current-only";
    explanationFocusPending = false;
    teachDraft = { targetLabel: "", note: "" };
    if (!preserveProgressionStatus) {
      clearOptimisticDecisionStatus({ preserveHandledFlight: Boolean(handledProgressionFlight) });
    }
  }

  function openThreadwiseHome(event) {
    if (event) {
      event.preventDefault();
    }
    onboardingVisible = false;
    onboardingActionInFlight = false;
    onboardingMessage = "";
    minimized = false;
    forcedHome = true;
    forcedHomeLiveContext = { ...selectedContext() };
    if (manualPreviewContext) {
      forcedHomeLiveContext = { ...manualPreviewContext };
    }
    manualPreviewContext = null;
    manualPreviewOriginContext = null;
    resetQueueState();
    gmailCheckResult = null;
    clearProgressionCheck();
    resetPerEmailInteraction();
    previousPayload = "";
    if (lastHarnessState) {
      renderState(lastHarnessState);
    }
    refreshSelection(true);
    renderMinimized();
  }

  function handleBrandToggle(event) {
    if (!minimized) {
      openThreadwiseHome(event);
      return;
    }
    if (event) {
      event.preventDefault();
    }
    minimized = false;
    forcedHome = false;
    forcedHomeLiveContext = null;
    lastLiveContext = stabilizedLiveContext(selectedContext());
    if (isMeaningfulContext(lastLiveContext)) {
      resetQueueState();
      manualPreviewContext = null;
      manualPreviewOriginContext = null;
      previousPayload = "";
      refreshSelection(true);
    } else if (lastHarnessState || lastSidebarState) {
      renderState(lastHarnessState || lastSidebarState);
    }
    renderMinimized();
    openOnboardingAfterExplicitOpen();
  }

  function hasFailedOrPendingHandling(selected) {
    const details = (selected && selected.details) || {};
    const statuses = [details.write_status, details.inbox_status]
      .map((value) => String(value || "").toLowerCase())
      .filter(Boolean);
    return statuses.some((status) => /failed|error|pending|retry|partial/.test(status));
  }

  function isHandledSelection(selected) {
    return ["auto-handled", "kept-visible", "auto-labeled"].includes(String(selected?.status || ""));
  }

  function isCurrentEmailResult() {
    return teachFlowState === "result" && teachOutcome?.scope === "current-email";
  }

  function isBroaderTeachResult() {
    return teachFlowState === "result"
      && teachResult
      && ["included-existing", "matching-existing", "current-email-and-future-rule"].includes(teachOutcome?.scope || "");
  }

  function currentEmailResultIsPartial() {
    if (!isCurrentEmailResult()) {
      return false;
    }
    return !teachOutcome?.current_email_written_to_gmail
      || Number(teachOutcome?.gmail_label_write_failed || 0) > 0
      || Number(teachWriteThrough?.label_write_failed || 0) > 0
      || Number(teachWriteThrough?.inbox_remove_failed || 0) > 0;
  }

  function resolveWorkspaceMode(sidebarState, selected) {
    if (forcedHome) {
      return "home";
    }
    if (!selected || (selected.status === "idle" && !selectedMessageIdentity(sidebarState, selected))) {
      return "home";
    }
    if (!selected.found) {
      return selected.status === "idle" ? "home" : "blocked";
    }
    if (selectedUnderstandingActive(selected)) {
      return "understanding";
    }
    if (selectedDecisionMode === "future-learning") {
      if (teachFlowState === "applying") {
        return "future-learning-applying";
      }
      if (teachFlowState === "result" && teachOutcome?.scope === "future-rule") {
        return "future-learning-receipt";
      }
      return "future-learning";
    }
    if (currentApplyError) {
      return queuePreviewActive && manualPreviewContext ? "review" : "current-apply-error";
    }
    if (isCurrentEmailResult()) {
      return currentEmailResultIsPartial() ? "partial-receipt" : "current-receipt";
    }
    if (isBroaderTeachResult()) {
      return "teach-result-receipt";
    }
    if (teachFlowState === "applying" && selectedDecisionMode === "review" && optimisticDecision?.flightActive) {
      return "review";
    }
    if (teachFlowState === "applying") {
      return "applying";
    }
    if (selectedDecisionMode === "teach-preview" && (teachPreview || teachResult || teachFlowState === "previewing")) {
      return "teach-preview";
    }
    if (selectedDecisionMode === "teach-scope" && teachPreview && teachFlowState === "scope-confirmation") {
      return "teach-scope";
    }
    if (selectedDecisionMode === "change" || autoHandledChangeOpen) {
      return "change";
    }
    if (selectedDecisionMode === "preview") {
      return "preview";
    }
    if (selected.status === "write-unconfirmed") {
      return "review";
    }
    if (isHandledSelection(selected)) {
      return hasFailedOrPendingHandling(selected) ? "blocked" : "handled-receipt";
    }
    return "review";
  }

  function renderWorkspaceShell(mode) {
    const workspace = document.getElementById("ea-workspace");
    if (!workspace) {
      return null;
    }

    workspace.dataset.eaWorkspaceMode = mode;
    const content = document.getElementById("ea-content");
    if (content) {
      content.dataset.eaWorkspaceMode = mode;
    }
    if (mode !== "home") {
      setHtml(workspace, `
        <section data-ea-workspace-body="${escapeHtml(mode)}" style="border:3px solid #241812;border-radius:18px;padding:16px;background:#fffdf7;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
          <div id="ea-selected-email"></div>
          <div id="ea-selected-email-secondary"></div>
        </section>
      `);
    } else {
      setHtml(workspace, `
        <section data-ea-workspace-body="home" style="border:3px solid #241812;border-radius:18px;padding:16px;background:#e9efe2;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
          <div style="color:#6b6255;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.14em;font-weight:820;">Home</div>
          <div id="ea-daily-summary"></div>
        </section>
      `);
    }

    return {
      selectedEmailNode: document.getElementById("ea-selected-email") || document.createElement("div"),
      selectedEmailSecondaryNode: document.getElementById("ea-selected-email-secondary") || document.createElement("div"),
      teachPanelNode: document.getElementById("ea-teach-panel"),
      dailySummaryNode: document.getElementById("ea-daily-summary"),
    };
  }

  function renderStandaloneWorkspace(mode, html) {
    invalidateContextActions();
    const nodes = renderWorkspaceShell(mode);
    if (!nodes) {
      return;
    }
    setHtml(nodes.selectedEmailNode, html);
    setHtml(nodes.selectedEmailSecondaryNode, "");
    renderMinimized();
  }

  function onboardingTarget() {
    if (lastConnectionState.kind !== "ready" || !lastSidebarState) {
      return { kind: "not-ready", provider: ACTIVE_PROVIDER };
    }
    return ONBOARDING.resolveTarget({
      provider: ACTIVE_PROVIDER,
      selectedEmail: lastSidebarState.selected_email,
      needsAttentionItems: lastHarnessState?.needs_attention_items || [],
    });
  }

  function onboardingReadyForHandoff() {
    return lastConnectionState.kind === "ready" && Boolean(lastSidebarState);
  }

  function onboardingTargetCopy(target) {
    if (target.kind === "selected-email") {
      return `Your selected ${activeProviderName()} email is ready to review.`;
    }
    if (target.kind === "needs-attention") {
      return `The next ${activeProviderName()} email needing attention is ready.`;
    }
    if (target.kind === "home") {
      return `No reviewable email is ready, so Threadwise will open Home.`;
    }
    return "Threadwise is still checking the current inbox state.";
  }

  function onboardingConnectionCopy() {
    if (lastConnectionState.kind === "ready" && lastSidebarState) {
      return `Using ${activeProviderName()} from this tab. No provider choice is needed.`;
    }
    if (lastConnectionState.kind === "connecting") {
      return "Threadwise is still connecting. Check again when the local companion is running.";
    }
    return `${lastConnectionState.label}: ${lastConnectionState.details}`;
  }

  function focusOnboardingAction() {
    window.setTimeout(() => {
      if (!onboardingVisible || minimized) {
        return;
      }
      const action = document.querySelector(
        `[data-ea-action="onboarding-continue"], [data-ea-action="onboarding-retry"]`,
      );
      if (!action) {
        return;
      }
      action.focus({ preventScroll: true });
    }, 0);
  }

  function renderOnboarding() {
    if (!onboardingVisible) {
      return;
    }
    invalidateContextActions();
    const nodes = renderWorkspaceShell("onboarding");
    if (!nodes) {
      return;
    }
    const ready = onboardingReadyForHandoff();
    const target = onboardingTarget();
    const primaryAction = ready ? "onboarding-continue" : "onboarding-retry";
    const primaryLabel = ready
      ? target.kind === "selected-email"
        ? "Review this email"
        : target.kind === "needs-attention"
          ? "Review next email"
          : "Open Home"
      : "Check again";
    const actionBusy = onboardingActionInFlight;
    const remediation = ready ? [] : connectionRemediationCopy(lastConnectionState);
    setHtml(nodes.selectedEmailNode, `
      <section data-ea-onboarding role="region" aria-labelledby="ea-onboarding-title" style="display:grid;gap:16px;">
        <div data-ea-onboarding-identity style="display:flex;align-items:center;gap:10px;min-width:0;">
          <img src="${BRAND_ICON_URL}" alt="Threadwise logo" data-ea-onboarding-logo="true" style="width:38px;height:38px;display:block;flex:0 0 auto;border:1px solid rgba(36,24,18,.28);border-radius:10px;background:#fff8df;object-fit:cover;">
          <div style="min-width:0;">
            <div style="font-size:0.82rem;color:#6b6255;line-height:1.3;">Threadwise</div>
            <div style="font-size:0.92rem;font-weight:760;line-height:1.3;overflow-wrap:anywhere;">${escapeHtml(activeProviderName())} companion</div>
          </div>
        </div>
        <div>
          <h2 id="ea-onboarding-title" data-ea-onboarding-title style="margin:0;font-size:1.42rem;font-weight:840;letter-spacing:-0.035em;line-height:1.08;">Make the next inbox decision clearer.</h2>
          <p data-ea-onboarding-description style="margin:10px 0 0;color:#3f352e;line-height:1.5;">Threadwise classifies and labels email, explains why, and lets you correct it. Broader changes are previewed before anything else is updated.</p>
          <p data-ea-onboarding-boundary style="margin:10px 0 0;color:#3f352e;line-height:1.5;font-weight:760;">It never writes or sends replies.</p>
        </div>
        <div data-ea-onboarding-status role="status" aria-live="polite" style="border-top:1px solid rgba(36,24,18,.24);border-bottom:1px solid rgba(36,24,18,.24);padding:12px 0;color:${ready ? "#0f766e" : "#8a4b00"};line-height:1.45;">
          <div style="font-weight:760;">${escapeHtml(onboardingConnectionCopy())}</div>
          <div style="margin-top:6px;color:#3f352e;">${escapeHtml(onboardingTargetCopy(target))}</div>
          ${remediation.length ? `<ul style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${remediation.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
        </div>
        ${onboardingMessage ? `<div data-ea-onboarding-error role="alert" style="border-radius:10px;background:#fde8e6;padding:10px 12px;color:#7f1d1d;line-height:1.45;">${escapeHtml(onboardingMessage)}</div>` : ""}
        <div data-ea-onboarding-actions style="display:grid;gap:10px;">
          <button type="button" data-ea-action="${primaryAction}" data-tw-primary-action ${actionBusy ? "disabled" : ""} style="min-height:44px;border:2px solid #241812;background:${actionBusy ? "#c7d8cc" : "#2eb67d"};color:#241812;border-radius:11px;padding:9px 12px;cursor:${actionBusy ? "wait" : "pointer"};font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">${actionBusy ? "Saving your choice..." : escapeHtml(primaryLabel)}</button>
          <button type="button" data-ea-action="onboarding-skip" data-ea-onboarding-skip ${actionBusy ? "disabled" : ""} style="justify-self:start;border:0;background:transparent;color:#5d5342;padding:7px 2px;cursor:${actionBusy ? "wait" : "pointer"};font:inherit;font-weight:760;text-decoration:underline;text-underline-offset:3px;">Skip intro</button>
        </div>
      </section>
    `);
    setHtml(nodes.selectedEmailSecondaryNode, "");
    renderMinimized();
    focusOnboardingAction();
  }

  async function openOnboardingAfterExplicitOpen() {
    const state = await onboardingReady;
    if (!(["unseen", "active"].includes(state.status))) {
      return;
    }
    onboardingVisible = true;
    onboardingMessage = "";
    try {
      onboardingState = await ONBOARDING.markActive();
    } catch (error) {
      onboardingState = { version: ONBOARDING.VERSION, status: "active" };
      onboardingMessage = `Threadwise could not save onboarding state yet: ${error.message || error}`;
    }
    renderOnboarding();
    ANALYTICS?.showOnboarding?.(ONBOARDING.VERSION, onboardingTarget().kind);
  }

  function handoffFromOnboarding(target) {
    onboardingVisible = false;
    onboardingActionInFlight = false;
    onboardingMessage = "";
    if (target.kind === "selected-email") {
      forcedHome = false;
      forcedHomeLiveContext = null;
      manualPreviewContext = null;
      manualPreviewOriginContext = null;
      previousPayload = "";
      refreshSelection(true);
      renderMinimized();
      return;
    }
    if (target.kind === "needs-attention") {
      openItemPreview(target.item);
      renderMinimized();
      return;
    }
    openThreadwiseHome();
  }

  async function finishOnboarding(status) {
    if (onboardingActionInFlight) {
      return;
    }
    const target = onboardingTarget();
    if (status === "completed" && !onboardingReadyForHandoff()) {
      previousPayload = "";
      refreshSelection(true);
      return;
    }
    onboardingActionInFlight = true;
    renderOnboarding();
    try {
      onboardingState = status === "completed"
        ? await ONBOARDING.markCompleted()
        : await ONBOARDING.markDismissed();
    } catch (error) {
      onboardingActionInFlight = false;
      onboardingMessage = `Threadwise could not save that choice: ${error.message || error}`;
      renderOnboarding();
      return;
    }
    if (status === "completed") {
      ANALYTICS?.completeOnboarding?.(ONBOARDING.VERSION, target.kind);
    } else {
      ANALYTICS?.dismissOnboarding?.(ONBOARDING.VERSION, target.kind);
    }
    handoffFromOnboarding(target);
  }

  function coverageSummary(model) {
    if (model.status === "unknown") return "Threadwise handled the email you opened. Check your inbox before judging the wider review queue.";
    if (model.status === "checking") return `Reading current ${activeProviderName()} Inbox membership. No labels, archive actions, or other provider changes can run.`;
    if (model.status === "queue-ready") return `Threadwise checked ${model.checked_count} current Inbox message${model.checked_count === 1 ? "" : "s"}. Only the messages needing a decision entered this queue.`;
    if (model.status === "verified-clear") return `Threadwise freshly checked ${model.checked_count} current Inbox message${model.checked_count === 1 ? "" : "s"}. None need your judgment.`;
    if (model.status === "partial" && model.requires_sync_count) return `${model.requires_sync_count} current Inbox message${model.requires_sync_count === 1 ? " has" : "s have"} not completed a Threadwise classification run. Update the inbox to classify and label ${model.requires_sync_count === 1 ? "it" : "them"}.`;
    if (model.status === "partial") return `Threadwise checked ${model.checked_count} of ${model.candidate_count || model.checked_count} messages in the stated scope. This is not a clear result.`;
    if (model.status === "stale") return "Your inbox may have changed since the last check. The previous queue result is no longer authoritative.";
    if (model.status === "offline") return "The handled email is saved, but Threadwise cannot verify the wider queue while the companion is offline.";
    return model.error || "Threadwise could not finish the read-only inbox check. No queue-clear claim is available.";
  }

  function coverageActionKind(model) {
    if (model.status === "queue-ready") return "coverage-review";
    if (model.status === "verified-clear") return "coverage-back";
    if (model.status === "partial" && model.requires_sync_count) return "coverage-sync";
    return "coverage-check";
  }

  function renderCoverageHtml({ includeHandledReceipt = false, handledMeta = "", showChange = false } = {}) {
    const model = COVERAGE.model(coverageState);
    const partialChecked = model.status === "partial" && model.candidate_count
      ? `${model.checked_count} of ${model.candidate_count}`
      : model.facts.checked;
    const indicator = model.indicator === "indeterminate"
      ? '<div data-ea-coverage-indicator="indeterminate" role="progressbar" aria-label="Checking inbox coverage" style="height:3px;overflow:hidden;border-radius:999px;background:#ecebff;"><div style="width:42%;height:100%;border-radius:999px;background:#635bff;animation:ea-coverage-slide 1.1s ease-in-out infinite;"></div></div>'
      : model.indicator === "determinate"
        ? `<div data-ea-coverage-indicator="determinate" role="progressbar" aria-label="Inbox coverage checked" aria-valuemin="0" aria-valuemax="${Math.max(1, model.candidate_count)}" aria-valuenow="${model.checked_count}" style="height:3px;overflow:hidden;border-radius:999px;background:#ecebff;"><div style="width:${Math.min(100, Math.round((model.checked_count / Math.max(1, model.candidate_count)) * 100))}%;height:100%;border-radius:999px;background:#635bff;"></div></div>`
        : "";
    const nextItem = model.review_items[0] || null;
    const nextHtml = model.status === "queue-ready" && nextItem
      ? `<div data-ea-coverage-next style="border-top:1px solid #e2e5e9;padding-top:10px;min-width:0;"><div style="font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:#7b8088;font-weight:760;">First up</div><div style="margin-top:4px;font-size:.86rem;font-weight:760;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(nextItem.subject || "(no subject)")}</div><div style="margin-top:2px;color:#6b6255;font-size:.75rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(nextItem.sender || "(unknown sender)")}</div></div>`
      : "";
    const secondaryAction = model.secondary
      ? `<button type="button" data-ea-action="${model.secondary.startsWith("Review") ? "coverage-review" : model.secondary === "Details" ? "coverage-details" : "coverage-check"}" style="border:0;background:transparent;color:#5f5a78;padding:7px 2px;cursor:pointer;font:inherit;font-size:.78rem;font-weight:720;">${escapeHtml(model.secondary)}</button>`
      : "";
    const details = coverageDetailsOpen
      ? `<div data-ea-coverage-details style="border-top:1px solid #e2e5e9;padding-top:9px;color:#6b6255;font-size:.73rem;line-height:1.45;"><div>Coverage: ${escapeHtml(model.scope)}</div><div>Queue: ${model.status === "verified-clear" ? "Freshly verified" : model.status === "queue-ready" ? "Freshly built" : "Not verified clear"}</div><div>${model.requires_sync_count ? "Update inbox will classify and apply Threadwise labels." : "Provider changes: None · read-only check"}</div></div>`
      : "";
    return `
      <section data-ea-coverage-state="${escapeHtml(model.status)}" aria-live="polite" style="display:grid;gap:10px;color:#1f2328;">
        ${includeHandledReceipt ? `<div data-ea-handled-coverage-receipt><div style="font-size:1.02rem;color:#1f2328;font-weight:820;">This email is handled</div><div style="margin-top:3px;color:#60666f;font-size:.76rem;">${escapeHtml(handledMeta || "Handled · kept in Inbox")}</div>${showChange ? '<button type="button" data-ea-action="edit-current-apply" style="margin-top:5px;border:0;background:transparent;color:#5f5a78;padding:3px 0;cursor:pointer;font:inherit;font-size:.73rem;font-weight:720;">Change</button>' : ""}</div>` : ""}
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;"><span data-ea-coverage-shell style="color:#6b6255;font-size:.72rem;font-weight:760;">${escapeHtml(model.shell)}</span><button type="button" data-ea-action="coverage-details" aria-label="Coverage details" style="border:0;background:transparent;color:#7b8088;padding:2px 4px;cursor:pointer;font:inherit;font-weight:800;">···</button></div>
        ${indicator}
        <div><h2 data-ea-coverage-heading style="margin:0;font-size:1.08rem;line-height:1.2;font-weight:820;letter-spacing:-.01em;">${escapeHtml(model.title)}</h2><div style="margin-top:5px;color:#60666f;font-size:.78rem;line-height:1.42;">${escapeHtml(coverageSummary(model))}</div></div>
        <div data-ea-coverage-facts style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid #e2e5e9;border-radius:9px;overflow:hidden;background:#f8f9fb;">
          <div style="padding:8px 7px;"><strong style="display:block;font-size:.86rem;font-variant-numeric:tabular-nums;">${escapeHtml(partialChecked)}</strong><span style="color:#7b8088;font-size:.65rem;">checked</span></div>
          <div style="padding:8px 7px;border-left:1px solid #e2e5e9;"><strong style="display:block;font-size:.86rem;font-variant-numeric:tabular-nums;">${escapeHtml(model.facts.review)}</strong><span style="color:#7b8088;font-size:.65rem;">need review</span></div>
          <div style="padding:8px 7px;border-left:1px solid #e2e5e9;"><strong style="display:block;font-size:.76rem;">${escapeHtml(model.facts.freshness)}</strong><span style="color:#7b8088;font-size:.65rem;">freshness</span></div>
        </div>
        ${nextHtml}
        <div data-ea-coverage-truth-note style="color:#60666f;font-size:.72rem;line-height:1.4;">${escapeHtml(model.truthNote)}</div>
        <div style="display:grid;gap:5px;"><button type="button" data-ea-action="${coverageActionKind(model)}" ${model.disabled ? "disabled" : ""} data-tw-primary-action style="width:100%;min-height:39px;border:0;border-radius:8px;background:${model.disabled ? "#b9b5ee" : "#635bff"};color:#fff;padding:8px 12px;cursor:${model.disabled ? "wait" : "pointer"};font:inherit;font-size:.8rem;font-weight:800;">${escapeHtml(model.action)}</button>${secondaryAction}</div>
        ${details}
      </section>`;
  }

  function renderState(state) {
    const preservedScroll = captureContextScroll();
    invalidateContextActions();
    ensureQueueProvider();
    lastHarnessState = normalizeHarnessState(state);
    lastSidebarState = lastHarnessState.sidebar_state;
    updateOptimisticDecisionLifecycle(lastSidebarState);
    const selected = lastSidebarState.selected_email || null;
    const selectedMessageId = selectedMessageIdentity(lastSidebarState, selected);
    if (selectedMessageId !== lastSelectedMessageId) {
      resetPerEmailInteraction({ preserveProgressionStatus: Boolean(optimisticDecision?.localAccepted) });
      lastSelectedMessageId = selectedMessageId;
    }
    if (onboardingVisible) {
      renderOnboarding();
      restoreContextScroll(preservedScroll);
      restorePendingContextActionFocus();
      return;
    }
    const workspaceMode = resolveWorkspaceMode(lastSidebarState, selected);
    const workspaceNodes = renderWorkspaceShell(workspaceMode);
    if (!workspaceNodes) {
      restoreContextScroll(preservedScroll);
      restorePendingContextActionFocus();
      return;
    }
    const {
      selectedEmailNode,
      selectedEmailSecondaryNode,
      teachPanelNode,
      dailySummaryNode,
    } = workspaceNodes;

    const summary = lastSidebarState.daily_summary || {};
    if (selected?.found && !manualPreviewContext) {
      ANALYTICS?.startEmailReview(
        selected.message_id || "",
        "provider_selected_email",
        Number(summary.needs_attention_count || 0),
      );
    }
    const activityHtml = renderRecentActivityHtml(recentActivityItems(lastSidebarState));
    const showingQueuePreview = Boolean(manualPreviewContext && queuePreviewActive);
    const stepCopy = nextStepCopy(selected, showingQueuePreview);
    const understandingActive = selectedUnderstandingActive(selected);
    scheduleUnderstandingRefresh(understandingActive);
    if (!(selected && selected.found)) {
      previousTeachPreview = null;
      detailsExpanded = false;
    }

    if (workspaceMode === "understanding") {
      const liveSubject = (selected && selected.subject) || (lastLiveContext && lastLiveContext.subject) || "(no subject)";
      const liveSender = (selected && selected.sender) || (lastLiveContext && lastLiveContext.sender) || "(unknown sender)";
      setHtml(selectedEmailNode, `
        <div style="margin-top:7px;font-size:1.45rem;font-weight:840;letter-spacing:-0.015em;line-height:1.04;">${escapeHtml(liveSubject)}</div>
        <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(liveSender)}</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#fff4dd;color:#8a4b00;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">${escapeHtml((selected && selected.understanding_label) || "Understanding")}</span>
        </div>
        <div style="margin-top:14px;border-radius:14px;background:#fff8eb;padding:12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Reading progress</div>
          <div style="margin-top:8px;">${escapeHtml(selectedUnderstandingMessage(selected))}</div>
          <div style="margin-top:6px;color:#6b6255;">Threadwise is updating the current email view before it shows the full judgment.</div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, `
        <div style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border-radius:14px;background:#fff8eb;padding:12px;color:#8a4b00;line-height:1.45;">
          <div style="font-weight:700;">${escapeHtml(selectedUnderstandingMessage(selected))}</div>
          <div style="margin-top:8px;">Threadwise is still understanding this email. Teaching controls will appear when the email is ready.</div>
        </div>
      `);
      setHtml(dailySummaryNode, `
        <div style="margin-top:10px;color:#6b6255;line-height:1.45;">Latest run snapshot</div>
        <div style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;color:#1f1a14;line-height:1.45;">${escapeHtml(selectedUnderstandingMessage(selected))}</div>
        ${activityHtml}
      `);
    } else if (workspaceMode === "home") {
      setHtml(dailySummaryNode, "");
    } else if (workspaceMode === "blocked") {
      const hasSnapshotMiss = selected && selected.status === "not-in-snapshot";
      const handlingFailed = selected?.found && hasFailedOrPendingHandling(selected);
      const title = hasSnapshotMiss
        ? "Threadwise has not synced this email yet."
        : handlingFailed
          ? "Threadwise could not finish handling this email."
          : "Threadwise needs a fresh check before it can continue.";
      const detail = hasSnapshotMiss
        ? (selected.reason || `Run a ${activeProviderName()} sync to classify this email with the latest rules.`)
        : handlingFailed
          ? "The label or Inbox step is still pending or failed. Threadwise will not describe it as handled until the recorded status is complete."
          : (selected?.reason || "Refresh the current state and try again.");
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="blocked" role="status" style="display:grid;gap:12px;">
          <h2 style="margin:0;font-size:1.3rem;line-height:1.2;">${escapeHtml(title)}</h2>
          <div style="border-radius:14px;background:#fff4dd;padding:12px;color:#1f1a14;line-height:1.45;">${escapeHtml(detail)}</div>
          <button type="button" data-ea-action="${hasSnapshotMiss && PROVIDER.canRunManualSync ? "run-provider-sync" : "force-refresh"}" ${gmailCheckPending ? "disabled" : ""} data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:${gmailCheckPending ? "#c7d8cc" : "#ffc64a"};color:#241812;border-radius:11px;padding:9px 12px;cursor:${gmailCheckPending ? "wait" : "pointer"};font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">${gmailCheckPending ? `Running ${activeProviderName()} sync...` : hasSnapshotMiss && PROVIDER.canRunManualSync ? `Run ${activeProviderName()} sync` : "Check again"}</button>
          ${gmailCheckResult ? renderGmailCheckResultHtml(gmailCheckResult) : ""}
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
    } else if (!selected || !selected.found) {
      const hasSnapshotMiss = selected && selected.status === "not-in-snapshot";
      const title = hasSnapshotMiss
        ? "Threadwise has not synced this email yet."
        : "Open an email to inspect or teach Threadwise.";
      const reason = hasSnapshotMiss && selected.reason
        ? `<div style="margin-top:12px;border-radius:14px;background:#fff4dd;padding:12px;color:#8a4b00;line-height:1.45;">${escapeHtml(selected.reason)}</div>`
        : "";
      const relatedItems = relatedSummaryItemsForContext(lastLiveContext).slice(0, 4);
      const primaryRelatedItem = relatedItems[0] || null;
      const relatedHtml = relatedItems.length
        ? `
          <div style="margin-top:14px;border-top:1px solid #e5dccb;padding-top:14px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Closest synced emails</div>
            <div style="margin-top:8px;color:#6b6255;line-height:1.45;">These are the best local matches the agent can explain right now.</div>
            <div style="display:grid;gap:8px;margin-top:10px;">${renderSummaryItemCards(relatedItems)}</div>
          </div>
        `
        : "";
      const fallbackItems = summaryItemsForFilter("needs_attention_items").slice(0, 4);
      const primaryFallbackItem = fallbackItems[0] || null;
      const fallbackHtml = fallbackItems.length
        ? `
          <div style="margin-top:14px;border-top:1px solid #e5dccb;padding-top:14px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Current Queue</div>
            <div style="display:grid;gap:8px;margin-top:10px;">${renderSummaryItemCards(fallbackItems)}</div>
          </div>
        `
        : "";
      const liveEmailCard = hasSnapshotMiss && lastLiveContext && (lastLiveContext.subject || lastLiveContext.sender)
        ? `
          <div style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Viewing in ${escapeHtml(activeProviderName())} now</div>
            <div style="margin-top:8px;font-weight:700;line-height:1.35;">${escapeHtml(lastLiveContext.subject || "(no subject)")}</div>
            <div style="margin-top:6px;color:#6b6255;line-height:1.45;overflow-wrap:anywhere;">${escapeHtml(lastLiveContext.sender || "(unknown sender)")}</div>
          </div>
        `
        : "";
      setHtml(selectedEmailNode, `
        <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${title}</div>
        ${reason}
        ${liveEmailCard}
        <div style="margin-top:12px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(stepCopy.title)}</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(stepCopy.body)}</div>
        </div>
        <div style="margin-top:12px;color:#6b6255;line-height:1.45;">Threadwise can explain emails it has already synced. Preview a synced match below, or refresh the provider sync to update what Threadwise knows.</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-action="${PROVIDER.canRunManualSync ? "run-provider-sync" : "force-refresh"}" ${gmailCheckPending ? "disabled" : ""} style="border:2px solid #241812;background:${gmailCheckPending ? "#c7d8cc" : "#ffc64a"};color:#241812;border-radius:11px;padding:9px 12px;cursor:${gmailCheckPending ? "wait" : "pointer"};font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">${gmailCheckPending ? `Running ${activeProviderName()} sync...` : PROVIDER.canRunManualSync ? `Run ${activeProviderName()} sync now` : "Check again"}</button>
          ${
            primaryRelatedItem
              ? `<button type="button" data-ea-related-item="${escapeHtml(primaryRelatedItem.message_id || "")}" style="border:0;background:#0f766e;color:#fff;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Preview closest synced match</button>`
              : ""
          }
          ${
            primaryFallbackItem
              ? '<button type="button" data-ea-action="open-needs-attention" style="border:0;background:#ebe4d7;color:#1f1a14;border-radius:999px;padding:9px 12px;cursor:pointer;font:inherit;">Open needs-attention queue</button>'
              : ""
          }
        </div>
        ${relatedHtml}
        ${fallbackHtml}
      `);
      const teachPanelHtml = teachFlowState === "result" && teachResult && !String(teachResult.kind || "").endsWith("-error")
        ? renderTeachReceiptHtml(teachResult.message || "", teachOutcome, ((lastSidebarState || {}).ui_state || {}).async_follow_up)
        : teachResult
          ? renderTeachResultHtml(teachResult)
          : gmailCheckResult
            ? renderGmailCheckResultHtml(gmailCheckResult)
            : `<div style="color:#6b6255;line-height:1.45;">Select a synced email to preview or teach a correction.</div>`;
      setHtml(teachPanelNode, teachPanelHtml);
      setHtml(selectedEmailSecondaryNode, "");
    } else if (workspaceMode === "future-learning") {
      const label = decisionLabelName(teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.classification || "");
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="future-learning" style="display:grid;gap:12px;margin-top:10px;">
          <div>
            <div style="color:#8a4b00;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:820;">Optional follow-up</div>
            <h2 data-ea-preview-heading style="margin:6px 0 0;font-size:1.3rem;font-weight:840;line-height:1.15;overflow-wrap:anywhere;">Teach future emails</h2>
          </div>
          <div style="border-radius:14px;background:#fff4dd;padding:12px;color:#1f1a14;line-height:1.45;">The current email is already changed to ${escapeHtml(label)}. Any lesson you create here applies to future emails only.</div>
          <label for="ea-future-note" style="display:grid;gap:7px;color:#241812;font-weight:760;">
            What should Threadwise remember?
            <textarea id="ea-future-note" rows="4" placeholder="Describe which future emails should be ${escapeHtml(label)}" style="box-sizing:border-box;width:100%;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:#fffdf7;color:#1f1a14;font:inherit;resize:vertical;">${escapeHtml(teachDraft.note)}</textarea>
          </label>
          ${futureLearningError ? `<div role="alert" style="border-radius:14px;background:#fde8e6;padding:12px;color:#7f1d1d;line-height:1.45;">${escapeHtml(futureLearningError)}</div>` : ""}
          <div style="display:grid;gap:9px;">
            <button type="button" data-ea-action="save-future-rule" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Save future rule</button>
          </div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "future-learning-applying") {
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="future-learning-applying" aria-live="polite" aria-busy="true" style="display:grid;gap:12px;margin-top:10px;">
          <h2 data-ea-preview-heading style="margin:0;font-size:1.3rem;line-height:1.2;">Saving future rule</h2>
          <div style="border-radius:14px;background:#fff4dd;padding:12px;color:#1f1a14;line-height:1.45;">Saving this lesson for future emails. The current email and ${escapeHtml(activeProviderName())} are not being changed.</div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
    } else if (workspaceMode === "future-learning-receipt") {
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="future-learning-receipt" role="status" style="display:grid;gap:12px;margin-top:10px;">
          <h2 data-ea-receipt-heading style="margin:0;font-size:1.3rem;line-height:1.2;">Future rule saved</h2>
          <div data-ea-receipt-outcome style="border-radius:14px;background:#eef7f5;padding:12px;color:#1f1a14;line-height:1.45;">Threadwise saved the lesson for future emails. No ${escapeHtml(activeProviderName())} message was changed.</div>
          <button type="button" data-ea-action="finish-future-learning" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Done</button>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
    } else if (workspaceMode === "current-apply-error") {
      const label = decisionLabelName(teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.classification || "");
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="current-apply-error" role="alert" style="display:grid;gap:12px;margin-top:10px;">
          <div>
            <div style="color:#8a4b00;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:820;">Blocked</div>
            <h2 data-ea-preview-heading style="margin:6px 0 0;font-size:1.3rem;line-height:1.2;overflow-wrap:anywhere;">Couldn’t apply ${escapeHtml(label)}</h2>
          </div>
          <div data-ea-preview-effect style="border-radius:14px;background:#fde8e6;padding:12px;color:#7f1d1d;line-height:1.45;">${escapeHtml(currentApplyError)}</div>
          <div style="display:grid;gap:9px;">
            <button type="button" data-ea-action="retry-current-apply" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Retry</button>
          </div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
    } else if (workspaceMode === "teach-result-receipt") {
      gmailCheckResult = null;
      const hasNextReviewItem = remainingNeedsAttentionItems().length > 0;
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="teach-result-receipt" role="status">
          ${renderTeachReceiptHtml(teachResult.message || "Rule applied.", teachOutcome, ((lastSidebarState || {}).ui_state || {}).async_follow_up)}
          ${hasNextReviewItem ? '<button type="button" data-ea-action="open-needs-attention" data-tw-primary-action style="width:100%;min-height:44px;margin-top:12px;border:0;background:#635bff;color:#fff;border-radius:8px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;">Next email</button>' : `<div style="margin-top:12px;">${renderCoverageHtml({ includeHandledReceipt: true })}</div>`}
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "current-receipt" || workspaceMode === "partial-receipt") {
      gmailCheckResult = null;
      const label = decisionLabelName(teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.classification || "");
      const providerLabelUpdated = Boolean(teachOutcome.current_email_written_to_provider ?? teachOutcome.current_email_written_to_gmail);
      const labelWriteFailed = !providerLabelUpdated
        || Number((teachOutcome.provider_label_write_failed ?? teachOutcome.gmail_label_write_failed) || 0) > 0
        || Number(teachWriteThrough?.label_write_failed || 0) > 0;
      const inboxFailed = Number(teachWriteThrough?.inbox_remove_failed || 0) > 0;
      const inboxRemoved = Number(teachWriteThrough?.inbox_removed || 0) > 0;
      const hasNextReviewItem = remainingNeedsAttentionItems().length > 0;
      const providerWriteQueued = Boolean(
        teachOutcome?.provider_write_queued
        || (teachOutcome?.local_decision_accepted && !teachOutcome?.provider_confirmation),
      );
      const successfulProviderChange = !labelWriteFailed && !inboxFailed && !providerWriteQueued;
      const receiptHeading = providerWriteQueued
        ? `Saved locally as ${label}`
        : labelWriteFailed
        ? (teachOutcome.current_email_changed_locally ? `Saved locally as ${label}` : `Couldn’t change to ${label}`)
        : `Changed to ${label}`;
      const receiptOutcomes = providerWriteQueued
        ? `
            <div data-ea-receipt-outcome>Saved locally in Threadwise.</div>
            <div data-ea-receipt-outcome>${escapeHtml(activeProviderName())} label update queued for background activity. Open Activity for aggregate status.</div>
            <div data-ea-receipt-outcome>Inbox handling remains part of the background provider update.</div>
          `
        : labelWriteFailed
        ? `
            <div data-ea-receipt-outcome>${teachOutcome.current_email_changed_locally ? "Saved locally in Threadwise." : "No label change was confirmed."}</div>
            <div data-ea-receipt-outcome>${escapeHtml(activeProviderName())} label not confirmed. Open Activity to review recovery.</div>
          `
        : `
            <div data-ea-receipt-outcome>${escapeHtml(activeProviderName())} label updated.</div>
            <div data-ea-receipt-outcome>${inboxFailed ? "Couldn’t remove from Inbox. Open Activity to review the failed step." : inboxRemoved ? "Removed from Inbox." : "Kept in Inbox."}</div>
          `;
      const coverageOnlyReceipt = !hasNextReviewItem && successfulProviderChange;
      const handledMeta = `${label} · ${inboxRemoved ? "removed from Inbox" : "kept in Inbox"}`;
      setHtml(selectedEmailNode, coverageOnlyReceipt
        ? `<div data-ea-selected-state="receipt" style="margin-top:6px;">${renderCoverageHtml({ includeHandledReceipt: true, handledMeta, showChange: true })}</div>`
        : `
        <div data-ea-selected-state="receipt" style="display:grid;gap:12px;margin-top:10px;">
          <div>
            <div data-ea-receipt-heading style="font-size:1.3rem;font-weight:840;line-height:1.15;overflow-wrap:anywhere;">${escapeHtml(receiptHeading)}</div>
            <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.subject || "(no subject)")}</div>
          </div>
          <div style="display:grid;gap:8px;border-radius:14px;background:#eef7f5;padding:12px;color:#1f1a14;line-height:1.45;">
            ${receiptOutcomes}
          </div>
          ${hasNextReviewItem && successfulProviderChange ? '<button type="button" data-ea-action="open-needs-attention" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Next email</button>' : ""}
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "handled-receipt") {
      gmailCheckResult = null;
      const label = decisionLabelName(selected.internal_label || selected.classification || "Uncategorized");
      const handledAction = handledAcknowledgementModel();
      const writeStatus = String((selected.details || {}).write_status || "").toLowerCase();
      const inboxStatus = String((selected.details || {}).inbox_status || "").toLowerCase();
      const handlingReceipt = selected.status === "auto-handled" && writeStatus === "applied" && inboxStatus === "applied"
        ? `Threadwise applied the ${label} ${activeProviderName()} label and removed this email from Inbox.`
        : selected.status === "kept-visible" && writeStatus === "applied"
          ? `Threadwise applied the ${label} ${activeProviderName()} label and kept this email in Inbox.`
          : `Threadwise classified this email as ${label} and kept it visible. ${activeProviderName()} label write is not confirmed.`;
      const handlingLabel = selected.status === "auto-handled" ? "Auto-handled" : (selected.status_label || "Handled");
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="handled-receipt" style="display:grid;gap:12px;margin-top:10px;">
          <div>
            <h2 data-ea-auto-handled-heading style="margin:0;font-size:1.3rem;font-weight:840;line-height:1.15;">${escapeHtml(label)} · ${escapeHtml(handlingLabel)}</h2>
            <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.subject || "(no subject)")} · ${escapeHtml(selected.sender || "(unknown sender)")}</div>
          </div>
          <div data-ea-auto-handled-receipt style="border-radius:14px;background:#eef7f5;padding:12px;color:#1f1a14;line-height:1.45;">${escapeHtml(handlingReceipt)}</div>
          ${renderPreviousDecisionStatusHtml()}
          ${selected.handled_review_acknowledged
            ? `<div data-ea-handled-reviewed role="status" style="color:#16815d;font-size:.76rem;font-weight:800;">Reviewed · Threadwise will not offer this email again</div>${remainingNeedsAttentionItems().length ? "" : renderCoverageHtml()}`
            : `<button type="button" data-ea-action="confirm-handled-and-next" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">${escapeHtml(handledAction.label)}</button>`}
          ${handledAdvanceError ? `<div data-ea-handled-advance-error role="alert" style="border-radius:14px;background:#f7e2e2;padding:12px;color:#8a1f1f;line-height:1.45;">${escapeHtml(handledAdvanceError)}</div>` : ""}
          <div style="display:flex;gap:12px;flex-wrap:wrap;">
            <button type="button" data-ea-action="change-auto-handled" style="border:0;background:transparent;color:#5d5342;padding:7px 2px;cursor:pointer;font:inherit;font-weight:760;text-decoration:underline;text-underline-offset:3px;">Change</button>
          </div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, detailsExpanded
        ? `<div id="ea-handled-why">${renderSelectedExplanationHtml(selected, workspaceMode, { showEvidence: detailsExpanded })}</div>`
        : "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "review") {
      gmailCheckResult = null;
      const suggestedLabelId = decisionSuggestedLabelId(selected);
      const label = suggestedLabelId ? decisionLabelName(suggestedLabelId) : "";
      const finishingProviderUpdate = selected.status === "write-unconfirmed";
      const localDecisionPending = Boolean(optimisticDecision?.flightActive);
      const progress = currentReviewProgress(selected);
      const progressPercent = Math.max(0, Math.min(100, (progress.value / progress.max) * 100));
      const facts = reviewActionFacts(selected, label);
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="review">
          <section data-ea-current-message-context>
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
              <div style="min-width:0;">
                <div style="font-size:.93rem;font-weight:780;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(selected.subject || "(no subject)")}</div>
                <div style="margin-top:3px;color:#6b6255;font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(selected.sender || "(unknown sender)")}</div>
              </div>
              <span data-ea-review-progress aria-label="Review progress ${escapeHtml(progress.label)}" style="flex:0 0 auto;color:#6b6255;font-size:.74rem;font-variant-numeric:tabular-nums;white-space:nowrap;">${escapeHtml(progress.label)}</span>
            </div>
            ${reviewReceivedLabel(selected.received_at) ? `<div data-ea-review-received-at style="margin-top:4px;color:#6b6255;font-size:0.8rem;">${escapeHtml(reviewReceivedLabel(selected.received_at))}</div>` : ""}
            <div data-ea-review-progress-track role="progressbar" aria-label="Review queue progress" aria-valuemin="0" aria-valuemax="${progress.max}" aria-valuenow="${progress.value}"><div data-ea-review-progress-fill style="width:${progressPercent}%;"></div></div>
          </section>
          ${renderPreviousDecisionStatusHtml()}
          ${showingQueuePreview ? renderQueuePreviewNavigationHtml() : ""}
          ${currentApplyError ? `<div data-ea-current-apply-error role="alert" style="margin-top:12px;border-radius:14px;background:#fde8e6;padding:12px;color:#7f1d1d;line-height:1.45;">${escapeHtml(currentApplyError)}</div>` : ""}
          ${renderSelectedExplanationHtml(selected, workspaceMode, { showEvidence: detailsExpanded })}
          <div data-ea-review-facts aria-label="Review action details">
            <div data-ea-review-fact><span style="color:#6b6255;">Action</span><strong style="text-align:right;">${escapeHtml(facts.action)}</strong></div>
            <div data-ea-review-fact><span style="color:#6b6255;">Inbox</span><strong style="text-align:right;">${escapeHtml(facts.inbox)}</strong></div>
            <div data-ea-review-fact><span style="color:#6b6255;">Scope</span><strong style="text-align:right;">${escapeHtml(facts.scope)}</strong></div>
          </div>
          <div data-ea-review-dock>
            ${currentApplyError
              ? '<button type="button" data-ea-action="retry-current-apply" data-tw-primary-action style="height:40px;border:0;background:#ffc64a;color:#241812;border-radius:8px;padding:0 12px;cursor:pointer;font:inherit;font-weight:760;">Retry <span aria-hidden="true" style="float:right;opacity:.72;">↵</span></button>'
              : label
                ? `<button type="button" data-ea-action="accept-suggestion" data-tw-primary-action ${localDecisionPending ? "disabled" : ""} style="height:40px;border:0;background:${localDecisionPending ? "#a9a5ff" : "#635bff"};color:#fff;border-radius:8px;padding:0 12px;cursor:${localDecisionPending ? "wait" : "pointer"};font:inherit;font-weight:680;">${localDecisionPending ? "Saving previous decision…" : finishingProviderUpdate ? `Apply ${escapeHtml(label)}` : `Accept ${escapeHtml(label)}`} <span aria-hidden="true" style="float:right;opacity:.72;">↵</span></button>`
                : '<button type="button" data-ea-action="change-suggestion" data-tw-primary-action style="height:40px;border:0;background:#635bff;color:#fff;border-radius:8px;padding:0 12px;cursor:pointer;font:inherit;font-weight:680;">Choose label <span aria-hidden="true" style="float:right;opacity:.72;">↵</span></button>'}
          </div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "change") {
      const allowedLabels = (((lastSidebarState.ui_state || {}).allowed_labels) || []);
      const currentLabel = internalLabelId(teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.internal_label || selected.classification || "");
      const labelOptions = allowedLabels.map((option) =>
        `<option value="${escapeHtml(option.id)}"${option.id === currentLabel ? " selected" : ""}>${escapeHtml(decisionLabelName(option.id))}</option>`,
      ).join("");
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="change" style="display:grid;gap:10px;padding:16px;">
          <div>
            <div style="font-size:1rem;font-weight:760;line-height:1.25;">What should this email be?</div>
            <div style="margin-top:4px;color:#60666f;font-size:.78rem;line-height:1.35;overflow-wrap:anywhere;">${escapeHtml(selected.subject || "(no subject)")}</div>
          </div>
          <label style="display:grid;gap:5px;color:#1f2328;font-size:.8rem;font-weight:680;">Tell Threadwise what should change
            <textarea id="ea-teach-note" rows="3" placeholder="For example: This is a LowValue welcome email." style="box-sizing:border-box;width:100%;min-height:84px;padding:9px 10px;border-radius:8px;border:1px solid #cdd2d8;background:#fff;color:#1f2328;font:inherit;font-size:.8rem;line-height:1.4;resize:vertical;">${escapeHtml(teachDraft.note)}</textarea>
          </label>
          <div style="margin-top:-3px;color:#60666f;font-size:.72rem;line-height:1.4;">A label named in your note takes priority over the current suggestion.</div>
          <label style="display:grid;gap:5px;color:#1f2328;font-size:.8rem;font-weight:680;">Label override <span style="color:#7b8088;font-weight:500;">(optional)</span>
            <select id="ea-target-label" style="box-sizing:border-box;width:100%;height:40px;padding:0 10px;border-radius:8px;border:1px solid #cdd2d8;background:#fff;color:#1f2328;font:inherit;font-size:.8rem;"><option value="">Use my instruction</option>${labelOptions}</select>
          </label>
          ${selectedDecisionConflict ? `<div data-ea-label-conflict role="alert" style="border-radius:8px;background:#fde8e6;padding:10px;color:#8a241a;font-size:.76rem;line-height:1.4;">${escapeHtml(selectedDecisionConflict)}</div>` : ""}
          <div style="display:grid;gap:8px;margin-top:2px;">
            <button type="button" data-ea-action="preview-current-change" data-tw-primary-action style="height:40px;border:0;background:#635bff;color:#fff;border-radius:8px;padding:0 12px;cursor:pointer;font:inherit;font-size:.8rem;font-weight:680;">Preview change</button>
          </div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "teach-preview") {
      const label = decisionLabelName(teachPreview?.target_label || teachPreview?.proposed_label || (teachPreview?.selected_label_after || [])[0] || teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.classification || "");
      const learningPreviewHtml = teachPreview
        ? renderCompactTeachPreviewHtml(teachPreview)
        : teachResult
          ? renderTeachResultHtml(teachResult)
          : renderTeachResultHtml(teachPendingResult("preview"));
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="teach-preview" style="display:grid;gap:10px;padding:16px;">
          <div>
            <div style="font-size:1rem;font-weight:760;line-height:1.25;">Change this email to ${escapeHtml(label)}</div>
            <div style="margin-top:4px;color:#60666f;font-size:.78rem;line-height:1.35;overflow-wrap:anywhere;">${escapeHtml(selected.subject || "(no subject)")}</div>
          </div>
          <div style="color:#60666f;font-size:.72rem;line-height:1.4;">Opening the email preserves the current correction draft.</div>
          <div style="border-radius:8px;background:#f6f7f9;padding:10px;color:#1f2328;font-size:.76rem;line-height:1.42;">Choose whether this change applies only here, to future matching mail, or to matching mail already in the inbox.</div>
          ${learningPreviewHtml}
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "teach-scope") {
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="teach-scope" style="display:grid;gap:12px;margin-top:10px;">
          ${renderTeachScopeHtml(teachPreview)}
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
    } else if (workspaceMode === "applying") {
      const label = decisionLabelName(teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.classification || "");
      const progressCopy = activeTeachApplyMode === "apply-included" || activeTeachApplyMode === "matching-existing"
        ? "Updating this email and matching inbox emails…"
        : activeTeachApplyMode === "future-only"
          ? "Updating this email and saving the future rule…"
          : "Updating the current email only…";
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="applying" aria-live="polite" style="display:grid;gap:12px;margin-top:10px;">
          <div>
            <div data-ea-preview-heading style="font-size:1.3rem;font-weight:840;line-height:1.15;overflow-wrap:anywhere;">Applying ${escapeHtml(label)}</div>
            <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.subject || "(no subject)")}</div>
          </div>
          <div data-ea-preview-effect style="border-radius:14px;background:#f5efe2;padding:12px;color:#1f1a14;line-height:1.45;">${escapeHtml(progressCopy)}</div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else if (workspaceMode === "preview") {
      const label = decisionLabelName(teachDraft.targetLabel || decisionSuggestedLabelId(selected) || selected.classification || "");
      setHtml(selectedEmailNode, `
        <div data-ea-selected-state="preview" style="display:grid;gap:12px;margin-top:10px;">
          <div>
            <div data-ea-preview-heading style="font-size:1.3rem;font-weight:840;line-height:1.15;overflow-wrap:anywhere;">Change this email to ${escapeHtml(label)}</div>
            <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.subject || "(no subject)")}</div>
          </div>
          <div data-ea-preview-effect style="border-radius:14px;background:#f5efe2;padding:12px;color:#1f1a14;line-height:1.45;">This updates the current email only.</div>
          <div style="display:grid;gap:9px;">
            <button type="button" data-ea-apply="current-only" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Apply change</button>
          </div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, "");
      setHtml(teachPanelNode, "");
    } else {
      gmailCheckResult = null;
      const statusStyle =
        selected.status === "needs-attention"
          ? "display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#fff4dd;color:#8a4b00;font-size:0.82rem;"
          : "display:inline-flex;align-items:center;padding:5px 10px;border-radius:999px;background:#d8f3ef;color:#0f766e;font-size:0.82rem;";
      const labelOptions = (((lastSidebarState.ui_state || {}).allowed_labels) || [])
        .map(
          (option) =>
            `<option value="${escapeHtml(option.id)}"${
              option.id === currentDraftTargetLabel(selected) ? " selected" : ""
            }>${escapeHtml(option.name)}</option>`,
        )
        .join("");
      const teachPending = isTeachPending();
      let teachPanelHtml = "";
      if (teachFlowState === "result" && teachResult && !String(teachResult.kind || "").endsWith("-error")) {
        teachPanelHtml = renderTeachReceiptHtml(teachResult.message || "", teachOutcome, ((lastSidebarState || {}).ui_state || {}).async_follow_up);
      } else if (teachPreview && (teachFlowState === "scope-confirmation" || teachFlowState === "applying")) {
        teachPanelHtml = `${renderPreviousTeachPreviewHtml(previousTeachPreview)}${renderTeachScopeHtml(teachPreview)}`;
      } else if (teachPreview && teachFlowState === "rule-proposed") {
        teachPanelHtml = `${renderPreviousTeachPreviewHtml(previousTeachPreview)}${renderTeachProposalHtml(teachPreview)}`;
      } else {
        const resultHtml = teachResult ? renderTeachResultHtml(teachResult) : "";
        teachPanelHtml = teachPreview
          ? `${resultHtml}${renderPreviousTeachPreviewHtml(previousTeachPreview)}${renderCompactTeachPreviewHtml(teachPreview)}`
          : teachResult
            ? resultHtml
            : renderPreviousTeachPreviewHtml(previousTeachPreview);
      }
      const details = selected.details || {};
      const decisionSource = humanDecisionSource(details.review_action || "");
      const writeStatusLabel = humanWriteStatus(details.write_status || "");
      const inboxStatusLabel = humanInboxStatus(details.inbox_status || "");
      const matchedRuleList = (details.matched_rule_ids || []).length
        ? `<div style="margin-top:6px;color:#6b6255;line-height:1.45;">Matched rules: ${escapeHtml((details.matched_rule_ids || []).join(", "))}</div>`
        : "";
      const allClassifications = Array.isArray(selected.all_classifications) ? selected.all_classifications : [];
      const allLabelsList = allClassifications.length > 1
        ? `<div style="margin-top:6px;color:#6b6255;line-height:1.45;">All labels: ${escapeHtml(allClassifications.join(", "))}</div>`
        : "";
      const detailsButtonLabel = detailsExpanded ? "Hide technical details" : "Show technical details";
      const detailsHtml = detailsExpanded
        ? `
          <div style="margin-top:10px;color:#6b6255;line-height:1.45;">Decision source: ${escapeHtml(decisionSource)}</div>
          <div style="margin-top:6px;color:#6b6255;line-height:1.45;">Label write status: ${escapeHtml(writeStatusLabel)}</div>
          <div style="margin-top:6px;color:#6b6255;line-height:1.45;">Inbox handling: ${escapeHtml(inboxStatusLabel)}</div>
          <div style="margin-top:6px;color:#6b6255;line-height:1.45;">Matched saved rules: ${escapeHtml(String(details.matched_rule_count || 0))}</div>
          ${matchedRuleList}
          ${allLabelsList}
        `
        : `<div style="margin-top:8px;color:#6b6255;line-height:1.45;">Open details to inspect decision source, Gmail write status, inbox handling, and matched rules.</div>`;
      const previewModeBanner = showingQueuePreview
        ? `
          <div style="margin-top:14px;border-radius:14px;background:#fff8eb;padding:12px;color:#1f1a14;line-height:1.45;">
            <div style="margin-top:8px;">You are previewing a stored queue email from the local snapshot.</div>
            ${renderQueuePreviewNavigationHtml()}
          </div>
        `
        : "";
      const overviewCard = `
        <div style="margin-top:14px;border-radius:14px;background:#f5efe2;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Agent view</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
            <div style="border-radius:12px;background:#fffdfa;padding:10px 12px;">
              <div style="font-size:0.72rem;color:#6b6255;text-transform:uppercase;letter-spacing:0.08em;">${escapeHtml(activeProviderName())} label</div>
              <div style="margin-top:6px;font-weight:700;line-height:1.3;">${escapeHtml(selected.classification || "Uncategorized")}</div>
            </div>
            <div style="border-radius:12px;background:#fffdfa;padding:10px 12px;">
              <div style="font-size:0.72rem;color:#6b6255;text-transform:uppercase;letter-spacing:0.08em;">Human meaning</div>
              <div style="margin-top:6px;font-weight:700;line-height:1.3;">${escapeHtml(humanMeaningForSelected(selected))}</div>
            </div>
          </div>
        </div>
      `;
      const nextStepCard = `
        <div style="margin-top:14px;border-radius:14px;background:${selected.status === "needs-attention" ? "#fff8eb" : "#eef7f5"};padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(stepCopy.title)}</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(stepCopy.body)}</div>
        </div>
      `;
      setHtml(selectedEmailNode, `
        <div style="margin-top:7px;font-size:1.45rem;font-weight:840;letter-spacing:-0.015em;line-height:1.04;">${escapeHtml(selected.subject || "(no subject)")}</div>
        <div style="margin-top:6px;color:#6b6255;font-size:0.88rem;overflow-wrap:anywhere;">${escapeHtml(selected.sender || "(unknown sender)")}</div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">${escapeHtml(selected.classification || "Uncategorized")}</span>
          <span style="${statusStyle};border:2px solid #241812;box-shadow:2px 2px 0 rgba(36,24,18,.28);font-weight:760;">${escapeHtml(selected.status_label)}</span>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
        </div>
        ${previewModeBanner}
        ${overviewCard}
        ${nextStepCard}
        <div style="margin-top:14px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Likely why</div>
          <div style="margin-top:8px;color:#1f1a14;line-height:1.45;">${escapeHtml(likelyReasonForSelected(selected))}</div>
        </div>
      `);
      setHtml(selectedEmailSecondaryNode, `
        <div style="margin-top:14px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Technical details</div>
            <button type="button" data-ea-action="toggle-details" style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:11px;padding:7px 10px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">${detailsButtonLabel}</button>
          </div>
          ${detailsHtml}
        </div>
      `);
      setHtml(teachPanelNode, `
        <div style="display:grid;gap:8px;">
          <textarea id="ea-teach-note" rows="3" placeholder="What should Threadwise understand?" ${teachPending ? "disabled" : ""} style="box-sizing:border-box;width:100%;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:${teachPending ? "#f1eadf" : "#fffdf7"};color:#1f1a14;font:inherit;resize:vertical;box-shadow:2px 2px 0 rgba(36,24,18,.18);">${escapeHtml(teachDraft.note)}</textarea>
          <details style="color:#6b6255;line-height:1.35;font-size:0.82rem;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Choose label manually</summary>
            <select id="ea-target-label" ${teachPending ? "disabled" : ""} style="box-sizing:border-box;width:100%;margin-top:8px;padding:10px 12px;border-radius:11px;border:2px solid #241812;background:${teachPending ? "#f1eadf" : "#fffdf7"};color:#1f1a14;font:inherit;box-shadow:2px 2px 0 rgba(36,24,18,.18);">
              <option value="">Infer from note</option>
              ${labelOptions}
            </select>
          </details>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button type="button" data-ea-action="preview-teach" ${teachPending ? "disabled" : ""} style="border:2px solid #241812;background:${teachPending ? "#c7d8cc" : "#2eb67d"};color:#241812;border-radius:11px;padding:9px 12px;cursor:${teachPending ? "wait" : "pointer"};font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">${teachFlowState === "previewing" ? "Preparing rule..." : "Propose rule"}</button>
            <button type="button" data-ea-action="clear-teach" ${teachPending ? "disabled" : ""} style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;cursor:${teachPending ? "wait" : "pointer"};font:inherit;font-weight:760;text-decoration:underline;text-underline-offset:3px;box-shadow:none;opacity:${teachPending ? "0.55" : "1"};">Clear draft</button>
          </div>
        </div>
        ${teachPanelHtml}
      `);
    }
    renderContextActions(workspaceMode);
    renderMinimized();
    restorePendingQueueNavigationFocus();
    restoreContextScroll(preservedScroll);
    restorePendingContextActionFocus();
    restorePendingExplanationFocus();

    const changedToday = summary.changed_today || {};
    const focus = summaryFocusCopy(activeSummaryFilter);
    const topLabels = (summary.top_labels || [])
      .map(
        (item) =>
          `<span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">${escapeHtml(item.label)} - ${item.count}</span>`,
      )
      .join("");
      const metricButtonStyle = (key) =>
      `border:2px solid #241812;border-radius:11px;background:${activeSummaryFilter === key ? "#dff8ed" : "#fffdf7"};box-shadow:2px 2px 0 rgba(36,24,18,.18);padding:12px;text-align:left;cursor:pointer;font:inherit;color:#241812;`;
    const keptVisibleCount = summary.kept_visible_count ?? countForFilter("kept_visible_items");
    if (workspaceMode === "home") {
      setHtml(
        dailySummaryNode,
        `<div data-ea-selected-state="home" style="display:grid;gap:14px;margin-top:8px;">${renderCoverageHtml()}${gmailCheckResult ? renderGmailCheckResultHtml(gmailCheckResult) : ""}${renderQueueFinderHtml()}${activityHtml}</div>`,
      );
      renderMinimized();
      restorePendingQueueNavigationFocus();
      restoreContextScroll(preservedScroll);
      restorePendingContextActionFocus();
      return;
      /* istanbul ignore next -- retained legacy dashboard markup is unreachable during the bounded coverage slice. */
      const progressionChecking = progressionCheck?.status === "checking"
        && progressionCheck?.filter === "needs_attention_items";
      const progressionRetry = progressionCheck?.status === "retry"
        && progressionCheck?.filter === "needs_attention_items";
      const needsReviewCount = progressionChecking || progressionRetry ? null : countForFilter("needs_attention_items");
      const analyticsStatus = lastHarnessState?.analytics_status || {};
      const analyticsState = analyticsStatus.state || "disabled";
      const analyticsTitle = analyticsState === "degraded"
        ? "Analytics delivery issue"
        : analyticsState === "active"
          ? "Analytics active"
          : analyticsState === "configured"
            ? "Analytics configured"
            : "Analytics disabled";
      const analyticsMessage = analyticsState === "degraded"
        ? "PostHog’s SDK reported a delivery error. Threadwise event counts may be incomplete."
        : analyticsState === "active"
          ? "No SDK delivery errors detected. PostHog arrival is checked separately."
          : analyticsState === "configured"
            ? "PostHog is configured. No events have been queued during this service run."
            : "Analytics is disabled for this Threadwise environment.";
      const analyticsBackground = analyticsState === "degraded" ? "#fff1d6" : "#eef7f5";
      const emptyQueueCopy = progressionChecking
        ? "Threadwise is verifying the current provider-scoped review queue."
        : progressionRetry
          ? "Threadwise could not verify the fresh provider-scoped review queue. No zero-state or sync-completion claim is available."
        : gmailCheckResult?.kind === "review-progression-complete"
          ? "The fresh provider-scoped state has no reviewable emails remaining."
          : gmailCheckResult
            ? `${activeProviderName()} sync completed. Threadwise handled everything automatically.`
            : "There is no review queue right now.";
      setHtml(dailySummaryNode, `
        <div data-ea-selected-state="home" style="display:grid;gap:12px;margin-top:10px;">
          <div style="font-size:1.3rem;font-weight:840;line-height:1.15;overflow-wrap:anywhere;">${progressionChecking ? "Checking review queue…" : progressionRetry ? "Review queue status unverified" : needsReviewCount ? `${needsReviewCount} email${needsReviewCount === 1 ? "" : "s"} need your review` : "No emails need review"}</div>
          ${needsReviewCount ? "" : `<div style="color:#0f766e;line-height:1.45;">${escapeHtml(emptyQueueCopy)}</div>`}
          <div style="color:#6b6255;line-height:1.45;">${Number(summary.processed_count || 0)} processed · ${Number(summary.auto_handled_count || 0)} auto-handled · ${Number(keptVisibleCount || 0)} kept visible</div>
          ${needsReviewCount ? '<button type="button" data-ea-action="open-needs-attention" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Review next</button>' : ""}
          ${renderQueueFinderHtml()}
          <div style="display:flex;flex-wrap:wrap;gap:12px;">
            <a href="${LOCAL_ORIGIN}/daily-dashboard" target="_blank" rel="noreferrer" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px;font:inherit;font-weight:760;box-shadow:none;">Activity</a>
          </div>
          <div data-ea-analytics-health="${escapeHtml(analyticsState)}" style="border-radius:12px;background:${analyticsBackground};padding:10px 12px;color:#155e59;line-height:1.4;">
            <div style="font-weight:820;">${escapeHtml(analyticsTitle)}</div>
            <div style="margin-top:4px;font-size:0.84rem;">${escapeHtml(analyticsMessage)}</div>
          </div>
          ${gmailCheckResult ? renderGmailCheckResultHtml(gmailCheckResult) : ""}
          ${activityHtml}
        </div>
      `);
      restorePendingQueueNavigationFocus();
      restoreContextScroll(preservedScroll);
      restorePendingContextActionFocus();
      return;
    }
    setHtml(dailySummaryNode, `
      ${activityHtml}
      <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${summary.run_count > 1 ? `Rolling view across the last ${summary.run_count} ${escapeHtml(activeProviderName())} runs` : "Latest run snapshot"}</div>
      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px;">
        <button type="button" data-ea-summary-filter="recent_items" style="${metricButtonStyle("recent_items")}"><strong style="display:block;font-size:1.15rem;">${summary.processed_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">processed</span></button>
        <button type="button" data-ea-summary-filter="auto_handled_items" style="${metricButtonStyle("auto_handled_items")}"><strong style="display:block;font-size:1.15rem;">${summary.auto_handled_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">auto-handled</span></button>
        <button type="button" data-ea-summary-filter="kept_visible_items" style="${metricButtonStyle("kept_visible_items")}"><strong style="display:block;font-size:1.15rem;">${keptVisibleCount || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">kept visible</span></button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
        ${summary.report_date ? `<span style="border:2px solid #241812;border-radius:999px;padding:6px 10px;background:#f1eadf;color:#241812;font-size:0.8rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Latest report - ${escapeHtml(summary.report_date)}</span>` : ""}
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
        <a href="${LOCAL_ORIGIN}/daily-dashboard" target="_blank" rel="noreferrer" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;display:inline-flex;align-items:center;text-decoration:underline;text-underline-offset:3px;font:inherit;font-weight:760;box-shadow:none;">Open daily dashboard</a>
      </div>
      <details style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:10px 12px;">
        <summary style="cursor:pointer;font-weight:800;color:#241812;">Report details</summary>
        <div style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#dff8ed;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Viewing</div>
          <div style="margin-top:8px;font-weight:700;line-height:1.35;">${escapeHtml(focus.label)} · ${focus.count}</div>
          <div style="margin-top:6px;color:#1f1a14;line-height:1.45;">${escapeHtml(focus.description)}</div>
        </div>
        <div style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">What Changed Today</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.label_writes_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">labels written</span></div>
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.inbox_removed_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">removed from inbox</span></div>
            <div style="border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:12px;box-shadow:2px 2px 0 rgba(36,24,18,.18);"><strong style="display:block;font-size:1.15rem;">${changedToday.taught_count || 0}</strong><span style="color:#6b6255;font-size:0.82rem;">teaching changes</span></div>
          </div>
          <div style="margin-top:12px;display:grid;gap:10px;">${renderChangedTodayGroups(changedToday)}</div>
        </div>
        ${
          (summary.top_labels || []).length
            ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">${topLabels}</div>`
            : '<p style="margin-top:12px;color:#6b6255;line-height:1.45;">No stored label mix yet.</p>'
        }
        <p style="color:#6b6255;font-size:0.85rem;margin-top:12px;">Source: ${escapeHtml(summary.source_label || `stored ${activeProviderName()} snapshot`)}${summary.batch_id ? ` - ${escapeHtml(summary.batch_id)}` : ""}</p>
        <div style="margin-top:12px;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(bucketLabelForFilter(activeSummaryFilter))}</div>
        <div style="margin-top:10px;display:grid;gap:8px;">${renderSummaryItemCards(summaryItemsForFilter(activeSummaryFilter))}</div>
      </details>
    `);
  }

  function scheduleUnderstandingRefresh(active) {
    if (understandingRefreshTimeoutId !== null) {
      window.clearTimeout(understandingRefreshTimeoutId);
      understandingRefreshTimeoutId = null;
    }
    if (!active) {
      return;
    }
    understandingRefreshTimeoutId = window.setTimeout(() => {
      understandingRefreshTimeoutId = null;
      previousPayload = "";
      refreshSelection(true);
    }, UNDERSTANDING_REFRESH_INTERVAL_MS);
  }

  function setHtml(node, html) {
    if (!node) {
      return;
    }
    node.innerHTML = toTrustedHtml(html);
  }

  function toTrustedHtml(html) {
    if (!globalThis.trustedTypes || typeof globalThis.trustedTypes.createPolicy !== "function") {
      return html;
    }
    if (!trustedHtmlPolicy) {
      try {
        trustedHtmlPolicy = globalThis.trustedTypes.createPolicy("email-agent-gmail-companion", {
          createHTML(value) {
            return value;
          },
        });
      } catch (_error) {
        trustedHtmlPolicy = {
          createHTML(value) {
            return value;
          },
        };
      }
    }
    return trustedHtmlPolicy.createHTML(html);
  }

  function normalizeHarnessState(state, { preserveMissingQueues = false } = {}) {
    const previous = lastHarnessState || {};
    const queueValue = (key) => {
      if (Array.isArray(state?.[key])) {
        return state[key];
      }
      if (preserveMissingQueues || Object.prototype.hasOwnProperty.call(state || {}, key)) {
        return state?.[key] ?? null;
      }
      return previous[key] || [];
    };
    if (state && state.sidebar_state) {
      return {
        ...previous,
        ...state,
        selected_context: state.selected_context || state.sidebar_state.selected_context || previous.selected_context || {},
        recent_items: queueValue("recent_items"),
        needs_attention_items: queueValue("needs_attention_items"),
        auto_handled_items: queueValue("auto_handled_items"),
        kept_visible_items: queueValue("kept_visible_items"),
      };
    }
    const standaloneQueueValue = (key) => {
      if (preserveMissingQueues || Object.prototype.hasOwnProperty.call(state || {}, key)) {
        return state?.[key] ?? null;
      }
      return previous[key] || [];
    };
    return {
      ...previous,
      selected_context: state?.selected_context || previous.selected_context || {},
      sidebar_state: state || previous.sidebar_state || {},
      recent_items: standaloneQueueValue("recent_items"),
      needs_attention_items: standaloneQueueValue("needs_attention_items"),
      auto_handled_items: standaloneQueueValue("auto_handled_items"),
      kept_visible_items: standaloneQueueValue("kept_visible_items"),
    };
  }

  function preserveHarnessQueues(nextSidebarState) {
    if (!nextSidebarState) {
      return lastHarnessState || lastSidebarState || {};
    }
    if (nextSidebarState.sidebar_state) {
      return nextSidebarState;
    }
    const previous = lastHarnessState || {};
    return {
      ...previous,
      selected_context: nextSidebarState.selected_context || previous.selected_context || {},
      sidebar_state: nextSidebarState,
    };
  }

  function summaryItemsForFilter(filter) {
    if (!lastHarnessState) {
      return [];
    }
    return Array.isArray(lastHarnessState[filter]) ? lastHarnessState[filter] : [];
  }

  function resetQueueState() {
    invalidateContextActions();
    queueQuery = "";
    queueFinderOpen = false;
    queueHelpOpen = false;
    queuePreviewActive = false;
    clearPendingQueueNavigationFocus();
  }

  function ensureQueueProvider() {
    if (queueProvider === ACTIVE_PROVIDER) {
      return;
    }
    queueProvider = ACTIVE_PROVIDER;
    resetQueueState();
  }

  function queueSourceItems() {
    ensureQueueProvider();
    return summaryItemsForFilter("needs_attention_items");
  }

  function filteredQueueItems(query = queueQuery, { excludeCommitted = true } = {}) {
    const items = queueSourceItems();
    const filtered = typeof QUEUE_NAVIGATION.filterQueueItems === "function"
      ? QUEUE_NAVIGATION.filterQueueItems(items, ACTIVE_PROVIDER, query)
      : items;
    if (!excludeCommitted) {
      return REVIEW_PROGRESSION.eligibleItems({
        items: filtered,
        activeProvider: ACTIVE_PROVIDER,
        committedIdentities: [],
      });
    }
    return REVIEW_PROGRESSION.eligibleItems({
      items: filtered,
      activeProvider: ACTIVE_PROVIDER,
      committedIdentities: committedReviewIdentities,
    });
  }

  function findQueueItem(messageId, query = queueQuery) {
    if (!messageId) {
      return null;
    }
    const items = filteredQueueItems(query);
    if (typeof QUEUE_NAVIGATION.findCurrentItem === "function") {
      return QUEUE_NAVIGATION.findCurrentItem(items, messageId);
    }
    return items.find((item) => item?.message_id === messageId) || null;
  }

  function adjacentQueueItem(direction) {
    const currentId = manualPreviewContext?.message_id || "";
    if (!currentId) {
      return null;
    }
    const items = filteredQueueItems();
    if (!findQueueItem(currentId)) {
      return null;
    }
    if (typeof QUEUE_NAVIGATION.findAdjacentItem === "function") {
      return QUEUE_NAVIGATION.findAdjacentItem(items, currentId, direction);
    }
    const index = items.findIndex((item) => item?.message_id === currentId);
    const nextIndex = index < 0 ? -1 : index + direction;
    return nextIndex >= 0 && nextIndex < items.length ? items[nextIndex] : null;
  }

  function queuePreviewPosition() {
    const items = filteredQueueItems();
    const currentId = manualPreviewContext?.message_id || "";
    const index = items.findIndex((item) => item?.message_id === currentId);
    return {
      items,
      index,
      currentPresent: index >= 0,
      position: index >= 0 ? `${index + 1} of ${items.length}` : `Current item not in this filter`,
    };
  }

  function currentReviewProgress(selected) {
    const items = filteredQueueItems("");
    const identity = progressionIdentity(lastSidebarState, selected);
    const index = items.findIndex((item) => reviewItemMatchesIdentity(item, identity));
    const summaryCount = Number(lastSidebarState?.daily_summary?.needs_attention_count);
    const total = items.length || (Number.isFinite(summaryCount) ? Math.max(0, summaryCount) : 0);
    if (index >= 0) {
      return {
        label: `${index + 1} of ${Math.max(total, index + 1)}`,
        value: index + 1,
        max: Math.max(total, index + 1),
      };
    }
    return {
      label: total ? `${total} in review` : "Current email",
      value: total ? 1 : 0,
      max: Math.max(total, 1),
    };
  }

  function reviewActionFacts(selected, label) {
    const labelId = internalLabelId(label || decisionSuggestedLabelId(selected));
    const removesFromGmailInbox = ACTIVE_PROVIDER === "gmail"
      && ["promotions", "spam-low-value"].includes(labelId);
    return {
      action: label ? `Apply ${label} label` : "Choose a label",
      inbox: removesFromGmailInbox
        ? "Remove after provider confirmation"
        : "Keep visible",
      scope: "This email only",
    };
  }

  function openQueuePreviewItem(item, origin = "needs_attention_queue", preserveProgressionStatus = false) {
    if (!item || !findQueueItem(item.message_id)) {
      return false;
    }
    return openItemPreview(item, {
      queueContext: true,
      origin,
      preserveProgressionStatus,
    });
  }

  function returnQueuePreviewToHome() {
    if (!queuePreviewActive) {
      return false;
    }
    manualPreviewContext = null;
    manualPreviewOriginContext = null;
    queuePreviewActive = false;
    clearPendingQueueNavigationFocus();
    forcedHome = true;
    forcedHomeLiveContext = lastLiveContext ? { ...lastLiveContext } : null;
    minimized = false;
    resetPerEmailInteraction({ preserveProgressionStatus: true });
    previousPayload = "";
    if (lastHarnessState) {
      renderState(lastHarnessState);
    }
    refreshSelection(true);
    renderMinimized();
    return true;
  }

  function leaveQueueFlow() {
    resetQueueState();
    manualPreviewContext = null;
    manualPreviewOriginContext = null;
  }

  function renderQueueResultCards(items) {
    if (!items.length) {
      return '<div data-ea-queue-empty role="status" style="color:#6b6255;line-height:1.45;">No loaded review emails match this filter.</div>';
    }
    return items.slice(0, QUEUE_RENDER_CAP).map((item) => `
      <button type="button" data-ea-queue-item="${escapeHtml(item.message_id || "")}" style="width:100%;text-align:left;border:1px solid #d7cfbf;border-radius:12px;background:#fffdfa;color:#1f1a14;padding:10px 11px;cursor:pointer;font:inherit;">
        <span style="display:block;font-weight:780;line-height:1.25;overflow-wrap:anywhere;">${escapeHtml(item.subject || "(no subject)")}</span>
        <span style="display:block;margin-top:4px;color:#6b6255;font-size:.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</span>
        <span style="display:flex;flex-wrap:wrap;gap:6px;margin-top:7px;">
          <span style="border-radius:999px;padding:4px 8px;background:#f1eadb;color:#5d5342;font-size:.74rem;">${escapeHtml(item.classification || item.label || "Uncategorized")}</span>
          <span style="border-radius:999px;padding:4px 8px;background:#f1eadb;color:#5d5342;font-size:.74rem;">${escapeHtml(item.status_label || item.status || "")}</span>
        </span>
      </button>
    `).join("");
  }

  function renderQueueFinderHtml() {
    const sourceItems = filteredQueueItems("");
    if (!sourceItems.length) {
      return "";
    }
    if (!queueFinderOpen) {
      return `
        <button type="button" data-ea-action="open-queue-finder" aria-expanded="false" style="justify-self:start;border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;cursor:pointer;font:inherit;font-weight:780;text-decoration:underline;text-underline-offset:3px;">Find in review queue</button>
      `;
    }
    const matches = filteredQueueItems();
    const capNotice = matches.length > QUEUE_RENDER_CAP
      ? `<div data-ea-queue-cap role="status" style="color:#6b6255;font-size:.8rem;line-height:1.35;">Showing the first ${QUEUE_RENDER_CAP} matches here. Open a result to traverse all ${matches.length} loaded matches.</div>`
      : "";
    const help = queueHelpOpen
      ? `<div data-ea-queue-help role="note" style="border-radius:10px;background:#f5efe2;padding:8px 10px;color:#5d5342;font-size:.78rem;line-height:1.4;">Open a result, then J / K move through its filtered queue · Enter runs the visible primary action · Escape backs out safely.</div>`
      : "";
    return `
      <section data-ea-queue-finder tabindex="0" aria-label="Find in review queue" style="display:grid;gap:9px;border-top:1px solid rgba(36,24,18,.2);padding-top:12px;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
          <div style="font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#6b6255;font-weight:820;">Review queue</div>
          <span data-ea-queue-count aria-live="polite" style="color:#6b6255;font-size:.78rem;">${matches.length} of ${sourceItems.length}</span>
        </div>
        <label for="ea-queue-query" style="font-size:.84rem;font-weight:760;">Find by sender, subject, label, or status</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input id="ea-queue-query" data-ea-queue-query type="search" value="${escapeHtml(queueQuery)}" placeholder="Search loaded review emails" autocomplete="off" style="box-sizing:border-box;min-width:0;flex:1;padding:9px 10px;border:1px solid #241812;border-radius:10px;background:#fffdf7;color:#241812;font:inherit;">
          ${queueQuery ? '<button type="button" data-ea-action="clear-queue-filter" aria-label="Clear filter" style="border:0;background:transparent;color:#5d5342;padding:6px 2px;cursor:pointer;font:inherit;font-weight:780;text-decoration:underline;text-underline-offset:3px;white-space:nowrap;">Clear</button>' : ""}
        </div>
        ${!matches.length && queueQuery ? '<div data-ea-queue-no-results role="status" style="color:#8a4b00;line-height:1.4;">No loaded review emails match this filter.</div>' : ""}
        ${capNotice}
        <div data-ea-queue-results style="display:grid;gap:7px;max-height:255px;overflow:auto;">${renderQueueResultCards(matches)}</div>
        <button type="button" data-ea-action="toggle-queue-help" aria-expanded="${queueHelpOpen ? "true" : "false"}" aria-controls="ea-queue-help" style="justify-self:start;border:0;background:transparent;color:#5d5342;padding:3px 2px;cursor:pointer;font:inherit;font-size:.8rem;font-weight:780;text-decoration:underline;text-underline-offset:3px;">${queueHelpOpen ? "Hide keyboard help" : "Keyboard help"}</button>
        ${help.replace('data-ea-queue-help', 'id="ea-queue-help" data-ea-queue-help')}
      </section>
    `;
  }

  function renderQueuePreviewNavigationHtml() {
    if (!queuePreviewActive) {
      return "";
    }
    const { index, currentPresent, position } = queuePreviewPosition();
    const previousDisabled = !currentPresent || index <= 0;
    const nextDisabled = !currentPresent || index >= filteredQueueItems().length - 1;
    return `
      <div data-ea-queue-navigation tabindex="0" style="margin-top:14px;border-radius:12px;background:#f5efe2;padding:10px 11px;color:#1f1a14;line-height:1.4;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
          <div><div style="font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#6b6255;font-weight:820;">Queue preview</div><div data-ea-queue-position style="margin-top:4px;font-weight:780;">${escapeHtml(position)}</div></div>
        </div>
        ${currentPresent ? "" : '<div role="status" style="margin-top:7px;color:#8a4b00;font-size:.8rem;">This email is no longer in the current loaded filter.</div>'}
        <div style="display:flex;gap:8px;margin-top:9px;">
          <button type="button" data-ea-queue-nav="previous" ${previousDisabled ? "disabled" : ""} aria-label="Previous review email" style="flex:1;border:1px solid #241812;background:#fffdf7;color:#241812;border-radius:9px;padding:8px 9px;cursor:${previousDisabled ? "not-allowed" : "pointer"};font:inherit;font-weight:780;opacity:${previousDisabled ? ".5" : "1"};">Previous</button>
          <button type="button" data-ea-queue-nav="next" ${nextDisabled ? "disabled" : ""} aria-label="Next review email" style="flex:1;border:1px solid #241812;background:#fffdf7;color:#241812;border-radius:9px;padding:8px 9px;cursor:${nextDisabled ? "not-allowed" : "pointer"};font:inherit;font-weight:780;opacity:${nextDisabled ? ".5" : "1"};">Next</button>
        </div>
      </div>
    `;
  }

  function remainingNeedsAttentionItems() {
    const current = currentReviewIdentity();
    const seen = new Set();
    return filteredQueueItems().filter((item) => {
      const messageId = item?.message_id || "";
      if (!messageId || reviewItemMatchesIdentity(item, current) || seen.has(messageId)) {
        return false;
      }
      seen.add(messageId);
      return true;
    });
  }

  function handledAcknowledgementModel() {
    const current = currentReviewIdentity();
    const activeItems = summaryItemsForFilter(activeSummaryFilter);
    const currentBelongsToActiveQueue = activeItems.some((item) => reviewItemMatchesIdentity(item, current));
    const filter = currentBelongsToActiveQueue ? activeSummaryFilter : "needs_attention_items";
    return {
      filter,
      ...REVIEW_PROGRESSION.handledAcknowledgementAction({
        items: progressionItemsForFilter(filter, { includeCommitted: true }),
        currentIdentity: current,
        activeProvider: ACTIVE_PROVIDER,
        committedIdentities: committedReviewIdentities,
      }),
    };
  }

  function currentReviewIdentity() {
    const selected = (lastSidebarState || {}).selected_email || {};
    const context = (lastSidebarState || {}).selected_context || {};
    return {
      provider: selected.provider || context.provider || ACTIVE_PROVIDER,
      messageId: selected.message_id || context.message_id || "",
      threadId: selected.thread_id || context.thread_id || "",
      sender: normalizedSender(selected.sender || context.sender || ""),
      subject: normalizedSubject(selected.subject || context.subject || ""),
    };
  }

  function reviewItemMatchesIdentity(item, current) {
    if (!item || !current) {
      return false;
    }
    const itemMessageId = String(item.message_id || "");
    const itemThreadId = String(item.thread_id || "");
    if (current.messageId && itemMessageId) {
      return itemMessageId === current.messageId;
    }
    if (current.threadId && itemThreadId) {
      return itemThreadId === current.threadId;
    }
    return Boolean(
      current.sender && current.subject
      && normalizedSender(item.sender || "") === current.sender
      && normalizedSubject(item.subject || "") === current.subject
    );
  }

  function beginProgressionCheck(filter, query = "") {
    clearProgressionRefreshTimer();
    const generation = ++reviewProgressionGeneration;
    const anchor = progressionContextAnchor(generation);
    progressionCheck = {
      generation,
      filter,
      query: String(query || ""),
      status: "checking",
      anchor,
    };
    forcedHome = true;
    forcedHomeLiveContext = lastLiveContext ? { ...lastLiveContext } : null;
    manualPreviewContext = null;
    manualPreviewOriginContext = null;
    queuePreviewActive = false;
    clearPendingQueueNavigationFocus();
    gmailCheckResult = {
      kind: "review-progression-checking",
      title: filter === "needs_attention_items" ? "Checking review queue…" : `Checking ${bucketLabelForFilter(filter)} queue…`,
      message: filter === "needs_attention_items"
        ? "Threadwise is verifying the current provider-scoped review queue."
        : "Threadwise is verifying the current provider-scoped handled queue.",
    };
    if (lastHarnessState) {
      renderState(lastHarnessState);
    }
    requestProgressionRefresh(generation);
    return generation;
  }

  function rollbackSynchronousDecision(token, message) {
    if (!optimisticDecision || optimisticDecision.token?.token !== token?.token) {
      return;
    }
    const scroll = captureContextScroll();
    forgetCommittedIdentity(token.identity);
    clearOptimisticDecisionStatus();
    applyInFlight = false;
    currentApplyError = friendlyErrorMessage(message || "Could not apply the lesson.");
    teachFlowState = "teaching";
    selectedDecisionMode = "review";
    renderState(lastHarnessState || lastSidebarState);
    restoreContextScroll(scroll);
    document.querySelector("[data-ea-action='retry-current-apply']")?.focus({ preventScroll: true });
    restoreContextScroll(scroll);
  }

  function markOptimisticDecisionRetry(token) {
    if (!optimisticDecision || optimisticDecision.token?.token !== token?.token) {
      return false;
    }
    forgetCommittedIdentity(token.identity);
    optimisticDecision.providerWriteState = "retry";
    optimisticDecision.localAccepted = false;
    optimisticDecision.retryStateLocked = true;
    optimisticDecision.responseReceived = true;
    optimisticDecision.responseAccepted = false;
    optimisticDecision.flightActive = false;
    return true;
  }

  function invalidateCompletionForDecisionFailure(token, message) {
    const completionWasActive = Boolean(
      progressionCheck
      || gmailCheckResult?.kind === "review-progression-complete",
    );
    if (!markOptimisticDecisionRetry(token) || !completionWasActive) {
      return false;
    }
    if (progressionCheck) {
      supersedeProgressionCheckWithDecisionFailure(progressionCheck.generation, message);
      return true;
    }
    refreshInFlight = false;
    latestStateReadGeneration = ++stateReadGeneration;
    gmailCheckResult = {
      kind: "review-progression-retry",
      title: "Review queue status unverified",
      message: `This check needs a retry. ${message || "The final decision was not confirmed. Threadwise needs a fresh queue check before completion can be trusted."}`,
    };
    renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
    return true;
  }

  function beginCurrentDecisionProgression(mode, requestSnapshot) {
    const identity = progressionIdentity(requestSnapshot.sidebarState, requestSnapshot.sidebarState?.selected_email);
    if (!identity.messageId || optimisticDecision?.flightActive
      || committedReviewIdentities.some((candidate) => progressionIdentityKey(candidate) === progressionIdentityKey(identity))) {
      return null;
    }
    const token = REVIEW_PROGRESSION.createRequestToken({
      generation: ++reviewProgressionGeneration,
      kind: mode === "current-only" ? "teach-apply" : "decision",
      identity,
      attemptId: globalThis.crypto?.randomUUID?.()
        || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`,
    });
    optimisticDecision = {
      token,
      identity,
      hostAnchor: currentProgressionHostAnchor(),
      localAccepted: false,
      decisionKind: "teach-apply",
      providerWriteState: "working",
      retryStateLocked: false,
      flightActive: true,
      advanceDone: false,
      responseReceived: false,
      responseAccepted: null,
    };
    return token;
  }

  function advanceAfterCommittedDecision(token, filter = "needs_attention_items") {
    if (!token || !optimisticDecision || optimisticDecision.token.token !== token.token) {
      return false;
    }
    if (optimisticDecision.advanceDone) {
      return true;
    }
    if (!REVIEW_PROGRESSION.decisionMayAdvance(optimisticDecision)) {
      return false;
    }
    optimisticDecision.advanceDone = true;
    const next = nextProgressionItem(filter, token.identity);
    if (next) {
      return openItemPreview(next, {
        queueContext: filter === "needs_attention_items",
        origin: "review_progression",
        preserveProgressionStatus: true,
      });
    }
    if (filter === "needs_attention_items" && queueQuery) {
      forcedHome = true;
      forcedHomeLiveContext = lastLiveContext ? { ...lastLiveContext } : null;
      manualPreviewContext = null;
      manualPreviewOriginContext = null;
      queuePreviewActive = false;
      queueFinderOpen = true;
      gmailCheckResult = {
        kind: REVIEW_PROGRESSION.FILTERED_EMPTY,
        title: "No loaded review emails match",
        message: "Clear the filter to continue reviewing the active provider queue.",
      };
      if (lastHarnessState) {
        renderState(lastHarnessState);
      }
      return false;
    }
    beginProgressionCheck(filter, filter === "needs_attention_items" ? queueQuery : "");
    return false;
  }

  function bucketLabelForFilter(filter) {
    return {
      recent_items: "Recent queue",
      auto_handled_items: "Auto-handled",
      needs_attention_items: "Needs attention",
      kept_visible_items: "Kept visible",
    }[filter] || "Queue";
  }

  function countForFilter(filter) {
    if (filter === "needs_attention_items") {
      return liveNeedsAttentionCount();
    }
    return summaryItemsForFilter(filter).length;
  }

  function liveNeedsAttentionCount() {
    if (progressionCheck?.filter === "needs_attention_items") {
      return 0;
    }
    const queuedItems = lastHarnessState?.needs_attention_items;
    if (Array.isArray(queuedItems)) {
      return filteredQueueItems("").length;
    }
    const summaryCount = Number((((lastSidebarState || {}).daily_summary || {}).needs_attention_count));
    return Number.isFinite(summaryCount)
      ? Math.max(0, summaryCount)
      : summaryItemsForFilter("needs_attention_items").length;
  }

  function nextStepCopy(selected, showingQueuePreview) {
    if (!selected || !selected.found) {
      return {
        title: "What to do now",
        body: "Open one of the synced queue items below if you want to review or teach the agent before the next Gmail sync finishes.",
      };
    }
    if (showingQueuePreview) {
      return {
        title: "What to do now",
        body: "Review this stored queue email, teach the agent if needed, or jump back to the live inbox email when you are done.",
      };
    }
    if (selected.status === "needs-attention") {
      return {
        title: "What to do now",
        body: "This email still needs a decision. Either teach the right label below or leave it visible for later.",
      };
    }
    return {
      title: "What to do now",
      body: "The agent has already classified this email. You only need to step in if the label or handling looks wrong.",
    };
  }

  function likelyReasonForSelected(selected) {
    const reason = (selected && selected.reason ? selected.reason : "").trim();
    if (reason) {
      return `Likely because: ${reason}`;
    }
    return "Likely because this matched the stored classification signals for the current label. Threadwise did not store a more specific reason for this decision yet.";
  }

  function selectedExplanationFor(selected, workspaceMode) {
    const details = selected?.details || {};
    const suggestedLabelId = decisionSuggestedLabelId(selected);
    return SELECTED_EXPLANATION.derive({
      workspaceMode,
      selectedStatus: selected?.status || "",
      providerName: activeProviderName(),
      suggestedLabel: suggestedLabelId ? decisionLabelName(suggestedLabelId) : "",
      storedReason: selected?.rationale || "",
      details: {
        confidence_band: details.confidence_band || "",
        near_misses: Array.isArray(details.near_misses) ? details.near_misses : [],
        matched_rule_count: details.matched_rule_count || 0,
        write_status: details.write_status || "",
        inbox_status: details.inbox_status || "",
        decision_provenance: details.decision_provenance || {},
      },
    });
  }

  function explanationEvidenceValue(row) {
    return (row.values || []).map((value) => {
      if (row.key === "near-misses") {
        return decisionLabelName(value);
      }
      return value;
    }).join(", ");
  }

  function renderSelectedExplanationHtml(selected, workspaceMode, { showEvidence = false } = {}) {
    const model = selectedExplanationFor(selected, workspaceMode);
    if (!model.visible) {
      return "";
    }
    const evidenceDisclosure = model.hasEvidence
      ? `
        <button type="button" data-ea-action="toggle-details" data-ea-explanation-disclosure aria-expanded="${showEvidence ? "true" : "false"}" aria-controls="ea-selected-evidence" style="margin-top:11px;border:0;background:transparent;color:#5d5342;padding:6px 2px;cursor:pointer;font:inherit;font-size:.82rem;font-weight:800;text-decoration:underline;text-underline-offset:3px;text-align:left;">${showEvidence ? "Hide evidence" : "Evidence"}</button>
        ${showEvidence ? `
          <div id="ea-selected-evidence" data-ea-explanation-evidence role="region" aria-label="Stored evidence" style="margin-top:8px;border-top:1px solid #e5dccb;padding-top:9px;display:grid;gap:7px;color:#6b6255;font-size:.86rem;line-height:1.4;">
            ${model.evidenceRows.map((row) => `<div data-ea-evidence-row="${escapeHtml(row.key)}"><strong style="color:#241812;">${escapeHtml(row.label)}:</strong> ${escapeHtml(explanationEvidenceValue(row))}</div>`).join("")}
          </div>
        ` : ""}
      `
      : "";
    const quietReview = workspaceMode === "review";
    const suggestionLabel = model.suggestionLabel
      ? decisionLabelName(model.suggestionLabel)
      : "Needs your label";
    return `
      <section data-ea-selected-explanation ${quietReview ? "data-ea-review-judgment" : ""} style="${quietReview ? "" : "margin-top:0;border:1px solid rgba(36,24,18,.18);border-radius:13px;background:#fff8eb;padding:11px 12px;"}color:#1f1a14;line-height:1.4;">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;">
          <div style="min-width:0;">
            ${quietReview ? "" : '<div style="font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:#6b6255;font-weight:820;">Threadwise\'s read</div>'}
            <div data-ea-explanation-suggestion style="${quietReview ? "font-size:1.25rem;letter-spacing:-.025em;" : "margin-top:4px;"}font-weight:800;overflow-wrap:anywhere;">${escapeHtml(quietReview ? suggestionLabel : model.suggestionText)}</div>
          </div>
          <span data-ea-explanation-confidence style="flex:0 0 auto;${quietReview ? "color:#0f766e;padding:4px 0;" : "border-radius:999px;background:#f1eadf;color:#5d5342;padding:5px 8px;"}font-size:.74rem;font-weight:800;white-space:nowrap;">${escapeHtml(model.confidenceText)}</span>
        </div>
        <div data-ea-explanation-rationale style="margin-top:8px;color:#5d5342;overflow-wrap:anywhere;">${escapeHtml(model.rationale)}</div>
        <div data-ea-explanation-queue-reason style="margin-top:8px;color:#8a4b00;font-size:.82rem;font-weight:760;">${escapeHtml(model.queueReason)}</div>
        ${evidenceDisclosure}
      </section>
    `;
  }

  function restorePendingExplanationFocus() {
    if (!explanationFocusPending) {
      return;
    }
    explanationFocusPending = false;
    const target = document.getElementById(ROOT_ID)?.querySelector("[data-ea-explanation-disclosure]");
    if (target && typeof target.focus === "function") {
      target.focus({ preventScroll: true });
    }
  }

  function humanMeaningForSelected(selected) {
    if (!selected) {
      return "Unknown";
    }
    const status = selected.status_label || "";
    const label = selected.classification || "";
    if (status && label) {
      return `${status} · ${label.replace(/^EA\//, "")}`;
    }
    return status || label.replace(/^EA\//, "") || "Unknown";
  }

  function summaryFocusCopy(filter) {
    const count = countForFilter(filter);
    const label = bucketLabelForFilter(filter);
    const descriptions = {
      recent_items: "Most recent synced emails across the current local snapshot.",
      auto_handled_items: "Items the agent already handled automatically.",
      needs_attention_items: "Items still waiting for a confident decision or follow-up.",
      kept_visible_items: "Items the agent understood but intentionally left in the inbox view.",
    };
    return {
      label,
      count,
      description: descriptions[filter] || "Current queue slice.",
    };
  }

  function renderSummaryItemCards(items) {
    if (!items.length) {
      return '<div style="color:#6b6255;line-height:1.45;">No synced emails in this bucket right now.</div>';
    }
    return items.slice(0, 6)
      .map((item) => {
        return `
          <button type="button" data-ea-summary-item="${escapeHtml(item.message_id || "")}" style="width:100%;text-align:left;border:1px solid ${item.message_id === ((lastSidebarState || {}).selected_email || {}).message_id ? "#0f766e" : "#d7cfbf"};border-radius:14px;background:${item.message_id === ((lastSidebarState || {}).selected_email || {}).message_id ? "#f5fbfa" : "#fffdfa"};padding:10px 12px;color:#1f1a14;cursor:pointer;font:inherit;">
            <div style="font-size:0.95rem;font-weight:700;line-height:1.25;">${escapeHtml(item.subject || "(no subject)")}</div>
            <div style="margin-top:4px;color:#6b6255;font-size:0.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
              <span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">${escapeHtml(item.classification || "Uncategorized")}</span>
              <span style="border-radius:999px;padding:6px 10px;background:#f1eadb;color:#5d5342;font-size:0.8rem;">${escapeHtml(item.status_label || item.status || "")}</span>
            </div>
            <a href="${escapeHtml(PROVIDER.messageUrl(item))}" target="_blank" rel="noreferrer" data-ea-open-gmail="true" style="display:inline-flex;width:max-content;margin-top:8px;border:1px solid #d7cfbf;border-radius:999px;background:#f5efe2;color:#241812;padding:6px 10px;text-decoration:none;font-size:0.78rem;font-weight:800;">Open in ${escapeHtml(activeProviderName())}</a>
          </button>
        `;
      })
      .join("");
  }

  function renderChangedTodayGroups(changedToday) {
    const groups = changedToday.groups || [];
    if (groups.length) {
      return groups.map((group) => `
        <div style="display:grid;gap:8px;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(group.label || "Changes")}</div>
          ${(group.items || []).map(renderChangedTodayItem).join("")}
        </div>
      `).join("");
    }
    const items = changedToday.items || [];
    if (items.length) {
      return items.map(renderChangedTodayItem).join("");
    }
    return '<div style="color:#6b6255;line-height:1.45;">No tracked agent changes in this stored batch yet.</div>';
  }

  function renderChangedTodayItem(item) {
    return `
      <div style="width:100%;text-align:left;border:1px solid #d7cfbf;border-radius:14px;background:#fffdfa;padding:10px 12px;color:#1f1a14;box-sizing:border-box;">
        <div style="font-size:0.95rem;font-weight:700;line-height:1.25;">${escapeHtml(item.subject || "(no subject)")}</div>
        <div style="margin-top:4px;color:#6b6255;font-size:0.82rem;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</div>
        <div style="margin-top:6px;color:#6b6255;line-height:1.45;">${escapeHtml(item.change_summary || "")}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
          <button type="button" data-ea-changed-item="${escapeHtml(item.message_id || "")}" style="border:1px solid #d7cfbf;border-radius:999px;background:#f5efe2;color:#241812;padding:6px 10px;cursor:pointer;font:inherit;font-size:0.78rem;font-weight:800;">Preview in Threadwise</button>
          <button type="button" data-ea-open-changed-gmail="${escapeHtml(item.message_id || "")}" style="border:1px solid #d7cfbf;border-radius:999px;background:#ffc64a;color:#241812;padding:6px 10px;cursor:pointer;font:inherit;font-size:0.78rem;font-weight:800;">Open in ${escapeHtml(activeProviderName())}</button>
        </div>
      </div>
    `;
  }

  function relatedSummaryItemsForContext(context) {
    if (!context) {
      return [];
    }
    const sender = normalizedSender(context.sender || "");
    const subject = normalizedSubject(context.subject || "");
    const seen = new Set();
    const results = [];
    const groups = [
      summaryItemsForFilter("needs_attention_items"),
      summaryItemsForFilter("recent_items"),
      summaryItemsForFilter("kept_visible_items"),
      summaryItemsForFilter("auto_handled_items"),
    ];
    for (const group of groups) {
      for (const item of group) {
        if (!item || !item.message_id || seen.has(item.message_id)) {
          continue;
        }
        const itemSender = normalizedSender(item.sender || "");
        const itemSubject = normalizedSubject(item.subject || "");
        const senderMatch = sender && itemSender && sender === itemSender;
        const subjectMatch = subject && itemSubject && subject === itemSubject;
        if (!senderMatch && !subjectMatch) {
          continue;
        }
        seen.add(item.message_id);
        results.push(item);
      }
    }
    return results;
  }

  function findSummaryItem(messageId) {
    if (!lastHarnessState || !messageId) {
      return null;
    }
    const groups = [
      lastHarnessState.recent_items || [],
      lastHarnessState.needs_attention_items || [],
      lastHarnessState.auto_handled_items || [],
      lastHarnessState.kept_visible_items || [],
    ];
    for (const group of groups) {
      const match = group.find((item) => item.message_id === messageId);
      if (match) {
        return match;
      }
    }
    return null;
  }

  function findChangedTodayItem(messageId) {
    if (!messageId) {
      return null;
    }
    const changedToday = (((lastSidebarState || {}).daily_summary || {}).changed_today) || {};
    for (const group of (changedToday.groups || [])) {
      const match = (group.items || []).find((item) => item.message_id === messageId);
      if (match) {
        return match;
      }
    }
    return (changedToday.items || []).find((item) => item.message_id === messageId) || null;
  }

  function selectedEmailAsItem() {
    const selected = ((lastSidebarState || {}).selected_email) || {};
    return {
      message_id: selected.message_id || "",
      subject: selected.subject || "",
      sender: selected.sender || "",
    };
  }

  function selectedUnderstandingState(selected) {
    return String((selected && selected.understanding_state) || "ready");
  }

  function selectedUnderstandingActive(selected) {
    return selectedUnderstandingState(selected) === "reading" || selectedUnderstandingState(selected) === "understanding";
  }

  function selectedUnderstandingMessage(selected) {
    const message = selected && selected.understanding_message;
    if (message) {
      return message;
    }
    return selectedUnderstandingState(selected) === "reading"
      ? "Reading this email..."
      : selectedUnderstandingState(selected) === "understanding"
        ? "Understanding this email..."
        : "Threadwise is ready with the current email.";
  }

  function isTeachPending() {
    return teachFlowState === "previewing" || teachFlowState === "applying";
  }

  function openSelectedEmailInGmail() {
    return openGmailItem(selectedEmailAsItem());
  }

  function openGmailItem(item) {
    if (!item || !(item.subject || item.sender || item.message_id)) {
      return;
    }
    window.location.href = PROVIDER.messageUrl(item);
  }

  function teachErrorResult(operation, failure) {
    const response = failure && typeof failure === "object" ? failure : null;
    return TEACHING_RECOVERY.describe({
      operation,
      error: response ? "" : failure,
      response,
      providerName: activeProviderName(),
    });
  }

  function teachPendingResult(operation, mode) {
    if (operation === "preview") {
      return {
        kind: "preview-pending",
        state_label: "Working",
        title: "Preview accepted",
        message: "Threadwise accepted your note and is drafting the rule now.",
      };
    }
    const modeLabel = mode === "apply-included"
      ? "Fix + inbox accepted"
      : mode === "future-only"
        ? "Fix + future accepted"
        : "Fix accepted";
    return {
      kind: "apply-pending",
      state_label: "Working",
      title: modeLabel,
      message: "Threadwise is applying this lesson now. We will update this panel when the result is ready.",
    };
  }

  function renderTeachResultHtml(result) {
    const kind = String(result.kind || "");
    const isError = kind.endsWith("-error");
    const isPending = kind.endsWith("-pending");
    const tone = isPending
      ? { background: "#eef3ff", color: "#2146b7" }
      : isError
        ? { background: "#fff4dd", color: "#8a4b00" }
        : { background: "#d8f3ef", color: "#0f766e" };
    const stateLabel = result.state_label || (isPending ? "Working" : isError ? "Retry available" : "Done");
    const recoveryActions = isError && Array.isArray(result.actions)
      ? `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">${result.actions.map((item) => {
        const background = item.primary ? "#635bff" : "#fff";
        const color = item.primary ? "#fff" : "#1f2328";
        const applyMode = item.action === "retry-apply-teach" ? ' data-ea-apply="current-only"' : "";
        return `<button type="button" data-ea-action="${escapeHtml(item.action || "")}"${applyMode} style="min-height:40px;border:1px solid ${item.primary ? "#635bff" : "#cdd2d8"};background:${background};color:${color};border-radius:8px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:700;">${escapeHtml(item.label || "Try again")}</button>`;
      }).join("")}</div>`
      : "";
    return `
      <div style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border-radius:14px;background:${tone.background};padding:12px;color:${tone.color};line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:850;">${escapeHtml(stateLabel)}</div>
        <div style="font-weight:700;">${escapeHtml(result.title || (isError ? "Lesson failed" : "Lesson applied"))}</div>
        <div style="margin-top:8px;">${escapeHtml(result.message || "")}</div>
        ${recoveryActions}
      </div>
    `;
  }

  function renderGmailCheckResultHtml(result) {
    if (!result) {
      return "";
    }
    const resultKind = String(result.kind || "");
    const isError = resultKind.endsWith("-error") || resultKind.endsWith("-retry");
    const tone = isError
      ? { background: "#fff4dd", color: "#8a4b00" }
      : { background: "#d8f3ef", color: "#0f766e" };
    return `
      <div data-ea-review-progression="${escapeHtml(result.kind || "state")}" role="${isError ? "alert" : "status"}" aria-live="polite" style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border-radius:14px;background:${tone.background};padding:12px;color:${tone.color};line-height:1.45;">
        <div style="font-weight:700;">${escapeHtml(result.title || "Gmail sync")}</div>
        <div style="margin-top:8px;">${escapeHtml(result.message || "")}</div>
        ${isError ? '<button type="button" data-ea-action="force-refresh" style="margin-top:10px;border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:9px;padding:7px 10px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Check again</button>' : ""}
      </div>
    `;
  }

  function renderAsyncFollowUpHtml(followUp) {
    if (!followUp || followUp.kind !== "teach-apply-refresh") {
      return "";
    }
    const state = String(followUp.state || "working");
    const tone = state === "done"
      ? { background: "#eef7f5", color: "#0f766e" }
      : state === "retry"
        ? { background: "#fff4dd", color: "#8a4b00" }
        : { background: "#eef3ff", color: "#2146b7" };
    return `
      <div style="margin-top:12px;border-radius:11px;background:${tone.background};padding:10px 12px;color:${tone.color};line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:850;">${escapeHtml(followUp.label || "Background refresh")}</div>
        <div style="margin-top:6px;">${escapeHtml(followUp.message || "")}</div>
      </div>
    `;
  }

  function localTeachActivityItem() {
    if (!teachResult) {
      return null;
    }
    const kind = String(teachResult.kind || "");
    if (kind.endsWith("-pending")) {
      return {
        id: kind,
        kind,
        state: "working",
        label: teachResult.title || "Action accepted",
        message: teachResult.message || "",
      };
    }
    if (kind.endsWith("-error")) {
      return {
        id: kind,
        kind,
        state: "retry",
        label: teachResult.title || "Retry available",
        message: teachResult.message || "",
        action: teachResult.actions?.[0]?.action || (kind === "apply-error" ? "retry-apply-teach" : "retry-preview-teach"),
        action_label: teachResult.actions?.[0]?.label || (kind === "apply-error" ? "Retry fix" : "Retry preview"),
      };
    }
    if (teachFlowState === "result") {
      return {
        id: kind || "teach-result",
        kind: kind || "teach-result",
        state: "done",
        label: teachResult.title || "Last lesson",
        message: teachResult.message || "",
      };
    }
    return null;
  }

  function recentActivityItems(sidebarState) {
    const items = [];
    const localTeach = localTeachActivityItem();
    if (localTeach) {
      items.push(localTeach);
    }
    const localProgression = localProgressionActivityItem();
    if (localProgression) {
      items.push(localProgression);
    }
    const backendItems = (((sidebarState || {}).ui_state || {}).activity_feed) || [];
    for (const item of backendItems) {
      if (!item || !item.id) {
        continue;
      }
      if (items.some((candidate) => candidate.id === item.id)) {
        continue;
      }
      items.push(item);
    }
    return items.slice(0, 3);
  }

  function renderRecentActivityHtml(items) {
    if (!items.length) {
      return "";
    }
    return `
      <div style="margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:#241812;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Recent activity</div>
        <div style="display:grid;gap:8px;margin-top:10px;">
          ${items.map((item) => {
            const state = String(item.state || "working");
            const tone = state === "done"
              ? { background: "#eef7f5", color: "#0f766e" }
              : state === "retry" || state === "error"
                ? { background: "#fff4dd", color: "#8a4b00" }
                : { background: "#eef3ff", color: "#2146b7" };
            return `
              <div data-ea-activity-item="${escapeHtml(item.id || item.kind || "activity")}" style="border-radius:11px;background:${tone.background};padding:10px 12px;color:${tone.color};">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
                  <div style="font-weight:800;">${escapeHtml(item.label || "Activity")}</div>
                  <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:850;">${escapeHtml(state)}</div>
                </div>
                <div style="margin-top:6px;">${escapeHtml(item.message || "")}</div>
                ${
                  item.action
                    ? `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
                        <button type="button" data-ea-action="${escapeHtml(item.action)}"${item.action === "retry-apply-teach" ? ' data-ea-apply="current-only"' : ""} style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:9px;padding:7px 10px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">${escapeHtml(item.action_label || "Retry")}</button>
                      </div>`
                    : ""
                }
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  function renderTeachReceiptHtml(message, outcome, followUp) {
    const rows = [
      ["This email", outcome?.current_email_changed_locally ? "done" : "not changed"],
      [`${activeProviderName()} label`, outcome?.current_email_written_to_provider || outcome?.current_email_written_to_gmail ? "done" : "not confirmed"],
      ["Other stored emails", (outcome?.matching_existing_changed_locally || 0) > 0 ? `${outcome.matching_existing_changed_locally} changed` : "not changed"],
      ["Future rule", outcome?.future_rule_saved ? "saved" : "not saved"],
    ];
    return `
      <div data-ea-teach-state="result" style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border-radius:14px;background:#d8f3ef;padding:12px;color:#0f766e;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:850;">Done</div>
        <div style="font-weight:700;">Rule applied</div>
        <div style="margin-top:8px;">${escapeHtml(message || "Rule applied.")}</div>
        <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:850;color:#0f766e;">What changed</div>
          <div style="display:grid;gap:8px;margin-top:10px;">
            ${rows.map(([label, value]) => `
              <div style="border:1px solid #d7cfbf;border-radius:12px;background:#fffdfa;padding:9px 10px;">
                <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">${escapeHtml(label)}</div>
                <div style="margin-top:5px;font-weight:800;">${escapeHtml(value)}</div>
              </div>
            `).join("")}
          </div>
        </div>
        ${renderAsyncFollowUpHtml(followUp)}
      </div>
    `;
  }

  function renderTeachProposalHtml(preview) {
    return `
      <div data-ea-teach-state="rule-proposed" style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:#241812;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Proposed rule:</div>
        <div style="margin-top:8px;font-weight:800;">${escapeHtml(preview.plain_english_rule || "No rule proposed.")}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-action="accept-teach-rule" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Looks right</button>
          <button type="button" data-ea-action="refine-teach" style="border:2px solid #241812;background:#fffdf7;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Edit</button>
        </div>
      </div>
    `;
  }

  function renderTeachScopeHtml(preview) {
    const pending = teachFlowState === "applying";
    if (pending && teachResult) {
      return renderTeachResultHtml(teachResult);
    }
    return renderCompactTeachPreviewHtml(preview);
  }

  function renderTeachPreviewHtml(preview) {
    const impact = preview.impact || {};
    const futureRuleAllowed = preview.future_rule_allowed !== false;
    const matchingCount = impact.matching_existing_count || 0;
    const similarCount = impact.similar_candidate_count || 0;
    const similarGroups = impact.similar_candidate_groups || [];
    const broaderRules = impact.broader_rule_candidates || [];
    const severityTone = matchingCount >= 50
      ? { bg: "#fff4dd", fg: "#8a4b00", label: "Large existing-email change" }
      : matchingCount > 0
        ? { bg: "#eef7f5", fg: "#0f766e", label: "Existing-email change to confirm" }
        : similarCount > 0
          ? { bg: "#fff4dd", fg: "#8a4b00", label: "Similar emails found" }
          : { bg: "#eef7f5", fg: "#0f766e", label: "Future-facing lesson" };
    const targetLabelName = humanLabelNameFromId((preview.selected_label_after || [])[0] || "");
    const examples = (impact.matching_existing_examples || [])
      .map(
        (item) =>
          `<li>${escapeHtml(item.subject || "(no subject)")} - ${escapeHtml(item.sender || "(unknown sender)")}</li>`,
      )
      .join("");
    const structuredRule = preview.structured_rule || {};
    const ruleMeta = `
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;">
        <span style="display:inline-flex;align-items:center;padding:6px 9px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.76rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.22);">${escapeHtml(preview.rule_type_label || "Future rule")}</span>
        <span style="display:inline-flex;align-items:center;padding:6px 9px;border:2px solid #241812;border-radius:999px;background:${preview.rule_confidence === "tentative" ? "#fff4dd" : "#eef7f5"};color:${preview.rule_confidence === "tentative" ? "#8a4b00" : "#0f766e"};font-size:0.76rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.22);">${escapeHtml(preview.rule_confidence_label || "Future rule")}</span>
      </div>
      ${
        preview.clarifying_question
          ? `<div style="margin-top:8px;color:#6b6255;line-height:1.45;">${escapeHtml(preview.clarifying_question)}</div>`
          : ""
      }
    `;
    const structuredRuleRows = Object.keys(structuredRule).length
      ? Object.entries(structuredRule)
          .map(([key, value]) => `<div><strong>${escapeHtml(key.replaceAll("_", " "))}:</strong> ${escapeHtml(Array.isArray(value) ? value.join(", ") : String(value))}</div>`)
          .join("")
      : '<div>No structured rule details are available yet.</div>';
    const similarGroupsHtml = similarGroups.length
      ? `
        <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#fff8eb;padding:10px 12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Similar emails found</div>
          <div style="margin-top:6px;color:#6b6255;">These are broader candidates. Threadwise is showing them for review, not applying them automatically.</div>
          <div style="display:grid;gap:8px;margin-top:10px;">
            ${similarGroups.map((group) => `
              <div style="border:1px solid #d7cfbf;border-radius:11px;background:#fffdfa;padding:9px 10px;">
                <div style="font-weight:800;">${escapeHtml(group.label || "Similar group")} · ${escapeHtml(String(group.count || 0))}</div>
                <div style="margin-top:4px;color:#6b6255;">${escapeHtml(group.reason || "")}</div>
                ${
                  (group.examples || []).length
                    ? `<ol style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${(group.examples || []).slice(0, 3).map((item) => `<li>${escapeHtml(item.subject || "(no subject)")} - ${escapeHtml(item.sender || "(unknown sender)")}</li>`).join("")}</ol>`
                    : ""
                }
              </div>
            `).join("")}
          </div>
          ${
            broaderRules.length
              ? `<div style="display:grid;gap:6px;margin-top:10px;">${broaderRules.map((rule) => `<div style="color:#6b6255;"><strong style="color:#1f1a14;">Broader rule candidate:</strong> ${escapeHtml(rule.plain_english_rule || "")}</div>`).join("")}</div>`
              : ""
          }
        </div>
      `
      : "";
    return `
      <div style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:#241812;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">This email</div>
        <div style="margin-top:6px;font-weight:700;">${escapeHtml(preview.acknowledgment || "Preview ready.")}</div>
        <div style="margin-top:8px;color:#6b6255;line-height:1.45;">Fix this email only updates the message you are reviewing.</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button type="button" data-ea-apply="current-only" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Fix email + Next</button>
        </div>
        <div style="margin-top:10px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;color:#1f1a14;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Future rule</div>
          <div style="margin-top:6px;font-weight:700;">${escapeHtml(preview.human_explanation || preview.plain_english_rule || "No future rule proposal was generated.")}</div>
          ${ruleMeta}
          <details style="margin-top:8px;color:#6b6255;">
            <summary style="cursor:pointer;font-weight:700;color:#241812;">Structured rule</summary>
            <div style="display:grid;gap:4px;margin-top:8px;">${structuredRuleRows}</div>
          </details>
        </div>
        ${renderRuleAmendmentHtml(preview.amendment_proposal)}
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:${severityTone.bg};color:${severityTone.fg};font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">${escapeHtml(severityTone.label)}</span>
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Current email -> ${escapeHtml(targetLabelName)}</span>
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Exact sender matches: ${matchingCount}</span>
          <span style="display:inline-flex;align-items:center;padding:7px 10px;border:2px solid #241812;border-radius:999px;background:#f1eadf;color:#241812;font-size:0.78rem;font-weight:760;box-shadow:2px 2px 0 rgba(36,24,18,.28);">Similar candidates: ${similarCount}</span>
        </div>
        <div style="margin-top:10px;color:#6b6255;line-height:1.45;">${escapeHtml(previewChoiceExplainer(matchingCount, similarCount))}</div>
        <div style="margin-top:10px;border:2px solid #241812;border-radius:11px;background:#fffdf7;padding:10px 12px;color:#6b6255;line-height:1.45;">
          <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Affected existing emails</div>
          <div style="margin-top:6px;">Would affect <strong style="color:#1f1a14;">${matchingCount}</strong> matching emails Threadwise has seen.</div>
          <details style="margin-top:8px;">
            <summary style="cursor:pointer;font-weight:800;color:#241812;">Show affected emails</summary>
            ${
              examples
                ? `<ol style="margin:8px 0 0;padding-left:18px;color:#6b6255;">${examples}</ol>`
                : '<div style="margin-top:8px;color:#6b6255;">No matching existing emails to show.</div>'
            }
          </details>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
            <button type="button" data-ea-action="open-affected-review" style="border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Review ${matchingCount}</button>
            ${affectedReviewOpen ? '<button type="button" data-ea-apply="apply-included" style="border:2px solid #241812;background:#3d6df2;color:#fff;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Apply to included</button>' : ""}
          </div>
        </div>
        ${renderAffectedReviewHtml(preview)}
        ${similarGroupsHtml}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          ${futureRuleAllowed ? '<button type="button" data-ea-apply="future-only" style="border:2px solid #241812;background:#ffc64a;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Teach future rule</button>' : '<span style="color:#6b6255;line-height:1.45;">This looks like a one-off or uncertain email, so Threadwise will only change this email.</span>'}
        </div>
      </div>
    `;
  }

  function renderCompactTeachPreviewHtml(preview) {
    const impact = preview?.impact || {};
    const matchingCount = Number(impact.matching_existing_count || 0);
    const similarCount = Number(impact.similar_candidate_count || 0);
    const inboxMatchScanWorking = preview?.inbox_backfill?.state === "working";
    const inboxMatchScanUnavailable = preview?.inbox_backfill?.state === "unavailable";
    const inboxMatchScanCapped = Boolean(preview?.inbox_backfill?.is_capped);
    const targetLabelName = humanLabelNameFromId((preview?.selected_label_after || [])[0] || "");
    const structuredRule = preview?.structured_rule || {};
    const labelSetChange = isSelectedEmailLabelSetChange(preview);
    const futureRuleAllowed = preview?.future_rule_allowed !== false && !labelSetChange;
    const intentStatus = preview?.intent_source === "llm"
      ? "LLM reviewed"
      : preview?.selected_label_conflict
        ? "Note override applied"
        : "Deterministic interpretation";
    const selectedStyle = "border:2px solid #241812;background:#dff8ed;";
    const idleStyle = "border:1px solid rgba(36,24,18,.24);background:#fffdf7;";
    const scopeCard = (mode, title, description, disabled = false) => `
      <button type="button" data-ea-scope-choice="${mode}" aria-pressed="${selectedTeachScope === mode ? "true" : "false"}" ${disabled ? "disabled" : ""} style="box-sizing:border-box;width:100%;display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;text-align:left;border-radius:13px;padding:11px 12px;color:#241812;cursor:${disabled ? "not-allowed" : "pointer"};font:inherit;${selectedTeachScope === mode ? selectedStyle : idleStyle}opacity:${disabled ? ".58" : "1"};">
        <span aria-hidden="true" style="display:grid;place-items:center;width:26px;height:26px;border-radius:999px;background:#241812;color:#fff;font-size:.76rem;font-weight:850;">${mode === "current-only" ? "1" : mode === "future-only" ? "2" : "3"}</span>
        <span><strong style="display:block;line-height:1.25;">${escapeHtml(title)}</strong><small style="display:block;margin-top:3px;color:#6b6255;line-height:1.35;">${escapeHtml(description)}</small></span>
      </button>
    `;
    const actionLabel = selectedTeachScope === "future-only"
      ? "Fix + remember + Next"
      : selectedTeachScope === "apply-included"
        ? `Review ${matchingCount} matches`
        : "Fix email + Next";
    const structuredRuleRows = Object.keys(structuredRule).length
      ? Object.entries(structuredRule).map(([key, value]) => `<div><strong>${escapeHtml(key.replaceAll("_", " "))}:</strong> ${escapeHtml(Array.isArray(value) ? value.join(", ") : String(value))}</div>`).join("")
      : "<div>No structured rule details are available yet.</div>";
    const examples = (impact.matching_existing_examples || []).slice(0, 4)
      .map((item) => `<li>${escapeHtml(item.subject || "(no subject)")} · ${escapeHtml(item.sender || "(unknown sender)")}</li>`)
      .join("");
    return `
      <div data-ea-compact-scope-chooser style="display:grid;gap:12px;">
        ${renderSelectedEmailLabelChange(preview)}
        <div>
          <div style="font-size:1.05rem;font-weight:840;line-height:1.25;">Where should this change apply?</div>
          <div style="margin-top:4px;color:#6b6255;font-size:.84rem;">Current label → ${escapeHtml(targetLabelName)}</div>
        </div>
        <div role="group" aria-label="Choose how broadly to apply this change" style="display:grid;gap:8px;">
          ${scopeCard("current-only", "Just this email", labelSetChange ? "This exact label-set change is limited to this message." : "Relabel this message only.")}
          ${futureRuleAllowed ? scopeCard("future-only", "This email + future emails", "Also remember the rule for new matching mail.") : ""}
          ${labelSetChange ? "" : scopeCard(
            "apply-included",
            `Also update ${matchingCount} reviewed inbox email${matchingCount === 1 ? "" : "s"}`,
            matchingCount
              ? inboxMatchScanCapped
                ? "Review these exact matches. More inbox emails may match, but they will not be changed."
                : "Review the exact matches before applying."
              : inboxMatchScanWorking
                ? "Checking matching inbox emails…"
                : inboxMatchScanUnavailable
                  ? "Inbox match scan couldn’t finish. Try the preview again to check existing emails."
                : "No matching existing emails are available.",
            inboxMatchScanWorking || matchingCount === 0,
          )}
        </div>
        <button type="button" data-ea-action="confirm-selected-scope" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">${escapeHtml(actionLabel)}</button>
        <details style="border-top:1px solid rgba(36,24,18,.2);padding-top:10px;color:#6b6255;">
          <summary style="cursor:pointer;font-weight:800;color:#241812;">How Threadwise understood this</summary>
          <div style="margin-top:8px;font-weight:700;color:#241812;">${escapeHtml(preview?.human_explanation || preview?.plain_english_rule || "No future rule proposal was generated.")}</div>
          ${preview?.selected_label_conflict?.message ? `<div style="margin-top:8px;color:#8a4b00;font-weight:700;">${escapeHtml(preview.selected_label_conflict.message)}</div>` : ""}
          <div style="margin-top:6px;">${escapeHtml(preview?.rule_type_label || "Future rule")} · ${escapeHtml(preview?.rule_confidence_label || "Confidence unavailable")} · ${escapeHtml(intentStatus)}</div>
          <button type="button" data-ea-action="force-llm-review" style="margin-top:10px;border:1px solid #241812;background:#fffdf7;color:#241812;border-radius:9px;padding:7px 10px;cursor:pointer;font:inherit;font-weight:800;">Ask LLM to review this</button>
          ${preview?.clarifying_question ? `<div style="margin-top:8px;color:#8a4b00;">${escapeHtml(preview.clarifying_question)}</div>` : ""}
          <div style="display:grid;gap:4px;margin-top:8px;font-size:.82rem;">${structuredRuleRows}</div>
        </details>
        <details style="border-top:1px solid rgba(36,24,18,.2);padding-top:10px;color:#6b6255;">
          <summary style="cursor:pointer;font-weight:800;color:#241812;">Matching evidence</summary>
          <div style="margin-top:8px;">${inboxMatchScanWorking ? "Checking matching inbox emails… You can still fix this email or save the future rule now." : inboxMatchScanUnavailable ? "Inbox match scan couldn’t finish. You can still fix this email or save the future rule; try the preview again before changing existing inbox emails." : `<strong style="color:#241812;">${matchingCount}</strong> exact matches can be reviewed. <strong style="color:#241812;">${similarCount}</strong> similar candidates will not be changed.${inboxMatchScanCapped ? " The live inbox scan was capped; unreviewed messages will not be changed." : ""}`}</div>
          ${examples ? `<ol style="margin:8px 0 0;padding-left:18px;">${examples}</ol>` : ""}
        </details>
        ${renderRuleAmendmentHtml(preview?.amendment_proposal)}
        ${affectedReviewOpen ? `${renderAffectedReviewHtml(preview)}<button type="button" data-ea-apply="apply-included" data-tw-primary-action style="min-height:44px;border:2px solid #241812;background:#3d6df2;color:#fff;border-radius:11px;padding:9px 12px;cursor:pointer;font:inherit;font-weight:800;box-shadow:3px 3px 0 #241812;">Apply to included</button>` : ""}
        ${labelSetChange ? '<div style="color:#6b6255;line-height:1.45;">Multi-label and relative corrections are limited to this selected email in this release.</div>' : futureRuleAllowed ? "" : '<div style="color:#6b6255;line-height:1.45;">This looks like a one-off or uncertain email. Threadwise will only change this email until you describe a recurring pattern.</div>'}
      </div>
    `;
  }

  function renderPreviousTeachPreviewHtml(previousPreview) {
    if (!previousPreview) {
      return "";
    }
    const impact = previousPreview.impact || {};
    const targetLabelName = humanLabelNameFromId((previousPreview.selected_label_after || [])[0] || "");
    return `
      <div data-ea-previous-preview="true" style="box-sizing:border-box;width:100%;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;margin-top:12px;border:2px solid #241812;border-radius:14px;background:#fffdf7;padding:12px;color:#241812;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Previous interpretation</div>
        <div style="margin-top:8px;font-weight:700;">${escapeHtml(previousPreview.acknowledgment || "Previous preview")}</div>
        <div style="margin-top:6px;color:#6b6255;">Would relabel to ${escapeHtml(targetLabelName)} and change ${impact.matching_existing_count || 0} existing emails.</div>
        <div style="margin-top:6px;color:#6b6255;">Use this to compare the old understanding against the current one before you confirm anything broader.</div>
      </div>
    `;
  }

  function renderRuleAmendmentHtml(amendment) {
    if (!amendment || !amendment.status || amendment.status === "accepted" || amendment.status === "rejected") {
      return "";
    }
    const proposedRule = amendment.plain_english_rule || amendment.clarifying_question || "Threadwise needs a clearer boundary before changing the rule.";
    const actions = amendment.status === "proposed"
      ? `
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">
          <button type="button" data-ea-amendment-decision="accept" style="border:2px solid #241812;background:#2eb67d;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Accept amendment</button>
          <button type="button" data-ea-amendment-decision="reject" style="border:2px solid #241812;background:#ebe4d7;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Reject</button>
          <button type="button" data-ea-action="refine-teach" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:7px 2px;cursor:pointer;font:inherit;font-weight:760;text-decoration:underline;text-underline-offset:3px;box-shadow:none;">Keep reviewing</button>
        </div>
      `
      : "";
    return `
      <div style="margin-top:12px;border:2px solid #241812;border-radius:11px;background:#eef7f5;padding:10px 12px;color:#1f1a14;line-height:1.45;">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Possible rule amendment</div>
        <div style="margin-top:6px;font-weight:800;">${escapeHtml(proposedRule)}</div>
        ${amendment.plain_english_rule && amendment.clarifying_question ? `<div style="margin-top:8px;color:#6b6255;">${escapeHtml(amendment.clarifying_question)}</div>` : ""}
        <div style="margin-top:8px;color:#6b6255;">This is only a proposal. Threadwise will not change the rule unless you accept it.</div>
        ${actions}
      </div>
    `;
  }

  function previewChoiceExplainer(matchingCount, similarCount) {
    if (matchingCount > 0) {
      return "Nothing beyond the current email changes unless you explicitly approve it. Use the broader apply option only if this lesson really should rewrite those stored emails too.";
    }
    if (similarCount > 0) {
      return "No exact-sender matches were found, but Threadwise found similar candidates. Those broader candidates are visible for review and need a separate confirmation path before they can be applied.";
    }
    return "This lesson only changes the current email now and teaches future behavior. There are no other stored emails waiting on this exact rule today.";
  }

  function humanLabelNameFromId(labelId) {
    if (!labelId) {
      return "Uncategorized";
    }
    const allowedLabels = ((((lastSidebarState || {}).ui_state || {}).allowed_labels) || []);
    const match = allowedLabels.find((item) => item.id === labelId);
    return match ? match.name : labelId;
  }

  function allowedDecisionLabels() {
    return ((((lastSidebarState || {}).ui_state || {}).allowed_labels) || []);
  }

  function normalizedLabelText(value) {
    return String(value || "").trim().toLowerCase().replace(/^ea\//, "");
  }

  function internalLabelId(value) {
    const normalized = normalizedLabelText(value);
    if (!normalized || normalized === "uncategorized") {
      return "";
    }
    const match = allowedDecisionLabels().find((item) => {
      const id = normalizedLabelText(item.id);
      const name = normalizedLabelText(item.name);
      return normalized === id || normalized === name;
    });
    return match ? String(match.id || "") : "";
  }

  function decisionLabelName(value) {
    const internalId = internalLabelId(value);
    const match = allowedDecisionLabels().find((item) => item.id === internalId);
    return String((match && match.name) || value || "Uncategorized").replace(/^EA\//i, "");
  }

  function decisionSuggestedLabelId(selected) {
    if (!selected) {
      return "";
    }
    return internalLabelId(selected.suggested_label || selected.internal_label || selected.classification || "");
  }

  function recordSuggestionDecisionOnce(decision) {
    if (!recordedSuggestionDecisions.approve && !recordedSuggestionDecisions.edit) {
      recordedSuggestionDecisions[decision] = true;
      try {
        ANALYTICS?.decideSuggestion(decision);
      } catch (_error) {
        // Product actions must continue even when optional analytics is unavailable.
      }
    }
  }

  function recordCommittedCurrentDecision() {
    const selected = lastSidebarState?.selected_email;
    if (!["needs-attention", "write-unconfirmed"].includes(selected?.status)) {
      return;
    }
    const suggestedLabel = decisionSuggestedLabelId(selected);
    const targetLabel = internalLabelId(teachDraft.targetLabel);
    recordSuggestionDecisionOnce(targetLabel && targetLabel === suggestedLabel ? "approve" : "edit");
    if (["queue-ready", "verified-clear"].includes(coverageState.status)) {
      coverageState = COVERAGE.normalize({ ...coverageState, status: "stale" });
    }
  }

  function labelConflictForDraft() {
    const note = String(teachDraft.note || "").trim().toLowerCase();
    const selectedLabel = internalLabelId(teachDraft.targetLabel || "");
    if (!note || !selectedLabel) {
      return "";
    }
    const allowedLabels = allowedDecisionLabels();
    const selectedItem = allowedLabels.find((item) => item.id === selectedLabel);
    const selectedAliases = selectedItem
      ? [
          normalizedLabelText(selectedItem.name),
          normalizedLabelText(selectedItem.id),
          normalizedLabelText(selectedItem.id).replaceAll("-", " "),
        ].filter(Boolean)
      : [];
    if (noteExplicitlyRejectsLabel(note, selectedAliases)) {
      if (!teachDraft.targetLabelExplicit) {
        return "";
      }
      const positiveAlternative = allowedLabels.find((item) => {
        if (item.id === selectedLabel) {
          return false;
        }
        const aliases = [
          normalizedLabelText(item.name),
          normalizedLabelText(item.id),
          normalizedLabelText(item.id).replaceAll("-", " "),
        ].filter(Boolean);
        return aliases.some((alias) => noteExplicitlyAssignsLabel(note, alias));
      });
      return positiveAlternative
        ? `Your note says this is not ${decisionLabelName(selectedLabel)}, but ${decisionLabelName(selectedLabel)} is selected. Choose ${decisionLabelName(positiveAlternative.id)} or choose "Use my instruction".`
        : `Your note says this is not ${decisionLabelName(selectedLabel)}, but ${decisionLabelName(selectedLabel)} is selected. Choose "Use my instruction" or a replacement label.`;
    }
    const mentioned = allowedLabels.find((item) => {
      const aliases = [
        normalizedLabelText(item.name),
        normalizedLabelText(item.id),
        normalizedLabelText(item.id).replaceAll("-", " "),
      ].filter(Boolean);
      if (!aliases.length || item.id === selectedLabel) {
        return false;
      }
      return aliases.some((alias) => noteExplicitlyAssignsLabel(note, alias));
    });
    if (!mentioned) {
      return "";
    }
    return `Your note sounds like ${decisionLabelName(mentioned.id)}, but ${decisionLabelName(selectedLabel)} is selected. Choose which one you mean.`;
  }

  function isSelectedEmailLabelSetChange(preview) {
    return REVIEW_PROGRESSION.labelChangeRequiresCurrentOnly(preview?.label_change || {});
  }

  function hasApprovedSelectedEmailLabelChange(preview) {
    return REVIEW_PROGRESSION.hasApprovedLabelChange(preview?.label_change || {});
  }

  function renderSelectedEmailLabelChange(preview) {
    const change = preview?.label_change;
    if (!change) return "";
    const names = (labels) => (labels || []).map((label) => decisionLabelName(label)).join(" + ") || "None";
    const provenance = change.interpretation || {};
    const source = provenance.source === "llm"
      ? `LLM reviewed${provenance.model ? ` · ${provenance.model}` : ""}`
      : provenance.source === "manual" ? "Manual selection" : "Deterministic fallback";
    return `<div data-ea-label-change-preview style="display:grid;gap:6px;border-radius:12px;background:#eef7f5;padding:10px 12px;line-height:1.4;">
      <div><strong>Before:</strong> ${escapeHtml(names(change.labels_before))}</div>
      <div><strong>After:</strong> ${escapeHtml(names(change.labels_after))}</div>
      <div><strong>Primary:</strong> ${escapeHtml(decisionLabelName(change.primary_label))}</div>
      <div style="color:#5d5342;font-size:.8rem;">${escapeHtml(change.operation)} · This email only · ${escapeHtml(source)}</div>
    </div>`;
  }

  function noteExplicitlyAssignsLabel(note, alias) {
    const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const clauses = String(note || "").split(/[.!?;]+/).map((part) => part.trim()).filter(Boolean);
    return clauses.some((clause) => {
      if (/^(if|unless|except|only when)\b/i.test(clause)) {
        return false;
      }
      if (new RegExp(`\\b(?:not|isn't|is not|aren't|are not|never)\\s+(?:an?\\s+)?${escaped}\\b`, "i").test(clause)) {
        return false;
      }
      if (new RegExp(`\\b${escaped}\\b[^.!?;]*\\b(?:if|when|unless)\\b`, "i").test(clause)) {
        return false;
      }
      return [
        `\\b(?:should be|belongs? (?:in|to)|label(?:ed)? (?:as|with)|categor(?:y|ize|ized) (?:as|with)|use)\\s+(?:an?\\s+)?${escaped}\\b`,
        `\\b${escaped}\\s+(?:is|should be)\\s+(?:the )?(?:label|category)\\b`,
      ].some((pattern) => new RegExp(pattern, "i").test(clause));
    });
  }

  function noteExplicitlyRejectsLabel(note, aliases) {
    return (aliases || []).some((alias) => {
      const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return [
        `\\b(?:not|isn't|is not|aren't|are not|doesn't|does not|don't|do not|never)(?:\\s+(?:be|an?|the|any))?\\s+${escaped}\\b`,
        `\\b(?:exclude|without|never include|do not include|does not include)(?:\\s+(?:an?|the|any))?\\s+${escaped}\\b`,
        `\\b${escaped}\\b\\s+(?:is|are|was|were)?\\s*(?:wrong|incorrect|not applicable|not wanted)\\b`,
      ].some((pattern) => new RegExp(pattern, "i").test(note));
    });
  }

  function defaultManualRuleNote() {
    const selected = lastSidebarState?.selected_email || {};
    const context = lastSidebarState?.selected_context || {};
    const sender = selected.sender || context.sender || "this sender";
    const label = decisionLabelName(teachDraft.targetLabel);
    return `Messages from ${sender} like this should be labeled ${label}.`;
  }

  function contextActionPolicyInput(workspaceMode) {
    const selected = lastSidebarState?.selected_email || null;
    const outcome = teachOutcome || {};
    const providerLabelUpdated = Boolean(
      outcome.current_email_written_to_provider ?? outcome.current_email_written_to_gmail,
    );
    const labelWriteFailed = !providerLabelUpdated
      || Number((outcome.provider_label_write_failed ?? outcome.gmail_label_write_failed) || 0) > 0
      || Number(teachWriteThrough?.label_write_failed || 0) > 0;
    const inboxFailed = Number(teachWriteThrough?.inbox_remove_failed || 0) > 0;
    return {
      workspaceMode,
      queuePreviewActive,
      detailsExpanded,
      hasSuggestedLabel: Boolean(decisionSuggestedLabelId(selected)),
      canOpenEmail: Boolean(selected && selected.found),
      canKeepDiscussing: Boolean(teachPreview),
      providerChangeSucceeded: !labelWriteFailed && !inboxFailed,
      receiptFailed: labelWriteFailed || inboxFailed,
      queueComplete: remainingNeedsAttentionItems().length === 0,
    };
  }

  function contextActionLabel(action, workspaceMode) {
    if (action.id === "open-email" && ["review", "teach-preview", "teach-scope"].includes(workspaceMode)) {
      return `Open email in ${activeProviderName()}`;
    }
    if (action.id === "why") {
      return detailsExpanded ? "Hide why" : "Why";
    }
    return action.label;
  }

  function contextActionHref(action) {
    return action.linkKind === "activity" ? `${LOCAL_ORIGIN}/daily-dashboard` : "";
  }

  function contextActionMarkup(action, workspaceMode, index) {
    const label = contextActionLabel(action, workspaceMode);
    const common = `data-ea-context-item="${escapeHtml(action.id)}" data-ea-context-generation="${contextActionsGeneration}" role="menuitem" tabindex="${index === contextActionsActiveIndex ? "0" : "-1"}" aria-label="${escapeHtml(label)}"`;
    if (action.linkKind) {
      return `<a ${common} href="${escapeHtml(contextActionHref(action))}" target="_blank" rel="noreferrer" style="display:flex;align-items:center;min-height:44px;box-sizing:border-box;padding:9px 11px;border:1px solid rgba(36,24,18,.2);border-radius:10px;background:#fffdf7;color:#241812;text-decoration:none;font:inherit;font-weight:780;">${escapeHtml(label)}</a>`;
    }
    return `<button type="button" ${common} data-ea-action="${escapeHtml(action.dataAction)}" style="display:flex;align-items:center;width:100%;min-height:44px;box-sizing:border-box;padding:9px 11px;border:1px solid rgba(36,24,18,.2);border-radius:10px;background:#fffdf7;color:#241812;text-align:left;cursor:pointer;font:inherit;font-weight:780;">${escapeHtml(label)}</button>`;
  }

  function restorePendingContextActionFocus() {
    if (!contextActionFocusPending) {
      return;
    }
    const root = document.getElementById(ROOT_ID);
    if (!root) {
      return;
    }
    const trigger = root.querySelector("#ea-context-actions [data-ea-context-trigger]");
    const primary = visibleEnabledPrimaryActions(root)[0];
    const workspace = root.querySelector("#ea-workspace") || root;
    const target = trigger || primary || workspace;
    if (!target || typeof target.focus !== "function") {
      return;
    }
    contextActionFocusPending = false;
    target.focus({ preventScroll: true });
  }

  function requestContextActionFocus() {
    contextActionFocusPending = true;
    if (contextActionFocusTimer !== null) {
      window.clearTimeout(contextActionFocusTimer);
    }
    contextActionFocusTimer = window.setTimeout(() => {
      contextActionFocusTimer = null;
      restorePendingContextActionFocus();
    }, 0);
  }

  function captureContextScroll() {
    const root = document.getElementById(ROOT_ID);
    const content = root?.querySelector("#ea-content");
    return {
      pageX: Number(globalThis.scrollX || 0),
      pageY: Number(globalThis.scrollY || 0),
      contentScrollTop: Number(content?.scrollTop || 0),
      contentScrollLeft: Number(content?.scrollLeft || 0),
    };
  }

  function restoreContextScroll(scroll) {
    if (!scroll) return;
    if (typeof globalThis.scrollTo === "function") {
      globalThis.scrollTo(scroll.pageX, scroll.pageY);
    }
    const root = document.getElementById(ROOT_ID);
    const content = root?.querySelector("#ea-content");
    if (content) {
      content.scrollTop = scroll.contentScrollTop;
      content.scrollLeft = scroll.contentScrollLeft;
    }
  }

  function visibleProtectedContextRects(root) {
    const nodes = Array.from(root?.querySelectorAll?.(
      "[data-tw-primary-action], [data-ea-action='change-suggestion'], [data-ea-action='change-auto-handled']",
    ) || []);
    return nodes.filter((node, index) => {
      if (nodes.indexOf(node) !== index) return false;
      if (node.disabled || node.getAttribute("aria-disabled") === "true" || node.hidden) {
        return false;
      }
      const style = globalThis.getComputedStyle?.(node);
      if (style && (style.display === "none" || style.visibility === "hidden")) {
        return false;
      }
      const rect = node.getBoundingClientRect?.();
      return Boolean(rect && rect.width > 0 && rect.height > 0);
    }).map((node) => {
      const rect = node.getBoundingClientRect();
      return {
        node,
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
      };
    });
  }

  function contextRectsIntersect(left, top, width, height, protectedRect) {
    return left < protectedRect.right
      && left + width > protectedRect.left
      && top < protectedRect.bottom
      && top + height > protectedRect.top;
  }

  function positionContextMenu() {
    if (!contextActionsOpen) {
      return;
    }
    const root = document.getElementById(ROOT_ID);
    const menu = root?.querySelector("#ea-context-menu");
    const trigger = root?.querySelector("#ea-context-actions [data-ea-context-trigger]");
    if (!root || !menu || !trigger) {
      return;
    }
    const rootRect = root.getBoundingClientRect();
    const triggerRect = trigger.getBoundingClientRect();
    const bounds = {
      left: Math.max(8, rootRect.left),
      right: Math.min(window.innerWidth - 8, rootRect.right),
      top: Math.max(8, rootRect.top),
      bottom: Math.min(window.innerHeight - 8, rootRect.bottom),
    };
    menu.style.visibility = "hidden";
    menu.style.left = "auto";
    menu.style.right = "8px";
    const menuRect = menu.getBoundingClientRect();
    const width = menuRect.width;
    const height = menuRect.height;
    const maxTop = Math.max(bounds.top, bounds.bottom - height);
    const left = Math.min(
      Math.max(bounds.right - width - 8, bounds.left),
      Math.max(bounds.left, bounds.right - width),
    );
    const clampTop = (candidate) => Math.min(Math.max(candidate, bounds.top), maxTop);
    const candidates = [
      { name: "above-trigger", top: clampTop(triggerRect.top - height - 7) },
      { name: "below-trigger", top: clampTop(triggerRect.bottom + 7) },
      { name: "top-of-companion", top: clampTop(bounds.top + 8) },
    ];
    const protectedRects = visibleProtectedContextRects(root);
    const selected = candidates.find((candidate) => !protectedRects.some((protectedRect) => (
      contextRectsIntersect(left, candidate.top, width, height, protectedRect)
    ))) || candidates[candidates.length - 1];
    menu.dataset.eaContextPlacement = selected.name;
    menu.style.left = "auto";
    menu.style.right = "8px";
    menu.style.top = `${selected.top - rootRect.top}px`;
    menu.style.visibility = "visible";
  }

  function renderContextActions(workspaceMode) {
    // These displaced controls keep their existing contracts while rendering only in the allowlisted menu:
    // data-ea-action="open-selected-gmail" style="border:0;background:transparent
    // data-ea-action="open-selected-gmail"
    // data-ea-action="open-selected-gmail"
    // data-ea-action="open-selected-gmail"
    // Open this email in ${escapeHtml(activeProviderName())}
    // data-ea-action="return-home-after-receipt"
    // Close preview remains a documented displaced queue affordance; Back to queue is the allowlisted menu action.
    // Keep discussing remains the exact teach-scope handler, displaced into this menu.
    // Keep discussing
    const root = document.getElementById(ROOT_ID);
    const secondary = root?.querySelector("#ea-selected-email-secondary");
    if (!secondary) return;
    const policyInput = contextActionPolicyInput(workspaceMode);
    const actions = CONTEXT_ACTIONS.deriveActions(policyInput);
    let host = root.querySelector("#ea-context-actions");
    if (!actions.length) {
      if (host?.parentNode) host.parentNode.removeChild(host);
      const menu = root.querySelector("#ea-context-menu");
      if (menu?.parentNode) menu.parentNode.removeChild(menu);
      return;
    }
    if (!host) {
      host = document.createElement("div");
      host.id = "ea-context-actions";
    }
    let parent = secondary;
    if (workspaceMode === "review") {
      parent = root.querySelector("[data-ea-review-dock]") || secondary;
    }
    if (host.parentNode !== parent) {
      parent.appendChild(host);
    }
    host.dataset.eaWorkspaceMode = workspaceMode;
    const quietDock = workspaceMode === "review";
    setHtml(host, `
      <div data-ea-context-actions-surface style="display:grid;gap:0;margin-top:14px;">
        <button type="button" data-ea-context-trigger aria-haspopup="menu" aria-expanded="${contextActionsOpen ? "true" : "false"}" aria-controls="ea-context-menu" aria-label="Open contextual actions" title="Actions (.)" style="display:inline-flex;align-items:center;justify-content:${quietDock ? "center" : "space-between"};gap:8px;height:40px;width:100%;box-sizing:border-box;padding:0 10px;border:1px solid #e2e5e9;border-radius:8px;background:#fff;color:#1f2328;cursor:pointer;font:inherit;font-size:.8rem;font-weight:650;">
          ${quietDock ? '<span aria-hidden="true">⋯</span>' : '<span>Actions</span><span aria-hidden="true" style="color:#7b8088;font-size:.72rem;">· .</span>'}
        </button>
      </div>
    `);
    const oldMenu = root.querySelector("#ea-context-menu");
    if (oldMenu?.parentNode) {
      oldMenu.parentNode.removeChild(oldMenu);
    }
    if (contextActionsOpen) {
      const menu = document.createElement("div");
      menu.id = "ea-context-menu";
      menu.dataset.eaContextMenu = "true";
      menu.setAttribute("role", "menu");
      menu.setAttribute("aria-label", "Contextual actions");
      Object.assign(menu.style, {
        position: "absolute",
        display: "grid",
        gap: "6px",
        boxSizing: "border-box",
        width: "max-content",
        maxWidth: "calc(100% - 16px)",
        padding: "7px",
        border: "1px solid rgba(36,24,18,.24)",
        borderRadius: "12px",
        background: "#f5efe2",
        zIndex: "2147483647",
        visibility: "hidden",
      });
      setHtml(menu, actions.map((action, index) => contextActionMarkup(action, workspaceMode, index)).join(""));
      root.appendChild(menu);
      positionContextMenu();
      window.requestAnimationFrame?.(() => positionContextMenu());
      window.setTimeout(() => positionContextMenu(), 0);
      const item = menu.querySelector(`[data-ea-context-item][data-ea-context-generation="${contextActionsGeneration}"]`);
      item?.focus({ preventScroll: true });
    }
  }

  function contextActionsWorkspaceMode() {
    const host = document.getElementById("ea-context-actions");
    return host?.dataset.eaWorkspaceMode
      || document.getElementById("ea-workspace")?.dataset.eaWorkspaceMode
      || "home";
  }

  function openContextActions() {
    const host = document.getElementById("ea-context-actions");
    if (!host || !CONTEXT_ACTIONS.deriveActions(contextActionPolicyInput(contextActionsWorkspaceMode())).length) {
      return false;
    }
    contextActionsOpen = true;
    contextActionsActiveIndex = 0;
    renderContextActions(contextActionsWorkspaceMode());
    return true;
  }

  function disarmContextEscapeRetreat() {
    contextEscapeRetreatArmed = false;
    if (contextEscapeRetreatTimer !== null) {
      window.clearTimeout(contextEscapeRetreatTimer);
      contextEscapeRetreatTimer = null;
    }
  }

  function armContextEscapeRetreat() {
    disarmContextEscapeRetreat();
    if (minimized) {
      return;
    }
    contextEscapeRetreatArmed = true;
    contextEscapeRetreatTimer = window.setTimeout(disarmContextEscapeRetreat, 2000);
  }

  function handleDocumentKeydown(event) {
    if (!contextEscapeRetreatArmed) {
      return;
    }
    disarmContextEscapeRetreat();
    const isEscape = event?.key === "Escape" || event?.key === "Esc";
    const isModified = Boolean(event?.altKey || event?.ctrlKey || event?.metaKey || event?.shiftKey);
    if (!isEscape || isModified || QUEUE_NAVIGATION.isEditableTarget?.(event?.target)) {
      return;
    }
    const root = document.getElementById(ROOT_ID);
    if (!root || minimized || contextActionsOpen) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    minimized = true;
    renderMinimized();
  }

  function closeContextActions({ restoreFocus = false, render = true, hide = true } = {}) {
    const host = document.getElementById("ea-context-actions");
    contextActionsOpen = false;
    contextActionsActiveIndex = 0;
    if (render) {
      renderContextActions(contextActionsWorkspaceMode());
    } else {
      host?.querySelector("[data-ea-context-trigger]")?.setAttribute("aria-expanded", "false");
      const menu = document.getElementById("ea-context-menu");
      if (menu?.parentNode) {
        menu.parentNode.removeChild(menu);
      }
    }
    if (restoreFocus) {
      document.getElementById("ea-context-actions")
        ?.querySelector("[data-ea-context-trigger]")
        ?.focus({ preventScroll: true });
    }
  }

  function contextActionItems() {
    const root = document.getElementById(ROOT_ID);
    return Array.from(root?.querySelectorAll?.(`[data-ea-context-item][data-ea-context-generation="${contextActionsGeneration}"]`) || []);
  }

  function setContextActionsActiveIndex(index) {
    const items = contextActionItems();
    if (!items.length) return;
    contextActionsActiveIndex = CONTEXT_ACTIONS.nextIndex(index, "first", items.length);
    items.forEach((item, itemIndex) => {
      item.setAttribute("tabindex", itemIndex === contextActionsActiveIndex ? "0" : "-1");
    });
    items[contextActionsActiveIndex]?.focus({ preventScroll: true });
  }

  function moveContextActions(command) {
    const items = contextActionItems();
    if (!items.length) return;
    contextActionsActiveIndex = CONTEXT_ACTIONS.nextIndex(contextActionsActiveIndex, command, items.length);
    items.forEach((item, itemIndex) => {
      item.setAttribute("tabindex", itemIndex === contextActionsActiveIndex ? "0" : "-1");
    });
    items[contextActionsActiveIndex]?.focus({ preventScroll: true });
  }

  function visibleEnabledPrimaryActions(root) {
    return Array.from(root?.querySelectorAll?.("[data-tw-primary-action]") || []).filter((node) => {
      if (node.disabled || node.getAttribute("aria-disabled") === "true" || node.hidden) {
        return false;
      }
      const style = globalThis.getComputedStyle?.(node);
      if (style && (style.display === "none" || style.visibility === "hidden")) {
        return false;
      }
      const rect = node.getBoundingClientRect?.();
      return !rect || rect.width > 0 || rect.height > 0;
    });
  }

  function panelKeyCommand(event, root) {
    if (typeof QUEUE_NAVIGATION.classifyPanelKey === "function") {
      return QUEUE_NAVIGATION.classifyPanelKey(event, root);
    }
    if (typeof QUEUE_NAVIGATION.classifyKey === "function") {
      return QUEUE_NAVIGATION.classifyKey(event, root);
    }
    return null;
  }

  function handlePanelKeydown(event) {
    const root = document.getElementById(ROOT_ID);
    const contextCommand = CONTEXT_ACTIONS.classifyMenuKey(event, root, contextActionsOpen);
    if (contextCommand === "open") {
      event.preventDefault();
      openContextActions();
      return;
    }
    if (contextActionsOpen) {
      if (contextCommand === "next" || contextCommand === "previous") {
        event.preventDefault();
        moveContextActions(contextCommand);
        return;
      }
      if (contextCommand === "first" || contextCommand === "last") {
        event.preventDefault();
        moveContextActions(contextCommand);
        return;
      }
      if (contextCommand === "activate") {
        event.preventDefault();
        const items = contextActionItems();
        const item = items[contextActionsActiveIndex];
        if (item && item.getAttribute("data-ea-context-generation") === String(contextActionsGeneration)) {
          requestContextActionFocus();
          item.click();
        }
        return;
      }
      if (contextCommand === "close") {
        event.preventDefault();
        closeContextActions({ restoreFocus: true });
        armContextEscapeRetreat();
        return;
      }
      if (contextCommand === "consume") {
        event.preventDefault();
        return;
      }
    }
    const command = panelKeyCommand(event, root);
    if (!command) {
      return;
    }
    if (command === "primary-action") {
      const queueFinder = event.target?.closest?.("[data-ea-queue-finder]");
      const firstQueueResult = queueFinder?.querySelector?.("[data-ea-queue-item]");
      if (firstQueueResult) {
        event.preventDefault();
        firstQueueResult.click();
        return;
      }
      const actions = visibleEnabledPrimaryActions(root);
      if (actions.length !== 1) {
        return;
      }
      event.preventDefault();
      actions[0].click();
      return;
    }
    if (command === "escape") {
      event.preventDefault();
      if (queueHelpOpen) {
        queueHelpOpen = false;
        renderState(lastHarnessState);
        return;
      }
      if (queueQuery) {
        queueQuery = "";
        queueFinderOpen = true;
        renderState(lastHarnessState);
        document.getElementById("ea-queue-query")?.focus({ preventScroll: true });
        return;
      }
      if (queuePreviewActive) {
        returnQueuePreviewToHome();
        return;
      }
      minimized = true;
      renderMinimized();
      return;
    }
    if (command !== "next" && command !== "previous") {
      return;
    }
    if (!queuePreviewActive) {
      return;
    }
    event.preventDefault();
    const item = adjacentQueueItem(command === "next" ? 1 : -1);
    if (item) {
      openQueuePreviewItem(item, "queue_keyboard");
    }
  }

  async function handlePanelClick(event) {
    const coverageCheckButton = event.target.closest("[data-ea-action='coverage-check']");
    if (coverageCheckButton) {
      event.preventDefault();
      return startCoverageCheck();
    }
    const coverageReviewButton = event.target.closest("[data-ea-action='coverage-review']");
    if (coverageReviewButton) {
      event.preventDefault();
      return openCoverageQueue();
    }
    const coverageSyncButton = event.target.closest("[data-ea-action='coverage-sync']");
    if (coverageSyncButton) {
      event.preventDefault();
      return triggerProviderSync({ refreshCoverageAfter: true });
    }
    const coverageBackButton = event.target.closest("[data-ea-action='coverage-back']");
    if (coverageBackButton) {
      event.preventDefault();
      minimized = true;
      renderMinimized();
      return true;
    }
    const coverageDetailsButton = event.target.closest("[data-ea-action='coverage-details']");
    if (coverageDetailsButton) {
      event.preventDefault();
      coverageDetailsOpen = !coverageDetailsOpen;
      renderState(lastHarnessState || lastSidebarState);
      return true;
    }
    const contextTrigger = event.target.closest("[data-ea-context-trigger]");
    if (contextTrigger) {
      event.preventDefault();
      openContextActions();
      return;
    }
    const contextItem = event.target.closest("[data-ea-context-item]");
    if (contextItem) {
      if (contextItem.getAttribute("data-ea-context-generation") !== String(contextActionsGeneration)) {
        event.preventDefault();
        return;
      }
      requestContextActionFocus();
      closeContextActions({ render: false });
    }
    const onboardingContinueButton = event.target.closest("[data-ea-action='onboarding-continue']");
    if (onboardingContinueButton) {
      event.preventDefault();
      return finishOnboarding("completed");
    }
    const onboardingRetryButton = event.target.closest("[data-ea-action='onboarding-retry']");
    if (onboardingRetryButton) {
      event.preventDefault();
      previousPayload = "";
      refreshSelection(true);
      return;
    }
    const onboardingSkipButton = event.target.closest("[data-ea-action='onboarding-skip']");
    if (onboardingSkipButton) {
      event.preventDefault();
      return finishOnboarding("dismissed");
    }
    const openFeedbackButton = event.target.closest("[data-ea-action='open-feedback']");
    if (openFeedbackButton) {
      event.preventDefault();
      feedbackOpen = !feedbackOpen;
      feedbackResult = "";
      renderFeedbackPanel();
      return;
    }
    const submitFeedbackButton = event.target.closest("[data-ea-action='submit-feedback']");
    if (submitFeedbackButton) {
      event.preventDefault();
      return submitFounderFeedback();
    }
    const clearFeedbackButton = event.target.closest("[data-ea-action='clear-feedback']");
    if (clearFeedbackButton) {
      event.preventDefault();
      feedbackDraft = "";
      feedbackResult = "";
      renderFeedbackPanel();
      return;
    }
    const forceRefreshButton = event.target.closest("[data-ea-action='force-refresh']");
    if (forceRefreshButton) {
      event.preventDefault();
      if (forceRefreshButton.hasAttribute("data-ea-recovery-action")) {
        if (connectionRetryInFlight) {
          return;
        }
        connectionRetryInFlight = true;
        connectionRetryFeedback = "checking";
        renderError(lastRecoveryMessage, lastConnectionState);
        previousPayload = "";
        if (refreshInFlight) {
          return;
        }
        refreshSelection(true, { suppressTransition: true });
        return;
      }
      if (progressionCheck) {
        progressionCheck.status = "checking";
        gmailCheckResult = {
          kind: "review-progression-checking",
          title: progressionCheck.filter === "needs_attention_items" ? "Checking review queue…" : `Checking ${bucketLabelForFilter(progressionCheck.filter)} queue…`,
          message: "Threadwise is verifying the current provider-scoped review queue.",
        };
        if (lastHarnessState) {
          renderState(lastHarnessState);
        }
        requestProgressionRefresh(progressionCheck.generation);
        return;
      }
      previousPayload = "";
      refreshSelection(true);
      return;
    }
    const reloadProviderTabButton = event.target.closest("[data-ea-action='reload-provider-tab']");
    if (reloadProviderTabButton) {
      event.preventDefault();
      window.location.reload();
      return;
    }
    const runProviderSyncButton = event.target.closest("[data-ea-action='run-provider-sync']");
    if (runProviderSyncButton) {
      event.preventDefault();
      triggerProviderSync();
      return;
    }
    const retryProviderWriteButton = event.target.closest("[data-ea-action='retry-provider-write']");
    if (retryProviderWriteButton) {
      event.preventDefault();
      retryProviderWriteButton.disabled = true;
      chrome.runtime.sendMessage({
        type: "email-agent:api",
        path: "/api/provider-write-retry",
        method: "POST",
        body: { selected_context: lastSidebarState?.selected_context || { provider: ACTIVE_PROVIDER } },
      }, (response) => {
        if (optimisticDecision?.retryStateLocked && optimisticDecision.localAccepted
          && !chrome.runtime.lastError && response?.ok) {
          rememberCommittedIdentity(optimisticDecision.identity);
          optimisticDecision.retryStateLocked = false;
          optimisticDecision.providerWriteState = "working";
        }
        previousPayload = "";
        refreshSelection(true);
      });
      return;
    }
    const summaryFilterButton = event.target.closest("[data-ea-summary-filter]");
    if (summaryFilterButton) {
      event.preventDefault();
      activeSummaryFilter = summaryFilterButton.getAttribute("data-ea-summary-filter") || "needs_attention_items";
      openFirstSummaryItemIfHelpful(activeSummaryFilter);
      return;
    }
    const openQueueFinderButton = event.target.closest("[data-ea-action='open-queue-finder']");
    if (openQueueFinderButton) {
      event.preventDefault();
      queueFinderOpen = true;
      renderState(lastHarnessState);
      document.getElementById("ea-queue-query")?.focus({ preventScroll: true });
      return;
    }
    const clearQueueFilterButton = event.target.closest("[data-ea-action='clear-queue-filter']");
    if (clearQueueFilterButton) {
      event.preventDefault();
      queueQuery = "";
      queueFinderOpen = true;
      renderState(lastHarnessState);
      document.getElementById("ea-queue-query")?.focus({ preventScroll: true });
      return;
    }
    const queueHelpButton = event.target.closest("[data-ea-action='toggle-queue-help']");
    if (queueHelpButton) {
      event.preventDefault();
      queueHelpOpen = !queueHelpOpen;
      renderState(lastHarnessState);
      document.querySelector("[data-ea-action='toggle-queue-help']")?.focus({ preventScroll: true });
      return;
    }
    const queueItemButton = event.target.closest("[data-ea-queue-item]");
    if (queueItemButton) {
      event.preventDefault();
      const item = findQueueItem(queueItemButton.getAttribute("data-ea-queue-item") || "");
      openQueuePreviewItem(item, "queue_finder");
      return;
    }
    const queueNavigationButton = event.target.closest("[data-ea-queue-nav]");
    if (queueNavigationButton) {
      event.preventDefault();
      if (queueNavigationButton.disabled) {
        return;
      }
      const direction = queueNavigationButton.getAttribute("data-ea-queue-nav") === "previous" ? -1 : 1;
      openQueuePreviewItem(adjacentQueueItem(direction), "queue_navigation");
      return;
    }
    const returnQueueHomeButton = event.target.closest("[data-ea-action='return-queue-home']");
    if (returnQueueHomeButton) {
      event.preventDefault();
      return returnQueuePreviewToHome();
    }
    const summaryItemButton = event.target.closest("[data-ea-summary-item]");
    if (summaryItemButton) {
      if (event.target.closest("[data-ea-open-gmail]")) {
        return;
      }
      event.preventDefault();
      const item = findSummaryItem(summaryItemButton.getAttribute("data-ea-summary-item") || "");
      openItemPreview(item);
      return;
    }
    const changedItemButton = event.target.closest("[data-ea-changed-item]");
    if (changedItemButton) {
      event.preventDefault();
      const messageId = changedItemButton.getAttribute("data-ea-changed-item") || "";
      const item = findSummaryItem(messageId) || findChangedTodayItem(messageId);
      openItemPreview(item);
      return;
    }
    const openSelectedGmailButton = event.target.closest("[data-ea-action='open-selected-gmail']");
    if (openSelectedGmailButton) {
      event.preventDefault();
      return openSelectedEmailInGmail();
    }
    const openChangedGmailButton = event.target.closest("[data-ea-open-changed-gmail]");
    if (openChangedGmailButton) {
      event.preventDefault();
      const messageId = openChangedGmailButton.getAttribute("data-ea-open-changed-gmail") || "";
      return openGmailItem(findSummaryItem(messageId) || findChangedTodayItem(messageId));
    }
    const relatedItemButton = event.target.closest("[data-ea-related-item]");
    if (relatedItemButton) {
      event.preventDefault();
      const item = findSummaryItem(relatedItemButton.getAttribute("data-ea-related-item") || "");
      openItemPreview(item);
      return;
    }
    const queueButton = event.target.closest("[data-ea-action='open-needs-attention']");
    if (queueButton) {
      event.preventDefault();
      forcedHome = false;
      forcedHomeLiveContext = null;
      activeSummaryFilter = "needs_attention_items";
      ANALYTICS?.openReviewQueue(Number((lastSidebarState?.daily_summary || {}).needs_attention_count || 0));
      openFirstSummaryItemIfHelpful(activeSummaryFilter);
      return;
    }
    const returnHomeAfterReceiptButton = event.target.closest("[data-ea-action='return-home-after-receipt']");
    if (returnHomeAfterReceiptButton) {
      return openThreadwiseHome(event);
    }
    const confirmHandledButton = event.target.closest("[data-ea-action='confirm-handled-and-next']");
    if (confirmHandledButton) {
      event.preventDefault();
      confirmHandledButton.disabled = true;
      confirmHandledButton.setAttribute("aria-busy", "true");
      confirmHandledButton.textContent = "Opening next…";
      return confirmHandledAndOpenNext();
    }

    const teachFutureAfterReceiptButton = event.target.closest("[data-ea-action='teach-future-after-receipt']");
    if (teachFutureAfterReceiptButton) {
      event.preventDefault();
      selectedDecisionMode = "future-learning";
      futureLearningError = "";
      renderState(lastHarnessState);
      document.getElementById("ea-future-note")?.focus();
      return;
    }

    const backToCurrentReceiptButton = event.target.closest("[data-ea-action='back-to-current-receipt']");
    if (backToCurrentReceiptButton) {
      event.preventDefault();
      syncTeachDraftFromDom();
      selectedDecisionMode = "review";
      futureLearningError = "";
      renderState(lastHarnessState);
      return;
    }

    const saveFutureRuleButton = event.target.closest("[data-ea-action='save-future-rule']");
    if (saveFutureRuleButton) {
      event.preventDefault();
      syncTeachDraftFromDom();
      if (!String(teachDraft.note || "").trim()) {
        futureLearningError = "Describe what Threadwise should remember before saving the rule.";
        renderState(lastHarnessState);
        document.getElementById("ea-future-note")?.focus();
        return;
      }
      futureLearningError = "";
      return startTeachApply("save-future-rule");
    }

    const finishFutureLearningButton = event.target.closest("[data-ea-action='finish-future-learning']");
    if (finishFutureLearningButton) {
      event.preventDefault();
      selectedDecisionMode = "review";
      teachFlowState = "teaching";
      teachResult = null;
      teachOutcome = null;
      teachWriteThrough = null;
      teachDraft = { targetLabel: "", note: "" };
      previousPayload = "";
      refreshSelection(true);
      return;
    }
    const openAffectedReviewButton = event.target.closest("[data-ea-action='open-affected-review']");
    if (openAffectedReviewButton) {
      event.preventDefault();
      affectedReviewOpen = true;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const collapseAffectedReviewButton = event.target.closest("[data-ea-action='collapse-affected-review']");
    if (collapseAffectedReviewButton) {
      event.preventDefault();
      affectedReviewOpen = false;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const openAffectedGmailButton = event.target.closest("[data-ea-open-affected-gmail]");
    if (openAffectedGmailButton) {
      event.preventDefault();
      const messageId = openAffectedGmailButton.getAttribute("data-ea-open-affected-gmail") || "";
      const item = affectedReviewItemsFromPreview(teachPreview).find((candidate) => candidate.message_id === messageId);
      return openGmailItem(item);
    }
    const excludeAffectedButton = event.target.closest("[data-ea-exclude-affected]");
    if (excludeAffectedButton) {
      event.preventDefault();
      const messageId = excludeAffectedButton.getAttribute("data-ea-exclude-affected") || "";
      const reasonNode = document.querySelector(`[data-ea-exclusion-reason="${CSS.escape(messageId)}"]`);
      return excludeAffectedMatch(messageId, reasonNode?.value || "");
    }
    const amendmentButton = event.target.closest("[data-ea-amendment-decision]");
    if (amendmentButton) {
      event.preventDefault();
      const decision = amendmentButton.getAttribute("data-ea-amendment-decision") || "";
      ANALYTICS?.decideSuggestion(decision === "accept" ? "approve" : "reject");
      return decideRuleAmendment(decision);
    }
    const previewButton = event.target.closest("[data-ea-action='preview-teach']");
    if (previewButton) {
      event.preventDefault();
      if (isTeachPending()) {
        return;
      }
      selectedDecisionMode = "teach-preview";
      return previewTeach();
    }
    const acceptSuggestionButton = event.target.closest("[data-ea-action='accept-suggestion']");
    if (acceptSuggestionButton) {
      event.preventDefault();
      const suggestedLabel = decisionSuggestedLabelId(lastSidebarState?.selected_email);
      if (!suggestedLabel) {
        return;
      }
      teachDraft = { targetLabel: suggestedLabel, note: "" };
      selectedDecisionMode = "review";
      return startTeachApply("current-only");
    }
    const changeSuggestionButton = event.target.closest("[data-ea-action='change-suggestion']");
    if (changeSuggestionButton) {
      event.preventDefault();
      selectedDecisionMode = "change";
      selectedDecisionConflict = "";
      teachDraft = {
        targetLabel: decisionSuggestedLabelId(lastSidebarState?.selected_email),
        targetLabelExplicit: false,
        note: "",
      };
      if (lastSidebarState) renderState(lastSidebarState);
      document.getElementById("ea-target-label")?.focus();
      return;
    }
    const retryCurrentApplyButton = event.target.closest("[data-ea-action='retry-current-apply']");
    if (retryCurrentApplyButton) {
      event.preventDefault();
      currentApplyError = "";
      selectedDecisionMode = "review";
      document.querySelector("[data-ea-queue-navigation]")?.focus({ preventScroll: true });
      return startTeachApply("current-only");
    }
    const editCurrentApplyButton = event.target.closest("[data-ea-action='edit-current-apply']");
    if (editCurrentApplyButton) {
      event.preventDefault();
      currentApplyError = "";
      teachFlowState = "teaching";
      selectedDecisionMode = "change";
      selectedDecisionConflict = "";
      if (lastSidebarState) renderState(lastSidebarState);
      document.getElementById("ea-target-label")?.focus();
      return;
    }
    const cancelCurrentChangeButton = event.target.closest("[data-ea-action='cancel-current-change']");
    if (cancelCurrentChangeButton) {
      event.preventDefault();
      selectedDecisionMode = "review";
      autoHandledChangeOpen = false;
      selectedDecisionConflict = "";
      teachDraft = { targetLabel: "", note: "" };
      if (lastSidebarState) renderState(lastSidebarState);
      document.querySelector("[data-ea-action='change-suggestion'], [data-ea-action='change-auto-handled']")?.focus();
      return;
    }
    const previewCurrentChangeButton = event.target.closest("[data-ea-action='preview-current-change']");
    if (previewCurrentChangeButton) {
      event.preventDefault();
      syncTeachDraftFromDom();
      teachDraft.targetLabel = internalLabelId(teachDraft.targetLabel);
      if (!teachDraft.targetLabel && !String(teachDraft.note || "").trim()) {
        selectedDecisionConflict = "Choose a label or describe the correction in the note.";
        if (lastSidebarState) renderState(lastSidebarState);
        document.getElementById("ea-teach-note")?.focus();
        return;
      }
      selectedDecisionConflict = labelConflictForDraft();
      if (selectedDecisionConflict) {
        if (lastSidebarState) renderState(lastSidebarState);
        return;
      }
      if (!String(teachDraft.note || "").trim()) {
        teachDraft.note = defaultManualRuleNote();
      }
      selectedDecisionMode = "teach-preview";
      return previewTeach();
    }
    const editCurrentChangeButton = event.target.closest("[data-ea-action='edit-current-change']");
    if (editCurrentChangeButton) {
      event.preventDefault();
      selectedDecisionMode = "change";
      selectedDecisionConflict = "";
      teachPreview = null;
      teachResult = null;
      teachFlowState = "teaching";
      inboxApplyConfirmOpen = false;
      affectedReviewOpen = false;
      if (lastSidebarState) renderState(lastSidebarState);
      document.getElementById("ea-target-label")?.focus();
      return;
    }
    const retryPreviewButton = event.target.closest("[data-ea-action='retry-preview-teach']");
    if (retryPreviewButton) {
      event.preventDefault();
      if (isTeachPending()) {
        return;
      }
      return previewTeach();
    }
    const forceLlmReviewButton = event.target.closest("[data-ea-action='force-llm-review']");
    if (forceLlmReviewButton) {
      event.preventDefault();
      if (isTeachPending()) {
        return;
      }
      forceLlmReviewRequested = true;
      return previewTeach();
    }
    const clearButton = event.target.closest("[data-ea-action='clear-teach']");
    if (clearButton) {
      event.preventDefault();
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = null;
      teachFlowState = "teaching";
      inboxApplyConfirmOpen = false;
      teachOutcome = null;
      teachWriteThrough = null;
      affectedReviewOpen = false;
      teachDraft = { targetLabel: "", note: "" };
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const acceptTeachRuleButton = event.target.closest("[data-ea-action='accept-teach-rule']");
    if (acceptTeachRuleButton) {
      event.preventDefault();
      ANALYTICS?.decideSuggestion("approve");
      teachFlowState = "scope-confirmation";
      inboxApplyConfirmOpen = false;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const refineButton = event.target.closest("[data-ea-action='refine-teach']");
    if (refineButton) {
      event.preventDefault();
      ANALYTICS?.decideSuggestion("edit");
      previousTeachPreview = teachPreview;
      teachPreview = null;
      teachResult = null;
      teachFlowState = "refining";
      selectedDecisionMode = "change";
      inboxApplyConfirmOpen = false;
      teachOutcome = null;
      teachWriteThrough = null;
      affectedReviewOpen = false;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const changeAutoHandledButton = event.target.closest("[data-ea-action='change-auto-handled']");
    if (changeAutoHandledButton) {
      event.preventDefault();
      autoHandledChangeOpen = true;
      selectedDecisionMode = "change";
      teachFlowState = "teaching";
      teachDraft = {
        targetLabel: internalLabelId(lastSidebarState?.selected_email?.internal_label || lastSidebarState?.selected_email?.classification || ""),
        note: "",
      };
      if (lastSidebarState) {
        renderState(lastSidebarState);
        document.getElementById("ea-target-label")?.focus();
      }
      return;
    }
    const confirmInboxApplyButton = event.target.closest("[data-ea-action='confirm-inbox-apply']");
    if (confirmInboxApplyButton) {
      event.preventDefault();
      if (!inboxApplyConfirmOpen || !teachPreview?.inbox_backfill?.requires_confirmation) {
        return;
      }
      return startTeachApply("apply-included");
    }
    const cancelInboxApplyButton = event.target.closest("[data-ea-action='cancel-inbox-apply']");
    if (cancelInboxApplyButton) {
      event.preventDefault();
      inboxApplyConfirmOpen = false;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const scopeChoiceButton = event.target.closest("[data-ea-scope-choice]");
    if (scopeChoiceButton) {
      event.preventDefault();
      if (isTeachPending() || scopeChoiceButton.disabled) {
        return;
      }
      selectedTeachScope = scopeChoiceButton.getAttribute("data-ea-scope-choice") || "current-only";
      affectedReviewOpen = false;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const confirmSelectedScopeButton = event.target.closest("[data-ea-action='confirm-selected-scope']");
    if (confirmSelectedScopeButton) {
      event.preventDefault();
      if (isTeachPending()) {
        return;
      }
      if (selectedTeachScope === "apply-included") {
        affectedReviewOpen = true;
        if (lastSidebarState) {
          renderState(lastSidebarState);
        }
        return;
      }
      return startTeachApply(selectedTeachScope);
    }
    const applyButton = event.target.closest("[data-ea-apply]");
    if (applyButton) {
      event.preventDefault();
      if (isTeachPending()) {
        return;
      }
      const mode = applyButton.getAttribute("data-ea-apply");
      if (mode === "apply-included" && teachPreview?.inbox_backfill?.requires_confirmation && !affectedReviewOpen) {
        if (!inboxApplyConfirmOpen) {
          inboxApplyConfirmOpen = true;
          if (lastSidebarState) {
            renderState(lastSidebarState);
          }
        }
        return;
      }
      return startTeachApply(mode);
    }
    const detailsButton = event.target.closest("[data-ea-action='toggle-details']");
    if (detailsButton) {
      event.preventDefault();
      if (detailsButton.hasAttribute("data-ea-explanation-disclosure")) {
        explanationFocusPending = true;
      }
      detailsExpanded = !detailsExpanded;
      if (lastSidebarState) {
        renderState(lastSidebarState);
      }
      return;
    }
    const returnButton = event.target.closest("[data-ea-action='return-to-live']");
    if (returnButton) {
      event.preventDefault();
      const wasQueuePreview = queuePreviewActive;
      if (wasQueuePreview) {
        leaveQueueFlow();
      }
      manualPreviewContext = null;
      manualPreviewOriginContext = null;
      forcedHome = false;
      forcedHomeLiveContext = null;
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = null;
      affectedReviewOpen = false;
      previousPayload = "";
      if (lastHarnessState) {
        lastSidebarState = lastHarnessState.sidebar_state || lastSidebarState;
        renderState(lastHarnessState);
      }
      refreshSelection(true);
    }
  }

  function openFirstSummaryItemIfHelpful(filter, { preserveProgressionStatus = false, currentIdentity = null } = {}) {
    const current = currentIdentity || currentReviewIdentity();
    const items = progressionItemsForFilter(filter, { includeCommitted: true });
    const next = REVIEW_PROGRESSION.nextEligibleItem({
      items,
      activeProvider: ACTIVE_PROVIDER,
      currentIdentity: current,
      committedIdentities: committedReviewIdentities,
    });
    if (!next) {
      if (filter === "needs_attention_items" && queueQuery) {
        forcedHome = true;
        forcedHomeLiveContext = lastLiveContext ? { ...lastLiveContext } : null;
        manualPreviewContext = null;
        manualPreviewOriginContext = null;
        queuePreviewActive = false;
        queueFinderOpen = true;
        resetPerEmailInteraction();
        if (lastHarnessState) {
          renderState(lastHarnessState);
        }
        renderMinimized();
        return false;
      }
      const syntheticToken = REVIEW_PROGRESSION.createRequestToken({
        generation: ++reviewProgressionGeneration,
        kind: "queue-check",
        identity: current,
      });
      beginProgressionCheck(filter, filter === "needs_attention_items" ? queueQuery : "");
      if (progressionCheck) {
        progressionCheck.sourceToken = syntheticToken.token;
      }
      return false;
    }
    return openItemPreview(next, {
      queueContext: filter === "needs_attention_items",
      preserveProgressionStatus,
    });
  }

  function handlePanelInput(event) {
    if (event.target?.id === "ea-queue-query") {
      queueQuery = event.target.value || "";
      queueFinderOpen = true;
      renderState(lastHarnessState);
      const queryInput = document.getElementById("ea-queue-query");
      queryInput?.focus({ preventScroll: true });
      if (typeof queryInput?.setSelectionRange === "function") {
        const cursor = Math.min(queueQuery.length, queryInput.value.length);
        queryInput.setSelectionRange(cursor, cursor);
      }
      return;
    }
    if (event.target?.id === "ea-target-label" && event.type === "change") {
      teachDraft.targetLabelExplicit = true;
    }
    if (
      event.target?.id === "ea-target-label" ||
      event.target?.id === "ea-teach-note" ||
      event.target?.id === "ea-future-note"
    ) {
      syncTeachDraftFromDom();
    }
    if (event.target?.id === "ea-feedback-note") {
      feedbackDraft = event.target.value || "";
    }
  }

  async function previewTeach() {
    if (!lastSidebarState || !lastSidebarState.selected_email || !lastSidebarState.selected_email.found) {
      return;
    }
    if (isTeachPending()) {
      return;
    }
    syncTeachDraftFromDom();
    const forceLlmReview = forceLlmReviewRequested;
    forceLlmReviewRequested = false;
    selectedTeachScope = "current-only";
    const targetLabel = teachDraft.targetLabel;
    const note = teachDraft.note;
    const requestId = ++teachPreviewRequestId;
    teachFlowState = "previewing";
    teachResult = teachPendingResult("preview");
    teachPreview = null;
    inboxApplyConfirmOpen = false;
    teachOutcome = null;
    teachWriteThrough = null;
    affectedReviewOpen = false;
    renderState(lastHarnessState || lastSidebarState);
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-preview",
      method: "POST",
      body: {
        selected_context: lastSidebarState.selected_context || {},
        target_label: targetLabel,
        target_label_explicit: Boolean(teachDraft.targetLabelExplicit),
        note,
        scope: "sender",
        force_llm_review: forceLlmReview,
      },
    }, (response) => {
      if (requestId !== teachPreviewRequestId) {
        return;
      }
      if (chrome.runtime.lastError) {
        teachResult = teachErrorResult("preview", chrome.runtime.lastError.message || "Could not preview the lesson.");
        teachPreview = null;
        teachFlowState = "preview-error";
        affectedReviewOpen = false;
      } else if (!response || !response.ok) {
        teachResult = teachErrorResult("preview", response || "Could not preview the lesson.");
        teachPreview = null;
        teachFlowState = "preview-error";
        affectedReviewOpen = false;
      } else {
        teachResult = null;
        teachPreview = response.payload;
        const previewTargetLabel = internalLabelId(response.payload?.target_label || response.payload?.proposed_label || (response.payload?.selected_label_after || [])[0] || "");
        if (previewTargetLabel) {
          teachDraft.targetLabel = previewTargetLabel;
        }
        teachFlowState = "rule-proposed";
        inboxApplyConfirmOpen = false;
        teachOutcome = null;
        teachWriteThrough = null;
        affectedReviewOpen = false;
      }
      renderState(lastHarnessState || lastSidebarState);
      if (teachPreview && requestId === teachPreviewRequestId) {
        loadTeachPreviewImpact(teachPreview, requestId);
      }
    });
  }

  function loadTeachPreviewImpact(initialPreview, requestId) {
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-preview-impact",
      method: "POST",
      body: { preview: initialPreview },
    }, (response) => {
      if (requestId !== teachPreviewRequestId) {
        return;
      }
      if (chrome.runtime.lastError || !response?.ok) {
        teachPreview = {
          ...initialPreview,
          inbox_backfill: {
            ...(initialPreview.inbox_backfill || {}),
            state: "unavailable",
          },
        };
        renderState(lastHarnessState || lastSidebarState);
        return;
      }
      teachPreview = response.payload;
      renderState(lastHarnessState || lastSidebarState);
    });
  }

  function confirmHandledAndOpenNext() {
    if (handledProgressionFlight) {
      return false;
    }
    const current = currentReviewIdentity();
    const nextFilter = handledAcknowledgementModel().filter;
    const requestContext = { ...(lastSidebarState?.selected_context || {}) };
    const token = REVIEW_PROGRESSION.createRequestToken({
      generation: ++reviewProgressionGeneration,
      kind: "handled-review-acknowledge",
      identity: current,
    });
    handledProgressionFlight = {
      token,
      identity: current,
      hostAnchor: currentProgressionHostAnchor(),
    };
    handledAdvanceError = "";
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/handled-review-acknowledge",
      method: "POST",
      body: {
        selected_context: requestContext,
      },
    }, (response) => {
      if (!handledProgressionFlight || handledProgressionFlight.token.token !== token.token) {
        return;
      }
      if (!progressionFlightHostIsCurrent(token)) {
        releaseStaleProgressionFlight(token);
        return;
      }
      const responseState = response?.payload?.harness_state?.sidebar_state || null;
      const requestMayRender = progressionResponseCanRender(token, responseState);
      const displayMayRender = progressionDisplayCanRender(token);
      if (chrome.runtime.lastError || !response?.ok) {
        rejectProgressionResponse(token);
        if (!requestMayRender && !displayMayRender) {
          if (displayedStateIsSettled()) {
            renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
          }
          return;
        }
        handledAdvanceError = `${friendlyErrorMessage(
          chrome.runtime.lastError?.message || response?.payload?.error || response?.error || "Could not save this review.",
        )} Threadwise kept this email in the review flow. Try again.`;
        renderState(lastHarnessState || lastSidebarState);
        return;
      }
      if (!progressionResponseIsAuthoritative(token, responseState)) {
        rejectProgressionResponse(token);
        if (displayedStateIsSettled()) {
          renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
        }
        return;
      }
      rememberCommittedIdentity(token.identity);
      optimisticDecision = {
        token,
        identity: token.identity,
        localAccepted: true,
        decisionKind: token.kind,
        providerWriteState: "done",
        retryStateLocked: false,
        flightActive: false,
        advanceDone: true,
        responseReceived: true,
        responseAccepted: true,
      };
      handledProgressionFlight = null;
      recordSuggestionDecisionOnce("approve");
      if (!requestMayRender) {
        if (displayedStateIsSettled()) {
          renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
        }
        return;
      }
      renderState(response.payload?.harness_state || lastHarnessState || lastSidebarState);
      openFirstSummaryItemIfHelpful(nextFilter, {
        preserveProgressionStatus: true,
        currentIdentity: token.identity,
      });
    });
    return true;
  }

  function startTeachApply(mode) {
    if (applyInFlight || !lastSidebarState?.selected_email?.found) {
      return false;
    }
    syncTeachDraftFromDom();
    const previewTargetLabel = internalLabelId(teachPreview?.target_label || teachPreview?.proposed_label || (teachPreview?.selected_label_after || [])[0] || "");
    if (previewTargetLabel) {
      teachDraft.targetLabel = previewTargetLabel;
    }
    currentApplyError = "";
    const requestSnapshot = {
      sidebarState: lastSidebarState,
      selectedContext: { ...(lastSidebarState.selected_context || {}) },
      targetLabel: teachDraft.targetLabel,
      note: teachDraft.note,
      approvedLabelChange: hasApprovedSelectedEmailLabelChange(teachPreview)
        ? REVIEW_PROGRESSION.cloneSerializable(teachPreview.label_change)
        : null,
    };
    let progressionToken = null;
    if (mode === "current-only") {
      progressionToken = beginCurrentDecisionProgression(mode, requestSnapshot);
      if (!progressionToken) {
        return false;
      }
    }
    teachPreviewRequestId += 1;
    applyInFlight = true;
    activeTeachApplyMode = mode;
    teachFlowState = "applying";
    teachResult = teachPendingResult("apply", mode);
    if (lastHarnessState || lastSidebarState) {
      renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
    }
    applyTeach(mode, progressionToken, requestSnapshot);
    return true;
  }

  function reconcileCurrentApplyAfterTransportFailure(rawError, expectedLabels, requestIdentity, retriesRemaining = 4) {
    const selectedContext = { ...(lastSidebarState?.selected_context || {}) };
    chrome.runtime.sendMessage({
      type: "email-agent:get-state",
      context: selectedContext,
    }, (response) => {
      if (requestIdentity && !progressionFlightIsCurrent(requestIdentity)) {
        return;
      }
      if (requestIdentity && !progressionFlightHostIsCurrent(requestIdentity)) {
        releaseStaleProgressionFlight(requestIdentity);
        return;
      }
      const payload = response?.payload;
      const sidebarState = payload?.sidebar_state || {};
      const selected = sidebarState.selected_email || {};
      const sameMessage = Boolean(requestIdentity && REVIEW_PROGRESSION.responseMatchesToken(requestIdentity, {
        generation: requestIdentity.generation,
        identity: progressionIdentity(sidebarState, selected),
      }));
      const confirmation = REVIEW_PROGRESSION.recoveryConfirmation({
        responseOk: Boolean(response?.ok),
        sameMessage,
        selected,
        expectedLabels,
        requestId: requestIdentity?.token || "",
      });
      if (confirmation.localAccepted) {
        rememberCommittedIdentity(requestIdentity.identity);
        teachPreview = null;
        previousTeachPreview = null;
        teachResult = {
          kind: "apply-success",
          title: confirmation.confirmed ? "Change confirmed" : "Change saved",
          message: confirmation.confirmed
            ? "Threadwise confirmed the completed Gmail change after reconnecting."
            : "Threadwise saved your decision. The Gmail update needs a background retry.",
        };
        teachFlowState = "result";
        teachOutcome = {
          scope: "current-email",
          current_email_changed_locally: true,
          current_email_written_to_gmail: confirmation.confirmed,
          local_decision_accepted: true,
          provider_confirmation: confirmation.confirmed,
          provider_write_queued: confirmation.providerFailed,
          gmail_label_write_failed: confirmation.providerFailed ? 1 : 0,
        };
        teachWriteThrough = {
          label_write_applied: confirmation.confirmed ? 1 : 0,
          label_write_failed: confirmation.providerFailed ? 1 : 0,
          inbox_removed: confirmation.inboxRemoved ? 1 : 0,
          inbox_remove_failed: 0,
        };
        currentApplyError = "";
        if (optimisticDecision?.token?.token === requestIdentity.token) {
          optimisticDecision.localAccepted = true;
          optimisticDecision.providerWriteState = confirmation.confirmed ? "done" : "retry";
          optimisticDecision.retryStateLocked = confirmation.providerFailed;
          optimisticDecision.responseReceived = true;
          optimisticDecision.responseAccepted = true;
          optimisticDecision.flightActive = false;
        }
        recordCommittedCurrentDecision();
        advanceAfterCommittedDecision(requestIdentity);
        return;
      }
      if (response?.ok && sameMessage && retriesRemaining > 0) {
        window.setTimeout(
          () => reconcileCurrentApplyAfterTransportFailure(
            rawError,
            expectedLabels,
            requestIdentity,
            retriesRemaining - 1,
          ),
          500,
        );
        return;
      }
      rollbackSynchronousDecision(
        requestIdentity,
        `${friendlyErrorMessage(rawError)} Threadwise checked again but could not confirm that the change completed.`,
      );
    });
  }

  async function applyTeach(mode, requestToken, requestSnapshot = null) {
    const requestState = requestSnapshot?.sidebarState || lastSidebarState;
    if (!requestState || !requestState.selected_email || !requestState.selected_email.found) {
      applyInFlight = false;
      return;
    }
    syncTeachDraftFromDom();
    const ruleScope = mode === "apply-included" || mode === "matching-existing"
      ? "included_existing"
      : mode === "save-future-rule" || mode === "future-only"
        ? "future_email"
        : "current_email";
    const affectedCount = mode === "apply-included" || mode === "matching-existing"
      ? Number(teachPreview?.impact?.matching_existing_count || 0) + 1
      : mode === "save-future-rule"
        ? 0
        : 1;
    const previousQueueSize = Number((requestState.daily_summary || {}).needs_attention_count || 0);
    ANALYTICS?.confirmRule(ruleScope, affectedCount, false);
    const targetLabel = requestSnapshot?.targetLabel || teachDraft.targetLabel;
    const note = requestSnapshot?.note ?? teachDraft.note;
    const approvedLabelChange = requestSnapshot?.approvedLabelChange
      || (hasApprovedSelectedEmailLabelChange(teachPreview) ? teachPreview.label_change : null);
    const expectedLabels = Array.isArray(approvedLabelChange?.labels_after)
      ? approvedLabelChange.labels_after
      : [targetLabel].filter(Boolean);
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-apply",
      method: "POST",
      body: {
        selected_context: requestSnapshot?.selectedContext || requestState.selected_context || {},
        target_label: targetLabel,
        note,
        scope: "sender",
        mode,
        request_id: requestToken?.token || "",
        defer_provider_write: mode !== "save-future-rule",
        included_message_ids: mode === "apply-included"
          ? affectedReviewItemsFromPreview(teachPreview).map((item) => item.message_id).filter(Boolean)
          : [],
        approved_label_change: approvedLabelChange,
      },
    }, (response) => {
      if (requestToken && !progressionFlightIsCurrent(requestToken)) {
        return;
      }
      if (requestToken && !progressionFlightHostIsCurrent(requestToken)) {
        releaseStaleProgressionFlight(requestToken);
        return;
      }
      applyInFlight = false;
      const transportError = chrome.runtime.lastError?.message || "";
      const rawError = transportError || (response && (response.payload?.error || response.error)) || "Could not apply the lesson.";
      const responseState = response?.payload?.sidebar_state || null;
      const requestMayRender = requestToken
        ? progressionResponseCanRender(requestToken, responseState)
        : true;
      const displayMayRender = requestToken
        ? progressionDisplayCanRender(requestToken)
        : true;
      if (requestToken && optimisticDecision?.token?.token === requestToken.token
        && !transportError && response?.ok
        && !progressionResponseIsAuthoritative(requestToken, responseState)) {
        const completionBlocked = invalidateCompletionForDecisionFailure(
          requestToken,
          "Threadwise rejected a response for the wrong email or thread. The decision remains retryable.",
        );
        if (!completionBlocked) {
          rejectProgressionResponse(requestToken);
          if (displayedStateIsSettled()) {
            renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
          }
        } else {
          teachFlowState = "teaching";
          selectedDecisionMode = "review";
        }
        return;
      }
      if (requestToken && optimisticDecision?.token?.token === requestToken.token) {
        optimisticDecision.responseReceived = true;
        optimisticDecision.responseAccepted = !transportError && Boolean(response?.ok);
        if (optimisticDecision.responseAccepted) {
          optimisticDecision.localAccepted = true;
          rememberCommittedIdentity(requestToken.identity);
          recordCommittedCurrentDecision();
          updateOptimisticDecisionLifecycle(response?.payload?.sidebar_state || lastSidebarState);
          optimisticDecision.flightActive = false;
          advanceAfterCommittedDecision(requestToken);
          return;
        } else if (transportError) {
          return reconcileCurrentApplyAfterTransportFailure(
            transportError,
            expectedLabels,
            requestToken,
          );
        } else {
          const completionBlocked = invalidateCompletionForDecisionFailure(
            requestToken,
            "The final decision was not confirmed. Threadwise kept this email eligible and needs a fresh queue check.",
          );
          if (completionBlocked) {
            optimisticDecision.flightActive = false;
            return;
          }
          markOptimisticDecisionRetry(requestToken);
        }
        if (!optimisticDecision.advanceDone) {
          if (!optimisticDecision.responseAccepted) {
            rollbackSynchronousDecision(requestToken, rawError);
          }
          return;
        }
        if (progressionCheck) {
          if (!optimisticDecision.responseAccepted) {
            supersedeProgressionCheckWithDecisionFailure(
              progressionCheck.generation,
              "The final decision was not confirmed. Threadwise kept this email eligible and needs a fresh queue check.",
            );
          }
          optimisticDecision.flightActive = false;
          return;
        }
        if (!requestMayRender && (!displayMayRender || optimisticDecision.responseAccepted)) {
          optimisticDecision.flightActive = false;
          if (displayedStateIsSettled()) {
            renderCurrentStatePreservingFocus(lastHarnessState || lastSidebarState);
          }
          return;
        }
      }
      if (transportError) {
        teachResult = teachErrorResult("apply", transportError || "Could not apply the lesson.");
        teachFlowState = mode === "save-future-rule" || mode === "current-only" ? "teaching" : "scope-confirmation";
        if (mode === "save-future-rule") {
          futureLearningError = teachResult.message;
        } else if (mode === "current-only") {
          return reconcileCurrentApplyAfterTransportFailure(
            transportError || "Could not apply the change.",
            expectedLabels,
            requestToken,
          );
        }
        renderState(lastHarnessState || lastSidebarState);
        return;
      }
      if (!response || !response.ok) {
        teachResult = teachErrorResult("apply", response || rawError);
        teachFlowState = mode === "save-future-rule" || mode === "current-only" ? "teaching" : "scope-confirmation";
        if (mode === "save-future-rule") {
          futureLearningError = teachResult.message;
        } else if (mode === "current-only") {
          return reconcileCurrentApplyAfterTransportFailure(rawError, expectedLabels, requestToken);
        }
        renderState(lastHarnessState || lastSidebarState);
        return;
      }
      const payload = response.payload || {};
      if (requestToken) {
        optimisticDecision.flightActive = false;
      }
      teachPreview = null;
      previousTeachPreview = null;
      teachResult = {
        kind: "apply-success",
        title: "Lesson applied",
        message: payload.acknowledgment || "Lesson applied.",
      };
      teachFlowState = "result";
      teachOutcome = payload.outcome
        ? {
            ...payload.outcome,
            local_decision_accepted: mode === "current-only" || Boolean(payload.outcome.local_decision_accepted),
            provider_write_queued: mode === "current-only"
              && payload.outcome.provider_confirmation !== true,
          }
        : null;
      teachWriteThrough = payload.provider_write || payload.gmail_write_through || null;
      futureLearningError = "";
      currentApplyError = "";
      inboxApplyConfirmOpen = false;
      affectedReviewOpen = false;
      const remainingQueueSize = Number((payload.sidebar_state?.daily_summary || {}).needs_attention_count || 0);
      if (previousQueueSize > 0 && remainingQueueSize === 0) {
        ANALYTICS?.completeReviewBatch(previousQueueSize);
      }
      renderState(preserveHarnessQueues(payload.sidebar_state || lastSidebarState));
    });
    if (mode !== "save-future-rule" && mode !== "current-only") {
      applyInFlight = false;
    }
  }

  function mergeCoverageReviewQueue(items, count) {
    const queue = Array.isArray(items) ? items : [];
    const nextSummary = {
      ...((lastHarnessState?.sidebar_state || lastSidebarState || {}).daily_summary || {}),
      needs_attention_count: Number(count || queue.length),
    };
    lastHarnessState = {
      ...(lastHarnessState || {}),
      needs_attention_items: queue,
      recent_items: queue,
      sidebar_state: {
        ...(lastHarnessState?.sidebar_state || lastSidebarState || {}),
        daily_summary: nextSummary,
      },
    };
    lastSidebarState = lastHarnessState.sidebar_state;
  }

  function startCoverageCheck() {
    if (coverageCheckInFlight) {
      return false;
    }
    coverageCheckInFlight = true;
    coverageDetailsOpen = false;
    coverageState = COVERAGE.normalize({ ...coverageState, status: "checking", error: "" });
    renderState(lastHarnessState || lastSidebarState);
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/provider-coverage-check",
      method: "POST",
      body: { provider: ACTIVE_PROVIDER },
    }, (response) => {
      coverageCheckInFlight = false;
      const connectionKind = response?.connection_state?.kind || "";
      if (chrome.runtime.lastError || !response?.ok) {
        coverageState = COVERAGE.normalize({
          ...coverageState,
          status: connectionKind && connectionKind !== "ready" ? "offline" : "failed",
          previous_status: coverageState.previous_status || "",
          error: friendlyErrorMessage(
            chrome.runtime.lastError?.message || response?.payload?.error || response?.error || "Could not check inbox.",
          ),
        });
        renderState(lastHarnessState || lastSidebarState);
        return;
      }
      coverageState = COVERAGE.normalize(response.payload || {});
      renderState(lastHarnessState || lastSidebarState);
    });
    return true;
  }

  function openCoverageQueue() {
    const items = coverageState.review_items || [];
    if (!items.length) {
      return false;
    }
    mergeCoverageReviewQueue(items, coverageState.needs_review_count);
    activeSummaryFilter = "needs_attention_items";
    forcedHome = false;
    if (coverageSyntheticNavigation) {
      return openItemPreview(items[0], { queueContext: false, origin: "provider_coverage" });
    }
    manualPreviewContext = null;
    manualPreviewOriginContext = null;
    queuePreviewActive = false;
    openGmailItem(items[0]);
    previousPayload = "";
    refreshSelection(true);
    return true;
  }

  function triggerProviderSync({ refreshCoverageAfter = false } = {}) {
    if (gmailCheckPending) {
      return;
    }
    gmailCheckPending = true;
    gmailCheckResult = null;
    if (lastHarnessState) {
      renderState(lastHarnessState);
    }
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/provider-sync-run",
      method: "POST",
      body: {
        confirmed: "true",
        provider: ACTIVE_PROVIDER,
        batch_size: ACTIVE_PROVIDER === "protonmail" ? 25 : 50,
      },
    }, (response) => {
      gmailCheckPending = false;
      if (chrome.runtime.lastError) {
        gmailCheckResult = {
          kind: "provider-sync-error",
          title: `${activeProviderName()} sync did not start`,
          message: chrome.runtime.lastError.message || `Could not start a ${activeProviderName()} sync.`,
        };
        if (lastHarnessState) {
          renderState(lastHarnessState);
        }
        return;
      }
      if (!response || !response.ok) {
        gmailCheckResult = {
          kind: "provider-sync-error",
          title: `${activeProviderName()} sync did not start`,
          message: (response && (response.payload?.error || response.error)) || `Could not start a ${activeProviderName()} sync.`,
        };
        if (lastHarnessState) {
          renderState(lastHarnessState);
        }
        return;
      }
      const syncSummary = response.payload?.result || {};
      const repairedCount = Number(syncSummary.reprocessed_count || 0);
      const syncWasRepair = syncSummary.outcome === "repaired_existing";
      gmailCheckResult = {
        kind: "provider-sync-success",
        title: `${activeProviderName()} sync finished`,
        message: syncWasRepair
          ? `Threadwise rechecked ${repairedCount} older unresolved message${repairedCount === 1 ? "" : "s"}. Checking this email again now.`
          : `Threadwise synced new ${activeProviderName()} messages. Checking this email again now.`,
      };
      previousPayload = "";
      refreshSelection(true);
      if (refreshCoverageAfter) {
        window.setTimeout(() => startCoverageCheck(), 250);
      }
    });
  }

  async function excludeAffectedMatch(messageId, reason) {
    if (!lastSidebarState || !teachPreview || !messageId) {
      return;
    }
    syncTeachDraftFromDom();
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-exclude",
      method: "POST",
      body: {
        selected_context: lastSidebarState.selected_context || {},
        target_label: teachDraft.targetLabel,
        note: teachDraft.note,
        scope: "sender",
        excluded_message_id: messageId,
        reason,
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        teachResult = teachErrorResult("apply", chrome.runtime.lastError.message || "Could not save the exception.");
      } else if (!response || !response.ok) {
        teachResult = teachErrorResult("apply", response || "Could not save the exception.");
      } else {
        const payload = response.payload || {};
        teachPreview = payload.preview || teachPreview;
        affectedReviewOpen = true;
        teachResult = {
          kind: "exclude-success",
          title: "Exception saved",
          message: "This rule will not apply to this email/pattern later.",
        };
      }
      renderState((response && response.payload && response.payload.sidebar_state) || lastSidebarState);
    });
  }

  async function decideRuleAmendment(decision) {
    if (!lastSidebarState || !teachPreview || !teachPreview.amendment_proposal || !decision) {
      return;
    }
    syncTeachDraftFromDom();
    chrome.runtime.sendMessage({
      type: "email-agent:api",
      path: "/api/teach-amendment",
      method: "POST",
      body: {
        selected_context: lastSidebarState.selected_context || {},
        target_label: teachDraft.targetLabel,
        note: teachDraft.note,
        scope: "sender",
        amendment: teachPreview.amendment_proposal,
        decision,
      },
    }, (response) => {
      if (chrome.runtime.lastError) {
        teachResult = teachErrorResult("apply", chrome.runtime.lastError.message || "Could not review the amendment.");
      } else if (!response || !response.ok) {
        teachResult = teachErrorResult("apply", response || "Could not review the amendment.");
      } else {
        const payload = response.payload || {};
        teachPreview = payload.preview || teachPreview;
        if (payload.note) {
          teachDraft = { ...teachDraft, note: payload.note };
        }
        affectedReviewOpen = true;
        teachResult = {
          kind: "amendment-success",
          title: payload.amendment_status === "accepted" ? "Amendment accepted" : "Amendment rejected",
          message: payload.acknowledgment || "Reviewed amendment.",
        };
      }
      renderState((response && response.payload && response.payload.sidebar_state) || lastSidebarState);
    });
  }

  function currentDraftTargetLabel(selected) {
    return teachDraft.targetLabel || "";
  }

  function syncTeachDraftFromDom() {
    const selectNode = document.getElementById("ea-target-label");
    const noteNode = document.getElementById("ea-teach-note");
    const futureNoteNode = document.getElementById("ea-future-note");
    teachDraft = {
      targetLabel: selectNode?.value || teachDraft.targetLabel || "",
      targetLabelExplicit: Boolean(teachDraft.targetLabelExplicit),
      note: noteNode ? noteNode.value : futureNoteNode ? futureNoteNode.value : teachDraft.note || "",
    };
  }

  function affectedReviewItemsFromPreview(preview) {
    const impact = (preview || {}).impact || {};
    return impact.matching_existing_items || impact.matching_existing_examples || [];
  }

  function renderAffectedReviewHtml(preview) {
    if (!affectedReviewOpen || !preview) {
      return "";
    }
    const items = affectedReviewItemsFromPreview(preview);
    const rows = items.length
      ? items.map((item) => `
        <tr style="border-top:1px solid #e2d8c6;">
          <td style="padding:9px 8px;vertical-align:top;font-weight:760;overflow-wrap:anywhere;">${escapeHtml(item.sender || "(unknown sender)")}</td>
          <td style="padding:9px 8px;vertical-align:top;overflow-wrap:anywhere;">${escapeHtml(item.subject || "(no subject)")}</td>
          <td style="padding:9px 8px;vertical-align:top;color:#6b6255;">${escapeHtml((item.labels_before || []).join(", ") || "Uncategorized")}</td>
          <td style="padding:9px 8px;vertical-align:top;color:#0f766e;font-weight:800;">${escapeHtml((item.labels_after || []).map(humanLabelNameFromId).join(", ") || "Uncategorized")}</td>
          <td style="padding:9px 8px;vertical-align:top;">
            <div style="display:grid;gap:7px;">
              <button type="button" data-ea-open-affected-gmail="${escapeHtml(item.message_id || "")}" style="border:0;background:transparent;color:#5d5342;border-radius:0;padding:0;cursor:pointer;font:inherit;font-weight:760;text-align:left;text-decoration:underline;text-underline-offset:3px;box-shadow:none;">Open in ${escapeHtml(activeProviderName())}</button>
              <button type="button" data-ea-exclude-affected="${escapeHtml(item.message_id || "")}" style="border:2px solid #241812;background:#fff4dd;color:#241812;border-radius:9px;padding:6px 8px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Exclude</button>
              <details style="color:#6b6255;">
                <summary style="cursor:pointer;">Why?</summary>
                <textarea data-ea-exclusion-reason="${escapeHtml(item.message_id || "")}" placeholder="Optional reason" style="box-sizing:border-box;width:100%;min-height:54px;margin-top:6px;border:1px solid #d8cbb7;border-radius:8px;background:#fffdf7;color:#241812;font:inherit;padding:6px;"></textarea>
              </details>
            </div>
          </td>
        </tr>
      `).join("")
      : `
        <tr>
          <td colspan="5" style="padding:12px 8px;color:#6b6255;">No exact affected emails are available in the current stored preview.</td>
        </tr>
      `;
    return `
      <div data-ea-affected-review="true" style="box-sizing:border-box;width:100%;min-width:0;margin-top:12px;border:3px solid #241812;border-radius:14px;background:#fffdf7;overflow:hidden;box-shadow:3px 3px 0 rgba(36,24,18,.22);">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;border-bottom:3px solid #241812;background:#fff4d7;">
          <div>
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b6255;">Reviewing affected emails</div>
            <div style="margin-top:4px;font-weight:850;">${escapeHtml(preview.plain_english_rule || "Pending future rule")}</div>
          </div>
          <button type="button" data-ea-action="collapse-affected-review" style="border:2px solid #241812;background:#e9efe2;color:#241812;border-radius:11px;padding:8px 11px;cursor:pointer;font:inherit;font-weight:800;box-shadow:2px 2px 0 #241812;">Collapse</button>
        </div>
        <div style="padding:12px 14px;color:#6b6255;line-height:1.45;">Exact affected list from Threadwise's preview. Excluding a row saves an exact exception for this rule/email before any broader apply.</div>
        <div style="overflow:auto;max-height:360px;">
          <table style="width:100%;border-collapse:collapse;font-size:0.86rem;line-height:1.35;">
            <thead>
              <tr style="text-align:left;background:#f5efe2;color:#6b6255;">
                <th style="padding:8px;">Sender</th>
                <th style="padding:8px;">Subject</th>
                <th style="padding:8px;">Current</th>
                <th style="padding:8px;">Proposed</th>
                <th style="padding:8px;">Inspect</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  function humanDecisionSource(reviewAction) {
    if (!reviewAction) {
      return "No prior decision recorded";
    }
    return {
      "auto-approve": "Auto-approved by current rules",
      approve: "Previously reviewed locally",
      "sidebar-current-only": "Taught on this email only",
      "sidebar-matching-existing": "Taught and rewrote matching stored emails",
      "sidebar-future-only": "Saved as a future lesson",
    }[reviewAction] || reviewAction.replaceAll("-", " ");
  }

  function humanWriteStatus(writeStatus) {
    if (!writeStatus) {
      return `Not written to ${activeProviderName()}`;
    }
    return {
      applied: `Written to ${activeProviderName()}`,
      skipped: `Skipped ${activeProviderName()} write`,
      failed: `${activeProviderName()} write failed`,
    }[writeStatus] || writeStatus;
  }

  function humanInboxStatus(inboxStatus) {
    if (!inboxStatus) {
      return "Inbox unchanged";
    }
    return {
      applied: "Removed from inbox",
      skipped: "Left in inbox",
      failed: "Inbox update failed",
    }[inboxStatus] || inboxStatus;
  }

  function installTestHooks() {
    globalThis.__eaTestHooks = {
      getSnapshot() {
        return {
          previousPayload,
          activeSummaryFilter,
          manualPreviewContext,
          forcedHome,
          forcedHomeLiveContext,
          detailsExpanded,
          lastLiveContext,
          selectedContext: lastSidebarState?.selected_context || {},
          selectedEmail: lastSidebarState?.selected_email || null,
          queueQuery,
          queueFinderOpen,
          queueHelpOpen,
          queuePreviewActive,
          pendingQueueNavigationFocus: Boolean(pendingQueueNavigationFocus),
          queueProvider,
          queueCurrentIdentity: manualPreviewContext?.message_id || "",
          queueMatchCount: filteredQueueItems().length,
          recentCount: (lastHarnessState?.recent_items || []).length,
          needsAttentionCount: (lastHarnessState?.needs_attention_items || []).length,
          contextActionsOpen,
          contextActionsActiveIndex,
          contextActionsGeneration,
          reviewProgressionGeneration,
          stateReadGeneration,
          refreshInFlight,
          connectionPollInFlight,
          pendingRefreshAfterConnectionPoll: Boolean(pendingRefreshAfterConnectionPoll),
          connectionRetryInFlight,
          connectionRetryFeedback,
          connectionKind: lastConnectionState.kind,
          optimisticDecision: optimisticDecision
            ? {
                token: optimisticDecision.token?.token || "",
                identity: optimisticDecision.identity,
                decisionKind: optimisticDecision.decisionKind || "",
                localAccepted: Boolean(optimisticDecision.localAccepted),
                providerWriteState: optimisticDecision.providerWriteState || "",
                retryStateLocked: Boolean(optimisticDecision.retryStateLocked),
                advanceDone: Boolean(optimisticDecision.advanceDone),
                responseReceived: Boolean(optimisticDecision.responseReceived),
                responseAccepted: optimisticDecision.responseAccepted,
              }
            : null,
          committedReviewIdentities: committedReviewIdentities.map((identity) => ({ ...identity })),
          progressionCheck: progressionCheck ? { ...progressionCheck } : null,
          handledProgressionFlight: Boolean(handledProgressionFlight),
        };
      },
      getCoverageState() {
        return {
          ...COVERAGE.model(coverageState),
          checkInFlight: coverageCheckInFlight,
          detailsOpen: coverageDetailsOpen,
        };
      },
      setCoverageState(state) {
        coverageCheckInFlight = state?.status === "checking";
        coverageState = COVERAGE.normalize(state || { status: "unknown" });
        if (!state?.preserve_surface) {
          forcedHome = true;
          manualPreviewContext = null;
          queuePreviewActive = false;
        }
        renderState(lastHarnessState || lastSidebarState);
        return { ok: true, state: COVERAGE.model(coverageState) };
      },
      startCoverageCheckForTest() {
        return { ok: startCoverageCheck() };
      },
      openCoverageQueueForTest() {
        return { ok: openCoverageQueue() };
      },
      setCoverageSyntheticNavigation(enabled) {
        coverageSyntheticNavigation = Boolean(enabled);
        return { ok: true, enabled: coverageSyntheticNavigation };
      },
      getContextActions() {
        return {
          open: contextActionsOpen,
          activeIndex: contextActionsActiveIndex,
          generation: contextActionsGeneration,
          items: contextActionItems().map((item) => ({
            id: item.getAttribute("data-ea-context-item") || "",
            label: item.textContent || "",
            action: item.getAttribute("data-ea-action") || "",
            href: item.getAttribute("href") || "",
            tabindex: item.getAttribute("tabindex") || "",
          })),
        };
      },
      getContextActionPolicy() {
        return contextActionPolicyInput(contextActionsWorkspaceMode());
      },
      getOnboardingState() {
        return {
          ...onboardingState,
          visible: onboardingVisible,
          target: onboardingTarget(),
        };
      },
      setFounderFeedbackVisible(visible) {
        founderFeedbackVisible = Boolean(visible);
        if (!founderFeedbackVisible) {
          feedbackOpen = false;
        }
        renderMinimized();
        renderFeedbackPanel();
        return { ok: true, visible: founderFeedbackVisible };
      },
      selectSummaryItem(messageId) {
        const item = findSummaryItem(messageId);
        if (!item) {
          return { ok: false, error: "item-not-found" };
        }
        openItemPreview(item);
        return { ok: true, messageId: item.message_id || "", subject: item.subject || "" };
      },
      selectSummaryFilter(filter) {
        if (!filter) {
          return { ok: false, error: "missing-filter" };
        }
        activeSummaryFilter = filter;
        openFirstSummaryItemIfHelpful(filter);
        return { ok: true, filter };
      },
      startProgressionCheck(filter = "needs_attention_items", query = "") {
        activeSummaryFilter = filter;
        return { ok: true, generation: beginProgressionCheck(filter, query) };
      },
      setDraft(targetLabel, note) {
        if (typeof targetLabel === "string" && targetLabel) {
          teachDraft.targetLabel = targetLabel;
        }
        if (typeof note === "string") {
          teachDraft.note = note;
        }
        const selectNode = document.getElementById("ea-target-label");
        const noteNode = document.getElementById("ea-teach-note");
        if (selectNode && teachDraft.targetLabel) {
          selectNode.value = teachDraft.targetLabel;
        }
        if (noteNode) {
          noteNode.value = teachDraft.note;
        }
        return { ok: true, draft: { ...teachDraft } };
      },
      getDraft() {
        syncTeachDraftFromDom();
        return { ...teachDraft };
      },
      showTeachScope(preview) {
        teachPreview = preview || null;
        teachFlowState = teachPreview ? "scope-confirmation" : "teaching";
        selectedDecisionMode = teachPreview ? "teach-scope" : "review";
        inboxApplyConfirmOpen = false;
        if (lastHarnessState || lastSidebarState) {
          renderState(lastHarnessState || lastSidebarState);
        }
        return { ok: Boolean(teachPreview) };
      },
      showTeachPreview(preview) {
        teachPreview = preview || { target_label: "work", selected_label_after: ["work"] };
        teachFlowState = "previewing";
        selectedDecisionMode = "teach-preview";
        if (lastHarnessState || lastSidebarState) {
          renderState(lastHarnessState || lastSidebarState);
        }
        return { ok: true };
      },
      showTeachError(operation = "preview", failure = {}) {
        teachPreview = null;
        teachResult = teachErrorResult(operation, failure);
        teachFlowState = operation === "preview" ? "preview-error" : "teaching";
        selectedDecisionMode = operation === "preview" ? "teach-preview" : "change";
        if (lastHarnessState || lastSidebarState) {
          renderState(lastHarnessState || lastSidebarState);
        }
        return { ok: true, result: { ...teachResult } };
      },
      showReceipt({ success = true, complete = false, inboxRemoved = true } = {}) {
        if (complete && lastHarnessState) {
          lastHarnessState = {
            ...lastHarnessState,
            needs_attention_items: [],
            sidebar_state: {
              ...(lastHarnessState.sidebar_state || {}),
              daily_summary: {
                ...(lastHarnessState.sidebar_state?.daily_summary || {}),
                needs_attention_count: 0,
              },
            },
          };
        }
        selectedDecisionMode = "review";
        currentApplyError = "";
        teachFlowState = "result";
        teachOutcome = {
          scope: "current-email",
          current_email_written_to_provider: Boolean(success),
          current_email_written_to_gmail: Boolean(success),
          provider_label_write_failed: success ? 0 : 1,
          gmail_label_write_failed: success ? 0 : 1,
        };
        teachWriteThrough = {
          label_write_failed: success ? 0 : 1,
          inbox_remove_failed: 0,
          inbox_removed: success && inboxRemoved ? 1 : 0,
        };
        renderState(lastHarnessState || lastSidebarState);
        return { ok: true, success: Boolean(success), complete: Boolean(complete) };
      },
      startApply(mode) {
        return { ok: startTeachApply(mode || "current-only"), mode: mode || "current-only" };
      },
      getApplyState() {
        return { applyInFlight, teachFlowState, selectedDecisionMode };
      },
      forceRefresh() {
        syncTeachDraftFromDom();
        refreshSelection(true);
        return { ok: true };
      },
      pollConnectionHealth() {
        pollConnectionHealth();
        return { ok: true };
      },
      previewTeach(targetLabel, note) {
        if (!lastSidebarState || !lastSidebarState.selected_email || !lastSidebarState.selected_email.found) {
          return { ok: false, error: "selected-email-not-found" };
        }
        teachDraft = {
          targetLabel: targetLabel || teachDraft.targetLabel || "",
          note: note || "",
        };
        const selectNode = document.getElementById("ea-target-label");
        const noteNode = document.getElementById("ea-teach-note");
        if (selectNode && targetLabel) {
          selectNode.value = targetLabel;
        }
        if (noteNode) {
          noteNode.value = note || "";
        }
        previewTeach();
        return {
          ok: true,
          targetLabel: teachDraft.targetLabel,
          note: teachDraft.note,
        };
      },
      returnToLive() {
        resetQueueState();
        manualPreviewContext = null;
        manualPreviewOriginContext = null;
        forcedHome = false;
        forcedHomeLiveContext = null;
        teachPreview = null;
        previousTeachPreview = null;
        teachResult = null;
        refreshSelection(true);
        return { ok: true };
      },
      openHome() {
        openThreadwiseHome();
        return { ok: true };
      },
      getQueueSnapshot() {
        const position = queuePreviewPosition();
        return {
          query: queueQuery,
          finderOpen: queueFinderOpen,
          helpOpen: queueHelpOpen,
          previewActive: queuePreviewActive,
          pendingFocus: Boolean(pendingQueueNavigationFocus),
          provider: queueProvider,
          currentMessageId: manualPreviewContext?.message_id || "",
          matchCount: position.items.length,
          position: position.index >= 0 ? position.index + 1 : null,
          total: position.items.length,
          items: position.items.map((item) => ({
            message_id: item.message_id || "",
            provider: item.provider || queueProvider,
          })),
        };
      },
      setQueueQuery(query) {
        queueQuery = typeof query === "string" ? query : "";
        queueFinderOpen = true;
        forcedHome = true;
        minimized = false;
        if (lastHarnessState) {
          renderState(lastHarnessState);
        }
        return this.getQueueSnapshot();
      },
      openQueueItem(messageId) {
        const item = findQueueItem(messageId);
        return { ok: openQueuePreviewItem(item, "queue_test_hook"), messageId: item?.message_id || "" };
      },
      navigateQueue(direction) {
        const item = adjacentQueueItem(direction === "previous" || direction === -1 ? -1 : 1);
        return { ok: openQueuePreviewItem(item, "queue_test_hook"), messageId: item?.message_id || "" };
      },
    };
  }

  function teardown() {
    companionLifecycleActive = false;
    connectionPollInFlight = false;
    pendingRefreshAfterConnectionPoll = null;
    if (refreshIntervalId !== null) {
      window.clearInterval(refreshIntervalId);
      refreshIntervalId = null;
    }
    if (understandingRefreshTimeoutId !== null) {
      window.clearTimeout(understandingRefreshTimeoutId);
      understandingRefreshTimeoutId = null;
    }
    clearProgressionRefreshTimer();
    if (hashChangeListener) {
      window.removeEventListener("hashchange", hashChangeListener);
      hashChangeListener = null;
    }
    if (popStateListener) {
      window.removeEventListener("popstate", popStateListener);
      popStateListener = null;
    }
    hostContextMutationObserver?.disconnect();
    hostContextMutationObserver = null;
    hostContextInvalidationMicrotaskPending = false;
    if (contextMenuResizeListener) {
      window.removeEventListener("resize", contextMenuResizeListener);
      contextMenuResizeListener = null;
    }
    contextMenuResizeObserver?.disconnect();
    contextMenuResizeObserver = null;
    if (contextActionFocusTimer !== null) {
      window.clearTimeout(contextActionFocusTimer);
      contextActionFocusTimer = null;
    }
    if (documentClickListener) {
      document.removeEventListener("click", documentClickListener, true);
      documentClickListener = null;
    }
    if (documentKeydownListener) {
      document.removeEventListener("keydown", documentKeydownListener, true);
      documentKeydownListener = null;
    }
    disarmContextEscapeRetreat();
    const root = document.getElementById(ROOT_ID);
    if (root && keyboardListener) {
      root.removeEventListener("keydown", keyboardListener);
    }
    keyboardListener = null;
    if (
      runtimeMessageListener &&
      chrome?.runtime?.onMessage &&
      typeof chrome.runtime.onMessage.removeListener === "function"
    ) {
      chrome.runtime.onMessage.removeListener(runtimeMessageListener);
    }
    runtimeMessageListener = null;
    if (root) {
      root.remove();
    }
    delete globalThis.__eaTestHooks;
    delete globalThis[SINGLETON_KEY];
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function reviewReceivedLabel(value) {
    if (!value) {
      return "";
    }
    const received = new Date(value);
    if (Number.isNaN(received.getTime())) {
      return "";
    }
    return `Received ${new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(received)}`;
  }

  boot();
})();
