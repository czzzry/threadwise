# Variant C Production Gauntlet Ledger

Status: LIVE read-only validation complete; founder checkpoint approved
Current as of: 2026-08-11
Parent direction: `docs/prd-threadwise-gauntlet-2026-08-09.md`
Implementation brief: GitHub issue `#110`
Approved reference: `prototypes/threadwise_ray_linear_ui_prototype.html?variant=C`

## Slice

Convert the approved Variant C hierarchy into the real provider-neutral companion's current-message review surface, with Gmail as the first acceptance host. Preserve the existing logo, overlay architecture, provider truth, review lifecycle, correction and teaching paths, keyboard safety, and recovery behavior.

The founder approved this milestone's LIVE checkpoint on 2026-08-11. Later work still proceeds only as separately bounded, approved slices.

## Acceptance summary

- The production extension, not the prototype, uses the compact Variant C hierarchy.
- Meaningful selected-message states remain truthful and reachable: understanding, ready, correction entry, working, confirmed success, delayed response, empty/complete, error, retry/recovery, navigation, reload, and context change.
- One state-valid primary action is visible; valid secondary actions remain available through contextual disclosure and keyboard operation.
- Action, Inbox effect, and Scope never overclaim provider success.
- Panel-scoped keyboard behavior, accessibility, Gmail coexistence, provider-neutral behavior, and existing safety gates do not regress.
- A separate fresh-context critic inspects implementation and rendered output.

## Evidence boundary

- `AUTOMATED`: unit, integration, browser harness, fixture, and synthetic-host evidence.
- `LIVE`: built production extension in real Gmail on an explicitly approved non-sensitive test account.
- Synthetic evidence is never reported as LIVE. If LIVE access or exact safe actions are not approved, the milestone is `BLOCKED` for completion.

## Rounds

### Baseline

- Production baseline: synthetic companion simulator at 1440x900, selected review item open.
- Approved reference: Variant C at 1440x900, first review item.
- Baseline finding: existing production behavior is present, but the selected-message decision is visually split across sparse sections and two similarly prominent actions; Variant C creates a quieter context/judgment/facts/primary-action hierarchy.
- Evidence: equivalent baseline and reference screenshots retained with the active Goal checkpoint artifacts.

### Round 1

