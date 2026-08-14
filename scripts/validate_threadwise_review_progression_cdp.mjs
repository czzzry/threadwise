import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cdpBase = process.argv[2] || "http://127.0.0.1:9222";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionRoot = path.join(repoRoot, "extensions", "gmail_companion");
const artifactRoot = "/tmp/threadwise-review-progression";
const tracePath = path.join(artifactRoot, "review-progression-trace.json");
const appUrl = "http://127.0.0.1:8891/#inbox/FMreview-a";
const onboardingStorageKey = "threadwise_onboarding_state";
const onboardingVersion = "2026-08-09-v1";
const requestLogStorageKey = "__tw_review_progression_request_log";
const seededPageScrollY = 180;
const seededContentScrollTop = 72;
const viewports = [
  { name: "1280x800", width: 1280, height: 800 },
  { name: "756x469", width: 756, height: 469 },
  { name: "360x800", width: 360, height: 800 },
];

const reviewItems = [
  { provider: "gmail", message_id: "review-a", thread_id: "thread-review", subject: "Finance approval A", sender: "a@example.test", classification: "EA/Finance", suggested_label: "job-related", status_label: "Needs attention", status: "needs-attention" },
  { provider: "gmail", message_id: "review-b", thread_id: "thread-review", subject: "Finance approval B", sender: "b@example.test", classification: "EA/Finance", suggested_label: "job-related", status_label: "Needs attention", status: "needs-attention" },
  { provider: "gmail", message_id: "review-c", thread_id: "thread-review", subject: "Finance approval C", sender: "c@example.test", classification: "EA/Finance", suggested_label: "job-related", status_label: "Needs attention", status: "needs-attention" },
];
const refreshedReviewItem = { provider: "gmail", message_id: "review-d", thread_id: "thread-review", subject: "Finance approval D", sender: "d@example.test", classification: "EA/Finance", suggested_label: "job-related", status_label: "Needs attention", status: "needs-attention" };
const handledItems = [
  { provider: "gmail", message_id: "handled-a", thread_id: "thread-handled", subject: "Handled synthetic A", sender: "handled-a@example.test", internal_label: "spam-low-value", classification: "EA/LowValue", status: "auto-handled", status_label: "Auto-handled", reason: "Synthetic handled fixture.", details: { write_status: "applied", inbox_status: "applied" } },
  { provider: "gmail", message_id: "handled-b", thread_id: "thread-handled", subject: "Handled synthetic B", sender: "handled-b@example.test", internal_label: "spam-low-value", classification: "EA/LowValue", status: "auto-handled", status_label: "Auto-handled", reason: "Synthetic handled fixture.", details: { write_status: "applied", inbox_status: "applied" } },
];

const target = await createTarget(appUrl);
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;
let activeStep = "create-target";
let failure = null;
const results = {
  ok: false,
  tracePath,
  screenshots: [],
  viewportChecks: [],
  requestTrace: [],
  advancementTrace: [],
  focusTrace: [],
  scrollTrace: [],
  completionTrace: [],
  handledTrace: [],
  responseBoundaryTrace: [],
  lifecycleTrace: [],
  localSuccessTrace: [],
  recoveryTrace: [],
  filterTrace: [],
  keyboardTrace: [],
  raceTrace: [],
  forbiddenRequests: [],
};

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  message.error ? reject(new Error(message.error.message)) : resolve(message.result);
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

