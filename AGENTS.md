# AGENTS.md

## Purpose

Threadwise is a human-in-the-loop email-triage product. Keep work bounded, auditable, and tied to an approved product decision or implementation slice.

## Route the task

Choose the shortest branch that fits the work:

- **Fuzzy product work:** use `/grill-me` until alignment is approved, turn that alignment into a PRD, split it into vertical slices, and triage the next slice.
- **Existing slice or issue:** confirm it is current and implementation-ready, then implement only that bounded slice.
- **Confirmed in-scope QA defect:** record reproducible evidence, fix the isolated behavior, add automated regression coverage at the user-facing seam or record why it cannot be automated, rerun the affected paths, and continue the requested QA.

Run `/triage` or equivalent issue triage before implementing a raw idea, stale issue, or unverified external report. A current issue that is already marked ready does not need to repeat earlier product-planning steps.

For QA evidence, distinguish `LIVE`, `AUTOMATED`, `PASS`, `FAIL`, and `BLOCKED`.

## Source of truth

Before product planning or implementation, read `CONTEXT.md` and the current PRD or issue it identifies. `CONTEXT.md` owns the current stage, read order, trust order, and historical/current document boundary.

Treat the founder's current request and its current task-specific PRD or triaged issue as the implementation authority, subject to the approval gates below.

## Implementation contract

- Keep changes small, reviewable, and inside the approved slice.
- Preserve existing product behavior and design unless the task explicitly changes them.
- Protect existing behavior with tests or explicit characterization before refactoring it.
- Use red → green → refactor: prove the desired behavior, make the smallest passing change, then perform only behavior-preserving cleanup needed for clarity or testability.
- Run the narrowest affected checks. Run the repository-wide test suite when shared infrastructure or more than one feature area changes.
- For email parsing, provider integrations, authentication, classification, rules, scheduling, vector search, or background jobs, inspect suitable existing tools and open-source patterns before building a generic subsystem.

`.hermes.md` guides Hermes. Work delegated from Hermes follows the same implementation contract and approval gates as direct Codex work.

## Approval gates

Proceed independently inside an approved slice. Ask the founder before:

- changing product scope or a locked product decision
- accessing private email, credentials, OAuth, or a live inbox
- sending email or executing unsubscribe, delete, trash, archive, label, or other provider writes
- adding an external integration, dependency, service, or framework
- taking a destructive, security-sensitive, materially costly, or difficult-to-reverse action

When a QA fix would cross one of these gates or require a new product decision, report the reproduced defect and request direction before implementation.

## Durable artifacts and handoffs

Create product documents only when the active workflow calls for them:

- PRDs record approved product scope.
- Issues describe bounded vertical slices.
- Checkpoints capture milestone state.
- ADRs record hard-to-reverse decisions.
- Handoffs transfer unfinished work between agents or sessions.

Give durable documents that could be mistaken for current a `Status`, `Current as of`, and, when applicable, `Superseded by` header.

Before transferring or ending unfinished work that another session must continue, write or update a handoff in `docs/handoff/`. It is complete when it names the current source-of-truth documents, completed work, validation, risks, and the next bounded step.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues. See `docs/agents/issue-tracker.md` for operations.

### Triage labels

Use the repository's mapped public labels for the five canonical triage roles. See `docs/agents/triage-labels.md` for the authoritative mapping.

### Domain docs

This is a single-context repository. See `docs/agents/domain.md` for how skills consume `CONTEXT.md` and relevant ADRs.

## Completion

Implementation work is complete when:

- every acceptance criterion in the current task-specific PRD or triaged issue is satisfied
- the affected checks pass, including the repository-wide suite when required by the implementation contract
- affected user paths are rerun after a QA fix
- current source-of-truth documents named by the task are updated when their claims changed
- the founder receives a plain-English summary of changes, decisions, validation, risks, and the recommended next step

## Learning capture

If `.learning/INBOX.md` exists, append at most three terse candidates after a task changes production behavior when they are novel, recurring, architecturally important, or substantially delegated. Skip this when nothing qualifies. Read no other `.learning/` files and run no teaching workflow unless the founder invokes `$learn-from-work`.