- Builder: fresh context; complete.
- Visible change: production review now follows context -> progress -> judgment -> disclosed Action/Inbox/Scope facts -> one-primary-action dock, with secondary review actions in the contextual menu.
- Red evidence: focused tests first failed because the Quiet Hybrid hierarchy and review-state contextual actions were absent.
- Green evidence: focused JavaScript syntax, contextual-actions, selected-explanation, queue-navigation, review-progression, onboarding, and targeted Python UI-contract checks pass.
- Broad regression: 117/122 companion UI tests passed; four pre-existing encoding/source-string assertions and one Windows temporary-file cleanup error remained.
- Browser harness: review-progression passed across success, failure, retry, completion, navigation, reload/reinjection, and response-boundary states at desktop, short, and narrow viewports.
- Browser harness conflicts: contextual-actions stopped at a fixture that requires nonzero inner-panel scroll even though the compact review fits without inner scrolling; selected-explanation stopped because its older contract requires visible one-click `Change label`, which round 1 moved into contextual disclosure.
- Critic: fresh context; complete. The two browser-harness conflicts are stale expectations: a compact panel that fits should not be forced to create inner scroll, and issue `#110` plus Variant C intentionally place the secondary label-change action in contextual disclosure.
- Scores: Gmail nativeness `3/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `4/5`; live reliability `2/5`.
- Biggest material gap: no LIVE evidence from the built production extension in real Gmail, so Gmail coexistence and provider-confirmed reliability cannot pass.
- Bounded correction: none in code. Run the critical LIVE pack only after explicit founder approval of the exact non-sensitive Gmail account and exact safe actions.
- `AUTOMATED`: partial pass; equivalent baseline/current/reference plus error and completion screenshots captured. Synthetic evidence only.
- `LIVE`: not started; no account or provider-write approval has been granted.
- Recommendation: `BLOCKED`.
- Status: `BLOCKED_ON_LIVE_APPROVAL`.

### Round 2 — AUTOMATED contract correction

- Justification: two existing controlled-browser acceptance scripts failed because they encoded the pre-Variant-C visible secondary action and required inner-panel scrolling even when the compact review fit without overflow.
- Builder: separate fresh context; complete.
- Product delta: none. Only the contextual-actions and selected-explanation CDP acceptance scripts changed.
- Red evidence: contextual actions stopped at `seeded companion scroll is nonzero: 0`; selected explanation stopped at `review keeps one-click Change label visible`.
- Green evidence: both controlled-browser scripts report `ok: true`, zero unexpected requests, 48 contained screenshots total, preserved Gmail-page scroll, preserved real inner overflow where present, one-click contextual correction discovery, focused keyboard activation, safe cancellation, and no provider request.
- Focused JavaScript, targeted Python UI-contract, syntax, whitespace, and diff checks pass.
- Critic: separate fresh context; complete. The revised assertions remain strict and aligned with Variant C; no material weakening or problematic test-to-implementation coupling was found.
- Scores: Gmail nativeness `3/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `4/5`; live reliability `2/5`.
- `AUTOMATED`: `PASS`. Both traces report `ok: true`, zero unexpected requests, and containment across all 48 screenshots. Compact fit permits `0 -> 0` only when no inner overflow exists; real overflow preserves nonzero scroll. Gmail-page scroll, focus, keyboard safety, correction entry/cancel, request boundaries, target sizing, collision avoidance, and one-primary-action hierarchy remain enforced.
- `LIVE`: unchanged; not started and not substituted by this synthetic evidence.
- Biggest material gap: no built-extension run in real Gmail proving host coexistence, real focus/scroll behavior, and provider-confirmed reliability.
- Recommendation: `BLOCKED` on LIVE approval.
- Status: `BLOCKED_ON_LIVE_APPROVAL`.

## LIVE authorization and environment

- Founder authorization: use `baraniecki@gmail.com` and its messages for continuing Threadwise LIVE testing. Reversible label and triage actions are approved without repeated permission prompts.
- Permanent prohibitions: never delete or trash email, and never send email. These prohibitions remain in force for all future testing.
- Current exact test: apply the existing `EA/Receipts` label to the designated open Amazon refund message through the production overlay, verify provider-confirmed success, then remove only that test label and verify cleanup.
- Safety configuration: the local helper will run with Gmail write-through and Gmail checks disabled for the read-only pass.
- Authentication: complete in the designated Brave Gmail `/u/0` session; the visible tab is the signed-in inbox.
- Helper: `http://127.0.0.1:8021/api/health` reports `ready`; the running process was verified with both `--disable-gmail-write-through` and `--disable-gmail-check`.
- Extension: `Threadwise Companion 0.3.2` was already loaded and enabled in Brave; no browser setting change or installation action was required.
- Credential boundary: no password, recovery code, 2FA code, cookie, or other credential was requested or handled by the agent.
- `LIVE`: the built production extension was exercised in the authenticated real Gmail DOM. The selected classification was supplied by an isolated local seed matched to the open immutable Gmail message identifier; Gmail checks and write-through remained disabled, so this is real-host interaction evidence but not provider-confirmed success evidence.

### Round 3 — LIVE read-only gate

