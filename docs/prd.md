# PRD

Status: Completed bounded-slice PRD
Current as of: 2026-07-01
Builds on: `docs/v2-alignment.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, and `docs/handoff/2026-06-30-mvp-plus-one-public-demo-closeout.md`
Supersedes as current planning focus: `docs/archive/prd-mvp-plus-one-portfolio-demo-completed-2026-06-30.md`
Release target: MVP+2 Gmail daily usefulness
GitHub issue: `#7`

This PRD describes MVP+2 for Threadwise: make the Gmail-first product useful in daily life before expanding to ProtonMail.

Implementation status: completed in GitHub issues `#8` through `#14`. Follow-up review candidates `#15` and `#16` are complete.

## Problem Statement

Threadwise already proves a Gmail-first supervised inbox workflow:

- fresh Gmail batch fetch
- classification into the approved taxonomy
- bounded `EA/` label write-back
- limited `INBOX` removal for `promotions` and `spam-low-value`
- daily reports and a fuller dashboard
- Gmail companion sidebar
- in-context `Correct / Teach`
- unsubscribe inventory and explicit review paths

The completed MVP+1 made the project stronger as a portfolio artifact. The next milestone should optimize for the founder's day-to-day usefulness.

The current daily experience still has several practical gaps:

- The founder does not have a clear "what needs my attention today?" surface.
- Existing `unlabeled` and review queues show classification exceptions, but they do not reliably pull forward important emails that were classified correctly.
- Time-sensitive messages such as flights, bills, account closure warnings, security notices, appointment reminders, and recruiter/interview scheduling can hide inside normal categories.
- The product does not yet learn the founder's threshold for what belongs in the attention lane.
- The founder is not yet confident how to start Threadwise or trigger a Gmail run from the product UI.
- Running Threadwise still feels too close to a developer harness.
- LLM cost is likely low, but it is not currently visible in the product.
- The local artifact architecture is useful for audit and teaching, but it needs a later review so local storage does not drift into a stale or over-retentive mailbox mirror.

The core problem is:

> Can Threadwise become a daily Gmail assistant that pulls out the few emails the founder should not miss, explains why, lets the founder correct it, and can be started from the product instead of from developer commands?

## Solution

Build a Gmail-first daily usefulness milestone centered on a teachable **Needs attention** lane.

MVP+2 should add a separate attention evaluator that runs over newly processed Gmail messages and a bounded stored lookback. It should use an LLM pass over actual message content to identify email-linked attention candidates such as:

- travel timing and changes
- bills, renewals, and payment deadlines
- account closure, suspension, or service interruption risk
- security notices and suspicious account activity
- reply deadlines
- appointments and scheduled reminders
- recruiter outreach, interview scheduling, application follow-up, hiring next steps, and take-home work

The daily dashboard should open with a Needs attention section that separates high-confidence items from lower-confidence possible attention. Each item must say why it was surfaced, link back to the source message, and show that attention detection itself did not mutate Gmail.

MVP+2 should also add a user-triggered **Run Gmail check** flow from the Threadwise UI. The dashboard should be the first home for the button and run progress. The Gmail companion sidebar should show status and link into that dashboard flow. The run button should require confirmation because it may perform existing safe Gmail mutations and may incur small LLM cost.

Attention detection is non-mutating. Dashboard-triggered Gmail checks may perform only the current accepted Gmail actions:

- apply approved `EA/` labels
- remove `INBOX` only for `promotions` and `spam-low-value`

The milestone should include simple attention feedback first, then broader attention-rule proposal within the same MVP+2 scope:

1. Phase 1: run Gmail check, generate attention candidates, show the queue, persist simple feedback, and track LLM usage.
2. Phase 2: propose broader attention rules from feedback, preview consequences, and require founder approval before applying any broader rule.

## User Stories

