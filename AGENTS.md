# AGENTS.md

## Project purpose

This repo is for building and iterating on Threadwise, a human-in-the-loop AI inbox triage product.

The product is no longer purely fuzzy discovery. The repo already contains a working Gmail MVP plus newer reporting, ProtonMail, and unsubscribe slices. Some scope is still exploratory, so the docs must clearly separate historical artifacts from the current operating model.

## Working method

Use a Matt Pocock-style AI-assisted development workflow:

1. Start with grill-me / alignment while the idea is fuzzy.
2. Turn approved alignment into a PRD.
3. Break the PRD into small vertical slices.
4. Triage the next slice or issue until it is implementation-ready.
5. Implement one approved bounded slice at a time.
6. Prefer test-first implementation once coding begins.
7. End major steps with a handoff summary and update any stale current-state docs.

Do not skip ahead in this sequence unless the founder explicitly asks.

## QA follow-through

When the founder asks for product QA or live user-path testing, treat confirmed in-scope defects as implementation work, not report-only findings:

- record the failure and its reproduction evidence
- fix it once the baseline or current test loop has isolated the behavior
- add regression coverage at the real user-facing seam where practical
- rerun the affected automated and live user paths after the fix
- continue the requested testing instead of stopping after filing an issue

Stop and ask only when a fix requires a materially new product decision, expands scope beyond the requested workflow, or crosses a sensitive or destructive-action boundary. Preserve the distinction between `LIVE`, `AUTOMATED`, `PASS`, `FAIL`, and `BLOCKED` evidence in QA reporting.

## Current-stage awareness

Treat alignment, PRD, issue, checkpoint, implementation, review, and handoff docs as different stages with different trust levels.

Do not treat an old alignment, PRD, or checkpoint as the current source of truth unless it is marked current or explicitly referenced by the latest current-state doc.

Historical planning and checkpoint docs should usually live under `docs/archive/` once they are no longer active inputs to the current stage.

When docs disagree, first identify which artifact is meant to describe the current stage before making product or implementation decisions.

## Current doc entrypoint

Before substantial implementation or planning work, read:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/v2-alignment.md`
4. `docs/prd.md` when a current bounded slice is active
5. `docs/checkpoints/current-operating-model-2026-06-22.md`
6. the relevant current issue if one exists

Do not infer approval from `docs/v2-issue-map.md`, archived V1 docs, or old handoffs alone.

## Scope control

Do not invent product scope.

Do not create broad architecture, large frameworks, or generic plumbing before the first useful vertical slice is clear.

Keep changes small, reviewable, and tied to the current approved step.

## Hermes + Codex workflow

This file guides Codex. `.hermes.md` guides Hermes.

When Hermes delegates implementation work here:

- prefer small, reviewable diffs over broad rewrites
- preserve current product behavior unless the task explicitly changes it
- preserve the current Threadwise aesthetic and interaction language unless the task explicitly changes design
- do not add new dependencies, services, or frameworks without explicit approval
- do not perform destructive email or provider actions; keep live-provider behavior bounded, auditable, and explicitly approved
- run the relevant checks before reporting completion, usually the narrowest affected `python3 -m unittest ...` commands and the repo-wide `python3 -m unittest discover -s tests` when the change is broad enough to justify it
- if a task touches live inbox, credentials, OAuth, unsubscribe execution, delete/trash/archive behavior, or provider write paths, stop and ask before proceeding

## Product artifacts

Use docs for durable product artifacts when needed:

- `CONTEXT.md` for the current stage, read order, and trust order
- `docs/v2-alignment.md` or the latest clearly marked current alignment doc for product understanding
- `docs/prd.md` for the current bounded slice when one exists
- versioned PRDs under `docs/` when multiple current or historical PRDs need to stay linkable
- `docs/v2-issue-map.md` for candidate next-slice mapping only, not implementation approval
- `docs/issues/` or an external tracker for vertical slices
- `docs/handoff/` for end-of-step summaries and context transfer
- `docs/checkpoints/` for milestone state snapshots when the repo has moved materially beyond an older PRD or alignment
- `docs/archive/` for historical alignments, PRDs, checkpoints, and guides that should stay linkable without driving current decisions
- ADRs only for hard-to-reverse decisions

When a durable doc might be mistaken for current, add short status headers such as `Status`, `Current as of`, and `Superseded by` or `Historical context`.

Do not create these artifacts prematurely. Create them only when the current workflow step calls for them.

## Agent skills

### Issue tracker

Issues for this repo are tracked in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

This repo uses the default Matt Pocock triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This repo is treated as a single-context product repo. Skills should read the root `CONTEXT.md` if present and `docs/adr/` when it exists. See `docs/agents/domain.md`.

## Triage gate

Before implementing a slice, run `/triage` or perform equivalent issue triage so the work is explicitly ready for bounded implementation.

A raw idea, a stale issue, or an old checkpoint is not an implementation brief.

## Refactoring

Refactor only after behavior is protected by tests or after the current behavior has been explicitly characterized.

During implementation, follow red -> green -> refactor:
- first prove the desired behavior with a test where practical
- then implement the smallest change that passes
- then perform only behavior-preserving cleanup needed for clarity, locality, or testability

Do not perform broad opportunistic rewrites during feature work. If a refactor is larger than the current slice, create a separate issue or architecture-improvement note.

## Context-window and handoff discipline

When the current task spans enough ground that the context window no longer comfortably holds the reasoning, write or update a handoff in `docs/handoff/` before continuing, switching branches, or handing work to another agent/session.

Each handoff should point to the current source-of-truth docs, note what has become historical, and record the next bounded step.

## Sensitive areas

This project may eventually involve private email.

Treat the following as sensitive:

- private email content
- credentials
- OAuth
- inbox access
- sending email
- deleting email
- archiving email
- external integrations
- real-world actions on a user's inbox

Stop and ask before doing anything involving those areas.

## Reuse-before-build

Before designing or implementing meaningful components, consider whether an existing tool, API, library, open-source project, or workflow should be reused, wrapped, or studied first.

This especially applies to:

- email parsing
- Gmail/Proton/provider integrations
- authentication
- classification
- rules engines
- scheduling
- vector search
- background jobs

Do not turn every small task into a research project, but do not build generic subsystems blindly.

## Founder approval

The founder/product lead makes final product decisions.

Ask for approval before product-scope changes, destructive actions, security-sensitive actions, external integrations, real-world email actions, or materially costly choices.

## Task summaries

At the end of repo-editing or implementation tasks, provide a plain-English summary covering:

- what changed
- key decisions
- validation performed
- risks or open questions
- recommended next step