- Builder/driver: lead agent; complete within the founder-approved read-only boundary.
- Real host: signed-in Brave Gmail `/u/0` with the unpacked production extension and local helper running with Gmail checks and provider write-through disabled.
- Visible states exercised: ready review, evidence disclosure, action-details disclosure, contextual actions, correction entry, safe cancellation, empty home, unsynced message, disabled-sync error, delayed reload/recovery, and selected-message persistence.
- Gmail coexistence: real message navigation and Older navigation remained usable; Gmail message scrolling worked with the overlay open and the Threadwise review context remained stable.
- Keyboard/accessibility: Enter activated the focused contextual correction action and Enter activated Cancel to return to review. Escape-to-minimize was not proven in the external browser session and appeared to lose focus.
- Reload/recovery: Gmail reload initially showed Threadwise Offline; the extension recovered to Ready with the same selected review after about 23 seconds.
- Provider boundary: `Accept Receipts` was not invoked and no Threadwise provider mutation was attempted. Provider-confirmed success/completion therefore remains untested.
- Incidental Gmail effect: opening an unread message through the real Gmail UI changed the inbox unread count from 36 to 35. It was not restored because marking it unread would itself be another provider write outside the approved boundary.
- Capture boundary: standard Windows Graphics Capture failed in this Brave environment; private fallback screenshots of ready, contextual-menu, and correction states were captured outside the repository. External Brave console/request capture was unavailable.
- `AUTOMATED`: unchanged `PASS` from Round 2; 48 controlled-browser screenshots, zero unexpected requests, focused suites green, and the known broad-suite exceptions remain recorded separately.
- `LIVE`: `PARTIAL PASS`. Real Gmail rendering, navigation, focusable contextual actions, correction/cancel, scrolling, reload, delayed recovery, empty, and truthful error behavior were observed. Provider-confirmed success/completion was not run because no exact Gmail label mutation is authorized.
- Biggest material gap: the critical provider-confirmed accept/success path has not been exercised through the production extension in real Gmail.
- Critic: separate fresh context; complete. The critic inspected the actual baseline, approved reference, controlled current render, and three private real-Gmail screenshots rather than relying on the implementation narrative alone.
- Critic assessment: current is clearly better than baseline and materially closer to Variant C, but its heavy border, cream surface, and shadows remain more visually assertive than Gmail and the reference.
- Scores: Gmail nativeness `3/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `3/5`; live reliability `3/5`.
- Recommendation: `BLOCKED`. `SHIP` is not permitted until the provider-confirmed critical flow is explicitly authorized and passes, and the founder approves the resulting real-Gmail behavior.

### Round 4 — provider-write truthfulness correction

- Justification: founder authorized reversible Gmail testing. The first production-overlay `Accept Receipts` attempt exposed a failed critical LIVE acceptance criterion, justifying one further bounded round.
- Provider baseline: authoritative Gmail read immediately before the attempt showed only `CATEGORY_UPDATES` and `INBOX`; the designated message did not have `EA/Receipts`.
- LIVE action: the production helper was restarted with Gmail write-through enabled and Gmail checks still disabled. The founder-approved `Accept Receipts` action was invoked through the built extension.
- Actual provider result: authoritative Gmail remained unchanged; no `EA/Receipts` label was applied.
- Incorrect product result: Threadwise locally accepted the decision and later displayed `Gmail labels applied` and `1 accepted Gmail change confirmed.`
- Root cause: Gmail client setup failure returns a `gmail-write-failed` summary with zero failure counters, so `ProviderWriteQueue` classifies the work as successful despite the attached error.
- Secondary observation: the concurrent local decision write briefly exposed an empty batch file to a background read, causing one transient JSON decode failure and a `Could not reach local companion server` surface. The file recovered validly; this separate atomic-write race is recorded but remains outside this round's single bounded correction.
- Single bounded correction: failed/unavailable Gmail provider setup must produce a failed provider-write result and retry/error UI, never a success claim.
- `LIVE`: failed critical provider-success acceptance. No Gmail label was applied, so no provider cleanup mutation was necessary.
- Builder: fresh context; complete. Added red-first regressions at the shared provider queue and Gmail sidebar activity seams, then changed only the shared queue classification so explicit `gmail-write-failed` and `provider-write-failed` modes remain retryable failures even when numeric counters are zero.
- Red evidence: two focused tests reproduced `done` instead of the required `error` state.
- Green evidence: the two regressions pass; 27 queue/runtime/Gmail+Proton adapter/workflow/runtime tests pass; 21 Proton review-console regressions pass; `git diff --check` passes.
- Repeat LIVE: helper restarted on the corrected code, local seed restored to pending, Gmail reloaded, and the approved production-overlay `Accept Receipts` action invoked again.
- Corrected visible result: `Gmail writes need attention`, `ERROR`, `1 accepted Gmail change could not be confirmed`, and `Try again`. No success or provider-confirmation claim was shown.
- Authoritative provider result: Gmail again showed only `CATEGORY_UPDATES` and `INBOX`; no `EA/Receipts` label was present.
- Permission isolation: through the connected Gmail provider, `EA/Receipts` was applied to the exact message, independently verified, removed, and independently verified absent. This proves the Gmail account and label are writable and cleanup is complete, but is not reported as production-extension end-to-end success.
- Remaining environment gap: the local production helper has no Google Desktop OAuth client secret or token; browser login and the connected Gmail provider do not automatically supply credentials to the helper.
- `AUTOMATED`: `PASS` for the bounded truthfulness correction.
- `LIVE`: `PASS` for truthful write-failure behavior and Gmail preservation; provider-confirmed success remains unavailable.
- Critic: separate fresh context; complete. The critic inspected the exact diff, strict regressions, and actual pre/post-fix real-Gmail screenshots.
- Critic assessment: bounded correction `PASS`; explicit failure-mode classification reuses the existing retry path without widening provider behavior. Tests would fail on the original logic and require error, retry, no success label, and successful retry.
- Scores: Gmail nativeness `3/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `3/5`; live reliability `3/5`.
- Biggest material gap: the production helper still lacks its own Google Desktop OAuth client secret/token, so the production-overlay -> helper -> Gmail -> provider-confirmed success path has not passed.
- Recommendation: `BLOCKED`. Connector-only permission proof cannot substitute for the critical product end-to-end success flow.
- Status: correction accepted; cleanup complete and Gmail has no test label. OAuth setup and final LIVE success remain pending.
- OAuth discovery: the signed-in Google Cloud project `email-agent-local-test` contains an existing Desktop OAuth client, `Email Agent Local Desktop`, but Google exposes only its client ID and no downloadable/recoverable client secret.
- OAuth attempt: a private gitignored local configuration using the existing public client ID reached the approved Gmail modification consent screen and completed the browser callback, but Google rejected the token exchange because the client secret was unavailable. No Gmail token was persisted.
- Required setup: create one new Desktop OAuth client in the existing project, download its JSON into the gitignored `data/gmail_credentials` directory, complete local Gmail modification consent, and repeat the production-overlay success test. Creating the persistent OAuth credential requires action-time founder confirmation.

