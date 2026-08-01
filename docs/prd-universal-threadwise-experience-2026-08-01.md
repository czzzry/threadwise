# Universal Threadwise Experience PRD

Status: Implemented; pending live Proton acceptance and legacy-console removal
Current as of: 2026-08-01
Builds on: `docs/v2-alignment.md`, `docs/prd-async-threadwise-extension-2026-07-10.md`, and `docs/issues/138-add-proton-bridge-review-console.md`
GitHub parent issue: `#96`

## Problem Statement

Threadwise currently presents two different products. Gmail has an inbox companion with selected-email context, conversational teaching, impact previews, background application, and activity feedback. ProtonMail has a separate local review console with different controls and a narrower teaching model.

The founder cannot build a reliable habit around Threadwise while the interaction depends on the provider. Improvements and bug fixes can also drift because the Gmail and Proton experiences are rendered and evolved separately.

The required outcome is user-visible parity: Threadwise should feel and behave like the same product in Gmail and ProtonMail. The existing Gmail experience is the baseline, but shared improvements may change both providers when they produce a better common experience.

## Solution

Build one provider-neutral Threadwise side panel that is automatically present in its minimized state on Gmail and ProtonMail. It never expands without the founder choosing to open it. Its expanded review experience uses the existing Gmail panel workflow as the behavioral baseline.

Any standalone batch-review page is a secondary entry point into the same interaction implementation, not a separate product and not a requirement for this milestone. Gmail and Proton-specific behavior sits behind provider adapters responsible for mailbox context, message retrieval, matching, label writes, verification, and provider navigation.

Inbox data, queue state, and reporting remain provider-scoped. The product does not merge Gmail and Proton into one inbox. It makes the workflow identical while preserving clear account and provider identity.

The milestone is successful when the founder can use Threadwise on Proton in the same way they use Threadwise on Gmail at the start of this work. A parity inventory of the live Gmail companion must be captured before implementation and used as the acceptance baseline. A shared improvement is complete only when it is available and verified on both providers.

## User Stories

1. As the founder, I want Threadwise to appear automatically in a minimized state on Gmail and Proton, so that it is available without obstructing either inbox.
2. As the founder, I want Threadwise to remain minimized until I open it, so that it never interrupts normal email use.
3. As the founder, I want the same control to open, minimize, and reposition Threadwise on both providers, so that I do not learn two interaction patterns.
4. As the founder, I want the expanded panel to use the same layout, language, controls, and states on both providers, so that provider switching feels effortless.
5. As the founder, I want Threadwise to identify the provider and account automatically, so that I do not manually select the inbox I am viewing.
6. As the founder, I want Gmail and Proton queues to remain separate, so that review counts and memory cannot leak between inboxes.
7. As the founder, I want the panel to follow the currently opened email when provider context can be identified reliably, so that I can inspect or correct it in place.
8. As the founder, I want a reliable queue fallback when selected-email context cannot be identified, so that Proton website changes do not make Threadwise unusable.
9. As the founder, I want the same Home state when no email is open, so that status and pending review work are predictable.
10. As the founder, I want the same classification, primary label, additional labels, confidence, and plain-language explanation on both providers.
11. As the founder, I want `Accept and next` to advance immediately on both providers while the mailbox update continues in the background.
12. As the founder, I want to change a suggested label using the same controls on both providers.
13. As the founder, I want to write natural-language feedback on either provider, so that Threadwise can learn what I mean rather than requiring rule syntax.
14. As the founder, I want written feedback interpreted by the LLM with the complete email as context during the training phase, so that deterministic shortcuts do not distort my instruction.
15. As the founder, I want to see a short human-readable account of what Threadwise understood before I apply a lesson.
16. As the founder, I want to force LLM reinterpretation from either provider when the initial understanding is wrong.
17. As the founder, I want the same choices for applying a correction to this email, future matching emails, or matching Inbox emails.
18. As the founder, I want broader matches previewed before they are changed, so that one correction cannot unexpectedly rewrite unrelated mail.
19. As the founder, I want one-off or rare instructions prevented from becoming broad future rules unless I explicitly refine them.
20. As the founder, I want primary and additional labels represented consistently, so that accepting one label does not silently reject valid secondary labels.
21. As the founder, I want the in-panel review mode to work beside the opened email in Gmail and Proton, so that reviewing either provider follows the familiar Gmail workflow.
22. As the founder, I want to open the original message in Gmail or Proton without losing my current review draft or queue position.
23. As the founder, I want pending, successful, and failed mailbox updates shown in the same recent-activity area.
24. As the founder, I want failed writes to remain retryable without repeating the teaching conversation.
25. As the founder, I want deleted, moved, already labelled, or no-longer-Inbox messages reconciled against the live provider, so that completed work does not return to review.
26. As the founder, I want changes to shared Threadwise interactions to appear on Gmail and Proton together, so that the two experiences cannot drift again.
27. As the founder, I want provider-specific limitations stated only when they materially affect an action, so that normal use remains consistent and understandable.
28. As the founder, I want Threadwise to preserve provider write receipts and an auditable history, so that I can trust background changes.
29. As the founder, I want labels, a primary label, and a future single folder destination represented as distinct concepts, so that later folder automation does not confuse classification.
30. As the founder, I want accessibility, keyboard behavior, responsive containment, and loading behavior verified equally on both providers.

