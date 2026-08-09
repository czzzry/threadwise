# Threadwise World-Class Triage Gauntlet PRD

Status: Current product-direction PRD; implementation proceeds one triaged slice at a time
Current as of: 2026-08-09
Builds on: `docs/v2-alignment.md`, `docs/prd-universal-threadwise-experience-2026-08-01.md`, and the founder's August 9 Gauntlet brief
GitHub parent issue: `#104`
Current slice map: `docs/threadwise-gauntlet-slice-map-2026-08-09.md`

## Problem Statement

Threadwise already proves a safe, teachable email-triage loop inside Gmail and Proton Mail, but it does not yet feel like the best email-triage product a new or experienced user could adopt. The real companion can classify, explain, review, teach, apply bounded changes, show receipts, retry failures, and preserve provider separation. The remaining gap is product coherence and speed: onboarding is only a detached throwaway prototype, the panel exposes too much operational structure, contextual actions are mouse-first, and Zero-level search, filtering, batch ergonomics, and compact configuration are incomplete.

The founder wants a serious upgrade without changing the Threadwise logo or replacing the Gmail-overlay product with a separate inbox. AI may classify, explain, and interpret teaching feedback, but Threadwise must not draft, write, send, forward, or auto-respond to email.

## Solution

Run a continuing Gauntlet Loop over the Threadwise Gmail-overlay experience. Break the product into the smallest independently useful and judgeable vertical slices. For each important slice, a fresh-context builder produces a real working result and a separate fresh-context critic inspects the real output against the applicable bar, identifies the single largest remaining gap, and sends that bounded gap into the next round.

Use Mail-0/Zero as the functionality bar, adapted to an overlay rather than copied as an inbox client. Use Grammarly as the bar for intelligence attached to the currently relevant email, Refined GitHub as the bar for native host integration and restraint, Raycast as the bar for contextual actions and keyboard flow, and Linear only as inspiration for compact progressive-disclosure configuration.

The first production slice is a provider-aware, Gmail-first onboarding experience inside the existing companion. It must get a new user from explicit panel open to a real safe review state without provider selection, fake metrics, fake connection tests, API-key ceremony, or mailbox writes.

## User Stories

