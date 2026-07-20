# Threadwise Architecture Refactor Closeout

Status: Complete
Current as of: 2026-07-20
Branch: `codex/runtime-a042b03`
Builds on: `CONTEXT.md`, `docs/v2-alignment.md`, the 2026-07-20 architecture reviews, and the bounded handoffs linked below

## Outcome

The full recommended behavior-preserving architecture refactor is complete. The original Gmail companion application has been deepened into cohesive modules:

- `gmail_companion_rendering.py` owns complete page composition behind five page interfaces.
- `companion_teaching_workflow.py` owns the local teaching lifecycle and exact outcome semantics.
- `gmail_teaching_adapter.py` owns Gmail-specific teaching preview and mutation mechanics behind two adapter interfaces.
- `companion_runtime_state.py` owns cached sidebar/harness snapshots, invalidation, handled-review state, and asynchronous refresh.
- `rfc822_readable_content.py` owns shared readable-content extraction for RFC822 providers.
- `cli_paths.py` remains the shared command-path module used by the refactored command entrypoints.

`GmailCompanionApp` decreased from 5,396 lines at the initial review to 1,196 lines. It now concentrates request dispatch, product commands, analytics coordination, bounded provider entrypoints, and thin page/state compatibility methods.

## Deepening decisions

Implemented because they passed the deletion test:

- Complete rendering locality behind five interfaces.
- Complete local teaching lifecycle behind one workflow.
- Gmail teaching provider mechanics behind an immutable request and two adapter interfaces.
- Companion snapshots and cache semantics behind one runtime-state module.
- Shared RFC822 readable-content extraction across two real provider adapters.
- Shared command-path resolution across command entrypoints.

Deliberately not implemented:

- A canonical provider-message normalizer. Its interface would nearly match its implementation, Gmail has materially different payload semantics, and a generic provider framework is a current non-goal.
- A separate HTTP router. It would move the 370-line route tree while leaking the same broad command interface, so it would not increase depth or locality.
- Classifier splitting. `FixtureBatchClassifier` is already deep: two public methods hide roughly 3,000 lines of decision implementation.
- Unified-review splitting. `UnifiedReviewQueue` is already deep: four public methods hide roughly 700 lines of queue implementation.
- Further rendering splitting by file size. The renderer's five page interfaces intentionally hide its large static implementation.
- Removal of local-artifact compatibility helpers. Their preservation is an explicit completed registry decision; the registry already concentrates descriptors, paths, JSON behavior, and opt-in validation.

## Validation

- Every implemented seam was characterized with failing-first tests.
- Provider behavior was exercised only through fixtures and fake clients.
- `python3 -m unittest discover -s tests`: 730 tests passed after the final implementation checkpoint.
- Python compilation and diff whitespace checks passed throughout the checkpoints.
- The worktree was clean after each checkpoint commit.
- No live inbox, private email, credentials, OAuth session, extension session, unsubscribe execution, or real provider mutation was accessed.

## Checkpoints

- `docs/handoff/2026-07-20-rfc822-readable-content-and-cli-path-refactor.md`
- `docs/handoff/2026-07-20-gmail-companion-rendering-refactor.md`
- `docs/handoff/2026-07-20-companion-teaching-workflow-refactor.md`
- `docs/handoff/2026-07-20-gmail-teaching-adapter-refactor.md`
- `docs/handoff/2026-07-20-companion-runtime-state-refactor.md`

## Future work

Further architecture changes should be driven by a concrete product slice or demonstrated test friction. No Strong or Worth-exploring deepening candidate remains from the current review; the remaining theoretical moves are speculative or conflict with current product direction.