## Implementation Decisions

- The existing Gmail companion is the initial behavioral baseline, not a permanent Gmail-specific implementation.
- The side panel automatically mounts in a minimized state on supported Gmail and Proton pages. It does not auto-expand. Expansion persists through navigation within the current browser tab until the founder minimizes it or closes the tab.
- Gmail and Proton side panels share the same rendering implementation, interaction state machine, teaching controls, copy, and activity model.
- A standalone batch-review page may reuse the shared experience later, but it is not required for provider parity and must not become a second interaction implementation.
- Shared UX code must not branch by provider except where provider identity or a genuine capability difference must be displayed.
- Provider adapters form the mailbox seam. They hide provider-specific message identity, selected-message discovery, message retrieval, matching, label application, write verification, and navigation.
- The provider-neutral workflow forms the review seam. It owns current-item state, drafts, interpretation, impact preview, scope selection, optimistic advancement, activity receipts, retry state, and queue reconciliation.
- Gmail and Proton use separate provider-scoped queues, message identities, rules, write receipts, and reconciliation state.
- Rules remain provider-specific for this milestone. Cross-provider learning requires a later explicit product decision.
- Written teaching feedback uses LLM interpretation with complete readable-message context during the training phase. Deterministic classification remains available when the founder supplies no written teaching feedback.
- Applying a decision records the local review transition and advances the interface before the provider write completes. Provider completion or failure updates recent activity asynchronously.
- A Proton selected-email connector may use provider-page context when reliable, but the canonical Proton queue and message content come from Bridge-backed Threadwise state. Loss of page context must not block review.
- A feature-parity inventory will capture every founder-visible Gmail companion state and action before implementation. Each item must either work identically on Proton or be explicitly excluded from this PRD before the milestone can complete.
- Labels are many-valued classifications. One label may be designated primary for display and folder-policy purposes. Folder destination is a separate, single-valued concept reserved for later work.
- Existing provider safety boundaries remain in force unless separately approved. Architecture cleanup does not authorize new live mailbox mutations.
- The shared experience may require replacing Gmail-specific rendering and request orchestration. Behavior will be characterized before replacement, and migration will proceed through bounded vertical slices.

## Testing Decisions

- Test the shared product at the highest user-visible seam: the same input review state must produce the same controls, copy, transitions, and outcomes for Gmail and Proton.
- Capture the current live Gmail companion behavior as a provider-parity acceptance inventory before restructuring it.
- Use fake Gmail and Proton adapters to prove the shared workflow without touching live inboxes.
- Contract tests will run the same review, teaching, scope, optimistic-advance, receipt, failure, retry, and reconciliation scenarios against both adapters.
- Browser acceptance will verify minimized-by-default behavior, explicit expansion, panel movement and containment, selected-email mode, Home mode, review mode, and full-workspace handoff on representative Gmail and Proton pages.
- Browser acceptance will verify that a shared interaction change is not shipped for only one provider.
- Proton context-detection tests will prove graceful fallback to the provider-scoped queue when the selected message cannot be mapped reliably.
- Existing Gmail companion, teaching-workflow, provider-writer, Proton review, queue-reconciliation, and analytics tests provide prior art and regression coverage.
- Live-provider verification remains a separately approved final step. It must distinguish read-only context checks from provider writes and preserve audit evidence.
- Performance acceptance will verify that accepting a decision advances without waiting for provider completion and that background status remains visible and retryable.

## Out of Scope

- Merging Gmail and Proton into a combined inbox or combined default review queue.
- B-label taxonomy migration.
- Folder structure design or automatic folder routing.
- Broad archive, delete, Trash, Spam, send, reply, or compose behavior.
- Building a complete replacement email client.
- Team accounts, shared inboxes, or multi-user infrastructure.
- Cross-provider rules or automatic transfer of learned sender rules between accounts.
- Removing existing provider safety and approval requirements.
- Styling-only duplication of the Gmail panel inside the existing Proton console.

## Further Notes

The existing Proton console was intentionally approved as a narrow Bridge-backed experiment. This PRD supersedes that console as the destination user experience while retaining its safe provider adapter behavior where useful.

The first implementation slices should prove one complete shared path before broad migration: open one Proton review item in the same in-panel review experience used by Gmail, teach or accept it through the shared workflow, advance immediately, complete the verified label write in the background, and show the receipt. The equivalent Gmail path must use the same interaction implementation in the same slice.