### Round 5 — OAuth completion and provider-confirmed LIVE success

- Founder confirmation: explicit action-time approval was granted to create a new Desktop OAuth client. The standing Gmail boundary remained unchanged: reversible label testing is approved; sending and deleting email are prohibited.
- OAuth setup: created `Threadwise Local Desktop 2026-08-11` in the existing `email-agent-local-test` Google Cloud project, downloaded its JSON, and moved it into the gitignored `data/gmail_credentials/client_secret.json` path. No client secret or token was printed or committed.
- Authorization: completed the Google testing-app consent flow for the designated Gmail account with `gmail.modify`; the private refresh token was persisted under the gitignored Gmail token directory. No password, recovery code, 2FA code, cookie, or inbox content was requested as a credential.
- Provider baseline: authoritative Gmail read showed only `CATEGORY_UPDATES` and `INBOX`; the existing `EA/Receipts` label was absent from the designated message.
- LIVE action: restarted the production helper with Gmail write-through enabled, restored the isolated local review seed to pending, reloaded real Gmail with the built production extension, opened the queued review, and invoked the approved `Accept Receipts` primary action.
- Visible product result: the real Gmail overlay advanced to queue completion and displayed `DONE`, `1 accepted Gmail change confirmed.`, and `Background refresh done` without an error state.
- Authoritative provider result: a separate Gmail read showed `Label_24` (`EA/Receipts`) alongside `CATEGORY_UPDATES` and `INBOX`, proving the production overlay -> local helper -> Gmail write -> provider-confirmed success path completed end to end.
- Cleanup: removed only `EA/Receipts` from the designated message through the approved Gmail provider action and independently verified that the authoritative message labels returned to exactly `CATEGORY_UPDATES` and `INBOX`.
- Diagnostics: the helper's captured stdout and stderr were both empty after the successful flow; no helper-side console/request failure was recorded. External Brave DevTools capture remains unavailable.
- Teardown: stopped the write-enabled local helper after evidence capture and provider cleanup.
- Evidence: private real-Gmail success screenshot `variant-c-live-provider-success.png` is stored outside the repository with the existing founder-checkpoint artifacts. The image contains private inbox context and must not be published.
- `AUTOMATED`: unchanged `PASS` from Rounds 2 and 4.
- `LIVE`: `PASS` for the critical provider-confirmed accept/success path, with provider truth independently verified and the reversible test label fully cleaned up.
- Status: ready for a fresh critic inspection and founder checkpoint. Do not start onboarding or another slice before founder approval.
- Critic: separate fresh context; complete. The critic inspected the implementation, assertions, git status, baseline/current/reference images, and the real-Gmail provider-success capture.
- Critic assessment: the critical LIVE provider path now passes and live reliability reaches `4/5`. Variant C still does not meet SHIP because Escape retreat/minimize was not proven with focus inside real Gmail and appeared to miss when focus remained outside the overlay.
- Scores: Gmail nativeness `3/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `3/5`; live reliability `4/5`.
- Biggest material gap: live keyboard focus ownership for Escape retreat/minimize.
- Recommendation: `ONE MORE ROUND`, subject to founder approval. Founder approval remains required before shipping or beginning onboarding.

### Round 6 — founder-directed visual-first Variant C correction

- Founder contract: the previous cream, heavy-border live surface was explicitly rejected. This round was limited to the production Gmail shell and selected-message review; functional plumbing could not substitute for immediate visual resemblance to the approved Variant C reference.
- Builder: separate fresh context; complete. Product changes are confined to the shared Gmail companion shell/review presentation in `extensions/gmail_companion/content.js`; visual assertions were added to the focused Python and controlled-browser contracts. No provider, OAuth, Gmail mutation, or onboarding behavior changed in this round.
- Visible delta: 420px cream editorial panel replaced by a 408px white Gmail-adjacent shell with 1px neutral borders, 12px radius, restrained soft shadow, 52px header, 28px existing logo, quiet Ready state, purple progress and primary action, compact context/judgment/facts hierarchy, and a 40px primary action. Loading, error, and completion inherit the same white shell and purple action system.
- Red evidence: the new computed-style contract first found the header shrinking below 52px; a later short-height check found contextual-menu/primary-action collision. Both failures were corrected before green evidence.
- `AUTOMATED`: `PASS` for the bounded visual delta. Three targeted Python contracts, five focused JavaScript suites, content syntax, and diff check pass. Contextual-actions CDP produced 30 contained screenshots with zero unexpected requests; selected-explanation CDP produced 18 with zero unexpected requests; review-progression CDP produced 42 screenshots. Equivalent baseline/reference/current plus short, narrow, blocked, and receipt captures are retained outside the repository.
- `LIVE`: production extension reloaded in the authenticated real Gmail UI against the designated Amazon refund message with Gmail checks and provider writes disabled. The selected-message review loaded in the real Gmail DOM and visibly matches the compact white/purple Variant C direction. Contextual menu opened by mouse; Escape closed it; Gmail message scrolling remained intact while the overlay stayed fixed. No label, archive, delete, trash, send, reply, or forward action was invoked.
- Recovery note: the first live state read failed because the disposable local seed had no valid applied label while prior activity metadata was present. Adding the expected pending `receipt-billing` classification to the disposable seed restored `/api/harness-state` to 200. Gmail and repository files were not modified by this repair.
- Keyboard finding: after the contextual menu closed, a further Escape did not minimize/retreat the overlay, including when the menu button had owned focus. This remains an observed LIVE acceptance gap rather than a passed behavior.
- Visual finding: the main review shell now immediately resembles Variant C and is materially more native to Gmail. The contextual menu still retains the older cream card treatment and is visually less coherent than the new shell.
- Critic: separate fresh context; complete. The critic inspected the implementation and the actual baseline/reference/AUTOMATED/LIVE captures directly.
- Critic assessment: the main production shell crossed the visual bar and immediately resembles Variant C. The contextual menu is less coherent but does not lower overall Gmail nativeness below `4/5`.
- Scores: Gmail nativeness `4/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `3/5`; live reliability `4/5`.
- Single biggest material gap: Escape retreat from a focused interactive control. The first Escape closes the menu and restores focus to its button; the next Escape leaves the overlay open because the keyboard classifier rejects interactive targets before recognizing Escape.
- Recommendation: `ONE MORE ROUND`. Return only the bounded Escape classification/focus gap for red-green correction, then repeat focused AUTOMATED and LIVE validation.
- Founder gate: pending. Do not start onboarding or another slice before founder approval of the real Gmail result.