1. As a new user in Gmail, I want Threadwise to appear minimized, so that it is available without obstructing my inbox.
2. As a new user, I want onboarding to begin only after I open Threadwise, so that the extension never interrupts normal Gmail use.
3. As a new user, I want Threadwise to detect the inbox I am already viewing, so that I do not choose Gmail from a redundant provider screen.
4. As a new user, I want to understand Threadwise's value in one compact view, so that setup does not feel like a separate application.
5. As a new user, I want to know that Threadwise labels, explains, and asks before broader changes, so that its autonomy is predictable.
6. As a new user, I want an explicit statement that Threadwise does not write or send replies, so that the product boundary is clear.
7. As a new user, I want to skip onboarding, so that an experienced user can reach the product immediately.
8. As a returning user, I want a completed or dismissed onboarding flow to stay out of my way, so that first-run guidance does not repeat.
9. As a user, I want onboarding to hand me into a real selected-email or needs-attention review, so that my first success is product value rather than configuration completion.
10. As a user, I want onboarding claims to come from current Threadwise state, so that I never see fabricated coverage, schedules, or success.
11. As a user, I want a truthful offline or not-ready path, so that a missing local companion is explained without false connection claims.
12. As a user, I want my current Gmail message to remain the interaction context, so that I never restate the email to Threadwise.
13. As a user, I want one obvious primary action for the current state, so that triage decisions are fast and calm.
14. As a user, I want secondary actions hidden behind contextual disclosure, so that the panel does not become a dashboard.
15. As a user, I want to understand why an email received its label and why it is in a queue, so that I can trust or correct the decision.
16. As a user, I want to correct a decision with one clear entry point, so that AI mistakes are one click away from repair.
17. As a user, I want broader impact previewed before any matching emails change, so that teaching remains bounded and auditable.
18. As a user, I want receipts to distinguish local state, provider confirmation, partial success, and failure, so that Threadwise never claims work it did not complete.
19. As a user, I want failed operations to remain retryable without losing my teaching draft, so that recovery does not repeat work.
20. As a keyboard user, I want a contextual action entry point, so that I can discover the actions relevant to the selected email.
21. As a keyboard user, I want Enter to perform the primary action and Escape to retreat safely while the panel is focused, so that triage does not require a mouse.
22. As a Gmail user, I want Threadwise shortcuts to avoid Gmail compose and reply shortcuts, so that the overlay never hijacks host behavior.
23. As a user clearing a review queue, I want to move to the next or previous item quickly, so that high-volume triage remains fluid.
24. As a user, I want to filter the current provider-scoped queue by sender, subject, label, and status, so that I can find the next useful decision.
25. As a user, I want no-results and clear-filter states, so that search never looks like missing mail.
26. As a user, I want small bounded batch-selection workflows with an explicit impact preview, so that repeated decisions can be handled efficiently without broad hidden mutation.
27. As a user, I want Threadwise to distinguish verified zero, no reviewable items, stale sync, and unavailable state, so that “inbox zero” is never an unsupported claim.
28. As a user, I want a clear queue-complete moment, so that finishing a review session feels final and trustworthy.
29. As a user, I want compact settings for Threadwise behavior only, so that the extension does not duplicate Gmail settings.
30. As a user, I want density, explanation visibility, onboarding replay, and keyboard help progressively disclosed, so that configuration stays compact.
31. As a user, I want unsubscribe opportunities surfaced beside relevant messages, so that the action is contextual and explicitly approved.
32. As a user, I want activity, undo where safe, and retry available without dominating the first viewport, so that trust tools remain close but quiet.
33. As a user, I want the panel to remain contained at compact, expanded-review, and narrow viewport sizes, so that Gmail stays usable.
34. As a user using assistive technology, I want meaningful labels, focus order, live status, and keyboard reachability, so that the full triage loop is accessible.
35. As a user, I want fast rendering and bounded refresh work, so that Threadwise feels native rather than layered on.
36. As a Gmail user, I want Threadwise additions to look and behave like a respectful extension of Gmail, so that the host and extension feel coherent.
37. As a Proton user, I want shared interaction improvements to preserve the provider-neutral workflow and provider-scoped state, so that parity does not create a merged inbox.
38. As the founder, I want the existing Threadwise logo preserved everywhere, so that product identity remains intact during redesign.
39. As the founder, I want no AI writing or auto-response behavior, so that the product remains a triage tool.
40. As the founder, I want each important piece judged independently against the named bars, so that polish is evidence-based rather than self-declared.

## Implementation Decisions

