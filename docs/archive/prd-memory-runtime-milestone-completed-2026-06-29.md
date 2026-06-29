# PRD

Status: Completed bounded-slice PRD
Current as of: 2026-06-29
Builds on: `docs/v2-alignment.md`, `docs/checkpoints/current-operating-model-2026-06-22.md`, `docs/issues/056-read-only-two-inbox-shadow-classifier-evaluation.md`
Supersedes as current planning focus: the prior Gmail whole-inbox readiness PRD at this path
Related decisions: `docs/decisions/gmail-bounded-autonomy.md`, `docs/decisions/gmail-whole-inbox-readiness-policy.md`
First implementation slice: `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`

This PRD's milestone is now complete:

- unified review queue landed
- founder feedback loop landed
- runtime cascade reached under `10%` unresolved on the current stored corpora
- queue was drained and compiled-rule rebuild path was hardened

This document remains the source for the completed memory/runtime hardening tranche.

It is not the current product-definition brief for the next release.

The next bounded PRD should cover the Gmail inbox companion release:

- browser-based inbox companion sidebar
- in-inbox `Correct / Teach`
- short conversational acknowledgments
- daily summary and unsubscribe actions in the Gmail surface

## Problem Statement

The repo already proves a bounded Gmail daily workflow, provider-aware local artifacts, ProtonMail read-only import/live fetch, and a newly recovered Hotmail read-only browser corpus. That is enough to answer the original MVP question.

The current product problem has shifted.

The founder does not want to manually review thousands of messages or maintain an ever-growing deterministic rule tree for every new sender family. A system that only says "teach me another rule" when unseen mail arrives is not providing enough value. The founder wants the assistant to generalize better from full email context, ask a small number of high-leverage preference questions, remember accepted decisions, and use an LLM in a disciplined daily cascade rather than only as a one-off offline helper.

There is also a trust problem:

- Gmail reviewed history is strong but training-adjacent.
- ProtonMail remains a discovery corpus with a high unlabeled rate.
- Hotmail is now a large out-of-distribution shadow corpus and exposes how weak the current deterministic classifier is on novel mail families.
- Spam, phishing, and security-sensitive mail are not the same problem as ordinary retrieval categories and should not be treated as just another hand-authored rule lane.

The next bounded milestone is therefore no longer "tighten Gmail readiness" in isolation. It is to define and prove a memory-first, LLM-assisted inbox classification path that reduces manual work while preserving explicit safety boundaries and scientific discipline.

## Solution

Define and implement a bounded multi-inbox classification operating model with four layers:

1. deterministic/provider-safe heuristics for obvious recurring patterns
2. durable memory from accepted family-level decisions and preference answers
3. LLM-backed structured suggestions for unresolved or novel families
4. explicit human follow-up only for ambiguous, preference-sensitive, or safety-sensitive cases

The system should not ask the founder to review 1.7k messages individually. Instead, it should:

- ingest and preserve large local provider-separated corpora
- split shadow corpora by recurring sender/normalized-subject family into discovery, validation, and holdout buckets
- generate family-level candidate suggestions from full message context
- ask compact preference-setting questions where the main uncertainty is founder preference rather than taxonomy
- persist accepted decisions as provider-scoped local memory
- re-measure projected impact on validation and holdout before claiming an improvement

The daily production target is not "LLM on every message forever" and not "LLM only helps author rules once." The intended steady-state is a cascade where repeated known families are resolved cheaply by memory and deterministic logic, while the LLM remains in the daily path for genuinely novel, ambiguous, or safety-sensitive mail.

## User Stories

1. As the inbox owner, I want the assistant to learn from recurring message families, so that I do not classify the same kind of mail over and over.
2. As the inbox owner, I want the assistant to review message families rather than thousands of individual emails, so that the setup burden stays practical.
3. As the inbox owner, I want the assistant to use the full email context when judging new mail, so that it can do better than sender-plus-subject heuristics.
4. As the inbox owner, I want the assistant to ask a small number of high-leverage preference questions, so that preference-sensitive categories can be resolved quickly.
5. As the inbox owner, I want accepted family decisions to persist as memory, so that future similar mail is handled consistently.
6. As the inbox owner, I want rejected candidate suggestions to stay rejected, so that the system does not keep resurfacing the same bad idea.
7. As the inbox owner, I want the assistant to keep Gmail, ProtonMail, and Hotmail evidence separated, so that evaluation claims stay honest.
8. As the inbox owner, I want shadow-provider suggestions to remain read-only until explicitly accepted, so that experimentation does not mutate live inboxes.
9. As the inbox owner, I want daily operation to use cheap memory and rules first, so that the cost and latency of the system stay reasonable.
10. As the inbox owner, I want the LLM to remain available for unresolved mail, so that the assistant can generalize beyond exact handwritten rules.
11. As the inbox owner, I want the assistant to treat phishing, account compromise, and suspicious mail as a distinct safety lane, so that dangerous mail is not flattened into ordinary taxonomy decisions.
12. As the inbox owner, I want the system to show where a suggested decision came from, so that I can trust and debug its behavior.
13. As the inbox owner, I want the assistant to tell me when a result comes from deterministic logic, accepted memory, or an LLM-backed suggestion, so that I understand the trust level.
14. As the inbox owner, I want model-backed suggestions to be stored locally as structured candidates rather than silently applied, so that review stays explicit.
15. As the inbox owner, I want accepted candidate memory to be provider-scoped when appropriate, so that Hotmail discoveries do not accidentally corrupt Gmail behavior.
16. As the inbox owner, I want validation and holdout evidence to remain usable after discovery tuning, so that improvements can be measured honestly.
17. As the product lead, I want a written contamination rule for shadow corpora, so that agents do not overclaim generalization from partially-exposed datasets.
18. As the product lead, I want the new PRD to separate memory, eval, family review, runtime cascade, and security handling into bounded slices, so that work can be parallelized safely.
19. As the product lead, I want multi-agent orchestration only on slices with low overlap, so that concurrent work does not corrupt shared artifacts or planning.
20. As the product lead, I want the first slices to improve evidence quality and review leverage before building a broad runtime agent, so that later product claims rest on solid footing.
21. As an agent working later, I want clear seams for corpus eval, candidate memory, accepted-rule export, and runtime cascade projection, so that I can extend the system without re-litigating the architecture.
22. As an agent working later, I want the current PRD to state that deterministic rules alone are insufficient, so that I do not mistake a useful fallback layer for the actual product strategy.

