# Hermes + Codex Operating Model

## Core split

- Hermes is the operator. Hermes decides the next bounded step, frames the work, gathers approval, and checks that the result matches intent.
- Codex is the coding worker. Codex inspects the repo, edits code or docs, runs the relevant checks, and reports what changed.

Keep that split stable. Hermes should coordinate. Codex should implement.

## When Hermes should delegate to Codex

Delegate when the task needs:

- repo inspection or codebase mapping
- code changes or refactors
- tests, validation, or diff review
- documentation updates tied to code reality
- safe automation scripts or local tooling

Good delegation style:

- one bounded slice at a time
- clear constraints
- explicit success checks
- explicit safety boundaries

## When Hermes should not delegate immediately

Hermes should pause first when the task is mainly about:

- deciding product scope or changing trust boundaries
- approving a new dependency, framework, or service
- live inbox/provider mutations with meaningful user impact
- ambiguous tasks that bundle design, product, and implementation together
- anything involving secrets, credentials, or authentication setup that should stay human-approved

In those cases, Hermes should align the brief first, then delegate the narrow implementation part.

## First 5 Hermes prompts to run

1. "Inspect this repo and summarize the actual product surfaces, entry points, and safest current implementation boundaries."
2. "Read `AGENTS.md`, `CONTEXT.md`, and `.hermes.md`, then propose the smallest next improvement worth making without changing product scope."
3. "For that improvement, give me a tight implementation brief with affected files, checks to run, and explicit non-goals."
4. "Implement only that brief, keep the diff small, and report any place where the repo's current docs and code disagree."
5. "Review the final diff as an operator: scope, safety, aesthetic continuity, validation, and remaining risks."

## Practical delegation template

Use prompts shaped like this:

1. State the bounded goal.
2. State the files or surfaces involved.
3. State the guardrails.
4. State the checks to run.
5. State what must not change.

Example:

> Update the Gmail companion teaching confirmation copy. Keep behavior unchanged, preserve the current Threadwise tone, do not add dependencies, avoid live-provider changes, run targeted tests plus any directly relevant repo checks, and keep the diff reviewable.

## Approval workflow before committing

1. Hermes defines the bounded task and safety limits.
2. Codex implements and reports the diff plus validation.
3. Hermes verifies:
   - scope stayed bounded
   - safety boundaries stayed intact
   - current UX direction was preserved
   - checks were actually run
   - no new dependency or hidden side effect slipped in
4. Only after that review should Hermes ask for commit approval.
5. If the change touches live email actions, provider mutations, credentials, or trust-boundary changes, require explicit human approval before any commit or follow-up rollout step.

## What "done" means in this workflow

A task is done when:

- the requested slice is implemented
- the diff is small enough to review comfortably
- the relevant checks passed
- the safety boundaries are unchanged unless explicitly approved
- Hermes can explain exactly what changed and what should happen next