1. As the founder, I want Threadwise to prioritize Gmail daily usefulness before ProtonMail expansion, so that the product helps my real workflow first.
2. As the founder, I want a Needs attention lane, so that I can see the few messages I should not miss.
3. As the founder, I want Needs attention to include emails that were classified correctly, so that important messages do not hide inside normal categories.
4. As the founder, I want flight and travel reminders surfaced, so that I do not miss time-sensitive travel details.
5. As the founder, I want bill and payment deadline reminders surfaced, so that I do not miss financial deadlines.
6. As the founder, I want account closure, cancellation, suspension, or service interruption warnings surfaced, so that I can intervene before consequences happen.
7. As the founder, I want security-sensitive account warnings surfaced, so that real account risks do not get buried.
8. As the founder, I want explicit reply-deadline emails surfaced, so that I do not miss commitments.
9. As the founder, I want appointments and scheduled reminders surfaced, so that I can prepare for real-world obligations.
10. As the founder, I want recruiter outreach and interview scheduling surfaced, so that job opportunities do not get lost.
11. As the founder, I want job-related scheduling links surfaced even when no email reply is required, so that I still act on hiring next steps.
12. As the founder, I want Threadwise to use actual message content for attention detection, so that urgency is not inferred only from coarse labels.
13. As the founder, I want attention detection to run across all newly processed Gmail messages, so that urgent items are not limited to unlabeled exceptions.
14. As the founder, I want a small stored lookback, so that recently fetched messages can be resurfaced when they become newly relevant.
15. As the founder, I want attention reminders linked to source emails, so that I can inspect the evidence.
16. As the founder, I want attention items worded like useful reminders, so that the daily view tells me what matters now.
17. As the founder, I want Needs attention now separated from Possible attention, so that strong signals do not get mixed with weak ones.
18. As the founder, I want lower-confidence possible attention capped and separated, so that the queue does not become noise.
19. As the founder, I want high-consequence insufficient-context items shown carefully, so that ambiguous risk is visible without overclaiming.
20. As the founder, I want ordinary insufficient-context items kept out of the daily queue, so that uncertainty does not swamp me.
21. As the founder, I want each attention item to show a plain-English reason, so that I can decide quickly whether it matters.
22. As the founder, I want each attention item to show evidence and category, so that I can audit the LLM's reasoning.
23. As the founder, I want attention detection to show that Gmail was not mutated by the attention pass, so that I trust the safety boundary.
24. As the founder, I want to mark an attention item as Good catch, so that Threadwise records useful positive feedback.
25. As the founder, I want to mark an item as Not attention, so that Threadwise does not keep surfacing noise.
26. As the founder, I want to mark Wrong reason, so that Threadwise can learn that an item mattered for a different reason.
27. As the founder, I want to mark a non-surfaced email as Needs attention, so that Threadwise can learn missed cases.
28. As the founder, I want feedback to persist per email, so that the same item does not keep reappearing after I correct it.
29. As the founder, I want Good catch recorded without silently creating rules, so that one confirmation does not overgeneralize.
30. As the founder, I want broader attention rules proposed from feedback, so that Threadwise can learn my threshold over time.
31. As the founder, I want broader attention rules to preview consequences, so that I can see what would change before approving them.
32. As the founder, I want to apply broader attention rules only after approval, so that Threadwise does not silently change my attention model.
33. As the founder, I want learned attention rules to auto-promote emails because promotion is non-mutating, so that useful reminders can appear without manual review.
34. As the founder, I want learned rules to promote to Needs attention now only when the email contains concrete time or consequence evidence, so that the urgent lane stays meaningful.
35. As the founder, I want learned rules without concrete time or consequence evidence to promote only to Possible attention, so that preference signals do not become alarms.
36. As the founder, I want a Run Gmail check button in the dashboard, so that I can trigger Threadwise from the product UI.
37. As the founder, I want the Gmail companion sidebar to show run/connectivity status, so that I know whether Threadwise is available.
38. As the founder, I want the sidebar to link into the dashboard run flow, so that I do not need to remember developer commands.
39. As the founder, I want the run button to require confirmation, so that accidental clicks do not trigger repeated Gmail writes or LLM calls.
40. As the founder, I want duplicate run requests blocked while a run is active, so that I do not accidentally start multiple runs.
41. As the founder, I want the UI to show running, succeeded, and failed states, so that I understand what happened.
42. As the founder, I want the confirmed dashboard run to perform the same existing safe Gmail mutations, so that product-triggered runs are useful and not only previews.
43. As the founder, I want attention LLM usage and estimated cost recorded, so that I know whether default-on attention is cheap in practice.
44. As the founder, I want a monthly or weekly LLM usage summary, so that I can see cumulative spend trends.
45. As the founder, I want attention detection default-on for confirmed runs, so that I do not forget to run the useful part.
46. As the founder, I want an escape hatch to disable attention detection, so that I can run Gmail classification without LLM cost if needed.
47. As the founder, I want compact payloads used by default, so that cost and privacy exposure stay bounded.
48. As the founder, I want a one-time full-body second pass for high-consequence ambiguous items, so that important cases can get enough context.
49. As the founder, I want full-body use recorded, so that I can audit when more sensitive context was sent to the model.
50. As the founder, I want attention artifacts to avoid duplicating email bodies, so that local retention does not get worse.
51. As the founder, I want the MVP+2 PRD to include a future local-data architecture review, so that retention and inbox freshness are revisited deliberately.
52. As the founder, I want the MVP+2 PRD to include a future startup/packaging review, so that the current local companion does not become accidental permanent product shape.
53. As a future agent, I want attention separated from classification, so that "what kind of email is this?" and "should I look now?" stay distinct.
54. As a future agent, I want an explicit attention artifact contract, so that attention candidates are not confused with unlabeled exceptions.
55. As a future agent, I want focused issue slices, so that MVP+2 can be implemented in reviewable increments.