### Round 7 — bounded Escape retreat correction

- Justification: Round 6 fresh critic scored keyboard/accessibility `3/5` because real Gmail proved that Escape closed the contextual menu but a subsequent Escape did not retreat/minimize the overlay.
- Builder: separate fresh context; complete. Scope was limited to keyboard classification, one-shot focus handoff, visible collapse rendering, and focused regressions.
- First red: a focused contextual trigger inside Threadwise returned no Escape command. The queue-navigation classifier was corrected so unmodified Escape retreats from non-editable in-panel controls while editable targets, modifiers, outside-root input, Enter, and J/K isolation remain unchanged.
- First green: focused JavaScript suites and controlled-browser sequence passed, but the first repeat LIVE sequence still left the overlay visibly open. LIVE remained authoritative.
- Second red: the controlled browser reproduced the real-host seam by dispatching the post-close Escape from the synthetic Gmail host outside Threadwise. A narrowly armed document-capture handoff was added for one unmodified Escape within two seconds only after Threadwise keyboard-closes its own contextual menu. It disarms on unrelated input, editable target, modifier, click, state invalidation, timeout, or teardown; ordinary unarmed Gmail Escape remains untouched.
- Second green: the controlled browser passed the outside-root event sequence with unchanged request count, but repeat LIVE still appeared visibly open. Inspection confirmed Brave's unpacked extension path was the exact active checkout, eliminating a stale checkout as the cause.
- Visible-collapse red: the browser contract was tightened to require actual layout pixels, not only internal state: root width at most 71px, content hidden, workspace width zero, and minimize control hidden. This found a stylesheet-priority defect: `display:grid !important` kept the minus control visible after collapse.
- Bounded render correction: minimized rendering now sets the minimize control display with an explicit important inline value (`none` minimized, `grid` expanded).
- `AUTOMATED`: `PASS`. Five focused JavaScript suites and syntax pass. Context-actions CDP reports exact collapsed layout `{rootWidth:70, contentDisplay:'none', workspaceWidth:0, minimizeDisplay:'none'}`, 30 contained screenshots, unchanged request count, unarmed Gmail Escape pass-through, unrelated/editable/modifier safety, and zero unexpected requests. Queue-navigation CDP passes with zero forbidden requests. `git diff --check` passes.
- `LIVE`: `PASS` for the bounded critical flow. After reloading the production extension from the verified checkout in authenticated real Gmail, the uninterrupted menu-open -> Escape -> Escape sequence collapsed Threadwise to its 70px top-right logo tile. Gmail remained visible and usable; no provider or mailbox action was invoked.
- Evidence: `variant-c-live-escape-retreat-passed-final.png` is retained with the private founder-checkpoint artifacts outside the repository.
- Critic: separate fresh context; complete. The critic accepted the ordinary LIVE retreat and visible-collapse correction but found the one-shot handoff omitted `shiftKey`, allowing armed `Shift+Escape` to collapse Threadwise despite the unmodified-Escape safety claim.
- Modifier red: focused unit expected `Shift+Escape` on the contextual trigger to return no Threadwise command; current code returned `escape`.
- Modifier correction: both the queue-navigation modifier guard and the document one-shot handoff now include `shiftKey`.
- Modifier green: five focused JavaScript suites, content/queue/CDP syntax, context-actions CDP, and diff check pass. The controlled browser proves armed `Shift+Escape` is unprevented, disarms the handoff, leaves Threadwise open, and leaves the following ordinary Gmail Escape untouched; the normal unmodified two-Escape flow still visibly collapses to the 70px tile. Thirty contained screenshots and zero unexpected requests.
- Final critic: separate fresh context; complete. Technical verdict: `SHIP`, held at the mandatory founder visual checkpoint.
- Final scores: Gmail nativeness `4/5`; visual clarity `4/5`; action efficiency `4/5`; information density `4/5`; keyboard/accessibility `4/5`; live reliability `4/5`.
- Final critic assessment: no material technical gap remains in the Variant C milestone. The cream contextual menu is backlog polish, not a further-round gap. Release and onboarding remain prohibited until the founder approves the visible real-Gmail result.