## Implementation Decisions

- Replace the old single-focus Gmail-readiness planning lane with a new bounded multi-inbox classification lane.
- Keep Gmail write boundaries unchanged. This PRD is about classification, memory, evaluation, and review leverage, not about expanding mutation scope.
- Keep ProtonMail and Hotmail read-only in provider terms. All new work should continue to operate on local artifacts unless a later approved slice explicitly broadens scope.
- Treat Gmail reviewed data as a regression benchmark, not as a pristine unseen test set.
- Treat shadow corpora as family-split evidence buckets:
  - discovery for candidate generation and founder review
  - validation for post-tuning checks
  - holdout for internal generalization checks, subject to explicit contamination rules
- Make family-level clustering the primary review unit for shadow corpora. Individual message review remains available as an exception path, not the default setup path.
- Preserve the distinction between:
  - deterministic rules
  - accepted durable memory
  - model-backed structured suggestions
  - reviewed final outcomes
- Use provider-scoped accepted memory when exported from shadow corpora unless a later reviewed decision explicitly broadens it.
- Keep model output structured. Candidate artifacts should carry:
  - provider
  - family keys
  - suggested labels
  - rationale
  - evidence terms
  - status
  - accepted/rejected notes
- The runtime target is a cascade, not a single classifier:
  - deterministic/provider-safe pass
  - accepted memory pass
  - LLM escalation for novel or uncertain cases
  - explicit human follow-up for unresolved or safety-sensitive cases
- Introduce a separate security/suspicion decision lane rather than assuming the current taxonomy is enough for phishing and well-made malicious mail.
- Prefer local CLI and local artifact seams first. A larger browser UI or end-user workbench should be justified by a bounded review slice, not assumed upfront.
- Avoid claiming that a future LLM call is required for every message. The intended design is selective LLM use on the unresolved slice, not full-message always-on inference.
- Multi-agent orchestration is appropriate only for slices with minimal shared write overlap. In practice that means:
  - eval contract / contamination rules
  - family review artifact generation
  - candidate memory tooling
  - runtime cascade prototype
  - security-lane prototype
  These can be parallelized once their interfaces are fixed, but not before.

## Testing Decisions

- Good tests should prove user-visible operator behavior and artifact semantics, not helper implementation details.
- Prefer the highest seam available:
  - corpus-eval CLI behavior
  - suggestion-memory CLI behavior
  - persisted local artifact contracts
  - runtime cascade projection over stored corpora
  - family-level review artifacts
- Existing prior art already exists in:
  - corpus eval tests
  - shadow label eval tests
  - teachable rule memory tests
  - local browser review UI tests
  - stored batch review store tests
- The early slices should test:
  - family-split stability and contamination handling
  - candidate-memory durability across refreshes
  - accepted-rule export behavior, including provider scoping
  - projection of accepted memory on stored corpora without regressing Gmail benchmark behavior
  - explicit review-state transitions for pending, accepted, and rejected candidates
  - distinction between deterministic matches, memory matches, and model-suggested candidates in persisted artifacts
- The runtime-cascade slice should be tested first over stored corpora rather than live inboxes.
- Security-lane tests should focus on externally visible behavior such as escalation, isolation, and artifact labeling, not speculative low-level model internals.

## Out of Scope

- expanding Gmail mutation beyond the current bounded policy
- ProtonMail or Hotmail provider-side mutation
- delete, trash, broad archive, send, or reply automation
- claiming a pristine publication-grade benchmark from already-inspected shadow corpora
- building a single monolithic always-on LLM classifier that handles every email identically
- forcing the founder to review the entire Hotmail corpus message by message
- broad multi-user support
- background scheduling as part of the first slices
- replacing the taxonomy wholesale before family-level evidence and founder preferences are clearer

## Further Notes

- The core product bet is not "more deterministic rules." It is "memory-first, LLM-assisted classification with explicit evaluation discipline."
- The immediate product leverage is founder review of high-value families and preferences, not broad autonomous runtime behavior on day one.
- The corpus-eval artifacts and local suggestion memory already in the repo are valuable exploratory assets, but they should now be pulled back under a current PRD and issue sequence.
- Because Hotmail was used to debug ingestion and inspect aggregate behavior, it should be treated as a strong shadow corpus with explicit contamination notes, not as a never-seen pristine final exam.