## Implementation Decisions

- MVP+2 optimizes for Gmail daily usefulness before ProtonMail expansion.
- The MVP+2 thesis is: Gmail daily attention queue with LLM urgency reasons, audit-backed and non-mutating.
- Attention detection is a separate evaluator from classification.
- Existing classification labels may be passed as context, but they do not determine attention by themselves.
- The first attention levels are:
  - `needs_attention_now`
  - `possible_attention`
  - `not_attention`
  - `insufficient_context`
- `insufficient_context` is normally audit/debug only, but can appear in the queue when the possible consequence is high.
- Attention categories for MVP+2 are:
  - `travel`
  - `bill_due`
  - `account_risk`
  - `security`
  - `reply_deadline`
  - `appointment`
  - `job_opportunity`
- Job opportunity covers recruiter outreach, interview scheduling, application follow-up, hiring next steps, calendar scheduling links, and take-home work.
- Attention detection runs over all newly processed Gmail messages, not only unlabeled exceptions.
- Attention detection uses the latest batch first and fills the remaining cap with a small stored local lookback.
- MVP+2 uses stored lookback only. It does not actively fetch older Gmail messages beyond the normal daily batch for lookback.
- The default hard cap is 50 evaluated messages per run, with room for a CLI/config override later.
- Compact payloads are used by default: sender, subject, date, snippet, current labels, local/Gmail state when available, and a truncated body.
- A second LLM pass may use the full email body only when compact context is insufficient and the candidate has high-consequence cues.
- The expanded-context pass is capped at one follow-up pass per email.
- LLM calls should batch multiple compact email payloads where practical.
- Expanded-context second passes should run per email.
- Attention artifacts must record when full body was used, but must not duplicate full email bodies.
- The Gmail daily report should gain an `attention` section rather than producing a separate user-facing report.
- The `attention` section should have its own schema version and be conceptually separate from `unlabeled_exceptions`.
- The attention contract should include:
  - schema version
  - evaluated message count
  - lookback window
  - model metadata
  - usage metadata
  - grouped candidate counts
  - items
  - per item: message id, thread id, level, category, reason, evidence, source, handled state, feedback state, and Gmail mutation set to none
- Attention detection remains non-mutating.
- Dashboard-triggered Gmail checks may perform only existing accepted Gmail mutations:
  - apply approved `EA/` labels
  - remove `INBOX` only for `promotions` and `spam-low-value`
- Delete, trash, broad archive, send, reply, background scheduling, and new Gmail mutation scope remain out of scope.
- The dashboard is the first primary surface for the Needs attention queue.
- The Gmail companion sidebar shows status and links into the dashboard run/attention flow.
- A future iteration should revisit making urgent items more visually present immediately in the sidebar once the signal is useful.
- The dashboard gets a **Run Gmail check** button.
- The Run Gmail check button requires confirmation before starting.
- The confirmation must state that the run may apply existing safe Gmail changes and may incur small LLM cost.
- Duplicate run requests must be blocked while a run is active.
- Run status should include at least idle, running, succeeded, and failed.
- Attention feedback starts with:
  - Good catch
  - Not attention
  - Wrong reason
  - Mark as needs attention for non-surfaced emails
- Feedback persists per email before broader-rule learning.
- Good catch is recorded as a positive signal but must not silently create a broader rule.
- Broader attention rules are part of MVP+2 phase 2.
- Broader attention rules must preview consequences before approval.
- Learned attention rules may auto-promote emails into attention because promotion is non-mutating.
- Learned rules may promote to Needs attention now only when the email contains concrete time or consequence evidence.
- Learned rules otherwise promote to Possible attention.
- MVP+2 includes a generic local LLM usage tracker, first wired to attention detection.
- The usage tracker records feature, model, token counts, estimated cost, timestamp, and run id.
- Cost estimates are not billing truth, but should show whether usage is pennies, dollars, or unexpectedly growing.
- MVP+2 must not expand local email-body retention.
- Attention can read existing stored messages and send full bodies in the bounded second pass, but attention artifacts store compact decision/evidence metadata only.
- A formal follow-up issue candidate should revisit local data retention and inbox freshness.
- A formal follow-up issue candidate should revisit startup, packaging, and delivery model options.