### Round 8 — founder-reported offline/recovery correction

- Justification: the founder observed a live `Threadwise is not connected` dead end whose retry action appeared ineffective and whose brown/cream presentation still used the rejected legacy visual system.
- Root cause: the local helper had been intentionally stopped after validation. In addition, the extension's unchanged-selection cache prevented the five-second interval from checking helper health after a previously ready state, so an outage could remain stale. `Check again` only retried the connection and could not start the helper.
- Visual correction: replaced the legacy recovery template with the compact white/neutral/purple Variant C shell, one primary `Check again` action, quiet automatic-recovery guidance, and collapsed exact diagnostics. Loading, connecting, wrong-service, health-failure, and unreachable states share the same system.
- Truthfulness correction: manual retry immediately enters a disabled `Checking…` state. A failed retry leaves persistent visible feedback (`Still offline · checked just now`, or the state-appropriate unavailable/connecting equivalent) while preserving the exact technical cause under Details. Ready recovery clears the feedback.
- Reliability correction: added lightweight single-flight helper-health polling that bypasses the unchanged-message cache without issuing repeated full state reads. Helper-down transitions to Offline and helper-up performs one bounded state read before returning to review/home.
- Race correction: a fresh critic found that manual retry could bypass the in-flight guard while an automatic offline full-state read was pending. Red controlled evidence showed full reads `26 -> 27 -> 28`. The retry handler now joins the existing read; green evidence is `26 -> 27 -> 27`, one disabled `Checking…` state, and one truthful final failure result.
- `AUTOMATED`: `PASS`. Three focused Python contracts, five JavaScript suites, content/background/harness syntax, manifest/assets checks, and `git diff --check` pass. The controlled browser reports `ok: true`, 48 screenshots including 18 recovery states, zero unexpected requests, helper-down detection in 4.614 seconds, helper-up restoration in 4.813 seconds, and no overlap or dropped forced refresh during delayed probes.
- `LIVE`: `PASS` for the bounded recovery flow in the production unpacked extension running in authenticated real Gmail. With no Gmail/provider action invoked, helper-up displayed Ready, stopping the helper automatically produced the new Offline surface in about five seconds, manual retry produced persistent truthful feedback, and restarting the helper automatically returned Threadwise to Ready in about five seconds.
- Evidence: equivalent live before/current comparison `variant-c-offline-before-vs-current.png`; live states `variant-c-live-recovery-outage-detected.png`, `variant-c-live-recovery-retry-visible.png`, and `variant-c-live-recovery-restored.png`, retained outside the repository with the founder-checkpoint artifacts.
- Fresh critic: separate non-builder context; complete. The critic inspected the implementation, diff, controlled trace, and actual LIVE screenshots.
- Scores: Gmail nativeness `4/5`; visual clarity `5/5`; action efficiency `5/5`; information density `5/5`; keyboard/accessibility `4/5`; live reliability `4/5`.
- Single biggest material gap: none within this bounded offline/recovery slice.
- Recommendation: `SHIP` this bounded correction. Windows automatic helper startup/keepalive and legacy Home/activity styling are separate whole-product slices and are not claimed complete.
- Founder checkpoint: approved on 2026-08-11 with “Looks great.” The Variant C production visual milestone is accepted; the Goal may proceed to a separately bounded slice.
- Next observed product gap: a selected-message/test snapshot was presented as a one-item review queue and its completion could be read as inbox-wide completion. The founder approved the Variant C coverage prototype and an explicit user-triggered read-only `Check Gmail` refresh on 2026-08-11. Slice 7 may now implement truthful coverage states without changing the approved active-review surface; LIVE Gmail remains a separate founder-present gate.
- System boundary: the helper was restored for the founder session, but no Scheduled Task, packaged runtime, Start-menu control, Windows setting, Gmail data, provider action, credential, commit, or push was changed.

