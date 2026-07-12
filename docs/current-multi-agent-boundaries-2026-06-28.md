Status: Current coordination note
Current as of: 2026-06-29
Owner slice: `docs/issues/062-define-multi-agent-boundaries-for-llm-assisted-inbox-work.md`
Builds on: `docs/prd.md`, `docs/issues/057-freeze-multi-inbox-eval-contract-and-contamination-rules.md`
Scope: Coordination only. This note does not define evaluation semantics or runtime behavior.

# Purpose

This note exists so later agents can tell whether a proposed parallel slice is safe without re-reading old handoffs or inferring concurrency rules from the codebase.

The current repo has several local JSON artifacts that are overwritten in place. Those paths require serialized writes even when the underlying product slices are logically related but not identical.

# Coordination Rules

## 1. One semantic owner per concern

- `057` owns evaluation-contract meaning, contamination rules, trust language, and allowed evidence claims.
- `062` owns only concurrency boundaries, shared-path warnings, and sequencing guidance.
- Any slice other than `057` may consume current eval artifacts, but should not redefine what those artifacts are allowed to prove.

## 2. Prefer read-only parallelism, serialize write-heavy work

- Parallel work is safe when agents read the same corpora but write only to disjoint docs or isolated output paths.
- Parallel work is not safe when two agents rewrite the same JSON memory file, processed-id file, or shared report path.
- If a slice needs to both read and rewrite a shared local artifact, treat that slice as single-agent unless the write target is explicitly isolated first.

## 3. Never rely on "latest file on disk" during concurrent runs

- `data/classifier_eval/evaluations/` and provider `reports/` directories can receive multiple timestamped files.
- In concurrent work, consumers must use explicit file paths or explicit artifact IDs.
- Do not claim evidence from "the newest report" when multiple agents can create reports in the same directory.

# Shared Local Artifacts Requiring Serialized Writes

## Classifier eval and shadow-memory artifacts

These paths are single-writer:

- `data/classifier_eval/shadow_suggestion_memory.json`
- `data/classifier_eval/accepted_shadow_teachable_rules.json`
- `data/classifier_eval/unified_review_queue.json`
- `data/classifier_eval/evaluations/*.json` when a consumer assumes one canonical fresh report

Practical rule:

- Only one agent at a time should refresh shadow suggestion memory or export accepted shadow rules.
- Only one agent at a time should rebuild or review-apply the unified review queue unless each agent is scoped to disjoint copied output roots.
- Multiple agents may generate eval reports only if each run is treated as append-only and all downstream consumers use explicit report paths.

## Provider fetch state

These paths are single-writer per provider:

- `data/gmail_fetch/processed_message_ids.json`
- `data/protonmail_fetch/processed_message_ids.json`
- `data/outlookmail_fetch/processed_message_ids.json`
- provider batch directories under:
  - `data/gmail_fetch/batches/`
  - `data/protonmail_fetch/batches/`
  - `data/outlookmail_fetch/batches/`

Practical rule:

- Run at most one fetch/backfill lane per provider at a time.
- Do not run two Hotmail fetch jobs concurrently against `data/outlookmail_fetch/`.
- Do not mix a fetch job and an artifact-rewriting migration in the same provider storage tree without sequencing them.

## Provider-local review memory and action logs

These paths are single-writer:

- `data/gmail_fetch/teachable_classification_rules.json` when present
- `data/gmail_fetch/evaluations/*-preferences.json`
- `data/gmail_fetch/unsubscribe_selections.json`
- `data/gmail_fetch/unsubscribe_execution_audit.json`
- Gmail writeback and inbox-removal status files under `data/gmail_fetch/*_write_*.json` and `data/gmail_fetch/*_inbox_removal_*.json`

Practical rule:

- Keep Gmail teaching/review/writeback work single-agent unless each agent is explicitly scoped to disjoint batch IDs and disjoint output files.

## Credentials and browser profiles

These paths should stay single-agent and should not be shared across autonomous runs:

- `data/gmail_credentials/`
- `data/protonmail_credentials/`
- `data/outlookmail_credentials/`
- `data/outlookmail_browser_profile/`
- `data/outlookmail_browser_profile_chrome2/`
- `data/outlookmail_browser_profile_pw/`
- `data/outlookmail_browser_profile_pw2/`