## Testing Decisions

- Good tests should prove product behavior at the highest practical seam, not internal helper details.
- Existing Gmail daily-run tests should remain the regression anchor for safe label write-back and limited `INBOX` removal.
- Existing Gmail companion/dashboard tests should remain the regression anchor for user-visible sidebar and dashboard behavior.
- Attention evaluator tests should cover structured outputs from compact payloads, category mapping, level handling, batching, and second-pass fallback behavior using fake model clients.
- Attention daily-report tests should prove the `attention` section is written without confusing attention counts with `unlabeled_count`.
- Dashboard tests should prove Needs attention now and Possible attention render separately.
- Dashboard tests should prove each attention item shows reason, category/evidence, feedback state, and non-mutating Gmail status.
- Feedback tests should prove Good catch, Not attention, Wrong reason, and Mark as needs attention persist per email.
- Broader-rule tests should prove feedback can produce a rule proposal, preview consequences, and require approval before application.
- Run UX tests should prove the dashboard exposes a confirmed Run Gmail check flow, rejects duplicate active runs, and reports success/failure states.
- Safety tests should prove dashboard-triggered runs perform only the same safe Gmail mutations already allowed by the daily run.
- Usage tracking tests should prove token/cost events are recorded and summarized by feature and time window.
- Retention tests should prove attention artifacts do not store duplicate full email bodies.
- Failure tests should prove attention failure is fail-soft: Gmail daily classification/reporting should still complete or report clearly according to the run stage.
- No tests should call live Gmail or the live OpenAI API by default.
- Live Gmail, OAuth, and real inbox operations remain explicit-founder-approval paths.

## Out of Scope

- ProtonMail expansion for MVP+2.
- Provider-side ProtonMail mutation.
- Merged multi-inbox UX.
- Active Gmail lookback fetch beyond the current daily batch.
- Whole-mailbox reprocessing.
- Background scheduling or always-on syncing.
- True extension-controlled background server startup.
- Native messaging host, installer, packaged desktop app, menubar app, or auto-start-on-login implementation.
- Full local data retention/deletion implementation.
- Full inbox freshness/reconciliation architecture implementation.
- Deleting, trashing, broad archiving, sending, or replying to email.
- Unsubscribe execution changes beyond existing explicit supported paths.
- Treating attention as a classification label.
- Storing duplicate full email bodies in attention artifacts.
- Making a broad observability platform for LLM spend.

## Further Notes

- MVP+2 intentionally reverses the initial "portfolio credibility first" recommendation from the handoff. The founder chose Gmail usefulness first.
- ProtonMail remains part of the mature direction, but it should wait until the Gmail daily loop is more useful.
- The current extension + local companion remains the assumed delivery model for MVP+2. It is not considered a dead end, but startup/packaging deserves a later review.
- The local artifact architecture remains accepted for MVP+2, with the explicit guardrail that attention does not worsen local email-body retention.
- MVP+2 implementation progress reached `issues 7/7 => MVP+2 = 7/7 done`, using implementation issues `#8` through `#14` as the numerator/denominator.
- Multi-agent parallelization plan:
  - Batch 1: `#8` alone, because it defines the shared attention report contract.
  - Batch 2 after `#8`: `#9`, `#10`, and `#13` can run in parallel if agents coordinate through the `attention` report contract. `#13` can build the generic usage ledger while final attention integration waits for `#9`.
  - Batch 3 after `#10`: `#11` can run.
  - Batch 4 after `#9` and `#10`: `#12` can run.
  - Batch 5 after `#11`: `#14` can run.
- `#15` is the completed local data retention and inbox freshness HITL review; `#16` is the completed startup/packaging HITL review.
- Completed follow-up review: **Local Data Retention and Inbox Freshness Review**.
- Completed follow-up review: **Threadwise Startup and Packaging Model Review**.
- Published MVP+2 issue briefs:
  - `#8` Add Gmail attention contract to daily report
  - `#9` Generate Gmail attention candidates with LLM
  - `#10` Show Needs attention in daily dashboard
  - `#11` Persist attention feedback
  - `#12` Trigger Gmail check from dashboard
  - `#13` Track LLM usage locally
  - `#14` Propose attention rules from feedback
  - `#15` Local data retention and inbox freshness review
  - `#16` Threadwise startup and packaging model review
- The next workflow step is to choose whether to triage one of the retention/freshness follow-ups from `#17` through `#21`, triage one of the startup/packaging follow-ups from `#22` onward, or open the next product alignment cycle.