## Remaining risks

- Provider-confirmed success passes end to end, the reversible test label has been removed, and the founder approved the visible Variant C milestone on 2026-08-11.
- Windows startup remains unimplemented: after logon or a helper crash, Threadwise cannot yet start/restart the local helper without an external Windows control surface. This is the largest whole-product gap between live reliability `4/5` and `5/5`.
- The restored Home/activity surface retains legacy styling. It is outside the bounded current-message recovery correction but remains a visible product-consistency gap.
- The corrected recovery loop detects and restores the helper in about five seconds; a dedicated LIVE keyboard-only recovery capture remains evidence backlog rather than a material blocker.
- The first intro dismissal did not persist, while completing the intro via `Review this email` did persist across reload.
- Standard browser capture and external console/request inspection were unavailable; fallback screenshots succeeded, but console/network diagnostics remain a validation limitation.

## Slice 7 — Truthful Gmail coverage and freshness

- Visual authority: `codex/threadwise-coverage-prototype` commit `e4f1b58`, with the approved Variant C production review surface preserved.
- Product boundary: selected-email handling and provider coverage are independent. `Check Gmail` is explicit and read-only; unread mail is not presented as the review queue.
- Provider boundary: dedicated `/api/gmail-coverage-check` uses Gmail read-only list/get access only. It never calls `/api/gmail-check-run`, `/api/provider-sync-run`, or label/archive/delete/trash/send routes.
- Truth boundary: bounded or failed reads return partial/failed, never clear. Verified clear includes checked count, Gmail Inbox scope, freshness, and the explicit warning that Gmail may still contain unread mail.
- States: handled/unknown, checking, queue ready, direct Variant C review, verified clear, partial, stale, failed, and offline.
- AUTOMATED: `809/809` full repository tests; `131/131` focused coverage/UI tests; all companion Node suites; dedicated controlled-browser gate `18/18` normal/short screenshots, all contained, zero forbidden routes.
- Evidence: `docs/gauntlet-evidence/coverage-2026-08-11/coverage-trace.json` plus paired state screenshots in the same directory.
- Fresh critic round 1: ONE MORE ROUND because forced-Home coverage states retained `Ready` and failed/offline invented `Just now` without a completed check.
- Bounded correction: every displayed coverage state now owns the header; failed/offline without a check show `— / — / Unknown`, while previous counts and age are preserved when available.
- Fresh re-critique: PASS. Scores — Gmail nativeness `4/5`; visual clarity `5/5`; action efficiency `4/5`; information density `5/5`; keyboard/accessibility `4/5`; automated reliability `4/5`.
- Single biggest material remaining gap: none in the automated slice.
- Recommendation: `SHIP` to founder checkpoint.
- LIVE: pending. The production unpacked extension must be reloaded and exercised in real Gmail with the founder present before this slice is called complete or pushed/deployed.
- Opening the selected unread Gmail message caused Gmail's native unread count to change from 36 to 35; it was intentionally not restored without explicit write approval.
- Visual restructuring must not hide recovery, receipts, correction, or provider-scoped truth in less common states.
- The prototype's simplified accept-and-advance behavior cannot replace the production async and live-anchor contracts.