try {
  await fs.mkdir(artifactRoot, { recursive: true });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: appUrl });
  await waitFor(() => evaluate("document.readyState === 'complete'"));
  activeStep = "install-synthetic-review-bridge";
  await createSyntheticHost();
  await installBridge();
  await injectContentScript();
  await waitFor(() => evaluate("Boolean(document.getElementById('email-agent-companion-root'))"));
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getOnboardingState()?.status !== 'loading'"));
  await waitFor(() => evaluate("globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === 'review-a'"));

  const initial = await evaluate(`(() => ({
    minimized: document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'true',
    contentHidden: document.getElementById('ea-content')?.style.display === 'none',
  }))()`);
  assert(initial.minimized, "fresh synthetic mount remains minimized");
  assert(initial.contentHidden, "fresh synthetic mount hides content");

  activeStep = "enter-queue-preview";
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=review]')?.textContent.includes('Finance approval A')"));
  await evaluate("document.querySelector('#ea-brand-toggle').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"));
  await evaluate("document.querySelector('[data-ea-action=open-queue-finder]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('#ea-queue-query'))"));
  await evaluate("document.querySelector('[data-ea-queue-item=review-a]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-a' && Boolean(document.querySelector('[data-ea-queue-navigation]'))"));
  await seedScroll();

  activeStep = "first-decision-waits-for-local-acceptance";
  const firstBefore = await scrollSnapshot();
  const firstFocusBefore = await activeFocusSnapshot();
  await evaluate("(() => { const node = document.querySelector('[data-ea-queue-navigation]'); if (document.activeElement !== node) node?.focus({ preventScroll: true }); return true; })()");
  await evaluate("window.__reviewProgressionHoldStateRead('review-b')");
  await pressKey("Enter");
  const firstAfterKey = await scrollSnapshot();
  const firstRequestTrace = await requestTrace();
  assert(firstRequestTrace.filter((request) => request.path === "/api/teach-apply").length === 1, "first Enter sends exactly one teach-apply request");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-a'"), "review stays on A before local acceptance");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().optimisticDecision?.responseReceived === false"), "the decision remains unconfirmed before the held response");
  assertScrollUnchanged(firstBefore, firstAfterKey, "pending first decision");

  activeStep = "mismatched-local-response-stays-current";
  await evaluate("window.__reviewProgressionRespondApply('review-a', true, { omitThreadId: true })");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().optimisticDecision?.responseAccepted === false"));
  const rejectedSnapshot = await evaluate("globalThis.__eaTestHooks.getSnapshot()");
  assert(rejectedSnapshot.manualPreviewContext?.message_id === "review-a", "a mismatched local response cannot advance review");
  assert(!rejectedSnapshot.committedReviewIdentities.some((identity) => identity.messageId === "review-a"), "rejected local response keeps A eligible");
  results.responseBoundaryTrace.push({
    step: "known-thread-response-missing",
    response: "omitted-thread-id",
    logicalOutcome: "rejected-retryable",
    snapshot: rejectedSnapshot,
    evidence: await progressionEvidence("known-thread-response-missing", firstRequestTrace),
  });

  activeStep = "accepted-local-response-opens-next";
  const acceptedBefore = await requestTrace();
  await evaluate("document.querySelector('[data-ea-queue-navigation]')?.focus({ preventScroll: true })");
  await pressKey("Enter");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-a'"), "retry remains on A until its local response is accepted");
  await evaluate("window.__reviewProgressionRespondApply('review-a', true)");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b'"));
  const acceptedSnapshot = await evaluate("globalThis.__eaTestHooks.getSnapshot()");
  assert(acceptedSnapshot.optimisticDecision?.responseAccepted === true, "accepted local response records local acceptance");
  assert(acceptedSnapshot.committedReviewIdentities.some((identity) => identity.messageId === "review-a"), "accepted local response commits A");
  await evaluate("window.__reviewProgressionRespondState('review-b')");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b' && globalThis.__eaTestHooks.getSnapshot().optimisticDecision?.responseAccepted === true"));
  const acceptedEvidence = await progressionEvidence("accepted-local-response-on-next-item", acceptedBefore);
  assert(acceptedEvidence.currentIdentity.messageId === "review-b", "accepted local response opens B");
  assert(acceptedEvidence.requestDelta.added.filter((request) => request.path === "/api/teach-apply").length === 1, "accepted retry sends one teaching request");
  results.localSuccessTrace.push(acceptedEvidence);
  results.advancementTrace.push({ step: "first-decision", current: "review-b", evidence: acceptedEvidence });
  results.focusTrace.push({ step: "first-decision", before: firstFocusBefore, after: await activeFocusSnapshot() });
  results.scrollTrace.push({ step: "first-decision", before: firstBefore, after: await scrollSnapshot() });
  await captureViewportSet("review-next");

  activeStep = "filtered-pointer-and-keyboard-navigation";
  await evaluate("document.querySelector('[data-ea-queue-navigation]')?.focus({ preventScroll: true })");
  await pressKey("Escape");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]')) && Boolean(document.querySelector('#ea-queue-query'))"));
  const filterBefore = await requestTrace();
  await evaluate(`(() => {
    const input = document.querySelector('#ea-queue-query');
    input.value = 'finance';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().queueQuery === 'finance' && globalThis.__eaTestHooks.getSnapshot().queueMatchCount === 2"));
  await evaluate("document.querySelector('[data-ea-queue-item=review-b]')?.click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b' && Boolean(document.querySelector('[data-ea-queue-navigation]'))"));
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await seedScroll();
  results.filterTrace.push(await progressionEvidence("nonempty-filter-ready", filterBefore));

  const pointerBefore = await requestTrace();
  await evaluate("document.querySelector('[data-ea-queue-nav=next]')?.click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c'"));
  const pointerEvidence = await progressionEvidence("filtered-pointer-next", pointerBefore);
  assert(pointerEvidence.currentIdentity.messageId === "review-c", "pointer navigation advances within the nonempty filter");
  assert(pointerEvidence.query === "finance", "pointer navigation preserves the nonempty filter");
  results.filterTrace.push(pointerEvidence);

  const keyboardBefore = await requestTrace();
  await evaluate("document.querySelector('[data-ea-queue-navigation]')?.focus({ preventScroll: true })");
  await pressKey("k");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b'"));
  const kEvidence = await progressionEvidence("filtered-k-previous", keyboardBefore);
  await pressKey("j");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c'"));
  const jEvidence = await progressionEvidence("filtered-j-next", keyboardBefore);
  assert(kEvidence.currentIdentity.messageId === "review-b", "K moves to the previous item inside the nonempty filter");
  assert(jEvidence.currentIdentity.messageId === "review-c", "J moves to the next item inside the nonempty filter");
  assert(kEvidence.query === "finance" && jEvidence.query === "finance", "J/K preserve the nonempty filter");
  results.filterTrace.push(kEvidence, jEvidence);
  results.keyboardTrace.push({ step: "filtered-j-k", activation: "keyboard-j-k", evidence: [kEvidence, jEvidence] });
  await pressKey("k");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b'"));

  activeStep = "rejected-local-response-stays-on-current-item";
  const failureBefore = await requestTrace();
  const failureScrollBefore = await scrollSnapshot();
  await evaluate("(() => { const node = document.querySelector('[data-ea-queue-navigation]'); if (document.activeElement !== node) node?.focus({ preventScroll: true }); return true; })()");
  await pressKey("Enter");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b'"), "B stays current before its local response");
  await evaluate("window.__reviewProgressionRespondApply('review-b', false)");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b' && !globalThis.__eaTestHooks.getSnapshot().optimisticDecision"));
  assert(!(await evaluate("globalThis.__eaTestHooks.getSnapshot().committedReviewIdentities.some((identity) => identity.messageId === 'review-b')")), "a rejected response keeps B eligible");

  activeStep = "accepted-retry-opens-next-with-provider-retry-status";
  await evaluate("document.querySelector('[data-ea-queue-navigation]')?.focus({ preventScroll: true })");
  await pressKey("Enter");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-b'"), "B remains current until the retry is accepted");
  await evaluate("window.__reviewProgressionRespondApply('review-b', true)");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c' && Boolean(document.querySelector('[data-ea-previous-decision-status=retry]'))"));
  assert(await evaluate("document.querySelector('[data-ea-selected-state=review]')?.textContent.includes('Finance approval C')"), "accepted retry opens C");
  const failureEvidence = await progressionEvidence("provider-failure-on-next-item", failureBefore);
  assert(failureEvidence.currentIdentity.messageId === "review-c", "accepted retry evidence keeps the next item current");
  assert(failureEvidence.query === "finance", "provider failure preserves the nonempty filter");
  assert(failureEvidence.requestDelta.added.filter((request) => request.path === "/api/teach-apply").length === 2, "rejection and accepted retry each send one teaching request");
  assertScrollUnchanged(failureScrollBefore, failureEvidence.scroll, "provider failure");
  results.recoveryTrace.push(failureEvidence);
  results.advancementTrace.push({
    step: "middle-item-decision",
    from: "review-b",
    current: failureEvidence.currentIdentity.messageId,
    excludedCommittedIdentity: "review-b",
    neverWrapsOrReopens: "review-a",
    query: failureEvidence.query,
    evidence: failureEvidence,
  });
  const staleFollowUpBefore = await requestTrace();
  await evaluate("window.__reviewProgressionSetAsyncFollowUp(true); window.__eaTestHooks.forceRefresh()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().optimisticDecision?.providerWriteState === 'retry'"));
  const staleFollowUpEvidence = await progressionEvidence("provider-retry-beats-stale-follow-up-done", staleFollowUpBefore);
  assert(await evaluate("Boolean(document.querySelector('[data-ea-previous-decision-status=retry]'))"), "stale async follow-up done does not clear the retryable previous decision");
  assert(staleFollowUpEvidence.snapshot.optimisticDecision?.providerWriteState === "retry", "provider-write retry remains authoritative beside the stale follow-up");
  results.lifecycleTrace.push({
    step: "provider-retry-versus-async-follow-up-done",
    evidence: staleFollowUpEvidence,
    snapshot: await evaluate("globalThis.__eaTestHooks.getSnapshot()"),
  });
  await captureViewportSet("provider-retry-stale-follow-up");
  await evaluate("window.__reviewProgressionSetAsyncFollowUp(false)");
  await captureViewportSet("provider-failure");

  await returnToQueueHomePreservingFilter();
  const providerRetrySurface = await evaluate("({ body: document.body.innerText.slice(-1800), activities: Array.from(document.querySelectorAll('[data-ea-activity-item]')).map((node) => node.textContent), retry: Boolean(document.querySelector('[data-ea-action=retry-provider-write]')) })");
  assert(providerRetrySurface.retry, `provider retry surface is present: ${JSON.stringify(providerRetrySurface)}`);
  const retryBefore = await requestTrace();
  await evaluate("document.querySelector('[data-ea-action=retry-provider-write]')?.focus({ preventScroll: true })");
  const retryFocusBefore = await activeFocusSnapshot();
  await pressKey("Enter");
  await waitFor(async () => (await requestTrace()).filter((request) => request.path === "/api/provider-write-retry").length > retryBefore.filter((request) => request.path === "/api/provider-write-retry").length);
  await evaluate("document.querySelector('[data-ea-action=open-queue-finder]')?.click()");
  await waitFor(() => evaluate("document.querySelector('#ea-queue-query')?.value === 'finance'"));
  await evaluate("document.querySelector('[data-ea-queue-item=review-c]')?.click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c' && Boolean(document.querySelector('[data-ea-queue-navigation]'))"));
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  const retryRecoveredScroll = await seedScroll();
  await evaluate("document.querySelector('[data-ea-queue-navigation]')?.focus({ preventScroll: true })");
  const retryEvidence = await progressionEvidence("provider-write-retry", retryBefore);
  assert(retryEvidence.currentIdentity.messageId === "review-c", "provider retry evidence keeps the current review identity");
  assert(retryEvidence.query === "finance", "provider retry preserves the nonempty filter");
  assert(retryEvidence.requestDelta.added.filter((request) => request.path === "/api/provider-write-retry").length === 1, "provider retry evidence records one retry request");
  assert(retryFocusBefore.queue === false && retryFocusBefore.action === "retry-provider-write", "provider retry begins from the focused retry action");
  assert(retryEvidence.focus.queue === true, "provider retry restores focus to queue navigation");
  assertScrollUnchanged(retryRecoveredScroll, retryEvidence.scroll, "provider retry");
  results.recoveryTrace.push(retryEvidence);
  await captureViewportSet("provider-retry");
  await returnToQueueHomePreservingFilter();
  await evaluate("document.querySelector('[data-ea-action=open-queue-finder]')?.click()");
  await waitFor(() => evaluate("document.querySelector('#ea-queue-query')?.value === 'finance'"));

  activeStep = "filtered-empty-stays-filtered";
  const beforeFilterMiss = await requestTrace();
  await evaluate(`(() => {
    const input = document.querySelector('#ea-queue-query');
    input.value = 'not-loaded';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);
  await waitFor(() => evaluate("document.querySelector('[data-ea-queue-no-results]')?.textContent.includes('No loaded review emails match')"));
  const afterFilterMiss = await requestTrace();
  assert(afterFilterMiss.length === beforeFilterMiss.length, "filtering stays local and sends no refresh request");
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression]')")), "filter miss never renders queue completion state");
  const filterMissEvidence = await progressionEvidence("filter-miss", beforeFilterMiss);
  results.filterTrace.push(filterMissEvidence);
  assert(filterMissEvidence.query === "not-loaded", "filter miss evidence records the nonempty query");
  assert(filterMissEvidence.focus.id === "ea-queue-query", "filter miss leaves focus in the filter input");
  assert(filterMissEvidence.requestDelta.added.length === 0, "filter miss evidence records no request delta");
  await captureViewportSet("filter-miss");
  await evaluate("document.querySelector('[data-ea-action=clear-queue-filter]').click()");
  await waitFor(() => evaluate("document.querySelector('#ea-queue-query')?.value === ''"));
  await evaluate("document.querySelector('[data-ea-queue-item=review-c]')?.click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c' && Boolean(document.querySelector('[data-ea-queue-navigation]'))"));

  activeStep = "final-item-checking-and-new-item-reconciliation";
  await evaluate("window.__reviewProgressionConfigureCompletion(window.__reviewProgressionReviewCompletionStates())");
  await evaluate("window.__reviewProgressionCompletionMode = true");
  const completionBefore = await requestTrace();
  await evaluate("(() => { const node = document.querySelector('[data-ea-queue-navigation]'); if (document.activeElement !== node) node?.focus({ preventScroll: true }); return true; })()");
  await pressKey("Enter");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c'"), "the final item stays visible before local acceptance");
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression=review-progression-checking]')")), "queue checking does not start before local acceptance");

  activeStep = "final-local-rejection-stays-retryable";
  await evaluate("window.__reviewProgressionRespondApply('review-c', false)");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c' && !globalThis.__eaTestHooks.getSnapshot().optimisticDecision"));
  const finalFailureSnapshot = await evaluate("globalThis.__eaTestHooks.getSnapshot()");
  assert(!finalFailureSnapshot.committedReviewIdentities.some((identity) => identity.messageId === "review-c"), "rejected final decision remains eligible");
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression]')")), "rejected final decision never starts or completes a queue check");
  results.completionTrace.push({ step: "final-local-rejection", evidence: await progressionEvidence("final-local-rejection", completionBefore), snapshot: finalFailureSnapshot });
  await captureViewportSet("final-apply-failure");

  await evaluate("window.__reviewProgressionConfigureCompletion([window.__reviewProgressionMakeState(['review-d'])])");
  await evaluate("(() => { const node = document.querySelector('[data-ea-queue-navigation]'); if (document.activeElement !== node) node?.focus({ preventScroll: true }); return true; })()");
  const finalRetryBefore = await requestTrace();
  await pressKey("Enter");
  assert(await evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-c'"), "the final retry still waits for local acceptance");
  await evaluate("window.__reviewProgressionRespondApply('review-c', true)");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().progressionCheck?.status === 'checking'"));
  const checkingSnapshot = await evaluate("globalThis.__eaTestHooks.getSnapshot()");
  assert(checkingSnapshot.committedReviewIdentities.some((identity) => identity.messageId === "review-c"), "accepted final retry commits C before queue checking");
  const checkingEvidence = await progressionEvidence("final-item-checking", finalRetryBefore);
  results.completionTrace.push({ step: "checking-after-local-acceptance", evidence: checkingEvidence, snapshot: checkingSnapshot });
  await captureViewportSet("checking");
  await evaluate("window.__reviewProgressionRespondCompletion()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === 'review-d'"));
  assert(await evaluate("!document.querySelector('[data-ea-review-progression=review-progression-complete]')"), "a fresh eligible item prevents a false complete verdict after retry");
  results.completionTrace.push({ step: "retried-final-item-opens-next", evidence: await progressionEvidence("retried-final-item-opens-next", finalRetryBefore), snapshot: await evaluate("globalThis.__eaTestHooks.getSnapshot()") });

  activeStep = "null-authoritative-count-stays-unverified";
  await evaluate("window.__reviewProgressionConfigureCompletion([window.__reviewProgressionMakeState([], { dailyCount: null })])");
  await evaluate("window.__reviewProgressionCompletionMode = true; window.__eaTestHooks.startProgressionCheck('needs_attention_items')");
  const nullCountBefore = await requestTrace();
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-checking]')"));
  await evaluate("window.__reviewProgressionRespondCompletion()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-checking]')?.textContent.includes('fresh provider count')"));
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression=review-progression-complete]')")), "null authoritative count never verifies completion");
  await waitFor(() => evaluate("window.__reviewProgressionPendingCompletionCount() === 1"));
  const nullCountEvidence = await progressionEvidence("null-authoritative-count", nullCountBefore);
  assert(nullCountEvidence.snapshot.progressionCheck?.status === "checking", "null authoritative count remains in checking state");
  results.completionTrace.push({ step: "null-authoritative-count", evidence: nullCountEvidence, snapshot: nullCountEvidence.snapshot });
  await evaluate("window.__reviewProgressionRespondCompletionError()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-retry]')"));

  activeStep = "verified-queue-completion";
  await evaluate(`(() => {
    const states = window.__reviewProgressionReviewCompletionStates().slice(2);
    delete states[0].needs_attention_items;
    return window.__reviewProgressionConfigureCompletion(states);
  })()`);
  await evaluate("window.__reviewProgressionCompletionMode = true");
  await evaluate("window.__eaTestHooks.startProgressionCheck('needs_attention_items')");
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-checking]')"));
  await evaluate("window.__reviewProgressionRespondCompletion()");
  await waitFor(() => evaluate(`Boolean(document.querySelector('[data-ea-review-progression="review-progression-retry"]')?.textContent.includes('needs a retry')) && Boolean(document.querySelector('[data-ea-review-progression="review-progression-retry"] [data-ea-action="force-refresh"]'))`));
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression=review-progression-complete]')")), "a missing fresh queue field never claims the queue is complete");
  const retryTruth = await evaluate("({ body: document.body.innerText, headline: document.querySelector('[data-ea-selected-state=home]')?.textContent || '' })");
  assert(retryTruth.headline.includes("status unverified"), "retry Home explicitly marks the queue status unverified");
  assert(!retryTruth.headline.includes("No emails need review"), "retry Home does not claim no emails need review");
  assert(!retryTruth.body.includes("Gmail sync completed"), "retry Home does not claim Gmail sync completed");
  assert(!retryTruth.body.includes("handled everything automatically"), "retry Home does not claim Threadwise handled everything automatically");
  const completionErrorBeforeRetry = await requestTrace();
  results.completionTrace.push({ step: "completion-read-retry-error", evidence: await progressionEvidence("completion-read-retry-error", completionErrorBeforeRetry) });
  await captureViewportSet("completion-retry-missing-queue");
  const completionRetryBefore = await requestTrace();
  const completionReadsBeforeRetry = completionRetryBefore.filter((request) => request.type === "email-agent:get-state" && !request.identity).length;
  await evaluate("window.__reviewProgressionConfigureCompletion(window.__reviewProgressionReviewCompletionStates().slice(2))");
  await evaluate(`document.querySelector('[data-ea-review-progression="review-progression-retry"] [data-ea-action="force-refresh"]').focus({ preventScroll: true })`);
  const completionRetryFocusBefore = await activeFocusSnapshot();
  await pressKey("Enter");
  await waitFor(async () => (await requestTrace()).filter((request) => request.type === "email-agent:get-state" && !request.identity).length > completionReadsBeforeRetry);
  const completionRetryEvidence = await progressionEvidence("completion-read-retry-keyboard", completionRetryBefore);
  assert(completionRetryFocusBefore.action === "force-refresh", "completion retry begins from the focused retry action");
  assert(completionRetryEvidence.requestDelta.added.filter((request) => request.type === "email-agent:get-state" && !request.identity).length === 1, "completion retry sends one fresh state read");
  results.completionTrace.push({ step: "completion-read-retry", completionReadsBeforeRetry, evidence: completionRetryEvidence });
  results.keyboardTrace.push({ step: "completion-retry", activation: "keyboard-enter", evidence: completionRetryEvidence });
  await evaluate("window.__reviewProgressionRespondCompletion()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-complete]')?.textContent.includes('Review queue complete')"));
  assert(!(await evaluate("document.querySelector('[data-ea-action=open-needs-attention]')")), "verified completion offers no nonexistent Next action");
  results.completionTrace.push({ step: "verified-complete", evidence: await progressionEvidence("verified-complete", completionRetryBefore), snapshot: await evaluate("globalThis.__eaTestHooks.getSnapshot()") });
  await captureViewportSet("queue-complete");

  activeStep = "host-navigation-supersedes-pending-completion";
  await evaluate("window.__reviewProgressionConfigureCompletion([window.__reviewProgressionMakeState([], { dailyCount: 0 })])");
  await evaluate("window.__reviewProgressionCompletionMode = true; window.__eaTestHooks.startProgressionCheck('needs_attention_items')");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().progressionCheck?.status === 'checking'"));
  await evaluate("window.__reviewProgressionHoldStateRead('review-b')");
  const hostNavigationBefore = await requestTrace();
  const hostNavigationFocusBefore = await activeFocusSnapshot();
  const hostNavigationScrollBefore = await scrollSnapshot();
  const hostDomMutationBefore = await requestTrace();
  await setHostDomMessage("review-b", "Finance approval B", "b@example.test");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().progressionCheck === null && globalThis.__eaTestHooks.getSnapshot().forcedHome === false"));
  const hostDomMutationAfter = await requestTrace();
  assert(hostDomMutationAfter.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length === hostDomMutationBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length + 1, "DOM-only current-context mutation starts exactly one automatic current-context read");
  await setHostRoute("review-b");
  const hostNavigationAfter = await requestTrace();
  const hostNavigationSnapshot = await evaluate("globalThis.__eaTestHooks.getSnapshot()");
  assert(hostNavigationAfter.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length === hostNavigationBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length + 1, "host navigation starts exactly one current-context state read");
  assert(hostNavigationAfter.filter((request) => request.type === "email-agent:get-state" && !request.identity).length === hostNavigationBefore.filter((request) => request.type === "email-agent:get-state" && !request.identity).length, "host navigation starts no second completion read");
  assert(await evaluate("window.__reviewProgressionPendingStateReadCount('review-b') === 1"), "DOM mutation leaves exactly one current-context refresh callback pending");
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression=review-progression-complete]')")), "host navigation cancels pending completion instead of showing complete");
  assertScrollUnchanged(hostNavigationScrollBefore, await scrollSnapshot(), "host navigation during completion check");
  assert(JSON.stringify(hostNavigationFocusBefore) === JSON.stringify(await activeFocusSnapshot()), "host navigation during completion check preserves focus");
  const staleCompletionBefore = await requestTrace();
  const staleCompletionLifecycleBefore = await evaluate("(() => { const snapshot = globalThis.__eaTestHooks.getSnapshot(); return { progressionCheck: snapshot.progressionCheck, manualPreviewContext: snapshot.manualPreviewContext, forcedHome: snapshot.forcedHome, forcedHomeLiveContext: snapshot.forcedHomeLiveContext, optimisticDecision: snapshot.optimisticDecision, handledProgressionFlight: snapshot.handledProgressionFlight, reviewProgressionGeneration: snapshot.reviewProgressionGeneration }; })()");
  assert(await evaluate("window.__reviewProgressionRespondCompletion()"), "the superseded completion response remains dispatchable for the stale-response proof");
  const staleCompletionAfter = await requestTrace();
  assert(staleCompletionAfter.filter((request) => request.type === "email-agent:get-state" && !request.identity).length === staleCompletionBefore.filter((request) => request.type === "email-agent:get-state" && !request.identity).length, "stale completion response schedules no reread");
  assert(staleCompletionAfter.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length === staleCompletionBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length, "stale completion response schedules no duplicate current-context read");
  const staleCompletionLifecycleAfter = await evaluate("(() => { const snapshot = globalThis.__eaTestHooks.getSnapshot(); return { progressionCheck: snapshot.progressionCheck, manualPreviewContext: snapshot.manualPreviewContext, forcedHome: snapshot.forcedHome, forcedHomeLiveContext: snapshot.forcedHomeLiveContext, optimisticDecision: snapshot.optimisticDecision, handledProgressionFlight: snapshot.handledProgressionFlight, reviewProgressionGeneration: snapshot.reviewProgressionGeneration }; })()");
  assert(JSON.stringify(staleCompletionLifecycleAfter) === JSON.stringify(staleCompletionLifecycleBefore), "stale completion response changes no next-item or progression lifecycle state");
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression=review-progression-complete]')")), "stale completion response cannot mark the new host context complete");
  assert(!(await evaluate("document.querySelector('[data-ea-action=open-needs-attention]')")), "stale completion response cannot offer a next-item action");
  assert(!(await evaluate("document.querySelector('[data-ea-review-progression]')")), "stale completion response leaves no completion lifecycle surface behind");
  assertScrollUnchanged(hostNavigationScrollBefore, await scrollSnapshot(), "stale completion response");
  assert(JSON.stringify(hostNavigationFocusBefore) === JSON.stringify(await activeFocusSnapshot()), "stale completion response preserves focus");
  results.raceTrace.push({
    step: "stale-completion-after-dom-and-route-mutation-before-refresh-callback",
    before: hostNavigationBefore,
    domMutation: { before: hostDomMutationBefore, after: hostDomMutationAfter, automaticRefresh: true },
    after: staleCompletionAfter,
    snapshot: hostNavigationSnapshot,
    lifecycleBefore: staleCompletionLifecycleBefore,
    lifecycleAfter: staleCompletionLifecycleAfter,
    focusBefore: hostNavigationFocusBefore,
    focusAfter: await activeFocusSnapshot(),
    scrollBefore: hostNavigationScrollBefore,
    scrollAfter: await scrollSnapshot(),
  });
  const currentContextReadDeliveries = await evaluate("window.__reviewProgressionRespondState('review-b')");
  assert(currentContextReadDeliveries === 1, "host navigation delivers exactly one eventual current-context read");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'review-b' && globalThis.__eaTestHooks.getSnapshot().progressionCheck === null"));
  assert((await requestTrace()).filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length === hostNavigationBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length + 1, "eventual current-context response does not duplicate the host read");
  assertScrollUnchanged(hostNavigationScrollBefore, await scrollSnapshot(), "eventual current-context response");
  assert(JSON.stringify(hostNavigationFocusBefore) === JSON.stringify(await activeFocusSnapshot()), "eventual current-context response preserves focus");

  activeStep = "teardown-reinjection-idempotence";
  const reinjectionBefore = await requestTrace();
  await injectContentScript();
  await waitFor(() => evaluate("Boolean(globalThis.__eaTestHooks) && document.querySelectorAll('#email-agent-companion-root').length === 1 && globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'review-b'"));
  const reinjectionAfter = await requestTrace();
  assert(await evaluate("document.querySelectorAll('#email-agent-companion-root').length === 1"), "teardown/reinjection leaves exactly one companion root");
  assert(reinjectionAfter.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length === reinjectionBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-b").length + 1, "reinjection performs exactly one fresh current-context read");
  await evaluate("window.__reviewProgressionHoldStateRead('review-a'); window.__reviewProgressionHashchangeCount = 0; window.addEventListener('hashchange', () => { window.__reviewProgressionHashchangeCount += 1; }, { once: true });");
  const reinjectionHashBefore = await requestTrace();
  await setHostDomMessage("review-a", "Finance approval A", "a@example.test");
  await setHostRoute("review-a");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().lastLiveContext?.message_id === 'review-a'"));
  const reinjectionHashAfter = await requestTrace();
  assert(await evaluate("window.__reviewProgressionHashchangeCount === 1"), "reinjected companion observes one hashchange");
  assert(reinjectionHashAfter.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-a").length === reinjectionHashBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === "review-a").length + 1, "reinjected companion performs one hash-triggered current-context read");
  assert(await evaluate("window.__reviewProgressionPendingStateReadCount('review-a') === 1"), "reinjected companion has one pending hash-triggered read");
  assert((await evaluate("window.__reviewProgressionRespondState('review-a')")) === 1, "reinjected companion delivers one hash-triggered state response");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === 'review-a'"));
  results.lifecycleTrace.push({
    step: "teardown-reinjection-idempotence",
    rootCount: await evaluate("document.querySelectorAll('#email-agent-companion-root').length"),
    reinjectionRequests: reinjectionAfter.slice(reinjectionBefore.length),
    hashTriggeredRequests: reinjectionHashAfter.slice(reinjectionHashBefore.length),
  });
  await evaluate("document.getElementById('ea-brand-toggle')?.click()");
  await waitFor(() => evaluate("document.getElementById('email-agent-companion-root')?.dataset.eaMinimized === 'false' && document.getElementById('ea-content')?.style.display !== 'none'"));

  activeStep = "handled-acknowledgement-lifecycle";
  await evaluate("window.__reviewProgressionPhase = 'handled'; window.__reviewProgressionCompletionMode = false; window.__reviewProgressionResetHandledQueue()");
  await setHostMessage("handled-a", "Handled synthetic A", "handled-a@example.test");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')?.textContent.includes('Handled synthetic A')"));
  const handledButton = await evaluate("document.querySelector('[data-ea-action=confirm-handled-and-next]')?.textContent.trim() || ''");
  assert(handledButton === "Looks right · Next", "handled receipt offers Next when another handled item is eligible");
  const handledBeforeTrace = await requestTrace();
  const handledBefore = handledBeforeTrace.filter((request) => request.path === "/api/handled-review-acknowledge").length;
  const handledFocusReady = await evaluate("(() => { const node = document.querySelector('[data-ea-action=confirm-handled-and-next]'); node?.focus({ preventScroll: true }); return document.activeElement === node; })()");
  assert(handledFocusReady, "handled receipt keeps the primary action focusable for keyboard acknowledgement");
  await pressKey("Enter");
  await pressKey("Enter");
  assert((await requestTrace()).filter((request) => request.path === "/api/handled-review-acknowledge").length === handledBefore + 1, "duplicate handled keyboard activation sends one acknowledgement");
  assert((await evaluate("globalThis.__eaTestHooks.getSnapshot().handledProgressionFlight")) === true, "handled acknowledgement remains single-flight while pending");
  assert(await evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')?.textContent.includes('Handled synthetic A')"), "handled pending state stays on the current item");
  await evaluate("window.__reviewProgressionHoldStateRead('handled-b')");
  await setHostMessage("handled-b", "Handled synthetic B", "handled-b@example.test");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().lastLiveContext?.message_id === 'handled-b'"));
  await evaluate("document.querySelector('#ea-brand-toggle')?.focus({ preventScroll: true })");
  const handledLateAckBeforeState = await requestTrace();
  const handledLateAckFocusBefore = await activeFocusSnapshot();
  await evaluate("window.__reviewProgressionFailNextHandled(); window.__reviewProgressionRespondHandled('handled-a', false)");
  const handledLateAckAfterState = await requestTrace();
  const handledLateAckFocusAfter = await activeFocusSnapshot();
  assert(handledLateAckAfterState.filter((request) => request.type === "email-agent:get-state" && request.identity === "handled-b").length === handledLateAckBeforeState.filter((request) => request.type === "email-agent:get-state" && request.identity === "handled-b").length, "late handled acknowledgement does not initiate a second navigation read after host navigation changed");
  assert(JSON.stringify(handledLateAckFocusAfter) === JSON.stringify(handledLateAckFocusBefore), "late handled acknowledgement does not steal focus from the changed navigation");
  assert((await evaluate("globalThis.__eaTestHooks.getSnapshot().handledProgressionFlight")) === false, "late handled failure releases the acknowledgement flight");
  results.raceTrace.push({
    step: "handled-failure-after-navigation-before-state-read",
    before: handledLateAckBeforeState,
    after: handledLateAckAfterState,
    focusBefore: handledLateAckFocusBefore,
    focusAfter: handledLateAckFocusAfter,
    snapshot: await evaluate("globalThis.__eaTestHooks.getSnapshot()"),
  });
  await evaluate("window.__reviewProgressionRespondState('handled-b')");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')?.textContent.includes('Handled synthetic B')"));
  assert(!(await evaluate("document.querySelector('[data-ea-previous-decision-status=retry]')")), "late handled failure does not attach a stale acknowledgement error to the new host item");
  assert(!(await evaluate("document.querySelector('[data-ea-auto-handled-heading]')?.textContent.includes('Handled synthetic A')")), "late handled failure never renders the stale handled item");
  await captureViewportSet("handled-late-response-inert");
  const handledLateFailureEvidence = await progressionEvidence("handled-failure-after-navigation", handledBeforeTrace);
  results.handledTrace.push({ step: "handled-failure-after-navigation", activation: "keyboard-enter", acknowledgementCount: handledBefore + 1, staleResponseInert: true, evidence: handledLateFailureEvidence, snapshot: handledLateFailureEvidence.snapshot });
  results.responseBoundaryTrace.push({ step: "handled-failure-after-navigation", response: "discarded-after-navigation", evidence: handledLateFailureEvidence });

  await setHostMessage("handled-a", "Handled synthetic A", "handled-a@example.test");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')?.textContent.includes('Handled synthetic A')"));
  const handledSuccessBeforeTrace = await requestTrace();
  await evaluate("document.querySelector('[data-ea-action=confirm-handled-and-next]')?.focus({ preventScroll: true })");
  await evaluate("window.__reviewProgressionHoldStateRead('handled-b')");
  await pressKey("Enter");
  await setHostMessage("handled-b", "Handled synthetic B", "handled-b@example.test");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().lastLiveContext?.message_id === 'handled-b'"));
  await evaluate("document.querySelector('#ea-brand-toggle')?.focus({ preventScroll: true })");
  const handledMismatchBeforeState = await requestTrace();
  await evaluate("window.__reviewProgressionRespondHandled('handled-a', true, { threadId: 'thread-other' })");
  const handledMismatchAfterState = await requestTrace();
  assert(handledMismatchAfterState.filter((request) => request.type === "email-agent:get-state" && request.identity === "handled-b").length === handledMismatchBeforeState.filter((request) => request.type === "email-agent:get-state" && request.identity === "handled-b").length, "mismatched-thread handled response does not initiate navigation");
  await evaluate("window.__reviewProgressionRespondState('handled-b')");
  await waitFor(() => evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')?.textContent.includes('Handled synthetic B')"));
  assert(!(await evaluate("document.querySelector('[data-ea-auto-handled-heading]')?.textContent.includes('Handled synthetic A')")), "mismatched-thread handled response never renders the stale handled item");
  const handledSuccessEvidence = await progressionEvidence("handled-success", handledSuccessBeforeTrace);
  results.responseBoundaryTrace.push({
    step: "known-thread-response-mismatch",
    response: "thread-other",
    before: handledMismatchBeforeState,
    after: handledMismatchAfterState,
    evidence: handledSuccessEvidence,
  });
  await captureViewportSet("handled-ack-after-navigation");
  assert(handledSuccessEvidence.currentIdentity.messageId === "handled-b", "handled success advances to the next handled identity");
  assert(handledSuccessEvidence.requestDelta.added.filter((request) => request.path === "/api/handled-review-acknowledge").length === 1, "handled success evidence records one acknowledgement");
  results.handledTrace.push({ step: "handled-success", activation: "keyboard-enter", acknowledgementCount: handledBefore + 2, evidence: handledSuccessEvidence, snapshot: handledSuccessEvidence.snapshot });
  results.keyboardTrace.push({ step: "handled-success", activation: "keyboard-enter", acknowledgementCount: handledBefore + 2, evidence: handledSuccessEvidence });

  activeStep = "handled-failure-and-completion";
  assert(
    await evaluate("document.querySelector('[data-ea-action=confirm-handled-and-next]')?.textContent.trim() === 'Looks right · Check queue'"),
    "the final handled item offers a queue check instead of Next",
  );
  const handledFailureBefore = await requestTrace();
  const handledAckBeforeFailure = handledFailureBefore.filter((request) => request.path === "/api/handled-review-acknowledge").length;
  await evaluate("document.querySelector('[data-ea-action=confirm-handled-and-next]')?.focus({ preventScroll: true })");
  await pressKey("Enter");
  await evaluate("window.__reviewProgressionRespondHandled('handled-b', false)");
  await waitFor(() => evaluate("document.body.innerText.includes('Try again')"));
  assert((await requestTrace()).filter((request) => request.path === "/api/handled-review-acknowledge").length === handledAckBeforeFailure + 1, "handled failure sends one acknowledgement");
  assert(await evaluate("document.querySelector('[data-ea-selected-state=handled-receipt]')?.textContent.includes('Handled synthetic B')"), "handled failure stays on the current identity");
  await evaluate("window.__reviewProgressionConfigureCompletion(window.__reviewProgressionHandledCompletionStates())");
  await evaluate("window.__reviewProgressionCompletionMode = true");
  const handledFailureEvidence = await progressionEvidence("handled-failure", handledFailureBefore);
  assert(handledFailureEvidence.currentIdentity.messageId === "handled-b", "handled failure evidence stays on the same item");
  assert(handledFailureEvidence.snapshot.handledProgressionFlight === false, "handled failure clears the acknowledgement flight");
  assert(handledFailureEvidence.requestDelta.added.filter((request) => request.path === "/api/handled-review-acknowledge").length === 1, "handled failure evidence records one acknowledgement");
  results.handledTrace.push({ step: "handled-failure", activation: "keyboard-enter", acknowledgementCount: handledAckBeforeFailure + 1, sameItemOnFailure: true, evidence: handledFailureEvidence });
  results.keyboardTrace.push({ step: "handled-failure", activation: "keyboard-enter", acknowledgementCount: handledAckBeforeFailure + 1, sameItemOnFailure: true, evidence: handledFailureEvidence });
  await captureViewportSet("handled-error");
  const handledRetryBefore = await requestTrace();
  await evaluate("document.querySelector('[data-ea-action=confirm-handled-and-next]')?.focus({ preventScroll: true })");
  await pressKey("Enter");
  assert((await requestTrace()).filter((request) => request.path === "/api/handled-review-acknowledge").length === handledAckBeforeFailure + 2, "handled retry keyboard activation sends one acknowledgement");
  await evaluate("window.__reviewProgressionRespondHandled('handled-b', true)");
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-checking]')"));
  const handledRetryEvidence = await progressionEvidence("handled-retry-and-completion-check", handledRetryBefore);
  assert(handledRetryEvidence.currentIdentity.messageId === "handled-b", "handled retry evidence retains the retried identity until completion check");
  assert(handledRetryEvidence.requestDelta.added.filter((request) => request.path === "/api/handled-review-acknowledge").length === 1, "handled retry evidence records one acknowledgement");
  results.handledTrace.push({ step: "handled-retry", activation: "keyboard-enter", acknowledgementCount: handledAckBeforeFailure + 2, evidence: handledRetryEvidence });
  results.keyboardTrace.push({ step: "handled-retry-and-completion", activation: "keyboard-enter", acknowledgementCount: handledAckBeforeFailure + 2, evidence: handledRetryEvidence });
  await evaluate("window.__reviewProgressionRespondCompletion()");
  await waitFor(() => evaluate("document.querySelector('[data-ea-review-progression=review-progression-complete]')?.textContent.includes('queue complete')"));
  results.handledTrace.push({ step: "handled-complete", activation: "keyboard-enter", evidence: await progressionEvidence("handled-complete", handledRetryBefore), snapshot: await evaluate("globalThis.__eaTestHooks.getSnapshot()") });
  await captureViewportSet("handled-complete");

  activeStep = "stale-action-responses-after-live-host-navigation";
  for (const scenario of [
    { kind: "teach", outcome: "success" },
    { kind: "teach", outcome: "failure" },
    { kind: "handled", outcome: "success" },
    { kind: "handled", outcome: "failure" },
  ]) {
    results.responseBoundaryTrace.push(await proveStaleActionResponseIsInert(scenario));
  }
  results.responseBoundaryTrace.push(await proveStaleReconciliationResponseIsInert());

  const requests = await requestTrace();
  const forbidden = requests.filter((request) => !(
    request.type === "email-agent:get-state"
    || request.type === "threadwise:analytics"
    || request.path === "/api/teach-apply"
    || request.path === "/api/provider-write-retry"
    || request.path === "/api/handled-review-acknowledge"
  ));
  results.requestTrace = requests;
  results.forbiddenRequests = forbidden;
  assert(forbidden.length === 0, `synthetic validator recorded forbidden requests: ${forbidden.map((request) => request.path || request.type).join(", ")}`);
  results.ok = true;
} catch (error) {
  failure = error;
  results.failure = { step: activeStep, message: error.message, stack: error.stack };
} finally {
  try {
    results.requestTrace = await requestTrace();
    results.forbiddenRequests = results.requestTrace.filter((request) => !(
      request.type === "email-agent:get-state"
      || request.type === "threadwise:analytics"
      || request.path === "/api/teach-apply"
      || request.path === "/api/provider-write-retry"
      || request.path === "/api/handled-review-acknowledge"
    ));
  } catch (_error) {
    results.requestTrace = [];
  }
  await fs.writeFile(tracePath, JSON.stringify(results, null, 2));
  socket.close();
  await fetch(`${cdpBase}/json/close/${target.id}`).catch(() => {});
}

console.log(JSON.stringify(results, null, 2));
if (failure || results.forbiddenRequests.length) process.exitCode = 1;

async function createSyntheticHost() {
  await evaluate(`(() => {
    document.body.innerHTML = '<main id="synthetic-gmail-host" style="min-height:1800px;margin:0;padding:32px 36px;background:#f4efe5;color:#241812;font-family:system-ui,sans-serif;"><h2 data-thread-perm-id="thread-review" style="margin-top:96px;font-size:28px;">Finance approval A</h2><div data-legacy-message-id="review-a" data-thread-perm-id="thread-review" style="display:block;max-width:620px;padding:20px;background:#fffdf8;border:1px solid #ded3c1;"><span email="a@example.test" data-hovercard-id="a@example.test">Synthetic sender</span><p>Synthetic Gmail host content for review progression acceptance.</p></div></main>';
    document.documentElement.style.margin = '0'; document.body.style.margin = '0'; document.documentElement.style.scrollBehavior = 'auto'; document.body.style.scrollBehavior = 'auto';
    return true;
  })()`);
}

async function setHostMessage(messageId, subject, sender) {
  await evaluate(`(() => {
    const host = document.getElementById('synthetic-gmail-host');
    const threadId = window.__reviewProgressionPhase === 'handled' ? 'thread-handled' : 'thread-review';
    host.querySelector('h2').textContent = ${JSON.stringify(subject)};
    host.querySelector('h2').setAttribute('data-thread-perm-id', threadId);
    const message = host.querySelector('[data-legacy-message-id]');
    message.setAttribute('data-legacy-message-id', ${JSON.stringify(messageId)});
    message.setAttribute('data-thread-perm-id', threadId);
    message.querySelector('[email]').setAttribute('email', ${JSON.stringify(sender)});
    window.location.hash = ${JSON.stringify(`#inbox/FM${messageId}`)};
    return true;
  })()`);
}

async function setHostDomMessage(messageId, subject, sender) {
  await evaluate(`(() => {
    const host = document.getElementById('synthetic-gmail-host');
    const threadId = window.__reviewProgressionPhase === 'handled' ? 'thread-handled' : 'thread-review';
    host.querySelector('h2').textContent = ${JSON.stringify(subject)};
    host.querySelector('h2').setAttribute('data-thread-perm-id', threadId);
    const message = host.querySelector('[data-legacy-message-id]');
    message.setAttribute('data-legacy-message-id', ${JSON.stringify(messageId)});
    message.setAttribute('data-thread-perm-id', threadId);
    message.querySelector('[email]').setAttribute('email', ${JSON.stringify(sender)});
    return true;
  })()`);
}

async function setHostRoute(messageId) {
  await evaluate(`(() => {
    window.location.hash = ${JSON.stringify(`#inbox/FM${messageId}`)};
    return true;
  })()`);
}

async function setHostMessageAndSettleLiveContext(messageId, subject, sender) {
  await evaluate(`(() => {
    const host = document.getElementById('synthetic-gmail-host');
    const threadId = window.__reviewProgressionPhase === 'handled' ? 'thread-handled' : 'thread-review';
    host.querySelector('h2').textContent = ${JSON.stringify(subject)};
    host.querySelector('h2').setAttribute('data-thread-perm-id', threadId);
    const message = host.querySelector('[data-legacy-message-id]');
    message.setAttribute('data-legacy-message-id', ${JSON.stringify(messageId)});
    message.setAttribute('data-thread-perm-id', threadId);
    message.querySelector('[email]').setAttribute('email', ${JSON.stringify(sender)});
    window.location.hash = ${JSON.stringify(`#inbox/FM${messageId}`)};
    return globalThis.__eaTestHooks.returnToLive();
  })()`);
}

async function installBridge() {
  const allowedLabels = [
    ["travel", "Travel"], ["receipt-billing", "Receipts"], ["shopping-order", "Orders"], ["financial-account", "Finance"],
    ["newsletter", "Newsletter"], ["promotions", "Promotions"], ["account-security", "Account"], ["calendar-event", "Calendar"],
    ["personal", "Personal"], ["job-related", "Work"], ["spam-low-value", "LowValue"], ["reply-needed", "NeedsAction"], ["suspicious", "Suspicious"],
  ].map(([id, name]) => ({ id, name: 'EA/' + name }));
  await evaluate(`(() => {
    const logKey = ${JSON.stringify(requestLogStorageKey)};
    const clone = (value) => JSON.parse(JSON.stringify(value));
    const reviewItems = ${JSON.stringify(reviewItems)};
    const refreshedReviewItem = ${JSON.stringify(refreshedReviewItem)};
    const handledItems = ${JSON.stringify(handledItems)};
    const labels = ${JSON.stringify(allowedLabels)};
    const reviewStates = Object.fromEntries(reviewItems.concat([refreshedReviewItem]).map((item) => [item.message_id, {
      found: true, ...item, details: {}, understanding_state: 'ready', understanding_label: 'Ready', rationale: 'Synthetic stored rationale for this review item.'
    }]));
    const handledStates = Object.fromEntries(handledItems.map((item) => [item.message_id, { found: true, ...item }]));
    let phase = 'review';
    let reviewQueue = clone(reviewItems);
    let handledQueue = clone(handledItems);
    let providerFailure = false;
    let staleAsyncFollowUpDone = false;
    let forceHandledFailure = false;
    let handledAttempts = {};
    const pendingApplies = [];
    const pendingHandled = [];
    const pendingCompletions = [];
    const pendingStateReads = [];
    let holdNextStateRead = false;
    let completionStates = [];
    const append = (request) => {
      const log = JSON.parse(localStorage.getItem(logKey) || '[]');
      log.push(request);
      localStorage.setItem(logKey, JSON.stringify(log));
    };
    const currentActivity = () => providerFailure ? [{ id: 'provider-write-review-b', state: 'retry', label: 'Provider write', message: 'Synthetic provider write needs retry.', action: 'retry-provider-write', action_label: 'Retry provider write' }] : [];
    const selectedFor = (context) => {
      const id = context?.message_id || '';
      if (phase === 'handled') return clone(handledStates[id] || { found: false, status: 'idle' });
      return clone(reviewStates[id] || { found: false, provider: 'gmail', message_id: id, subject: '', sender: '', status: id ? 'not-in-snapshot' : 'idle' });
    };
    const makeState = (context, options = {}) => {
      const selected = selectedFor(context || {});
      const queue = options.reviewQueue || (phase === 'handled' ? [] : reviewQueue);
      const handled = options.handledQueue || (phase === 'handled' ? handledQueue : []);
      const daily = options.daily || {};
      const selectedContext = phase === 'handled'
        ? { ...(context || {}), thread_id: 'thread-handled' }
        : (context || {});
      return {
        selected_context: selectedContext,
        sidebar_state: {
          selected_context: selectedContext,
          selected_email: selected,
          daily_summary: { processed_count: 8, auto_handled_count: handled.length, kept_visible_count: 1, needs_attention_count: queue.length, ...daily },
          ui_state: { provider_name: 'Gmail', allowed_labels: labels, async_follow_up: clone(options.asyncFollowUp || (staleAsyncFollowUpDone ? { kind: 'teach-apply-refresh', state: 'done', label: 'Background refresh', message: 'Synthetic stale follow-up completed.' } : {})), activity_feed: phase === 'review' ? currentActivity() : [] },
        },
        needs_attention_items: clone(queue),
        recent_items: phase === 'handled' ? clone(handled) : clone(queue),
        auto_handled_items: clone(handled),
        kept_visible_items: [],
        analytics_status: { state: 'disabled' },
      };
    };
    const stateForContext = (context) => { phase = window.__reviewProgressionPhase || phase; return makeState(context || {}); };
    window.__reviewProgressionPhase = 'review';
    window.__reviewProgressionCompletionMode = false;
    window.__reviewProgressionHeldStateMessage = '';
    window.__reviewProgressionHoldStateRead = (messageId) => {
      window.__reviewProgressionHeldStateMessage = String(messageId || '');
      return window.__reviewProgressionHeldStateMessage;
    };
    window.__reviewProgressionHoldNextStateRead = () => { holdNextStateRead = true; return true; };
    window.__reviewProgressionRespondState = (messageId) => {
      const wanted = String(messageId || '');
      const entries = pendingStateReads.filter((entry) => entry.messageId === wanted);
      for (const entry of entries) {
        entry.callback({ ok: true, payload: stateForContext(entry.context), connection_state: { kind: 'ready', label: 'Ready', details: 'Synthetic fixture state.' } });
      }
      for (const entry of entries) {
        const index = pendingStateReads.indexOf(entry);
        if (index >= 0) pendingStateReads.splice(index, 1);
      }
      if (window.__reviewProgressionHeldStateMessage === wanted) {
        window.__reviewProgressionHeldStateMessage = '';
      }
      return entries.length;
    };
    window.__reviewProgressionRespondNextStateRead = () => {
      const entry = pendingStateReads.shift();
      if (!entry) return { delivered: false, messageId: '' };
      entry.callback({ ok: true, payload: stateForContext(entry.context), connection_state: { kind: 'ready', label: 'Ready', details: 'Synthetic fixture state.' } });
      return { delivered: true, messageId: entry.messageId };
    };
    window.__reviewProgressionPendingStateReadCount = (messageId = '') => {
      const wanted = String(messageId || '');
      return pendingStateReads.filter((entry) => !wanted || entry.messageId === wanted).length;
    };
    window.__reviewProgressionResetReviewQueue = () => { reviewQueue = clone(reviewItems); providerFailure = false; return reviewQueue.length; };
    window.__reviewProgressionResetHandledQueue = () => { handledQueue = clone(handledItems); return handledQueue.length; };
    window.__reviewProgressionSetAsyncFollowUp = (enabled) => { staleAsyncFollowUpDone = Boolean(enabled); return staleAsyncFollowUpDone; };
    window.__reviewProgressionFailNextHandled = () => { forceHandledFailure = true; return true; };
    window.__reviewProgressionMakeState = (messageIds = [], options = {}) => {
      const allReviewItems = reviewItems.concat([refreshedReviewItem]);
      const queue = (messageIds || []).map((id) => allReviewItems.find((item) => item.message_id === id)).filter(Boolean);
      return makeState({ provider: 'gmail' }, {
        reviewQueue: queue,
          daily: { needs_attention_count: Object.prototype.hasOwnProperty.call(options, 'dailyCount') ? options.dailyCount : queue.length },
        asyncFollowUp: options.asyncFollowUp || {},
      });
    };
    const applyResponseThread = (state, responseOptions = {}) => {
      const targets = [state.selected_context, state.sidebar_state?.selected_context, state.selected_email, state.sidebar_state?.selected_email].filter(Boolean);
      if (responseOptions.omitThreadId) {
        targets.forEach((target) => { delete target.thread_id; });
      } else if (Object.prototype.hasOwnProperty.call(responseOptions, 'threadId')) {
        targets.forEach((target) => { target.thread_id = responseOptions.threadId; });
      }
      return state;
    };
    window.__reviewProgressionRespondApply = (messageId, ok = true, responseOptions = {}) => {
      const index = pendingApplies.findIndex((entry) => entry.messageId === messageId);
      if (index < 0) return false;
      const entry = pendingApplies.splice(index, 1)[0];
      if (!ok) {
        providerFailure = true;
        entry.callback({ ok: false, payload: { error: 'Synthetic provider write failed.' } });
        return true;
      }
      const responseState = applyResponseThread(makeState(entry.context).sidebar_state, responseOptions);
      entry.callback({ ok: true, payload: { acknowledgment: 'Synthetic local decision accepted.', outcome: { scope: 'current-email', current_email_changed_locally: true, provider_write_queued: true, current_email_written_to_provider: false }, sidebar_state: responseState } });
      return true;
    };
    window.__reviewProgressionRespondApplyTransportError = (messageId) => {
      const index = pendingApplies.findIndex((entry) => entry.messageId === messageId);
      if (index < 0) return false;
      const entry = pendingApplies.splice(index, 1)[0];
      window.chrome.runtime.lastError = { message: 'Synthetic transport response lost.' };
      entry.callback();
      window.chrome.runtime.lastError = null;
      return true;
    };
    window.__reviewProgressionRespondHandled = (messageId, ok = true, responseOptions = {}) => {
      const index = pendingHandled.findIndex((entry) => entry.messageId === messageId);
      if (index < 0) return false;
      const entry = pendingHandled.splice(index, 1)[0];
      const attempt = (handledAttempts[messageId] || 0) + 1;
      handledAttempts[messageId] = attempt;
      if (forceHandledFailure || (messageId === 'handled-b' && attempt === 1)) {
        forceHandledFailure = false;
        entry.callback({ ok: false, payload: { error: 'Synthetic acknowledgement failed.' } });
        return true;
      }
      handledQueue = handledQueue.filter((item) => item.message_id !== messageId);
      const responseState = applyResponseThread(makeState(entry.context, { handledQueue }), responseOptions);
      entry.callback({ ok: true, payload: { acknowledged: true, harness_state: responseState } });
      return true;
    };
    window.__reviewProgressionRespondCompletion = () => {
      const entry = pendingCompletions.shift();
      const state = completionStates.shift();
      if (!entry || !state) return false;
      if (state.needs_attention_items) reviewQueue = clone(state.needs_attention_items);
      if (state.auto_handled_items) handledQueue = clone(state.auto_handled_items);
      entry.callback({ ok: true, payload: clone(state), connection_state: { kind: 'ready', label: 'Ready', details: 'Synthetic fixture state.' } });
      return true;
    };
    window.__reviewProgressionRespondCompletionError = () => {
      const entry = pendingCompletions.shift();
      if (!entry) return false;
      entry.callback({ ok: false, error: 'Synthetic queue check failed.', connection_state: { kind: 'ready', label: 'Ready', details: 'Synthetic fixture state.' } });
      return true;
    };
    window.__reviewProgressionPendingCompletionCount = () => pendingCompletions.length;
    window.__reviewProgressionConfigureCompletion = (states) => { completionStates = clone(states || []); return completionStates.length; };
    window.__reviewProgressionReviewCompletionStates = () => [
      makeState({ provider: 'gmail' }, { reviewQueue: [], daily: { needs_attention_count: 0 }, asyncFollowUp: { kind: 'teach-apply-refresh', state: 'working' } }),
      makeState({ provider: 'gmail' }, { reviewQueue: reviewItems.concat([refreshedReviewItem]), daily: { needs_attention_count: 1 } }),
      makeState({ provider: 'gmail' }, { reviewQueue: [], daily: { needs_attention_count: 0 } }),
    ];
    window.__reviewProgressionHandledCompletionStates = () => [
      makeState({ provider: 'gmail' }, { reviewQueue: [], handledQueue: [], daily: { needs_attention_count: 0 } }),
    ];
    window.chrome = { runtime: {
      lastError: null,
      onMessage: { addListener: () => undefined, removeListener: () => undefined },
      getURL: () => ${JSON.stringify(await assetDataUri())},
      getManifest: () => ({ version: '0.3.2' }),
      sendMessage(message, callback) {
        const context = message?.context || message?.body?.selected_context || {};
        const request = { type: message?.type || 'unknown', path: message?.path || '', method: message?.method || '', identity: context?.message_id || '' };
        append(request);
        if (message?.type === 'email-agent:get-state') {
          if (holdNextStateRead) {
            holdNextStateRead = false;
            pendingStateReads.push({ messageId: context.message_id || '', context: clone(context), callback });
            return true;
          }
          if (!context?.message_id && window.__reviewProgressionCompletionMode) {
            pendingCompletions.push({ callback });
            return true;
          }
          if (context?.message_id && context.message_id === window.__reviewProgressionHeldStateMessage) {
            pendingStateReads.push({ messageId: context.message_id, context: clone(context), callback });
            return true;
          }
          callback?.({ ok: true, payload: stateForContext(context), connection_state: { kind: 'ready', label: 'Ready', details: 'Synthetic fixture state.' } });
          return true;
        }
        if (message?.type === 'threadwise:analytics') { callback?.({ ok: true }); return true; }
        if (message?.type === 'email-agent:api' && message.path === '/api/teach-apply') {
          const messageId = message.body?.selected_context?.message_id || '';
          if (messageId === 'review-d') {
            callback?.({ ok: true, payload: { acknowledgment: 'Synthetic local decision accepted.', outcome: { scope: 'current-email', current_email_changed_locally: true, provider_write_queued: true, current_email_written_to_provider: false }, sidebar_state: makeState({ provider: 'gmail', message_id: messageId }).sidebar_state } });
          } else {
            pendingApplies.push({ messageId, context: clone(message.body?.selected_context || {}), callback });
          }
          return true;
        }
        if (message?.type === 'email-agent:api' && message.path === '/api/provider-write-retry') {
          providerFailure = false;
          callback?.({ ok: true, payload: stateForContext(context) });
          return true;
        }
        if (message?.type === 'email-agent:api' && message.path === '/api/handled-review-acknowledge') {
          pendingHandled.push({ messageId: message.body?.selected_context?.message_id || '', context: clone(message.body?.selected_context || {}), callback });
          return true;
        }
        callback?.({ ok: false, error: 'Synthetic validator rejects ' + (message?.path || message?.type || 'unknown') + '.' });
        return true;
      },
    }, storage: { local: {
      async get(key) { const raw = localStorage.getItem(key); return { [key]: raw ? JSON.parse(raw) : undefined }; },
      async set(values) { Object.entries(values).forEach(([key, value]) => localStorage.setItem(key, JSON.stringify(value))); },
    } } };
    localStorage.setItem(${JSON.stringify(onboardingStorageKey)}, JSON.stringify({ version: ${JSON.stringify(onboardingVersion)}, status: 'dismissed' }));
    localStorage.setItem(${JSON.stringify(requestLogStorageKey)}, '[]');
    return true;
  })()`);
}

async function injectContentScript() {
  for (const scriptName of ["provider_adapter.js", "analytics.js", "onboarding.js", "queue_navigation.js", "context_actions.js", "selected_explanation.js", "review_progression.js", "coverage.js", "content.js"]) {
    await evaluate(await fs.readFile(path.join(extensionRoot, scriptName), "utf8"));
  }
}

async function seedScroll() {
  await evaluate(`(() => { const content = document.getElementById('ea-content'); window.scrollTo(0, ${seededPageScrollY}); content.scrollTop = ${seededContentScrollTop}; return true; })()`);
  const snapshot = await scrollSnapshot();
  assert(snapshot.pageY === seededPageScrollY, "synthetic Gmail page scroll is genuinely nonzero");
  assert(snapshot.contentScrollTop === seededContentScrollTop, "synthetic companion scroll is genuinely nonzero");
  return snapshot;
}

async function returnToQueueHomePreservingFilter() {
  assert(await evaluate("Boolean(document.querySelector('[data-ea-context-trigger]'))"), "queue preview exposes the contextual actions trigger");
  await evaluate("document.querySelector('[data-ea-context-trigger]').click()");
  await waitFor(() => evaluate("globalThis.__eaTestHooks.getContextActions().open && Boolean(document.querySelector('[data-ea-context-item=back-to-queue]'))"));
  await evaluate("document.querySelector('[data-ea-context-item=back-to-queue]').click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]')) && globalThis.__eaTestHooks.getSnapshot().queueQuery === 'finance' && Boolean(document.querySelector('#ea-queue-query'))"));
}

async function captureViewportSet(stateName) {
  for (const viewport of viewports) {
    await send("Emulation.setDeviceMetricsOverride", { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: false });
    await waitFor(() => evaluate("Boolean(document.getElementById('email-agent-companion-root')?.getBoundingClientRect().width)"));
    const containment = await containmentSnapshot();
    assert(containment.contained, `${stateName} stays contained at ${viewport.name}`);
    const outputPath = path.join(artifactRoot, `${stateName}-${viewport.name}.png`);
    await captureScreenshot(outputPath);
    results.screenshots.push({ state: stateName, viewport: viewport.name, path: outputPath, containment });
    results.viewportChecks.push({ state: stateName, viewport: viewport.name, ...containment });
  }
}

async function scrollSnapshot() {
  return evaluate("(() => ({ pageX: window.scrollX, pageY: window.scrollY, contentScrollTop: document.getElementById('ea-content')?.scrollTop || 0, contentScrollLeft: document.getElementById('ea-content')?.scrollLeft || 0 }))()");
}

async function activeFocusSnapshot() {
  return evaluate("document.activeElement ? { tag: document.activeElement.tagName, id: document.activeElement.id || '', action: document.activeElement.getAttribute('data-ea-action') || '', queue: document.activeElement.hasAttribute('data-ea-queue-navigation') } : null");
}

async function requestTrace() {
  return evaluate(`JSON.parse(localStorage.getItem(${JSON.stringify(requestLogStorageKey)}) || '[]')`);
}

function requestSummary(requests) {
  const list = Array.isArray(requests) ? requests : [];
  const count = (predicate) => list.filter(predicate).length;
  return {
    total: list.length,
    stateReads: count((request) => request.type === "email-agent:get-state"),
    analytics: count((request) => request.type === "threadwise:analytics"),
    teachApply: count((request) => request.path === "/api/teach-apply"),
    providerWriteRetry: count((request) => request.path === "/api/provider-write-retry"),
    handledAcknowledgements: count((request) => request.path === "/api/handled-review-acknowledge"),
  };
}

async function progressionEvidence(step, beforeRequests = []) {
  const [snapshot, focus, scroll, requests] = await Promise.all([
    evaluate("globalThis.__eaTestHooks.getSnapshot()"),
    activeFocusSnapshot(),
    scrollSnapshot(),
    requestTrace(),
  ]);
  const currentMessageId = snapshot?.manualPreviewContext?.message_id
    || snapshot?.selectedEmail?.message_id
    || snapshot?.forcedHomeLiveContext?.message_id
    || snapshot?.selectedContext?.message_id
    || snapshot?.queueCurrentIdentity
    || "";
  const currentProvider = snapshot?.manualPreviewContext?.provider
    || snapshot?.selectedEmail?.provider
    || snapshot?.forcedHomeLiveContext?.provider
    || snapshot?.selectedContext?.provider
    || snapshot?.queueProvider
    || "gmail";
  return {
    step,
    currentIdentity: { provider: currentProvider, messageId: currentMessageId },
    query: snapshot?.queueQuery || "",
    queue: {
      provider: snapshot?.queueProvider || "",
      previewActive: Boolean(snapshot?.queuePreviewActive),
      currentIdentity: snapshot?.queueCurrentIdentity || "",
      matchCount: Number(snapshot?.queueMatchCount || 0),
    },
    snapshot,
    focus,
    scroll,
    requestDelta: {
      before: requestSummary(beforeRequests),
      after: requestSummary(requests),
      added: requests.slice(Array.isArray(beforeRequests) ? beforeRequests.length : 0),
    },
  };
}

async function proveStaleActionResponseIsInert({ kind, outcome }) {
  const handled = kind === "handled";
  const source = handled
    ? { messageId: "handled-a", subject: "Handled synthetic A", sender: "handled-a@example.test" }
    : { messageId: "review-a", subject: "Finance approval A", sender: "a@example.test" };
  const destination = handled
    ? { messageId: "handled-b", subject: "Handled synthetic B", sender: "handled-b@example.test" }
    : { messageId: "review-c", subject: "Finance approval C", sender: "c@example.test" };
  const action = handled ? "confirm-handled-and-next" : "accept-suggestion";
  const route = handled ? "/api/handled-review-acknowledge" : "/api/teach-apply";
  const label = `${kind}-${outcome}-after-host-navigation`;

  await evaluate("globalThis.__eaCompanionSingleton?.teardown(); true");
  await evaluate(`window.__reviewProgressionPhase = ${JSON.stringify(handled ? "handled" : "review")}; window.__reviewProgressionCompletionMode = false; window.${handled ? "__reviewProgressionResetHandledQueue" : "__reviewProgressionResetReviewQueue"}()`);
  await setHostDomMessage(source.messageId, source.subject, source.sender);
  await setHostRoute(source.messageId);
  await injectContentScript();
  await waitFor(() => evaluate(`globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === ${JSON.stringify(source.messageId)}`));
  await evaluate("document.getElementById('ea-brand-toggle')?.click()");
  await waitFor(() => evaluate(`Boolean(document.querySelector('[data-ea-action=${action}]'))`));
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await evaluate("document.querySelector('#ea-workspace').style.minHeight = '900px'; true");
  await seedScroll();

  const activationBefore = await requestTrace();
  await evaluate(`document.querySelector('[data-ea-action=${action}]')?.focus({ preventScroll: true })`);
  await pressKey("Enter");
  await waitFor(async () => (await requestTrace()).filter((request) => request.path === route).length === activationBefore.filter((request) => request.path === route).length + 1);
  if (handled) {
    await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().handledProgressionFlight === true"));
  } else {
    await waitFor(() => evaluate("globalThis.__eaTestHooks.getSnapshot().optimisticDecision?.responseReceived === false"));
  }

  const navigationBefore = await requestTrace();
  if (handled) {
    await setHostDomMessage(destination.messageId, destination.subject, destination.sender);
    await setHostRoute(destination.messageId);
  } else {
    await setHostMessageAndSettleLiveContext(destination.messageId, destination.subject, destination.sender);
  }
  await waitFor(() => evaluate(`globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === ${JSON.stringify(destination.messageId)} && globalThis.__eaTestHooks.getSnapshot().lastLiveContext?.message_id === ${JSON.stringify(destination.messageId)} && window.location.hash.endsWith(${JSON.stringify(`FM${destination.messageId}`)})`));
  const navigationAfter = await requestTrace();
  assert(
    navigationAfter.filter((request) => request.type === "email-agent:get-state").length
      === navigationBefore.filter((request) => request.type === "email-agent:get-state").length + 1,
    `${label} performs exactly one navigation state read after real DOM plus route navigation`,
  );
  await seedScroll();
  await evaluate("document.querySelector('#ea-brand-toggle')?.focus({ preventScroll: true })");
  const beforeResponse = {
    requests: await requestTrace(),
    focus: await activeFocusSnapshot(),
    scroll: await scrollSnapshot(),
    surface: await staleActionSurfaceSnapshot(),
  };

  if (handled) {
    if (outcome === "failure") {
      await evaluate("window.__reviewProgressionFailNextHandled()");
    }
    assert(await evaluate(`window.__reviewProgressionRespondHandled(${JSON.stringify(source.messageId)}, ${outcome === "success"})`), `${label} dispatches the pending same-token handled response`);
  } else {
    assert(await evaluate(`window.__reviewProgressionRespondApply(${JSON.stringify(source.messageId)}, ${outcome === "success"})`), `${label} dispatches the pending same-token teach response`);
  }

  const afterResponse = {
    requests: await requestTrace(),
    focus: await activeFocusSnapshot(),
    scroll: await scrollSnapshot(),
    surface: await staleActionSurfaceSnapshot(),
  };
  const beforeSummary = requestSummary(beforeResponse.requests);
  const afterSummary = requestSummary(afterResponse.requests);
  assert(afterSummary.stateReads === beforeSummary.stateReads, `${label} schedules no duplicate state read`);
  assert(afterSummary.analytics === beforeSummary.analytics, `${label} emits no stale analytics`);
  assert(JSON.stringify(afterResponse.surface) === JSON.stringify(beforeResponse.surface), `${label} changes no new-message controls, lifecycle, receipt, or error`);
  assertScrollUnchanged(beforeResponse.scroll, afterResponse.scroll, label);
  assert(JSON.stringify(afterResponse.focus) === JSON.stringify(beforeResponse.focus), `${label} preserves focus`);
  assert(
    handled
      ? (await evaluate("globalThis.__eaTestHooks.getSnapshot().handledProgressionFlight")) === false
      : (await evaluate("globalThis.__eaTestHooks.getApplyState().applyInFlight")) === false,
    `${label} safely releases the stale action flight`,
  );

  return {
    step: label,
    source,
    destination,
    outcome,
    before: beforeResponse,
    after: afterResponse,
  };
}

async function staleActionSurfaceSnapshot() {
  return evaluate(`(() => {
    const snapshot = globalThis.__eaTestHooks.getSnapshot();
    const workspace = document.querySelector('#ea-workspace');
    return {
      workspaceHtml: workspace?.innerHTML || '',
      selectedContext: snapshot.selectedContext,
      selectedEmail: snapshot.selectedEmail,
      manualPreviewContext: snapshot.manualPreviewContext,
      forcedHome: snapshot.forcedHome,
      optimisticDecision: snapshot.optimisticDecision,
      progressionCheck: snapshot.progressionCheck,
      previousDecision: document.querySelector('[data-ea-previous-decision-status]')?.textContent || '',
      progression: document.querySelector('[data-ea-review-progression]')?.textContent || '',
      selectedReceipt: document.querySelector('[data-ea-selected-state=receipt], [data-ea-selected-state=teach-result-receipt], [data-ea-selected-state=handled-receipt]')?.textContent || '',
      controls: Array.from(workspace?.querySelectorAll('button, input, select, textarea, a') || []).map((node) => ({
        tag: node.tagName,
        action: node.getAttribute('data-ea-action') || '',
        text: node.textContent || '',
        value: node.value || '',
        disabled: Boolean(node.disabled),
      })),
    };
  })()`);
}

async function proveStaleReconciliationResponseIsInert() {
  const source = { messageId: "review-a", subject: "Finance approval A", sender: "a@example.test" };
  const destination = { messageId: "review-c", subject: "Finance approval C", sender: "c@example.test" };
  const label = "teach-reconciliation-after-host-navigation";

  await evaluate("globalThis.__eaCompanionSingleton?.teardown(); true");
  await evaluate("window.__reviewProgressionPhase = 'review'; window.__reviewProgressionCompletionMode = false; window.__reviewProgressionResetReviewQueue()");
  await setHostDomMessage(source.messageId, source.subject, source.sender);
  await setHostRoute(source.messageId);
  await injectContentScript();
  await waitFor(() => evaluate(`globalThis.__eaTestHooks?.getSnapshot()?.selectedEmail?.message_id === ${JSON.stringify(source.messageId)}`));
  await evaluate("document.getElementById('ea-brand-toggle')?.click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-action=accept-suggestion]'))"));
  await evaluate("document.getElementById('ea-brand-toggle')?.click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('[data-ea-selected-state=home]'))"));
  await evaluate("document.querySelector('[data-ea-action=open-queue-finder]')?.click()");
  await waitFor(() => evaluate("Boolean(document.querySelector('#ea-queue-query'))"));
  await evaluate(`(() => {
    const input = document.querySelector('#ea-queue-query');
    input.value = ${JSON.stringify(source.sender)};
    input.dispatchEvent(new Event('input', { bubbles: true }));
    document.querySelector(${JSON.stringify(`[data-ea-queue-item=${source.messageId}]`)})?.click();
    return true;
  })()`);
  await waitFor(() => evaluate(`globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === ${JSON.stringify(source.messageId)} && globalThis.__eaTestHooks.getSnapshot().queueMatchCount === 1`));
  await send("Emulation.setDeviceMetricsOverride", { width: 756, height: 469, deviceScaleFactor: 1, mobile: false });
  await evaluate("document.querySelector('#ea-workspace').style.minHeight = '900px'; true");
  await seedScroll();

  await evaluate("document.querySelector('[data-ea-action=accept-suggestion]')?.focus({ preventScroll: true })");
  const activationBefore = await requestTrace();
  await pressKey("Enter");
  await waitFor(() => evaluate(`globalThis.__eaTestHooks.getSnapshot().manualPreviewContext?.message_id === ${JSON.stringify(source.messageId)} && globalThis.__eaTestHooks.getSnapshot().optimisticDecision?.responseReceived === false`));
  assert(
    (await requestTrace()).filter((request) => request.path === "/api/teach-apply").length
      === activationBefore.filter((request) => request.path === "/api/teach-apply").length + 1,
    `${label} sends exactly one current-only teaching request`,
  );

  await evaluate("window.__reviewProgressionHoldNextStateRead()");
  assert(await evaluate("window.__reviewProgressionRespondApplyTransportError('review-a')"), `${label} dispatches a lost source response while its host is current`);
  await waitFor(() => evaluate("window.__reviewProgressionPendingStateReadCount() === 1"));

  const navigationBefore = await requestTrace();
  await setHostDomMessage(destination.messageId, destination.subject, destination.sender);
  await setHostRoute(destination.messageId);
  await waitFor(() => evaluate(`globalThis.__eaTestHooks.getSnapshot().selectedEmail?.message_id === ${JSON.stringify(destination.messageId)} && globalThis.__eaTestHooks.getSnapshot().lastLiveContext?.message_id === ${JSON.stringify(destination.messageId)} && window.location.hash.endsWith(${JSON.stringify(`FM${destination.messageId}`)})`));
  const navigationAfter = await requestTrace();
  assert(
    navigationAfter.filter((request) => request.type === "email-agent:get-state" && request.identity === destination.messageId).length
      === navigationBefore.filter((request) => request.type === "email-agent:get-state" && request.identity === destination.messageId).length + 1,
    `${label} settles exactly one new-context state read after DOM plus route navigation`,
  );
  assert(await evaluate("window.__reviewProgressionPendingStateReadCount() === 1"), `${label} still holds the exact old reconciliation read`);

  await seedScroll();
  await evaluate("document.querySelector('#ea-brand-toggle')?.focus({ preventScroll: true })");
  const beforeResponse = {
    requests: await requestTrace(),
    focus: await activeFocusSnapshot(),
    scroll: await scrollSnapshot(),
    surface: await staleActionSurfaceSnapshot(),
    apply: await evaluate("globalThis.__eaTestHooks.getApplyState()"),
  };
  const reconciliationDelivery = await evaluate("window.__reviewProgressionRespondNextStateRead()");
  assert(reconciliationDelivery.delivered, `${label} delivers exactly one old reconciliation response`);
  const afterResponse = {
    requests: await requestTrace(),
    focus: await activeFocusSnapshot(),
    scroll: await scrollSnapshot(),
    surface: await staleActionSurfaceSnapshot(),
    apply: await evaluate("globalThis.__eaTestHooks.getApplyState()"),
  };
  const beforeSummary = requestSummary(beforeResponse.requests);
  const afterSummary = requestSummary(afterResponse.requests);
  assert(afterSummary.stateReads === beforeSummary.stateReads, `${label} schedules no duplicate state read`);
  assert(afterSummary.analytics === beforeSummary.analytics, `${label} emits no stale analytics`);
  assert(JSON.stringify(afterResponse.surface) === JSON.stringify(beforeResponse.surface), `${label} changes no new-message controls, lifecycle, receipt, or error`);
  assertScrollUnchanged(beforeResponse.scroll, afterResponse.scroll, label);
  assert(JSON.stringify(afterResponse.focus) === JSON.stringify(beforeResponse.focus), `${label} preserves focus`);
  assert(afterResponse.apply.applyInFlight === false, `${label} leaves the stale teaching flight safely released`);
  assert(JSON.stringify(afterResponse.apply) === JSON.stringify(beforeResponse.apply), `${label} does not change the settled new-context apply lifecycle`);

  return {
    step: label,
    source,
    destination,
    reconciliationReadIdentity: reconciliationDelivery.messageId,
    before: beforeResponse,
    after: afterResponse,
  };
}

async function containmentSnapshot() {
  return evaluate("(() => { const root = document.getElementById('email-agent-companion-root')?.getBoundingClientRect(); const host = document.getElementById('synthetic-gmail-host')?.getBoundingClientRect(); return { contained: Boolean(root && root.left >= 0 && root.top >= 0 && root.right <= innerWidth + 1 && root.bottom <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth && host?.left === 0), root: root ? { left: root.left, top: root.top, right: root.right, bottom: root.bottom, width: root.width } : null, viewport: { width: innerWidth, height: innerHeight } }; })()");
}

function assertScrollUnchanged(before, after, label) {
  for (const key of ["pageX", "pageY", "contentScrollTop", "contentScrollLeft"]) {
    assert(before[key] === after[key], `${label} preserves ${key}: ${before[key]} -> ${after[key]}`);
  }
}

async function captureScreenshot(outputPath) {
  const result = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  await fs.writeFile(outputPath, Buffer.from(result.data, "base64"));
}

async function assetDataUri() {
  const bytes = await fs.readFile(path.join(extensionRoot, "assets", "brand", "threadwise-app-icon.png"));
  return `data:image/png;base64,${bytes.toString("base64")}#assets/brand/threadwise-app-icon.png`;
}

async function createTarget(url) {
  const response = await fetch(`${cdpBase}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  if (!response.ok) throw new Error(`Could not create Chrome target: ${response.status}`);
  return response.json();
}

function send(method, params = {}) {
  const id = nextId++;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "CDP evaluation failed");
  return result.result.value;
}

async function waitFor(check, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error(`Timed out at ${activeStep}: ${await evaluate("document.body.innerText.slice(0, 1200)").catch(() => "unavailable")}`);
}

async function pressKey(key) {
  await send("Page.bringToFront");
  const windowsVirtualKeyCode = key === "Enter" ? 13 : key === "Escape" ? 27 : key.length === 1 ? key.toUpperCase().charCodeAt(0) : 0;
  const code = key.length === 1 ? `Key${key.toUpperCase()}` : key;
  const text = key === "Enter" ? "\r" : key.length === 1 ? key : "";
  const keyIdentifier = key.length === 1 ? `U+${windowsVirtualKeyCode.toString(16).padStart(4, "0")}` : "";
  await send("Input.dispatchKeyEvent", { type: text ? "keyDown" : "rawKeyDown", key, code, windowsVirtualKeyCode, nativeVirtualKeyCode: windowsVirtualKeyCode, keyIdentifier, text, unmodifiedText: text });
  await send("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode, nativeVirtualKeyCode: windowsVirtualKeyCode });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}
