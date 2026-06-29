# PRD

Status: Current bounded-slice PRD
Current as of: 2026-06-29
Builds on: `docs/v2-alignment.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, `docs/handoff/2026-06-29-queue-drained-and-compiled-rules-hardened.md`
Supersedes as current planning focus: `docs/archive/prd-memory-runtime-milestone-completed-2026-06-29.md`
Release target: Gmail first serious release
Next release target after this: founder's ProtonMail inbox in MVP+1

## Problem Statement

The repo now proves the backend trust milestone that mattered most for the classifier itself:

- deterministic plus memory plus founder feedback can reach under `10%` unresolved on the current stored corpora
- the queue, safety lane, runtime cascade, unsubscribe plumbing, and reporting backbone all exist

But that does not yet equal a real release product.

The current system still feels too much like supporting infrastructure:

- local workbench
- review queue
- readiness reports
- batch tooling

The founder does not want the product to live mainly in a separate review tool.

The next real product must live in the inbox itself.

The founder wants a Gmail-first release where:

- the agent appears as a browser-based companion sidebar in Gmail
- the sidebar shows what the agent thinks about the currently selected email
- the user can correct the agent in context
- the agent can acknowledge feedback conversationally
- the agent can learn from that feedback carefully
- the agent can surface when a correction would affect other existing emails and ask before applying broader changes
- the user can see a compact daily summary of what happened
- unsubscribe opportunities are surfaced and actionable

So the next product problem is no longer "can the classifier work?" It is:

> Can we turn the proved backend into a trustworthy, inbox-native Gmail companion that feels like a teachable agent rather than a disconnected review system?

## Solution

Build the first serious Gmail release as a browser-based inbox companion sidebar.

The sidebar should be the primary product surface and should:

- attach to the active Gmail browsing session
- be minimizable
- react to the currently selected email in real time
- show the email's current classification, handling status, and a short plain-English reason
- expose `Correct / Teach`
- allow a short conversational correction loop
- acknowledge what the agent understood
- show whether the agent thinks the correction is:
  - only for this email
  - a sender or family lesson
  - a broader future rule candidate
- surface broader impact before changing any other existing emails
- let the user choose:
  - apply only to this email
  - apply to matching emails too
  - use for future emails only
  - refine this
- preserve the previous interpretation when refining so the user can compare old vs revised understanding
- show unsubscribe availability for the current email when relevant
- include a compact daily summary in the sidebar and hand off to fuller dashboard and unsubscribe views when needed

The release should remain Gmail-first:

- Gmail is the release target
- ProtonMail belongs in MVP+1 after the Gmail experience is real and trustworthy
- the architecture should still preserve a path to a more magical thread-native experience later without requiring that risk now

## User Stories

1. As the inbox owner, I want the agent to appear in Gmail beside the email I am reading, so that the product feels like part of my inbox workflow.
2. As the inbox owner, I want the companion sidebar to be minimizable, so that it does not dominate my inbox when I do not need it.
3. As the inbox owner, I want the selected email's current classification shown first, so that I immediately know what the agent thinks this email is.
4. As the inbox owner, I want a short plain-English reason shown by default, so that I can trust the decision without reading a long explanation.
5. As the inbox owner, I want deeper reasoning and provenance behind a small details affordance, so that I can inspect the decision when I care without cluttering the everyday UI.
6. As the inbox owner, I want the sidebar to tell me whether the email was auto-handled, left visible, or still needs attention, so that I understand what the agent already did.
7. As the inbox owner, I want a clear `Correct / Teach` action on the selected email, so that I can quickly intervene when the agent is wrong.
8. As the inbox owner, I want to relabel the current email quickly and optionally explain what I meant, so that I can both fix the email and teach the agent.
9. As the inbox owner, I want the agent to reply briefly after I correct it, so that I know it understood my feedback.
10. As the inbox owner, I want that acknowledgment to say what the agent thinks it learned, so that I can detect misunderstanding early.
11. As the inbox owner, I want the agent to decide whether the feedback is a one-off fix, a sender or family lesson, or a broader rule candidate, so that learning becomes structured rather than ad hoc.
12. As the inbox owner, I want corrections to start from the email I am looking at but to generalize across future or similar emails when appropriate, so that I do not have to teach the same thing repeatedly.
13. As the inbox owner, I want the agent to tell me if my feedback would change existing classifications on other emails, so that broader consequences are visible before they happen.
14. As the inbox owner, I want any broader existing-email rewrite to require confirmation first, so that the agent cannot silently change a large set of mail.
15. As the inbox owner, I want the impact summary to tell me how many emails would change and how, so that I can judge whether the agent interpreted me correctly.
16. As the inbox owner, I want to choose whether to apply a correction only to the current email, to matching existing emails too, or only to future emails, so that I control the blast radius.
17. As the inbox owner, I want a `Refine this` option when the agent's interpretation is off, so that I can keep clarifying until we are aligned.
18. As the inbox owner, I want the current and revised interpretation preserved during refinement, so that I can see whether the agent actually changed its understanding.
19. As the inbox owner, I want broader confirmed changes to apply immediately or visibly refresh right away, so that the product feels responsive instead of deferred.
20. As the inbox owner, I want the agent to remain mostly reactive, so that the inbox stays calm.
21. As the inbox owner, I want bounded prompting, so that the agent can surface a few important clarifications without turning my day into endless chat.
22. As the inbox owner, I want unanswered prompts to degrade gracefully, so that ignoring a clarification does not break the rest of the system.
23. As the inbox owner, I want the sidebar to be useful even when nothing is wrong, so that it feels like the normal product surface rather than only an exception tool.
24. As the inbox owner, I want the sidebar to show a compact daily summary of what happened, so that I understand the day's automation at a glance.
25. As the inbox owner, I want that compact summary to be operational first, so that I see what came in, what was categorized, and what needs attention.
26. As the inbox owner, I want the dashboard to be fuller than the sidebar, so that I can drill into details without bloating the inbox surface.
27. As the inbox owner, I want the dashboard to remain secondary, so that the inbox stays the center of gravity for daily use.
28. As the inbox owner, I want the sidebar to show when unsubscribe is available for the selected email, so that subscription management is visible in context.
29. As the inbox owner, I want obvious one-email unsubscribe opportunities to be actionable from the sidebar, so that simple cases stay fast.
30. As the inbox owner, I want broader subscription-family selection, preview, and confirmation in a fuller unsubscribe view, so that unsubscribe management remains explicit and safe.
31. As the inbox owner, I want the dashboard to show what the agent changed today, so that I can trust the system without reading a giant audit log.
32. As the inbox owner, I want the history emphasis to stay lightweight, so that the product remains practical instead of feeling like enterprise governance software.
33. As the inbox owner, I want safety-sensitive mail to remain visibly separate, so that important caution cases are not flattened into ordinary category automation.
34. As the inbox owner, I want the agent to ask more rather than less while I am still teaching it, so that early learning is careful and aligned.
35. As the inbox owner, I want the product to stay focused on my personal inboxes and not drift into a team/shared-inbox tool, so that the experience remains sharp.
36. As the product lead, I want Gmail to be the first serious release target, so that we can ship one coherent product before broadening to other providers.
37. As the product lead, I want ProtonMail to be the next release after Gmail, so that the multi-inbox vision stays real without blocking the Gmail launch.
38. As the product lead, I want the sidebar architecture to preserve a path to more magical thread-native rendering later, so that the first robust version does not trap the product in a dead-end UI model.
39. As the product lead, I want the conversation model separate from the rendering surface, so that the same correction interaction can later appear in a more native-feeling presentation.
40. As the product lead, I want provider adapters separated from the product interaction model, so that Gmail-first release decisions do not corrupt the future ProtonMail path.

## Implementation Decisions

- The release should be Gmail-first. The current bounded slice should not try to ship Gmail and ProtonMail as equal first-class product surfaces at the same time.
- The primary product surface should be a browser-based Gmail companion sidebar. The current local workbench can inform the implementation, but it should not remain the main user-facing story.
- The sidebar should be minimizable and should default to a compact operational state rather than an always-open chat transcript.
- The selected-email view should lead with:
  - current classification
  - handling status
  - short plain-English reason
  - `Correct / Teach`
- Reasoning should use a split presentation:
  - short explanation by default
  - deeper provenance and decision details only on demand
- Correction should be a combined fast relabel plus optional free-form explanation interaction, not just one or the other.
- The agent acknowledgment should remain short by default, but it must clearly state:
  - what changed now
  - what it thinks it learned
  - whether it generalized or deferred generalization
- Broader-change planning should be first-class product behavior. When the system infers that feedback would change other existing emails, it must compute and show proposed impact before applying it.
- The confirmation model for broader learning should support four outcomes:
  - apply only to this email
  - apply to matching emails too
  - use for future emails only
  - refine this
- Refinement should preserve the previous interpretation visibly rather than replacing it silently. The user needs to be able to compare the old and revised understanding.
- In the early Gmail release, any change affecting emails beyond the current one should require confirmation. That is a release-trust rule, not merely a tuning preference.
- The agent should be mostly reactive, but allowed to surface bounded prompts such as:
  - clarification needed
  - unsubscribe opportunities found
  - change confirmation pending
- Prompt budget should be productized:
  - ideal day: `0`
  - normal acceptable day: `1-3`
  - heavy day: up to `5`
  Beyond that, the system should batch and summarize rather than continuing to interrupt.
- Unanswered prompts should not block the whole system. The affected decision should remain in a safe current state and stay available for later follow-up.
- The daily dashboard should remain operational-first:
  - what came in
  - what was categorized
  - what was auto-handled
  - what needs attention
  - what unsubscribe opportunities were found
  A small learning-progress section is acceptable but should stay secondary.
- The sidebar should show a compact daily summary and open or hand off to a fuller dashboard view for deeper inspection.
- Unsubscribe should be split across surfaces:
  - quick contextual signal and simple action in the sidebar when obvious
  - fuller family-level selection, preview, and confirmation in the expanded unsubscribe view
- The correction conversation model should be stored as structured product interaction state rather than being hardwired to one UI surface. This preserves the ability to evolve from companion sidebar to more thread-native rendering later.
- Provider-specific selection context should feed a common product layer. The Gmail sidebar implementation should not embed product logic inside Gmail-specific DOM assumptions beyond what is needed to identify the selected message and render the panel.
- Existing backend capabilities should be reused where possible:
  - current classification/runtime artifacts for selected-email status
  - current founder-feedback and memory logic for learning candidates
  - current unsubscribe inventory and execution flow for subscription handling
  - current reporting/readiness infrastructure for compact daily summary inputs
- The product should visibly distinguish agent interaction from actual email content. Even if a later iteration becomes more native-feeling, the system should not confuse users into thinking the agent has literally sent an email when it has not.

## Testing Decisions

- Good tests should prove user-visible behavior of the Gmail companion experience and its contracts, not internal DOM implementation details or helper wiring.
- Prefer the highest seams available:
  - sidebar application state and selected-email contract
  - correction conversation and impact-confirmation APIs
  - immediate write/apply behavior after confirmation
  - compact daily summary rendering contracts
  - unsubscribe quick-action and handoff behavior
- Existing prior art in the repo already exists for:
  - local browser review UI behavior
  - unified review queue behavior
  - founder-answer application and memory-impact behavior
  - unsubscribe selection and execution flows
  - runtime cascade and readiness reports
- The sidebar slice should be tested first against:
  - selected-email status rendering
  - minimized/default state
  - compact summary behavior
  - safe behavior when no current email is selected
- The correction/teaching slice should be tested first against:
  - one-email correction
  - broader impact estimation
  - confirmation-first behavior for multi-email changes
  - refine-this compare flow
  - immediate visible update after confirmation
- The unsubscribe slice should be tested first against:
  - current-email unsubscribe availability
  - quick-action cases
  - handoff into fuller family-level unsubscribe flow
  - explicit confirmation before execution
- Gmail release hardening tests should emphasize:
  - live selected-email context continuity
  - stable agent acknowledgment loop
  - bounded prompting behavior
  - recoverability when the user ignores clarifications

## Out of Scope

- shipping ProtonMail as part of the first Gmail release
- team/shared-inbox workflows
- delete, trash, broad archive, send, or reply automation
- pretending the workbench/dashboard is the primary release surface
- forcing the first Gmail release to feel fully native-thread-integrated before the robust companion model is proven
- unlimited proactive prompting by the agent
- silent multi-email reclassification in the early trust model
- building a generic provider platform before the Gmail release is solid

## Further Notes

- The classifier and memory milestone is complete. The next risk is no longer backend classification leverage; it is the productization of that leverage into an inbox-native experience.
- The Gmail release should be treated as a product-surface milestone, not another backend-accuracy milestone.
- The most important distinction to preserve in execution is:
  - inbox is primary
  - dashboard/workbench is secondary
- The architecture should preserve a path to a later more magical inbox-native rendering model, but the first serious version should optimize for robustness and releaseability rather than illusion.