- The Threadwise logo and app icon are fixed. All other visual and interaction choices may change when the user experience wins.
- Threadwise remains a browser overlay on Gmail. It must not become a separate inbox application, a unified-inbox replacement, or a Gmail clone.
- Current Gmail/Proton provider separation, provider-scoped queues, rules, receipts, and safety boundaries remain in force.
- Shared companion behavior should stay provider-neutral. Gmail is the first acceptance surface for the Gauntlet, not a reason to fork the implementation.
- AI may classify, explain, summarize triage evidence, and interpret teaching feedback. It must not compose, draft, reply, forward, send, or auto-respond.
- The real extension starts minimized and never auto-expands. First-run guidance appears only after the user explicitly opens the panel.
- Onboarding is part of the real companion, not a full-screen setup product. It detects the active provider, uses current Threadwise state, offers skip, persists completion by onboarding version, and hands off to the existing Home or review workflow.
- The first onboarding slice requests no AI key, credentials, OAuth, provider authentication, or new provider action. It performs no mailbox write.
- The current throwaway onboarding prototype is a source of hypotheses, not a visual or behavioral implementation contract. Its fake metrics, fake connection test, fake schedule, fabricated `TW` mark, and detached full-page layout must not ship.
- Mail-0/Zero capabilities are adapted only when they improve triage inside Gmail. Compose, reply, drafts, unified inbox, full mailbox navigation, snooze, archive, and delete remain Gmail responsibilities unless separately approved.
- Contextual action surfaces expose only actions valid for the current object and state. Keyboard handling is panel-scoped, ignores text-entry targets, and must not collide with Gmail shortcuts.
- Search and filtering operate on the already-loaded provider-scoped Threadwise queue before any broader indexing work is considered.
- Existing optimistic advancement, provider receipts, retry, reconciliation, and audit behavior remain the trust baseline.
- No new dependency, service, framework, credential flow, or live-provider mutation is authorized by this PRD.
- Every important slice follows builder → independent critic → bounded correction. A slice wins only when it passes the rubric, beats its baseline by at least ten points where a scored A/B is feasible, wins at least four of six fixed tasks, and introduces no hard-gate regression.

## Testing Decisions

- Test at the highest existing user-visible seam: the companion rendered inside a controlled synthetic Gmail host with the real content-script interaction model.
- The onboarding state module should also be testable with deterministic storage and product-state inputs, but DOM and browser acceptance are the authority.
- Browser acceptance must prove minimized-by-default behavior, explicit open, first-run visibility, skip, continue, completion persistence, reload behavior, and handoff into the existing Home or review state.
- Intercept product requests during onboarding and fail if the flow invokes Gmail sync, Proton sync, teaching apply, safety apply, unsubscribe execution, credentials, or provider clients.
- Verify the approved icon asset is used and no substitute `TW` mark appears.
- Verify keyboard focus, Escape behavior, readable live status, reduced motion, compact width, expanded width, and a narrow viewport without overflow or Gmail-host displacement.
- Preserve the existing provider-adapter, companion analytics, focused companion UI, and repo-wide unit suites as regression coverage.
- Critics inspect the actual rendered result, not only source or test claims. Use anonymized baseline/candidate screenshots and task recordings for blind A/B comparison when practical.
- The fixed critic task pack is: minimized footprint; first correct action on a selected email; safe current-email decision; context change without stale state; open/cancel explanation or teaching; keyboard-only completion; onboarding-to-first-review handoff.
- Record first-correct-action rate, completion time, clicks or keystrokes, wrong-message actions, context switches, visible control count, scrolling, overflow, and false-success or no-op events.
- Live-provider reads or writes remain separately approval-gated and must distinguish `LIVE`, `AUTOMATED`, `PASS`, `FAIL`, and `BLOCKED` evidence.

## Out of Scope

- Changing or replacing the Threadwise logo.
- A separate Threadwise inbox, unified inbox, email client, or Gmail replacement.
- AI-generated email writing, auto-response, reply, forward, compose, drafts, or send.
- New delete, Trash, Spam, broad archive, autonomous unsubscribe, provider-rule, or other mailbox mutation.
- Merging Gmail and Proton state or transferring learned rules across providers.
- Team accounts, shared inboxes, or multi-user infrastructure.
- Rebuilding the current runtime architecture before a vertical slice requires it.
- Treating the throwaway onboarding prototype as shippable product code.

## Further Notes

The August 9 baseline rubric scores the real companion approximately 70/100 and the detached onboarding prototype 17/100. The real companion is strongest in contextual provider state, safe scope, receipts, retries, and recovery. Its largest functional UX gap after onboarding is the absence of a queue-local search and Raycast-style keyboard/contextual action surface.

The first slice therefore closes context-bound activation. The next planned slice combines provider-scoped queue filtering with safe panel-scoped keyboard navigation. Later slices remain decomposed candidates until the preceding critic round establishes their exact biggest gap.