Practical rule:

- Treat credential material and live browser-profile state as exclusive resources.
- Do not run parallel experiments that point at the same live browser profile directory.

# Parallelization Guidance By Slice

## Safe to parallelize now with a narrow contract

### `057` + `059` + `062`

This is the highest-throughput safe bundle, but only under these constraints:

- `057` may define trust language and eval-contract meaning.
- `059` may improve durability, review-state handling, provider scoping, and refresh safety in suggestion memory.
- `059` must not redefine eval semantics owned by `057`.
- `062` may write docs only.
- `062` must not invent trust or runtime policy.

### `058` in parallel with docs-only work

- `058` can proceed once `057` has frozen the evidence contract it relies on.
- `058` is safe alongside docs-only work that does not rewrite shared shadow-memory artifacts.
- `058` becomes unsafe if it directly mutates `shadow_suggestion_memory.json` or exported accepted-rule files while `059` is also rewriting them.

## Parallelizable only after interfaces are fixed

### `060`

- `060` depends on the memory/export seams stabilized by `059`.
- It should not start broad runtime work until the accepted-memory artifact contract is stable enough that it will not be churned mid-slice.

### `061`

- `061` should wait for the runtime cascade seam from `060`.
- Security-lane work touches overlapping routing and escalation surfaces, so it should not race a still-moving runtime slice.

# Work That Should Stay Single-Agent

Keep these classes of work single-agent unless a later note explicitly narrows them further:

- any slice rewriting `data/classifier_eval/shadow_suggestion_memory.json`
- any slice exporting `data/classifier_eval/accepted_shadow_teachable_rules.json`
- any runtime slice that both consumes and rewrites teachable-rule memory
- any live provider fetch or backfill into the same provider storage tree
- any live Gmail mutation, unsubscribe execution, or inbox-removal run
- any work using the same live Outlook/Brave browser profile directory
- any cross-cutting refactor that edits `src/classifier_corpus_eval.py`, `src/shadow_suggestion_memory.py`, and runtime entrypoints in one pass

# Practical Multi-Agent Operating Pattern

For this repo, the default safe pattern is:

1. Put one agent on the current contract/coordination doc slice.
2. Put separate agents on bounded implementation slices only if their write targets are disjoint.
3. Require each agent to name the exact files it expects to write before implementation starts.
4. Serialize merges for any slice that touches shared JSON memory or provider storage trees.
5. Prefer append-only outputs with explicit IDs over in-place rewrites whenever a slice is likely to run in parallel later.

# Current Recommendation

Use this sequence for the current LLM-assisted inbox work:

1. `057` as the semantic anchor.
2. In parallel, `059` and `062` with the constraints above.
3. `058` after `057`, and not concurrently with any slice rewriting `shadow_suggestion_memory.json` unless outputs are isolated.
4. `060` after `059`.
5. `061` after `060`.

If a proposed slice cannot explain which shared local artifacts it reads and writes, it is not ready for multi-agent parallelization in this repo.

# Gmail Companion Release Recommendation

For the current Gmail inbox companion release, use this sequence:

1. `063` alone.
2. After `063` freezes the sidebar and selected-email contract, run `064` and `065` in parallel if their write targets stay separated.
3. `066` only after `064` and `065` are merged.

## Why `063` should stay single-agent

`063` defines the shared product shell:

- Gmail sidebar mount/render behavior
- selected-email context contract
- sidebar state contract

If two agents race those interfaces, the later slices will merge badly and re-litigate core assumptions. That is not useful parallelism.

## Why `064` and `065` are the best parallel pair

After `063`, these slices are mostly separate product lanes:

- `064` owns the correction conversation, acknowledgment model, impact preview, and confirmation flow
- `065` owns the operational daily-summary presentation, current-email unsubscribe signal, and handoff into fuller unsubscribe review

They still touch the sidebar, but they should be able to coexist if they agree not to rewrite each other's state contracts and if each agent names exact write targets before coding starts.

## Practical guardrails for `064` and `065`

- Freeze the selected-email contract first in `063`.
- Keep conversation state owned by `064`.
- Keep daily-summary and unsubscribe presentation state owned by `065`.
- Avoid broad shared refactors in sidebar rendering while both slices are active.
- Merge one slice before starting the final hardening pass in `066`.
